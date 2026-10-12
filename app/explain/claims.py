"""Tipli iddia şeması ve deterministik doğrulayıcı.

Bir iddia, belirli bir zaman aralığında bir özne (takım ve/veya oyuncu) için
bir metriğin değeri hakkındadır ve dayanak olaylara işaret eder. Doğrulayıcı
iddianın ``end`` anından sonraki hiçbir olayı kullanmaz.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, NamedTuple

from app.analytics.config import DEFAULT_CONFIG, AnalyticsConfig
from app.analytics.metrics import ENTRY, MatchTracker, other
from app.generator.models import Event, EventType

from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig

KINDS = ("count", "ratio", "state")
COMPARISONS = ("eq", "gte", "lte", "gt", "lt", "approx")
SIDES = ("home", "away")


class MatchTime(NamedTuple):
    period: int
    minute: int
    second: int

    @classmethod
    def of(cls, e: Event) -> MatchTime:
        return cls(e.period, e.minute, e.second)

    def label(self) -> str:
        return f"{self.period}H {self.minute:02d}:{self.second:02d}"


KICKOFF = MatchTime(1, 0, 0)


def event_ref(e: Event) -> str:
    return f"{e.match_id}#{e.seq}"


def parse_ref(ref: str) -> tuple[str, int]:
    match_id, sep, seq = ref.rpartition("#")
    if not sep or not match_id or not seq.isdigit():
        raise ValueError(f"Geçersiz event id: {ref!r}")
    return match_id, int(seq)


@dataclass(frozen=True)
class Subject:
    team: str | None = None
    player: str | None = None

    def label(self) -> str:
        parts = [f"team={self.team}"] if self.team else []
        if self.player:
            parts.append(f"player={self.player}")
        return " ".join(parts) or "all"


@dataclass(frozen=True)
class Claim:
    kind: str  # "count" | "ratio" | "state"
    subject: Subject
    metric: str
    comparison: str  # eq | gte | lte | gt | lt | approx
    value: float
    start: MatchTime  # dahil
    end: MatchTime  # dahil; iddianın "şimdi"si
    event_ids: tuple[str, ...]  # "m-42-red_card_swing#213"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "subject": {"team": self.subject.team, "player": self.subject.player},
            "metric": self.metric,
            "comparison": self.comparison,
            "value": self.value,
            "start": list(self.start),
            "end": list(self.end),
            "event_ids": list(self.event_ids),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Claim:
        return cls(
            kind=d["kind"],
            subject=Subject(**d["subject"]),
            metric=d["metric"],
            comparison=d["comparison"],
            value=d["value"],
            start=MatchTime(*d["start"]),
            end=MatchTime(*d["end"]),
            event_ids=tuple(d["event_ids"]),
        )

    def describe(self) -> str:
        return (
            f"{self.kind} {self.metric} {self.subject.label()} "
            f"[{self.start.label()}–{self.end.label()}] {self.comparison} {self.value:g} "
            f"refs=[{', '.join(self.event_ids)}]"
        )


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    reason: str  # "ok" ya da ret nedeni
    actual: float | None = None


@dataclass(frozen=True)
class Measurement:
    value: float
    counted: tuple[int, ...] = ()  # count türünde sayılan olayların seq'leri


# --- metrik kayıt defteri -----------------------------------------------------


def _type_is(t: EventType) -> Callable[[Event], bool]:
    return lambda e: e.type is t


def _penalty(outcome: str) -> Callable[[Event], bool]:
    return lambda e: e.type is EventType.PENALTY and e.outcome == outcome


COUNT_METRICS: dict[str, Callable[[Event], bool]] = {
    "goals": _type_is(EventType.GOAL),
    "shots": _type_is(EventType.SHOT),
    "shots_on_target": lambda e: e.type is EventType.SHOT and e.outcome in ("goal", "saved"),
    "corners": _type_is(EventType.CORNER),
    "fouls": _type_is(EventType.FOUL),
    "yellow_cards": _type_is(EventType.YELLOW_CARD),
    "red_cards": _type_is(EventType.RED_CARD),
    "penalties_scored": _penalty("scored"),
    "penalties_saved": _penalty("saved"),
    "penalties_missed": _penalty("missed"),
    "substitutions": _type_is(EventType.SUBSTITUTION),
}
RATIO_METRICS = ("possession", "field_tilt")
STATE_METRICS = ("score", "score_margin", "min_score_margin", "players_on_pitch", "pressure_balance")
METRIC_KINDS: dict[str, str] = {
    **{m: "count" for m in COUNT_METRICS},
    **{m: "ratio" for m in RATIO_METRICS},
    **{m: "state" for m in STATE_METRICS},
}


def _visible(events: Sequence[Event], end: MatchTime) -> list[Event]:
    """`end` anına kadarki olaylar; kesmeyi geçen ilk olayda durulur."""
    out = []
    for e in events:
        if MatchTime.of(e) > end:
            break
        out.append(e)
    return out


def _matches(e: Event, subject: Subject) -> bool:
    if subject.team is not None and e.team != subject.team:
        return False
    if subject.player is not None and e.player != subject.player:
        return False
    return True


def _margin(score: dict[str, int], team: str) -> int:
    return score[team] - score[other(team)]


def measure(
    metric: str,
    subject: Subject,
    start: MatchTime,
    end: MatchTime,
    events: Sequence[Event],
    analytics_config: AnalyticsConfig = DEFAULT_CONFIG,
) -> Measurement:
    """Metriği yalnızca `end` anına kadarki olaylardan hesaplar."""
    visible = _visible(events, end)
    in_range = [e for e in visible if MatchTime.of(e) >= start]
    kind = METRIC_KINDS[metric]
    team = subject.team

    if kind == "count":
        pred = COUNT_METRICS[metric]
        hits = tuple(e.seq for e in in_range if pred(e) and _matches(e, subject))
        return Measurement(len(hits), hits)

    if metric == "possession":
        touches = Counter(
            e.team for e in in_range if e.type in (EventType.PASS, EventType.DRIBBLE)
        )
        total = touches["home"] + touches["away"]
        return Measurement(touches[team] / total if total else 0.5)

    current = visible[-1].score if visible else {"home": 0, "away": 0}
    if metric == "score":
        return Measurement(current[team])
    if metric == "score_margin":
        return Measurement(_margin(current, team))
    if metric == "min_score_margin":
        margins = [_margin(e.score, team) for e in in_range] or [_margin(current, team)]
        return Measurement(min(margins))
    if metric == "players_on_pitch":
        meta = events[0].data if events and events[0].type is EventType.MATCH_META else None
        squad = len(meta["teams"][team]["lineup"]) if meta else DEFAULT_EXPLAIN_CONFIG.full_squad
        reds = sum(e.type is EventType.RED_CARD and e.team == team for e in visible)
        return Measurement(squad - reds)

    tracker = MatchTracker(analytics_config)
    for e in visible:
        tracker.update(e)
    if metric == "pressure_balance":
        balance = tracker.pressure_balance()
        return Measurement(balance if team == "home" else -balance)
    # field_tilt: aralıktaki son üçte bir girişlerinin payı
    first = in_range[0].seq if in_range else None
    entries = Counter(
        r.team for r in tracker.records
        if r.kind == ENTRY and first is not None and r.seq >= first
    )
    total = entries["home"] + entries["away"]
    return Measurement(entries[team] / total if total else 0.5)


def _compare(actual: float, comparison: str, value: float, config: ExplainConfig) -> bool:
    if comparison == "eq":
        return actual == value
    if comparison == "approx":
        return abs(actual - value) <= config.approx_tolerance + config.float_epsilon
    if comparison == "gte":
        return actual >= value
    if comparison == "lte":
        return actual <= value
    if comparison == "gt":
        return actual > value
    return actual < value  # "lt"


def verify_claim(
    claim: Claim,
    events: Sequence[Event],
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
    analytics_config: AnalyticsConfig = DEFAULT_CONFIG,
) -> VerificationResult:
    def fail(reason: str, actual: float | None = None) -> VerificationResult:
        return VerificationResult(False, reason, actual)

    kind = METRIC_KINDS.get(claim.metric)
    if kind is None:
        return fail("unknown_metric")
    if claim.kind != kind:
        return fail("kind_mismatch")
    if claim.comparison not in COMPARISONS:
        return fail("invalid_comparison")
    if claim.start < KICKOFF or claim.end < claim.start:
        return fail("invalid_range")
    if claim.subject.team not in (None, *SIDES) or (kind != "count" and claim.subject.team is None):
        return fail("invalid_subject")
    if not events:
        return fail("unknown_event")

    match_id = events[0].match_id
    by_seq = {e.seq: e for e in events}
    cited: list[int] = []
    for ref in claim.event_ids:
        try:
            ref_match, seq = parse_ref(ref)
        except ValueError:
            return fail("unknown_event")
        if ref_match != match_id:
            return fail("foreign_event")
        e = by_seq.get(seq)
        if e is None:
            return fail("unknown_event")
        t = MatchTime.of(e)
        if t > claim.end:
            return fail("future_event")
        if t < claim.start:
            return fail("evidence_out_of_range")
        cited.append(seq)
    if kind != "count" and not cited:
        return fail("missing_evidence")

    m = measure(claim.metric, claim.subject, claim.start, claim.end, events, analytics_config)
    if kind == "count" and set(cited) != set(m.counted):
        return fail("evidence_mismatch", m.value)
    if not _compare(m.value, claim.comparison, claim.value, config):
        return fail("value_mismatch", m.value)
    return VerificationResult(True, "ok", m.value)
