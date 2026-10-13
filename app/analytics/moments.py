"""Moment detector: processes the stream event by event and emits moments worth narrating.

Each moment relies only on events seen up to that point (``at_seq``); its evidence
events (``event_ids``) are always less than or equal to ``at_seq``.

One goal event yields one card: a goal that changes the match state (opener / equalizer /
go_ahead) carries that change as a sub-label in ``detail["score_change"]``; its importance is
the maximum of the goal and the score change importance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from app.generator.models import Event, EventType

from .config import DEFAULT_CONFIG, AnalyticsConfig
from .metrics import CORNER, ENTRY, GOAL, SHOT, SIDES, TOUCH, MatchTracker, other, stated

MOMENT_TYPES = (
    "goal",
    "red_card",
    "penalty",
    "pressure_shift",
    "dominance_without_reward",
)


@dataclass(frozen=True)
class Moment:
    id: str
    type: str
    period: int
    minute: int
    second: int
    at_seq: int  # event that triggered the moment
    importance: float
    event_ids: tuple[int, ...]
    team: str | None
    detail: dict[str, Any]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["event_ids"] = list(self.event_ids)
        return d


def _state(score: dict[str, int]) -> str:
    if score["home"] > score["away"]:
        return "home"
    if score["away"] > score["home"]:
        return "away"
    return "draw"


class MomentDetector:
    def __init__(self, config: AnalyticsConfig = DEFAULT_CONFIG) -> None:
        self.config = config
        self.tracker = MatchTracker(config)
        self.moments: list[Moment] = []
        self._match_id = ""
        self._prev_seq: int | None = None
        self._last_foul: dict[str, int] = {}
        self._max_deficit = {"home": 0, "away": 0}
        self._pressure_side: str | None = None  # hysteresis state
        self._last_shift_side: str | None = None
        self._last_shift_at: int | None = None
        self._neutral_since: int | None = None
        self._last_dominance_at: dict[str, int | None] = {"home": None, "away": None}

    # --- helpers -----------------------------------------------------

    def _importance(self, mtype: str, e: Event, from_behind: bool = False) -> float:
        c = self.config
        v = c.importance_base[mtype]
        if e.period == 2 and e.minute >= c.late_game_minute:
            v += c.late_bonus
        if abs(e.score["home"] - e.score["away"]) <= c.close_game_margin:
            v += c.close_game_bonus
        if from_behind:
            v += c.from_behind_bonus
        return round(min(1.0, max(0.0, v)), 3)

    def _make(
        self,
        mtype: str,
        e: Event,
        team: str | None,
        event_ids: Iterable[int],
        detail: dict[str, Any],
        importance: float | None = None,
    ) -> Moment:
        m = Moment(
            id=f"{self._match_id}-M{len(self.moments) + 1:03d}",
            type=mtype,
            period=e.period,
            minute=e.minute,
            second=e.second,
            at_seq=e.seq,
            importance=self._importance(mtype, e) if importance is None else importance,
            event_ids=tuple(event_ids),
            team=team,
            detail=detail,
            metrics=self.tracker.snapshot().summary(self.config.summary_decimals),
        )
        self.moments.append(m)
        return m

    # --- main loop --------------------------------------------------------

    def process(self, e: Event) -> list[Moment]:
        """Processes an event and returns the moments it produces."""
        if not self._match_id:
            self._match_id = e.match_id
        prev_score = dict(self.tracker.score)
        self.tracker.update(e)
        start = len(self.moments)
        t = e.type

        if t is EventType.FOUL:
            self._last_foul[e.team] = e.seq
        elif t is EventType.PENALTY:
            ids = [s for s in (self._last_foul.get(other(e.team)),) if s is not None]
            self._make(
                "penalty", e, e.team, [*ids, e.seq],
                {"player": e.player, "outcome": e.outcome},
            )
        elif t is EventType.RED_CARD:
            foul = self._last_foul.get(e.team)
            ids = [foul] if foul is not None and e.seq - foul <= 3 else []
            self._make(
                "red_card", e, e.team, [*ids, e.seq],
                {"player": e.player, "reason": (e.data or {}).get("reason")},
            )
        elif t is EventType.GOAL:
            self._on_goal(e, prev_score)

        if t is EventType.SHOT and e.outcome != "goal":  # a shot that scored is not 'without reward'
            self._check_dominance(e)
        self._check_pressure_shift(e)

        self._prev_seq = e.seq
        return self.moments[start:]

    def _on_goal(self, e: Event, prev_score: dict[str, int]) -> None:
        # A goal event always comes right after a shot(goal) or penalty(scored) event.
        ids = [s for s in (self._prev_seq,) if s is not None]
        detail: dict[str, Any] = {"player": e.player, "score": dict(e.score)}
        importance = self._importance("goal", e)

        before, after = _state(prev_score), _state(e.score)
        if before != after:
            change: dict[str, Any] = {"from_state": before, "to_state": after}
            from_behind = False
            if before == "draw":
                if prev_score["home"] + prev_score["away"] == 0:
                    change["kind"] = "opener"
                else:
                    change["kind"] = "go_ahead"
                    # from_behind: the team trailed at some earlier point of the match (not necessarily just
                    # before this goal: the score before it was level); max_deficit is that largest deficit.
                    from_behind = self._max_deficit[e.team] > 0
                    change["from_behind"] = from_behind
                    change["max_deficit"] = self._max_deficit[e.team]
            else:
                change["kind"] = "equalizer"
            detail["score_change"] = change
            importance = max(importance, self._importance("score_change", e, from_behind))
        self._make("goal", e, e.team, [*ids, e.seq], detail, importance=importance)

        for side in SIDES:
            deficit = e.score[other(side)] - e.score[side]
            self._max_deficit[side] = max(self._max_deficit[side], deficit)

    def _check_pressure_shift(self, e: Event) -> None:
        c, tr = self.config, self.tracker
        if tr.played < c.pressure_window_min * 60:
            return
        balance = tr.pressure_balance()
        if balance >= c.shift_enter:
            self._pressure_side = "home"
        elif balance <= -c.shift_enter:
            self._pressure_side = "away"
        elif abs(balance) < c.shift_exit:
            self._pressure_side = None
        side = self._pressure_side
        if side is None:
            if self._neutral_since is None:
                self._neutral_since = tr.played
            elif tr.played - self._neutral_since >= c.shift_rearm_min * 60:
                self._last_shift_side = None  # pressure faded
            return
        self._neutral_since = None
        if side == self._last_shift_side:
            return
        if (
            self._last_shift_at is not None
            and tr.played - self._last_shift_at < c.shift_cooldown_min * 60
        ):
            return
        # A shot in the final third can produce both an entry and a shot record; seq is deduplicated.
        evidence = list(dict.fromkeys(
            r.seq for r in tr.window(c.pressure_window_min)
            if r.team == side and r.kind in (SHOT, ENTRY, CORNER)
        ))[-c.max_evidence :]
        self._make(
            "pressure_shift", e, side, evidence,
            {
                "from": self._last_shift_side,
                "to": side,
                "balance": stated(balance),
                "window_min": c.pressure_window_min,
            },
        )
        self._last_shift_side = side
        self._last_shift_at = tr.played

    def _check_dominance(self, e: Event) -> None:
        c, tr = self.config, self.tracker
        side, opp = e.team, other(e.team)
        if tr.played < c.dominance_window_min * 60:
            return
        last = self._last_dominance_at[side]
        if last is not None and tr.played - last < c.dominance_cooldown_min * 60:
            return
        if tr.score[side] > tr.score[opp]:
            return
        window = tr.window(c.dominance_window_min)
        counts = {k: {"home": 0, "away": 0} for k in (SHOT, TOUCH, GOAL)}
        for r in window:
            if r.kind in counts:
                counts[r.kind][r.team] += 1
        touches = counts[TOUCH]["home"] + counts[TOUCH]["away"]
        if touches == 0 or counts[GOAL][side] > 0:
            return
        possession = counts[TOUCH][side] / touches
        shot_margin = counts[SHOT][side] - counts[SHOT][opp]
        if shot_margin < c.dominance_shot_margin or possession < c.dominance_possession:
            return
        evidence = [r.seq for r in window if r.team == side and r.kind == SHOT][-c.max_evidence :]
        self._make(
            "dominance_without_reward", e, side, evidence,
            {
                "shots": {side: counts[SHOT][side], opp: counts[SHOT][opp]},
                "possession": stated(possession),
                "score": dict(tr.score),
                "window_min": c.dominance_window_min,
            },
        )
        self._last_dominance_at[side] = tr.played


def detect_moments(
    events: Iterable[Event], config: AnalyticsConfig = DEFAULT_CONFIG
) -> list[Moment]:
    detector = MomentDetector(config)
    for e in events:
        detector.process(e)
    return detector.moments
