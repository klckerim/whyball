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
from .scenarios import SCENARIOS, ForcedEvent, Scenario

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
PERIOD_SECONDS = 45 * 60
LINEUP_SIZE = 11
BENCH_SIZE = 5
MAX_SUBS = 3
MIN_PLAYERS = 7  # altına düşülürse kart verilmez
SIDES = ("home", "away")

PASS_SUCCESS = 0.82
DRIBBLE_SUCCESS = 0.6
TURNOVER_PER_MISSING = 0.06  # sahadaki her eksik oyuncu için ek top kaybı olasılığı
STRAIGHT_RED_PROB = 0.002  # faul başına
YELLOW_PROB = 0.15  # faul başına
BOOKED_CAUTION = 0.15  # sarısı olan oyuncunun tekrar sarı görme çarpanı
BOX_PROGRESS = 0.83  # bunun ötesi ceza sahası
PENALTY_FROM_BOX_FOUL = 0.065
PENALTY_SPOT = 1.0 - 11.0 / PITCH_LENGTH


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
    def __init__(self, seed: int, scenario: Scenario | None = None) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.scenario = scenario
        self.match_id = f"m-{seed}" if scenario is None else f"m-{seed}-{scenario.name}"
        # Senaryo modunda skor yalnızca zorunlu olaylardan gelir.
        self.natural_goals = scenario is None
        overrides = (scenario.turnover_factor if scenario else None) or {}
        self.turnover_factor = {s: overrides.get(s, 1.0) for s in SIDES}
        tempo = (scenario.tempo if scenario else None) or {}
        self.tempo = {s: tempo.get(s, 1.0) for s in SIDES}
        # sorted kararlıdır: aynı dakikadaki olaylar tanım sırasını korur.
        self.forced: list[ForcedEvent] = (
            sorted(scenario.forced, key=lambda f: f.minute) if scenario else []
        )
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
                "scenario": self.scenario.name if self.scenario else None,
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
            step = self.rng.randint(2, 20)
            due = self._next_forced_at()
            if due is not None and due <= self.clock + step:
                # Zorunlu olay tam dakikasında; saat zaten geçtiyse (gol kutlaması) hemen.
                self.clock = max(self.clock, due)
                self._run_due_subs(subs)
                self._run_forced(self.forced.pop(0))
                continue
            self.clock += step
            if self.clock >= self.period_end:
                break
            self._run_due_subs(subs)
            self._play_step()
        self.clock = max(self.clock, self.period_end)
        end_type = EventType.HALF_TIME if period == 1 else EventType.FULL_TIME
        self._emit(end_type, at_ball=False)

    def _next_forced_at(self) -> int | None:
        if self.forced and self.forced[0].period == self.period:
            return self.forced[0].minute * 60
        return None

    def _run_forced(self, f: ForcedEvent) -> None:
        side = f.team
        if f.kind == "goal":
            self._give_ball(side, 0.9, self.rng.uniform(24.0, 44.0))
            player = self._attacker()
            self._emit(EventType.SHOT, side, player, outcome="goal")
            self._score_goal(side, player)
        elif f.kind == "red_card":
            if self.possession == side:
                self._turnover()
            offender = self.rng.choice(self.teams[side].outfield())
            self._emit(EventType.FOUL, side, offender)
            self._send_off(side, offender, "straight_red")
        else:  # penalty
            defending = _other(side)
            self._give_ball(side, 0.9, self.rng.uniform(20.0, 48.0))
            self._emit(EventType.FOUL, defending, self.rng.choice(self.teams[defending].outfield()))
            self._penalty(side, f.outcome)

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

    def _keeps_ball(self, side: str, base_success: float) -> bool:
        missing = LINEUP_SIZE - len(self.teams[side].on_pitch)
        fail = (1.0 - base_success) * self.turnover_factor[side] + TURNOVER_PER_MISSING * missing
        return self.rng.random() >= fail

    def _pass(self) -> None:
        side, player = self.possession, self._attacker()
        if self._keeps_ball(side, PASS_SUCCESS):
            self._emit(EventType.PASS, side, player, outcome="success")
            delta = self.rng.uniform(-0.04, 0.10) * self.tempo[side]
            self.progress = _clamp(self.progress + delta, 0.02, 0.98)
            self._walk_y()
        else:
            self._emit(EventType.PASS, side, player, outcome="fail")
            self._turnover()

    def _dribble(self) -> None:
        side, player = self.possession, self._attacker()
        if self._keeps_ball(side, DRIBBLE_SUCCESS):
            self._emit(EventType.DRIBBLE, side, player, outcome="success")
            delta = self.rng.uniform(0.02, 0.10) * self.tempo[side]
            self.progress = _clamp(self.progress + delta, 0.02, 0.98)
            self._walk_y()
        else:
            self._emit(EventType.DRIBBLE, side, player, outcome="fail")
            self._turnover()

    def _shot(self) -> None:
        side, player = self.possession, self._attacker()
        defending = _other(side)
        goal_prob = 0.04 + 0.14 * _clamp((self.progress - 0.6) / 0.4, 0.0, 1.0)
        r = self.rng.random()
        if r < goal_prob and self.natural_goals:
            self._emit(EventType.SHOT, side, player, outcome="goal")
            self._score_goal(side, player)
        elif r < goal_prob + 0.30:  # doğal goller kapalıysa gol şutu kurtarışa döner
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

    def _score_goal(self, side: str, player: str) -> None:
        # Çağıran topu `side` takımına vermiş olmalı (gol koordinatı için).
        self.score[side] += 1
        self.progress, self.y = 1.0, PITCH_WIDTH / 2
        self._emit(EventType.GOAL, side, player)
        self.clock += self.rng.randint(30, 75)
        if self.clock < self.period_end:
            self._kickoff(_other(side))

    def _penalty(self, side: str, outcome: str | None = None) -> None:
        """`side` penaltıyı kullanır. outcome verilmezse doğal sonuç çekilir."""
        defending = _other(side)
        self._give_ball(side, PENALTY_SPOT, PITCH_WIDTH / 2)
        taker = self._attacker()
        if outcome is None:
            r = self.rng.random()
            outcome = "scored" if r < 0.76 else ("saved" if r < 0.92 else "missed")
            if outcome == "scored" and not self.natural_goals:
                outcome = "saved"
        self._emit(EventType.PENALTY, side, taker, outcome=outcome)
        if outcome == "scored":
            self._score_goal(side, taker)
        elif outcome == "saved":
            self._give_ball(defending, 0.03, PITCH_WIDTH / 2)
            self._emit(EventType.SAVE, defending, self.teams[defending].goalkeeper())
        else:
            self._give_ball(defending, 0.05, PITCH_WIDTH / 2)

    def _corner(self, side: str) -> None:
        self._give_ball(side, 1.0, self.rng.choice((0.0, PITCH_WIDTH)))
        self._emit(EventType.CORNER, side, self._attacker())
        self._give_ball(side, 0.9, self.rng.uniform(20.0, 48.0))

    def _foul(self) -> None:
        attacking = self.possession
        defending = _other(attacking)
        team = self.teams[defending]
        offender = self.rng.choice(team.outfield())
        self._emit(EventType.FOUL, defending, offender)
        if len(team.on_pitch) > MIN_PLAYERS:
            self._maybe_card(defending, offender)
        if self.progress > BOX_PROGRESS and self.rng.random() < PENALTY_FROM_BOX_FOUL:
            self._penalty(attacking)
        # Aksi halde top hücum eden takımda kalır (serbest vuruş).

    def _maybe_card(self, side: str, offender: str) -> None:
        team = self.teams[side]
        booked = offender in team.booked
        yellow_prob = YELLOW_PROB * (BOOKED_CAUTION if booked else 1.0)
        r = self.rng.random()
        if r < STRAIGHT_RED_PROB:
            self._send_off(side, offender, "straight_red")
        elif r < STRAIGHT_RED_PROB + yellow_prob:
            self._emit(EventType.YELLOW_CARD, side, offender, at_ball=False)
            if booked:
                self._send_off(side, offender, "second_yellow")
            else:
                team.booked.append(offender)

    def _send_off(self, side: str, player: str, reason: str) -> None:
        self._emit(EventType.RED_CARD, side, player, at_ball=False, data={"reason": reason})
        self.teams[side].on_pitch.remove(player)

    def _offside(self) -> None:
        self._emit(EventType.OFFSIDE, self.possession, self._attacker())
        self._turnover()


def generate_match(seed: int, scenario: str | Scenario | None = None) -> list[Event]:
    """Verilen seed (ve isteğe bağlı senaryo) için tam bir maçın olay akışını üretir."""
    if isinstance(scenario, str):
        if scenario not in SCENARIOS:
            choices = ", ".join(sorted(SCENARIOS))
            raise ValueError(f"Bilinmeyen senaryo: {scenario!r} (seçenekler: {choices})")
        scenario = SCENARIOS[scenario]
    return _Match(seed, scenario).run()
