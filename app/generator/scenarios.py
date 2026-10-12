"""Hazır maç senaryoları: belirli dakikalarda zorunlu olaylar.

Senaryo modunda doğal goller kapalıdır; skor yalnızca zorunlu olaylardan
oluşur. Böylece hikâye her seed'de korunur, geri kalan akış (pas, şut,
korner, kart, değişiklik) seed'e göre doğal üretilir.
"""

from __future__ import annotations

from dataclasses import dataclass

FORCED_KINDS = ("goal", "red_card", "penalty")
PENALTY_OUTCOMES = ("scored", "saved")
LAST_MINUTE = 89  # uzatma dakikaları değişken olduğu için zorunlu olay 90'dan önce


@dataclass(frozen=True)
class ForcedEvent:
    minute: int  # <45 → 1. devre, ≥45 → 2. devre
    kind: str  # "goal" | "red_card" | "penalty"
    team: str  # "home" | "away"; penaltıda kullanan, kırmızıda cezayı alan takım
    outcome: str | None = None  # yalnızca penaltı: "scored" | "saved"

    def __post_init__(self) -> None:
        if not 0 <= self.minute <= LAST_MINUTE:
            raise ValueError(f"minute 0..{LAST_MINUTE} aralığında olmalı: {self.minute}")
        if self.kind not in FORCED_KINDS:
            raise ValueError(f"Bilinmeyen kind: {self.kind!r}")
        if self.team not in ("home", "away"):
            raise ValueError(f"team 'home' ya da 'away' olmalı: {self.team!r}")
        if self.kind == "penalty":
            if self.outcome not in PENALTY_OUTCOMES:
                raise ValueError(f"Penaltı outcome {PENALTY_OUTCOMES} içinden olmalı")
        elif self.outcome is not None:
            raise ValueError(f"{self.kind} için outcome verilmez")

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
    # Takım bazlı top kaybı çarpanı (pas ve top sürme): 1.0 normal, <1 topa daha hâkim.
    turnover_factor: dict[str, float] | None = None
    # Takım bazlı ileri gidiş çarpanı (pas ve top sürme): <1 sabırlı oyun kurma.
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
            description="Deplasman 2-0 öne geçer, ev sahibi son 20 dakikada 3 golle döner.",
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
            description="Ev sahibi öne geçer, kırmızı kartla 10 kişi kalır ve maçı kaybeder.",
            forced=(
                ForcedEvent(22, "goal", "home"),
                ForcedEvent(38, "red_card", "home"),
                ForcedEvent(61, "goal", "away"),
                ForcedEvent(84, "goal", "away"),
            ),
        ),
        Scenario(
            name="dominant_loss",
            description="Ev sahibi topa hâkim olur, penaltı kaçırır ve tek kontra golle kaybeder.",
            forced=(
                ForcedEvent(57, "goal", "away"),
                ForcedEvent(70, "penalty", "home", "saved"),
            ),
            turnover_factor={"home": 0.45, "away": 1.25},
            tempo={"home": 0.5},
        ),
    )
}
