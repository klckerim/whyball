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
    assert first["rejections"] == [{"attempt": a, "codes": ["invalid_output"]} for a in (1, 2, 3)]

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
