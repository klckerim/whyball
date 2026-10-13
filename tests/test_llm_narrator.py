import asyncio
import json
import logging
import sys
from dataclasses import replace

import pytest
from openai.lib._pydantic import to_strict_json_schema

from app.analytics import detect_moments
from app.explain import DEFAULT_EXPLAIN_CONFIG
from app.explain.claims import KICKOFF, METRIC_KINDS, Claim, MatchTime, Subject
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
)
from app.explain.pipeline import run_match, run_moment
from app.explain.slots import player_ids
from tests.explain_helpers import match, moment_case

EVENTS, MOMENT = moment_case("goal")  # red_card_swing 42, 22' ev sahibi golü
MATCH_ID = EVENTS[0].match_id
IDS = player_ids(EVENTS)
ID_OF = {name: pid for pid, name in IDS.items()}


def _t(time):
    return {"period": time[0], "minute": time[1], "second": time[2]}


def slot_json(template, claims, claim_ids, events=EVENTS):
    """Slot taslağını modelin döndüreceği JSON'a çevirir (oyuncu adı → id)."""
    id_of = {name: pid for pid, name in player_ids(events).items()}
    out = []
    for cid, c in zip(claim_ids, claims):
        d = c.to_dict()
        d.update(
            id=cid, start=_t(c.start), end=_t(c.end),
            subject={"team": c.subject.team, "player": id_of.get(c.subject.player)},
        )
        out.append(d)
    return json.dumps({"text": template, "claims": out})


def goal_slot(moment=MOMENT, events=EVENTS, value=1):
    t = MatchTime(moment.period, moment.minute, moment.second)
    player, side = moment.detail["player"], moment.team
    ref = f"{events[0].match_id}#{moment.event_ids[-1]}"
    claim = Claim("count", Subject(side, player), "goals", "eq", value, t, t, (ref,))
    return f"{{event:{ref}}}, making it {{score_named}}.", (claim,), ("c1",)


class Sleep:
    def __init__(self, seconds):
        self.seconds = seconds


class FakeChatClient:
    """Sırayla yanıt verir; son adım tekrarlanır. Adım: str, callable(messages)->str, Sleep, Exception."""

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
    """Her moment için kapalı şemaya uyan slot taslağı üreten sahte model (yalnızca moment kaydı)."""
    moments = {m.id: m for m in detect_moments(events)}

    def respond(messages):
        record, _ = json.JSONDecoder().raw_decode(messages[1]["content"])
        moment = moments[record["moment"]["id"]]
        end = MatchTime(**record["moment"]["time"])
        ref = record["events"][0]["id"]
        claim = Claim("state", Subject("home"), "score", "eq", record["metrics_at_moment"]["score"]["home"],
                      KICKOFF, end, (ref,))
        assert moment.id == record["moment"]["id"]
        return slot_json("{score_named} at {minute:c1}.", (claim,), ("c1",), events)

    return respond


# --- moment kaydı ve kapalı şema ---------------------------------------------------------


def test_prompt_contains_only_the_moment_record():
    system, user = (m["content"] for m in build_messages(MOMENT, EVENTS, "analyst", "tr"))
    assert "Turkish" in system and "analyst" in system and "No outside knowledge" in system
    assert "NEVER write digits" in system and "{score}" in system
    assert "{event:<event id>}" in system and "{score_named}" in system
    assert "leaving" not in system  # bozuk "leaving X with {score}" kalıbı örneklerde yok
    record = json.loads(user)
    assert record == moment_record(MOMENT, EVENTS, "tr")
    assert [e["id"] for e in record["events"]] == [f"{MATCH_ID}#{s}" for s in MOMENT.event_ids]
    assert {e["player"] for e in record["events"]} == {ID_OF[MOMENT.detail["player"]]}
    assert record["metrics_at_moment"] == MOMENT.metrics
    assert record["events"][-1]["phrase"] == f"{MOMENT.detail['player']} gol attı (22')"
    assert record["metric_labels"]["possession"] == "topa sahip olma"
    assert record["squads"]["home"][0] == {"id": "h01", "name": IDS["h01"]}
    allowed = {f"{MATCH_ID}#{s}" for s in MOMENT.event_ids}
    mentioned = {tok.strip('",') for tok in user.split() if f"{MATCH_ID}#" in tok}
    assert mentioned <= allowed


def test_response_schema_is_closed_per_moment():
    schema = to_strict_json_schema(_narrator(FakeChatClient("{}")).response_model(MOMENT))
    claim = schema["$defs"]["ClaimOut"]
    assert claim["properties"]["event_ids"]["items"]["enum"] == [f"{MATCH_ID}#{s}" for s in MOMENT.event_ids]
    assert claim["properties"]["metric"]["enum"] == list(METRIC_KINDS)
    assert claim["properties"]["kind"]["enum"] == ["count", "ratio", "state"]
    assert claim["properties"]["id"]["type"] == "string"
    players = schema["$defs"]["SubjectOut"]["properties"]["player"]["anyOf"][0]["enum"]
    assert players == list(IDS)
    assert claim["additionalProperties"] is False


def test_event_id_outside_moment_is_rejected_by_schema():
    template, (claim,), ids = goal_slot()
    foreign = replace(claim, event_ids=(f"{MATCH_ID}#0",))
    with pytest.raises(InvalidNarratorOutput):
        _narrator(FakeChatClient(slot_json(template, (foreign,), ids))).narrate(MOMENT, "neutral", "en")


def test_parse_draft_returns_slot_draft_with_player_names():
    template, claims, ids = goal_slot()
    model = draft_model_for([f"{MATCH_ID}#{s}" for s in MOMENT.event_ids], list(IDS))
    draft = parse_draft(model, slot_json(template, claims, ids), IDS)
    assert draft.template == draft.text == template
    assert draft.claim_ids == ("c1",)
    assert draft.claims == claims  # oyuncu id'si ada çevrildi


# --- geçerli yanıt -----------------------------------------------------------------------


def test_valid_response_logs_usage_and_sends_reasoning_effort(caplog):
    client = FakeChatClient(slot_json(*goal_slot()))
    narrator = _narrator(client)
    with caplog.at_level(logging.INFO, logger="whyball.llm"):
        draft = narrator.narrate(MOMENT, "neutral", "en")

    assert draft.template is not None
    call = client.calls[0]
    assert call["max_tokens"] == DEFAULT_EXPLAIN_CONFIG.llm_max_tokens
    assert call["reasoning_effort"] == DEFAULT_EXPLAIN_CONFIG.llm_reasoning_effort == "low"
    [usage] = narrator.usage
    assert (usage.call, usage.moment_id, usage.outcome, usage.error) == (1, MOMENT.id, "ok", None)
    assert (usage.input_tokens, usage.output_tokens, usage.reasoning_tokens) == (321, 87, 64)
    for field in ("input_tokens=321", "output_tokens=87", "reasoning_tokens=64", "latency_ms="):
        assert field in caplog.text


def test_pipeline_renders_slots_from_verified_claims():
    record = run_moment(MOMENT, _narrator(FakeChatClient(slot_json(*goal_slot()))), EVENTS)
    teams = EVENTS[0].data["teams"]
    home, away = teams["home"]["name"], teams["away"]["name"]
    assert (record.source, record.attempts, record.ok) == ("llm", 1, True)
    assert record.template.startswith("{event:")
    assert record.text == f"{MOMENT.detail['player']} scored at 22', making it {home} 1–0 {away}."
    assert [c.metric for c in record.claims] == ["goals", "score", "score"]  # + otomatik skor iddiaları


def test_away_goal_score_is_rendered_home_first():
    events, moments = match(7, "dominant_loss")
    moment = next(m for m in moments if m.type == "goal")
    template, claims, ids = goal_slot(moment, events)
    narrator = FoundryNarrator(events, FakeChatClient(slot_json(template, claims, ids, events)))
    record = run_moment(moment, narrator, events)
    teams = events[0].data["teams"]
    assert record.text.endswith(f"making it {teams['home']['name']} 0–1 {teams['away']['name']}.")


def test_protocol_prompt_version_and_defaults():
    narrator = _narrator(FakeChatClient("{}"))
    assert isinstance(narrator, Narrator)
    assert narrator.prompt_version == PROMPT_VERSION == "foundry-v4"
    assert FoundryNarrator(EVENTS, FakeChatClient("{}"), model_tag="gpt-x").prompt_version == "foundry-v4:gpt-x"
    assert DEFAULT_EXPLAIN_CONFIG.llm_max_calls_per_run == 60


# --- slot ihlalleri geri bildirimle düzelir --------------------------------------------------


def test_raw_values_in_template_are_rejected_then_fixed():
    raw = slot_json("Murek Brestani scored for the home side at 22'.", goal_slot()[1], ("c1",))
    client = FakeChatClient(raw, slot_json(*goal_slot()))
    record = run_moment(MOMENT, _narrator(client), EVENTS)
    assert (record.source, record.attempts) == ("llm", 2)
    codes = record.trace[3]["codes"]
    assert {"raw_entity", "raw_side_label", "raw_number"} <= set(codes)
    assert "raw_number" in _user(client.calls[1])


def test_unbound_placeholder_is_rejected():
    template, claims, ids = goal_slot()
    bad = slot_json(template + " {home} lead at {minute:c9}.", claims, ids)
    record = run_moment(MOMENT, _narrator(FakeChatClient(bad, slot_json(template, claims, ids))), EVENTS)
    assert record.attempts == 2 and "unbound_placeholder" in record.trace[3]["codes"]


def test_free_role_verb_is_rejected_then_event_placeholder_accepted():
    # v3'te yayınlanan rol hatası: "{player:h02} saved a penalty at {minute:c1}" (h02 penaltıyı kullanandı).
    events, moment = moment_case("penalty")
    t = MatchTime(moment.period, moment.minute, moment.second)
    taker, outcome = moment.detail["player"], moment.detail["outcome"]
    ref = f"{events[0].match_id}#{moment.event_ids[-1]}"
    claim = Claim("count", Subject(moment.team, taker), f"penalties_{outcome}", "eq", 1, t, t, (ref,))
    pid = {name: p for p, name in player_ids(events).items()}[taker]
    bad = slot_json(f"{{player:{pid}}} saved a penalty at {{minute:c1}}.", (claim,), ("c1",), events)
    good = slot_json(f"{{event:{ref}}}.", (claim,), ("c1",), events)
    record = run_moment(moment, FoundryNarrator(events, FakeChatClient(bad, good)), events)
    assert record.attempts == 2 and "event_word" in record.trace[3]["codes"]
    assert record.text.startswith(taker) and "saved a penalty" not in record.text


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
    assert "Şemaya uymayan" in narrator.usage[0].error


def test_pipeline_retries_after_broken_json_with_feedback():
    client = FakeChatClient("not json", slot_json(*goal_slot()))
    record = run_moment(MOMENT, _narrator(client), EVENTS)
    assert (record.source, record.attempts) == ("llm", 2)
    assert record.trace[0]["step"] == "narrate" and record.trace[0]["error"] == "invalid_output"
    assert "invalid_output" in _user(client.calls[1])
    assert "FEEDBACK" not in _user(client.calls[0])


# --- zaman aşımı ve istemci hatası ---------------------------------------------------------


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


# --- bütçe aşımı -------------------------------------------------------------------------


def test_budget_exceeded_before_calling_client():
    client = FakeChatClient(slot_json(*goal_slot()))
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


# --- feedback prompta giriyor --------------------------------------------------------------


def test_feedback_items_appear_in_prompt():
    feedback = Feedback(1, (
        FeedbackItem("verify", "value_mismatch", claim_index=0),
        FeedbackItem("lint", "raw_entity", fragment="Arlo Quintana"),
    ))
    user = build_messages(MOMENT, EVENTS, "neutral", "en", feedback)[1]["content"]
    assert "Previous attempt 1 was rejected" in user
    assert "[verify] value_mismatch claim[0]" in user
    assert "[lint] raw_entity fragment='Arlo Quintana'" in user


def test_pipeline_feeds_verifier_feedback_into_second_call():
    client = FakeChatClient(slot_json(*goal_slot(value=2)), slot_json(*goal_slot()))
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


@pytest.mark.parametrize("effort", ["low", None])
def test_adapter_maps_options_and_usage(effort):
    inner = _InnerClient()
    model = draft_model_for(["m#1"], ["h01"])
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
    assert result == ChatResult('{"text": "x", "claims": []}', 12, 34, 20)


def test_adapter_without_agent_framework_gives_install_hint(monkeypatch):
    # Paket kurulu olsa da olmasa da: sys.modules'ta None → import ImportError verir.
    monkeypatch.setitem(sys.modules, "agent_framework.foundry", None)
    with pytest.raises(ImportError, match="agent-framework-foundry"):
        FoundryChatClientAdapter(project_endpoint="https://example", model="m")
