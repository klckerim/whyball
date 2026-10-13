import asyncio
import json
import logging
import sys
from dataclasses import replace

import pytest
from openai.lib._pydantic import to_strict_json_schema

from app.analytics import detect_moments
from app.explain import DEFAULT_EXPLAIN_CONFIG
from app.explain.llm_narrator import (
    PROMPT_VERSION,
    ChatResult,
    FoundryChatClientAdapter,
    FoundryNarrator,
    MenuDraftOut,
    build_messages,
    moment_record,
    parse_draft,
)
from app.explain.menu import build_menu
from app.explain.narrator import (
    BudgetExceeded,
    Feedback,
    FeedbackItem,
    InvalidNarratorOutput,
    Narrator,
    NarratorTimeout,
)
from app.explain.pipeline import run_match, run_moment
from app.explain.slots import player_ids
from tests.explain_helpers import match, moment_case

EVENTS, MOMENT = moment_case("goal")  # red_card_swing 42, home goal at 22'
MATCH_ID = EVENTS[0].match_id
IDS = player_ids(EVENTS)
ID_OF = {name: pid for pid, name in IDS.items()}
GOAL_REF = f"{MATCH_ID}#{MOMENT.event_ids[-1]}"


def text_json(template):
    """The JSON the model returns (foundry-v5: text only)."""
    return json.dumps({"text": template})


def goal_text(moment=MOMENT, events=EVENTS):
    return f"{{event:{events[0].match_id}#{moment.event_ids[-1]}}}, making it {{score_named}}."


class Sleep:
    def __init__(self, seconds):
        self.seconds = seconds


class FakeChatClient:
    """Replies in order; the last step repeats. Step: str, callable(messages)->str, Sleep, Exception."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = []

    async def complete(self, messages, *, response_model, max_tokens, reasoning_effort=None):
        self.calls.append({"messages": messages, "response_model": response_model,
                           "max_tokens": max_tokens, "reasoning_effort": reasoning_effort})
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


def responder(events):
    """A fake model that picks a valid template from the menu for each moment (moment record only)."""
    moments = {m.id: m for m in detect_moments(events)}

    def respond(messages):
        record, _ = json.JSONDecoder().raw_decode(messages[1]["content"])
        moment = moments[record["moment"]["id"]]
        clauses = {c["id"] for c in record["clauses"]}
        assert {c["id"] for c in record["claims_menu"]} and moment.id == record["moment"]["id"]
        for first in ("dominance", "pressure", "goal", "goals", "sent_off", "penalty"):
            if first in clauses:
                return text_json(f"{{clause:{first}}}, and {{clause:score}}.")
        return text_json("{clause:score}.")

    return respond


def _user(call):
    return call["messages"][1]["content"]


def _narrator(client, **cfg):
    return FoundryNarrator(EVENTS, client, config=replace(DEFAULT_EXPLAIN_CONFIG, **cfg))


# --- moment record and closed schema ---------------------------------------------------------


def test_record_holds_menu_clauses_and_evidence_events():
    system, user = (m["content"] for m in build_messages(MOMENT, EVENTS, "analyst", "en"))
    assert "English" in system and "analyst" in system and "No outside knowledge" in system
    assert "NEVER write digits" in system and "{clause:<clause id>}" in system
    assert "do not link events" in system
    record = json.loads(user)
    assert record == moment_record(MOMENT, EVENTS, "en")
    assert "metrics_at_moment" not in record and "metric_labels" not in record
    menu = build_menu(MOMENT, EVENTS)
    assert [c["id"] for c in record["claims_menu"]] == [c.id for c in menu.claims]
    evidence = {r for c in menu.claims for r in c.claim.event_ids}
    assert {e["id"] for e in record["events"]} == evidence  # every claim's evidence events
    goal = next(e for e in record["events"] if e["id"] == GOAL_REF)
    assert goal["phrase"] == f"{MOMENT.detail['player']} scored at 22'" and goal["selectable"]
    assert goal["player"] == ID_OF[MOMENT.detail["player"]] and goal["minute"] == "22'"
    poss = next(c for c in record["claims_menu"] if c["id"] == "possession")
    assert poss["label"] == "possession" and poss["value"].endswith("%")
    assert next(c for c in record["clauses"] if c["id"] == "score")["text"].startswith("the score is ")
    assert record["squads"]["home"][0] == {"id": "h01", "name": IDS["h01"]}


def test_v5_prompt_rules():
    system = build_messages(MOMENT, EVENTS, "neutral", "en")[0]["content"]
    assert '"selectable": true' in system and "pronoun" in system and 'no article ("the {home}")' in system
    assert "never add that player's" in system and "same minute must not appear twice" in system
    assert 'never put "The"/"the" in front of {clause:}' in system
    assert "Every sentence must use at least one menu fact" in system
    assert '"At"' not in system and '"Possession"' not in system and '"They"' not in system
    events, pressure = moment_case("pressure_shift")
    assert "pressure balance must be used" in build_messages(pressure, events, "neutral", "en")[0]["content"]


def test_response_schema_has_no_claims_or_event_ids():
    schema = to_strict_json_schema(_narrator(FakeChatClient("{}")).response_model(MOMENT))
    assert set(schema["properties"]) == {"text"} and schema["additionalProperties"] is False
    assert "$defs" not in schema  # no field for claims / event links: the evidence_mismatch path is closed


def test_parse_draft_returns_menu_draft():
    menu = build_menu(MOMENT, EVENTS)
    draft = parse_draft(text_json(goal_text()), menu)
    assert draft.template == draft.text == goal_text()
    assert draft.claims == () and draft.menu is menu


# --- valid response -----------------------------------------------------------------------


def test_valid_response_logs_usage_and_sends_reasoning_effort(caplog):
    client = FakeChatClient(text_json(goal_text()))
    narrator = _narrator(client)
    with caplog.at_level(logging.INFO, logger="whyball.llm"):
        draft = narrator.narrate(MOMENT, "neutral", "en")

    assert draft.template is not None and draft.menu is not None
    call = client.calls[0]
    assert call["response_model"] is MenuDraftOut
    assert call["max_tokens"] == DEFAULT_EXPLAIN_CONFIG.llm_max_tokens
    assert call["reasoning_effort"] == DEFAULT_EXPLAIN_CONFIG.llm_reasoning_effort == "low"
    [usage] = narrator.usage
    assert (usage.call, usage.moment_id, usage.outcome, usage.error) == (1, MOMENT.id, "ok", None)
    assert (usage.input_tokens, usage.output_tokens, usage.reasoning_tokens) == (321, 87, 64)
    for field in ("input_tokens=321", "output_tokens=87", "reasoning_tokens=64", "latency_ms="):
        assert field in caplog.text


def test_pipeline_renders_menu_claims_and_clauses():
    teams = EVENTS[0].data["teams"]
    home, away = teams["home"]["name"], teams["away"]["name"]
    record = run_moment(MOMENT, _narrator(FakeChatClient(text_json(goal_text()))), EVENTS)
    assert (record.source, record.attempts, record.ok) == ("llm", 1, True)
    assert record.text == f"{MOMENT.detail['player']} scored at 22', making it {home} 1–0 {away}."
    assert [c.metric for c in record.claims] == ["goals", "score", "score"]
    clause = run_moment(MOMENT, _narrator(FakeChatClient(text_json("{clause:possession}, and {clause:score}."))), EVENTS)
    assert clause.ok and clause.text.startswith(f"{home} have had ") and "of the ball since kickoff" in clause.text
    assert clause.text.endswith(f"and the score is {home} 1–0 {away}.")


def test_away_goal_score_is_rendered_home_first():
    events, moments = match(7, "dominant_loss")
    moment = next(m for m in moments if m.type == "goal")
    narrator = FoundryNarrator(events, FakeChatClient(text_json(goal_text(moment, events))))
    record = run_moment(moment, narrator, events)
    teams = events[0].data["teams"]
    assert record.text.endswith(f"making it {teams['home']['name']} 0–1 {teams['away']['name']}.")


def test_protocol_prompt_version_and_defaults():
    narrator = _narrator(FakeChatClient("{}"))
    assert isinstance(narrator, Narrator)
    assert narrator.prompt_version == PROMPT_VERSION == "foundry-v5.1"
    assert FoundryNarrator(EVENTS, FakeChatClient("{}"), model_tag="gpt-x").prompt_version == "foundry-v5.1:gpt-x"
    assert DEFAULT_EXPLAIN_CONFIG.llm_max_calls_per_run == 60


# --- menu violations are fixed through feedback ---------------------------------------------------


def test_raw_values_in_template_are_rejected_then_fixed():
    client = FakeChatClient(text_json("Murek Brestani scored for the home side at 22'."), text_json(goal_text()))
    record = run_moment(MOMENT, _narrator(client), EVENTS)
    assert (record.source, record.attempts) == ("llm", 2)
    codes = record.trace[3]["codes"]
    assert {"raw_entity", "raw_side_label", "raw_number", "sentence_without_claim"} <= set(codes)
    assert "raw_number" in _user(client.calls[1])


def test_id_outside_menu_is_rejected():
    bad = text_json(goal_text() + " {home} lead at {minute:c9} with {clause:nope}.")
    client = FakeChatClient(bad, text_json(goal_text()))
    record = run_moment(MOMENT, _narrator(client), EVENTS)
    assert record.attempts == 2
    assert record.trace[3]["codes"].count("unknown_claim_id") == 2
    assert "unknown_claim_id" in _user(client.calls[1])


def test_event_outside_menu_evidence_is_rejected():
    bad = text_json(f"{{event:{MATCH_ID}#{MOMENT.event_ids[0]}}}, making it {{score}}.")  # shot event
    record = run_moment(MOMENT, _narrator(FakeChatClient(bad, text_json(goal_text()))), EVENTS)
    assert record.attempts == 2 and "event_not_evidence" in record.trace[3]["codes"]


def test_free_role_verb_is_rejected_then_clause_accepted():
    events, moment = moment_case("penalty")
    pid = {name: p for p, name in player_ids(events).items()}[moment.detail["player"]]
    bad = text_json(f"{{player:{pid}}} saved a penalty at {{minute:penalty}}.")
    good = text_json("{clause:penalty}, and {clause:score}.")
    record = run_moment(moment, FoundryNarrator(events, FakeChatClient(bad, good)), events)
    assert record.attempts == 2 and "event_word" in record.trace[3]["codes"]
    assert record.text.startswith(moment.detail["player"]) and "saved a penalty" not in record.text


# --- broken JSON --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    ["not json", '{"txt": "hi"}', '{"text": "hi", "claims": []}', '{"text": 3}'],
    ids=["not-json", "missing-text", "extra-claims-field", "bad-type"],
)
def test_broken_json_raises_invalid_output(bad):
    narrator = _narrator(FakeChatClient(bad))
    with pytest.raises(InvalidNarratorOutput):
        narrator.narrate(MOMENT, "neutral", "en")
    assert narrator.usage[0].outcome == "invalid_output"
    assert "Response does not match the schema" in narrator.usage[0].error


def test_pipeline_retries_after_broken_json_with_feedback():
    client = FakeChatClient("not json", text_json(goal_text()))
    record = run_moment(MOMENT, _narrator(client), EVENTS)
    assert (record.source, record.attempts) == ("llm", 2)
    assert record.trace[0]["step"] == "narrate" and record.trace[0]["error"] == "invalid_output"
    assert "invalid_output" in _user(client.calls[1])
    assert "FEEDBACK" not in _user(client.calls[0])


# --- timeout and client error ---------------------------------------------------------


def test_timeout_raises_narrator_timeout():
    narrator = _narrator(FakeChatClient(Sleep(1.0)), llm_timeout_s=0.05)
    with pytest.raises(NarratorTimeout, match="0.05"):
        narrator.narrate(MOMENT, "neutral", "en")
    assert narrator.usage[0].outcome == "timeout"
    assert "0.05" in narrator.usage[0].error
    assert narrator.usage[0].latency_ms < 900


def test_pipeline_falls_back_after_repeated_timeouts():
    client = FakeChatClient(Sleep(1.0))
    record = run_moment(MOMENT, _narrator(client, llm_timeout_s=0.05), EVENTS)
    assert (record.source, record.attempts, len(client.calls)) == ("template_fallback", 3, 3)
    assert [s.get("error") for s in record.trace if s["step"] == "narrate"] == ["timeout"] * 3
    assert record.trace[-1]["reason"] == "max_retries_exceeded"
    assert record.ok


def test_client_exception_message_is_logged():
    narrator = _narrator(FakeChatClient(ConnectionError("boom")))
    with pytest.raises(Exception, match="boom") as exc:
        narrator.narrate(MOMENT, "neutral", "en")
    assert exc.value.code == "client_error"
    assert "ConnectionError('boom')" in narrator.usage[0].error


# --- budget exceeded -------------------------------------------------------------------------


def test_budget_exceeded_before_calling_client():
    client = FakeChatClient(text_json(goal_text()))
    narrator = _narrator(client, llm_max_calls_per_run=2)
    narrator.narrate(MOMENT, "neutral", "en")
    narrator.narrate(MOMENT, "neutral", "en")
    with pytest.raises(BudgetExceeded, match="2/2"):
        narrator.narrate(MOMENT, "neutral", "en")
    assert len(client.calls) == 2


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


# --- feedback goes into the prompt --------------------------------------------------------------


def test_feedback_items_appear_in_prompt():
    feedback = Feedback(1, (
        FeedbackItem("lint", "unknown_claim_id", fragment="{value:c9}"),
        FeedbackItem("lint", "raw_entity", fragment="Arlo Quintana"),
    ))
    user = build_messages(MOMENT, EVENTS, "neutral", "en", feedback)[1]["content"]
    assert "Previous attempt 1 was rejected" in user
    assert "[lint] unknown_claim_id fragment='{value:c9}' (use only ids from claims_menu" in user
    assert "[lint] raw_entity fragment='Arlo Quintana'" in user


def test_pipeline_feeds_lint_feedback_into_second_call():
    client = FakeChatClient(text_json("{home} looked lively."), text_json(goal_text()))
    record = run_moment(MOMENT, _narrator(client), EVENTS)
    assert (record.source, record.attempts) == ("llm", 2)
    assert "sentence_without_claim" in _user(client.calls[1])


# --- Agent Framework adapter ---------------------------------------------------------------


class _InnerClient:
    def __init__(self):
        self.seen = None

    async def get_response(self, messages, options):
        self.seen = (messages, options)

        class Response:
            text = '{"text": "x"}'
            # agent-framework-core 1.21: UsageDetails is a TypedDict (dict)
            usage_details = {"input_token_count": 12, "output_token_count": 34,
                             "reasoning_output_token_count": 20}

        return Response()


@pytest.mark.parametrize("effort", ["low", None])
def test_adapter_maps_options_and_usage(effort):
    inner = _InnerClient()
    model = MenuDraftOut
    adapter = FoundryChatClientAdapter(inner, message_factory=lambda role, text: (role, text))
    result = asyncio.run(adapter.complete(
        [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
        response_model=model, max_tokens=99, reasoning_effort=effort,
    ))
    messages, options = inner.seen
    assert messages == [("system", "s"), ("user", "u")]
    expected = {"max_tokens": 99, "response_format": model}
    if effort:
        expected["reasoning"] = {"effort": effort}
    assert options == expected
    assert result == ChatResult('{"text": "x"}', 12, 34, 20)


def test_adapter_without_agent_framework_gives_install_hint(monkeypatch):
    # Whether the package is installed or not: None in sys.modules → the import raises ImportError.
    monkeypatch.setitem(sys.modules, "agent_framework.foundry", None)
    with pytest.raises(ImportError, match="agent-framework-foundry"):
        FoundryChatClientAdapter(project_endpoint="https://example", model="m")
