import copy
import json

import pytest

from app.analytics import detect_moments
from app.explain.selector import select_moments
from app.generator.freeze import demo_paths
from app.generator.models import read_jsonl
from app.publish import SOURCES, MatchStore
from app.publish.__main__ import main
from app.publish.store import DEFAULT_OUT_DIR, DEFAULT_REPORT, DEFAULT_RUN, PublishError, build, outputs

REGEN_HINT = "the store is out of date; run python -m app.publish"
RED_CARD = [p for p in demo_paths() if p[2].stem == "red_card_swing_seed42"]


@pytest.fixture(scope="module")
def result():
    return build()


@pytest.fixture(scope="module")
def run_data():
    return json.loads(DEFAULT_RUN.read_text(encoding="utf-8"))


def _write_run(tmp_path, data):
    path = tmp_path / "run.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _red_card_moments(data):
    return next(m for m in data["runs"][-1]["matches"] if m["match_id"] == "red_card_swing_seed42")["moments"]


def _card(result, moment_id):
    return next(m for s in result.stores for m in s.moments if m.id == moment_id)


# --- schema --------------------------------------------------------------------------------------


@pytest.mark.parametrize("scenario,seed,path", demo_paths(), ids=[p.name for _, _, p in demo_paths()])
def test_repo_store_matches_schema_and_events(scenario, seed, path):
    stored = DEFAULT_OUT_DIR / f"{path.stem}.json"
    assert stored.exists(), REGEN_HINT
    store = MatchStore.model_validate_json(stored.read_text(encoding="utf-8"))
    events = read_jsonl(path)
    by_seq = {e.seq: e for e in events}
    assert store.match_id == path.stem
    assert store.event_match_id == events[0].match_id
    assert [m.id for m in store.moments] == [m.id for m in detect_moments(events)]
    for m in store.moments:
        assert m.source in SOURCES
        assert m.trace == []
        assert m.text.strip() and m.claims
        for c in m.claims:
            assert c.evidence or c.kind == "count"
            for ev in c.evidence:
                e = by_seq[ev.seq]
                assert ev.id == f"{events[0].match_id}#{e.seq}"
                assert (ev.type, ev.team, ev.player, ev.minute, ev.second) == (
                    e.type.value, e.team, e.player, e.minute, e.second)


@pytest.mark.parametrize("scenario,seed,path", demo_paths(), ids=[p.name for _, _, p in demo_paths()])
def test_repo_store_records_the_checks_of_each_card(scenario, seed, path):
    store = MatchStore.model_validate_json((DEFAULT_OUT_DIR / f"{path.stem}.json").read_text(encoding="utf-8"))
    for m in store.moments:  # build_match publishes only cards that passed; the record says so per card
        assert m.checks.lint_issues == 0
        assert m.checks.claims_verified == m.checks.claims_total == len(m.claims) > 0


def test_checks_come_from_the_pipeline_result(result):
    for store in result.stores:
        for m in store.moments:
            assert (m.checks.lint_issues, m.checks.claims_verified) == (0, m.checks.claims_total)


# --- reproducibility -----------------------------------------------------------------------------


def test_build_is_byte_reproducible(tmp_path):
    for out in ("a", "b"):
        assert main(["--out-dir", str(tmp_path / out), "--report", str(tmp_path / out / "report.md")]) == 0
    for path in (tmp_path / "a").iterdir():
        assert path.read_bytes() == (tmp_path / "b" / path.name).read_bytes()
        repo = DEFAULT_REPORT if path.name == "report.md" else DEFAULT_OUT_DIR / path.name
        assert path.read_bytes() == repo.read_bytes(), REGEN_HINT


def test_check_mode(tmp_path):
    assert main(["--check"]) == 0, REGEN_HINT
    assert main(["--check", "--out-dir", str(tmp_path)]) == 1


# --- source of each card -------------------------------------------------------------------------


def test_every_card_source(result, run_data):
    run_cards = {m["id"] for match in run_data["runs"][-1]["matches"] for m in match["moments"]}
    for (_, _, path), store in zip(demo_paths(), result.stores):
        selected = {m.id for m in select_moments(detect_moments(read_jsonl(path)))}
        for m in store.moments:
            if m.id in selected:
                assert m.id in run_cards
                assert m.source == "llm"
                assert m.prompt_version == run_data["meta"]["prompt_version"]
                assert m.run_id == result.run_id
            else:
                assert m.source == "template"
                assert m.prompt_version == "template-v1"
                assert m.run_id is None
    assert result.fallbacks == []


def test_llm_card_claims_use_menu_ids(result):
    card = _card(result, "m-42-red_card_swing-M002")
    assert {"goal", "score_home", "score_away", "possession"} <= {c.id for c in card.claims}


def test_rejected_draft_falls_back_to_template(tmp_path, run_data):
    data = copy.deepcopy(run_data)
    moment = next(m for m in _red_card_moments(data) if m["id"] == "m-42-red_card_swing-M002")
    moment["template"] = "{event:m-42-red_card_swing#127}, and they lead 1 to 0."
    result = build(_write_run(tmp_path, data), RED_CARD)
    card = _card(result, "m-42-red_card_swing-M002")
    assert card.source == "template_fallback"
    assert card.prompt_version == "template-v1"
    assert card.run_id == result.run_id
    assert card.text and card.claims
    [fallback] = result.fallbacks
    assert fallback.moment_id == card.id and "raw_number" in fallback.codes
    assert "## Template fallbacks" in (report := outputs(result, tmp_path, tmp_path / "r.md")[tmp_path / "r.md"])
    assert f"`{card.id}` | `" in report


@pytest.mark.parametrize("change,code", [
    (lambda ms: ms.remove(next(m for m in ms if m["id"].endswith("M004"))), "no_draft"),
    (lambda ms: next(m for m in ms if m["id"].endswith("M004")).update(minute=39), "moment_mismatch"),
    (lambda ms: next(m for m in ms if m["id"].endswith("M004")).update(source="template_fallback"), "no_draft"),
])
def test_missing_or_mismatched_draft_falls_back(tmp_path, run_data, change, code):
    data = copy.deepcopy(run_data)
    change(_red_card_moments(data))
    result = build(_write_run(tmp_path, data), RED_CARD)
    assert _card(result, "m-42-red_card_swing-M004").source == "template_fallback"
    assert [f.codes for f in result.fallbacks] == [(code,)]


# --- difference report ---------------------------------------------------------------------------


def test_diff_report_lists_changed_cards(result):
    assert [d.moment_id for d in result.diffs] == ["m-42-red_card_swing-M008", "m-7-dominant_loss-M003"]
    assert all(d.old != d.new for d in result.diffs)
    m003 = result.diffs[1]
    assert "58% of the ball" in m003.old and "59% of the ball" in m003.new
    assert _card(result, "m-7-dominant_loss-M003").text == m003.new


def test_diff_report_with_edited_run_text(tmp_path, run_data):
    data = copy.deepcopy(run_data)
    moment = next(m for m in _red_card_moments(data) if m["id"] == "m-42-red_card_swing-M004")
    published = moment["text"]
    moment["text"] = "Edited text."
    result = build(_write_run(tmp_path, data), RED_CARD)
    diffs = {d.moment_id: d for d in result.diffs}
    assert diffs["m-42-red_card_swing-M004"].old == "Edited text."
    assert diffs["m-42-red_card_swing-M004"].new == published
    report = outputs(result, tmp_path, tmp_path / "r.md")[tmp_path / "r.md"]
    assert f"| `m-42-red_card_swing-M004` | Edited text. | {published} |" in report


# --- same-second check ---------------------------------------------------------------------------


def test_same_second_cases(result):
    found = {s.moment_id: s for s in result.same_second}
    assert set(found) == {"m-7-dominant_loss-M004", "m-100-M003"}
    for s in found.values():
        assert not s.selected and s.source == "template"
        assert not s.affects_card
        assert [d.claim_id for d in s.menu] in (["score_away"], ["score_home"])
        assert any(e.endswith(" goal") for e in s.later_events)


# --- segments ------------------------------------------------------------------------------------


def test_every_card_has_segments_that_join_to_its_text(result):
    for s in result.stores:
        for card in s.moments:
            assert card.segments
            assert "".join(seg.text for seg in card.segments) == card.text
            assert all(seg.text for seg in card.segments)
            ids = {c.id for c in card.claims}
            assert {seg.claim_id for seg in card.segments if seg.claim_id} <= ids


def test_claim_segments_show_the_claim_display(result):
    assert not [s for s in result.segment_stats if s.mismatched]
    n = sum(seg.claim_id is not None for s in result.stores for c in s.moments for seg in c.segments)
    assert n > 0


def test_llm_and_template_cards_both_have_claim_segments(result):
    for source in ("llm", "template"):
        cards = [c for s in result.stores for c in s.moments if c.source == source]
        assert cards and any(seg.claim_id for c in cards for seg in c.segments)


def test_report_lists_the_segment_numbers(result):
    assert "## Segments" in outputs(result, DEFAULT_OUT_DIR, DEFAULT_REPORT)[DEFAULT_REPORT]


# --- verification and trace (P2) ---------------------------------------------------------------------------


def _step(step, agent, attempt=1, output=None, status="ok", tokens=None):
    return {"step": step, "agent": agent, "attempt": attempt, "started_ms": 0, "duration_ms": 1, "input_ref": "x",
            "output": output or {}, "tokens": tokens or {"in": None, "out": None, "reasoning": None},
            "model": None, "status": status}


def _agent_moment(data, verifier="passed", trace=None, attempts=1, label=None, source="llm"):
    """The run with the first model card of red_card_swing given a verification and a trace (agent run shape)."""
    moments = _red_card_moments(data)
    card = next(m for m in moments if m["source"] == "llm")
    card["verification"] = {"guard": True, "verifier": verifier, "attempts": attempts,
                            "label_source": label or ("llm" if verifier in ("passed", "retried_then_passed") else "guard_only")}
    card["trace"] = trace if trace is not None else [
        _step("narrate", "narrator"), _step("guard", "guard", output={"ok": True, "codes": []}),
        _step("verify", "verifier", output={"verdict": "pass", "issues": []}), _step("finalize", "workflow")]
    card["source"] = source
    return card


def _build_one(tmp_path, data):
    from app.publish.store import build

    return build(_write_run(tmp_path, data), RED_CARD)


def test_cards_of_an_older_run_say_no_meaning_check_ran(result):
    for s in result.stores:
        for c in s.moments:
            assert c.trace == []
            v = c.verification
            assert (v.guard, v.verifier) == (True, "not_run")
            assert v.label_source == {"llm": "guard_only", "template": "template", "template_fallback": "template_fallback"}[c.source]


def test_an_agent_runs_verification_and_trace_are_stored_with_the_card(tmp_path, run_data):
    data = copy.deepcopy(run_data)
    card = _agent_moment(data)
    store = _build_one(tmp_path, data).stores[0]
    got = next(m for m in store.moments if m.id == card["id"])
    assert got.verification.model_dump() == card["verification"]
    assert [t["step"] for t in got.trace] == ["narrate", "guard", "verify", "finalize"]
    assert got.source == "llm" and got.verification.label_source == "llm"


@pytest.mark.parametrize("kw,message", [
    (dict(verifier="passed", label="guard_only"), "label_source"),
    (dict(verifier="skipped_error", label="llm"), "label_source"),
    (dict(verifier="passed", attempts=4), "attempts"),
    (dict(verifier="passed", trace=[_step("narrate", "narrator")]), "finalize"),
    (dict(verifier="passed", trace=[_step("narrate", "narrator"), _step("finalize", "workflow")]), "passing verify step"),
    (dict(verifier="skipped_error", trace=[_step("narrate", "narrator"), _step("finalize", "workflow")]), "verifier_error"),
    (dict(verifier="not_run", label="guard_only", trace=[_step("verify", "verifier", output={"verdict": "pass"}),
                                                          _step("finalize", "workflow")]), "not_run"),
    (dict(verifier="passed", trace=[]), "without a trace"),
    (dict(verifier="passed", trace=[_step("dance", "narrator")]), "step"),
])
def test_a_card_cannot_claim_a_check_its_trace_does_not_show(tmp_path, run_data, kw, message):
    from pydantic import ValidationError

    data = copy.deepcopy(run_data)
    _agent_moment(data, **kw)
    with pytest.raises((PublishError, ValidationError), match=message):
        _build_one(tmp_path, data)


def test_a_guard_only_card_is_stored_as_such(tmp_path, run_data):
    data = copy.deepcopy(run_data)
    trace = [_step("narrate", "narrator"), _step("guard", "guard"),
             _step("verifier_error", "verifier", status="timeout", output={"reason": "timeout"}), _step("finalize", "workflow")]
    card = _agent_moment(data, verifier="skipped_error", trace=trace)
    got = next(m for m in _build_one(tmp_path, data).stores[0].moments if m.id == card["id"])
    assert got.source == "llm" and got.verification.label_source == "guard_only" and got.verification.verifier == "skipped_error"


def test_a_trace_is_dropped_when_the_current_code_publishes_another_kind_of_card(tmp_path, run_data):
    data = copy.deepcopy(run_data)
    card = _agent_moment(data)
    card["template"] = "{clause:goal}, and 3 shots."  # the run says llm, but its draft no longer passes the current Guard
    result = _build_one(tmp_path, data)
    got = next(m for m in result.stores[0].moments if m.id == card["id"])
    assert got.source == "template_fallback" and got.trace == [] and got.verification.verifier == "not_run"
    assert any(card["id"] in line for line in result.trace_dropped)
    assert "Run traces not stored" in outputs(result, DEFAULT_OUT_DIR, DEFAULT_REPORT)[DEFAULT_REPORT]


def test_the_trace_vocabulary_matches_the_agents():
    from app.agents.trace import AGENTS, STATUSES, STEPS
    from app.publish.schema import TRACE_AGENTS, TRACE_STATUSES, TRACE_STEPS

    assert (TRACE_STEPS, TRACE_AGENTS, TRACE_STATUSES) == (STEPS, AGENTS, STATUSES)


def test_a_step_written_by_the_agents_validates_against_the_store_schema():
    from app.agents.trace import Tokens, TraceStep
    from app.publish.schema import TraceStep as Stored

    step = TraceStep.make("narrate", "narrator", attempt=1, started_ms=3, duration_ms=9, input_ref="menu",
                          output={"template": "{clause:goal}."}, tokens=Tokens(1, 2, 3), model="m")
    assert Stored.model_validate(step.to_dict()).model_dump() == step.to_dict()
