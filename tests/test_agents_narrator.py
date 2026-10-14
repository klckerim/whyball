"""P2 / 3c: the Narrator agent is foundry-v5.2 wrapped: same prompt, same messages, same drafts."""

import asyncio
import json

import pytest

from app.agents.limits import AgentsConfig, CallBudget
from app.agents.narrator_agent import BRIEFING_HEADER, NarratorAgent, narrator_messages
from app.agents.trace import Stopwatch
from app.explain.config import DEFAULT_EXPLAIN_CONFIG
from app.explain.llm_narrator import PROMPT_VERSION, SYSTEM_PROMPT, FoundryNarrator, build_messages
from app.explain.menu import build_menu
from app.explain.narrator import BudgetExceeded, Feedback, FeedbackItem, InvalidNarratorOutput, NarratorTimeout
from tests.agent_fakes import ScriptedClient, Sleep, draft_json
from tests.explain_helpers import moment_case

EVENTS, MOMENT = moment_case("goal")
MENU = build_menu(MOMENT, EVENTS)
GOOD = "{clause:goal}."


def run(coro):
    return asyncio.run(coro)


def agent(client, budget=None, **kw):
    return NarratorAgent(EVENTS, client, budget=budget or CallBudget(50), model_tag="m", **kw)


def write(a, **kw):
    return run(a.write(MOMENT, MENU, attempt=kw.pop("attempt", 1), clock=Stopwatch(), **kw))


def test_the_prompt_version_is_still_foundry_v5_2():
    assert PROMPT_VERSION == "foundry-v5.2"
    assert agent(ScriptedClient(MenuDraftOut=draft_json(GOOD))).prompt_version == "foundry-v5.2:m"
    # the system prompt text itself: frozen; a hash keeps an accidental edit from passing unnoticed
    import hashlib
    assert hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:16] == "9ab7b72db56779b8"


def test_same_input_same_messages_as_the_foundry_narrator():
    fb = Feedback(1, (FeedbackItem("lint", "raw_number", fragment="3"),))
    for feedback in (None, fb):
        expected = build_messages(MOMENT, EVENTS, "neutral", "en", feedback, DEFAULT_EXPLAIN_CONFIG, MENU)
        assert narrator_messages(MOMENT, EVENTS, "neutral", "en", feedback, DEFAULT_EXPLAIN_CONFIG, MENU) == expected
        sync_client = ScriptedClient(MenuDraftOut=draft_json(GOOD))
        FoundryNarrator(EVENTS, sync_client, model_tag="m").narrate(MOMENT, "neutral", "en", feedback)
        agent_client = ScriptedClient(MenuDraftOut=draft_json(GOOD))
        write(agent(agent_client), feedback=feedback)
        assert agent_client.calls[0]["messages"] == sync_client.calls[0]["messages"] == expected
        for key in ("max_tokens", "reasoning_effort"):
            assert agent_client.calls[0][key] == sync_client.calls[0][key]


def test_the_draft_is_the_foundry_narrators_draft():
    sync = FoundryNarrator(EVENTS, ScriptedClient(MenuDraftOut=draft_json(GOOD)), model_tag="m")
    expected = sync.narrate(MOMENT, "neutral", "en")
    got = write(agent(ScriptedClient(MenuDraftOut=draft_json(GOOD)))).draft
    assert got is not None and (got.text, got.template, got.claims, got.claim_ids) == (
        expected.text, expected.template, expected.claims, expected.claim_ids)
    assert got.menu == expected.menu


def test_a_briefing_note_goes_into_the_user_message_only():
    base = build_messages(MOMENT, EVENTS, "neutral", "en", None, DEFAULT_EXPLAIN_CONFIG, MENU)
    with_note = narrator_messages(MOMENT, EVENTS, "neutral", "en", None, DEFAULT_EXPLAIN_CONFIG, MENU, "a late goal")
    assert with_note[0] == base[0]  # system prompt untouched
    assert with_note[1]["content"] == base[1]["content"] + BRIEFING_HEADER + "a late goal"


def test_the_note_comes_before_the_feedback_block():
    fb = Feedback(1, (FeedbackItem("guard", "raw_number"),))
    user = narrator_messages(MOMENT, EVENTS, "neutral", "en", fb, DEFAULT_EXPLAIN_CONFIG, MENU, "note")[1]["content"]
    assert user.index("BRIEFING") < user.index("FEEDBACK")
    assert json.JSONDecoder().raw_decode(user)[0]["moment"]["id"] == MOMENT.id  # the record is still the JSON head


def test_no_note_leaves_the_messages_alone():
    assert narrator_messages(MOMENT, EVENTS, "neutral", "en", None, DEFAULT_EXPLAIN_CONFIG, MENU, None) == \
        build_messages(MOMENT, EVENTS, "neutral", "en", None, DEFAULT_EXPLAIN_CONFIG, MENU)


# --- results and failures --------------------------------------------------------------------------------


def test_success_gives_a_trace_step_with_tokens_and_the_template():
    r = write(agent(ScriptedClient(MenuDraftOut=draft_json(GOOD))), attempt=2)
    assert r.error is None and r.draft is not None
    s = r.step
    assert (s.step, s.agent, s.attempt, s.status, s.model) == ("narrate", "narrator", 2, "ok", "m")
    assert s.output["template"] == GOOD and s.output["feedback"] == []
    assert (s.tokens.input, s.tokens.output, s.tokens.reasoning) == (321, 87, 64)
    assert r.usage.outcome == "ok" and s.input_ref == "menu"


def test_feedback_codes_are_in_the_step_and_the_note_in_the_input_ref():
    fb = Feedback(1, (FeedbackItem("verifier", "role_reversed"),))
    r = write(agent(ScriptedClient(MenuDraftOut=draft_json(GOOD))), feedback=fb, note="n")
    assert r.step.output["feedback"] == ["role_reversed"] and r.step.input_ref == "menu+briefing"


def test_a_client_error_is_a_result_not_a_crash():
    r = write(agent(ScriptedClient(MenuDraftOut=RuntimeError("boom"))))
    assert r.draft is None and r.error is not None and r.error.code == "client_error"
    assert r.step.status == "error" and r.step.output["error"] == "client_error"


def test_a_timeout_is_a_result_and_uses_the_configured_limit():
    a = agent(ScriptedClient(MenuDraftOut=Sleep(5)), agents=AgentsConfig(narrator_timeout_s=0.05))
    r = write(a)
    assert isinstance(r.error, NarratorTimeout) and r.step.status == "timeout" and r.draft is None
    assert r.step.duration_ms < 2000


def test_a_reply_that_breaks_the_schema_is_invalid_output():
    r = write(agent(ScriptedClient(MenuDraftOut='{"text": "x", "extra": 1}')))
    assert isinstance(r.error, InvalidNarratorOutput) and r.step.status == "error"
    assert r.step.tokens is not None  # the call happened and cost tokens


def test_the_shared_budget_stops_calls_without_calling_the_model():
    client = ScriptedClient(MenuDraftOut=draft_json(GOOD))
    a = agent(client, budget=CallBudget(1))
    assert write(a).error is None
    r = write(a)
    assert isinstance(r.error, BudgetExceeded) and r.draft is None and client.count("MenuDraftOut") == 1


def test_usage_records_every_call_including_failures():
    a = agent(ScriptedClient(MenuDraftOut=[RuntimeError("x"), draft_json(GOOD)]))
    write(a)
    write(a)
    assert [u.outcome for u in a.usage] == ["client_error", "ok"] and [u.call for u in a.usage] == [1, 2]
