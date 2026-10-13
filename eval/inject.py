"""Enjeksiyon değerlendirmesi: eski (foundry-v2, serbest metin) ve yeni (foundry-v3, slot)
anlatım yaklaşımı kontrollü hataları ne oranda yakalıyor?

Template anlatıcının doğru taslaklarından başlar:
- v2: serbest metin + iddialar; denetim `check_draft` (text_lint + verify_claim).
- v3: aynı taslak deterministik olarak slot şablonuna çevrilir (`slotify`); denetim
  `check_slot_draft` (şablon lint + yer tutucu bağlama + verify_claim).
Her hata türü iki yaklaşımın kendi biçiminde, aynı anlamda enjekte edilir.

    python -m eval.inject [--quick] [--out docs/EVAL.md] [--no-write]
"""

from __future__ import annotations

import argparse
import hashlib
import random
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from app.analytics import detect_moments
from app.analytics.moments import Moment
from app.explain.claims import Claim
from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.narrator import TemplateNarrator
from app.explain.pipeline import check_draft, check_slot_draft
from app.explain.slots import PLACEHOLDER_RE, SlotContext, parse_placeholders, player_ids
from app.explain.text_lint import NUMBER_RE, NUMBER_WORDS, Roster
from app.generator import generate_match
from app.generator.models import Event

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "docs" / "EVAL.md"
LANGS = ("en", "tr")

# (seed, senaryo): 3 demo maç + her senaryodan 5 seed + 10 senaryosuz maç
FULL_CORPUS = (
    [(42, "red_card_swing"), (7, "dominant_loss"), (100, None)]
    + [(s, sc) for sc in ("late_comeback", "red_card_swing", "dominant_loss") for s in range(5)]
    + [(s, None) for s in range(10)]
)
QUICK_CORPUS = [(42, "red_card_swing"), (7, "dominant_loss"), (42, "late_comeback"), (100, None)]

FABRICATED_START = {"en": "Quintana scores.", "tr": "Quintana gol attı."}
UNSUPPORTED_NUMBER = {"en": "{team} have won {n} corners.", "tr": "{team} şimdiye kadar {n} korner kazandı."}
UNSUPPORTED_QUALITATIVE = {"en": "{team} were the better side.", "tr": "{team} daha iyi taraftı."}
SIDE_LABEL = {
    "en": {"home": "the home side", "away": "the away side"},
    "tr": {"home": "ev sahibi ekip", "away": "deplasman ekibi"},
}


@dataclass(frozen=True)
class Sample:
    events: Sequence[Event]
    roster: Roster
    players: tuple[str, ...]  # bu maçın kadrosu
    teams: dict[str, str]
    moment: Moment
    lang: str
    text: str
    claims: tuple[Claim, ...]
    slot: SlotDraft | None = None  # v3 tabanı (slotify başarısızsa None)


@dataclass(frozen=True)
class SlotDraft:
    template: str
    claims: tuple[Claim, ...]
    claim_ids: tuple[str, ...]
    ctx: SlotContext = field(repr=False)


@dataclass(frozen=True)
class Injection:
    text: str  # v2: metin, v3: şablon
    claims: tuple[Claim, ...]
    claim_ids: tuple[str, ...] = ()


Injector = Callable[[Sample, random.Random, Sequence[str]], Injection | None]


# --- yardımcılar ------------------------------------------------------------------------


def _fmt(v: float) -> str:
    return f"{v:g}"


def _masked(sample: Sample) -> str:
    """İsim aralıkları boşlukla maskelenmiş metin (uzunluk aynı)."""
    chars = list(sample.text)
    for m in sample.roster.pattern.finditer(sample.text):
        chars[m.start() : m.end()] = " " * (m.end() - m.start())
    return "".join(chars)


def _splice(text: str, start: int, end: int, new: str) -> str:
    return text[:start] + new + text[end:]


def _bumped_number(m: re.Match[str]) -> str:
    g = m.groupdict()
    if g["trmin"] is not None:
        return m.group().replace(g["trmin"], str(int(g["trmin"]) + 1), 1)
    if g["min"] is not None:
        if g["extra"]:
            return f"{g['min']}+{int(g['extra']) + 1}'"
        return f"{int(g['min']) + 1}'"
    if g["pct1"] is not None:
        return f"%{int(g['pct1']) + 5}"
    if g["pct2"] is not None:
        return f"{int(g['pct2']) + 5}%"
    if g["dec"] is not None:
        value = float(g["dec"]) + 0.10
        return f"{value:+.2f}" if g["dec"][0] in "+-" else f"{value:.2f}"
    return str(int(g["int"]) + 1)


def _unused_number(claims: Sequence[Claim]) -> int:
    used = {abs(c.value) for c in claims}
    used |= {c.start.minute for c in claims} | {c.end.minute for c in claims}
    n = 7
    while n in used:
        n += 1
    return n


def _score_re(teams: dict[str, str]) -> re.Pattern[str]:
    return re.compile(re.escape(teams["home"]) + r" (\d+)–(\d+) " + re.escape(teams["away"]))


def _swap_player(sample: Sample, rng: random.Random, pool: Sequence[str]) -> Injection | None:
    mentioned = [p for p in sample.players if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", sample.text)]
    claimed = {c.subject.player for c in sample.claims}
    candidates = [p for p in pool if p not in claimed and p not in sample.text]
    if not mentioned or not candidates:
        return None
    old, new = rng.choice(mentioned), rng.choice(candidates)
    return Injection(re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", new, sample.text), sample.claims)


# --- slotify: v3 tabanı -----------------------------------------------------------------------


def slotify(sample: Sample) -> SlotDraft | None:
    """Template taslağını slot şablonuna çevirir; temiz çevrilemezse None."""
    ctx = SlotContext.from_moment(sample.moment, sample.events, sample.lang)
    claims = sample.claims
    ids = tuple(f"c{i + 1}" for i in range(len(claims)))
    text = _score_re(sample.teams).sub("{score}", sample.text)
    id_of = {name: pid for pid, name in player_ids(sample.events).items()}
    for name in sorted(id_of, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", f"{{player:{id_of[name]}}}", text)
    for side in ("home", "away"):
        text = re.sub(rf"(?<!\w){re.escape(sample.teams[side])}(?!\w)", f"{{{side}}}", text)

    masked = PLACEHOLDER_RE.sub(lambda m: "x" * len(m.group()), text)
    out, last = [], 0
    for m in NUMBER_RE.finditer(masked):
        g = m.groupdict()
        slot = None
        if g["min"] is not None or g["trmin"] is not None:
            minute = int(g["min"] or g["trmin"]) + (int(g["extra"]) - 1 if g["extra"] else 0)
            end = next((i for i, c in enumerate(claims) if c.end.minute == minute), None)
            start = next((i for i, c in enumerate(claims) if c.start.minute == minute), None)
            if end is not None:
                slot = f"{{minute:{ids[end]}}}"
            elif start is not None:
                slot = f"{{start:{ids[start]}}}"
            if g["trmin"] is not None and slot:
                slot += m.group()[len(g["trmin"]):]  # ". dakika" kalsın
        elif g["pct1"] is not None or g["pct2"] is not None:
            p = int(g["pct1"] or g["pct2"])
            i = next((i for i, c in enumerate(claims) if c.kind == "ratio" and abs(c.value * 100 - p) <= 0.5), None)
            slot = f"{{value:{ids[i]}}}" if i is not None else None
        else:
            v = abs(float(g["dec"] or g["int"]))
            i = next((i for i, c in enumerate(claims) if c.kind != "ratio" and abs(abs(c.value) - v) < 0.006), None)
            slot = f"{{value:{ids[i]}}}" if i is not None else None
        if slot is None:
            return None
        out += [text[last:m.start()], slot]
        last = m.end()
    template = "".join(out) + text[last:]

    items, _, _, _, _ = check_slot_draft(template, claims, ids, ctx)
    return SlotDraft(template, claims, ids, ctx) if not items else None


# --- v2 enjeksiyonları (serbest metin) -----------------------------------------------------------


def v2_control(s, rng, foreign):
    return Injection(s.text, s.claims)


def v2_number_text(s, rng, foreign):
    tokens = list(NUMBER_RE.finditer(_masked(s)))
    if not tokens:
        return None
    m = rng.choice(tokens)
    return Injection(_splice(s.text, m.start(), m.end(), _bumped_number(m)), s.claims)


def v2_number_text_and_claim(s, rng, foreign):
    candidates = []
    for i, c in enumerate(s.claims):
        pattern = rf"(?<![\d.]){re.escape(_fmt(abs(c.value)))}(?![\d.%])"
        if c.kind != "ratio" and re.search(pattern, _masked(s)):
            candidates.append((i, c, pattern))
    if not candidates:
        return None
    i, c, pattern = rng.choice(candidates)
    step = 1 if float(c.value).is_integer() else 0.1
    new_value = round(c.value + step, 2)
    text = re.sub(pattern, _fmt(abs(new_value)), s.text, count=1)
    claims = list(s.claims)
    claims[i] = replace(c, value=new_value)
    return Injection(text, tuple(claims))


def v2_player_swap(s, rng, foreign):
    return _swap_player(s, rng, s.players)


def v2_foreign_player(s, rng, foreign):
    return _swap_player(s, rng, [p for p in foreign if p not in s.players])


def v2_unsupported_sentence_number(s, rng, foreign):
    extra = UNSUPPORTED_NUMBER[s.lang].format(team=s.teams[s.moment.team], n=_unused_number(s.claims))
    return Injection(f"{s.text} {extra}", s.claims)


def v2_unsupported_sentence_qualitative(s, rng, foreign):
    return Injection(f"{s.text} {UNSUPPORTED_QUALITATIVE[s.lang].format(team=s.teams[s.moment.team])}", s.claims)


def v2_number_words(s, rng, foreign):
    tokens = [m for m in NUMBER_RE.finditer(_masked(s)) if m.group("int") and int(m.group("int")) < 20]
    if not tokens:
        return None
    m = rng.choice(tokens)
    return Injection(_splice(s.text, m.start(), m.end(), NUMBER_WORDS[s.lang][int(m.group("int")) + 1]), s.claims)


def v2_sentence_start_fabricated(s, rng, foreign):
    return Injection(f"{FABRICATED_START[s.lang]} {s.text}", s.claims)


def v2_score_order_reversed(s, rng, foreign):
    m = _score_re(s.teams).search(s.text)
    if not m or m.group(1) == m.group(2):
        return None
    swapped = f"{s.teams['home']} {m.group(2)}–{m.group(1)} {s.teams['away']}"
    return Injection(_splice(s.text, m.start(), m.end(), swapped), s.claims)


def v2_raw_side_label(s, rng, foreign):
    side = s.moment.team
    name = s.teams[side]
    if name not in s.text:
        return None
    return Injection(s.text.replace(name, SIDE_LABEL[s.lang][side], 1), s.claims)


def _coincidence(s: Sample, value: float) -> int | None:
    """Metindeki değerden farklı, ama başka bir iddiada geçen tamsayı (zorlanmış tesadüf)."""
    others = sorted({int(abs(c.value)) for c in s.claims if float(c.value).is_integer() and abs(c.value) != value})
    return others[0] if others else None


def v2_free_number(s, rng, foreign):
    tokens = [m for m in NUMBER_RE.finditer(_masked(s)) if m.group("int")]
    rng.shuffle(tokens)
    for m in tokens:
        other = _coincidence(s, int(m.group("int")))
        if other is not None:
            return Injection(_splice(s.text, m.start(), m.end(), str(other)), s.claims)
    return None


# --- v3 enjeksiyonları (slot şablonu) ---------------------------------------------------------


def _slot(s: Sample) -> SlotDraft | None:
    return s.slot


def _placeholders(template: str, kinds: Sequence[str]):
    return [p for p in parse_placeholders(template)[0] if p.kind in kinds]


def _inj(d: SlotDraft, template: str, claims: tuple[Claim, ...] | None = None) -> Injection:
    return Injection(template, d.claims if claims is None else claims, d.claim_ids)


def _claim_of(d: SlotDraft, cid: str) -> Claim:
    return d.claims[d.claim_ids.index(cid)]


def v3_control(s, rng, foreign):
    d = _slot(s)
    return _inj(d, d.template) if d else None


def v3_number_text(s, rng, foreign):
    d = _slot(s)
    phs = _placeholders(d.template, ("value", "minute", "start")) if d else []
    if not phs:
        return None
    ph = rng.choice(phs)
    raw = str(int(abs(_claim_of(d, ph.arg).value)) + 1)
    return _inj(d, _splice(d.template, ph.start, ph.end, raw))


def v3_number_text_and_claim(s, rng, foreign):
    d = _slot(s)
    if not d:
        return None
    candidates = [i for i, c in enumerate(d.claims) if c.kind != "ratio"]
    if not candidates:
        return None
    i = rng.choice(candidates)
    c = d.claims[i]
    claims = list(d.claims)
    claims[i] = replace(c, value=round(c.value + (1 if float(c.value).is_integer() else 0.1), 2))
    return _inj(d, d.template, tuple(claims))


def v3_player_swap(s, rng, foreign):
    d = _slot(s)
    phs = _placeholders(d.template, ("player",)) if d else []
    claimed = {c.subject.player for c in d.claims} if d else set()
    candidates = [pid for pid, name in d.ctx.players.items() if name not in claimed] if d else []
    if not phs or not candidates:
        return None
    ph = rng.choice(phs)
    return _inj(d, _splice(d.template, ph.start, ph.end, f"{{player:{rng.choice(candidates)}}}"))


def v3_foreign_player(s, rng, foreign):
    d = _slot(s)
    phs = _placeholders(d.template, ("player",)) if d else []
    outsiders = [p for p in foreign if p not in s.players]
    if not phs or not outsiders:
        return None
    ph = rng.choice(phs)
    return _inj(d, _splice(d.template, ph.start, ph.end, rng.choice(outsiders)))


def v3_unsupported_sentence_number(s, rng, foreign):
    d = _slot(s)
    if not d:
        return None
    extra = UNSUPPORTED_NUMBER[s.lang].format(team=f"{{{s.moment.team}}}", n=_unused_number(d.claims))
    return _inj(d, f"{d.template} {extra}")


def v3_unsupported_sentence_qualitative(s, rng, foreign):
    d = _slot(s)
    if not d:
        return None
    return _inj(d, f"{d.template} {UNSUPPORTED_QUALITATIVE[s.lang].format(team='{' + s.moment.team + '}')}")


def v3_number_words(s, rng, foreign):
    d = _slot(s)
    phs = [p for p in _placeholders(d.template, ("value",)) if abs(_claim_of(d, p.arg).value) < 20] if d else []
    if not phs:
        return None
    ph = rng.choice(phs)
    word = NUMBER_WORDS[s.lang][int(abs(_claim_of(d, ph.arg).value)) + 1]
    return _inj(d, _splice(d.template, ph.start, ph.end, word))


def v3_sentence_start_fabricated(s, rng, foreign):
    d = _slot(s)
    return _inj(d, f"{FABRICATED_START[s.lang]} {d.template}") if d else None


def v3_score_order_reversed(s, rng, foreign):
    d = _slot(s)
    m = _score_re(s.teams).search(s.text)
    if not d or "{score}" not in d.template or not m or m.group(1) == m.group(2):
        return None
    return _inj(d, d.template.replace("{score}", f"{{home}} {m.group(2)}–{m.group(1)} {{away}}", 1))


def v3_raw_side_label(s, rng, foreign):
    d = _slot(s)
    slot = "{" + s.moment.team + "}"
    if not d or slot not in d.template:
        return None
    return _inj(d, d.template.replace(slot, SIDE_LABEL[s.lang][s.moment.team], 1))


def v3_free_number(s, rng, foreign):
    d = _slot(s)
    phs = _placeholders(d.template, ("value",)) if d else []
    rng.shuffle(phs)
    for ph in phs:
        other = _coincidence(s, abs(_claim_of(d, ph.arg).value))
        if other is not None:
            return _inj(d, _splice(d.template, ph.start, ph.end, str(other)))
    return None


def v3_wrong_slot_binding(s, rng, foreign):
    d = _slot(s)
    if not d:
        return None
    phs = _placeholders(d.template, ("value", "minute"))
    pairs = [
        (a, b) for i, a in enumerate(phs) for b in phs[i + 1:]
        if a.kind == b.kind and a.arg != b.arg
        and _claim_of(d, a.arg).value != _claim_of(d, b.arg).value
    ]
    if not pairs:
        return None
    a, b = rng.choice(pairs)
    t = d.template
    t = t[:b.start] + a.raw + t[b.end:]
    t = t[:a.start] + b.raw + t[a.end:]
    return _inj(d, t)


@dataclass(frozen=True)
class InjectionType:
    name: str
    description: str
    v2: Injector | None
    v3: Injector | None
    miss_v2: str = "—"
    miss_v3: str = "—"


COINCIDENCE = ("Lint sayının hangi iddiaya ait olduğuna değil, herhangi bir iddiada geçip "
               "geçmediğine bakar; yanlış yerdeki doğru-görünen sayı geçer.")
QUALITATIVE = ("Cümlede ne sayı ne yeni bir isim var; nitel yargılar lint ve verify'ın kapsamı dışında.")
SENTENCE_START = ("Cümle başındaki tek büyük harfli kelime isim sayılmıyor (cümle başı büyük harfi normal); "
                  "kadroda olmayan tek kelimelik isim bu konumda fark edilmiyor.")
AMBIGUOUS = ("Belirsiz kelime (TR \"bir\", EN \"one\") ardından sayılabilir bir isim gelmediği için sayı "
             "sayılmıyor (\"bir ara\", \"one of\" gibi kullanımlarda yanlış alarmı önlemek için).")

INJECTION_TYPES = (
    InjectionType("control", "Değişiklik yok (yanlış alarm ölçümü)", v2_control, v3_control),
    InjectionType("number_text", "Bir sayı yanlış yazılır (v3: yer tutucu yerine ham sayı)",
                  v2_number_text, v3_number_text, miss_v2=COINCIDENCE),
    InjectionType("number_text_and_claim", "İddia değeri yanlış (v2: metin de birlikte)",
                  v2_number_text_and_claim, v3_number_text_and_claim,
                  miss_v2="Gevşetilmiş eşitsizlik iddiası (`score_margin lte 0` → `lte 1`) hâlâ doğru kalıyor.",
                  miss_v3="Gevşetilmiş eşitsizlik iddiası (`score_margin lte 0` → `lte 1`) hâlâ doğru kalıyor; "
                          "verify değerin doğruluğunu ölçer, sınırın sıkılığını değil."),
    InjectionType("player_swap", "Oyuncu, aynı maçtan iddiasız başka bir oyuncuyla değişir",
                  v2_player_swap, v3_player_swap),
    InjectionType("foreign_player", "Oyuncu, başka maçın oyuncusuyla değişir (v3: ham ad)",
                  v2_foreign_player, v3_foreign_player,
                  miss_v2="Yabancı oyuncunun soyadı iddiadaki oyuncuyla aynı; soyad takma ad olarak destekli, "
                          "ad \"—\" sonrası cümle başında."),
    InjectionType("unsupported_sentence_number", "İddiasız, sayı içeren yeni cümle",
                  v2_unsupported_sentence_number, v3_unsupported_sentence_number),
    InjectionType("unsupported_sentence_qualitative", "İddiasız, nitel yeni cümle",
                  v2_unsupported_sentence_qualitative, v3_unsupported_sentence_qualitative,
                  miss_v2=QUALITATIVE, miss_v3=QUALITATIVE),
    InjectionType("number_words", "Yanlış sayı yazıyla (\"two\", \"iki\")",
                  v2_number_words, v3_number_words, miss_v2=AMBIGUOUS + " Ya da " + COINCIDENCE,
                  miss_v3=AMBIGUOUS),
    InjectionType("sentence_start_fabricated", "Başa uydurma isimli cümle (\"Quintana scores.\")",
                  v2_sentence_start_fabricated, v3_sentence_start_fabricated,
                  miss_v2=SENTENCE_START, miss_v3=SENTENCE_START),
    InjectionType("score_order_reversed", "Skor sırası ters (deplasman–ev sahibi)",
                  v2_score_order_reversed, v3_score_order_reversed,
                  miss_v2="Her iki skor rakamı da bir skor iddiasında geçiyor; lint sırayı bilmiyor."),
    InjectionType("raw_side_label", "Takım adı yerine ham \"home/away\" etiketi",
                  v2_raw_side_label, v3_raw_side_label,
                  miss_v2="Küçük harfli \"home side\" ne sayı ne isim; v2 lint'i etiketleri denetlemiyor."),
    InjectionType("free_number", "Serbest yazılmış sayı: başka bir iddianın değeri yanlış yere yazılır",
                  v2_free_number, v3_free_number, miss_v2=COINCIDENCE),
    InjectionType("wrong_slot_binding", "Yer tutucu yanlış iddiaya bağlanır (iki referans yer değiştirir)",
                  None, v3_wrong_slot_binding,
                  miss_v3="Her yer tutucu doğru türde ve doğrulanmış bir iddiaya bağlı; hangi iddianın "
                          "cümlede nereye ait olduğu denetlenmiyor (v3'ün yeni açığı)."),
)


# --- ölçüm ---------------------------------------------------------------------------------


@dataclass
class Stats:
    applicable: int = 0
    caught: int = 0
    missed_example: tuple[str, str] | None = None

    @property
    def rate(self) -> float | None:
        return self.caught / self.applicable if self.applicable else None


@dataclass
class TypeResult:
    spec: InjectionType
    v2: Stats = field(default_factory=Stats)
    v3: Stats = field(default_factory=Stats)


@dataclass
class EvalReport:
    corpus: list[tuple[int, str | None]]
    samples: int
    slotified: int
    v2_number_words_without_fix: float | None = None
    results: list[TypeResult] = field(default_factory=list)


def _rng(moment: Moment, type_name: str, lang: str, variant: str) -> random.Random:
    digest = hashlib.sha256(f"{moment.id}|{type_name}|{lang}|{variant}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def build_samples(corpus: Sequence[tuple[int, str | None]]) -> tuple[list[Sample], list[str]]:
    samples, all_players = [], []
    for seed, scenario in corpus:
        events = generate_match(seed, scenario)
        meta = events[0].data["teams"]
        players = tuple(p for side in ("home", "away") for p in (*meta[side]["lineup"], *meta[side]["bench"]))
        all_players += [p for p in players if p not in all_players]
        roster, narrator = Roster.from_events(events), TemplateNarrator(events)
        teams = {side: meta[side]["name"] for side in ("home", "away")}
        for m in detect_moments(events):
            for lang in LANGS:
                d = narrator.narrate(m, "neutral", lang)
                base = Sample(events, roster, players, teams, m, lang, d.text, d.claims)
                samples.append(replace(base, slot=slotify(base)))
    return samples, all_players


def _check_v2(s: Sample, inj: Injection, config: ExplainConfig) -> bool:
    items, _, _ = check_draft(inj.text, inj.claims, s.events, s.roster, config, s.lang)
    return bool(items)


def _check_v3(s: Sample, inj: Injection, config: ExplainConfig) -> bool:
    items, *_ = check_slot_draft(inj.text, inj.claims, inj.claim_ids, s.slot.ctx, config)
    return bool(items)


def run_eval(
    corpus: Sequence[tuple[int, str | None]] = FULL_CORPUS,
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
) -> EvalReport:
    samples, all_players = build_samples(corpus)
    report = EvalReport(list(corpus), len(samples), sum(s.slot is not None for s in samples))
    for spec in INJECTION_TYPES:
        result = TypeResult(spec)
        for s in samples:
            for variant, inject, check, stats, base in (
                ("v2", spec.v2, _check_v2, result.v2, s.text),
                ("v3", spec.v3, _check_v3, result.v3, s.slot.template if s.slot else None),
            ):
                if inject is None or (variant == "v3" and s.slot is None):
                    continue
                inj = inject(s, _rng(s.moment, spec.name, s.lang, variant), all_players)
                if inj is None:
                    continue
                stats.applicable += 1
                caught = check(s, inj, config)
                stats.caught += caught
                if not caught and spec.name != "control" and stats.missed_example is None:
                    stats.missed_example = (base, inj.text)
        report.results.append(result)

    # Not: yazıyla-sayı denetimi kapalıyken v2'nin number_words yakalaması (önceki düzeltmenin etkisi).
    off = replace(config, lint_number_words=False)
    nw = next(t for t in INJECTION_TYPES if t.name == "number_words")
    caught = applicable = 0
    for s in samples:
        inj = nw.v2(s, _rng(s.moment, nw.name, s.lang, "v2"), all_players)
        if inj is not None:
            applicable += 1
            caught += _check_v2(s, inj, off)
    report.v2_number_words_without_fix = caught / applicable if applicable else None
    return report


# --- rapor ---------------------------------------------------------------------------------


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def render_table(report: EvalReport) -> str:
    lines = [
        "| Tür | Enjeksiyon | v2 N | v2 yakalama | v3 N | v3 yakalama |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in report.results:
        lines.append(
            f"| `{r.spec.name}` | {r.spec.description} | {r.v2.applicable or '—'} | {_pct(r.v2.rate)} | "
            f"{r.v3.applicable or '—'} | {_pct(r.v3.rate)} |"
        )
    return "\n".join(lines)


def uncaught(report: EvalReport, variant: str) -> list[TypeResult]:
    return [
        r for r in report.results
        if r.spec.name != "control" and getattr(r, variant).applicable
        and getattr(r, variant).caught < getattr(r, variant).applicable
    ]


def render_markdown(report: EvalReport) -> str:
    control = next(r for r in report.results if r.spec.name == "control")
    corpus = ", ".join(f"{sc or 'senaryosuz'}/{seed}" for seed, sc in report.corpus)
    out = [
        "# Enjeksiyon değerlendirmesi: foundry-v2 (serbest metin) ↔ foundry-v3 (slot)",
        "",
        "Bu dosya `python -m eval.inject` ile üretilir; elle düzenlemeyin.",
        "",
        "## Yöntem",
        "",
        "- Başlangıç: template anlatıcının doğru taslakları (metin + iddialar), tüm momentler, EN ve TR.",
        f"- Derlem: {len(report.corpus)} maç, {report.samples} taslak. Maçlar: {corpus}.",
        "- **v2 (serbest metin)**: model metni ve iddiaları serbest yazar; denetim text_lint + verify_claim.",
        "- **v3 (slot)**: model somut değer yazmaz; yer tutuculu şablon + iddialar yazar, değerleri kod "
        "doğrulanmış iddialardan ve olay anındaki maç durumundan render eder. Denetim: şablon lint (yer "
        "tutucu dışında rakam/sayı kelimesi/isim/home-away/ham metrik adı yasak) + yer tutucu bağlama + "
        "verify_claim.",
        f"- v3 tabanı: taslaklar deterministik olarak slot şablonuna çevrildi (`slotify`); "
        f"{report.slotified}/{report.samples} taslak temiz çevrildi, v3 sütunu bunlar üzerinden ölçülür.",
        "- Her hata türü iki yaklaşımın kendi biçiminde, aynı anlamda enjekte edilir (moment + tür + dil "
        "seed'li). Uygulanamayan taslak N'ye girmez; \"—\" o yaklaşımda karşılığı olmayan tür.",
        "- **Yakalandı** = denetim en az bir hata döndürdü; pipeline bu durumda taslağı yayınlamaz.",
        "",
        "## Sonuçlar",
        "",
        render_table(report),
        "",
        f"Yanlış alarm (control): v2 {control.v2.caught}/{control.v2.applicable}, "
        f"v3 {control.v3.caught}/{control.v3.applicable}.",
        "",
        f"Not: yazıyla-sayı denetimi (önceki tek lint düzeltmesi) kapalıyken v2'nin `number_words` "
        f"yakalaması {_pct(report.v2_number_words_without_fix)}.",
        "",
    ]
    for variant, title in (("v2", "foundry-v2 (serbest metin)"), ("v3", "foundry-v3 (slot)")):
        out += [f"## Yakalanmayan türler: {title}", ""]
        misses = uncaught(report, variant)
        if not misses:
            out += ["Yok: tüm türler %100 yakalandı.", ""]
        for r in misses:
            stats = getattr(r, variant)
            out += [
                f"### `{r.spec.name}`: {_pct(stats.rate)} yakalandı "
                f"({stats.applicable - stats.caught}/{stats.applicable} kaçtı)",
                "",
                f"**Neden:** {getattr(r.spec, 'miss_' + variant)}",
                "",
            ]
            if stats.missed_example:
                original, injected = stats.missed_example
                out += ["Örnek:", "", f"- Orijinal: `{original}`", f"- Enjekte: `{injected}`", ""]
    out += [
        "## Yeniden üretme",
        "",
        "```",
        ".venv/bin/python -m eval.inject",
        "```",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enjeksiyon değerlendirmesi (v2 ↔ v3)")
    parser.add_argument("--quick", action="store_true", help="Küçük derlem")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)

    report = run_eval(QUICK_CORPUS if args.quick else FULL_CORPUS)
    print(render_table(report))
    print(f"\nslotify: {report.slotified}/{report.samples}")
    for variant in ("v2", "v3"):
        print(f"Yakalanmayan ({variant}): " + (", ".join(r.spec.name for r in uncaught(report, variant)) or "yok"))
    if not args.no_write:
        Path(args.out).write_text(render_markdown(report), encoding="utf-8")
        print(f"Yazıldı: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
