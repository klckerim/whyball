"""Ready-made match scenarios: forced events at given minutes.

Natural goals are off in scenario mode; the score comes only from forced events.
That keeps the story intact for every seed, while the rest of the flow (passes, shots,
corners, cards, substitutions) is generated naturally from the seed.
"""

from __future__ import annotations

from dataclasses import dataclass

FORCED_KINDS = ("goal", "red_card", "penalty")
PENALTY_OUTCOMES = ("scored", "saved")
LAST_MINUTE = 89  # stoppage time varies, so forced events come before 90


@dataclass(frozen=True)
class ForcedEvent:
    minute: int  # <45 → first half, ≥45 → second half
    kind: str  # "goal" | "red_card" | "penalty"
    team: str  # "home" | "away"; the team taking the penalty, or the one receiving the red card
    outcome: str | None = None  # penalty only: "scored" | "saved"

    def __post_init__(self) -> None:
        if not 0 <= self.minute <= LAST_MINUTE:
            raise ValueError(f"minute must be in 0..{LAST_MINUTE}: {self.minute}")
        if self.kind not in FORCED_KINDS:
            raise ValueError(f"Unknown kind: {self.kind!r}")
        if self.team not in ("home", "away"):
            raise ValueError(f"team must be 'home' or 'away': {self.team!r}")
        if self.kind == "penalty":
            if self.outcome not in PENALTY_OUTCOMES:
                raise ValueError(f"Penalty outcome must be one of {PENALTY_OUTCOMES}")
        elif self.outcome is not None:
            raise ValueError(f"No outcome for {self.kind}")

    @property
    def period(self) -> int:
        return 1 if self.minute < 45 else 2

    @property
    def scores(self) -> bool:
        return self.kind == "goal" or (self.kind == "penalty" and self.outcome == "scored")


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    forced: tuple[ForcedEvent, ...]
    # Per-team turnover multiplier (passes and dribbles): 1.0 normal, <1 keeps the ball better.
    turnover_factor: dict[str, float] | None = None
    # Per-team progression multiplier (passes and dribbles): <1 means patient build-up.
    tempo: dict[str, float] | None = None

    @property
    def final_score(self) -> dict[str, int]:
        score = {"home": 0, "away": 0}
        for f in self.forced:
            if f.scores:
                score[f.team] += 1
        return score


SCENARIOS: dict[str, Scenario] = {
    s.name: s
    for s in (
        Scenario(
            name="late_comeback",
            description="The away side go 2-0 up, the home side come back with 3 goals in the last 20 minutes.",
            forced=(
                ForcedEvent(18, "goal", "away"),
                ForcedEvent(52, "goal", "away"),
                ForcedEvent(74, "goal", "home"),
                ForcedEvent(83, "penalty", "home", "scored"),
                ForcedEvent(89, "goal", "home"),
            ),
        ),
        Scenario(
            name="red_card_swing",
            description="The home side go ahead, are reduced to 10 men by a red card and lose.",
            forced=(
                ForcedEvent(22, "goal", "home"),
                ForcedEvent(38, "red_card", "home"),
                ForcedEvent(61, "goal", "away"),
                ForcedEvent(84, "goal", "away"),
            ),
        ),
        Scenario(
            name="dominant_loss",
            description="The home side dominate possession, miss a penalty and lose to a single counter-attack goal.",
            forced=(
                ForcedEvent(57, "goal", "away"),
                ForcedEvent(70, "penalty", "home", "saved"),
            ),
            turnover_factor={"home": 0.45, "away": 1.25},
            tempo={"home": 0.5},
        ),
    )
}
