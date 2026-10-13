"""foundry-v4 / v4.1 lint kurallarının yan ölçümleri (eval.inject bunları docs/EVAL.md'ye yazar).

- İzinli cümle başı listesinin temiz taslaklardan çıkarılması (`derive_sentence_starts`);
  sonuç app/explain/config.py'ye dondurulur, tests/test_lint_rates.py eşitliği denetler.
- Kural başına yanlış alarm: template taslakları, v3/v4 slot şablonları ve gerçek LLM çıktıları
  (foundry-v2 serbest metin, foundry-v3 ve foundry-v4 şablon) üzerinde.
- foundry-v3 insan etiketlerinin ham sayımı.
- Template anlatıcının pencere denetimi (hangi iddia hangi pencereden, metinde yazılı mı).
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.analytics import detect_moments
from app.explain.claims import KICKOFF, MatchTime
from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.phrases import (
    OVERSTATEMENT,
    event_word_spans,
    first_word,
    overstatement_spans,
)
from app.explain.labels import METRIC_LABELS, metric_label
from app.explain.slots import (
    PLACEHOLDER_RE,
    SIDE_LABEL_RE,
    SlotContext,
    article_team_issues,
    event_type_issues,
    player_repeat_issues,
    sentence_start_issues,
    template_sentence_starts,
)
from app.explain.template_narrator import narrate
from app.explain.text_lint import NUMBER_RE, NUMBER_WORDS, Roster, _number_words, bare_surname_spans
from app.generator import generate_match
from app.generator.models import Event, read_jsonl

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
DEMO_DIR = REPO_ROOT / "data" / "demo"
V2_RUN = DOCS / "LLM_RUN.foundry-v2.json"
V3_RUN = DOCS / "LLM_RUN.foundry-v3.json"
V4_RUN = DOCS / "LLM_RUN.foundry-v4.json"
V3_REVIEW = DOCS / "human_review.foundry-v3.csv"
LANGS = ("en", "tr")
LABELS = ("correct", "wrong_fact", "misleading", "dull")


# --- metin birimleri ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Text:
    """Ölçülen tek taslak. `template` yer tutuculu biçim (ham metinde adlar/sayılar yer tutucuya çevrilir)."""

    source: str
    lang: str
    moment_id: str
    moment_type: str
    template: str
    raw: str | None = None  # ham metin (bare_surname için)
    roster: Roster | None = None
    label: dict[str, str] | None = None  # insan etiketi (yalnızca foundry-v3)
    ctx: SlotContext | None = None  # {event:}/{player:} kuralları için (yalnızca slot şablonları)


def to_template(text: str, roster: Roster) -> str:
    """Ham metin → yer tutuculu biçim: kadro adları ve sayılar yer tutucu sayılır."""
    return NUMBER_RE.sub("{n}", roster.pattern.sub("{name}", text))


def _mask(template: str) -> str:
    return PLACEHOLDER_RE.sub(lambda m: "x" * len(m.group()), template)


def template_drafts(corpus: Iterable[tuple[int, str | None]]) -> list[Text]:
    """Template anlatıcının taslakları (ham metin), tüm momentler, EN ve TR."""
    out = []
    for seed, scenario in corpus:
        events = generate_match(seed, scenario)
        roster = Roster.from_events(events)
        for m in detect_moments(events):
            n = narrate(m, events)
            for lang in LANGS:
                raw = " ".join(s.text[lang] for s in n.sentences)
                out.append(Text("template", lang, m.id, m.type, to_template(raw, roster), raw, roster))
    return out


def _demo_events(match_id: str) -> list[Event]:
    return read_jsonl(DEMO_DIR / f"{match_id}.jsonl")


def _review() -> dict[str, dict[str, str]]:
    if not V3_REVIEW.exists():
        return {}
    with V3_REVIEW.open(encoding="utf-8", newline="") as fp:
        return {row["moment_id"]: row for row in csv.DictReader(fp)}


def llm_outputs() -> list[Text]:
    """Gerçek model çıktıları: foundry-v2 serbest metin (ham) ve foundry-v3 kabul edilen şablonlar."""
    out: list[Text] = []
    review = _review()
    for path, version in ((V2_RUN, "llm-v2"), (V3_RUN, "llm-v3")):
        if not path.exists():
            continue
        run = json.loads(path.read_text(encoding="utf-8"))
        lang = run["meta"]["lang"]
        for match in run["matches"]:
            roster = Roster.from_events(_demo_events(match["match_id"]))
            for mo in match["moments"]:
                if mo["source"] != "llm":
                    continue
                if version == "llm-v2":
                    out.append(Text(version, lang, mo["id"], mo["type"], to_template(mo["text"], roster),
                                    mo["text"], roster))
                else:
                    out.append(Text(version, lang, mo["id"], mo["type"], mo["template"],
                                    label=review.get(mo["id"])))
    return out


def llm_v4_outputs() -> list[Text]:
    """foundry-v4'ün kabul edilen şablonları (izinli liste türetmesine girmez; v4.1 kurallarının hedefi)."""
    if not V4_RUN.exists():
        return []
    run = json.loads(V4_RUN.read_text(encoding="utf-8"))
    lang = run["meta"]["lang"]
    runs = run.get("runs") or [run]
    out: list[Text] = []
    for one in runs:
        for match in one["matches"]:
            events = _demo_events(match["match_id"])
            moments = {m.id: m for m in detect_moments(events)}
            for mo in match["moments"]:
                if mo["source"] == "llm" and mo["template"]:
                    ctx = SlotContext.from_moment(moments[mo["id"]], events, lang)
                    out.append(Text("llm-v4", lang, mo["id"], mo["type"], mo["template"], ctx=ctx))
    return out


# --- izinli cümle başı listesi --------------------------------------------------------------------


# Zamirler takım yer tutucusunun yerini tutar; cümle başında {home}/{away} yazılır (foundry-v4.1).
PRONOUNS = {
    "en": frozenset({"they", "their", "them", "we", "he", "she", "it", "its"}),
    "tr": frozenset({"onlar", "bunlar", "o"}),
}


# foundry-v5: zaman edatları dakikayı cümle başına taşır ("At 29' … since kickoff"), dakika yer tutucu ya da
# yan cümleden gelir; metrik adları ("Possession …") {label:}/{clause:} ile gelir.
TIME_PREPOSITIONS = {"en": frozenset({"at", "since", "in", "after", "before", "by"}), "tr": frozenset()}
LABEL_WORDS = {
    lang: frozenset(w.casefold() for label in labels.values() for w in label.split())
    for lang, labels in METRIC_LABELS.items()
}


def _excluded(word: str, lang: str) -> bool:
    """Başlangıç listesine girmeyecek kelimeler: home/away, zamir, zaman edatı, metrik adı, sayı kelimesi,
    olay sözcüğü, abartı."""
    w = word.casefold()
    return bool(
        SIDE_LABEL_RE[lang].fullmatch(word)
        or w in PRONOUNS[lang]
        or w in TIME_PREPOSITIONS[lang]
        or (w in LABEL_WORDS[lang] and w not in ("the", "of", "over", "on"))
        or w in NUMBER_WORDS[lang]
        or event_word_spans(word, lang)
        or overstatement_spans(word, lang, None)
    )


def start_words(template: str) -> list[tuple[int, int, str]]:
    """Yer tutucuyla başlamayan cümlelerin ilk kelimeleri."""
    upper = PLACEHOLDER_RE.sub(lambda m: "X" * len(m.group()), template)
    spans = [(m.start(), m.end()) for m in PLACEHOLDER_RE.finditer(template)]
    out = []
    for pos, is_placeholder in template_sentence_starts(template):
        found = None if is_placeholder else first_word(upper, pos)
        if found and not any(s <= found[0] < e for s, e in spans):
            out.append(found)
    return out


def _clean(t: Text) -> bool:
    return t.label is None or (t.label.get("correct") or "").strip() == "1"


def derive_sentence_starts(texts: Iterable[Text]) -> dict[str, tuple[str, ...]]:
    """Temiz taslakların cümle başı kelimeleri (dil başına, ilk görülen yazılış, alfabetik)."""
    seen: dict[str, dict[str, str]] = {lang: {} for lang in LANGS}
    for t in texts:
        if not _clean(t):
            continue
        for _, _, word in start_words(t.template):
            if not _excluded(word, t.lang):
                seen[t.lang].setdefault(word.casefold(), word)
    return {lang: tuple(sorted(words.values(), key=str.casefold)) for lang, words in seen.items()}


def derive_frozen(corpus: Iterable[tuple[int, str | None]]) -> dict[str, tuple[str, ...]]:
    """config.py'deki dondurulmuş liste: template taslakları + gerçek LLM çıktıları (v3'te yalnızca 'correct')."""
    return derive_sentence_starts([*template_drafts(corpus), *llm_outputs()])


# --- kural başına tetiklenme --------------------------------------------------------------------

RULES = ("sentence_start", "number_words", "overstatement", "bare_surname", "event_word",
         "event_type", "player_repeat", "article_team")
V41_RULES = ("event_type", "player_repeat", "article_team")  # foundry-v4.1 ile eklenen kurallar


def fired(t: Text, rule: str, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG) -> list[str]:
    """Kuralın bu taslakta yakaladığı parçalar (boş = tetiklenmedi)."""
    masked = _mask(t.template)
    if rule == "sentence_start":
        return [i.fragment for i in sentence_start_issues(t.template, t.lang, config)]
    if rule == "number_words":
        return [masked[s:e] for s, e, _ in _number_words(masked, t.lang, strict=True)]
    if rule == "overstatement":
        return [masked[s:e] for s, e in overstatement_spans(masked, t.lang, t.moment_type)]
    if rule == "event_word":
        return [masked[s:e] for s, e in event_word_spans(masked, t.lang)]
    if rule == "bare_surname":
        if t.raw is None or t.roster is None:
            return []
        return [t.raw[s:e] for s, e in bare_surname_spans(t.raw, t.roster)]
    if rule == "article_team":
        return [i.fragment for i in article_team_issues(t.template)] if config.slot_article_team else []
    if rule in ("event_type", "player_repeat"):
        if t.ctx is None:
            return []
        if rule == "event_type":
            return [i.fragment for i in event_type_issues(t.template, t.ctx)] if config.slot_event_type_allowlist else []
        return [i.fragment for i in player_repeat_issues(t.template, t.ctx)] if config.slot_player_repeat else []
    raise ValueError(rule)


@dataclass
class RuleRate:
    dataset: str
    rule: str
    flagged: int
    total: int
    examples: Counter[str]


def rule_rates(datasets: Sequence[tuple[str, Sequence[Text]]], config: ExplainConfig) -> list[RuleRate]:
    out = []
    for name, texts in datasets:
        for rule in RULES:
            if rule == "bare_surname" and not any(t.raw for t in texts):
                continue
            hits = [fired(t, rule, config) for t in texts]
            examples = Counter(f for h in hits for f in h)
            out.append(RuleRate(name, rule, sum(bool(h) for h in hits), len(texts), examples))
    return out


def held_out_sentence_starts(templates: Sequence[Text], llm: Sequence[Text]) -> tuple[dict[str, tuple[str, ...]], int, int, Counter[str]]:
    """Liste yalnızca template taslaklarından çıkarılsaydı gerçek LLM çıktılarında kaç cümle reddedilirdi."""
    allowed = derive_sentence_starts(templates)
    config = replace(DEFAULT_EXPLAIN_CONFIG, sentence_start_allowed_en=allowed["en"],
                     sentence_start_allowed_tr=allowed["tr"])
    sentences = flagged = 0
    examples: Counter[str] = Counter()
    for t in llm:
        sentences += len(template_sentence_starts(t.template))
        issues = sentence_start_issues(t.template, t.lang, config)
        flagged += len(issues)
        examples.update(i.fragment for i in issues)
    return allowed, flagged, sentences, examples


# --- insan etiketleri (foundry-v3) ------------------------------------------------------------------


def human_review_counts() -> dict[str, Any] | None:
    review = _review()
    if not review or not V3_RUN.exists():
        return None
    run = json.loads(V3_RUN.read_text(encoding="utf-8"))
    meta = {mo["id"]: mo for m in run["matches"] for mo in m["moments"]}
    by_source: dict[str, Counter[str]] = {}
    ids: dict[str, list[str]] = {label: [] for label in LABELS}
    texts = Counter()
    for mid, row in review.items():
        source = meta[mid]["source"] if mid in meta else "?"
        texts[source] += 1
        for label in LABELS:
            if (row.get(label) or "").strip() == "1":
                by_source.setdefault(source, Counter())[label] += 1
                ids[label].append(mid)
    return {"texts": texts, "by_source": by_source, "ids": ids, "total": len(review)}


# --- şablon pencere denetimi ------------------------------------------------------------------------


def _window(c) -> str:
    if c.metric == "pressure_balance":
        return "kayan pencere (son oynanmış dakikalar)"
    if c.start == c.end:
        return "olay anı"
    if c.start == KICKOFF:
        return "maç başı → an"
    return "pencere (X' → an)"


def window_audit(corpus: Iterable[tuple[int, str | None]], config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG) -> dict[str, Any]:
    """Moment tipi başına iddia pencereleri ve pencerenin metinde yazılı olup olmadığı."""
    rows: dict[tuple[str, str, str, str], list[int]] = {}
    clamped_pressure = clamped_dominance = pressure_total = dominance_total = 0
    clamp_example = None
    for seed, scenario in corpus:
        events = generate_match(seed, scenario)
        for m in detect_moments(events):
            n = narrate(m, events, config)
            for s in n.sentences:
                for c in s.claims:
                    stated = None
                    if _window(c) == "pencere (X' → an)":
                        stated = (f"since {c.start.minute}'" in s.text["en"]
                                  and f"{c.start.minute}. dakikadan" in s.text["tr"])
                    elif c.metric == "pressure_balance":  # pencere etiketin içinde
                        stated = all(metric_label(c.metric, lang) in s.text[lang] for lang in LANGS)
                    key = (m.type, c.metric, c.kind, _window(c))
                    entry = rows.setdefault(key, [0, 0])
                    entry[0] += 1
                    entry[1] += bool(stated)
            t = MatchTime(m.period, m.minute, m.second)
            if m.type in ("pressure_shift", "dominance_without_reward"):
                minutes = config.context_minutes if m.type == "pressure_shift" else config.dominance_context_minutes
                windowed = next(c for s in n.sentences for c in s.claims if c.metric in ("shots", "possession"))
                span = (t.minute - windowed.start.minute) * 60 + (t.second - windowed.start.second)
                clamped = span < minutes * 60
                if m.type == "pressure_shift":
                    pressure_total += 1
                    clamped_pressure += clamped
                    if clamped and clamp_example is None:
                        clamp_example = (m.id, " ".join(s.text["en"] for s in n.sentences), span)
                else:
                    dominance_total += 1
                    clamped_dominance += clamped
    return {
        "rows": rows,
        "pressure": (clamped_pressure, pressure_total),
        "dominance": (clamped_dominance, dominance_total),
        "clamp_example": clamp_example,
    }


# --- yasak listesi (rapor için okunur biçim) ------------------------------------------------------


def overstatement_table() -> list[tuple[str, str, str]]:
    out = []
    for lang, entries in OVERSTATEMENT.items():
        for pattern, supported in entries:
            readable = re.sub(r"\\w\*", "…", pattern).replace("(?:", "(").replace("|", " · ")
            out.append((lang, readable, ", ".join(sorted(supported)) or "—"))
    return out

