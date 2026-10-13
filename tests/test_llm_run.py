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
            return "not json" if state["n"] <= 3 else good(messages)  # ilk moment 3 kez bozuk

        return respond

    data, _ = _run(broken_then_ok)
    s = summarize(data)
    assert (s["fallback"], s["first_try"]) == (1, s["moments"] - 1)
    first = data["moments"][0]
    assert first["source"] == "template_fallback" and first["fallback_reason"] == "max_retries_exceeded"
    assert [(r["attempt"], r["codes"]) for r in first["rejections"]] == [
        (a, ["invalid_output"]) for a in (1, 2, 3)
    ]
    assert all("Şemaya uymayan" in r["message"] for r in first["rejections"])

    report = render_report({"meta": _meta(), "matches": [data]})
    assert "## Yedeğe düşen momentler" in report
    assert "`invalid_output`" in report and "#3:" in report
    assert "**Toplam**" in report and "foundry-v2:fake" in report


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


# --- hata mesajları, reasoning oranı, insan değerlendirme CSV'si -----------------------------


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
    assert "## İstemci hataları" in report and "upstream reset" in report
    assert "## Yeniden denemeyle geçen momentler" in report


def test_reasoning_ratio_and_latency_columns():
    data, _ = _run(responder)
    report = render_report({"meta": {**_meta(), "reasoning_effort": "low"}, "matches": [data]})
    s = summarize(data)
    ratio = s["reasoning_tokens"] / s["output_tokens"] * 100
    assert f"({ratio:.1f}%)" in report
    assert "Reasoning çabası: `low`" in report and "| Medyan |" in report


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


# --- ölçüm modu: reddedilen taslaklar, çoklu koşu, sürüm karşılaştırması --------------------------


class _ShotsNarrator:
    """v4 tarzı (model iddia kurar) taslak: 'maç başından beri ev sahibi şutu', yalnızca ilk olaya bağlı.

    foundry-v5'te model iddia kuramaz; bu, arşivlenen v4/v4.1 ölçümlerindeki evidence_mismatch
    raporlamasının hâlâ çalıştığını gösterir.
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
    assert f["claim"]["metric"] == "shots" and f["window"] == "maç başı → an"
    assert len(f["cited"]) == 1 and all(e["type"] == "shot" for e in f["counted"])
    first = next(r for r in rejected if "evidence_mismatch" in r["codes"])
    assert first["template"] == "{home} had {value:c1} {label:c1}."
    assert first["claims"][0]["id"] == "c1"
    assert "cited [#" in first["message"] and "counted [#" in first["message"]

    report = render_report({"meta": _meta(), "matches": [data]})
    assert "## evidence_mismatch: bağlanan ve sayılan olaylar" in report
    assert "count shots home" in report and "shot×" in report
    assert "## Reddedilen taslaklar" in report and "{home} had {value:c1} {label:c1}." in report


def test_trace_rejections_have_messages_without_attempt_log():
    narrator = _ShotsNarrator(EVENTS)
    data = collect_match("red_card_swing_seed42", run_match(EVENTS, narrator), narrator.usage)
    rejected = [r for mo in data["moments"] for r in mo["rejections"]]
    assert rejected and all(r["message"] and "evidence_mismatch" in r["message"] for r in rejected
                            if "evidence_mismatch" in r["codes"])
    assert "template" not in rejected[0]  # taslak yalnızca ölçüm modunda


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
    assert "### Koşu 2 (c – d)" in report and "### Koşu başına yedeğe düşen" in report
    assert "## Sürüm karşılaştırması: foundry-v4, foundry-v4.1" in report
    assert "foundry-v4.1 · koşu 1" in report and "**foundry-v4.1 · toplam (2 koşu)**" in report
    assert "### Koşu 1 · red_card_swing_seed42" in report
    assert "## Ret kodu sıklığı" in report and "| `evidence_mismatch` | " in report
    side = report[report.index("## Yan yana"):]
    assert "| Moment | Tip | foundry-v4 | foundry-v4.1 |" in side and "*(yedek)*" in side
    assert render_report(run, {"foundry-v4.1": run, "foundry-v4": baseline}) == report  # kendi sürümü dışlanır
    n = len(bad["moments"])
    assert f"| 1 | {n} | {n} |" in report and f"| 2 | {n} | 0 |" in report  # koşu başına yedek

    rows = list(csv.DictReader(write_human_review(run, tmp_path / "hr.csv").open(encoding="utf-8")))
    assert [r["text"] for r in rows] == [mo["text"] for mo in ok["moments"]]
    assert tuple(rows[0]) == REVIEW_COLUMNS
    assert render_report(json.loads(json.dumps(run)), {"foundry-v4": baseline}) == report


def test_menu_drafts_never_reach_evidence_mismatch():
    """foundry-v5: model iddia ve olay bağlamadığı için evidence_mismatch yolu kullanılmaz."""
    from tests.test_llm_narrator import text_json

    def sloppy(events):
        good = responder(events)
        state = {"n": 0}

        def respond(messages):
            state["n"] += 1
            if state["n"] % 2:  # her ilk deneme kötü: menü dışı id, olay sözcüğü, ham sayı
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
