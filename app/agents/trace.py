"""Trace of one narration: one step per agent action, written by our own executors.

The Agent Framework's workflow events carry no timestamps, and we do not depend on OpenTelemetry: each executor
measures itself with `time.perf_counter` (`Stopwatch`) and the step is stored with the card
(`StoredMoment.trace`). A step is immutable and holds its output as JSON text, so it is safe to keep in the
workflow state (which deep-copies what it stores).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

# Closed sets: a step outside them is a bug, not data.
STEPS = (
    "analyst", "analyst_fallback", "narrate", "guard", "verify", "verifier_error",
    "retry", "fallback", "finalize", "workflow_error",
)
AGENTS = ("analyst", "narrator", "guard", "verifier", "workflow", "template")
STATUSES = ("ok", "error", "timeout")


@dataclass(frozen=True)
class Tokens:
    input: int | None = None
    output: int | None = None
    reasoning: int | None = None

    def to_dict(self) -> dict[str, int | None]:
        return {"in": self.input, "out": self.output, "reasoning": self.reasoning}


@dataclass(frozen=True)
class TraceStep:
    step: str
    agent: str
    attempt: int  # 0: before the first attempt (analyst) or after the last (finalize)
    started_ms: int  # since the card's start
    duration_ms: int
    input_ref: str  # which state field the step read ("menu", "drafts[1]"); never a copy of the data
    output_json: str  # small JSON object: ids, codes, a short template; see `output`
    tokens: Tokens | None
    model: str | None
    status: str

    def __post_init__(self) -> None:
        if self.step not in STEPS:
            raise ValueError(f"unknown trace step {self.step!r}")
        if self.agent not in AGENTS:
            raise ValueError(f"unknown trace agent {self.agent!r}")
        if self.status not in STATUSES:
            raise ValueError(f"unknown trace status {self.status!r}")
        if self.attempt < 0 or self.started_ms < 0 or self.duration_ms < 0:
            raise ValueError("attempt and times cannot be negative")
        if not isinstance(json.loads(self.output_json), dict):
            raise ValueError("a step's output is a JSON object")

    @classmethod
    def make(
        cls, step: str, agent: str, *, attempt: int, started_ms: int, duration_ms: int, input_ref: str,
        output: Mapping[str, Any] | None = None, tokens: Tokens | None = None, model: str | None = None,
        status: str = "ok",
    ) -> TraceStep:
        return cls(step, agent, attempt, started_ms, duration_ms, input_ref,
                   json.dumps(dict(output or {}), sort_keys=True, ensure_ascii=False), tokens, model, status)

    @property
    def output(self) -> dict[str, Any]:
        """A fresh dict each time: changing it changes nothing stored."""
        return json.loads(self.output_json)

    def to_dict(self) -> dict[str, Any]:
        """The stored shape (`StoredMoment.trace` item, docs/DESIGN.md)."""
        return {
            "step": self.step, "agent": self.agent, "attempt": self.attempt, "started_ms": self.started_ms,
            "duration_ms": self.duration_ms, "input_ref": self.input_ref, "output": self.output,
            "tokens": self.tokens.to_dict() if self.tokens else {"in": None, "out": None, "reasoning": None},
            "model": self.model, "status": self.status,
        }


class Stopwatch:
    """Times steps relative to the card's start with an injectable clock (tests pass a fake)."""

    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock
        self._t0 = clock()

    @staticmethod
    def _ms(seconds: float) -> int:
        return max(0, round(seconds * 1000))

    def now_ms(self) -> int:
        return self._ms(self._clock() - self._t0)

    def start(self) -> float:
        return self._clock()

    def span(self, started: float) -> tuple[int, int]:
        """(started_ms, duration_ms) of a step that began at `started` (a `start()` value)."""
        return self._ms(started - self._t0), self._ms(self._clock() - started)
