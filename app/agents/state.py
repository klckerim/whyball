"""Shared state of one narration, immutable.

The workflow keeps this object in its state under `STATE_KEY`. The framework deep-copies whatever is stored
(`set_state`) and what is read (`get_state`), so changing a value in place is silently lost (verified in the P2
spike, repeated by tests/test_agents_state.py). Hence: every type here is a frozen dataclass of scalars, tuples
and other frozen dataclasses, and an update is read-modify-write through `update`:

    update(ctx, lambda s: s.with_draft(draft))

`with_*` methods return a new state. tests/test_agents_state.py scans `app/agents` for the in-place patterns.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Protocol

from app.analytics.moments import Moment
from app.explain.claims import Claim, VerificationResult
from app.explain.menu import ClaimMenu
from app.explain.narrator import Feedback, FeedbackItem
from app.explain.template_narrator import Part

from .trace import TraceStep

STATE_KEY = "narration"
MAX_ATTEMPTS = 3  # Narrator + Guard + Verifier rounds per card; enforced by the workflow's edge conditions

Source = Literal["llm", "template", "template_fallback"]
VerifierStatus = Literal["passed", "retried_then_passed", "skipped_error", "not_run"]
LabelSource = Literal["llm", "template", "template_fallback", "guard_only"]


@dataclass(frozen=True)
class Flags:
    analyst: bool = True
    verifier: bool = True


@dataclass(frozen=True)
class Briefing:
    """What the Analyst hands to the Narrator: a subset of the menu and a short note (never published)."""

    claim_ids: tuple[str, ...]
    context_note: str


@dataclass(frozen=True)
class DraftRecord:
    attempt: int
    template: str  # the Narrator's placeholder text
    text: str | None = None  # rendered, only once the Guard accepted it


@dataclass(frozen=True)
class FeedbackEntry:
    """One reason an attempt was rejected, in the pipeline's own terms (`FeedbackItem`): source is lint | verify |
    draft (the Guard), verifier (the Verifier) or narrator (a failed call)."""

    source: str
    code: str
    fragment: str | None = None
    claim_index: int | None = None

    @classmethod
    def from_item(cls, item: FeedbackItem) -> FeedbackEntry:
        return cls(item.source, item.code, item.fragment, item.claim_index)

    def to_item(self) -> FeedbackItem:
        return FeedbackItem(self.source, self.code, fragment=self.fragment, claim_index=self.claim_index)


@dataclass(frozen=True)
class FeedbackRecord:
    """Why attempt `attempt` was rejected; the next Narrator call receives it as Feedback."""

    attempt: int
    entries: tuple[FeedbackEntry, ...]

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(e.code for e in self.entries)

    def to_feedback(self) -> Feedback:
        """The Narrator's input for the next attempt: the type the pipeline sends."""
        return Feedback(self.attempt, tuple(e.to_item() for e in self.entries))


@dataclass(frozen=True)
class GuardResult:
    """What the deterministic Guard decided about one draft (agents/guard.py computes it)."""

    ok: bool
    template: str
    items: tuple[FeedbackItem, ...]  # why it was rejected (empty when ok)
    lint_codes: tuple[str, ...]
    claims: tuple[Claim, ...]
    claim_ids: tuple[str, ...]
    verification: tuple[VerificationResult, ...]
    text: str | None  # rendered by code; None unless ok
    parts: tuple[Part, ...]

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(i.code for i in self.items)

    def feedback_record(self, attempt: int) -> FeedbackRecord:
        return FeedbackRecord(attempt, tuple(FeedbackEntry.from_item(i) for i in self.items))

    def feedback(self, attempt: int) -> Feedback:
        return self.feedback_record(attempt).to_feedback()


@dataclass(frozen=True)
class Verification:
    guard: bool
    verifier: VerifierStatus
    attempts: int
    label_source: LabelSource

    def to_dict(self) -> dict[str, Any]:
        return {"guard": self.guard, "verifier": self.verifier, "attempts": self.attempts,
                "label_source": self.label_source}


@dataclass(frozen=True)
class FinalCard:
    text: str
    parts: tuple[Part, ...]
    claims: tuple[Claim, ...]
    claim_ids: tuple[str, ...]
    verification_results: tuple[VerificationResult, ...]
    source: Source
    template: str | None
    verification: Verification


@dataclass(frozen=True)
class NarrationState:
    moment: Moment
    menu: ClaimMenu
    flags: Flags = Flags()
    briefing: Briefing | None = None
    drafts: tuple[DraftRecord, ...] = ()
    feedback_history: tuple[FeedbackRecord, ...] = ()
    attempt: int = 0
    trace: tuple[TraceStep, ...] = ()
    guard: GuardResult | None = None  # the Guard's latest verdict (the Verifier reads an accepted one)
    final_card: FinalCard | None = field(default=None)

    @property
    def can_retry(self) -> bool:
        return self.attempt < MAX_ATTEMPTS

    @property
    def last_feedback(self) -> FeedbackRecord | None:
        return self.feedback_history[-1] if self.feedback_history else None

    def next_attempt(self) -> NarrationState:
        return replace(self, attempt=self.attempt + 1)

    def with_briefing(self, briefing: Briefing) -> NarrationState:
        return replace(self, briefing=briefing)

    def with_draft(self, draft: DraftRecord) -> NarrationState:
        return replace(self, drafts=(*self.drafts, draft))

    def with_feedback(self, feedback: FeedbackRecord) -> NarrationState:
        return replace(self, feedback_history=(*self.feedback_history, feedback))

    def with_rendered(self, text: str) -> NarrationState:
        """The newest draft's rendered text, once the Guard accepted it."""
        last = replace(self.drafts[-1], text=text)
        return replace(self, drafts=(*self.drafts[:-1], last))

    def with_guard(self, guard: GuardResult) -> NarrationState:
        return replace(self, guard=guard)

    def with_step(self, step: TraceStep) -> NarrationState:
        return replace(self, trace=(*self.trace, step))

    def finish(self, card: FinalCard) -> NarrationState:
        if self.final_card is not None:
            raise ValueError("the card is already final")
        return replace(self, final_card=card)


class StateStore(Protocol):
    """The two methods of the Agent Framework's `WorkflowContext` the state helpers use."""

    def get_state(self, key: str, default: Any = None) -> Any: ...
    def set_state(self, key: str, value: Any) -> None: ...


def load(ctx: StateStore) -> NarrationState:
    state = ctx.get_state(STATE_KEY)
    if not isinstance(state, NarrationState):
        raise LookupError("no narration state in the workflow (the start executor must save it)")
    return state


def save(ctx: StateStore, state: NarrationState) -> None:
    ctx.set_state(STATE_KEY, state)


def update(ctx: StateStore, change: Callable[[NarrationState], NarrationState]) -> NarrationState:
    """Read-modify-write: the only way an executor changes the state."""
    new = change(load(ctx))
    if not isinstance(new, NarrationState):
        raise TypeError("a state update returns the new NarrationState")
    save(ctx, new)
    return new
