"""The agent workflow of one card, on Microsoft Agent Framework (graph API, agent-framework-core 1.19.0).

    start -> [analyst] -> narrate -> guard -> verify -> finalize
                            ^          |         |
                            +----------+---------+   rejection with attempts left (feedback loop)
                narrate / guard / verify --> fallback   when the attempts are used up (3) or the Narrator cannot go on

Every executor reads and writes ONE immutable `NarrationState` (state.py) by read-modify-write. The "at most 3 attempts"
rule lives in the conditional edges (the executors' `Signal.next`); `max_iterations` is only an emergency cap. A
workflow instance cannot run twice at once, so each card gets its own (building one takes about a millisecond), and the
cards in flight are bounded by a semaphore. The trace is written by our executors, not by the framework's events.

Guarantees (tests/test_agents_workflow.py): numbers and events are rendered by code; a draft the Guard rejects is never
published; an Analyst or Verifier failure labels the card instead of blocking it; the Verifier's answer never changes the
Guard's; an exception anywhere in the workflow still produces a card (the labelled template fallback, trace `workflow_error`).
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler
from typing_extensions import Never

from app.analytics.moments import Moment
from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.llm_narrator import ChatClient
from app.explain.menu import ClaimMenu
from app.explain.narrator import NarratorError
from app.explain.slots import SlotContext
from app.generator.models import Event

from . import tools
from .analyst import AnalystAgent, effective_menu
from .guard import guard_check
from .limits import DEFAULT_AGENTS_CONFIG, AgentsConfig, CallBudget
from .narrator_agent import NarratorAgent
from .state import (
    DraftRecord, FeedbackEntry, FeedbackRecord, FinalCard, Flags, NarrationState, Verification, VerifierStatus, load, save, update,
)
from .trace import Stopwatch, TraceStep
from .verifier import VerifierAgent

TROUBLE_RE = re.compile(r"\b429\b|rate.?limit|too many requests|quota", re.IGNORECASE)
EMERGENCY_MAX_ITERATIONS = 60  # supersteps; a card needs about 14 at most: this cap is never the rule that stops a card


@dataclass(frozen=True)
class Signal:
    """The only message between executors: where the card goes next (an edge condition reads `next`)."""

    next: str  # analyst | narrate | guard | verify | finalize | fallback
    reason: str = ""


@dataclass(frozen=True)
class CardOutcome:
    state: NarrationState

    @property
    def card(self) -> FinalCard:
        assert self.state.final_card is not None
        return self.state.final_card

    @property
    def trace(self) -> tuple[TraceStep, ...]:
        return self.state.trace


def trouble(outcome: CardOutcome) -> str | None:
    """Why a run should stop at once: a model call timed out, or the service said 429 / rate limit / quota."""
    for s in outcome.trace:
        if s.status == "timeout":
            return f"{s.agent} call timed out ({s.step}, attempt {s.attempt})"
        text = json.dumps(s.output)
        if s.status == "error" and TROUBLE_RE.search(text):
            return f"{s.agent} call hit a rate limit or quota ({s.step}): {s.output.get('message', '')[:120]}"
    return None


class _Run:
    """What one card's executors share besides the state: the agents, the context and the stopwatch (not state)."""

    def __init__(self, moment: Moment, events: Sequence[Event], wf: AgentWorkflow, flags: Flags) -> None:
        self.moment, self.events, self.wf, self.flags = moment, events, wf, flags
        self.slot_ctx: SlotContext = tools.slot_context(moment, events, wf.language)
        self.clock = Stopwatch()
        self.last_state: NarrationState | None = None  # for the workflow_error path

    def remember(self, state: NarrationState) -> NarrationState:
        self.last_state = state
        return state


def _steps(state: NarrationState, steps: Sequence[TraceStep]) -> NarrationState:
    for s in steps:
        state = state.with_step(s)
    return state


def _agent_step(run: _Run, kind: str, agent: str, *, attempt: int, started: float, input_ref: str, output: dict,
                status: str = "ok") -> TraceStep:
    started_ms, duration_ms = run.clock.span(started)
    return TraceStep.make(kind, agent, attempt=attempt, started_ms=started_ms, duration_ms=duration_ms,
                          input_ref=input_ref, output=output, status=status)


def _after_rejection(run: _Run, state: NarrationState, reason: str, codes: Sequence[str]) -> tuple[NarrationState, Signal]:
    """Retry while attempts are left (the edge goes back to the Narrator), else the labelled template fallback."""
    if state.can_retry:
        started = run.clock.start()
        step = _agent_step(run, "retry", "workflow", attempt=state.attempt, started=started, input_ref="feedback_history",
                           output={"reason": reason, "codes": list(codes), "next_attempt": state.attempt + 1})
        return state.with_step(step), Signal("narrate", reason)
    return state, Signal("fallback", reason)


class StartExec(Executor):
    def __init__(self, run: _Run) -> None:
        super().__init__(id="start")
        self.run = run

    @handler
    async def start(self, moment_id: str, ctx: WorkflowContext[Signal]) -> None:
        menu = await tools.menu_for(self.run.moment, self.run.events, self.run.wf.config)
        save(ctx, self.run.remember(NarrationState(self.run.moment, menu, self.run.flags)))
        await ctx.send_message(Signal("analyst" if self.run.flags.analyst else "narrate"))


class AnalystExec(Executor):
    def __init__(self, run: _Run) -> None:
        super().__init__(id="analyst")
        self.run = run

    @handler
    async def brief(self, signal: Signal, ctx: WorkflowContext[Signal]) -> None:
        state = load(ctx)
        assert self.run.wf.analyst is not None
        result = await self.run.wf.analyst.brief(state.moment, state.menu, clock=self.run.clock)

        def change(s: NarrationState) -> NarrationState:
            s = _steps(s, result.steps)
            return s.with_briefing(result.briefing) if result.briefing else s

        self.run.remember(update(ctx, change))
        await ctx.send_message(Signal("narrate"))


class NarratorExec(Executor):
    def __init__(self, run: _Run) -> None:
        super().__init__(id="narrate")
        self.run = run

    @handler
    async def narrate(self, signal: Signal, ctx: WorkflowContext[Signal]) -> None:
        state = update(ctx, lambda s: s.next_attempt())
        menu = effective_menu(state.menu, state.briefing)
        feedback = state.last_feedback.to_feedback() if state.last_feedback else None
        note = state.briefing.context_note if state.briefing and state.briefing.context_note else None
        res = await self.run.wf.narrator.write(
            state.moment, menu, attempt=state.attempt, clock=self.run.clock, feedback=feedback, note=note)
        if res.draft is None:
            err: NarratorError = res.error  # type: ignore[assignment]
            record = FeedbackRecord(state.attempt, (FeedbackEntry("narrator", err.code, str(err)[:200]),))
            state = update(ctx, lambda s: s.with_step(res.step).with_feedback(record))
            self.run.remember(state)
            # a retryable failure goes through the Guard executor's rejection path (retry or fallback); one that cannot
            # be retried (a spent budget) goes straight to the fallback
            await ctx.send_message(Signal("guard", "narrator_error") if err.retryable else Signal("fallback", err.code))
            return
        self.run.remember(update(ctx, lambda s: s.with_step(res.step).with_draft(DraftRecord(s.attempt, res.draft.template or ""))))
        await ctx.send_message(Signal("guard"))


class GuardExec(Executor):
    def __init__(self, run: _Run) -> None:
        super().__init__(id="guard")
        self.run = run

    @handler
    async def check(self, signal: Signal, ctx: WorkflowContext[Signal]) -> None:
        state = load(ctx)
        if signal.reason == "narrator_error":  # no draft to check: the Narrator's failure is the rejection
            codes = state.last_feedback.codes if state.last_feedback else ()
            state, out = _after_rejection(self.run, state, "narrator_error", codes)
            save(ctx, self.run.remember(state))
            await ctx.send_message(out)
            return
        draft = state.drafts[-1]
        started = self.run.clock.start()
        g = await guard_check(draft.template, effective_menu(state.menu, state.briefing), self.run.slot_ctx,
                              self.run.wf.config)
        step = _agent_step(self.run, "guard", "guard", attempt=state.attempt, started=started,
                           input_ref=f"drafts[{state.attempt}]", output={"ok": g.ok, "codes": list(g.codes)})
        if g.ok:
            assert g.text is not None
            self.run.remember(update(ctx, lambda s: s.with_step(step).with_guard(g).with_rendered(g.text)))
            await ctx.send_message(Signal("verify"))
            return
        state = update(ctx, lambda s: s.with_step(step).with_guard(g).with_feedback(g.feedback_record(s.attempt)))
        state, out = _after_rejection(self.run, state, "guard", g.codes)
        save(ctx, self.run.remember(state))
        await ctx.send_message(out)


class VerifierExec(Executor):
    def __init__(self, run: _Run) -> None:
        super().__init__(id="verify")
        self.run = run

    @handler
    async def verify(self, signal: Signal, ctx: WorkflowContext[Signal]) -> None:
        state = load(ctx)
        if not self.run.flags.verifier or self.run.wf.verifier is None:
            await ctx.send_message(Signal("finalize", "verifier_off"))
            return
        assert state.guard is not None and state.guard.ok
        res = await self.run.wf.verifier.verify(state.moment, state.guard, self.run.slot_ctx, attempt=state.attempt,
                                                clock=self.run.clock)
        if res.verdict == "reject":
            assert res.feedback is not None
            state = update(ctx, lambda s: _steps(s, res.steps).with_feedback(res.feedback))
            state, out = _after_rejection(self.run, state, "verifier", res.feedback.codes)
            save(ctx, self.run.remember(state))
            await ctx.send_message(out)
            return
        self.run.remember(update(ctx, lambda s: _steps(s, res.steps)))
        # pass: finalize; error (D6): the Guard-passed draft goes out, labelled guard-only
        await ctx.send_message(Signal("finalize", "verifier_error" if res.verdict == "error" else "verified"))


def _verifier_status(state: NarrationState) -> VerifierStatus:
    if not state.flags.verifier:
        return "not_run"
    here = [s for s in state.trace if s.attempt == state.attempt and s.agent == "verifier"]
    if any(s.step == "verifier_error" for s in here):
        return "skipped_error"
    if any(s.step == "verify" and s.output.get("verdict") == "pass" for s in here):
        return "passed" if state.attempt == 1 else "retried_then_passed"
    return "not_run"


class FinalizeExec(Executor):
    def __init__(self, run: _Run) -> None:
        super().__init__(id="finalize")
        self.run = run

    @handler
    async def finish(self, signal: Signal, ctx: WorkflowContext[Never, CardOutcome]) -> None:
        state = load(ctx)
        g = state.guard
        assert g is not None and g.ok and g.text is not None, "finalize only follows an accepted draft"
        started = self.run.clock.start()
        status = _verifier_status(state)
        label = "llm" if status in ("passed", "retried_then_passed") else "guard_only"
        card = FinalCard(g.text, g.parts, g.claims, g.claim_ids, g.verification, "llm", g.template,
                         Verification(True, status, state.attempt, label))
        step = _agent_step(self.run, "finalize", "workflow", attempt=state.attempt, started=started, input_ref="guard",
                           output={"source": "llm", "verifier": status, "label_source": label})
        final = update(ctx, lambda s: s.with_step(step).finish(card))
        await ctx.yield_output(CardOutcome(self.run.remember(final)))


async def fallback_card(state: NarrationState, run: _Run, reason: str) -> NarrationState:
    """The labelled template fallback, as a finished state (shared by the Fallback executor and the error path)."""
    started = run.clock.start()
    fb = await tools.template_fallback(state.moment, run.events, run.wf.config, run.wf.language)
    ids = tools.template_claim_ids(fb.claims)
    card = FinalCard(fb.text, fb.parts, fb.claims, ids, fb.verification, "template_fallback", None,
                     Verification(True, "not_run", state.attempt, "template_fallback"))
    step = _agent_step(run, "fallback", "template", attempt=state.attempt, started=started, input_ref="moment",
                       output={"reason": reason, "published_sentences": fb.published_sentences,
                               "total_sentences": fb.total_sentences})
    done = _agent_step(run, "finalize", "workflow", attempt=state.attempt, started=run.clock.start(), input_ref="fallback",
                       output={"source": "template_fallback", "verifier": "not_run", "label_source": "template_fallback"})
    return state.with_step(step).with_step(done).finish(card)


class FallbackExec(Executor):
    def __init__(self, run: _Run) -> None:
        super().__init__(id="fallback")
        self.run = run

    @handler
    async def fall_back(self, signal: Signal, ctx: WorkflowContext[Never, CardOutcome]) -> None:
        final = await fallback_card(load(ctx), self.run, signal.reason or "max_attempts")
        save(ctx, self.run.remember(final))
        await ctx.yield_output(CardOutcome(final))


class AgentWorkflow:
    """Runs the cards of one match through the agent graph. One instance per run (it owns the call budget)."""

    def __init__(
        self,
        events: Sequence[Event],
        client: ChatClient,
        *,
        flags: Flags = Flags(),
        config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
        agents: AgentsConfig = DEFAULT_AGENTS_CONFIG,
        model_tag: str = "",
        persona: str | None = None,
        language: str = "en",
        budget: CallBudget | None = None,
    ) -> None:
        self.events, self.flags, self.config, self.agents, self.language = events, flags, config, agents, language
        self.budget = budget or CallBudget(agents.max_calls_per_run)
        kw: dict[str, Any] = {"budget": self.budget, "config": config, "agents": agents, "model_tag": model_tag}
        self.narrator = NarratorAgent(events, client, persona=persona, language=language, **kw)
        self.analyst = AnalystAgent(events, client, language=language, **kw) if flags.analyst else None
        self.verifier = VerifierAgent(events, client, **kw) if flags.verifier else None
        self.trouble: str | None = None  # set by the first timeout / 429; cards not yet started are then skipped

    def build(self, run: _Run):
        start, analyst, narrate = StartExec(run), AnalystExec(run), NarratorExec(run)
        guard, verify, finalize, fallback = GuardExec(run), VerifierExec(run), FinalizeExec(run), FallbackExec(run)
        is_ = lambda name: (lambda s: s.next == name)  # noqa: E731 - edge conditions read Signal.next
        builder = WorkflowBuilder(start_executor=start, max_iterations=EMERGENCY_MAX_ITERATIONS, name="whyball-card")
        builder.add_edge(start, narrate, is_("narrate"))
        builder.add_edge(narrate, guard, is_("guard"))
        builder.add_edge(narrate, fallback, is_("fallback"))
        builder.add_edge(guard, verify, is_("verify"))
        builder.add_edge(guard, narrate, is_("narrate"))
        builder.add_edge(guard, fallback, is_("fallback"))
        builder.add_edge(verify, finalize, is_("finalize"))
        builder.add_edge(verify, narrate, is_("narrate"))
        builder.add_edge(verify, fallback, is_("fallback"))
        if run.flags.analyst:
            builder.add_edge(start, analyst, is_("analyst"))
            builder.add_edge(analyst, narrate, is_("narrate"))
        return builder.build()

    async def run_card(self, moment: Moment) -> CardOutcome:
        """One card. Never raises: a failure inside the workflow produces the labelled template fallback."""
        run = _Run(moment, self.events, self, self.flags)
        try:
            result = await self.build(run).run(moment.id)
            outputs = result.get_outputs()
            if not outputs or not isinstance(outputs[0], CardOutcome):
                raise RuntimeError("the workflow ended without a card")
            return outputs[0]
        except Exception as e:  # noqa: BLE001 - the card must still be produced (D6 / guarantee 3)
            state = run.last_state
            if state is None:
                try:
                    menu = await tools.menu_for(moment, self.events, self.config)
                except Exception:  # noqa: BLE001 - even the menu tool failed: the template fallback needs no menu
                    menu = ClaimMenu(moment.id, (), (), ())
                state = NarrationState(moment, menu, self.flags)
            started = run.clock.start()
            state = state.with_step(_agent_step(
                run, "workflow_error", "workflow", attempt=state.attempt, started=started, input_ref="state",
                output={"error": type(e).__name__, "message": str(e)[:200]}, status="error"))
            return CardOutcome(await fallback_card(state, run, "workflow_error"))

    async def run_cards(self, moments: Sequence[Moment], *, stop_on_trouble: bool = False) -> list[CardOutcome | None]:
        """Cards in the given order, at most `max_concurrent_cards` in flight. With `stop_on_trouble`, the first model
        timeout or 429 stops the run: cards that have not started return None (the ones in flight finish)."""
        sem = asyncio.Semaphore(self.agents.max_concurrent_cards)

        async def one(m: Moment) -> CardOutcome | None:
            async with sem:
                if stop_on_trouble and self.trouble:
                    return None
                out = await self.run_card(m)
                if stop_on_trouble and self.trouble is None:
                    self.trouble = trouble(out)
                return out

        return list(await asyncio.gather(*(one(m) for m in moments)))
