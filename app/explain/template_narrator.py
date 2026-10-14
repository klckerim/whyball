"""Template narrator: produces typed claims and EN plain text from a moment.

It is the LLM narrator's fallback. Every concrete statement in the text rests on a
claim; a sentence whose claim does not verify is never published (``Narration.published``).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.analytics.config import DEFAULT_CONFIG as ANALYTICS_CONFIG
from app.analytics.metrics import MatchTracker, other, stated
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
class Part:
    """A piece of a sentence. `claim` is the index of the claim whose value the piece states (None: plain text)."""

    text: str
    claim: int | None = None


def coalesce(parts: Sequence[Part]) -> tuple[Part, ...]:
    """Drops empty pieces and joins neighbouring plain pieces."""
    out: list[Part] = []
    for p in parts:
        if not p.text:
            continue
        if out and out[-1].claim is None and p.claim is None:
            out[-1] = Part(out[-1].text + p.text)
        else:
            out.append(p)
    return tuple(out)


@dataclass(frozen=True)
class Sentence:
    text: dict[str, str]  # language → text
    claims: tuple[Claim, ...]
    # English pieces with the claim values marked, written by the code that wrote the text (no matching).
    # Empty: the sentence states no claim value in numbers.
    parts: tuple[Part, ...] = ()

    def __post_init__(self) -> None:
        if self.parts:
            assert "".join(p.text for p in self.parts) == self.text["en"], "parts differ from the sentence"
            assert all(p.claim is None or 0 <= p.claim < len(self.claims) for p in self.parts)

    def pieces(self, language: str) -> tuple[Part, ...]:
        """Parts of the sentence; plain text when it has none (or the language has no parts)."""
        if self.parts and language == "en":
            return self.parts
        return (Part(self.text[language]),)


def join_sentences(
    sentences: Sequence[Sentence], language: str
) -> tuple[str, tuple[Claim, ...], tuple[Part, ...]]:
    """Text (sentences joined by a space), claims and parts; part claim indices are offset into the joined claims."""
    parts: list[Part] = []
    claims: list[Claim] = []
    for i, s in enumerate(sentences):
        if i:
            parts.append(Part(" "))
        parts += [Part(p.text, None if p.claim is None else p.claim + len(claims)) for p in s.pieces(language)]
        claims += s.claims
    return " ".join(s.text[language] for s in sentences), tuple(claims), coalesce(parts)


def sentence(claims: Sequence[Claim], *pieces: str | tuple[str, Claim]) -> Sentence:
    """A sentence from plain strings and (value text, claim) pairs; the claim is found by identity."""
    parts = tuple(
        Part(p) if isinstance(p, str) else Part(p[0], next(i for i, c in enumerate(claims) if c is p[1]))
        for p in pieces
    )
    return Sentence({"en": "".join(p.text for p in parts)}, tuple(claims), coalesce(parts))


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

    def detector_window(self, minutes: float) -> MatchTime:
        """Inclusive start of the detector's window ending at the moment (played minutes, so in the second half
        it can start in the first): claims over it count the same events as the moment detail."""
        tracker = MatchTracker(ANALYTICS_CONFIG)
        for e in self.events[: self.m.at_seq + 1]:
            tracker.update(e)
        return MatchTime(*tracker.window_start(minutes))

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
        ch = self.state("score", "home", "eq", h, evidence)
        ca = self.state("score", "away", "eq", a, evidence)
        return sentence((ch, ca), f"{home} ", (f"{h:g}", ch), "–", (f"{a:g}", ca), f" {away}.")


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
        _down_to(c, team, side, left, team_reds),
    ]


def _down_to(c: _Context, team: str, side: str, left: float, team_reds: Sequence[int]) -> Sentence:
    claim = c.state("players_on_pitch", side, "eq", left, team_reds)
    return sentence((claim,), f"{team} are down to ", (f"{left:g}", claim), " players.")


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
    """Sub-label sentence of a goal that changed the match state (the minute is in the goal sentence)."""
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
    if change.get("from_behind"):
        # from_behind (detector): the team trailed at some earlier point; the score before this goal was level.
        deficit = change["max_deficit"]
        conceded = measure("goals", Subject(other(side)), KICKOFF, c.t, c.events).counted
        claims += (c.state("min_score_margin", side, "eq", -deficit, conceded),)
        text = {"en": f"{team} come from behind to take the lead, having trailed by {deficit} "
                      f"goal{'s' if deficit > 1 else ''} earlier in the match."}
    return [Sentence(text, claims)]


def _pressure_shift(c: _Context) -> list[Sentence]:
    side = c.m.team
    team, opp = c.names[side], c.names[other(side)]
    balance = stated(c.measured("pressure_balance", side))
    start = _since(c.t, c.config.context_minutes)
    shots = c.count("shots", Subject(side), start)
    opp_shots = c.count("shots", Subject(other(side)), start)
    pressure = c.state("pressure_balance", side, "approx", balance, c.m.event_ids)
    return [
        sentence(
            (pressure,),
            f"{c.minute} — {team} take control: {metric_label('pressure_balance', 'en')} is ",
            (f"{balance:+.2f}", pressure),
            " in their favour.",
        ),
        sentence(
            (shots, opp_shots),
            f"Shots since {start.minute}': {team} ", (f"{shots.value:g}", shots),
            f", {opp} ", (f"{opp_shots.value:g}", opp_shots), ".",
        ),
    ]


def _dominance(c: _Context) -> list[Sentence]:
    side = c.m.team
    team = c.names[side]
    home, away = c.names["home"], c.names["away"]
    start = c.detector_window(ANALYTICS_CONFIG.dominance_window_min)
    pct = round(stated(c.measured("possession", side, start)) * 100)
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
    poss, home_score, away_score = claims[0], claims[3], claims[4]
    return [
        sentence(
            claims,
            f"{c.minute} — {team} dominate without reward: since {fmt_minute(start.period, start.minute)} "
            "they have had ",
            (f"{pct}%", poss), " of the ball and a ", (f"{s:g}", shots), "–", (f"{o:g}", opp_shots),
            " lead in shots, yet the score is ",
            f"{home} ", (f"{h:g}", home_score), "–", (f"{a:g}", away_score), f" {away}.",
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
