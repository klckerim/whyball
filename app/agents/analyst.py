"""Analyst agent (analyst-v1): decides which verified claims matter for a moment and why, in one short note.

It reads the moment record the Narrator would read (moment, claims_menu, clauses, events) and returns a closed JSON:
`{claim_ids: [...], context_note: "..."}`. The briefing only changes the Narrator's INPUT: the menu it sees is narrowed
to the chosen claims (plus whatever a clause or a primary claim needs) and the note is appended to the user message.
It cannot add a claim, a number or a fact: ids must be on the menu, the note may carry no digit, number word or
placeholder, and the code Guard checks against the same narrowed menu. Any failure (budget, client error, timeout,
schema or validation violation) falls back to the FULL menu with a trace step `analyst_fallback`: the card is never
blocked by the Analyst. `analyst=off` skips it (the P4 comparison arms).
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from pydantic import BaseModel, ConfigDict, ValidationError

from app.analytics.moments import Moment
from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.llm_narrator import ChatClient, ChatResult, moment_record
from app.explain.menu import ClaimMenu
from app.explain.narrator import BudgetExceeded
from app.generator.models import Event

from .limits import DEFAULT_AGENTS_CONFIG, AgentsConfig, CallBudget
from .state import Briefing
from .trace import Stopwatch, Tokens, TraceStep

ANALYST_VERSION = "analyst-v1"
NOTE_MAX_CHARS = 240
DIGIT = re.compile(r"\d")
NUMBER_WORDS = re.compile(
    r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
    r"seventeen|eighteen|nineteen|twenty|hundred|dozen|once|twice|first|second|third)\b", re.IGNORECASE)

ANALYST_PROMPT = """You are the analyst of a football narration team (synthetic data). Another writer will turn ONE \
moment into one or two sentences. Code has already built and verified every fact in claims_menu; you decide which \
of them matter for THIS moment and why the moment matters.

Use ONLY the moment record in the user message. Do not invent facts, numbers, names or minutes.

Return JSON: {{"claim_ids": [...], "context_note": "..."}}.
- claim_ids: ids from claims_menu[].id, most important first. Choose what a viewer needs to understand why this \
moment matters; skip claims that only add noise. Always include the claims marked "primary": true.
- context_note: at most {note_max} characters of plain words that say why the moment matters (the turn of the match, \
what changed, what is unusual). No digits, no number words, no team or player names, no minutes, no scores, no hype.

Respond only with the JSON object."""


class AnalystOut(BaseModel):
    """The Analyst's whole answer: ids and a note; there is no field for claims, numbers or text to publish."""

    model_config = ConfigDict(extra="forbid")
    claim_ids: list[str]
    context_note: str


class BriefingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_briefing(out: AnalystOut, menu: ClaimMenu) -> Briefing:
    """The Analyst's answer as a Briefing, or a BriefingError. Adds what the Narrator needs to stay usable: every claim
    of a clause the selection touches (so the clause stays on the menu) and the moment's primary claims."""
    ids = out.claim_ids
    if not ids:
        raise BriefingError("empty_selection", "no claim chosen")
    if len(set(ids)) != len(ids):
        raise BriefingError("duplicate_claim_id", "a claim id is repeated")
    known = menu.by_id
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise BriefingError("unknown_claim_id", f"not on the menu: {unknown[0]}")
    note = out.context_note.strip()
    if len(note) > NOTE_MAX_CHARS:
        raise BriefingError("note_too_long", f"{len(note)} characters")
    if DIGIT.search(note) or NUMBER_WORDS.search(note):
        raise BriefingError("note_has_number", "the note contains a number")
    if "{" in note or "}" in note:
        raise BriefingError("note_has_placeholder", "the note contains a placeholder")
    return Briefing(effective_claim_ids(menu, ids), note)


def effective_claim_ids(menu: ClaimMenu, selected: Sequence[str]) -> tuple[str, ...]:
    """Selected claims, the other claims of every clause that uses one of them, and the primary claims; menu order."""
    keep = set(selected)
    for clause in menu.clauses:
        if keep & set(clause.claim_ids):
            keep |= set(clause.claim_ids)
    for group in menu.primary:
        keep |= group
    return tuple(c.id for c in menu.claims if c.id in keep)


def narrow_menu(menu: ClaimMenu, claim_ids: Sequence[str]) -> ClaimMenu:
    """The menu the Narrator sees and the Guard checks against: only `claim_ids`, and the clauses that need no other."""
    keep = set(claim_ids)
    return replace(
        menu,
        claims=tuple(c for c in menu.claims if c.id in keep),
        clauses=tuple(c for c in menu.clauses if set(c.claim_ids) <= keep),
        primary=tuple(g & keep for g in menu.primary if g & keep),
    )


def effective_menu(menu: ClaimMenu, briefing: Briefing | None) -> ClaimMenu:
    return menu if briefing is None else narrow_menu(menu, briefing.claim_ids)


@dataclass(frozen=True)
class AnalystResult:
    briefing: Briefing | None  # None: no briefing, the Narrator gets the full menu
    steps: tuple[TraceStep, ...]  # [analyst] or [analyst (error|timeout), analyst_fallback]


class AnalystAgent:
    name = "analyst"

    def __init__(
        self,
        events: Sequence[Event],
        client: ChatClient,
        *,
        budget: CallBudget,
        config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
        agents: AgentsConfig = DEFAULT_AGENTS_CONFIG,
        model_tag: str = "",
        language: str = "en",
    ) -> None:
        self.events, self.client, self.budget = events, client, budget
        self.config, self.agents, self.model_tag, self.language = config, agents, model_tag, language

    def messages(self, moment: Moment, menu: ClaimMenu) -> list[dict[str, str]]:
        record = moment_record(moment, self.events, self.language, menu)
        return [
            {"role": "system", "content": ANALYST_PROMPT.format(note_max=NOTE_MAX_CHARS)},
            {"role": "user", "content": json.dumps(record, ensure_ascii=False, sort_keys=True)},
        ]

    async def brief(self, moment: Moment, menu: ClaimMenu, *, clock: Stopwatch) -> AnalystResult:
        """One Analyst call. Never raises for a model/client/validation failure: falls back to the full menu."""
        started = clock.start()

        def step(kind: str, status: str, output: dict, result: ChatResult | None = None) -> TraceStep:
            started_ms, duration_ms = clock.span(started)
            tokens = Tokens(result.input_tokens, result.output_tokens, result.reasoning_tokens) if result else None
            return TraceStep.make(kind, "analyst", attempt=0, started_ms=started_ms, duration_ms=duration_ms,
                                  input_ref="menu", output=output, tokens=tokens, model=self.model_tag or None,
                                  status=status)

        def fall_back(status: str, reason: str, message: str, result: ChatResult | None = None) -> AnalystResult:
            first = step("analyst", status, {"error": reason, "message": message[:200]}, result)
            second = step("analyst_fallback", "ok", {"reason": reason, "menu": "full"})
            return AnalystResult(None, (first, second))

        try:
            self.budget.take()
        except BudgetExceeded as e:
            return fall_back("error", e.code, str(e))
        timeout = self.agents.analyst_timeout_s
        call = self.client.complete(
            self.messages(moment, menu), response_model=AnalystOut, max_tokens=self.agents.analyst_max_tokens,
            reasoning_effort=self.config.llm_reasoning_effort,
        )
        try:
            result = await asyncio.wait_for(call, timeout)
        except TimeoutError:
            return fall_back("timeout", "timeout", f"no answer within {timeout:g} s")
        except Exception as e:  # noqa: BLE001 - a client failure never blocks the card
            return fall_back("error", "client_error", repr(e))
        try:
            out = AnalystOut.model_validate_json(result.text)
        except ValidationError as e:
            return fall_back("error", "invalid_output", f"{e.error_count()} schema errors: {e.errors()[0]['type']}", result)
        try:
            briefing = validate_briefing(out, menu)
        except BriefingError as e:
            return fall_back("error", e.code, str(e), result)
        done = step("analyst", "ok", {"selected": list(out.claim_ids), "effective": list(briefing.claim_ids),
                                       "note": briefing.context_note}, result)
        return AnalystResult(briefing, (done,))
