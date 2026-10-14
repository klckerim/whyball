"""Slot-based narration: the model writes placeholders, never concrete values.

Team and player names, minutes, the score, event phrases and metric values are produced
by code from verified claims, the event data and the match state at the moment of the event.
A template that keeps a digit, number word, name, raw home/away label or raw metric name
outside a placeholder is rejected; so is a placeholder that cannot be bound.
foundry-v4 rules (config `slot_*` flags): event type / role words, a disallowed sentence
start, number words regardless of context and qualitative overstatement the moment type
does not support are rejected too (see phrases.py). foundry-v4.1: {event:} for an event type
the moment type does not allow, a {player:} that names the event's player again in the same
sentence, and the article "the" before a team placeholder are rejected as well.

Placeholders:
  {home} {away}          team name
  {score}                score at the moment of the event, "1–2" (home–away order, no team names)
  {score_named}          the same score with team names, "Home 1–2 Away"
  {event:<event id>}     the event's standard phrase ("X was sent off at 63'"); the event must be evidence of a claim
  {player:<id>}          player (squad id: h01…, a01…); must be the subject of a claim
  {minute:<claim_id>}    the claim's end minute; {start:<claim_id>} its start minute
  {value:<claim_id>}     the claim's verified value (formatted by metric)
  {label:<claim_id>}     readable name of the claim's metric (agrees with the number if the same
                         claim's {value:} comes right before it: "1 shot", "2 shots")
  {clause:<clause_id>}   claim menu only (foundry-v5, menu.py): a clause written by code
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.analytics.moments import Moment
from app.generator.models import Event

from .claims import KICKOFF, Claim, MatchTime, Subject, VerificationResult, measure
from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from .labels import METRIC_LABELS, metric_label
from .phrases import (
    event_phrase,
    event_word_spans,
    first_word,
    overstatement_spans,
    selectable,
    sentence_starts,
)
from .template_narrator import Part, coalesce, fmt_minute
from .text_lint import LintIssue, LintResult, Roster, _capitalized_groups, _is_sentence_start, _number_words

SIDES = ("home", "away")
SIMPLE_SLOTS = ("home", "away", "score", "score_named")
ARG_SLOTS = ("player", "minute", "start", "value", "label", "event", "clause")
PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")
SLOT_ARG_RE = re.compile(r"[A-Za-z0-9_\-]+")
EVENT_ARG_RE = re.compile(r"[A-Za-z0-9_\-]+#\d+")
SCORE_IDS = {"home": "score_home", "away": "score_away"}

SIDE_LABEL_RE = {
    "en": re.compile(r"(?<!\w)(?:home|away)(?!\w)", re.IGNORECASE),
}
METRIC_NAME_RE = re.compile(r"(?<![\w{])[a-z]+(?:_[a-z]+)+(?!\w)")
DIGIT_RE = re.compile(r"\d+(?:[.,]\d+)?")
# Clauses start with their own subject / article ("the score is …", "{home} have had …").
ARTICLE_TEAM_RE = re.compile(r"(?<!\w)the\s+\{(?:home|away|score_named|clause:[^{}]*)\}", re.IGNORECASE)


def player_ids(events: Sequence[Event]) -> dict[str, str]:
    """Squad ids → name: home h01…, away a01… (first 11, then substitutes in order)."""
    teams = events[0].data["teams"]
    out = {}
    for side, prefix in (("home", "h"), ("away", "a")):
        for i, name in enumerate([*teams[side]["lineup"], *teams[side]["bench"]], start=1):
            out[f"{prefix}{i:02d}"] = name
    return out


@dataclass(frozen=True)
class Placeholder:
    kind: str
    arg: str | None
    start: int
    end: int

    @property
    def raw(self) -> str:
        return "{" + self.kind + (f":{self.arg}" if self.arg is not None else "") + "}"


@dataclass(frozen=True)
class SlotContext:
    events: Sequence[Event]
    language: str
    teams: dict[str, str]
    players: dict[str, str]  # id → name
    moment_time: MatchTime
    anchor_ref: str
    roster: Roster = field(repr=False)
    moment_type: str = ""

    @classmethod
    def from_moment(cls, moment: Moment, events: Sequence[Event], language: str) -> SlotContext:
        teams = events[0].data["teams"]
        return cls(
            events=events,
            language=language,
            teams={side: teams[side]["name"] for side in SIDES},
            players=player_ids(events),
            moment_time=MatchTime(moment.period, moment.minute, moment.second),
            anchor_ref=f"{events[0].match_id}#{moment.at_seq}",
            roster=Roster.from_events(events),
            moment_type=moment.type,
        )

    def event(self, ref: str) -> Event | None:
        match_id, _, seq = ref.rpartition("#")
        if match_id != self.events[0].match_id or not seq.isdigit():
            return None
        by_seq = {e.seq: e for e in self.events}
        return by_seq.get(int(seq))

    def phrase(self, ref: str) -> str | None:
        e = self.event(ref)
        return event_phrase(e, self.teams, self.language) if e is not None else None


def parse_placeholders(template: str) -> tuple[list[Placeholder], list[LintIssue]]:
    found, issues = [], []
    for m in PLACEHOLDER_RE.finditer(template):
        kind, sep, arg = m.group(1).partition(":")
        arg_re = EVENT_ARG_RE if kind == "event" else SLOT_ARG_RE
        if (kind in SIMPLE_SLOTS and not sep) or (
            kind in ARG_SLOTS and sep and arg_re.fullmatch(arg)
        ):
            found.append(Placeholder(kind, arg if sep else None, m.start(), m.end()))
        else:
            issues.append(LintIssue("unknown_placeholder", m.group(), m.start(), m.end(), "placeholder"))
    stripped = PLACEHOLDER_RE.sub(lambda m: " " * len(m.group()), template)
    for m in re.finditer(r"[{}]", stripped):
        issues.append(LintIssue("unknown_placeholder", m.group(), m.start(), m.end(), "placeholder"))
    return found, issues


def bind_template(
    template: str, claims: Sequence[Claim], claim_ids: Sequence[str], ctx: SlotContext
) -> tuple[tuple[Claim, ...], tuple[str, ...], list[LintIssue]]:
    """Binds placeholders to claims; adds the score claims at the moment of the event for {score}/{score_named}.

    {event:<id>} can only be one of the claims' evidence events.
    """
    placeholders, issues = parse_placeholders(template)
    ids = list(claim_ids)
    if len(ids) != len(claims):
        issues.append(LintIssue("claim_id_mismatch", "", 0, 0, "placeholder"))
        ids = (ids + [f"_{i}" for i in range(len(claims))])[: len(claims)]
    for cid in sorted({c for c in ids if ids.count(c) > 1}):
        issues.append(LintIssue("duplicate_claim_id", cid, 0, 0, "placeholder"))
    by_id = dict(zip(ids, claims))
    subjects = {c.subject.player for c in claims if c.subject.player}
    evidence = {ref for c in claims for ref in c.event_ids}

    for ph in placeholders:
        if ph.kind == "event":
            if ctx.event(ph.arg) is None:
                bound = False
            elif ctx.phrase(ph.arg) is None:
                issues.append(LintIssue("unsupported_event", ph.raw, ph.start, ph.end, "placeholder"))
                continue
            elif ph.arg not in evidence:
                issues.append(LintIssue("event_not_evidence", ph.raw, ph.start, ph.end, "placeholder"))
                continue
            else:
                bound = True
        elif ph.kind == "player":
            name = ctx.players.get(ph.arg)
            bound = name is not None and name in subjects
        elif ph.kind in ("minute", "start", "value", "label"):
            bound = ph.arg in by_id
        elif ph.kind == "clause":
            bound = False  # clauses only exist in menu drafts (menu.bind_menu)
        else:
            bound = True
        if not bound:
            issues.append(LintIssue("unbound_placeholder", ph.raw, ph.start, ph.end, "placeholder"))

    out_claims, out_ids = list(claims), ids
    if any(ph.kind in ("score", "score_named") for ph in placeholders):
        for side in SIDES:
            if SCORE_IDS[side] in by_id:
                continue
            value = measure("score", Subject(side), KICKOFF, ctx.moment_time, ctx.events).value
            out_claims.append(Claim(
                "state", Subject(side), "score", "eq", value, KICKOFF, ctx.moment_time, (ctx.anchor_ref,)
            ))
            out_ids = [*out_ids, SCORE_IDS[side]]
    return tuple(out_claims), tuple(out_ids), issues


def _mask_placeholders(template: str, char: str = "x") -> str:
    # Mask with a lowercase word: keeps sentence-start / capital detection intact and hides id digits.
    return PLACEHOLDER_RE.sub(lambda m: char * len(m.group()), template)


def allowed_sentence_starts(language: str | None, config: ExplainConfig) -> frozenset[str]:
    by_lang = {"en": config.sentence_start_allowed_en}
    words = by_lang[language] if language in by_lang else [w for ws in by_lang.values() for w in ws]
    return frozenset(w.casefold() for w in words)


def template_sentence_starts(template: str) -> list[tuple[int, bool]]:
    """Sentence starts in the template: (position, whether it starts with a placeholder)."""
    upper = _mask_placeholders(template, "X")
    spans = [(m.start(), m.end()) for m in PLACEHOLDER_RE.finditer(template)]
    return [(pos, any(s <= pos < e for s, e in spans)) for pos in sentence_starts(upper)]


def sentence_start_issues(
    template: str, language: str | None, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> list[LintIssue]:
    """Reject when the first word of a sentence is neither a placeholder nor on the allowed start list."""
    allowed = allowed_sentence_starts(language, config)
    upper = _mask_placeholders(template, "X")
    spans = [(m.start(), m.end()) for m in PLACEHOLDER_RE.finditer(template)]
    issues = []
    for pos, is_placeholder in template_sentence_starts(template):
        if is_placeholder:
            continue
        found = first_word(upper, pos)
        if found is None:
            continue
        start, end, word = found
        if any(s <= start < e for s, e in spans) or word.casefold() in allowed:
            continue
        issues.append(LintIssue("sentence_start", template[start:end], start, end, "name"))
    return issues


def template_sentences(template: str) -> list[tuple[int, int]]:
    """Sentence spans of the template (start, end)."""
    starts = sorted({0, *(pos for pos, _ in template_sentence_starts(template))})
    return list(zip(starts, [*starts[1:], len(template)]))


def _event_players(e: Event, players: dict[str, str]) -> set[str]:
    """Squad ids of the players named in the event's phrase (the player coming on included)."""
    names = {e.player, (e.data or {}).get("player_in")} - {None}
    return {pid for pid, name in players.items() if name in names}


def event_type_issues(template: str, ctx: SlotContext) -> list[LintIssue]:
    """The {event:} event must be of a type the moment type allows (not a pass, dribble, offside…)."""
    issues = []
    for ph in parse_placeholders(template)[0]:
        if ph.kind != "event":
            continue
        e = ctx.event(ph.arg)
        if e is not None and not selectable(e, ctx.moment_type):
            issues.append(LintIssue("event_type_not_allowed", ph.raw, ph.start, ph.end, "placeholder"))
    return issues


def player_repeat_issues(template: str, ctx: SlotContext) -> list[LintIssue]:
    """If {event:X} already names the player in the same sentence, a {player:} for that player is a repeat."""
    placeholders = parse_placeholders(template)[0]
    issues = []
    for start, end in template_sentences(template):
        inside = [ph for ph in placeholders if start <= ph.start < end]
        named: set[str] = set()
        for ph in inside:
            e = ctx.event(ph.arg) if ph.kind == "event" else None
            if e is not None:
                named |= _event_players(e, ctx.players)
        issues += [
            LintIssue("player_repeat", ph.raw, ph.start, ph.end, "placeholder")
            for ph in inside if ph.kind == "player" and ph.arg in named
        ]
    return issues


def article_team_issues(template: str) -> list[LintIssue]:
    """Team names and clauses are written without an article: "The {home}", "the {score_named}", "The {clause:score}"."""
    return [LintIssue("article_team", m.group(), m.start(), m.end(), "name")
            for m in ARTICLE_TEAM_RE.finditer(template)]


def lint_template(
    template: str, ctx: SlotContext, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> LintResult:
    """No digit, number word, name, home/away or raw metric name may remain outside placeholders."""
    issues: list[LintIssue] = []
    masked = list(_mask_placeholders(template))
    for m in ctx.roster.pattern.finditer("".join(masked)):
        issues.append(LintIssue("raw_entity", template[m.start():m.end()], m.start(), m.end(), "name"))
        masked[m.start():m.end()] = "x" * (m.end() - m.start())
    text = "".join(masked)

    allowed = set(config.lint_allowed_capitalized)
    for start, end, words in _capitalized_groups(text):
        if all(w in allowed for w in words):
            continue
        if len(words) == 1 and _is_sentence_start(text, start):
            continue
        issues.append(LintIssue("raw_entity", template[start:end], start, end, "name"))

    for m in DIGIT_RE.finditer(text):
        issues.append(LintIssue("raw_number", template[m.start():m.end()], m.start(), m.end(), "integer"))
    for start, end, _ in _number_words(text, ctx.language, strict=config.slot_strict_number_words):
        issues.append(LintIssue("raw_number", template[start:end], start, end, "word"))

    if config.slot_event_words:
        for start, end in event_word_spans(text, ctx.language):
            issues.append(LintIssue("event_word", template[start:end], start, end, "label"))
    if config.slot_overstatement:
        for start, end in overstatement_spans(text, ctx.language, ctx.moment_type):
            issues.append(LintIssue("overstatement", template[start:end], start, end, "label"))
    if config.slot_sentence_start:
        issues += sentence_start_issues(template, ctx.language, config)
    if config.slot_event_type_allowlist:
        issues += event_type_issues(template, ctx)
    if config.slot_player_repeat:
        issues += player_repeat_issues(template, ctx)
    if config.slot_article_team:
        issues += article_team_issues(template)

    side_res = [SIDE_LABEL_RE[ctx.language]] if ctx.language in SIDE_LABEL_RE else list(SIDE_LABEL_RE.values())
    for pattern in side_res:
        for m in pattern.finditer(text):
            issues.append(LintIssue("raw_side_label", template[m.start():m.end()], m.start(), m.end(), "label"))
    for m in METRIC_NAME_RE.finditer(text):
        issues.append(LintIssue("raw_metric_name", template[m.start():m.end()], m.start(), m.end(), "label"))
    return LintResult(tuple(sorted(issues, key=lambda i: (i.start, i.code))))


def format_value(metric: str, value: float, language: str) -> str:
    if metric in ("possession", "field_tilt"):
        pct = round(value * 100)
        return f"{pct}%"
    if metric == "pressure_balance":
        return f"{value:+.2f}"
    if metric == "min_score_margin":
        return str(abs(round(value)))
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def render(
    template: str,
    claims: Sequence[Claim],
    claim_ids: Sequence[str],
    verdicts: Sequence[VerificationResult],
    ctx: SlotContext,
    clauses: dict[str, str] | None = None,
) -> str:
    """Final text from a bound and verified template. `clauses`: menu clauses (id → template)."""
    return "".join(p.text for p in render_parts(template, claims, claim_ids, verdicts, ctx, clauses))


def render_parts(
    template: str,
    claims: Sequence[Claim],
    claim_ids: Sequence[str],
    verdicts: Sequence[VerificationResult],
    ctx: SlotContext,
    clauses: dict[str, str] | None = None,
) -> tuple[Part, ...]:
    """The rendered text in pieces. A piece with a `claim` index is the value of that claim ({value:} and the two
    numbers of {score} / {score_named}); everything else (names, minutes, labels, event phrases) is plain text.
    The code that fills each placeholder knows where its text goes, so nothing is matched afterwards."""
    index = {cid: i for i, cid in enumerate(claim_ids)}
    by_id = {cid: (c, v) for cid, c, v in zip(claim_ids, claims, verdicts)}
    starts = {pos for pos, is_placeholder in template_sentence_starts(template) if is_placeholder}

    def verified(cid: str) -> float:
        claim, verdict = by_id[cid]
        return verdict.actual if verdict.actual is not None else claim.value

    def capitalized(parts: list[Part]) -> list[Part]:
        for i, p in enumerate(parts):
            if p.text:
                if p.text[0].islower():
                    parts[i] = Part(p.text[0].upper() + p.text[1:], p.claim)
                break
        return parts

    def score(side: str) -> Part:
        return Part(format_value("score", verified(SCORE_IDS[side]), ctx.language), index[SCORE_IDS[side]])

    def fill(m: re.Match[str]) -> list[Part]:
        kind, _, arg = m.group(1).partition(":")
        if kind in SIDES:
            return [Part(ctx.teams[kind])]
        if kind == "score":
            return [score("home"), Part("–"), score("away")]
        if kind == "score_named":
            return [Part(f"{ctx.teams['home']} "), score("home"), Part("–"), score("away"),
                    Part(f" {ctx.teams['away']}")]
        if kind == "player":
            return [Part(ctx.players[arg])]
        if kind == "event":
            return [Part(ctx.phrase(arg) or "")]
        if kind == "clause":
            return list(render_parts((clauses or {})[arg], claims, claim_ids, verdicts, ctx, clauses))
        claim, _ = by_id[arg]
        if kind == "minute":
            return [Part(fmt_minute(claim.end.period, claim.end.minute))]
        if kind == "start":
            return [Part(fmt_minute(claim.start.period, claim.start.minute))]
        if kind == "label":
            counted = template[:m.start()].endswith("{value:" + arg + "} ")
            return [Part(metric_label(claim.metric, ctx.language, verified(arg) if counted else None))]
        return [Part(format_value(claim.metric, verified(arg), ctx.language), index[arg])]  # {value:}

    out: list[Part] = []
    last = 0
    for m in PLACEHOLDER_RE.finditer(template):
        out.append(Part(template[last:m.start()]))
        filled = fill(m)
        out += capitalized(filled) if m.start() in starts else filled
        last = m.end()
    out.append(Part(template[last:]))
    return coalesce(out)
