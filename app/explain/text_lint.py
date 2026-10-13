"""Narration text check: every number and every name must appear in a claim.

Names are recognised from the match squad (match_meta). Capitalized word groups that look
like names but are not in the squad count as made-up names. Numbers are matched against the
claims' values and ranges by kind (minute, percent, decimal, integer).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from app.generator.models import Event

from .claims import Claim
from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from .labels import window_phrase_spans
from .template_narrator import require_language

NUMBER_RE = re.compile(
    r"(?P<min>\d{1,3})(?:\+(?P<extra>\d{1,2}))?'"  # "22'", "45+1'"
    r"|(?P<pct>\d{1,3})%"  # "58%"
    r"|(?P<dec>[+-]?\d+\.\d+)"
    r"|(?P<int>\d+)"
)
WORD_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
SENTENCE_BREAKS = ".!?:—–\"("

# Numbers written as words (0-20). Index = value.
NUMBER_WORDS: dict[str, tuple[str, ...]] = {
    "en": (
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
        "eighteen", "nineteen", "twenty",
    ),
}
# Words also common outside numbers: a number only if a countable noun follows.
# EN "one" ("one of").
AMBIGUOUS_NUMBER_WORDS: dict[str, frozenset[str]] = {
    "en": frozenset({"one"}),
}
COUNT_NOUN_STEMS = (
    "goal", "shot", "corner", "player", "minute", "card", "penalt", "point", "save",
)
NEXT_WORD_RE = re.compile(r"\s+([^\W\d_]+)")


def _number_word_pattern(words: Sequence[str]) -> re.Pattern[str]:
    ordered = sorted(words, key=lambda w: (-len(w), w))
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(w) for w in ordered) + r")(?!\w)")


NUMBER_WORD_RE = {
    "en": _number_word_pattern(NUMBER_WORDS["en"]),
}
WORD_VALUES = {w: i for words in NUMBER_WORDS.values() for i, w in enumerate(words)}


@dataclass(frozen=True)
class LintIssue:
    code: str  # unsupported_number | unsupported_name | unknown_name | bare_surname | ... (slot lint)
    fragment: str
    start: int
    end: int
    kind: str  # minute | percent | decimal | integer | word | name

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LintResult:
    issues: tuple[LintIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "issues": [i.to_dict() for i in self.issues]}


@dataclass(frozen=True)
class Entity:
    kind: str  # "team" | "player"
    key: str  # side for a team, full name for a player


class Roster:
    """Team and player names in the match, with their aliases (city, surname)."""

    def __init__(self, teams: dict[str, str], players: Sequence[str]) -> None:
        self.aliases: dict[str, set[Entity]] = {}
        self.full_names = frozenset(players)
        for side, name in teams.items():
            entity = Entity("team", side)
            self._add(name, entity)
            if " " in name:
                self._add(name.rsplit(" ", 1)[0], entity)  # city
        for name in players:
            entity = Entity("player", name)
            self._add(name, entity)
            self._add(name.rsplit(" ", 1)[-1], entity)  # surname
        ordered = sorted(self.aliases, key=lambda a: (-len(a), a))
        self.pattern = re.compile(
            r"(?<!\w)(?:" + "|".join(re.escape(a) for a in ordered) + r")(?!\w)"
        )

    def _add(self, alias: str, entity: Entity) -> None:
        self.aliases.setdefault(alias, set()).add(entity)

    @classmethod
    def from_events(cls, events: Sequence[Event]) -> Roster:
        teams = events[0].data["teams"]
        players = [p for side in ("home", "away") for p in (*teams[side]["lineup"], *teams[side]["bench"])]
        return cls({side: teams[side]["name"] for side in ("home", "away")}, players)


def bare_surname_spans(text: str, roster: Roster) -> list[tuple[int, int]]:
    """Spans where a player is named by surname only, not the full name (team aliases excluded)."""
    out = []
    for m in roster.pattern.finditer(text):
        entities = roster.aliases[m.group()]
        if (
            m.group() not in roster.full_names
            and any(e.kind == "player" for e in entities)
            and not any(e.kind == "team" for e in entities)
        ):
            out.append((m.start(), m.end()))
    return out


def _is_sentence_start(text: str, pos: int) -> bool:
    before = text[:pos].rstrip()
    return not before or before[-1] in SENTENCE_BREAKS


def _capitalized_groups(text: str) -> list[tuple[int, int, list[str]]]:
    groups: list[tuple[int, int, list[str]]] = []
    for m in WORD_RE.finditer(text):
        word = m.group()
        if not word[0].isupper():
            continue
        if groups and text[groups[-1][1] : m.start()] == " ":
            start, _, words = groups[-1]
            groups[-1] = (start, m.end(), [*words, word])
        else:
            groups.append((m.start(), m.end(), [word]))
    return groups


def _number_words(text: str, language: str | None, strict: bool = False) -> list[tuple[int, int, int]]:
    """(start, end, value) — ambiguous words only before a countable noun.

    `strict`: regardless of context, every number word ("one of" included).
    """
    language = language or "en"
    scan = text.lower()
    ambiguous = frozenset() if strict else AMBIGUOUS_NUMBER_WORDS[language]
    found = []
    for m in NUMBER_WORD_RE[language].finditer(scan):
        word = m.group()
        if word in ambiguous:
            nxt = NEXT_WORD_RE.match(scan, m.end())
            if not nxt or not nxt.group(1).startswith(COUNT_NOUN_STEMS):
                continue
        found.append((m.start(), m.end(), WORD_VALUES[word]))
    return found


def lint_text(
    text: str,
    claims: Sequence[Claim],
    roster: Roster,
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
    language: str | None = None,
) -> LintResult:
    """`language`: None (unspecified) or "en"; any other language raises."""
    if language is not None:
        require_language(language)
    issues: list[LintIssue] = []
    teams = {c.subject.team for c in claims if c.subject.team}
    players = {c.subject.player for c in claims if c.subject.player}

    # 1) Known names: must be the subject of a claim; a player cannot be named by surname only
    # (the same surname can appear in both teams). Then they are masked.
    masked = list(text)
    bare = set(bare_surname_spans(text, roster))
    for m in roster.pattern.finditer(text):
        entities = roster.aliases[m.group()]
        if config.lint_bare_surname and (m.start(), m.end()) in bare:
            issues.append(LintIssue("bare_surname", m.group(), m.start(), m.end(), "name"))
        if not any(
            (e.kind == "team" and e.key in teams) or (e.kind == "player" and e.key in players)
            for e in entities
        ):
            issues.append(LintIssue("unsupported_name", m.group(), m.start(), m.end(), "name"))
        masked[m.start() : m.end()] = " " * (m.end() - m.start())
    # Fixed window phrases written by code ("over the last 10 minutes of play"): not claims.
    for start, end in window_phrase_spans(text):
        masked[start:end] = "x" * (end - start)
    masked_text = "".join(masked)

    # 2) Name-like words not in the squad.
    allowed = set(config.lint_allowed_capitalized)
    for start, end, words in _capitalized_groups(masked_text):
        if all(w in allowed for w in words):
            continue
        if len(words) == 1 and _is_sentence_start(masked_text, start):
            continue
        issues.append(LintIssue("unknown_name", text[start:end], start, end, "name"))

    # 3) Numbers.
    minutes = {c.start.minute for c in claims} | {c.end.minute for c in claims}
    values = [abs(float(c.value)) for c in claims]
    ratios = [float(c.value) for c in claims if c.kind == "ratio"]
    eps = config.float_epsilon
    for m in NUMBER_RE.finditer(masked_text):
        g = m.groupdict()
        if g["min"] is not None:
            minute = int(g["min"]) + (int(g["extra"]) - 1 if g["extra"] else 0)
            kind, ok = "minute", minute in minutes
        elif g["pct"] is not None:
            p = int(g["pct"])
            kind = "percent"
            ok = any(abs(v * 100 - p) <= config.lint_percent_tolerance + eps for v in ratios)
        elif g["dec"] is not None:
            d = abs(float(g["dec"]))
            kind = "decimal"
            ok = any(abs(v - d) <= config.approx_tolerance + eps for v in values)
        else:
            n = int(g["int"])
            kind, ok = "integer", any(v == n for v in values)
        if not ok:
            issues.append(LintIssue("unsupported_number", m.group(), m.start(), m.end(), kind))

    # 4) Number words (same rule as integers).
    if config.lint_number_words:
        for start, end, n in _number_words(masked_text, language):
            if not any(v == n for v in values):
                issues.append(LintIssue("unsupported_number", text[start:end], start, end, "word"))

    return LintResult(tuple(sorted(issues, key=lambda i: (i.start, i.code))))
