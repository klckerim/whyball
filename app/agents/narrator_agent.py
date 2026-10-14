"""Narrator agent: the foundry-v5.2 narrator, wrapped. Prompt and slot language are frozen.

It builds its messages with `llm_narrator.build_messages` (the system prompt is untouched) and parses the answer with
`parse_draft`, like `FoundryNarrator.narrate`, but asynchronously, on a shared call budget, and reporting a trace
step instead of raising. The only addition to the model's input is the Analyst's short note, appended to the USER
message (never the system prompt); without a note the messages are byte for byte the ones `FoundryNarrator` sends
(tests/test_agents_narrator.py). Which claims the model sees is decided by the menu it is given (the Analyst narrows it).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.analytics.moments import Moment
from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.llm_narrator import (
    PROMPT_VERSION,
    ChatClient,
    ChatResult,
    MenuDraftOut,
    UsageRecord,
    build_messages,
    parse_draft,
)
from app.explain.menu import ClaimMenu
from app.explain.narrator import (
    BudgetExceeded,
    Draft,
    Feedback,
    InvalidNarratorOutput,
    NarratorError,
    NarratorTimeout,
)
from app.generator.models import Event

from .limits import DEFAULT_AGENTS_CONFIG, AgentsConfig, CallBudget
from .trace import Stopwatch, Tokens, TraceStep

logger = logging.getLogger("whyball.llm")
FEEDBACK_MARKER = "\n\nFEEDBACK\n"
BRIEFING_HEADER = "\n\nBRIEFING (a note from the analyst; it is not a source of facts: use only claims_menu ids)\n"


def narrator_messages(
    moment: Moment, events: Sequence[Event], persona: str, language: str, feedback: Feedback | None,
    config: ExplainConfig, menu: ClaimMenu, note: str | None = None,
) -> list[dict[str, str]]:
    """`build_messages` plus the analyst's note in the user message, before any feedback block."""
    messages = build_messages(moment, events, persona, language, feedback, config, menu)
    if note:
        user = messages[1]["content"]
        head, sep, tail = user.partition(FEEDBACK_MARKER)
        messages[1] = {"role": "user", "content": head + BRIEFING_HEADER + note + sep + tail}
    return messages


@dataclass(frozen=True)
class NarrateResult:
    draft: Draft | None  # None when the call failed
    error: NarratorError | None
    step: TraceStep
    usage: UsageRecord | None


class NarratorAgent:
    name = "narrator"
    source = "llm"

    def __init__(
        self,
        events: Sequence[Event],
        client: ChatClient,
        *,
        budget: CallBudget,
        config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
        agents: AgentsConfig = DEFAULT_AGENTS_CONFIG,
        model_tag: str = "",
        persona: str | None = None,
        language: str = "en",
    ) -> None:
        self.events = events
        self.client = client
        self.budget = budget
        self.config = config
        self.agents = agents
        self.model_tag = model_tag
        self.persona = persona or config.default_persona
        self.language = language
        self.prompt_version = f"{PROMPT_VERSION}:{model_tag}" if model_tag else PROMPT_VERSION
        self.usage: list[UsageRecord] = []

    def response_model(self) -> type[BaseModel]:
        return MenuDraftOut

    async def write(
        self, moment: Moment, menu: ClaimMenu, *, attempt: int, clock: Stopwatch,
        feedback: Feedback | None = None, note: str | None = None,
    ) -> NarrateResult:
        """One Narrator call. Never raises for a model/client failure: the result carries the error."""
        started = clock.start()
        input_ref = "menu+briefing" if note else "menu"
        feedback_codes = list(feedback.codes) if feedback else []

        def step(status: str, output: dict, result: ChatResult | None = None) -> TraceStep:
            started_ms, duration_ms = clock.span(started)
            tokens = Tokens(result.input_tokens, result.output_tokens, result.reasoning_tokens) if result else None
            return TraceStep.make("narrate", "narrator", attempt=attempt, started_ms=started_ms,
                                  duration_ms=duration_ms, input_ref=input_ref, output=output, tokens=tokens,
                                  model=self.model_tag or None, status=status)

        try:
            call_no = self.budget.take()
        except BudgetExceeded as e:
            return NarrateResult(None, e, step("error", {"error": e.code, "message": str(e), "feedback": feedback_codes}), None)
        messages = narrator_messages(moment, self.events, self.persona, self.language, feedback, self.config, menu, note)
        timeout = self.agents.narrator_timeout_s
        call = self.client.complete(
            messages, response_model=self.response_model(), max_tokens=self.config.llm_max_tokens,
            reasoning_effort=self.config.llm_reasoning_effort,
        )
        try:
            result = await asyncio.wait_for(call, timeout)
        except TimeoutError:
            err: NarratorError = NarratorTimeout(f"LLM did not respond within {timeout:g} s")
            return self._failed(moment, call_no, "timeout", err, step("timeout", {"error": err.code, "feedback": feedback_codes}))
        except Exception as e:  # noqa: BLE001 - any client failure is a Narrator failure, not a crash
            err = NarratorError(f"LLM client error: {e!r}")
            return self._failed(moment, call_no, "client_error", err, step("error", {"error": err.code, "message": str(err)[:200], "feedback": feedback_codes}))
        try:
            draft = parse_draft(result.text, menu)
        except ValidationError as e:
            first = e.errors()[0]
            err = InvalidNarratorOutput(
                f"Response does not match the schema ({e.error_count()} errors): {first['type']} at "
                f"{'.'.join(map(str, first['loc'])) or '<root>'}"
            )
            return self._failed(moment, call_no, "invalid_output", err,
                                step("error", {"error": err.code, "message": str(err), "feedback": feedback_codes}, result), result)
        usage = self._record(moment, call_no, "ok", result=result, clock=clock, started=started)
        return NarrateResult(draft, None, step("ok", {"template": draft.template, "feedback": feedback_codes}, result), usage)

    # --- bookkeeping ---------------------------------------------------------------------------------

    def _record(self, moment: Moment, call_no: int, outcome: str, *, result: ChatResult | None,
                clock: Stopwatch, started: float, error: str | None = None) -> UsageRecord:
        _, duration_ms = clock.span(started)
        rec = UsageRecord(
            call=call_no, moment_id=moment.id, outcome=outcome,
            input_tokens=result.input_tokens if result else None,
            output_tokens=result.output_tokens if result else None,
            reasoning_tokens=result.reasoning_tokens if result else None,
            latency_ms=duration_ms, error=error,
        )
        self.usage.append(rec)
        logger.info("agent_call agent=narrator call=%d moment=%s outcome=%s input_tokens=%s output_tokens=%s "
                    "reasoning_tokens=%s latency_ms=%d", rec.call, rec.moment_id, rec.outcome, rec.input_tokens,
                    rec.output_tokens, rec.reasoning_tokens, rec.latency_ms)
        return rec

    def _failed(self, moment: Moment, call_no: int, outcome: str, err: NarratorError, step: TraceStep,
                result: ChatResult | None = None) -> NarrateResult:
        rec = UsageRecord(call_no, moment.id, outcome,
                          result.input_tokens if result else None, result.output_tokens if result else None,
                          result.reasoning_tokens if result else None, step.duration_ms, str(err)[:200])
        self.usage.append(rec)
        return NarrateResult(None, err, step, rec)
