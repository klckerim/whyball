"""Narrator protocol, the template narrator and a FakeNarrator for tests.

Narrators are built with the match context (event stream); a protocol call only takes
the moment, persona, language and the previous attempt's feedback. The LLM
narrator implements the same protocol.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from app.analytics.moments import Moment
from app.generator.models import Event

from .claims import Claim, parse_ref
from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from .template_narrator import Narration
from .template_narrator import narrate as template_narrate

if TYPE_CHECKING:
    from .menu import ClaimMenu


@dataclass(frozen=True)
class Draft:
    text: str
    claims: tuple[Claim, ...]
    # Slot-based draft: `template` is placeholder text, `claim_ids` one id per claim.
    # The pipeline renders the final text after verification (see slots.py).
    template: str | None = None
    claim_ids: tuple[str, ...] = ()
    # Claim menu draft (foundry-v5): claims come from the menu, `claims` is empty; see menu.py.
    menu: ClaimMenu | None = None


class NarratorError(Exception):
    """The narrator could not produce a draft. With `retryable=False` the pipeline falls back at once."""

    code = "client_error"
    retryable = True


class NarratorTimeout(NarratorError):
    code = "timeout"


class InvalidNarratorOutput(NarratorError):
    code = "invalid_output"


class BudgetExceeded(NarratorError):
    code = "budget_exceeded"
    retryable = False


@dataclass(frozen=True)
class FeedbackItem:
    source: str  # "lint" | "verify" | "draft" | "narrator"
    code: str
    fragment: str | None = None
    claim_index: int | None = None


@dataclass(frozen=True)
class Feedback:
    attempt: int
    items: tuple[FeedbackItem, ...]

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(i.code for i in self.items)


@runtime_checkable
class Narrator(Protocol):
    name: str
    source: str  # "source" in the record: "llm" | "template"
    prompt_version: str

    def narrate(
        self, moment: Moment, persona: str, language: str, feedback: Feedback | None = None
    ) -> Draft: ...


class TemplateNarrator:
    """Binds the existing templates to the Narrator protocol. Ignores persona and feedback."""

    source = "template"
    name = "template"

    def __init__(self, events: Sequence[Event], config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG) -> None:
        self.events = events
        self.config = config
        self.prompt_version = config.template_prompt_version

    def narration(self, moment: Moment) -> Narration:
        return template_narrate(moment, self.events, self.config)

    def narrate(
        self, moment: Moment, persona: str, language: str, feedback: Feedback | None = None
    ) -> Draft:
        n = self.narration(moment)
        return Draft(
            " ".join(s.text[language] for s in n.sentences),
            tuple(c for s in n.sentences for c in s.claims),
        )


FAKE_MODES = (
    "correct",
    "wrong_number",
    "foreign_event",
    "hallucinated_name",
    "unsupported_sentence",
    "fixes_after_feedback",
)
HALLUCINATED = {"en": "Arlo Quintana was everywhere."}
UNSUPPORTED = {
    "en": "{team} have now won {n} corners.",
}


def _fmt(v: float) -> str:
    return f"{v:g}"


class FakeNarrator:
    """Mimics typical LLM mistakes deterministically (tests/demo only)."""

    source = "llm"

    def __init__(
        self, events: Sequence[Event], mode: str, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
    ) -> None:
        if mode not in FAKE_MODES:
            raise ValueError(f"Unknown fake mode: {mode!r} (options: {', '.join(FAKE_MODES)})")
        self.mode = mode
        self.name = f"fake:{mode}"
        self.prompt_version = f"fake-{mode}-v1"
        self.calls = 0
        self._template = TemplateNarrator(events, config)
        teams = events[0].data["teams"]
        self._names = {side: teams[side]["name"] for side in ("home", "away")}

    def narrate(
        self, moment: Moment, persona: str, language: str, feedback: Feedback | None = None
    ) -> Draft:
        self.calls += 1
        draft = self._template.narrate(moment, persona, language)
        mode = self.mode
        if mode == "fixes_after_feedback":
            mode = "correct" if feedback is not None else "wrong_number"

        if mode == "wrong_number":
            first = draft.claims[0]
            bumped = first.value + 1
            pattern = rf"(?<![\d.]){re.escape(_fmt(first.value))}(?![\d.])"
            text = re.sub(pattern, _fmt(bumped), draft.text, count=1)
            return Draft(text, (replace(first, value=bumped), *draft.claims[1:]))
        if mode == "foreign_event":
            i = next(i for i, c in enumerate(draft.claims) if c.event_ids)
            refs = tuple(f"m-foreign#{parse_ref(r)[1]}" for r in draft.claims[i].event_ids)
            claims = list(draft.claims)
            claims[i] = replace(claims[i], event_ids=refs)
            return Draft(draft.text, tuple(claims))
        if mode == "hallucinated_name":
            return Draft(f"{draft.text} {HALLUCINATED[language]}", draft.claims)
        if mode == "unsupported_sentence":
            used = {abs(c.value) for c in draft.claims}
            used |= {c.start.minute for c in draft.claims} | {c.end.minute for c in draft.claims}
            n = 7
            while n in used:
                n += 1
            extra = UNSUPPORTED[language].format(team=self._names[moment.team], n=n)
            return Draft(f"{draft.text} {extra}", draft.claims)
        return draft


def make_narrator(
    spec: str, events: Sequence[Event], config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> Narrator:
    """"template", "fake:<mode>" or "foundry" (FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL)."""
    if spec == "template":
        return TemplateNarrator(events, config)
    if spec == "foundry":
        from .llm_narrator import foundry_narrator_from_env

        return foundry_narrator_from_env(events, config)
    kind, _, mode = spec.partition(":")
    if kind == "fake" and mode:
        return FakeNarrator(events, mode, config)
    raise ValueError(f"Unknown narrator: {spec!r} (template | fake:<mode> | foundry)")
