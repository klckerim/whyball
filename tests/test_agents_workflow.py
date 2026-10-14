"""P2 / 3f: the agent graph on Agent Framework, with a scripted fake client (no model, no network).

Covers the loop and its limits (3 attempts in the edges, `max_iterations` only an emergency cap), both agents' failures,
the four guarantees, concurrency, and an exception inside the workflow."""

import asyncio
from collections import Counter

import pytest

from app.agents import tools, workflow as wf_mod
from app.agents.guard import guard_check
from app.agents.limits import AgentsConfig, CallBudget
from app.agents.state import Flags
from app.agents.workflow import EMERGENCY_MAX_ITERATIONS, AgentWorkflow
from app.explain.menu import build_menu
from tests.agent_fakes import (
    VERDICT_PASS, ScriptedClient, Sleep, analyst_reply, draft_json, passing_template, verdict_reject,
)
from tests.explain_helpers import moment_case

EVENTS, MOMENT = moment_case("goal")
MENU = build_menu(MOMENT, EVENTS)
ALL_IDS = [c.id for c in MENU.claims]
GOOD = passing_template(MOMENT, EVENTS)
BAD = "{clause:goal}, and 3 shots."  # a digit: the Guard rejects it


def card(client, *, flags=Flags(), agents=AgentsConfig(), moment=MOMENT, events=EVENTS, **kw):
    w = AgentWorkflow(events, client, flags=flags, agents=agents, model_tag="m", **kw)
    return asyncio.run(w.run_card(moment)), w


def client(draft=GOOD, verdict=VERDICT_PASS, analyst=None):
    return ScriptedClient(MenuDraftOut=draft if isinstance(draft, list) else [draft_json(d) for d in [draft]] if isinstance(draft, str) else draft,
                          VerifierOut=verdict, AnalystOut=analyst or analyst_reply(ALL_IDS))


def steps(out):
    return [s.step for s in out.trace]


def narrator_users(c):
    return [x["messages"][1]["content"] for x in c.calls if x["model"] == "MenuDraftOut"]


# --- the happy path ---------------------------------------------------------------------------------------


def test_all_agents_agree_first_time():
    c = client()
    out, _ = card(c)
    assert steps(out) == ["analyst", "narrate", "guard", "verify", "finalize"]
    k = out.card
    assert k.source == "llm" and k.verification.to_dict() == {
        "guard": True, "verifier": "passed", "attempts": 1, "label_source": "llm"}
    assert Counter(x["model"] for x in c.calls) == {"AnalystOut": 1, "MenuDraftOut": 1, "VerifierOut": 1}
    assert k.text and k.template == GOOD and "".join(p.text for p in k.parts) == k.text
    assert [s.agent for s in out.trace] == ["analyst", "narrator", "guard", "verifier", "workflow"]
    assert all(s.status == "ok" for s in out.trace)


def test_the_text_is_what_the_guard_renders_from_the_template():
    out, _ = card(client())
    g = asyncio.run(guard_check(GOOD, MENU, tools.slot_context(MOMENT, EVENTS)))
    assert out.card.text == g.text and out.card.parts == g.parts and out.card.claim_ids == g.claim_ids


def test_trace_steps_are_timed_in_order_and_carry_tokens_and_model():
    out, _ = card(client())
    starts = [s.started_ms for s in out.trace]
    assert starts == sorted(starts)
    by = {s.step: s for s in out.trace}
    assert by["narrate"].tokens.output == 87 and by["narrate"].model == "m"
    assert by["analyst"].tokens.input == 321 and by["guard"].tokens is None or by["guard"].to_dict()["tokens"]["in"] is None


# --- the feedback loop ------------------------------------------------------------------------------------


def test_a_guard_rejection_goes_back_to_the_narrator_with_coded_feedback():
    c = client(draft=[draft_json(BAD), draft_json(GOOD)])
    out, _ = card(c)
    assert steps(out) == ["analyst", "narrate", "guard", "retry", "narrate", "guard", "verify", "finalize"]
    users = narrator_users(c)
    assert "FEEDBACK" not in users[0] and "raw_number" in users[1].split("FEEDBACK")[1]
    assert out.card.verification.verifier == "retried_then_passed" and out.card.verification.attempts == 2
    assert c.count("VerifierOut") == 1  # the Verifier only sees drafts the Guard accepted
    assert out.state.feedback_history[0].codes and out.state.feedback_history[0].attempt == 1


def test_a_verifier_rejection_goes_back_to_the_narrator_with_its_code():
    g = asyncio.run(guard_check(GOOD, MENU, tools.slot_context(MOMENT, EVENTS)))
    span = g.text.split()[0]
    c = client(verdict=[verdict_reject(span, "role_reversed"), VERDICT_PASS])
    out, _ = card(c)
    assert steps(out).count("narrate") == 2 and steps(out).count("verify") == 2 and "retry" in steps(out)
    assert "[verifier] role_reversed" in narrator_users(c)[1]
    assert out.card.source == "llm" and out.card.verification.verifier == "retried_then_passed"
    assert out.card.text == g.text  # the retry wrote the same template; the Verifier changed nothing


def test_three_verifier_rejections_end_in_the_template_fallback_without_a_convergence_error():
    g = asyncio.run(guard_check(GOOD, MENU, tools.slot_context(MOMENT, EVENTS)))
    c = client(verdict=verdict_reject(g.text.split()[0]))
    out, _ = card(c)  # must not raise WorkflowConvergenceException
    assert c.count("MenuDraftOut") == 3 and c.count("VerifierOut") == 3
    assert out.card.source == "template_fallback" and out.card.verification.label_source == "template_fallback"
    assert steps(out)[-2:] == ["fallback", "finalize"] and steps(out).count("retry") == 2
    fb = next(s for s in out.trace if s.step == "fallback")
    assert fb.output["reason"] == "verifier" and fb.agent == "template"
    assert out.card.text and out.card.claims


def test_three_guard_rejections_also_end_in_the_fallback_and_the_verifier_never_runs():
    c = client(draft=[draft_json(BAD)])
    out, _ = card(c)
    assert out.card.source == "template_fallback" and c.count("MenuDraftOut") == 3 and c.count("VerifierOut") == 0
    assert next(s for s in out.trace if s.step == "fallback").output["reason"] == "guard"


def test_the_three_attempt_rule_is_in_the_edges_not_in_max_iterations():
    g = asyncio.run(guard_check(GOOD, MENU, tools.slot_context(MOMENT, EVENTS)))
    out, _ = card(client(verdict=verdict_reject(g.text.split()[0])))
    supersteps_used = len(out.trace)
    assert supersteps_used < EMERGENCY_MAX_ITERATIONS // 2  # nowhere near the cap
    assert out.state.attempt == 3 and not out.state.can_retry


# --- narrator failures ------------------------------------------------------------------------------------


def test_a_failed_narrator_call_is_retried_with_a_narrator_feedback_entry():
    c = client(draft=[RuntimeError("down"), draft_json(GOOD)])
    out, _ = card(c)
    assert steps(out) == ["analyst", "narrate", "retry", "narrate", "guard", "verify", "finalize"]
    assert out.trace[1].status == "error" and out.state.feedback_history[0].entries[0].source == "narrator"
    assert "[narrator] client_error" in narrator_users(c)[1]


def test_three_narrator_timeouts_end_in_the_fallback():
    c = client(draft=Sleep(5))
    out, _ = card(c, agents=AgentsConfig(narrator_timeout_s=0.05))
    assert out.card.source == "template_fallback" and [s.status for s in out.trace if s.step == "narrate"] == ["timeout"] * 3


def test_a_spent_budget_goes_straight_to_the_fallback():
    out, _ = card(client(), budget=CallBudget(1))  # the Analyst takes the only call
    assert out.card.source == "template_fallback"
    assert next(s for s in out.trace if s.step == "fallback").output["reason"] == "budget_exceeded"


# --- analyst and verifier failures: labelled, never blocking -----------------------------------------------


def test_an_analyst_crash_gives_the_narrator_the_full_menu_and_the_card_goes_on():
    import json
    c = client(analyst=RuntimeError("analyst down"))
    out, _ = card(c)
    assert steps(out)[:3] == ["analyst", "analyst_fallback", "narrate"] and out.card.source == "llm"
    record = json.JSONDecoder().raw_decode(narrator_users(c)[0])[0]
    assert {x["id"] for x in record["claims_menu"]} == set(ALL_IDS)  # the full menu
    assert out.state.briefing is None


def test_an_analyst_that_narrows_changes_only_what_the_narrator_sees():
    import json
    only = [ALL_IDS[0]]
    c = client(analyst=analyst_reply(only, "a goal"))
    out, _ = card(c)
    record = json.JSONDecoder().raw_decode(narrator_users(c)[0])[0]
    assert len(record["claims_menu"]) < len(ALL_IDS) and out.state.briefing is not None
    assert narrator_users(c)[0].endswith("a goal")


def test_a_verifier_timeout_publishes_the_guard_passed_draft_labelled_guard_only():
    c = client(verdict=Sleep(5))
    out, _ = card(c, agents=AgentsConfig(verifier_timeout_s=0.05))
    k = out.card
    assert k.source == "llm"  # the badge keeps its meaning
    assert k.verification.to_dict() == {"guard": True, "verifier": "skipped_error", "attempts": 1, "label_source": "guard_only"}
    ve = next(s for s in out.trace if s.step == "verifier_error")
    assert ve.status == "timeout" and steps(out)[-1] == "finalize"


def test_a_malformed_verifier_answer_is_the_same_labelled_path():
    out, _ = card(client(verdict="not json"))
    assert out.card.verification.verifier == "skipped_error" and out.card.verification.label_source == "guard_only"


def test_the_flags_switch_agents_off():
    c = client()
    out, _ = card(c, flags=Flags(analyst=False, verifier=False))
    assert steps(out) == ["narrate", "guard", "finalize"]
    assert c.count("AnalystOut") == 0 and c.count("VerifierOut") == 0
    assert out.card.verification.verifier == "not_run" and out.card.verification.label_source == "guard_only"
    out, _ = card(client(), flags=Flags(analyst=False, verifier=True))
    assert steps(out) == ["narrate", "guard", "verify", "finalize"] and out.card.verification.verifier == "passed"
    out, _ = card(client(), flags=Flags(analyst=True, verifier=False))
    assert steps(out)[:2] == ["analyst", "narrate"] and "verify" not in steps(out)


# --- guarantees -------------------------------------------------------------------------------------------


def test_a_draft_the_guard_rejects_is_never_published_whatever_the_verifier_says():
    c = client(draft=[draft_json(BAD)], verdict=VERDICT_PASS)
    out, _ = card(c)
    assert out.card.source == "template_fallback"
    assert "3 shots" not in out.card.text and out.card.template is None  # nothing of the bad draft is in the card


def test_the_verifiers_ok_does_not_change_the_guards_verdict():
    out_ok, _ = card(client(verdict=VERDICT_PASS))
    out_off, _ = card(client(), flags=Flags(analyst=True, verifier=False))
    assert out_ok.card.text == out_off.card.text and out_ok.card.claim_ids == out_off.card.claim_ids


def test_numbers_and_events_come_from_code_and_the_claims_are_verified():
    out, _ = card(client())
    k = out.card
    assert all(r.ok for r in k.verification_results) and len(k.claims) == len(k.claim_ids)
    for p in k.parts:
        if p.claim is not None:
            assert 0 <= p.claim < len(k.claims)


def test_an_exception_inside_the_workflow_still_produces_a_card(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("tool crashed")

    monkeypatch.setattr(tools, "check_template", boom)
    out, _ = card(client())
    assert out.card.source == "template_fallback" and out.card.text
    assert "workflow_error" in steps(out)
    err = next(s for s in out.trace if s.step == "workflow_error")
    assert err.status == "error" and err.output["error"] == "RuntimeError"
    assert steps(out)[-2:] == ["fallback", "finalize"] and "narrate" in steps(out)  # the partial trace is kept


def test_a_workflow_that_cannot_start_still_produces_a_card(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("menu tool crashed")

    monkeypatch.setattr(tools, "menu_for", boom)
    out, _ = card(client())
    assert out.card.source == "template_fallback" and out.card.text
    assert steps(out) == ["workflow_error", "fallback", "finalize"]


# --- cards in flight ---------------------------------------------------------------------------------------


class CountingClient:
    """Answers like a good model and records how many calls are in flight at once."""

    def __init__(self, delay=0.03):
        self.delay, self.now, self.peak, self.by_moment = delay, 0, 0, Counter()

    async def complete(self, messages, *, response_model, max_tokens, reasoning_effort=None):
        import json

        from app.explain.llm_narrator import ChatResult
        self.now += 1
        self.peak = max(self.peak, self.now)
        try:
            await asyncio.sleep(self.delay)
        finally:
            self.now -= 1
        name = response_model.__name__
        if name == "VerifierOut":
            return ChatResult(VERDICT_PASS, 1, 1, 0)
        record = json.JSONDecoder().raw_decode(messages[1]["content"])[0]
        if name == "AnalystOut":
            return ChatResult(analyst_reply([c["id"] for c in record["claims_menu"]]), 1, 1, 0)
        self.by_moment[record["moment"]["id"]] += 1
        return ChatResult(draft_json(TEMPLATES[record["moment"]["id"]]), 1, 1, 0)


CASES = [moment_case(c) for c in ("goal", "red_card", "penalty", "pressure_shift")]
TEMPLATES = {m.id: passing_template(m, e) for e, m in CASES}  # computed outside the running loop


def test_cards_run_concurrently_up_to_the_limit_and_keep_their_order():
    results = {}
    for events, m in CASES:
        c = CountingClient()
        w = AgentWorkflow(events, c, agents=AgentsConfig(max_concurrent_cards=2), model_tag="m")
        results[m.id] = asyncio.run(w.run_cards([m, m, m, m]))
        assert c.peak <= 2 and len(results[m.id]) == 4
        assert all(o.card.source == "llm" and o.card.text == results[m.id][0].card.text for o in results[m.id])
    assert len(results) == 4


def test_the_limit_actually_limits():
    events, m = CASES[0]
    wide, narrow = CountingClient(), CountingClient()
    asyncio.run(AgentWorkflow(events, wide, agents=AgentsConfig(max_concurrent_cards=4), model_tag="m").run_cards([m] * 4))
    asyncio.run(AgentWorkflow(events, narrow, agents=AgentsConfig(max_concurrent_cards=1), model_tag="m").run_cards([m] * 4))
    assert narrow.peak == 1 and wide.peak > 1


def test_each_card_has_its_own_state():
    events, m = CASES[0]
    outs = asyncio.run(AgentWorkflow(events, CountingClient(0.01), model_tag="m").run_cards([m, m, m]))
    assert [o.state.attempt for o in outs] == [1, 1, 1]
    assert all(len(o.trace) == 5 for o in outs)  # nothing leaked from a neighbouring card
