"""Olay ifadeleri ve slot lint sözlükleri (foundry-v4).

`event_phrase`: bir olayın standart kısa ifadesi, yalnızca olay alanlarından (tip,
sonuç, oyuncu, data.reason / data.player_in, dakika). Model olay tipini ya da oyuncu
rolünü kendisi yazamaz; `{event:<id>}` yer tutucusu bu ifadeye render edilir. Veride
penaltıyı kurtaran oyuncu alanı yok: kurtarış ifadelerinde kaleci adı geçmez
(`save` olayı yalnızca takım adıyla anılır).

Sözlükler: olay tipi / rol sözcükleri (yer tutucu dışında yasak), nitel abartı
ifadeleri (moment tipi desteklemiyorsa yasak), cümle başı denetimi ve (foundry-v4.1)
moment tipine göre `{event:}` ile seçilebilir olay tipleri.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from app.generator.models import Event, EventType

from .template_narrator import fmt_minute

# --- olay ifadeleri ---------------------------------------------------------------------------

# (tip, sonuç) → (EN, TR). {p} oyuncu, {m} dakika, {in} oyuna giren, {team} takım.
# TR'de dakika parantez içinde: ek uyumu (22'de / 30'da) gerekmez.
_PHRASES: dict[tuple[str, str | None], tuple[str, str]] = {
    ("goal", None): ("{p} scored at {m}", "{p} gol attı ({m})"),
    ("shot", "goal"): ("{p} scored at {m}", "{p} gol attı ({m})"),
    ("shot", "saved"): ("{p} had a shot saved at {m}", "{p} şut çekti, kurtarıldı ({m})"),
    ("shot", "blocked"): ("{p} had a shot blocked at {m}", "{p} şut çekti, rakibe çarptı ({m})"),
    ("shot", "off_target"): ("{p} shot off target at {m}", "{p} şut çekti, isabet bulmadı ({m})"),
    ("penalty", "scored"): ("{p} scored a penalty at {m}", "{p} penaltıyı gole çevirdi ({m})"),
    ("penalty", "saved"): ("{p}'s penalty was saved at {m}", "{p} penaltı kullandı, vuruş kurtarıldı ({m})"),
    ("penalty", "missed"): ("{p} missed a penalty at {m}", "{p} penaltıyı kaçırdı ({m})"),
    ("red_card", "straight_red"): ("{p} was sent off at {m}", "{p} kırmızı kartla oyundan atıldı ({m})"),
    ("red_card", "second_yellow"): (
        "{p} was sent off for a second yellow at {m}", "{p} ikinci sarı karttan oyundan atıldı ({m})",
    ),
    ("red_card", None): ("{p} was sent off at {m}", "{p} kırmızı kartla oyundan atıldı ({m})"),
    ("yellow_card", None): ("{p} was booked at {m}", "{p} sarı kart gördü ({m})"),
    ("foul", None): ("{p} committed a foul at {m}", "{p} faul yaptı ({m})"),
    ("corner", None): ("{p} took a corner at {m}", "{p} korner kullandı ({m})"),
    ("pass", "success"): ("{p} completed a pass at {m}", "{p} pas verdi ({m})"),
    ("pass", "fail"): ("{p} lost the ball with a pass at {m}", "{p} pas denedi, top rakibe geçti ({m})"),
    ("dribble", "success"): ("{p} beat a defender at {m}", "{p} rakibini geçti ({m})"),
    ("dribble", "fail"): ("{p} was dispossessed at {m}", "{p} top kaybetti ({m})"),
    ("offside", None): ("{p} was caught offside at {m}", "{p} ofsayta düştü ({m})"),
    ("substitution", None): ("{in} came on for {p} at {m}", "{in}, {p} yerine oyuna girdi ({m})"),
    ("save", None): ("{team} made a save at {m}", "{team} kurtarış yaptı ({m})"),
}
NARRATABLE = frozenset(t for t, _ in _PHRASES)

# {event:} ile seçilebilir olay tipleri, moment tipine göre (foundry-v4.1). Pas, çalım, ofsayt,
# faul, korner, kurtarış hiçbir momentte seçilemez: momentin kendisini anlatmazlar.
_KEY_EVENTS = frozenset({"goal", "shot", "penalty", "red_card", "yellow_card", "substitution"})
SELECTABLE_EVENT_TYPES: dict[str, frozenset[str]] = {
    "goal": frozenset({"goal", "shot", "penalty"}),
    "score_change": frozenset({"goal", "shot", "penalty"}),
    "red_card": frozenset({"red_card", "yellow_card"}),
    "penalty": frozenset({"penalty"}),
    "pressure_shift": _KEY_EVENTS,
    "dominance_without_reward": _KEY_EVENTS,
}


def selectable(e: Event, moment_type: str) -> bool:
    """Olay bu moment tipinde {event:} ile anılabilir mi (bilinmeyen moment tipinde hayır)."""
    return e.type.value in SELECTABLE_EVENT_TYPES.get(moment_type, frozenset())


def _variant(e: Event) -> str | None:
    t = e.type.value
    if t == "red_card":
        return (e.data or {}).get("reason")
    if t in ("shot", "penalty", "pass", "dribble"):
        return e.outcome
    return None


def event_phrase(e: Event, teams: dict[str, str], language: str) -> str | None:
    """Olayın standart ifadesi; anlatılamayan tipte (maç başı, devre arası…) None."""
    key = (e.type.value, _variant(e))
    pair = _PHRASES.get(key) or _PHRASES.get((e.type.value, None))
    if pair is None:
        return None
    if e.type is EventType.SAVE:
        values = {"team": teams[e.team]} if e.team in teams else None
    else:
        values = {"p": e.player, "in": (e.data or {}).get("player_in")} if e.player else None
    if values is None or ("{in}" in pair[0] and not values.get("in")):
        return None
    template = pair[1] if language == "tr" else pair[0]
    return template.format(m=fmt_minute(e.period, e.minute), **values)


# --- sözlükler --------------------------------------------------------------------------------


def _fold(text: str) -> str:
    """Aynı uzunlukta küçük harf (TR büyük İ dahil)."""
    return text.replace("İ", "i").lower()


# Olay tipi ve oyuncu rolü sözcükleri: yer tutucu dışında yasak (olay bilgisi yalnızca {event:} ile).
# Metrik adları ({label:}) da bu yüzden ham yazılmaz ("shots", "şut"). "score" (isim) ve "skor" serbest.
EVENT_WORDS: dict[str, tuple[str, ...]] = {
    "en": (
        r"goals?", r"(?:goal)?keepers?", r"scor(?:ed|es|ing|ers?)", r"net(?:s|ted|ting)?",
        r"shots?", r"shoot\w*", r"strikes?", r"struck", r"fired", r"efforts?",
        r"penalt(?:y|ies)", r"spot[- ]kicks?", r"sav(?:e|ed|es|ing)", r"denied",
        r"miss(?:ed|es|ing)?", r"sent off", r"send(?:s|ing)? off", r"dismiss\w*", r"cards?",
        r"booked", r"booking", r"caution(?:ed)?", r"fouls?", r"fouled", r"tackl\w*", r"corners?",
        r"offsides?", r"substitut\w*", r"came on", r"equali[sz]\w*", r"level(?:led|ed|s|ling)?",
        r"conced\w*", r"assist\w*", r"header", r"headed", r"brace",
    ),
    "tr": (
        r"gol\w*", r"şut\w*", r"penaltı\w*", r"kurtar\w*", r"kaçır\w*", r"kart\w*", r"atıldı",
        r"ihraç\w*", r"faul\w*", r"korner\w*", r"ofsayt\w*", r"oyuna gir\w*", r"oyundan çık\w*",
        r"eşitle\w*", r"kaleci\w*", r"asist\w*", r"vuruş\w*", r"kafa vuruş\w*",
    ),
}

# Nitel abartı: (regex, destekleyen moment tipleri). Boş küme = her zaman yasak.
DOMINANCE = frozenset({"dominance_without_reward"})
PRESSURE = frozenset({"pressure_shift"})
OVERSTATEMENT: dict[str, tuple[tuple[str, frozenset[str]], ...]] = {
    "en": (
        (r"deep into", frozenset()),
        (r"dominat\w*|dominance", DOMINANCE),
        (r"(?:take|takes|took|taking|seiz\w*|in) control", PRESSURE),
        (r"momentum", PRESSURE),
        (r"on top", DOMINANCE | PRESSURE),
        (r"stunning|sensational|incredible|brilliant|superb|spectacular|magnificent|dramatic|thrilling",
         frozenset()),
        (r"relentless\w*|siege|battered|bombard\w*|r[au]n riot|rampant", frozenset()),
        (r"against the run of play", frozenset()),
        (r"last[- ]gasp|at the death|dying (?:seconds|minutes)", frozenset()),
        (r"winner|winning goal|sealed|clinch\w*|decisive|crucial|killer", frozenset()),
        (r"totally|completely|utterly|absolutely", frozenset()),
        (r"comfortabl\w*|cruis\w*|stroll\w*", frozenset()),
        (r"deserv\w*|undeserv\w*", frozenset()),
    ),
    "tr": (
        (r"domine\w*|hükmet\w*|ezici|üstünlük kur\w*", DOMINANCE),
        (r"kontrol\w*", PRESSURE),
        (r"muhteşem|inanılmaz|harika|mükemmel|nefes kesen|dramatik|çılgın", frozenset()),
        (r"son nefes\w*|son saniye\w*|uzatmaların derin\w*|derinlerinde", frozenset()),
        (r"galibiyet golü|maçı kopar\w*|fişi çek\w*|kritik", frozenset()),
        (r"tamamen|kesinlikle|bütünüyle", frozenset()),
        (r"rahat\w*", frozenset()),
        (r"hak e[dt]\w*", frozenset()),
        (r"abluka\w*", frozenset()),
    ),
}


def _compile(patterns: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"(?<!\w)(?:" + "|".join(patterns) + r")(?!\w)")


EVENT_WORD_RE = {lang: _compile(p) for lang, p in EVENT_WORDS.items()}
OVERSTATEMENT_RE = {
    lang: [(_compile((p,)), types) for p, types in entries] for lang, entries in OVERSTATEMENT.items()
}


def _langs(language: str | None) -> tuple[str, ...]:
    return (language,) if language in EVENT_WORDS else tuple(EVENT_WORDS)


def event_word_spans(text: str, language: str | None) -> list[tuple[int, int]]:
    scan = _fold(text)
    return sorted({(m.start(), m.end()) for lang in _langs(language) for m in EVENT_WORD_RE[lang].finditer(scan)})


def overstatement_spans(text: str, language: str | None, moment_type: str | None) -> list[tuple[int, int]]:
    """Moment tipinin desteklemediği abartı ifadeleri."""
    scan = _fold(text)
    found = set()
    for lang in _langs(language):
        for pattern, supported in OVERSTATEMENT_RE[lang]:
            if moment_type in supported:
                continue
            found |= {(m.start(), m.end()) for m in pattern.finditer(scan)}
    return sorted(found)


# --- cümle başı -------------------------------------------------------------------------------

SENTENCE_END_RE = re.compile(r"[.!?]+\s+(?=[^\s])")
FIRST_WORD_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")


def sentence_starts(text: str) -> Iterator[int]:
    """Cümle başı konumları: metin başı ve [.!?] + boşluktan sonra küçük harfle başlamayan yer.

    Küçük harfle devam eden nokta cümle sonu sayılmaz (TR sıra sayısı: "45. dakikada").
    Yer tutucular çağıran tarafından büyük harfle maskelenmiş olmalı.
    """
    if text.strip():
        yield len(text) - len(text.lstrip())
    for m in SENTENCE_END_RE.finditer(text):
        if not text[m.end()].islower():
            yield m.end()


def first_word(text: str, pos: int) -> tuple[int, int, str] | None:
    """`pos`taki cümlenin ilk kelimesi; baştaki noktalama ("—", "(", tırnak) atlanır."""
    m = FIRST_WORD_RE.search(text, pos)
    if m is None:
        return None
    if any(c.isalnum() for c in text[pos:m.start()]):
        return None  # cümle sayı ya da yer tutucuyla başlıyor
    return m.start(), m.end(), m.group()
