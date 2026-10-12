"""Olay akışından deterministik maç metrikleri.

Çekirdek ``MatchTracker`` olayları tek tek tüketir; gelecekteki bir olayı hiç
görmediği için ileriye bakma yapısal olarak imkânsızdır. Fonksiyonel API
(``metrics_at`` vb.) tracker'ı kesme noktasına kadar besleyip durur.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.generator.models import Event, EventType

from .config import DEFAULT_CONFIG, AnalyticsConfig

SIDES = ("home", "away")
SECOND_HALF_START = 45 * 60
ON_BALL = (EventType.PASS, EventType.DRIBBLE, EventType.SHOT, EventType.CORNER)
TOUCHES = (EventType.PASS, EventType.DRIBBLE)

# Pencere kayıt türleri
SHOT, ENTRY, CORNER, TOUCH, GOAL = "shot", "entry", "corner", "touch", "goal"


def other(side: str) -> str:
    return "away" if side == "home" else "home"


def _share(counts: dict[str, int | float]) -> dict[str, float]:
    total = counts["home"] + counts["away"]
    if total == 0:
        return {"home": 0.5, "away": 0.5}
    return {side: counts[side] / total for side in SIDES}


@dataclass(frozen=True)
class Record:
    """Pencere hesapları için olay özeti."""

    seq: int
    played: int  # oynanan saniye (devre arası hariç)
    team: str
    kind: str


@dataclass(frozen=True)
class MetricSnapshot:
    seq: int | None  # dahil edilen son olay
    period: int
    minute: int
    second: int
    played_seconds: int
    score: dict[str, int]
    possession: dict[str, float]
    shots: dict[str, int]
    final_third_entries: dict[str, int]
    field_tilt: dict[str, float]
    pressure: dict[str, float]
    pressure_balance: float

    def summary(self, decimals: int = DEFAULT_CONFIG.summary_decimals) -> dict[str, Any]:
        def r(d: dict[str, float]) -> dict[str, float]:
            return {k: round(v, decimals) for k, v in d.items()}

        return {
            "score": dict(self.score),
            "possession": r(self.possession),
            "shots": dict(self.shots),
            "final_third_entries": dict(self.final_third_entries),
            "field_tilt": r(self.field_tilt),
            "pressure": r(self.pressure),
            "pressure_balance": round(self.pressure_balance, decimals),
        }


class MatchTracker:
    def __init__(self, config: AnalyticsConfig = DEFAULT_CONFIG) -> None:
        self.config = config
        self.last: Event | None = None
        self.played = 0
        self.first_half_played: int | None = None
        self.score = {"home": 0, "away": 0}
        self.touches = {"home": 0, "away": 0}
        self.shots = {"home": 0, "away": 0}
        self.entries = {"home": 0, "away": 0}
        self._in_final_third = {"home": False, "away": False}
        self.records: list[Record] = []

    def _played_seconds(self, e: Event) -> int:
        clock = e.minute * 60 + e.second
        if e.period == 1:
            return clock
        first_half = self.first_half_played if self.first_half_played is not None else SECOND_HALF_START
        return first_half + clock - SECOND_HALF_START

    def _is_final_third(self, side: str, x: float) -> bool:
        c = self.config
        if side == "home":
            return x >= c.final_third_x
        return x <= c.pitch_length - c.final_third_x

    def _record(self, e: Event, kind: str) -> None:
        self.records.append(Record(e.seq, self.played, e.team, kind))

    def update(self, e: Event) -> None:
        self.last = e
        self.played = self._played_seconds(e)
        self.score = dict(e.score)
        t = e.type

        if t is EventType.HALF_TIME:
            self.first_half_played = self.played
        if t is EventType.KICKOFF:
            self._in_final_third = {"home": False, "away": False}

        if t in ON_BALL and e.team is not None:
            self._in_final_third[other(e.team)] = False
            if e.x is not None:
                inside = self._is_final_third(e.team, e.x)
                if inside and not self._in_final_third[e.team]:
                    self.entries[e.team] += 1
                    self._record(e, ENTRY)
                self._in_final_third[e.team] = inside

        if t in TOUCHES:
            self.touches[e.team] += 1
            self._record(e, TOUCH)
        elif t is EventType.SHOT:
            self.shots[e.team] += 1
            self._record(e, SHOT)
        elif t is EventType.CORNER:
            self._record(e, CORNER)
        elif t is EventType.GOAL:
            self._record(e, GOAL)

    # --- pencere sorguları ---------------------------------------------

    def window(self, minutes: float) -> list[Record]:
        """Son `minutes` oynanan dakikadaki kayıtlar (eski → yeni)."""
        start = self.played - minutes * 60
        out = []
        for r in reversed(self.records):
            if r.played <= start:
                break
            out.append(r)
        out.reverse()
        return out

    def window_counts(self, minutes: float) -> dict[str, dict[str, int]]:
        counts = {k: {"home": 0, "away": 0} for k in (SHOT, ENTRY, CORNER, TOUCH, GOAL)}
        for r in self.window(minutes):
            counts[r.kind][r.team] += 1
        return counts

    def pressure(self) -> dict[str, float]:
        c = self.config
        counts = self.window_counts(c.pressure_window_min)
        return {
            side: counts[SHOT][side] * c.w_shot
            + counts[ENTRY][side] * c.w_entry
            + counts[CORNER][side] * c.w_corner
            for side in SIDES
        }

    def pressure_balance(self, pressure: dict[str, float] | None = None) -> float:
        p = pressure if pressure is not None else self.pressure()
        total = p["home"] + p["away"]
        if total < self.config.min_pressure_volume:
            return 0.0
        return (p["home"] - p["away"]) / total

    def snapshot(self) -> MetricSnapshot:
        e = self.last
        pressure = self.pressure()
        return MetricSnapshot(
            seq=e.seq if e else None,
            period=e.period if e else 1,
            minute=e.minute if e else 0,
            second=e.second if e else 0,
            played_seconds=self.played,
            score=dict(self.score),
            possession=_share(self.touches),
            shots=dict(self.shots),
            final_third_entries=dict(self.entries),
            field_tilt=_share(self.entries),
            pressure=pressure,
            pressure_balance=self.pressure_balance(pressure),
        )


# --- fonksiyonel API ------------------------------------------------------


def _included(e: Event, until_seq: int | None, until_minute: int | None) -> bool:
    if until_seq is not None and e.seq > until_seq:
        return False
    if until_minute is not None:
        period = 1 if until_minute < 45 else 2
        if (e.period, e.minute) > (period, until_minute):
            return False
    return True


def metrics_at(
    events: Iterable[Event],
    *,
    until_seq: int | None = None,
    until_minute: int | None = None,
    config: AnalyticsConfig = DEFAULT_CONFIG,
) -> MetricSnapshot:
    """Kesme noktasına kadarki olaylardan metrikler.

    until_minute=t: t < 45 ise 1. devrenin t. dakikasına, aksi halde 2. devrenin
    t. dakikasına kadar (o dakika dahil). Akış zaman sıralı olduğundan kesmeyi
    geçen ilk olayda durulur; sonrası hiç okunmaz.
    """
    tracker = MatchTracker(config)
    for e in events:
        if not _included(e, until_seq, until_minute):
            break
        tracker.update(e)
    return tracker.snapshot()


def possession_share(events: Iterable[Event], **cut: Any) -> dict[str, float]:
    return metrics_at(events, **cut).possession


def shot_counts(events: Iterable[Event], **cut: Any) -> dict[str, int]:
    return metrics_at(events, **cut).shots


def final_third_entries(events: Iterable[Event], **cut: Any) -> dict[str, int]:
    return metrics_at(events, **cut).final_third_entries


def field_tilt(events: Iterable[Event], **cut: Any) -> dict[str, float]:
    return metrics_at(events, **cut).field_tilt


def pressure_index(events: Iterable[Event], **cut: Any) -> dict[str, float]:
    """Son pencere için {"home", "away", "balance"}."""
    snap = metrics_at(events, **cut)
    return {**snap.pressure, "balance": snap.pressure_balance}
