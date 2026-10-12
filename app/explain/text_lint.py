"""Anlatı metni denetimi: her sayı ve her isim bir iddiada geçmeli.

İsimler maç kadrosundan (match_meta) tanınır. Kadroda olmayan, isim gibi
görünen büyük harfli kelime grupları uydurma isim sayılır. Sayılar türüne
göre (dakika, yüzde, ondalık, tamsayı) iddiaların değer ve aralıklarıyla
eşleştirilir.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from app.generator.models import Event

from .claims import Claim
from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig

NUMBER_RE = re.compile(
    r"(?P<trmin>\d{1,3})\.\s*dakika"  # TR: "46. dakikadan"
    r"|(?P<min>\d{1,3})(?:\+(?P<extra>\d{1,2}))?'"  # "22'", "45+1'"
    r"|%(?P<pct1>\d{1,3})(?![\d.])"  # TR: "%58"
    r"|(?P<pct2>\d{1,3})%"  # EN: "58%"
    r"|(?P<dec>[+-]?\d+\.\d+)"
    r"|(?P<int>\d+)"
)
WORD_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
SENTENCE_BREAKS = ".!?:—–\"("


@dataclass(frozen=True)
class LintIssue:
    code: str  # unsupported_number | unsupported_name | unknown_name
    fragment: str
    start: int
    end: int
    kind: str  # minute | percent | decimal | integer | name

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
    key: str  # takım için taraf, oyuncu için tam ad


class Roster:
    """Maçtaki takım ve oyuncu adları ile takma adları (şehir, soyad)."""

    def __init__(self, teams: dict[str, str], players: Sequence[str]) -> None:
        self.aliases: dict[str, set[Entity]] = {}
        for side, name in teams.items():
            entity = Entity("team", side)
            self._add(name, entity)
            if " " in name:
                self._add(name.rsplit(" ", 1)[0], entity)  # şehir
        for name in players:
            entity = Entity("player", name)
            self._add(name, entity)
            self._add(name.rsplit(" ", 1)[-1], entity)  # soyad
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


def lint_text(
    text: str,
    claims: Sequence[Claim],
    roster: Roster,
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
) -> LintResult:
    issues: list[LintIssue] = []
    teams = {c.subject.team for c in claims if c.subject.team}
    players = {c.subject.player for c in claims if c.subject.player}

    # 1) Bilinen isimler: bir iddianın öznesi olmalı. Sonra maskelenir.
    masked = list(text)
    for m in roster.pattern.finditer(text):
        entities = roster.aliases[m.group()]
        if not any(
            (e.kind == "team" and e.key in teams) or (e.kind == "player" and e.key in players)
            for e in entities
        ):
            issues.append(LintIssue("unsupported_name", m.group(), m.start(), m.end(), "name"))
        masked[m.start() : m.end()] = " " * (m.end() - m.start())
    masked_text = "".join(masked)

    # 2) Kadroda olmayan isim benzeri kelimeler.
    allowed = set(config.lint_allowed_capitalized)
    for start, end, words in _capitalized_groups(masked_text):
        if all(w in allowed for w in words):
            continue
        if len(words) == 1 and _is_sentence_start(masked_text, start):
            continue
        issues.append(LintIssue("unknown_name", text[start:end], start, end, "name"))

    # 3) Sayılar.
    minutes = {c.start.minute for c in claims} | {c.end.minute for c in claims}
    values = [abs(float(c.value)) for c in claims]
    ratios = [float(c.value) for c in claims if c.kind == "ratio"]
    eps = config.float_epsilon
    for m in NUMBER_RE.finditer(masked_text):
        g = m.groupdict()
        if g["trmin"] is not None:
            kind, ok = "minute", int(g["trmin"]) in minutes
        elif g["min"] is not None:
            minute = int(g["min"]) + (int(g["extra"]) - 1 if g["extra"] else 0)
            kind, ok = "minute", minute in minutes
        elif g["pct1"] is not None or g["pct2"] is not None:
            p = int(g["pct1"] or g["pct2"])
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

    return LintResult(tuple(sorted(issues, key=lambda i: (i.start, i.code))))
