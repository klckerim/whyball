"""Seed'li, deterministik sentetik maç üreticisi.

Tüm rastgelelik tek bir ``random.Random(seed)`` örneğinden gelir. Global
``random``, saat, ``uuid`` veya hash/set sırasına bağlı hiçbir şey kullanılmaz;
böylece aynı seed her süreçte bayt bayt aynı olay akışını üretir.

Basitleştirmeler: home takımı iki devrede de x=105 yönüne hücum eder,
duran toplar (serbest vuruş, aut) ayrı olay olarak üretilmez.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .models import SCHEMA_VERSION, Event, EventType
from .names import FIRST_NAMES, LAST_NAMES, TEAM_CITIES, TEAM_SUFFIXES

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
PERIOD_SECONDS = 45 * 60
LINEUP_SIZE = 11
BENCH_SIZE = 5
MAX_SUBS = 3
MIN_PLAYERS = 7  # altına düşülürse kart verilmez
SIDES = ("home", "away")


def _other(side: str) -> str:
    return "away" if side == "home" else "home"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass
class _Team:
    name: str
    lineup: list[str]
    bench: list[str]
    on_pitch: list[str] = field(default_factory=list)  # index 0 kaleci
    booked: list[str] = field(default_factory=list)

    def outfield(self) -> list[str]:
        return self.on_pitch[1:]

    def goalkeeper(self) -> str:
        return self.on_pitch[0]


class _Match:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.match_id = f"m-{seed}"
        self.events: list[Event] = []
        self.score = {"home": 0, "away": 0}
        self.period = 1
        self.clock = 0  # maç başından itibaren saniye
        self.period_end = 0
        self.possession = "home"
        self.progress = 0.5  # topa sahip takım açısından: 0 kendi kalesi, 1 rakip kale
        self.y = PITCH_WIDTH / 2
        self.teams = self._build_teams()

    # --- kurulum ---------------------------------------------------------

    def _build_teams(self) -> dict[str, _Team]:
        cities = self.rng.sample(TEAM_CITIES, 2)
        pool = [f"{f} {l}" for f in FIRST_NAMES for l in LAST_NAMES]
        squad_size = LINEUP_SIZE + BENCH_SIZE
        players = self.rng.sample(pool, 2 * squad_size)
        teams = {}
        for i, side in enumerate(SIDES):
            squad = players[i * squad_size : (i + 1) * squad_size]
            team = _Team(
                name=f"{cities[i]} {self.rng.choice(TEAM_SUFFIXES)}",
                lineup=squad[:LINEUP_SIZE],
                bench=squad[LINEUP_SIZE:],
            )
            team.on_pitch = list(team.lineup)
            teams[side] = team
        return teams

    # --- olay yayma ------------------------------------------------------

    def _emit(
        self,
        etype: EventType,
        team: str | None = None,
        player: str | None = None,
        at_ball: bool = True,
        outcome: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        x = y = None
        if at_ball:
            p = self.progress if self.possession == "home" else 1.0 - self.progress
            x = round(_clamp(p * PITCH_LENGTH, 0.0, PITCH_LENGTH), 1)
            y = round(_clamp(self.y, 0.0, PITCH_WIDTH), 1)
        self.events.append(
            Event(
                match_id=self.match_id,
                seq=len(self.events),
                period=self.period,
                minute=self.clock // 60,
                second=self.clock % 60,
                type=etype,
                team=team,
                player=player,
                x=x,
                y=y,
                outcome=outcome,
                score=dict(self.score),
                data=data,
            )
        )

    def _turnover(self) -> None:
        # Top aynı fiziksel noktada kalır, yalnızca bakış açısı döner.
        self.possession = _other(self.possession)
        self.progress = 1.0 - self.progress

    def _give_ball(self, side: str, progress: float, y: float) -> None:
        self.possession = side
        self.progress = progress
        self.y = y

    def _walk_y(self) -> None:
        self.y = _clamp(self.y + self.rng.uniform(-12.0, 12.0), 1.0, PITCH_WIDTH - 1.0)

    # --- maç akışı -------------------------------------------------------

    def run(self) -> list[Event]:
        self._emit(
            EventType.MATCH_META,
            at_ball=False,
            data={
                "schema": SCHEMA_VERSION,
                "seed": self.seed,
                "teams": {
                    # Kopya: bench maç içinde değişiklikle küçülür, meta değişmemeli.
                    side: {"name": t.name, "lineup": list(t.lineup), "bench": list(t.bench)}
                    for side, t in self.teams.items()
                },
            },
        )
        first = self.rng.choice(SIDES)
        self._play_period(1, first)
        self._play_period(2, _other(first))
        return self.events

    def _play_period(self, period: int, kickoff_side: str) -> None:
        self.period = period
        start = (period - 1) * PERIOD_SECONDS
        stoppage = self.rng.randint(60, 240) if period == 1 else self.rng.randint(120, 420)
        self.period_end = start + PERIOD_SECONDS + stoppage
        self.clock = start
        subs = self._plan_subs() if period == 2 else {side: [] for side in SIDES}
        self._kickoff(kickoff_side)
        while True:
            self.clock += self.rng.randint(2, 20)
            if self.clock >= self.period_end:
                break
            self._run_due_subs(subs)
            self._play_step()
        self.clock = max(self.clock, self.period_end)
        end_type = EventType.HALF_TIME if period == 1 else EventType.FULL_TIME
        self._emit(end_type, at_ball=False)

    def _kickoff(self, side: str) -> None:
        self._give_ball(side, 0.5, PITCH_WIDTH / 2)
        self._emit(EventType.KICKOFF, side, self.rng.choice(self.teams[side].outfield()))

    def _plan_subs(self) -> dict[str, list[int]]:
        window = range(PERIOD_SECONDS + 15 * 60, PERIOD_SECONDS + 40 * 60)
        plan = {}
        for side in SIDES:
            n = self.rng.randint(1, MAX_SUBS)
            plan[side] = sorted(self.rng.sample(window, n))
        return plan

    def _run_due_subs(self, subs: dict[str, list[int]]) -> None:
        for side in SIDES:
            queue = subs[side]
            while queue and queue[0] <= self.clock:
                queue.pop(0)
                team = self.teams[side]
                if not team.bench or not team.outfield():
                    continue
                out = self.rng.choice(team.outfield())
                sub_in = team.bench.pop(self.rng.randrange(len(team.bench)))
                team.on_pitch[team.on_pitch.index(out)] = sub_in
                self._emit(
                    EventType.SUBSTITUTION, side, out, at_ball=False,
                    data={"player_in": sub_in},
                )

    def _play_step(self) -> None:
        p = self.progress
        actions = (
            (self._pass, 70),
            (self._dribble, 12),
            (self._shot, 16 if p > 0.75 else (4 if p > 0.6 else 0)),
            (self._foul, 5),
            (self._offside, 3 if p > 0.6 else 0),
        )
        action = self.rng.choices([a for a, _ in actions], [w for _, w in actions])[0]
        action()

    def _attacker(self) -> str:
        return self.rng.choice(self.teams[self.possession].outfield())

    def _pass(self) -> None:
        side, player = self.possession, self._attacker()
        if self.rng.random() < 0.82:
            self._emit(EventType.PASS, side, player, outcome="success")
            self.progress = _clamp(self.progress + self.rng.uniform(-0.04, 0.10), 0.02, 0.98)
            self._walk_y()
        else:
            self._emit(EventType.PASS, side, player, outcome="fail")
            self._turnover()

    def _dribble(self) -> None:
        side, player = self.possession, self._attacker()
        if self.rng.random() < 0.6:
            self._emit(EventType.DRIBBLE, side, player, outcome="success")
            self.progress = _clamp(self.progress + self.rng.uniform(0.02, 0.10), 0.02, 0.98)
            self._walk_y()
        else:
            self._emit(EventType.DRIBBLE, side, player, outcome="fail")
            self._turnover()

    def _shot(self) -> None:
        side, player = self.possession, self._attacker()
        defending = _other(side)
        goal_prob = 0.04 + 0.14 * _clamp((self.progress - 0.6) / 0.4, 0.0, 1.0)
        r = self.rng.random()
        if r < goal_prob:
            self._emit(EventType.SHOT, side, player, outcome="goal")
            self.score[side] += 1
            self.progress, self.y = 1.0, PITCH_WIDTH / 2
            self._emit(EventType.GOAL, side, player)
            self.clock += self.rng.randint(30, 75)
            if self.clock < self.period_end:
                self._kickoff(defending)
        elif r < goal_prob + 0.30:
            self._emit(EventType.SHOT, side, player, outcome="saved")
            self._give_ball(defending, 0.03, PITCH_WIDTH / 2)
            self._emit(EventType.SAVE, defending, self.teams[defending].goalkeeper())
            if self.rng.random() < 0.45:  # kaleci kornere çeler
                self._corner(side)
        elif r < goal_prob + 0.55:
            self._emit(EventType.SHOT, side, player, outcome="blocked")
            if self.rng.random() < 0.5:
                self._corner(side)
            else:
                self._turnover()
        else:
            self._emit(EventType.SHOT, side, player, outcome="off_target")
            self._give_ball(defending, 0.05, PITCH_WIDTH / 2)

    def _corner(self, side: str) -> None:
        self._give_ball(side, 1.0, self.rng.choice((0.0, PITCH_WIDTH)))
        self._emit(EventType.CORNER, side, self._attacker())
        self._give_ball(side, 0.9, self.rng.uniform(20.0, 48.0))

    def _foul(self) -> None:
        defending = _other(self.possession)
        team = self.teams[defending]
        offender = self.rng.choice(team.outfield())
        self._emit(EventType.FOUL, defending, offender)
        if len(team.on_pitch) <= MIN_PLAYERS:
            return
        r = self.rng.random()
        if r < 0.004:
            self._send_off(defending, offender, "straight_red")
        elif r < 0.15:
            self._emit(EventType.YELLOW_CARD, defending, offender, at_ball=False)
            if offender in team.booked:
                self._send_off(defending, offender, "second_yellow")
            else:
                team.booked.append(offender)
        # Faul sonrası top hücum eden takımda kalır (serbest vuruş).

    def _send_off(self, side: str, player: str, reason: str) -> None:
        self._emit(EventType.RED_CARD, side, player, at_ball=False, data={"reason": reason})
        self.teams[side].on_pitch.remove(player)

    def _offside(self) -> None:
        self._emit(EventType.OFFSIDE, self.possession, self._attacker())
        self._turnover()


def generate_match(seed: int) -> list[Event]:
    """Verilen seed için tam bir maçın olay akışını üretir."""
    return _Match(seed).run()
