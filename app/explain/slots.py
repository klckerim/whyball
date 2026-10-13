"""Slot tabanlı anlatı: model somut değer yazmaz, yer tutucu yazar.

Takım ve oyuncu adları, dakikalar, skor, olay ifadeleri ve metrik değerleri kod
tarafından doğrulanmış iddialardan, olay verisinden ve olay anındaki maç durumundan
üretilir. Şablonda yer tutucu dışında rakam, sayı kelimesi, isim, ham home/away
etiketi ya da ham metrik adı kalırsa reddedilir; bağlanamayan yer tutucu da
reddedilir. foundry-v4 kuralları (config `slot_*` bayrakları): olay tipi / rol
sözcükleri, izinsiz cümle başı, bağlamdan bağımsız yazıyla sayı ve moment tipinin
desteklemediği nitel abartı da reddedilir (bkz. phrases.py).

Yer tutucular:
  {home} {away}          takım adı
  {score}                olay anındaki skor, "1–2" (ev sahibi–deplasman sırası, takım adı yok)
  {score_named}          aynı skor takım adlarıyla, "Ev 1–2 Deplasman"
  {event:<olay id>}      olayın standart ifadesi ("X was sent off at 63'"); olay bir iddianın dayanağı olmalı
  {player:<id>}          oyuncu (kadro id'si: h01…, a01…); bir iddianın öznesi olmalı
  {minute:<claim_id>}    iddianın bitiş dakikası; {start:<claim_id>} başlangıç dakikası
  {value:<claim_id>}     iddianın doğrulanmış değeri (metriğe göre biçimli)
  {label:<claim_id>}     iddianın metriğinin okunur adı
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.analytics.moments import Moment
from app.generator.models import Event

from .claims import KICKOFF, Claim, MatchTime, Subject, VerificationResult, measure
from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from .phrases import event_phrase, event_word_spans, first_word, overstatement_spans, sentence_starts
from .template_narrator import fmt_minute
from .text_lint import LintIssue, LintResult, Roster, _capitalized_groups, _is_sentence_start, _number_words

SIDES = ("home", "away")
SIMPLE_SLOTS = ("home", "away", "score", "score_named")
ARG_SLOTS = ("player", "minute", "start", "value", "label", "event")
PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")
SLOT_ARG_RE = re.compile(r"[A-Za-z0-9_\-]+")
EVENT_ARG_RE = re.compile(r"[A-Za-z0-9_\-]+#\d+")
SCORE_IDS = {"home": "score_home", "away": "score_away"}

METRIC_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "goals": "goals", "shots": "shots", "shots_on_target": "shots on target",
        "corners": "corners", "fouls": "fouls", "yellow_cards": "yellow cards",
        "red_cards": "red cards", "penalties_scored": "penalties scored",
        "penalties_saved": "penalties saved", "penalties_missed": "penalties missed",
        "substitutions": "substitutions", "possession": "possession",
        "field_tilt": "territorial share", "score": "goals", "score_margin": "goal margin",
        "min_score_margin": "largest deficit", "players_on_pitch": "players on the pitch",
        "pressure_balance": "pressure balance",
    },
    "tr": {
        "goals": "gol", "shots": "şut", "shots_on_target": "isabetli şut",
        "corners": "korner", "fouls": "faul", "yellow_cards": "sarı kart",
        "red_cards": "kırmızı kart", "penalties_scored": "atılan penaltı",
        "penalties_saved": "kurtarılan penaltı", "penalties_missed": "kaçan penaltı",
        "substitutions": "oyuncu değişikliği", "possession": "topa sahip olma",
        "field_tilt": "saha üstünlüğü", "score": "gol", "score_margin": "gol farkı",
        "min_score_margin": "en büyük geri kalış farkı", "players_on_pitch": "sahadaki oyuncu",
        "pressure_balance": "baskı dengesi",
    },
}
SIDE_LABEL_RE = {
    "en": re.compile(r"(?<!\w)(?:home|away)(?!\w)", re.IGNORECASE),
    "tr": re.compile(r"(?<!\w)(?:ev sahibi|deplasman)", re.IGNORECASE),
}
METRIC_NAME_RE = re.compile(r"(?<![\w{])[a-z]+(?:_[a-z]+)+(?!\w)")
DIGIT_RE = re.compile(r"\d+(?:[.,]\d+)?")


def player_ids(events: Sequence[Event]) -> dict[str, str]:
    """Kadro id'leri → ad: ev sahibi h01…, deplasman a01… (ilk 11 + yedekler sırasıyla)."""
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
    players: dict[str, str]  # id → ad
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
    """Yer tutucuları iddialara bağlar; {score}/{score_named} için olay anındaki skor iddialarını ekler.

    {event:<id>} yalnızca iddiaların dayanak olaylarından biri olabilir.
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
    # Küçük harf kelimeyle maskeleme: cümle başı / büyük harf tespiti bozulmasın, id rakamları gizlensin.
    return PLACEHOLDER_RE.sub(lambda m: char * len(m.group()), template)


def allowed_sentence_starts(language: str | None, config: ExplainConfig) -> frozenset[str]:
    by_lang = {"en": config.sentence_start_allowed_en, "tr": config.sentence_start_allowed_tr}
    words = by_lang[language] if language in by_lang else [w for ws in by_lang.values() for w in ws]
    return frozenset(w.casefold() for w in words)


def template_sentence_starts(template: str) -> list[tuple[int, bool]]:
    """Şablondaki cümle başları: (konum, yer tutucuyla mı başlıyor)."""
    upper = _mask_placeholders(template, "X")
    spans = [(m.start(), m.end()) for m in PLACEHOLDER_RE.finditer(template)]
    return [(pos, any(s <= pos < e for s, e in spans)) for pos in sentence_starts(upper)]


def sentence_start_issues(
    template: str, language: str | None, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> list[LintIssue]:
    """Cümlenin ilk kelimesi yer tutucu ya da izinli başlangıç listesinde değilse ret."""
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


def lint_template(
    template: str, ctx: SlotContext, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> LintResult:
    """Yer tutucu dışında rakam, sayı kelimesi, isim, home/away ya da ham metrik adı kalmamalı."""
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
        return f"%{pct}" if language == "tr" else f"{pct}%"
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
) -> str:
    """Bağlanmış ve doğrulanmış şablondan nihai metin."""
    by_id = {cid: (c, v) for cid, c, v in zip(claim_ids, claims, verdicts)}
    labels = METRIC_LABELS.get(ctx.language, METRIC_LABELS["en"])
    starts = {pos for pos, is_placeholder in template_sentence_starts(template) if is_placeholder}

    def verified(cid: str) -> float:
        claim, verdict = by_id[cid]
        return verdict.actual if verdict.actual is not None else claim.value

    def capitalize(text: str) -> str:
        if not text or not text[0].islower():
            return text
        first = "İ" if ctx.language == "tr" and text[0] == "i" else text[0].upper()
        return first + text[1:]

    def fill(m: re.Match[str]) -> str:
        out = value(m)
        return capitalize(out) if m.start() in starts else out

    def value(m: re.Match[str]) -> str:
        kind, _, arg = m.group(1).partition(":")
        if kind in SIDES:
            return ctx.teams[kind]
        if kind in ("score", "score_named"):
            h = format_value("score", verified(SCORE_IDS["home"]), ctx.language)
            a = format_value("score", verified(SCORE_IDS["away"]), ctx.language)
            return f"{ctx.teams['home']} {h}–{a} {ctx.teams['away']}" if kind == "score_named" else f"{h}–{a}"
        if kind == "player":
            return ctx.players[arg]
        if kind == "event":
            return ctx.phrase(arg) or ""
        claim, _ = by_id[arg]
        if kind == "minute":
            return fmt_minute(claim.end.period, claim.end.minute)
        if kind == "start":
            return fmt_minute(claim.start.period, claim.start.minute)
        if kind == "label":
            return labels.get(claim.metric, claim.metric.replace("_", " "))
        return format_value(claim.metric, verified(arg), ctx.language)

    return PLACEHOLDER_RE.sub(fill, template)
