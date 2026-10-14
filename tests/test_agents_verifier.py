"""P2 / 3e: the Verifier checks meaning, can only reject, and its failure never blocks a card."""

import asyncio
import dataclasses
import json

import pytest

from app.agents import tools
from app.agents.guard import guard_check
from app.agents.limits import AgentsConfig, CallBudget
from app.agents.trace import Stopwatch
from app.agents.verifier import (
    CODES, EVAL_CLASSES, REASON_MAX_CHARS, VERIFIER_PROMPT, IssueOut, VerdictError, VerifierAgent, VerifierOut,
    VerifyResult, check_verdict, verifier_record,
)
from app.explain.menu import build_menu
from tests.agent_fakes import ScriptedClient, Sleep
from tests.explain_helpers import moment_case

PASS = json.dumps({"ok": True, "issues": []})


def run(coro):
    return asyncio.run(coro)


def passing_draft(menu, ctx):
    """The first one- or two-clause template the Guard accepts (the moment's primary claims need some of them)."""
    ids = [c.id for c in menu.clauses]
    for template in [f"{{clause:{a}}}." for a in ids] + [f"{{clause:{a}}}, and {{clause:{b}}}." for a in ids for b in ids if a != b]:
        g = run(guard_check(template, menu, ctx))
        if g.ok:
            return g
    raise AssertionError("no passing template")


def setup(case="goal"):
    events, moment = moment_case(case)
    menu = build_menu(moment, events)
    ctx = tools.slot_context(moment, events)
    return events, moment, ctx, passing_draft(menu, ctx)


def verify(client, case="goal", budget=None, **kw):
    events, moment, ctx, g = setup(case)
    a = VerifierAgent(events, client, budget=budget or CallBudget(20), model_tag="m", **kw)
    return run(a.verify(moment, g, ctx, build_menu(moment, events), attempt=1, clock=Stopwatch())), g


def reject(code="role_reversed", span=None, reason="the roles are swapped"):
    _, _, _, g = setup()
    span = span or g.text.split()[0]
    return json.dumps({"ok": False, "issues": [{"code": code, "span": span, "reason": reason}]})


# --- the closed verdict ------------------------------------------------------------------------------------


def test_the_code_set_is_closed_and_answers_the_evals_missed_classes():
    assert set(CODES) == {"wrong_slot_binding", "role_reversed", "event_wrong_claim", "qualitative_unsupported",
                          "unsupported_statement", "misleading_connector", "other_semantic"}
    assert set(EVAL_CLASSES) == set(CODES)
    from eval.inject import INJECTION_TYPES
    names = {t.name for t in INJECTION_TYPES}
    for code, classes in EVAL_CLASSES.items():
        assert set(classes) <= names, code
    # the three types the deterministic check misses (docs/EVAL.md) are all covered
    assert {"wrong_slot_binding", "role_reversed", "event_wrong_claim"} <= {c for cs in EVAL_CLASSES.values() for c in cs}


def test_every_code_is_explained_in_the_prompt():
    for code in CODES:
        assert code + ":" in VERIFIER_PROMPT


def test_the_verdict_has_no_field_for_text_or_numbers():
    assert set(VerifierOut.model_fields) == {"ok", "issues"}
    assert set(IssueOut.model_fields) == {"code", "span", "reason"}
    with pytest.raises(Exception):
        VerifierOut.model_validate_json('{"ok": true, "issues": [], "text": "better text"}')
    with pytest.raises(Exception):
        IssueOut(code="made_up", span="x", reason="y")
    # length limits are checked by check_verdict, not by the schema (see below)


def test_the_verifier_result_carries_no_text():
    assert {f.name for f in dataclasses.fields(VerifyResult)} == {"verdict", "feedback", "steps"}


@pytest.mark.parametrize("out,code", [
    (VerifierOut(ok=True, issues=[IssueOut(code="role_reversed", span="a", reason="r")]), "ok_with_issues"),
    (VerifierOut(ok=False, issues=[]), "reject_without_issue"),
    (VerifierOut(ok=False, issues=[IssueOut(code="role_reversed", span="some", reason="r" * (REASON_MAX_CHARS + 1))]), "reason_too_long"),
])
def test_an_inconsistent_verdict_is_refused(out, code):
    with pytest.raises(VerdictError) as e:
        check_verdict(out)
    assert e.value.code == code


# --- the record --------------------------------------------------------------------------------------------


def test_the_record_holds_text_pieces_claims_and_evidence_and_nothing_of_the_narrators_work():
    events, moment, ctx, g = setup("dominance_without_reward")
    rec = verifier_record(moment, g, events, ctx, build_menu(moment, events))
    assert set(rec) == {"moment", "teams", "text", "pieces", "claims", "clauses", "events"}
    assert rec["text"] == g.text and "".join(p["text"] for p in rec["pieces"]) == g.text
    assert {p["claim_id"] for p in rec["pieces"] if p["claim_id"]} <= {c["id"] for c in rec["claims"]}
    assert all({"id", "metric", "definition", "window", "team", "player", "value", "to", "evidence"} <= set(c) <= {"id", "metric", "definition", "window", "team", "player", "value", "from", "to", "evidence"} for c in rec["claims"])
    raw = json.dumps(rec)
    assert "{clause" not in raw and "{value" not in raw  # no placeholder template, no draft history


def test_the_record_refuses_a_draft_the_guard_rejected():
    events, moment, ctx, _ = setup()
    bad = run(guard_check("three shots", build_menu(moment, events), ctx))
    assert not bad.ok
    with pytest.raises(ValueError):
        verifier_record(moment, bad, events, ctx, build_menu(moment, events))


def test_the_call_is_the_verifier_prompt_plus_the_record():
    client = ScriptedClient(VerifierOut=PASS)
    verify(client)
    call = client.calls[0]
    assert call["model"] == "VerifierOut" and call["messages"][0]["content"] == VERIFIER_PROMPT
    assert set(json.loads(call["messages"][1]["content"])) == {"moment", "teams", "text", "pieces", "claims", "clauses", "events"}


# --- outcomes ----------------------------------------------------------------------------------------------


def test_a_clean_draft_passes_with_one_verify_step():
    r, _ = verify(ScriptedClient(VerifierOut=PASS))
    assert r.verdict == "pass" and r.feedback is None and r.narrator_feedback(1) is None
    (s,) = r.steps
    assert (s.step, s.agent, s.status, s.attempt) == ("verify", "verifier", "ok", 1)
    assert s.output == {"verdict": "pass", "issues": []} and s.tokens.input == 321 and s.input_ref == "drafts[1]"


def test_a_rejection_becomes_coded_feedback_for_the_narrator():
    r, g = verify(ScriptedClient(VerifierOut=reject("role_reversed", reason="swapped")))
    assert r.verdict == "reject" and r.feedback is not None
    assert r.feedback.codes == ("role_reversed",) and r.feedback.entries[0].source == "verifier"
    fb = r.narrator_feedback(1)
    assert fb.codes == ("role_reversed",) and fb.items[0].source == "verifier" and "swapped" in fb.items[0].fragment
    assert r.steps[0].output["verdict"] == "reject" and r.steps[0].output["issues"][0]["code"] == "role_reversed"


@pytest.mark.parametrize("script,reason,status", [
    (RuntimeError("down"), "client_error", "error"),
    (Sleep(5), "timeout", "timeout"),
    ("{not json", "invalid_output", "error"),
    (json.dumps({"ok": False, "issues": [{"code": "dance", "span": "x", "reason": "y"}]}), "invalid_output", "error"),
    (json.dumps({"ok": True, "issues": [{"code": "role_reversed", "span": "x", "reason": "y"}]}), "ok_with_issues", "error"),
])
def test_a_verifier_failure_is_an_error_verdict_with_a_verifier_error_step(script, reason, status):
    r, _ = verify(ScriptedClient(VerifierOut=script), agents=AgentsConfig(verifier_timeout_s=0.05))
    assert r.verdict == "error" and r.feedback is None
    (s,) = r.steps
    assert (s.step, s.status, s.output["reason"]) == ("verifier_error", status, reason)


def test_a_spent_budget_is_an_error_verdict_without_a_model_call():
    client = ScriptedClient(VerifierOut=PASS)
    r, _ = verify(client, budget=CallBudget(0))
    assert r.verdict == "error" and client.calls == [] and r.steps[0].step == "verifier_error"


def test_the_verifiers_answer_never_changes_the_guards_result():
    events, moment, ctx, g = setup()
    before = dataclasses.asdict(g)
    a = VerifierAgent(events, ScriptedClient(VerifierOut=reject()), budget=CallBudget(5))
    run(a.verify(moment, g, ctx, build_menu(moment, events), attempt=1, clock=Stopwatch()))
    assert dataclasses.asdict(g) == before and g.ok and g.text


def test_the_response_schemas_use_only_what_strict_structured_outputs_take():
    from openai.lib._pydantic import to_strict_json_schema

    from app.agents.analyst import AnalystOut

    for model in (VerifierOut, AnalystOut):
        raw = json.dumps(to_strict_json_schema(model))
        for keyword in ("minLength", "maxLength", "pattern", "minItems", "maxItems", "minimum", "maximum"):
            assert keyword not in raw, (model.__name__, keyword)
    assert set(json.loads(json.dumps(to_strict_json_schema(VerifierOut)))["required"]) == {"ok", "issues"}


def test_the_verifier_prompt_is_still_verifier_v1():
    import hashlib

    from app.agents.verifier import VERIFIER_VERSION

    assert VERIFIER_VERSION == "verifier-v1"
    assert hashlib.sha256(VERIFIER_PROMPT.encode()).hexdigest()[:16] == "e19185ba149f1a39"


# --- an unlocated span is still a rejection (P2 final round) -------------------------------------------------


@pytest.mark.parametrize("span", ["NOT IN THE TEXT", "", "   "])
def test_a_rejection_whose_span_is_not_in_the_text_is_still_a_rejection(span):
    script = json.dumps({"ok": False, "issues": [{"code": "role_reversed", "span": span, "reason": "roles swapped"}]})
    r, _ = verify(ScriptedClient(VerifierOut=script))
    assert r.verdict == "reject" and r.feedback is not None  # not a verifier_error
    entry = r.feedback.entries[0]
    assert (entry.source, entry.code, entry.fragment) == ("verifier", "role_reversed", None)
    (s,) = r.steps
    assert s.step == "verify" and s.status == "ok" and s.output["verdict"] == "reject"
    assert s.output["issues"] == [{"code": "role_reversed", "span": span, "reason": "roles swapped", "unlocated_span": True}]
    fb = r.narrator_feedback(1)
    assert fb.codes == ("role_reversed",) and fb.items[0].fragment is None


def test_a_located_span_is_marked_so_and_keeps_its_fragment():
    r, g = verify(ScriptedClient(VerifierOut=reject("role_reversed", reason="swapped")))
    assert r.steps[0].output["issues"][0]["unlocated_span"] is False
    assert r.feedback.entries[0].fragment.startswith(g.text.split()[0])


def test_the_narrator_gets_the_code_when_the_place_is_unknown():
    from app.agents.narrator_agent import narrator_messages
    from app.explain.config import DEFAULT_EXPLAIN_CONFIG

    script = json.dumps({"ok": False, "issues": [{"code": "qualitative_unsupported", "span": "nowhere", "reason": "hype"}]})
    r, _ = verify(ScriptedClient(VerifierOut=script))
    events, moment = moment_case("goal")
    user = narrator_messages(moment, events, "neutral", "en", r.narrator_feedback(1), DEFAULT_EXPLAIN_CONFIG,
                             build_menu(moment, events))[1]["content"]
    assert "[verifier] qualitative_unsupported" in user and "fragment=" not in user.split("FEEDBACK")[1]


def test_verifier_error_is_only_for_schema_timeout_or_exceptions():
    cases = {
        "invalid_output": "{not json",
        "ok_with_issues": json.dumps({"ok": True, "issues": [{"code": "role_reversed", "span": "x", "reason": "y"}]}),
        "reject_without_issue": json.dumps({"ok": False, "issues": []}),
        "reason_too_long": json.dumps({"ok": False, "issues": [{"code": "role_reversed", "span": "x", "reason": "r" * 300}]}),
    }
    for reason, script in cases.items():
        r, _ = verify(ScriptedClient(VerifierOut=script))
        assert r.verdict == "error" and r.steps[0].output["reason"] == reason, reason


# --- clauses in the record ----------------------------------------------------------------------------------


def test_the_record_names_each_clause_the_text_uses_with_its_claims_and_rendered_text():
    events, moment = moment_case("dominance_without_reward")
    menu = build_menu(moment, events)
    ctx = tools.slot_context(moment, events)
    g = run(guard_check("{clause:dominance}, yet {clause:score}.", menu, ctx))
    assert g.ok
    rec = verifier_record(moment, g, events, ctx, menu)
    by = {c["id"]: c for c in rec["clauses"]}
    assert set(by) == {"dominance", "score"}
    assert set(by["dominance"]["claims"]) == {"possession", "shots_for", "shots_against"} and by["dominance"]["written_by"] == "code"
    assert "of the ball" in by["dominance"]["text"] and set(by["score"]["claims"]) == {"score_home", "score_away"}
    assert {c["id"] for c in rec["claims"]} >= set(by["dominance"]["claims"])  # their definitions are in `claims`


def test_a_score_change_clause_carries_the_detectors_meaning_and_basis():
    for case in ("goal", "goal_from_behind"):
        events, moment = moment_case(case)
        change = moment.detail.get("score_change")
        if not change:
            continue
        menu = build_menu(moment, events)
        ctx = tools.slot_context(moment, events)
        kind = change["kind"]
        g = run(guard_check("{clause:%s}, and {clause:score}." % kind, menu, ctx))
        assert g.ok, case
        clause = next(c for c in verifier_record(moment, g, events, ctx, menu)["clauses"] if c["id"] == kind)
        assert clause["meaning"] and clause["basis"]["kind"] == kind and clause["claims"]
    events, moment = moment_case("goal_from_behind")
    menu = build_menu(moment, events)
    ctx = tools.slot_context(moment, events)
    g = run(guard_check("{clause:go_ahead}, and {clause:score}.", menu, ctx))
    clause = next(c for c in verifier_record(moment, g, events, ctx, menu)["clauses"] if c["id"] == "go_ahead")
    assert "came from behind" in clause["text"] and "deficit" in clause["claims"] and clause["basis"]["from_behind"] is True
    assert "level score that already had goals" in clause["meaning"]


def test_clauses_not_used_are_not_listed_and_event_phrases_are_not_clauses():
    events, moment = moment_case("red_card")
    menu = build_menu(moment, events)
    ctx = tools.slot_context(moment, events)
    g = run(guard_check("{clause:sent_off}, and {clause:score}.", menu, ctx))
    rec = verifier_record(moment, g, events, ctx, menu)
    assert [c["id"] for c in rec["clauses"]] == ["sent_off", "score"]
