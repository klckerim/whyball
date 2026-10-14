"""Limits of an agent run: per-call timeouts, concurrency, and one call budget shared by every agent."""

from __future__ import annotations

from dataclasses import dataclass

from app.explain.narrator import BudgetExceeded


@dataclass(frozen=True)
class AgentsConfig:
    narrator_timeout_s: float = 60.0  # per call; a reasoning-model call once hung for 60 s, so this is a hard stop
    analyst_timeout_s: float = 30.0
    analyst_max_tokens: int = 1500  # includes reasoning tokens
    verifier_max_tokens: int = 1500
    verifier_timeout_s: float = 30.0
    max_concurrent_cards: int = 3  # cards in flight at once (one workflow instance per card)
    max_calls_per_run: int = 200  # model calls of all agents together; worst case 25 cards x (1 + 3 + 3) = 175
    max_attempts: int = 3  # Narrator + Guard + Verifier rounds per card (state.MAX_ATTEMPTS)


DEFAULT_AGENTS_CONFIG = AgentsConfig()


class CallBudget:
    """Counts model calls of a whole run; `take()` raises once the budget is spent."""

    def __init__(self, max_calls: int) -> None:
        self.max_calls = max_calls
        self.calls = 0

    def take(self) -> int:
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"agent call budget exceeded: {self.calls}/{self.max_calls}")
        self.calls += 1
        return self.calls
