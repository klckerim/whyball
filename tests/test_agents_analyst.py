"""P2 / 3d: the Analyst narrows the Narrator's input; any failure falls back to the full menu."""

import asyncio
import json

import pytest

from app.agents.analyst import (
    ANALYST_PROMPT, NOTE_MAX_CHARS, AnalystAgent, AnalystOut, BriefingError, effective_claim_ids, effective_menu,
    narrow_menu, validate_briefing,
)
from app.agents.limits import AgentsConfig, CallBudget
from app.agents.narrator_agent import narrator_messages
from app.agents.trace import Stopwatch
from app.explain.config import DEFAULT_EXPLAIN_CONFIG
from app.explain.menu import build_menu
from app.explain.llm_narrator import moment_record
from tests.agent_fakes import ScriptedClient, Sleep
from tests.explain_helpers import moment_case


def run(coro):
    return asyncio.run(coro)


def case(name):
    events, moment = moment_case(name)
    return events, moment, build_menu(moment, events)


def analyst(events, client, budget=None, **kw):
    return AnalystAgent(events, client, budget=budget or CallBudget(20), model_tag="m", **kw)


def brief(a, moment, menu):
    return run(a.brief(moment, menu, clock=Stopwatch()))


def reply(ids, note="why it matters"):
    return json.dumps({"claim_ids": ids, "context_note": note})


# --- validation ---------------------------------------------------------------------------------------------


def test_a_valid_answer_becomes_a_briefing_with_what_the_narrator_needs():
    _, _, menu = case("dominance_without_reward")
    b = validate_briefing(AnalystOut(claim_ids=["shots_for"], context_note="a side on top without a goal"), menu)
    ids = set(b.claim_ids)
    assert {"shots_for", "shots_against"} <= ids  # the shots clause needs both
    assert {"possession", "score_home", "score_away"} <= ids  # primary groups are always kept
    assert b.context_note == "a side on top without a goal"
    assert list(b.claim_ids) == [c.id for c in menu.claims if c.id in ids]  # menu order


@pytest.mark.parametrize("out,code", [
    (AnalystOut(claim_ids=[], context_note="x"), "empty_selection"),
    (AnalystOut(claim_ids=["goal", "goal"], context_note="x"), "duplicate_claim_id"),
    (AnalystOut(claim_ids=["not_on_the_menu"], context_note="x"), "unknown_claim_id"),
    (AnalystOut(claim_ids=["goal"], context_note="x" * (NOTE_MAX_CHARS + 1)), "note_too_long"),
    (AnalystOut(claim_ids=["goal"], context_note="he scored in the 90th minute"), "note_has_number"),
    (AnalystOut(claim_ids=["goal"], context_note="the third goal"), "note_has_number"),
    (AnalystOut(claim_ids=["goal"], context_note="see {value:goal}"), "note_has_placeholder"),
])
def test_invalid_answers_are_refused_with_a_code(out, code):
    _, _, menu = case("goal")
    with pytest.raises(BriefingError) as e:
        validate_briefing(out, menu)
    assert e.value.code == code


def test_the_answer_schema_has_no_field_for_facts():
    assert set(AnalystOut.model_fields) == {"claim_ids", "context_note"}
    with pytest.raises(Exception):
        AnalystOut.model_validate_json('{"claim_ids": [], "context_note": "", "text": "published?"}')


def test_effective_ids_are_closed_under_clauses_and_primary_groups():
    _, _, menu = case("pressure_shift")
    ids = effective_claim_ids(menu, ["shots_for"])
    assert "shots_against" in ids and "pressure" in ids  # clause "shots"; primary pressure claim
    assert set(ids) <= {c.id for c in menu.claims}


# --- narrowing ----------------------------------------------------------------------------------------------


def test_the_narrowed_menu_keeps_only_clauses_it_can_fully_support():
    _, _, menu = case("goal")
    ids = effective_claim_ids(menu, ["goal"])
    narrow = narrow_menu(menu, ids)
    assert {c.id for c in narrow.claims} == set(ids)
    assert all(set(c.claim_ids) <= set(ids) for c in narrow.clauses)
    assert all(g <= set(ids) for g in narrow.primary)
    assert narrow.moment_id == menu.moment_id


def test_no_briefing_means_the_full_menu():
    _, _, menu = case("goal")
    assert effective_menu(menu, None) is menu


def test_the_narrator_sees_only_the_narrowed_claims_and_the_note():
    events, moment, menu = case("dominance_without_reward")
    b = validate_briefing(AnalystOut(claim_ids=["possession"], context_note="dominance without a goal"), menu)
    narrow = effective_menu(menu, b)
    user = narrator_messages(moment, events, "neutral", "en", None, DEFAULT_EXPLAIN_CONFIG, narrow, b.context_note)[1]["content"]
    record = json.JSONDecoder().raw_decode(user)[0]
    assert {c["id"] for c in record["claims_menu"]} == {c.id for c in narrow.claims}
    assert user.endswith("dominance without a goal")


# --- the agent ----------------------------------------------------------------------------------------------


def test_a_good_answer_gives_a_briefing_and_one_step():
    events, moment, menu = case("goal")
    client = ScriptedClient(AnalystOut=reply(["goal", "team_goals"]))
    r = brief(analyst(events, client), moment, menu)
    assert r.briefing is not None and len(r.steps) == 1
    s = r.steps[0]
    assert (s.step, s.agent, s.status, s.attempt, s.model) == ("analyst", "analyst", "ok", 0, "m")
    assert s.output["selected"] == ["goal", "team_goals"] and s.output["note"] == "why it matters"
    assert s.tokens.input == 321
    # it asked once, with the analyst prompt as system message and the moment record as user message
    call = client.calls[0]
    assert call["model"] == "AnalystOut" and call["messages"][0]["content"].startswith("You are the analyst")
    assert json.loads(call["messages"][1]["content"])["moment"]["id"] == moment.id


def test_the_analyst_sees_what_the_narrator_sees_and_nothing_more():
    events, moment, menu = case("goal")
    a = analyst(events, ScriptedClient(AnalystOut=reply(["goal"])))
    assert a.messages(moment, menu)[1]["content"] == json.dumps(
        moment_record(moment, events, "en", menu), ensure_ascii=False, sort_keys=True)
    assert "{note_max}" not in ANALYST_PROMPT.format(note_max=NOTE_MAX_CHARS)


@pytest.mark.parametrize("script,reason,status", [
    (RuntimeError("boom"), "client_error", "error"),
    (Sleep(5), "timeout", "timeout"),
    ("not json", "invalid_output", "error"),
    (json.dumps({"claim_ids": ["goal"], "context_note": "x", "extra": 1}), "invalid_output", "error"),
    (reply(["ghost"]), "unknown_claim_id", "error"),
    (reply(["goal"], "the 90th minute"), "note_has_number", "error"),
])
def test_any_failure_falls_back_to_the_full_menu_with_a_trace_step(script, reason, status):
    events, moment, menu = case("goal")
    a = analyst(events, ScriptedClient(AnalystOut=script), agents=AgentsConfig(analyst_timeout_s=0.05))
    r = brief(a, moment, menu)
    assert r.briefing is None  # the workflow then gives the Narrator the full menu
    assert [s.step for s in r.steps] == ["analyst", "analyst_fallback"]
    assert r.steps[0].status == status and r.steps[0].output["error"] == reason
    assert r.steps[1].status == "ok" and r.steps[1].output == {"menu": "full", "reason": reason}
    assert effective_menu(menu, r.briefing) is menu


def test_a_spent_budget_falls_back_without_calling_the_model():
    events, moment, menu = case("goal")
    client = ScriptedClient(AnalystOut=reply(["goal"]))
    r = brief(analyst(events, client, budget=CallBudget(0)), moment, menu)
    assert r.briefing is None and client.calls == [] and r.steps[1].step == "analyst_fallback"


def test_the_analyst_cannot_remove_a_primary_claim():
    events, moment, menu = case("pressure_shift")
    r = brief(analyst(events, ScriptedClient(AnalystOut=reply(["score_home"]))), moment, menu)
    assert r.briefing is not None
    assert "pressure" in r.briefing.claim_ids  # the primary claim came back
