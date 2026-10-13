"""Narrator protokolü, template anlatıcı ve testler için FakeNarrator.

Anlatıcılar maç bağlamıyla (olay akışı) kurulur; protokol çağrısı yalnızca
moment, persona, dil ve önceki denemenin geri bildirimini alır. İleride LLM
anlatıcı da aynı protokolü uygulayacak.
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
    # Slot tabanlı taslak: `template` yer tutuculu metin, `claim_ids` iddia başına id.
    # Nihai metni pipeline doğrulamadan sonra render eder (bkz. slots.py).
    template: str | None = None
    claim_ids: tuple[str, ...] = ()
    # Claim menüsü taslağı (foundry-v5): iddialar menüden, `claims` boş; bkz. menu.py.
    menu: ClaimMenu | None = None


class NarratorError(Exception):
    """Anlatıcı taslak üretemedi. `retryable=False` ise hat hemen yedeğe geçer."""

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
    source: str  # kayıttaki "source": "llm" | "template"
    prompt_version: str

    def narrate(
        self, moment: Moment, persona: str, language: str, feedback: Feedback | None = None
    ) -> Draft: ...


class TemplateNarrator:
    """Mevcut şablonları Narrator protokolüne bağlar. Persona ve feedback'i yok sayar."""

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
    """LLM'in tipik hatalarını deterministik olarak taklit eder (yalnızca test/demo)."""

    source = "llm"

    def __init__(
        self, events: Sequence[Event], mode: str, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
    ) -> None:
        if mode not in FAKE_MODES:
            raise ValueError(f"Bilinmeyen fake mod: {mode!r} (seçenekler: {', '.join(FAKE_MODES)})")
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
    """"template", "fake:<mod>" ya da "foundry" (FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL)."""
    if spec == "template":
        return TemplateNarrator(events, config)
    if spec == "foundry":
        from .llm_narrator import foundry_narrator_from_env

        return foundry_narrator_from_env(events, config)
    kind, _, mode = spec.partition(":")
    if kind == "fake" and mode:
        return FakeNarrator(events, mode, config)
    raise ValueError(f"Bilinmeyen anlatıcı: {spec!r} (template | fake:<mod> | foundry)")
