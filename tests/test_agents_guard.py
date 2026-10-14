"""P2 / 3b: the Guard is the pipeline's own deterministic check, wrapped; same results on the same drafts."""

import asyncio
import json

import pytest

from app.agents import tools
from app.agents.guard import GuardResult, guard_check
from app.explain.config import DEFAULT_EXPLAIN_CONFIG
from app.explain.menu import build_menu
from app.explain.narrator import TemplateNarrator
from app.explain.pipeline import check_menu_draft, run_moment
from app.explain.selector import select_moments
from app.generator.freeze import demo_paths
from app.generator.models import read_jsonl
from app.analytics import detect_moments
from app.publish.store import DEFAULT_RUN, ReplayNarrator
from tests.explain_helpers import moment_case


def run(coro):
    return asyncio.run(coro)


def _drafts():
    """(match events, moment, stored model template) for every selected moment of the demo run that has one."""
    data = json.loads(DEFAULT_RUN.read_text(encoding="utf-8"))
    run_matches = {m["match_id"]: m["moments"] for m in data["runs"][-1]["matches"]}
    out = []
    for _, _, path in demo_paths():
        events = read_jsonl(path)
        by_id = {m["id"]: m for m in run_matches.get(path.stem, [])}
        for moment in select_moments(detect_moments(events), DEFAULT_EXPLAIN_CONFIG):
            rec = by_id.get(moment.id)
            if rec and rec["source"] == "llm" and rec.get("template"):
                out.append(pytest.param(events, moment, rec["template"], id=moment.id))
    return out


DRAFTS = _drafts()


def test_there_are_stored_model_drafts_to_compare():
    assert len(DRAFTS) >= 10


@pytest.mark.parametrize("events,moment,template", DRAFTS)
def test_guard_gives_the_pipelines_verdict_text_and_claims(events, moment, template):
    menu = build_menu(moment, events)
    ctx = tools.slot_context(moment, events)
    g = run(guard_check(template, menu, ctx))
    items, _, _, claims, ids = check_menu_draft(template, menu, ctx)
    assert g.ok == (not items)
    assert g.codes == tuple(i.code for i in items)
    assert g.claim_ids == tuple(ids) and g.claims == tuple(claims)
    # the same draft through the whole pipeline gives the same text and the same pieces
    rec = run_moment(moment, ReplayNarrator(events, [{"id": moment.id, "type": moment.type, "period": moment.period,
                     "minute": moment.minute, "second": moment.second, "source": "llm", "template": template}],
                     "x"), events, config=DEFAULT_EXPLAIN_CONFIG.__class__(max_retries=0))
    if g.ok:
        assert rec.source == "llm"
        assert g.text == rec.text and g.parts == rec.parts
    else:
        assert rec.source == "template_fallback" and g.text is None and g.parts == ()


BAD_TEMPLATES = {
    "digit": "{clause:goal}, and 3 shots.",
    "number_word": "{clause:goal}, and three chances.",
    "unknown_id": "{clause:goal}, {value:nope}.",
    "raw_name": "{clause:goal}, said Murek.",
    "no_claim": "A good moment.",
    "empty": "",
}


@pytest.mark.parametrize("name", BAD_TEMPLATES)
def test_a_bad_template_is_rejected_with_coded_feedback_and_no_text(name):
    events, moment = moment_case("goal")
    menu = build_menu(moment, events)
    g = run(guard_check(BAD_TEMPLATES[name], menu, tools.slot_context(moment, events)))
    assert not g.ok and g.text is None and g.parts == () and g.codes
    fb = g.feedback(2)
    assert fb.attempt == 2 and fb.codes == g.codes
    rec = g.feedback_record(2)
    assert rec.attempt == 2 and rec.codes == g.codes
    assert all(e.source == "guard" for e in rec.entries)


def test_a_failing_verify_claim_rejects_the_draft():
    events, moment = moment_case("goal")
    menu = build_menu(moment, events)
    ctx = tools.slot_context(moment, events)
    # a menu whose claim value is wrong: verify_claim must stop it even though the template itself is clean
    from dataclasses import replace
    wrong = replace(menu.claims[0], claim=replace(menu.claims[0].claim, value=menu.claims[0].claim.value + 7))
    bad_menu = replace(menu, claims=(wrong, *menu.claims[1:]))
    g = run(guard_check("{clause:" + menu.clauses[0].id + "}.", bad_menu, ctx))
    assert not g.ok and any(i.source == "verify" for i in g.items) and g.text is None


def test_guard_result_is_immutable():
    events, moment = moment_case("goal")
    g = run(guard_check("{clause:goal}.", build_menu(moment, events), tools.slot_context(moment, events)))
    assert isinstance(g, GuardResult)
    with pytest.raises(Exception):
        g.ok = not g.ok  # type: ignore[misc]


def test_template_narration_still_passes_the_same_guard_unchanged():
    # sanity: nothing in the wrapper touches the pipeline's own template path
    events, moment = moment_case("red_card")
    assert run_moment(moment, TemplateNarrator(events), events).ok
