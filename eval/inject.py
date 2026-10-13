"""Enjeksiyon değerlendirmesi: foundry-v2 (serbest metin), foundry-v3 (slot) ve foundry-v4
(slot + {event:} + sıkı lint) anlatım yaklaşımları kontrollü hataları ne oranda yakalıyor?

Template anlatıcının doğru taslaklarından başlar:
- v2: serbest metin + iddialar; denetim `check_draft` (text_lint + verify_claim), v2 kurallarıyla.
- v3: aynı taslak deterministik olarak slot şablonuna çevrilir (`slotify`); denetim
  `check_slot_draft` (şablon lint + yer tutucu bağlama + verify_claim), v3 kurallarıyla.
- v4: aynı iddialarla moment tipi başına v4 şablonu (`slotify_v4`: olaylar {event:} ile,
  metrik adları {label:} ile); denetim `check_slot_draft`, varsayılan (v4) kurallarla.
Her hata türü her yaklaşımın kendi biçiminde, aynı anlamda enjekte edilir.

    python -m eval.inject [--quick] [--out docs/EVAL.md] [--no-write]
"""

from __future__ import annotations

import argparse
import hashlib
import random
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from app.analytics import detect_moments
from app.analytics.metrics import other
from app.analytics.moments import Moment
from app.explain.claims import KICKOFF, Claim, Subject, measure
from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.phrases import sentence_starts
from app.explain.pipeline import check_draft, check_slot_draft
from app.explain.slots import PLACEHOLDER_RE, SlotContext, parse_placeholders, player_ids, template_sentence_starts
from app.explain.template_narrator import fmt_minute
from app.explain.template_narrator import narrate as template_narrate
from app.explain.text_lint import NUMBER_RE, NUMBER_WORDS, Roster
from app.generator import generate_match
from app.generator.models import Event

from . import lint_rates

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "docs" / "EVAL.md"
LANGS = ("en", "tr")
VARIANTS = ("v2", "v3", "v4")
TITLES = {"v2": "foundry-v2 (serbest metin)", "v3": "foundry-v3 (slot)", "v4": "foundry-v4 (slot + {event:} + sıkı lint)"}

# Her sütun kendi sürümünün kurallarıyla ölçülür: sonradan eklenen kurallar kapatılır.
V4_CONFIG = DEFAULT_EXPLAIN_CONFIG
V3_CONFIG = replace(
    DEFAULT_EXPLAIN_CONFIG, slot_event_words=False, slot_sentence_start=False,
    slot_strict_number_words=False, slot_overstatement=False,
)
V2_CONFIG = replace(DEFAULT_EXPLAIN_CONFIG, lint_bare_surname=False)
CONFIGS = {"v2": V2_CONFIG, "v3": V3_CONFIG, "v4": V4_CONFIG}

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
    slot4: SlotDraft | None = None  # v4 tabanı
    sentences: tuple[str, ...] = ()  # template anlatıcının cümleleri (ham)


@dataclass(frozen=True)
class SlotDraft:
    template: str
    claims: tuple[Claim, ...]
    claim_ids: tuple[str, ...]
    ctx: SlotContext = field(repr=False)
    event_ref: str | None = None  # v4: şablondaki {event:} olayı


@dataclass(frozen=True)
class Injection:
    text: str  # v2: metin, v3/v4: şablon
    claims: tuple[Claim, ...]
    claim_ids: tuple[str, ...] = ()
    tag: str | None = None  # kullanılan ifade / ad (kaçanları listelemek için)


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


def _ids(claims: Sequence[Claim]) -> tuple[str, ...]:
    return tuple(f"c{i + 1}" for i in range(len(claims)))


def slotify(sample: Sample) -> SlotDraft | None:
    """Template taslağını v3 slot şablonuna çevirir; temiz çevrilemezse None."""
    ctx = SlotContext.from_moment(sample.moment, sample.events, sample.lang)
    template = _slot_text(sample.text, sample)
    if template is None:
        return None
    ids = _ids(sample.claims)
    items, _, _, _, _ = check_slot_draft(template, sample.claims, ids, ctx, V3_CONFIG)
    return SlotDraft(template, sample.claims, ids, ctx) if not items else None


def _slot_text(raw: str, sample: Sample) -> str | None:
    """Ham metni v3 yer tutucularına çevirir (adlar, takımlar, skor, sayılar)."""
    claims = sample.claims
    ids = _ids(claims)
    text = _score_re(sample.teams).sub("{score}", raw)
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
    return "".join(out) + text[last:]


# --- slotify_v4: v4 tabanı ----------------------------------------------------------------------

# Moment tipi başına v4 şablonu; iddialar template anlatıcınınkiyle aynı sırada (c1, c2, ...).
# {E} olay yer tutucusu, {T}/{O} momentin takımı / rakibi.
V4_BASE = {
    "goal": {"en": "{E}, making it {score_named}.", "tr": "{E}; skor {score_named}."},
    "penalty": {"en": "{E}.", "tr": "{E}."},
    "red_card": {"en": "{E}. {T} are down to {value:c2} players.", "tr": "{E}. {T} sahada {value:c2} kişi kaldı."},
    "score_change": {"en": "{E}, making it {score}.", "tr": "{E}; skor {score}."},
    "pressure_shift": {
        "en": "{minute:c1} — {T} take control: {label:c1} {value:c1} in their favour. "
              "{label:c2} since {start:c2}: {T} {value:c2}, {O} {value:c3}.",
        "tr": "{minute:c1} — Baskı {T} tarafına geçti: {label:c1} {value:c1}. "
              "{start:c2}–{minute:c2} arası {label:c2}: {T} {value:c2}, {O} {value:c3}.",
    },
    "dominance_without_reward": {
        "en": "{minute:c1} — {T} dominate without reward: since {start:c1} they have had {value:c1} of the "
              "ball and a {value:c2}–{value:c3} lead in {label:c2}, yet the score is {score_named}.",
        "tr": "{minute:c1} — {T} üstün ama sonuç alamıyor: {start:c1}–{minute:c1} arası {label:c1} "
              "{value:c1}, {label:c2} {value:c2}–{value:c3}; skor ise {score_named}.",
    },
}
V4_BEHIND = {"en": " {T} had been {value:c3} down.", "tr": " {T} en fazla {value:c3} farkla gerideydi."}
EVENT_MOMENTS = ("goal", "penalty", "red_card", "score_change")


def _event_ref(sample: Sample) -> str | None:
    if sample.moment.type not in EVENT_MOMENTS:
        return None
    match_id = sample.events[0].match_id
    if sample.moment.type in ("score_change",):
        return f"{match_id}#{sample.moment.event_ids[-1]}"
    return sample.claims[0].event_ids[-1]  # sayılan olay: gol / penaltı / kırmızı kart


def slotify_v4(sample: Sample) -> SlotDraft | None:
    """Template iddialarıyla v4 şablonu; v4 kurallarından geçmezse None."""
    m = sample.moment
    template = V4_BASE[m.type][sample.lang]
    if m.type == "score_change" and m.detail.get("from_behind"):
        template += V4_BEHIND[sample.lang]
    ref = _event_ref(sample)
    template = template.replace("{T}", "{" + m.team + "}").replace("{O}", "{" + other(m.team) + "}")
    if ref is not None:
        template = template.replace("{E}", "{event:" + ref + "}")
    ctx = SlotContext.from_moment(m, sample.events, sample.lang)
    ids = _ids(sample.claims)
    items, _, _, _, _ = check_slot_draft(template, sample.claims, ids, ctx, V4_CONFIG)
    return SlotDraft(template, sample.claims, ids, ctx, ref) if not items else None


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
    phs = _placeholders(d.template, ("player", "event")) if d else []
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


# --- v4 enjeksiyonları: v3 enjektörü v4 tabanında ------------------------------------------------


def on_v4(inject: Injector) -> Injector:
    """v3 enjektörünü v4 tabanına uygular (aynı anlam, v4 şablon biçimi)."""

    def run(s, rng, foreign):
        return inject(replace(s, slot=s.slot4), rng, foreign) if s.slot4 else None

    run.__name__ = f"v4_{inject.__name__.removeprefix('v3_')}"
    return run


def _score_at(s: Sample) -> tuple[int, int]:
    t = s.slot4.ctx.moment_time
    return tuple(int(measure("score", Subject(side), KICKOFF, t, s.events).value) for side in ("home", "away"))


def v4_score_order_reversed(s, rng, foreign):
    d = s.slot4
    if not d:
        return None
    h, a = _score_at(s)
    if h == a:
        return None
    if "{score_named}" in d.template:
        return _inj(d, d.template.replace("{score_named}", f"{{home}} {a}–{h} {{away}}", 1))
    if "{score}" in d.template:
        return _inj(d, d.template.replace("{score}", f"{a}–{h}", 1))
    return None


# --- yeni türler (foundry-v4) --------------------------------------------------------------------

# Olay cümlesi ters rolle: penaltıyı kullanan "kurtardı", golcü "kurtardı/yedi", atılan "kart gördürdü".
# Her tür için birkaç ifade; bir kısmı bilerek olay sözcüğü içermiyor (yasak listeyi sınamak için).
REVERSED_ROLE = {
    "goal": {
        "en": ("{p} saved the shot at {m}", "{p} conceded at {m}", "{p} kept it out at {m}"),
        "tr": ("{p} şutu kurtardı ({m})", "{p} golü engelleyemedi ({m})", "{p} topu çizgiden çıkardı ({m})"),
    },
    "penalty": {
        "en": ("{p} saved a penalty at {m}", "{p} stopped the spot-kick at {m}", "{p} kept the kick out at {m}"),
        "tr": ("{p} penaltı kurtardı ({m})", "{p} penaltıda gole izin vermedi ({m})", "{p} vuruşu çeldi ({m})"),
    },
    "red_card": {
        "en": ("{p} drew a red card at {m}", "{p} was brought down and saw a rival dismissed at {m}",
               "{p} was the victim of the challenge at {m}"),
        "tr": ("{p} rakibine kırmızı kart gördürdü ({m})", "{p} yerde kaldı, rakibi oyundan atıldı ({m})",
               "{p} sert müdahaleye maruz kaldı ({m})"),
    },
}
FABRICATED_NAMES = ("Ravello", "Okonde", "Marisk", "Telvano", "Quintara", "Dusko", "Fernhal", "Albrecz")
FABRICATED_PREDICATES = {
    "en": ("{n} pressed high.", "{n} kept running.", "{n} looked sharp."),
    "tr": ("{n} önde baskı yaptı.", "{n} durmadan koştu.", "{n} çok hareketliydi."),
}
# Nitel abartı: lint yasak listesinden bağımsız yazıldı; bir kısmı listede yok. (EN, TR, destekleyen tipler)
OVERSTATED = (
    ("{t} were utterly dominant.", "{t} rakibini ezdi geçti.", ("dominance_without_reward",)),
    ("{t} pushed on deep into stoppage time.", "{t} uzatmaların son saniyelerinde bastırdı.", ()),
    ("{t} completely took control.", "{t} oyunun kontrolünü tamamen ele aldı.", ("pressure_shift",)),
    ("{t} were stunning.", "{t} inanılmaz oynadı.", ()),
    ("{t} were relentless.", "{t} durdurulamaz göründü.", ()),
    ("{t} ran the show.", "{t} gösteri yaptı.", ()),
    ("{t} were in total command.", "{t} sahada fırtına gibi esti.", ()),
    ("{t} deserved more.", "{t} çok daha fazlasını hak etti.", ()),
    ("{t} put on a masterclass.", "{t} ders verir gibi oynadı.", ()),
)


def _role_phrase(s: Sample, rng: random.Random, p: str, m: str) -> tuple[str, str] | None:
    phrases = REVERSED_ROLE.get(s.moment.type, {}).get(s.lang)
    if not phrases:
        return None
    template = rng.choice(phrases)
    return template.format(p=p, m=m), template.format(p="X", m="m").replace("X ", "", 1)


def _pid(s: Sample, name: str) -> str:
    return {n: pid for pid, n in player_ids(s.events).items()}[name]


def v2_role_reversed(s, rng, foreign):
    if s.moment.type not in REVERSED_ROLE:
        return None
    player = s.moment.detail["player"]
    phrase = _role_phrase(s, rng, player, fmt_minute(s.moment.period, s.moment.minute))
    rest = " ".join(s.sentences[1:])
    return Injection(f"{phrase[0]}. {rest}".strip(), s.claims, tag=phrase[1])


def v3_role_reversed(s, rng, foreign):
    d = _slot(s)
    if not d or s.moment.type not in REVERSED_ROLE:
        return None
    phrase = _role_phrase(s, rng, f"{{player:{_pid(s, s.moment.detail['player'])}}}", "{minute:c1}")
    rest = _slot_text(" ".join(s.sentences[1:]), s) if len(s.sentences) > 1 else ""
    if rest is None:
        return None
    return Injection(f"{phrase[0]}. {rest}".strip(), d.claims, d.claim_ids, tag=phrase[1])


def v4_role_reversed(s, rng, foreign):
    d = s.slot4
    if not d or not d.event_ref or s.moment.type not in REVERSED_ROLE:
        return None
    phrase = _role_phrase(s, rng, f"{{player:{_pid(s, s.moment.detail['player'])}}}", "{minute:c1}")
    template = d.template.replace("{event:" + d.event_ref + "}", phrase[0], 1)
    return Injection(template, d.claims, d.claim_ids, tag=phrase[1])


def _other_event(s: Sample, rng: random.Random) -> Event | None:
    """Momentin olayından farklı ifadeli gerçek bir olay: önce moment kaydındakiler, yoksa aynı tipten öncekiler."""
    d = s.slot4
    if not d or not d.event_ref:
        return None
    by_seq = {e.seq: e for e in s.events}
    own = d.ctx.event(d.event_ref)
    phrase = d.ctx.phrase(d.event_ref)
    record = [by_seq[q] for q in dict.fromkeys(s.moment.event_ids)]
    candidates = []
    for e in record:
        ref = f"{s.events[0].match_id}#{e.seq}"
        if e.seq != own.seq and d.ctx.phrase(ref) not in (None, phrase):
            candidates.append(e)
    if not candidates:
        candidates = [
            e for e in s.events
            if e.type is own.type and e.seq < own.seq
            and d.ctx.phrase(f"{s.events[0].match_id}#{e.seq}") not in (None, phrase)
        ]
    return rng.choice(candidates) if candidates else None


def _evidence_tag(s: Sample, e: Event) -> str:
    ref = f"{s.events[0].match_id}#{e.seq}"
    cited = any(ref in c.event_ids for c in s.claims)
    return f"{e.type.value}, {'bir iddianın kanıtı' if cited else 'kanıt değil'}"


def v4_event_wrong_claim(s, rng, foreign):
    e = _other_event(s, rng)
    if e is None:
        return None
    d = s.slot4
    ref = f"{s.events[0].match_id}#{e.seq}"
    template = d.template.replace("{event:" + d.event_ref + "}", "{event:" + ref + "}", 1)
    return Injection(template, d.claims, d.claim_ids, tag=_evidence_tag(s, e))


def _wrong_player(s: Sample, rng: random.Random) -> tuple[str, str, Event] | None:
    """v2/v3 karşılığı: olay cümlesinin oyuncusu başka bir gerçek olayın oyuncusuyla değişir."""
    if s.moment.type not in REVERSED_ROLE:
        return None
    e = _other_event(s, rng)
    if e is None or not e.player or e.player == s.moment.detail["player"]:
        return None
    return s.moment.detail["player"], e.player, e


def v2_event_wrong_claim(s, rng, foreign):
    found = _wrong_player(s, rng)
    if found is None:
        return None
    old, new, e = found
    text = re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", new, s.text, count=1)
    return Injection(text, s.claims, tag=_evidence_tag(s, e))


def v3_event_wrong_claim(s, rng, foreign):
    d = _slot(s)
    found = _wrong_player(s, rng) if d else None
    if found is None:
        return None
    old, new, e = found
    template = d.template.replace(f"{{player:{_pid(s, old)}}}", f"{{player:{_pid(s, new)}}}", 1)
    return Injection(template, d.claims, d.claim_ids, tag=_evidence_tag(s, e))


def _insert_sentence(base: str, starts: Sequence[int], rng: random.Random, sentence: str) -> str:
    pos = rng.choice(list(starts))
    return f"{base[:pos]}{sentence} {base[pos:]}"


def _fabricated(s: Sample, rng: random.Random) -> tuple[str, str]:
    name = rng.choice(FABRICATED_NAMES)
    return rng.choice(FABRICATED_PREDICATES[s.lang]).format(n=name), name


def v2_sentence_start_fabricated_name(s, rng, foreign):
    sentence, name = _fabricated(s, rng)
    return Injection(_insert_sentence(s.text, list(sentence_starts(s.text)), rng, sentence), s.claims, tag=name)


def _slot_fabricated(d: SlotDraft | None, s: Sample, rng: random.Random) -> Injection | None:
    if not d:
        return None
    sentence, name = _fabricated(s, rng)
    starts = [pos for pos, _ in template_sentence_starts(d.template)]
    return Injection(_insert_sentence(d.template, starts, rng, sentence), d.claims, d.claim_ids, tag=name)


def v3_sentence_start_fabricated_name(s, rng, foreign):
    return _slot_fabricated(_slot(s), s, rng)


def v4_sentence_start_fabricated_name(s, rng, foreign):
    return _slot_fabricated(s.slot4, s, rng)


def _overstated(s: Sample, rng: random.Random, team: str) -> tuple[str, str]:
    options = [o for o in OVERSTATED if s.moment.type not in o[2]]
    en, tr, _ = rng.choice(options)
    template = tr if s.lang == "tr" else en
    return template.format(t=team), template.replace("{t} ", "")


def v2_qualitative_overstatement(s, rng, foreign):
    sentence, tag = _overstated(s, rng, s.teams[s.moment.team])
    return Injection(f"{s.text} {sentence}", s.claims, tag=tag)


def _slot_overstated(d: SlotDraft | None, s: Sample, rng: random.Random) -> Injection | None:
    if not d:
        return None
    sentence, tag = _overstated(s, rng, "{" + s.moment.team + "}")
    return Injection(f"{d.template} {sentence}", d.claims, d.claim_ids, tag=tag)


def v3_qualitative_overstatement(s, rng, foreign):
    return _slot_overstated(_slot(s), s, rng)


def v4_qualitative_overstatement(s, rng, foreign):
    return _slot_overstated(s.slot4, s, rng)


@dataclass(frozen=True)
class InjectionType:
    name: str
    description: str
    v2: Injector | None
    v3: Injector | None
    v4: Injector | None = None
    miss_v2: str = "—"
    miss_v3: str = "—"
    miss_v4: str = "—"
    new: bool = False  # foundry-v4 ile eklenen tür


COINCIDENCE = ("Lint sayının hangi iddiaya ait olduğuna değil, herhangi bir iddiada geçip "
               "geçmediğine bakar; yanlış yerdeki doğru-görünen sayı geçer.")
QUALITATIVE = ("Cümlede ne sayı ne yeni bir isim var; nitel yargılar lint ve verify'ın kapsamı dışında.")
QUALITATIVE_V4 = ("Cümle yer tutucuyla başlıyor, sayı ve olay sözcüğü yok; \"were the better side\" nitel "
                  "abartı listesinde değil (abartı değil, yargı). Nitel yargılar v4'te de kapsam dışında.")
SENTENCE_START = ("Cümle başındaki tek büyük harfli kelime isim sayılmıyor (cümle başı büyük harfi normal); "
                  "kadroda olmayan tek kelimelik isim bu konumda fark edilmiyor.")
AMBIGUOUS = ("Belirsiz kelime (TR \"bir\", EN \"one\") ardından sayılabilir bir isim gelmediği için sayı "
             "sayılmıyor (\"bir ara\", \"one of\" gibi kullanımlarda yanlış alarmı önlemek için).")
SLOT_BINDING = ("Her yer tutucu doğru türde ve doğrulanmış bir iddiaya bağlı; hangi iddianın cümlede nereye "
                "ait olduğu denetlenmiyor.")
LOOSE_BOUND = "Gevşetilmiş eşitsizlik iddiası (`score_margin lte 0` → `lte 1`) hâlâ doğru kalıyor."
NO_ROLE_CHECK = "Ad iddianın öznesi ve dakika doğru; lint ve verify olayın rolünü (kim attı / kim kurtardı) bilmiyor."
ROLE_V4 = ("Ters rol, olay sözcüğü yasak listesinde olmayan bir fiille yazıldığında (\"kept it out\", "
           "\"victim of the challenge\", \"topu çizgiden çıkardı\") yakalanmıyor; yakalama sözlüğe dayanıyor.")
WRONG_EVENT_V4 = ("Seçilen yanlış olay başka bir iddianın kanıtıysa {event:} bağlama kuralından geçiyor "
                  "(yalnızca \"bir iddianın kanıtı\" olması aranıyor, cümledeki rolüyle eşleşmesi değil).")
WRONG_EVENT_V2V3 = ("Yeni oyuncu bir iddianın öznesiyse ad destekli sayılıyor; olay ile oyuncu eşleşmesi denetlenmiyor.")
OVERSTATEMENT_V4 = ("İfade nitel abartı listesinde yok (liste sabit; eş anlamlı ve deyimler kaçar).")

INJECTION_TYPES = (
    InjectionType("control", "Değişiklik yok (yanlış alarm ölçümü)", v2_control, v3_control, on_v4(v3_control)),
    InjectionType("number_text", "Bir sayı yanlış yazılır (v3/v4: yer tutucu yerine ham sayı)",
                  v2_number_text, v3_number_text, on_v4(v3_number_text), miss_v2=COINCIDENCE),
    InjectionType("number_text_and_claim", "İddia değeri yanlış (v2: metin de birlikte)",
                  v2_number_text_and_claim, v3_number_text_and_claim, on_v4(v3_number_text_and_claim),
                  miss_v2=LOOSE_BOUND, miss_v3=LOOSE_BOUND + " Verify değerin doğruluğunu ölçer, sınırın sıkılığını değil.",
                  miss_v4=LOOSE_BOUND + " Verify değerin doğruluğunu ölçer, sınırın sıkılığını değil."),
    InjectionType("player_swap", "Oyuncu, aynı maçtan iddiasız başka bir oyuncuyla değişir (v4: tabanda {player:} yok, "
                  "karşılığı `event_wrong_claim`)",
                  v2_player_swap, v3_player_swap, None),
    InjectionType("foreign_player", "Oyuncu, başka maçın oyuncusuyla değişir (v3/v4: ham ad)",
                  v2_foreign_player, v3_foreign_player, on_v4(v3_foreign_player),
                  miss_v2="Yabancı oyuncunun soyadı iddiadaki oyuncuyla aynı; soyad takma ad olarak destekli, "
                          "ad \"—\" sonrası cümle başında."),
    InjectionType("unsupported_sentence_number", "İddiasız, sayı içeren yeni cümle",
                  v2_unsupported_sentence_number, v3_unsupported_sentence_number,
                  on_v4(v3_unsupported_sentence_number)),
    InjectionType("unsupported_sentence_qualitative", "İddiasız, nitel yeni cümle (\"were the better side\")",
                  v2_unsupported_sentence_qualitative, v3_unsupported_sentence_qualitative,
                  on_v4(v3_unsupported_sentence_qualitative),
                  miss_v2=QUALITATIVE, miss_v3=QUALITATIVE, miss_v4=QUALITATIVE_V4),
    InjectionType("number_words", "Yanlış sayı yazıyla (\"two\", \"iki\")",
                  v2_number_words, v3_number_words, on_v4(v3_number_words),
                  miss_v2=AMBIGUOUS + " Ya da " + COINCIDENCE, miss_v3=AMBIGUOUS),
    InjectionType("sentence_start_fabricated", "Başa uydurma isimli cümle (\"Quintana scores.\")",
                  v2_sentence_start_fabricated, v3_sentence_start_fabricated,
                  on_v4(v3_sentence_start_fabricated), miss_v2=SENTENCE_START, miss_v3=SENTENCE_START),
    InjectionType("score_order_reversed", "Skor sırası ters (deplasman–ev sahibi)",
                  v2_score_order_reversed, v3_score_order_reversed, v4_score_order_reversed,
                  miss_v2="Her iki skor rakamı da bir skor iddiasında geçiyor; lint sırayı bilmiyor."),
    InjectionType("raw_side_label", "Takım adı yerine ham \"home/away\" etiketi",
                  v2_raw_side_label, v3_raw_side_label, on_v4(v3_raw_side_label),
                  miss_v2="Küçük harfli \"home side\" ne sayı ne isim; v2 lint'i etiketleri denetlemiyor."),
    InjectionType("free_number", "Serbest yazılmış sayı: başka bir iddianın değeri yanlış yere yazılır",
                  v2_free_number, v3_free_number, on_v4(v3_free_number), miss_v2=COINCIDENCE),
    InjectionType("wrong_slot_binding", "Yer tutucu yanlış iddiaya bağlanır (iki referans yer değiştirir)",
                  None, v3_wrong_slot_binding, on_v4(v3_wrong_slot_binding),
                  miss_v3=SLOT_BINDING + " (v3'ün açığı)", miss_v4=SLOT_BINDING + " v4'te de açık."),
    InjectionType("role_reversed", "Rol ters: olay cümlesi oyuncunun ters rolüyle yazılır "
                  "(penaltıyı kullanan \"saved a penalty\")",
                  v2_role_reversed, v3_role_reversed, v4_role_reversed,
                  miss_v2=NO_ROLE_CHECK, miss_v3=NO_ROLE_CHECK, miss_v4=ROLE_V4, new=True),
    InjectionType("event_wrong_claim", "Yanlış iddiaya bağlı yer tutucu: olay başka bir gerçek olaya bağlanır "
                  "(v4: {event:} başka olay; v2/v3: olay cümlesinin oyuncusu o olayın oyuncusu)",
                  v2_event_wrong_claim, v3_event_wrong_claim, v4_event_wrong_claim,
                  miss_v2=WRONG_EVENT_V2V3, miss_v3=WRONG_EVENT_V2V3, miss_v4=WRONG_EVENT_V4, new=True),
    InjectionType("sentence_start_fabricated_name", "Rastgele bir cümle sınırına uydurma adla, olay sözcüğü ve "
                  "sayı içermeyen cümle (\"Ravello pressed high.\")",
                  v2_sentence_start_fabricated_name, v3_sentence_start_fabricated_name,
                  v4_sentence_start_fabricated_name,
                  miss_v2=SENTENCE_START, miss_v3=SENTENCE_START, new=True),
    InjectionType("qualitative_overstatement", "Moment tipinin desteklemediği nitel abartı cümlesi "
                  "(bağımsız yazılmış listeden)",
                  v2_qualitative_overstatement, v3_qualitative_overstatement, v4_qualitative_overstatement,
                  miss_v2=QUALITATIVE, miss_v3=QUALITATIVE, miss_v4=OVERSTATEMENT_V4, new=True),
)


# --- ölçüm ---------------------------------------------------------------------------------


@dataclass
class Stats:
    applicable: int = 0
    caught: int = 0
    missed_example: tuple[str, str] | None = None
    tags: Counter[str] = field(default_factory=Counter)  # uygulanan ifade/ad → sayı
    missed_tags: Counter[str] = field(default_factory=Counter)

    @property
    def rate(self) -> float | None:
        return self.caught / self.applicable if self.applicable else None


@dataclass
class TypeResult:
    spec: InjectionType
    v2: Stats = field(default_factory=Stats)
    v3: Stats = field(default_factory=Stats)
    v4: Stats = field(default_factory=Stats)


@dataclass
class EvalReport:
    corpus: list[tuple[int, str | None]]
    samples: int
    slotified: int
    slotified_v4: int = 0
    v2_number_words_without_fix: float | None = None
    results: list[TypeResult] = field(default_factory=list)
    rule_rates: list[lint_rates.RuleRate] = field(default_factory=list)
    held_out: tuple | None = None
    llm_texts: int = 0
    # foundry-v3 LLM şablonlarında abartı kuralının tetiklendiği metinler: (moment, parçalar, insan etiketi)
    overstatement_llm: list[tuple[str, list[str], str]] = field(default_factory=list)


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
        roster = Roster.from_events(events)
        teams = {side: meta[side]["name"] for side in ("home", "away")}
        for m in detect_moments(events):
            narration = template_narrate(m, events)
            claims = tuple(c for s in narration.sentences for c in s.claims)
            for lang in LANGS:
                sentences = tuple(s.text[lang] for s in narration.sentences)
                base = Sample(events, roster, players, teams, m, lang, " ".join(sentences), claims,
                              sentences=sentences)
                samples.append(replace(base, slot=slotify(base), slot4=slotify_v4(base)))
    return samples, all_players


def _check(variant: str, s: Sample, inj: Injection, config: ExplainConfig) -> bool:
    if variant == "v2":
        items, _, _ = check_draft(inj.text, inj.claims, s.events, s.roster, config, s.lang)
    else:
        ctx = (s.slot if variant == "v3" else s.slot4).ctx
        items, *_ = check_slot_draft(inj.text, inj.claims, inj.claim_ids, ctx, config)
    return bool(items)


def run_eval(
    corpus: Sequence[tuple[int, str | None]] = FULL_CORPUS,
    configs: dict[str, ExplainConfig] | None = None,
) -> EvalReport:
    configs = configs or CONFIGS
    samples, all_players = build_samples(corpus)
    report = EvalReport(list(corpus), len(samples), sum(s.slot is not None for s in samples),
                        sum(s.slot4 is not None for s in samples))
    for spec in INJECTION_TYPES:
        result = TypeResult(spec)
        for s in samples:
            bases = {"v2": s.text, "v3": s.slot.template if s.slot else None,
                     "v4": s.slot4.template if s.slot4 else None}
            for variant in VARIANTS:
                inject = getattr(spec, variant)
                if inject is None or bases[variant] is None:
                    continue
                inj = inject(s, _rng(s.moment, spec.name, s.lang, variant), all_players)
                if inj is None:
                    continue
                stats = getattr(result, variant)
                stats.applicable += 1
                caught = _check(variant, s, inj, configs[variant])
                stats.caught += caught
                if inj.tag:
                    stats.tags[inj.tag] += 1
                    if not caught:
                        stats.missed_tags[inj.tag] += 1
                if not caught and spec.name != "control" and stats.missed_example is None:
                    stats.missed_example = (bases[variant], inj.text)
        report.results.append(result)

    # Not: yazıyla-sayı denetimi kapalıyken v2'nin number_words yakalaması (önceki düzeltmenin etkisi).
    off = replace(configs["v2"], lint_number_words=False)
    nw = next(t for t in INJECTION_TYPES if t.name == "number_words")
    caught = applicable = 0
    for s in samples:
        inj = nw.v2(s, _rng(s.moment, nw.name, s.lang, "v2"), all_players)
        if inj is not None:
            applicable += 1
            caught += _check("v2", s, inj, off)
    report.v2_number_words_without_fix = caught / applicable if applicable else None

    # v4 kurallarının yanlış alarmı: temiz taslaklar ve gerçek LLM çıktıları.
    raw = [lint_rates.Text("template", s.lang, s.moment.id, s.moment.type,
                           lint_rates.to_template(s.text, s.roster), s.text, s.roster) for s in samples]
    v3_templates = [lint_rates.Text("v3-slot", s.lang, s.moment.id, s.moment.type, s.slot.template)
                    for s in samples if s.slot]
    llm = lint_rates.llm_outputs()
    report.llm_texts = len(llm)
    datasets = [
        ("Template taslakları (ham metin)", raw),
        ("v3 slot şablonları (temiz)", v3_templates),
        ("Gerçek LLM, foundry-v2 serbest metin", [t for t in llm if t.source == "llm-v2"]),
        ("Gerçek LLM, foundry-v3 şablon", [t for t in llm if t.source == "llm-v3"]),
    ]
    report.rule_rates = lint_rates.rule_rates(datasets, configs["v4"])
    report.held_out = lint_rates.held_out_sentence_starts(raw, llm)
    for t in llm:
        hits = lint_rates.fired(t, "overstatement", configs["v4"])
        if hits:
            labels = [k for k in lint_rates.LABELS if t.label and (t.label.get(k) or "").strip() == "1"]
            report.overstatement_llm.append((t.moment_id, hits, ", ".join(labels) or "etiketsiz"))
    return report


# --- rapor ---------------------------------------------------------------------------------


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def render_table(report: EvalReport) -> str:
    lines = [
        "| Tür | Enjeksiyon | v2 N | v2 yakalama | v3 N | v3 yakalama | v4 N | v4 yakalama |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in report.results:
        cells = []
        for variant in VARIANTS:
            st = getattr(r, variant)
            cells += [str(st.applicable or "—"), _pct(st.rate)]
        name = f"`{r.spec.name}`" + (" (yeni)" if r.spec.new else "")
        lines.append(f"| {name} | {r.spec.description} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def uncaught(report: EvalReport, variant: str) -> list[TypeResult]:
    return [
        r for r in report.results
        if r.spec.name != "control" and getattr(r, variant).applicable
        and getattr(r, variant).caught < getattr(r, variant).applicable
    ]


def _tags(counter: Counter[str]) -> str:
    return ", ".join(f"`{t}`×{n}" for t, n in sorted(counter.items(), key=lambda x: (-x[1], x[0])))


def _rate_cell(flagged: int, total: int) -> str:
    return f"{flagged}/{total} ({flagged / total * 100:.1f}%)" if total else "—"


RULE_NAMES = {
    "sentence_start": "Cümle başı (izinli liste)",
    "number_words": "Yazıyla sayı (bağlamsız)",
    "overstatement": "Nitel abartı",
    "bare_surname": "Yalnızca soyad (text_lint)",
    "event_word": "Olay sözcüğü (politika)",
}


def render_rule_rates(report: EvalReport) -> list[str]:
    datasets = list(dict.fromkeys(r.dataset for r in report.rule_rates))
    out = [
        "| Kural | " + " | ".join(datasets) + " |",
        "|---|" + "---:|" * len(datasets),
    ]
    by_key = {(r.dataset, r.rule): r for r in report.rule_rates}
    for rule in lint_rates.RULES:
        cells = []
        for ds in datasets:
            r = by_key.get((ds, rule))
            cells.append(_rate_cell(r.flagged, r.total) if r else "—")
        out.append(f"| {RULE_NAMES[rule]} | " + " | ".join(cells) + " |")
    out += ["", "Tetiklenen parçalar (taslak başına sayım):", ""]
    for r in report.rule_rates:
        if r.examples:
            out.append(f"- {RULE_NAMES[r.rule]} · {r.dataset}: {_tags(r.examples)}")
    return out


def render_human_review() -> list[str]:
    counts = lint_rates.human_review_counts()
    out = ["## İnsan etiketleri: foundry-v3 (ham sayılar)", ""]
    if counts is None:
        return [*out, "Etiket dosyası bulunamadı.", ""]
    sources = sorted(counts["texts"])
    out += [
        f"Kaynak: `docs/human_review.foundry-v3.csv` ({counts['total']} metin; "
        f"{', '.join(f'{s}: {counts['texts'][s]}' for s in sources)}), kaynak bilgisi "
        "`docs/LLM_RUN.foundry-v3.json`'dan. Bir metin birden fazla etiket alabilir (ör. correct + dull).",
        "",
        "| Etiket | Toplam | " + " | ".join(sources) + " | Momentler |",
        "|---|---:|" + "---:|" * len(sources) + "---|",
    ]
    for label in lint_rates.LABELS:
        per = [counts["by_source"].get(s, Counter())[label] for s in sources]
        ids = ", ".join(i.replace("m-", "").replace("-M", " M") for i in counts["ids"][label]) or "—"
        out.append(f"| `{label}` | {sum(per)} | " + " | ".join(map(str, per)) + f" | {ids if label != 'correct' else '…'} |")
    return [*out, ""]


def render_window_audit(corpus: Sequence[tuple[int, str | None]]) -> list[str]:
    audit = lint_rates.window_audit(corpus)
    out = [
        "## Şablon pencere denetimi (template anlatıcı)",
        "",
        "Her iddianın penceresi ve pencereli (başlangıcı ne maç başı ne olay anı) iddiaların cümlede "
        "yazılı olup olmadığı (EN \"since X'\" ve TR \"X. dakikadan\").",
        "",
        "| Moment tipi | Metrik | Tür | Pencere | İddia | Pencere metinde |",
        "|---|---|---|---|---:|---:|",
    ]
    for (mtype, metric, kind, window), (n, stated) in sorted(audit["rows"].items()):
        cell = f"{stated}/{n}" if window.startswith("pencere") else "—"
        out.append(f"| {mtype} | {metric} | {kind} | {window} | {n} | {cell} |")
    pc, pt = audit["pressure"]
    dc, dt = audit["dominance"]
    out += [
        "",
        "Bulgular:",
        "",
        "- `dominance_without_reward`: possession ve şut iddiaları zaten aynı pencereden "
        "(`dominance_context_minutes`); hata EN cümlesindeydi (\"58% of possession and 4–0 shots since 25'\" "
        "pencereyi yalnızca şutlara bağlıyordu). Düzeltme: pencere iki değerden önce yazılıyor "
        "(\"since 25' they have had 58% of the ball and a 4–0 lead in shots\"). TR cümlesi pencereyi zaten başa koyuyordu.",
        "- `pressure_shift`: `pressure_balance` iddiası `start = maç başı` taşıyor, ama `measure` başlangıcı yok "
        "sayıyor; metrik son 10 oynanmış dakikanın kayan penceresi. Metin bu pencereyi yazmıyor. Şut sayımı "
        "ise maç saatine göre `_since` penceresinden geliyor ve devre başında kırpılıyor; "
        f"{pc}/{pt} baskı momentinde şut penceresi {DEFAULT_EXPLAIN_CONFIG.context_minutes} dakikadan kısa"
        + (f" (ör. `{audit['clamp_example'][0]}`: \"{audit['clamp_example'][1]}\", pencere "
           f"{audit['clamp_example'][2]} sn)" if audit["clamp_example"] else "")
        + ". Bu durumda iki değer farklı pencerelerden geliyor. Metne \"10 minutes\" yazmak lint_text'te iddiasız "
        "sayı olur; düzeltme kapsam dışı bırakıldı (verifier'ın `pressure_balance` için pencere desteği gerekir).",
        f"- `dominance_without_reward`: {dc}/{dt} momentte pencere devre başında kırpılmış (dedektör oynanmış "
        "süreyle 20 dakika geriye bakıyor; anlatı maç saatiyle). Metin kırpılmış pencerenin başlangıcını yazdığı için "
        "yanıltıcı değil, ama dedektörün değeriyle (moment.detail) birebir aynı değil.",
        "- `goal`, `red_card`, `penalty`, `score_change`: iddialar olay anı ya da maç başı → an; ayrı pencere yok.",
        "",
    ]
    return out


def render_overstatement_list() -> list[str]:
    out = [
        "## Nitel abartı yasak listesi (v4 lint)",
        "",
        "Sabit liste (`app/explain/phrases.py` `OVERSTATEMENT`). Yer tutucu dışındaki metinde eşleşen ifade, moment "
        "tipi desteklemiyorsa reddedilir (`overstatement`). Destekleyen tipler yalnızca momentin kendi kanıtıdır: "
        "\"dominate\" bir `dominance_without_reward` momentinde, \"take control\" bir `pressure_shift` momentinde "
        "dedektörün eşiğiyle desteklenir. Liste foundry-v3 insan etiketindeki \"deep into stoppage\" bulgusundan ve "
        "genel futbol abartı sözlüğünden yazıldı; enjeksiyondaki abartı cümleleri ayrı yazıldı (bkz. kaçan ifadeler).",
        "",
        "| Dil | İfade (regex, `…` = devamı) | Destekleyen moment tipi |",
        "|---|---|---|",
    ]
    for lang, readable, supported in lint_rates.overstatement_table():
        out.append(f"| {lang} | `{readable}` | {supported} |")
    return [*out, ""]


def render_markdown(report: EvalReport) -> str:
    control = next(r for r in report.results if r.spec.name == "control")
    corpus = ", ".join(f"{sc or 'senaryosuz'}/{seed}" for seed, sc in report.corpus)
    allowed_en = ", ".join(f"`{w}`" for w in DEFAULT_EXPLAIN_CONFIG.sentence_start_allowed_en)
    allowed_tr = ", ".join(f"`{w}`" for w in DEFAULT_EXPLAIN_CONFIG.sentence_start_allowed_tr)
    out = [
        "# Enjeksiyon değerlendirmesi: foundry-v2 ↔ foundry-v3 ↔ foundry-v4",
        "",
        "Bu dosya `python -m eval.inject` ile üretilir; elle düzenlemeyin.",
        "",
        "## Yöntem",
        "",
        "- Başlangıç: template anlatıcının doğru taslakları (metin + iddialar), tüm momentler, EN ve TR.",
        f"- Derlem: {len(report.corpus)} maç, {report.samples} taslak. Maçlar: {corpus}.",
        "- **v2 (serbest metin)**: model metni ve iddiaları serbest yazar; denetim text_lint + verify_claim "
        "(v2 kuralları: yalnızca-soyad denetimi kapalı).",
        "- **v3 (slot)**: model somut değer yazmaz; yer tutuculu şablon + iddialar yazar, değerleri kod "
        "doğrulanmış iddialardan render eder. Denetim: şablon lint (yer tutucu dışında rakam/sayı kelimesi/isim/"
        "home-away/ham metrik adı yasak) + yer tutucu bağlama + verify_claim (v3 kuralları).",
        "- **v4 (slot + {event:} + sıkı lint)**: olay bilgisi yalnızca `{event:<id>}` ile gelir (kod olayın "
        "standart ifadesini veriden üretir; olay bir iddianın dayanağı olmalı), metrik adları `{label:}` ile; "
        "`{score}` takım adsız \"1–0\", `{score_named}` takım adlı. Lint ek olarak olay tipi / rol sözcüklerini, "
        "izinli listede olmayan cümle başlarını, bağlamdan bağımsız yazıyla sayıları ve moment tipinin "
        "desteklemediği nitel abartıyı reddeder.",
        f"- Tabanlar: v3 `slotify` {report.slotified}/{report.samples}, v4 `slotify_v4` "
        f"{report.slotified_v4}/{report.samples} taslak temiz çevrildi; v3/v4 sütunları bunlar üzerinden ölçülür.",
        "- Her hata türü her yaklaşımın kendi biçiminde, aynı anlamda enjekte edilir (moment + tür + dil + "
        "sürüm seed'li). Uygulanamayan taslak N'ye girmez; \"—\" o yaklaşımda karşılığı olmayan tür. "
        "\"(yeni)\" işaretli türler foundry-v4 ile eklendi.",
        "- **Yakalandı** = denetim en az bir hata döndürdü; pipeline bu durumda taslağı yayınlamaz.",
        "",
        "## Sonuçlar",
        "",
        render_table(report),
        "",
        "Yanlış alarm (control): " + ", ".join(
            f"{v} {getattr(control, v).caught}/{getattr(control, v).applicable}" for v in VARIANTS) + ".",
        "",
        f"Not: yazıyla-sayı denetimi kapalıyken v2'nin `number_words` yakalaması "
        f"{_pct(report.v2_number_words_without_fix)}.",
        "",
    ]
    for variant in VARIANTS:
        out += [f"## Yakalanmayan türler: {TITLES[variant]}", ""]
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
            if stats.missed_tags:
                out += [f"Kaçan ifadeler / adlar: {_tags(stats.missed_tags)}", ""]
            if stats.missed_example:
                original, injected = stats.missed_example
                out += ["Örnek:", "", f"- Orijinal: `{original}`", f"- Enjekte: `{injected}`", ""]
    out += ["## Yeni türlerde uygulanan ifadeler (tüm sürümler)", ""]
    for r in report.results:
        if r.spec.new:
            for variant in VARIANTS:
                st = getattr(r, variant)
                if st.tags:
                    caught = st.tags - st.missed_tags
                    out.append(f"- `{r.spec.name}` {variant}: yakalanan {_tags(caught) or '—'}; "
                               f"kaçan {_tags(st.missed_tags) or '—'}")
    allowed_from, flagged, sentences, examples = report.held_out
    out += [
        "",
        "## v4 lint kuralları ve yanlış alarm",
        "",
        "Kural başına, kuralın tetiklendiği taslak oranı. Temiz taslaklarda (template, v3 slot) her tetiklenme "
        "yanlış alarmdır. Gerçek LLM çıktıları: foundry-v2'nin yayınlanan serbest metinleri ve foundry-v3'ün "
        "kabul edilen şablonları (EN, adlar ve sayılar yer tutucu sayılır); bunlarda sayı kelimesi, uydurma ad "
        "yok, yani cümle başı ve sayı kelimesi tetiklenmesi yanlış alarmdır. Nitel abartı tetiklenmesinin doğru "
        "olup olmadığı insan etiketiyle karşılaştırılır (aşağıda). \"Olay sözcüğü\" satırı yanlış alarm değil, "
        "politika: v4'te olay ve metrik adları serbest yazılamaz.",
        "",
        *render_rule_rates(report),
        "",
        "Template ve v3 satırlarında cümle başı ve sayı kelimesi tetiklenmeleri template anlatıcının kendi "
        "kalıplarından geliyor (EN \"Shots since …\", TR \"Bir ara … gerideydi\"). Bu kelimeler listeye bilerek "
        "alınmadı: \"Shots\" olay sözcüğü (v4'te metrik adı `{label:}` ile gelir), \"Bir\" sayı kelimesi. Template "
        "yedeği v4 slot lint'inden değil text_lint'ten geçtiği için bu, yayınlanan yedek metinleri etkilemez; "
        "\"Bir ara\" bağlamsız sayı kelimesi kuralının gerçek bir yanlış alarmıdır.",
        "",
        "Nitel abartı kuralının gerçek LLM çıktılarında tetiklendiği metinler ve insan etiketi: "
        + ("; ".join(f"`{mid}` ({', '.join(h)}) → {label}" for mid, h, label in report.overstatement_llm) or "yok")
        + ".",
        "",
        "### İzinli cümle başı listesi",
        "",
        f"Liste temiz taslaklardan çıkarıldı (`eval/lint_rates.py` `derive_frozen`): template anlatıcının "
        f"{report.samples} taslağı + gerçek LLM çıktıları ({report.llm_texts} metin; foundry-v3'te yalnızca insan "
        "etiketi `correct` olanlar). Cümlenin yer tutucuyla başlamayan ilk kelimesi alınır; home/away, sayı "
        "kelimesi, olay sözcüğü ve abartı ifadeleri listeye girmez. Sonuç `config.py`'ye donduruldu: "
        f"EN {allowed_en}; TR {allowed_tr}.",
        "",
        "Liste ölçüldüğü veriyi içerdiği için yukarıdaki oran iyimser. Dış-örneklem tahmini: liste yalnızca template "
        f"taslaklarından çıkarılsaydı (EN {', '.join(allowed_from['en']) or '—'}; TR "
        f"{', '.join(allowed_from['tr']) or '—'}) gerçek LLM çıktılarındaki {sentences} cümleden {flagged} tanesi "
        f"({_pct(flagged / sentences if sentences else None)}) reddedilirdi: {_tags(examples) or '—'}.",
        "",
        *render_overstatement_list(),
        *render_window_audit(report.corpus),
        *render_human_review(),
        "## Yeniden üretme",
        "",
        "```",
        ".venv/bin/python -m eval.inject",
        "```",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enjeksiyon değerlendirmesi (v2 ↔ v3 ↔ v4)")
    parser.add_argument("--quick", action="store_true", help="Küçük derlem")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)

    report = run_eval(QUICK_CORPUS if args.quick else FULL_CORPUS)
    print(render_table(report))
    print(f"\nslotify: v3 {report.slotified}/{report.samples}, v4 {report.slotified_v4}/{report.samples}")
    for variant in VARIANTS:
        print(f"Yakalanmayan ({variant}): " + (", ".join(r.spec.name for r in uncaught(report, variant)) or "yok"))
    if not args.no_write:
        Path(args.out).write_text(render_markdown(report), encoding="utf-8")
        print(f"Yazıldı: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
