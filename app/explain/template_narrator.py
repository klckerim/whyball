"""Template narrator: produces typed claims and EN plain text from a moment.

It is the LLM narrator's fallback. Every concrete statement in the text rests on a
claim; a sentence whose claim does not verify is never published (``Narration.published``).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.analytics.metrics import other
from app.analytics.moments import Moment
from app.generator.models import Event

from .claims import (
    KICKOFF,
    Claim,
    MatchTime,
    Subject,
    VerificationResult,
    measure,
    verify_claim,
)
from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from .labels import metric_label

LANGS = ("en",)


def require_language(language: str | None) -> str:
    """EN is the only supported language; anything else is rejected with a clear error."""
    if language not in LANGS:
        raise ValueError(f"unsupported language {language!r}: only 'en' is supported")
    return language


@dataclass(frozen=True)
class Sentence:
    text: dict[str, str]  # language → text
    claims: tuple[Claim, ...]


@dataclass(frozen=True)
class Narration:
    moment_id: str
    moment_type: str
    sentences: tuple[Sentence, ...]
    results: tuple[tuple[VerificationResult, ...], ...]  # claim results per sentence

    def sentence_ok(self, i: int) -> bool:
        return all(r.ok for r in self.results[i])

    @property
    def all_verified(self) -> bool:
        return all(self.sentence_ok(i) for i in range(len(self.sentences)))

    def published(self, lang: str) -> str:
        """Only the sentences whose claims all verify."""
        return " ".join(
            s.text[lang] for i, s in enumerate(self.sentences) if self.sentence_ok(i)
        )


def build_narration(
    moment: Moment,
    sentences: Sequence[Sentence],
    events: Sequence[Event],
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
) -> Narration:
    results = tuple(tuple(verify_claim(c, events, config) for c in s.claims) for s in sentences)
    return Narration(moment.id, moment.type, tuple(sentences), results)


def fmt_minute(period: int, minute: int) -> str:
    if period == 1 and minute >= 45:
        return f"45+{minute - 44}'"
    if period == 2 and minute >= 90:
        return f"90+{minute - 89}'"
    return f"{minute}'"


def _since(t: MatchTime, minutes: int) -> MatchTime:
    floor = 0 if t.period == 1 else 45
    if t.minute - minutes >= floor:
        return MatchTime(t.period, t.minute - minutes, t.second)
    return MatchTime(t.period, floor, 0)


class _Context:
    def __init__(self, moment: Moment, events: Sequence[Event], config: ExplainConfig) -> None:
        self.m = moment
        self.events = events
        self.config = config
        self.match_id = events[0].match_id
        teams = events[0].data["teams"]
        self.names = {side: teams[side]["name"] for side in ("home", "away")}
        self.t = MatchTime(moment.period, moment.minute, moment.second)
        self.minute = fmt_minute(moment.period, moment.minute)

    def ref(self, seq: int) -> str:
        return f"{self.match_id}#{seq}"

    def count(self, metric: str, subject: Subject, start: MatchTime) -> Claim:
        """A count claim whose value and evidence are measured from the events."""
        m = measure(metric, subject, start, self.t, self.events)
        return Claim(
            "count", subject, metric, "eq", m.value, start, self.t,
            tuple(self.ref(s) for s in m.counted),
        )

    def state(self, metric: str, team: str, comparison: str, value: float,
              evidence: Sequence[int], start: MatchTime = KICKOFF) -> Claim:
        return Claim(
            "state", Subject(team), metric, comparison, value, start, self.t,
            tuple(self.ref(s) for s in evidence),
        )

    def measured(self, metric: str, team: str, start: MatchTime = KICKOFF) -> float:
        return measure(metric, Subject(team), start, self.t, self.events).value

    def score_sentence(self, evidence: Sequence[int]) -> Sentence:
        h = self.measured("score", "home")
        a = self.measured("score", "away")
        home, away = self.names["home"], self.names["away"]
        return Sentence(
            {"en": f"{home} {h:g}–{a:g} {away}."},
            (
                self.state("score", "home", "eq", h, evidence),
                self.state("score", "away", "eq", a, evidence),
            ),
        )


# --- sentences per moment type ------------------------------------------------


def _goal(c: _Context) -> list[Sentence]:
    side, player = c.m.team, c.m.detail["player"]
    team = c.names[side]
    goal_seq = c.m.event_ids[-1]
    scored = c.count("goals", Subject(side, player), c.t)
    sentences = [
        Sentence(
            {
                "en": f"{c.minute} — {player} scores for {team}.",
            },
            (scored,),
        ),
    ]
    change = c.m.detail.get("score_change")
    if change is not None:
        sentences += _score_change(c, change)
    return [*sentences, c.score_sentence([goal_seq])]


def _red_card(c: _Context) -> list[Sentence]:
    side, player = c.m.team, c.m.detail["player"]
    team = c.names[side]
    sent_off = c.count("red_cards", Subject(side, player), c.t)
    team_reds = measure("red_cards", Subject(side), KICKOFF, c.t, c.events).counted
    left = c.measured("players_on_pitch", side)
    return [
        Sentence(
            {
                "en": f"{c.minute} — {player} ({team}) is sent off.",
            },
            (sent_off,),
        ),
        Sentence(
            {
                "en": f"{team} are down to {left:g} players.",
            },
            (c.state("players_on_pitch", side, "eq", left, team_reds),),
        ),
    ]


_PENALTY_TEXT = {
    "scored": "{minute} — Penalty for {team}: {player} scores from the spot.",
    "saved": "{minute} — Penalty for {team}, but {player} sees the kick saved.",
    "missed": "{minute} — Penalty for {team}, but {player} misses.",
}


def _penalty(c: _Context) -> list[Sentence]:
    side, player, outcome = c.m.team, c.m.detail["player"], c.m.detail["outcome"]
    en = _PENALTY_TEXT[outcome]
    values = {"minute": c.minute, "team": c.names[side], "player": player}
    claim = c.count(f"penalties_{outcome}", Subject(side, player), c.t)
    return [Sentence({"en": en.format(**values)}, (claim,))]


def _score_change(c: _Context, change: dict) -> list[Sentence]:
    """Sub-label sentences of a goal that changed the match state (the minute is in the goal sentence)."""
    side = c.m.team
    team = c.names[side]
    goal_seq = c.m.event_ids[-1]
    kind = change["kind"]
    if kind == "opener":
        claims = (
            c.state("score", side, "eq", 1, [goal_seq]),
            c.state("score", other(side), "eq", 0, [goal_seq]),
        )
        text = {"en": f"{team} open the scoring."}
    else:
        # The goal itself is already counted in the goal sentence.
        margin = 0 if kind == "equalizer" else 1
        claims = (c.state("score_margin", side, "eq", margin, [goal_seq]),)
        text = (
            {"en": f"{team} draw level."}
            if kind == "equalizer"
            else {"en": f"{team} go ahead."}
        )
    sentences = [Sentence(text, claims)]

    if change.get("from_behind"):
        deficit = change["max_deficit"]
        conceded = measure("goals", Subject(other(side)), KICKOFF, c.t, c.events).counted
        sentences.append(
            Sentence(
                {
                    "en": f"They had been {deficit} goal{'s' if deficit > 1 else ''} down.",
                },
                (c.state("min_score_margin", side, "eq", -deficit, conceded),),
            )
        )
    return sentences


def _pressure_shift(c: _Context) -> list[Sentence]:
    side = c.m.team
    team, opp = c.names[side], c.names[other(side)]
    balance = round(c.measured("pressure_balance", side), 2)
    start = _since(c.t, c.config.context_minutes)
    shots = c.count("shots", Subject(side), start)
    opp_shots = c.count("shots", Subject(other(side)), start)
    return [
        Sentence(
            {
                "en": f"{c.minute} — {team} take control: {metric_label('pressure_balance', 'en')} "
                      f"is {balance:+.2f} in their favour.",
            },
            (c.state("pressure_balance", side, "approx", balance, c.m.event_ids),),
        ),
        Sentence(
            {
                "en": f"Shots since {start.minute}': {team} {shots.value:g}, {opp} {opp_shots.value:g}.",
            },
            (shots, opp_shots),
        ),
    ]


def _dominance(c: _Context) -> list[Sentence]:
    side = c.m.team
    team = c.names[side]
    home, away = c.names["home"], c.names["away"]
    start = _since(c.t, c.config.dominance_context_minutes)
    pct = round(c.measured("possession", side, start) * 100)
    shots = c.count("shots", Subject(side), start)
    opp_shots = c.count("shots", Subject(other(side)), start)
    h, a = c.measured("score", "home"), c.measured("score", "away")
    anchor = [c.m.at_seq]
    claims = (
        Claim("ratio", Subject(side), "possession", "approx", pct / 100, start, c.t, (c.ref(c.m.at_seq),)),
        shots,
        opp_shots,
        c.state("score", "home", "eq", h, anchor),
        c.state("score", "away", "eq", a, anchor),
        c.state("score_margin", side, "lte", 0, anchor),
    )
    s, o = shots.value, opp_shots.value
    # Possession and shots share one window; the window is written before both values so it binds to both.
    return [
        Sentence(
            {
                "en": f"{c.minute} — {team} dominate without reward: since {start.minute}' they have had "
                      f"{pct}% of the ball and a {s:g}–{o:g} lead in shots, yet the score is "
                      f"{home} {h:g}–{a:g} {away}.",
            },
            claims,
        )
    ]


BUILDERS: dict[str, Callable[[_Context], list[Sentence]]] = {
    "goal": _goal,
    "red_card": _red_card,
    "penalty": _penalty,
    "pressure_shift": _pressure_shift,
    "dominance_without_reward": _dominance,
}


def narrate(
    moment: Moment,
    events: Sequence[Event],
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
) -> Narration:
    sentences = BUILDERS[moment.type](_Context(moment, events, config))
    return build_narration(moment, sentences, events, config)
