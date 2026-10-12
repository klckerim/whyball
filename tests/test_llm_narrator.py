import asyncio
import json
import logging
import sys
from dataclasses import replace

import pytest

from app.analytics import detect_moments
from app.explain import DEFAULT_EXPLAIN_CONFIG
from app.explain.llm_narrator import (
    PROMPT_VERSION,
    ChatResult,
    DraftOut,
    FoundryChatClientAdapter,
    FoundryNarrator,
    build_messages,
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


def _draft_json(draft):
    return json.dumps({"text": draft.text, "claims": [c.to_dict() for c in draft.claims]})


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
        return ChatResult(text, input_tokens=321, output_tokens=87)


def _user(call):
    return call["messages"][1]["content"]


def _narrator(client, **cfg):
    return FoundryNarrator(EVENTS, client, config=replace(DEFAULT_EXPLAIN_CONFIG, **cfg))


# --- geçerli yanıt -----------------------------------------------------------------------


def test_valid_response_becomes_draft_and_logs_usage(caplog):
    client = FakeChatClient(_template_json(MOMENT))
    narrator = _narrator(client)
    with caplog.at_level(logging.INFO, logger="whyball.llm"):
        draft = narrator.narrate(MOMENT, "neutral", "en")

    assert draft == TEMPLATE.narrate(MOMENT, "neutral", "en")
    assert client.calls[0]["max_tokens"] == DEFAULT_EXPLAIN_CONFIG.llm_max_tokens
    assert client.calls[0]["response_model"] is DraftOut
    [usage] = narrator.usage
    assert (usage.call, usage.moment_id, usage.outcome) == (1, MOMENT.id, "ok")
    assert (usage.input_tokens, usage.output_tokens) == (321, 87)
    assert "input_tokens=321" in caplog.text and "output_tokens=87" in caplog.text


def test_valid_response_passes_pipeline():
    narrator = _narrator(FakeChatClient(_template_json(MOMENT)))
    record = run_moment(MOMENT, narrator, EVENTS)
    assert (record.source, record.attempts, record.ok) == ("llm", 1, True)


def test_protocol_and_prompt_version():
    narrator = _narrator(FakeChatClient("{}"))
    assert isinstance(narrator, Narrator)
    assert narrator.prompt_version == PROMPT_VERSION == "foundry-v1"
    tagged = FoundryNarrator(EVENTS, FakeChatClient("{}"), model_tag="gpt-x")
    assert tagged.prompt_version == "foundry-v1:gpt-x"


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


def test_budget_exceeded_falls_back_cleanly_for_rest_of_match():
    events, _ = match(42, "red_card_swing")

    def respond(messages):
        payload, _ = json.JSONDecoder().raw_decode(messages[1]["content"])
        moment = next(m for m in detect_moments(events) if m.id == payload["moment"]["id"])
        return _template_json(moment, events=events)

    client = FakeChatClient(respond)
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


def test_prompt_contains_allowed_event_ids_and_language():
    system, user = (m["content"] for m in build_messages(MOMENT, EVENTS, "analyst", "tr"))
    assert "Turkish" in system and "analyst" in system
    payload = json.loads(user)
    assert payload["allowed_event_ids"] == [f"{EVENTS[0].match_id}#{s}" for s in MOMENT.event_ids]


# --- Agent Framework adaptörü ---------------------------------------------------------------


class _InnerClient:
    def __init__(self):
        self.seen = None

    async def get_response(self, messages, options):
        self.seen = (messages, options)

        class Usage:
            input_token_count = 12
            output_token_count = 34

        class Response:
            text = '{"text": "x", "claims": []}'
            usage_details = Usage()

        return Response()


def test_adapter_maps_options_and_usage():
    inner = _InnerClient()
    adapter = FoundryChatClientAdapter(inner, message_factory=lambda role, text: (role, text))
    result = asyncio.run(adapter.complete(
        [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
        response_model=DraftOut, max_tokens=99,
    ))
    messages, options = inner.seen
    assert messages == [("system", "s"), ("user", "u")]
    assert options == {"max_tokens": 99, "response_format": DraftOut}
    assert result == ChatResult('{"text": "x", "claims": []}', 12, 34)


def test_adapter_without_agent_framework_gives_install_hint(monkeypatch):
    # Paket kurulu olsa da olmasa da: sys.modules'ta None → import ImportError verir.
    monkeypatch.setitem(sys.modules, "agent_framework.foundry", None)
    with pytest.raises(ImportError, match="agent-framework-foundry"):
        FoundryChatClientAdapter(project_endpoint="https://example", model="m")
