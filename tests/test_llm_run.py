import json
from dataclasses import replace

from app.explain import DEFAULT_EXPLAIN_CONFIG
from app.explain.llm_narrator import FoundryNarrator
from app.explain.pipeline import run_match
from eval.llm_run import collect_match, render_report, summarize
from tests.explain_helpers import match
from tests.test_llm_narrator import FakeChatClient, responder

EVENTS, _ = match(42, "red_card_swing")


def _run(script_factory, **cfg):
    client = FakeChatClient(script_factory(EVENTS))
    narrator = FoundryNarrator(EVENTS, client, config=replace(DEFAULT_EXPLAIN_CONFIG, **cfg), model_tag="fake")
    results = run_match(EVENTS, narrator)
    return collect_match("red_card_swing_seed42", results, narrator.usage), client


def _meta():
    return {"model": "fake", "prompt_version": "foundry-v2:fake", "lang": "en",
            "started_at": "2026-10-12T00:00:00+00:00", "finished_at": "2026-10-12T00:01:00+00:00",
            "max_calls_per_run": 60, "max_tokens": 4000, "timeout_s": 60.0, "max_retries": 2}


def test_all_first_try_when_model_is_correct():
    data, client = _run(responder)
    s = summarize(data)
    assert s["moments"] == s["first_try"] == len(data["moments"]) > 0
    assert s["after_retry"] == s["fallback"] == 0
    assert s["calls"] == len(client.calls) == s["moments"]
    assert s["input_tokens"] == 321 * s["calls"] and s["reasoning_tokens"] == 64 * s["calls"]


def test_fallbacks_are_listed_with_rejection_codes():
    def broken_then_ok(events):
        good = responder(events)
        state = {"n": 0}

        def respond(messages):
            state["n"] += 1
            return "not json" if state["n"] <= 3 else good(messages)  # first moment broken 3 times

        return respond

    data, _ = _run(broken_then_ok)
    s = summarize(data)
    assert (s["fallback"], s["first_try"]) == (1, s["moments"] - 1)
    first = data["moments"][0]
    assert first["source"] == "template_fallback" and first["fallback_reason"] == "max_retries_exceeded"
    assert [(r["attempt"], r["codes"]) for r in first["rejections"]] == [
        (a, ["invalid_output"]) for a in (1, 2, 3)
    ]
    assert all("Response does not match the schema" in r["message"] for r in first["rejections"])

    report = render_report({"meta": _meta(), "matches": [data]})
    assert "## Moments that fell back" in report
    assert "`invalid_output`" in report and "#3:" in report
    assert "**Total**" in report and "foundry-v2:fake" in report


def test_budget_fallback_reason_is_reported():
    data, client = _run(responder, llm_max_calls_per_run=2)
    assert len(client.calls) == 2
    reasons = {m["fallback_reason"] for m in data["moments"] if m["source"] == "template_fallback"}
    assert reasons == {"budget_exceeded"}
    assert "`budget_exceeded`" in render_report({"meta": _meta(), "matches": [data]})


def test_render_from_json_is_deterministic():
    data, _ = _run(responder)
    run = {"meta": _meta(), "matches": [data]}
    reloaded = json.loads(json.dumps(run))
    assert render_report(reloaded) == render_report(run)


# --- error messages, reasoning ratio, human review CSV -----------------------------


def test_client_error_messages_reach_report():
    def flaky(events):
        good = responder(events)
        state = {"n": 0}

        def respond(messages):
            state["n"] += 1
            if state["n"] == 1:
                raise ConnectionError("upstream reset")
            return good(messages)

        return respond

    client = FakeChatClient(flaky(EVENTS))
    narrator = FoundryNarrator(EVENTS, client, model_tag="fake")
    data = collect_match("red_card_swing_seed42", run_match(EVENTS, narrator), narrator.usage)
    first = data["moments"][0]
    assert first["attempts"] == 2 and first["rejections"][0]["codes"] == ["client_error"]
    assert "upstream reset" in first["rejections"][0]["message"]
    report = render_report({"meta": _meta(), "matches": [data]})
    assert "## Client errors" in report and "upstream reset" in report
    assert "## Moments that passed after a retry" in report


def test_reasoning_ratio_and_latency_columns():
    data, _ = _run(responder)
    report = render_report({"meta": {**_meta(), "reasoning_effort": "low"}, "matches": [data]})
    s = summarize(data)
    ratio = s["reasoning_tokens"] / s["output_tokens"] * 100
    assert f"({ratio:.1f}%)" in report
    assert "Reasoning effort: `low`" in report and "| Median |" in report


def test_human_review_csv(tmp_path):
    import csv

    from eval.llm_run import REVIEW_COLUMNS, write_human_review

    data, _ = _run(responder)
    run = {"meta": _meta(), "matches": [data]}
    path = write_human_review(run, tmp_path / "human_review.csv")
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert tuple(rows[0].keys()) == REVIEW_COLUMNS
    assert [r["moment_id"] for r in rows] == [m["id"] for m in data["moments"]]
    assert all(r["text"] and not any(r[c] for c in REVIEW_COLUMNS[2:]) for r in rows)


def test_human_review_csv_never_overwrites_annotations(tmp_path):
    from eval.llm_run import write_human_review

    data, _ = _run(responder)
    run = {"meta": _meta(), "matches": [data]}
    path = tmp_path / "human_review.csv"
    write_human_review(run, path)
    annotated = path.read_text(encoding="utf-8").replace(",,,,\n", ",1,,,\n", 1)
    path.write_text(annotated, encoding="utf-8")

    target = write_human_review(run, path, stamp="T1")
    assert target.name == "human_review.T1.csv"
    assert path.read_text(encoding="utf-8") == annotated


# --- measurement mode: rejected drafts, multiple runs, version comparison --------------------------


class _ShotsNarrator:
    """A v4-style draft (the model builds the claim): 'home shots since kickoff', citing only the first event.

    In foundry-v5 the model cannot build claims; this shows that evidence_mismatch reporting on the
    archived v4/v4.1 measurements still works.
    """

    name, source, prompt_version = "shots", "llm", "test-v4"

    def __init__(self, events):
        self.events = events
        self.usage = []

    def narrate(self, moment, persona, language, feedback=None):
        from app.explain.claims import KICKOFF, Claim, MatchTime, Subject
        from app.explain.narrator import Draft

        end = MatchTime(moment.period, moment.minute, moment.second)
        ref = f"{self.events[0].match_id}#{moment.event_ids[0]}"
        claim = Claim("count", Subject("home"), "shots", "eq", 1, KICKOFF, end, (ref,))
        template = "{home} had {value:c1} {label:c1}."
        return Draft(template, (claim,), template=template, claim_ids=("c1",))


def _measured_run(make_narrator):
    narrator = make_narrator(EVENTS)
    logs = []
    results = run_match(EVENTS, narrator, on_attempt=logs.append)
    return collect_match("red_card_swing_seed42", results, narrator.usage, logs, EVENTS)


def _foundry(events):
    return FoundryNarrator(events, FakeChatClient(responder(events)), model_tag="fake")


def test_rejected_drafts_are_recorded_with_message_and_evidence():
    data = _measured_run(_ShotsNarrator)
    rejected = [r for mo in data["moments"] for r in mo["rejections"]]
    assert rejected and all(r["message"] for r in rejected)
    mismatch = [f for r in rejected for f in r["verify_failures"] if f["reason"] == "evidence_mismatch"]
    assert mismatch
    f = mismatch[0]
    assert f["claim"]["metric"] == "shots" and f["window"] == "kickoff → now"
    assert len(f["cited"]) == 1 and all(e["type"] == "shot" for e in f["counted"])
    first = next(r for r in rejected if "evidence_mismatch" in r["codes"])
    assert first["template"] == "{home} had {value:c1} {label:c1}."
    assert first["claims"][0]["id"] == "c1"
    assert "cited [#" in first["message"] and "counted [#" in first["message"]

    report = render_report({"meta": _meta(), "matches": [data]})
    assert "## evidence_mismatch: cited and counted events" in report
    assert "count shots home" in report and "shot×" in report
    assert "## Rejected drafts" in report and "{home} had {value:c1} {label:c1}." in report


def test_trace_rejections_have_messages_without_attempt_log():
    narrator = _ShotsNarrator(EVENTS)
    data = collect_match("red_card_swing_seed42", run_match(EVENTS, narrator), narrator.usage)
    rejected = [r for mo in data["moments"] for r in mo["rejections"]]
    assert rejected and all(r["message"] and "evidence_mismatch" in r["message"] for r in rejected
                            if "evidence_mismatch" in r["codes"])
    assert "template" not in rejected[0]  # the draft only in measurement mode


def test_multi_run_report_comparison_and_review_from_last_run(tmp_path):
    import csv

    from eval.llm_run import REVIEW_COLUMNS, write_human_review

    ok = _measured_run(_foundry)
    bad = _measured_run(_ShotsNarrator)
    meta = {**_meta(), "prompt_version": "foundry-v4.1:fake", "repeats": 2}
    run = {"meta": meta, "runs": [
        {"started_at": "a", "finished_at": "b", "matches": [bad]},
        {"started_at": "c", "finished_at": "d", "matches": [ok]},
    ]}
    baseline = {"meta": {**_meta(), "prompt_version": "foundry-v4:fake"}, "matches": [bad]}
    report = render_report(run, {"foundry-v4": baseline})
    assert "### Run 2 (c – d)" in report and "### Fallbacks per run" in report
    assert "## Version comparison: foundry-v4, foundry-v4.1" in report
    assert "foundry-v4.1 · run 1" in report and "**foundry-v4.1 · total (2 runs)**" in report
    assert "### Run 1 · red_card_swing_seed42" in report
    assert "## Rejection code frequency" in report and "| `evidence_mismatch` | " in report
    side = report[report.index("## Side by side"):]
    assert "| Moment | Type | foundry-v4 | foundry-v4.1 |" in side and "*(fallback)*" in side
    assert render_report(run, {"foundry-v4.1": run, "foundry-v4": baseline}) == report  # its own version is excluded
    n = len(bad["moments"])
    assert f"| 1 | {n} | {n} |" in report and f"| 2 | {n} | 0 |" in report  # fallbacks per run

    rows = list(csv.DictReader(write_human_review(run, tmp_path / "hr.csv").open(encoding="utf-8")))
    assert [r["text"] for r in rows] == [mo["text"] for mo in ok["moments"]]
    assert tuple(rows[0]) == REVIEW_COLUMNS
    assert render_report(json.loads(json.dumps(run)), {"foundry-v4": baseline}) == report


def test_menu_drafts_never_reach_evidence_mismatch():
    """foundry-v5: the model links no claims or events, so the evidence_mismatch path is unused."""
    from tests.test_llm_narrator import text_json

    def sloppy(events):
        good = responder(events)
        state = {"n": 0}

        def respond(messages):
            state["n"] += 1
            if state["n"] % 2:  # every first attempt is bad: off-menu id, event word, raw number
                return text_json("{home} had {value:c9} shots and 3 corners.")
            return good(messages)

        return respond

    narrator = FoundryNarrator(EVENTS, FakeChatClient(sloppy(EVENTS)), model_tag="fake")
    logs = []
    run_match(EVENTS, narrator, on_attempt=logs.append)
    assert logs and any(not log.accepted for log in logs)
    reasons = [r.reason for log in logs for r in log.verification]
    assert reasons and set(reasons) == {"ok"}
    assert all(log.draft.menu is not None and log.draft.claims == () for log in logs)


def test_side_by_side_matches_cards_by_time_and_type_across_renumbered_ids():
    """foundry-v5.1 renumbered moment ids (score_change merged into goal): rows match by time and type."""
    from eval.llm_run import render_side_by_side

    def mo(mid, mtype, minute, text):
        return {"id": f"m-1-{mid}", "type": mtype, "period": 2, "minute": minute, "second": 0,
                "source": "llm", "text": text}

    old = {"meta": {**_meta(), "prompt_version": "foundry-v5:fake"}, "matches": [{"match_id": "x_seed1", "moments": [
        mo("M001", "goal", 61, "old goal"), mo("M002", "score_change", 61, "old change"),
        mo("M003", "pressure_shift", 70, "old shift")]}]}
    new = {"meta": {**_meta(), "prompt_version": "foundry-v5.1:fake"}, "matches": [{"match_id": "x_seed1", "moments": [
        mo("M001", "goal", 61, "new goal"), mo("M002", "pressure_shift", 70, "new shift")]}]}
    rows = [line for line in render_side_by_side(new, {"foundry-v5": old}) if line.startswith("| x ")]
    assert rows == ["| x M001 | goal | old goal | new goal |", "| x M002 | pressure_shift | old shift | new shift |"]


def test_primary_usage_counts_main_claims_per_card_type():
    """foundry-v5.2 table: the main claims of each card type, measured on the model template."""
    import copy
    from pathlib import Path

    from eval.llm_run import render_primary_usage

    v51 = json.loads((Path(__file__).resolve().parents[1] / "docs" / "LLM_RUN.foundry-v5.1.json").read_text())
    new = copy.deepcopy(v51)
    new["meta"]["prompt_version"] = "foundry-v5.2:fake"
    for m in new["runs"][0]["matches"]:
        for mo in m["moments"]:
            if mo["id"] == "m-7-dominant_loss-M007":
                mo["template"] = "{clause:dominance}, yet {clause:score}."
            if mo["id"] == "m-42-red_card_swing-M009":
                mo["source"] = "template_fallback"
    rows = render_primary_usage(new, {"foundry-v5.1": v51, "foundry-v4": v51})  # pre-menu versions are left out
    assert "| Card | Main claim | foundry-v5.1 | foundry-v5.2 |" in rows
    assert "| dominance_without_reward | score | 0/3 (0%) | 1/3 (33%) |" in rows
    assert "| dominance_without_reward | possession | 3/3 (100%) | 3/3 (100%) |" in rows
    assert "| pressure_shift | shot balance | 0/2 (0%) | 0/1 (0%) |" in rows
    assert "| **Fallback cards** | | 0 | pressure_shift 1 |" in rows
