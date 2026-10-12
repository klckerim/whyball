import asyncio
import json
import logging
import sys
from dataclasses import replace

import pytest
from openai.lib._pydantic import to_strict_json_schema

from app.analytics import detect_moments
from app.explain import DEFAULT_EXPLAIN_CONFIG
from app.explain.claims import METRIC_KINDS
from app.explain.llm_narrator import (
    PROMPT_VERSION,
    ChatResult,
    FoundryChatClientAdapter,
    FoundryNarrator,
    build_messages,
    draft_model_for,
    moment_record,
    parse_draft,
)
from app.explain.narrator import (
    BudgetExceeded,
    Feedback,
    FeedbackItem,
    InvalidNarratorOutput,
    Narrator,
    NarratorTimeout,
    TemplateNarrator,
)
from app.explain.pipeline import run_match, run_moment
from tests.explain_helpers import match, moment_case

EVENTS, MOMENT = moment_case("goal")
TEMPLATE = TemplateNarrator(EVENTS)
MATCH_ID = EVENTS[0].match_id


def _t(time):
    return {"period": time[0], "minute": time[1], "second": time[2]}


def _draft_json(draft):
    claims = [
        {**c.to_dict(), "start": _t(c.start), "end": _t(c.end)} for c in draft.claims
    ]
    return json.dumps({"text": draft.text, "claims": claims})


def _template_json(moment, lang="en", events=EVENTS):
    return _draft_json(TemplateNarrator(events).narrate(moment, "neutral", lang))


class Sleep:
    def __init__(self, seconds):
        self.seconds = seconds


class FakeChatClient:
    """Sırayla yanıt verir; son adım tekrarlanır. Adım: str, callable(messages)->str, Sleep, Exception."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = []

    async def complete(self, messages, *, response_model, max_tokens):
        self.calls.append({"messages": messages, "response_model": response_model, "max_tokens": max_tokens})
        step = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(step, Exception):
            raise step
        if isinstance(step, Sleep):
            await asyncio.sleep(step.seconds)
            return ChatResult("{}")
        text = step(messages) if callable(step) else step
        return ChatResult(text, input_tokens=321, output_tokens=87, reasoning_tokens=64)


def _user(call):
    return call["messages"][1]["content"]


def _narrator(client, **cfg):
    return FoundryNarrator(EVENTS, client, config=replace(DEFAULT_EXPLAIN_CONFIG, **cfg))


# --- moment kaydı ve kapalı şema ---------------------------------------------------------


def test_prompt_contains_only_the_moment_record():
    system, user = (m["content"] for m in build_messages(MOMENT, EVENTS, "analyst", "tr"))
    assert "Turkish" in system and "analyst" in system and "No outside knowledge" in system
    record = json.loads(user)
    assert record == moment_record(MOMENT, EVENTS)
    assert [e["id"] for e in record["events"]] == [f"{MATCH_ID}#{s}" for s in MOMENT.event_ids]
    assert record["metrics_at_moment"] == MOMENT.metrics
    assert record["moment"]["detail"] == MOMENT.detail
    teams = EVENTS[0].data["teams"]
    assert record["squads"]["home"]["lineup"] == teams["home"]["lineup"]
    # Moment dışında hiçbir olay modele gitmez.
    allowed = {f"{MATCH_ID}#{s}" for s in MOMENT.event_ids}
    mentioned = {tok.strip('",') for tok in user.split() if f"{MATCH_ID}#" in tok}
    assert mentioned <= allowed


def test_response_schema_is_closed_per_moment():
    model = _narrator(FakeChatClient("{}")).response_model(MOMENT)
    schema = to_strict_json_schema(model)
    claim = schema["$defs"]["ClaimOut"]
    assert claim["properties"]["event_ids"]["items"]["enum"] == [f"{MATCH_ID}#{s}" for s in MOMENT.event_ids]
    assert claim["properties"]["metric"]["enum"] == list(METRIC_KINDS)
    assert claim["properties"]["kind"]["enum"] == ["count", "ratio", "state"]
    players = schema["$defs"]["SubjectOut"]["properties"]["player"]["anyOf"][0]["enum"]
    teams = EVENTS[0].data["teams"]
    assert players == [*teams["home"]["lineup"], *teams["home"]["bench"],
                       *teams["away"]["lineup"], *teams["away"]["bench"]]
    assert claim["additionalProperties"] is False


def test_event_id_outside_moment_is_rejected_by_schema():
    good = TEMPLATE.narrate(MOMENT, "neutral", "en")
    foreign = replace(good, claims=(replace(good.claims[0], event_ids=(f"{MATCH_ID}#0",)), *good.claims[1:]))
    with pytest.raises(InvalidNarratorOutput):
        _narrator(FakeChatClient(_draft_json(foreign))).narrate(MOMENT, "neutral", "en")


def test_parse_draft_round_trips_template_draft():
    model = draft_model_for([f"{MATCH_ID}#{s}" for s in MOMENT.event_ids], ["x y", MOMENT.detail["player"]])
    assert parse_draft(model, _template_json(MOMENT)) == TEMPLATE.narrate(MOMENT, "neutral", "en")


# --- geçerli yanıt -----------------------------------------------------------------------


def test_valid_response_becomes_draft_and_logs_usage(caplog):
    client = FakeChatClient(_template_json(MOMENT))
    narrator = _narrator(client)
    with caplog.at_level(logging.INFO, logger="whyball.llm"):
        draft = narrator.narrate(MOMENT, "neutral", "en")

    assert draft == TEMPLATE.narrate(MOMENT, "neutral", "en")
    assert client.calls[0]["max_tokens"] == DEFAULT_EXPLAIN_CONFIG.llm_max_tokens
    [usage] = narrator.usage
    assert (usage.call, usage.moment_id, usage.outcome) == (1, MOMENT.id, "ok")
    assert (usage.input_tokens, usage.output_tokens, usage.reasoning_tokens) == (321, 87, 64)
    for field in ("input_tokens=321", "output_tokens=87", "reasoning_tokens=64", "latency_ms="):
        assert field in caplog.text


def test_valid_response_passes_pipeline():
    narrator = _narrator(FakeChatClient(_template_json(MOMENT)))
    record = run_moment(MOMENT, narrator, EVENTS)
    assert (record.source, record.attempts, record.ok) == ("llm", 1, True)


def test_protocol_prompt_version_and_defaults():
    narrator = _narrator(FakeChatClient("{}"))
    assert isinstance(narrator, Narrator)
    assert narrator.prompt_version == PROMPT_VERSION == "foundry-v2"
    assert FoundryNarrator(EVENTS, FakeChatClient("{}"), model_tag="gpt-x").prompt_version == "foundry-v2:gpt-x"
    assert DEFAULT_EXPLAIN_CONFIG.llm_max_calls_per_run == 60


# --- bozuk JSON --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    ["not json", '{"text": "hi"}', '{"text": "hi", "claims": [], "extra": 1}',
     '{"text": "x", "claims": [{"kind": "count"}]}'],
    ids=["not-json", "missing-claims", "extra-field", "bad-claim"],
)
def test_broken_json_raises_invalid_output(bad):
    narrator = _narrator(FakeChatClient(bad))
    with pytest.raises(InvalidNarratorOutput):
        narrator.narrate(MOMENT, "neutral", "en")
    assert narrator.usage[0].outcome == "invalid_output"


def test_pipeline_retries_after_broken_json_with_feedback():
    client = FakeChatClient("not json", _template_json(MOMENT))
    record = run_moment(MOMENT, _narrator(client), EVENTS)
    assert (record.source, record.attempts) == ("llm", 2)
    assert record.trace[0]["step"] == "narrate" and record.trace[0]["error"] == "invalid_output"
    assert "invalid_output" in _user(client.calls[1])
    assert "FEEDBACK" not in _user(client.calls[0])


# --- zaman aşımı -------------------------------------------------------------------------


def test_timeout_raises_narrator_timeout():
    narrator = _narrator(FakeChatClient(Sleep(1.0)), llm_timeout_s=0.05)
    with pytest.raises(NarratorTimeout, match="0.05"):
        narrator.narrate(MOMENT, "neutral", "en")
    assert narrator.usage[0].outcome == "timeout"
    assert narrator.usage[0].latency_ms < 900


def test_pipeline_falls_back_after_repeated_timeouts():
    client = FakeChatClient(Sleep(1.0))
    record = run_moment(MOMENT, _narrator(client, llm_timeout_s=0.05), EVENTS)
    assert (record.source, record.attempts, len(client.calls)) == ("template_fallback", 3, 3)
    assert [s.get("error") for s in record.trace if s["step"] == "narrate"] == ["timeout"] * 3
    assert record.trace[-1]["reason"] == "max_retries_exceeded"
    assert record.ok


def test_client_exception_is_wrapped():
    narrator = _narrator(FakeChatClient(ConnectionError("boom")))
    with pytest.raises(Exception, match="boom") as exc:
        narrator.narrate(MOMENT, "neutral", "en")
    assert exc.value.code == "client_error"


# --- bütçe aşımı -------------------------------------------------------------------------


def test_budget_exceeded_before_calling_client():
    client = FakeChatClient(_template_json(MOMENT))
    narrator = _narrator(client, llm_max_calls_per_run=2)
    narrator.narrate(MOMENT, "neutral", "en")
    narrator.narrate(MOMENT, "neutral", "en")
    with pytest.raises(BudgetExceeded, match="2/2"):
        narrator.narrate(MOMENT, "neutral", "en")
    assert len(client.calls) == 2


def responder(events):
    """Her moment için kapalı şemaya uyan, doğrulanabilir bir taslak üreten sahte model.

    Yalnızca moment kaydını kullanır: skoru metrics_at_moment'tan alır, dayanak olarak
    momentin ilk olayını gösterir (template iddiaları kayıt dışı olaylara dayanabilir).
    """
    moments = {m.id: m for m in detect_moments(events)}

    def respond(messages):
        record, _ = json.JSONDecoder().raw_decode(messages[1]["content"])
        moment = moments[record["moment"]["id"]]
        score, squads = record["metrics_at_moment"]["score"], record["squads"]
        start = {"period": 1, "minute": 0, "second": 0}
        end = record["moment"]["time"]
        evidence = [record["events"][0]["id"]]
        claims = [
            {"kind": "state", "subject": {"team": side, "player": None}, "metric": "score",
             "comparison": "eq", "value": score[side], "start": start, "end": end, "event_ids": evidence}
            for side in ("home", "away")
        ]
        text = f"{squads['home']['name']} {score['home']}–{score['away']} {squads['away']['name']}."
        assert moment.id == record["moment"]["id"]
        return json.dumps({"text": text, "claims": claims})

    return respond


def test_budget_exceeded_falls_back_cleanly_for_rest_of_match():
    events, _ = match(42, "red_card_swing")
    client = FakeChatClient(responder(events))
    narrator = FoundryNarrator(events, client, config=replace(DEFAULT_EXPLAIN_CONFIG, llm_max_calls_per_run=2))
    results = run_match(events, narrator)

    assert len(client.calls) == 2
    sources = [r.source for _, r in results]
    assert sources[:2] == ["llm", "llm"] and set(sources[2:]) == {"template_fallback"}
    for _, r in results[2:]:
        assert r.trace[0]["error"] == "budget_exceeded"
        assert r.trace[-1]["reason"] == "budget_exceeded"
        assert r.ok


# --- feedback prompta giriyor --------------------------------------------------------------


def test_feedback_items_appear_in_prompt():
    feedback = Feedback(1, (
        FeedbackItem("verify", "value_mismatch", claim_index=0),
        FeedbackItem("lint", "unknown_name", fragment="Arlo Quintana"),
    ))
    user = build_messages(MOMENT, EVENTS, "neutral", "en", feedback)[1]["content"]
    assert "Previous attempt 1 was rejected" in user
    assert "[verify] value_mismatch claim[0]" in user
    assert "[lint] unknown_name fragment='Arlo Quintana'" in user


def test_pipeline_feeds_verifier_feedback_into_second_call():
    good = TEMPLATE.narrate(MOMENT, "neutral", "en")
    wrong = replace(good, claims=(replace(good.claims[0], value=good.claims[0].value + 1), *good.claims[1:]))
    client = FakeChatClient(_draft_json(wrong), _draft_json(good))
    record = run_moment(MOMENT, _narrator(client), EVENTS)
    assert (record.source, record.attempts) == ("llm", 2)
    second = _user(client.calls[1])
    assert "value_mismatch" in second and "claim[0]" in second


# --- Agent Framework adaptörü ---------------------------------------------------------------


class _InnerClient:
    def __init__(self):
        self.seen = None

    async def get_response(self, messages, options):
        self.seen = (messages, options)

        class Response:
            text = '{"text": "x", "claims": []}'
            # agent-framework-core 1.21: UsageDetails bir TypedDict (dict)
            usage_details = {"input_token_count": 12, "output_token_count": 34,
                             "reasoning_output_token_count": 20}

        return Response()


def test_adapter_maps_options_and_usage():
    inner = _InnerClient()
    model = draft_model_for(["m#1"], ["a b"])
    adapter = FoundryChatClientAdapter(inner, message_factory=lambda role, text: (role, text))
    result = asyncio.run(adapter.complete(
        [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
        response_model=model, max_tokens=99,
    ))
    messages, options = inner.seen
    assert messages == [("system", "s"), ("user", "u")]
    assert options == {"max_tokens": 99, "response_format": model}
    assert result == ChatResult('{"text": "x", "claims": []}', 12, 34, 20)


def test_adapter_without_agent_framework_gives_install_hint(monkeypatch):
    # Paket kurulu olsa da olmasa da: sys.modules'ta None → import ImportError verir.
    monkeypatch.setitem(sys.modules, "agent_framework.foundry", None)
    with pytest.raises(ImportError, match="agent-framework-foundry"):
        FoundryChatClientAdapter(project_endpoint="https://example", model="m")
