"""Enjeksiyon değerlendirmesi: anlatım hattı (lint + verify_claim) hangi hataları yakalıyor?

Template anlatıcının doğru taslaklarından (metin + iddialar) başlar, her hata
türünü deterministik olarak enjekte eder ve `check_draft`'ın yakalama oranını
yazıyla sayı denetimi kapalı (düzeltme öncesi) ve açık (sonrası) ölçer.

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
from app.analytics.moments import Moment
from app.explain.claims import Claim
from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.narrator import TemplateNarrator
from app.explain.pipeline import check_draft
from app.explain.text_lint import AMBIGUOUS_NUMBER_WORDS, NUMBER_RE, NUMBER_WORDS, Roster
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


@dataclass(frozen=True)
class Injection:
    text: str
    claims: tuple[Claim, ...]
    note: str | None = None  # kaçarsa dağılımda gösterilecek alt neden


Injector = Callable[[Sample, random.Random, Sequence[str]], Injection | None]


# --- yardımcılar ------------------------------------------------------------------


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


def _swap_player(sample: Sample, rng: random.Random, pool: Sequence[str]) -> Injection | None:
    mentioned = [p for p in sample.players if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", sample.text)]
    claimed = {c.subject.player for c in sample.claims}
    candidates = [p for p in pool if p not in claimed and p not in sample.text]
    if not mentioned or not candidates:
        return None
    old, new = rng.choice(mentioned), rng.choice(candidates)
    return Injection(re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", new, sample.text), sample.claims)


# --- enjeksiyonlar ------------------------------------------------------------------


def inject_control(s: Sample, rng: random.Random, foreign: Sequence[str]) -> Injection | None:
    return Injection(s.text, s.claims)


def inject_number_text(s: Sample, rng: random.Random, foreign: Sequence[str]) -> Injection | None:
    tokens = list(NUMBER_RE.finditer(_masked(s)))
    if not tokens:
        return None
    m = rng.choice(tokens)
    return Injection(_splice(s.text, m.start(), m.end(), _bumped_number(m)), s.claims)


def inject_number_text_and_claim(s: Sample, rng: random.Random, foreign: Sequence[str]) -> Injection | None:
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


def inject_player_swap(s: Sample, rng: random.Random, foreign: Sequence[str]) -> Injection | None:
    return _swap_player(s, rng, s.players)


def inject_foreign_player(s: Sample, rng: random.Random, foreign: Sequence[str]) -> Injection | None:
    outsiders = [p for p in foreign if p not in s.players]
    return _swap_player(s, rng, outsiders)


def inject_unsupported_sentence_number(s: Sample, rng: random.Random, foreign: Sequence[str]) -> Injection | None:
    extra = UNSUPPORTED_NUMBER[s.lang].format(team=s.teams[s.moment.team], n=_unused_number(s.claims))
    return Injection(f"{s.text} {extra}", s.claims)


def inject_unsupported_sentence_qualitative(s: Sample, rng: random.Random, foreign: Sequence[str]) -> Injection | None:
    extra = UNSUPPORTED_QUALITATIVE[s.lang].format(team=s.teams[s.moment.team])
    return Injection(f"{s.text} {extra}", s.claims)


def inject_number_words(s: Sample, rng: random.Random, foreign: Sequence[str]) -> Injection | None:
    tokens = [m for m in NUMBER_RE.finditer(_masked(s)) if m.group("int") and int(m.group("int")) < 20]
    if not tokens:
        return None
    m = rng.choice(tokens)
    word = NUMBER_WORDS[s.lang][int(m.group("int")) + 1]  # yanlış değer, yazıyla
    note = (
        "belirsiz kelime, ardında sayılabilir isim yok"
        if word in AMBIGUOUS_NUMBER_WORDS[s.lang]
        else "değer başka bir iddiada geçiyor"
    )
    return Injection(_splice(s.text, m.start(), m.end(), word), s.claims, note)


def inject_sentence_start_fabricated(s: Sample, rng: random.Random, foreign: Sequence[str]) -> Injection | None:
    return Injection(f"{FABRICATED_START[s.lang]} {s.text}", s.claims)


@dataclass(frozen=True)
class InjectionType:
    name: str
    description: str
    inject: Injector
    miss_reason: str  # yakalanmazsa neden


INJECTION_TYPES = (
    InjectionType("control", "Değişiklik yok (yanlış alarm ölçümü)", inject_control, "—"),
    InjectionType(
        "number_text", "Metindeki bir sayı değişir, iddialar aynı kalır", inject_number_text,
        "Yeni sayı tesadüfen başka bir iddianın değeri ya da dakikasıyla aynı. Lint, sayının "
        "hangi iddiaya ait olduğuna değil, herhangi bir iddiada geçip geçmediğine bakar.",
    ),
    InjectionType(
        "number_text_and_claim", "Metin ve ilgili iddia birlikte yanlış değere değişir",
        inject_number_text_and_claim,
        "Değişen iddia bir eşitsizlik (`score_margin lte 0` → `lte 1`) ve gevşetilmiş hâliyle "
        "hâlâ doğru; metinde değişen sayı da bu iddianın yeni değerine denk geldiği için lint de "
        "geçiyor. Verify değerin doğruluğunu ölçer, sınırın ne kadar sıkı olduğunu değil.",
    ),
    InjectionType(
        "player_swap", "Oyuncu adı aynı maçtan iddiasız başka bir oyuncuyla değişir",
        inject_player_swap, "—",
    ),
    InjectionType(
        "foreign_player", "Oyuncu adı başka maçın oyuncusuyla değişir", inject_foreign_player,
        "Yabancı oyuncunun soyadı iddiadaki oyuncunun soyadıyla aynı (örn. \"Tamsel Selvado\" ↔ "
        "\"Davel Selvado\"). Soyad, iddialı oyuncunun takma adı olarak destekli sayılıyor; ad ise "
        "\"—\" sonrası cümle başında olduğu için tek kelimelik isim denetimine girmiyor.",
    ),
    InjectionType(
        "unsupported_sentence_number", "İddiasız, sayı içeren yeni cümle eklenir",
        inject_unsupported_sentence_number, "—",
    ),
    InjectionType(
        "unsupported_sentence_qualitative", "İddiasız, nitel yeni cümle eklenir (sayı/yeni isim yok)",
        inject_unsupported_sentence_qualitative,
        "Cümlede ne sayı ne de yeni bir isim var. Lint yalnızca sayıları ve isimleri denetler, "
        "verify_claim de yalnızca Claim listesini doğrular; nitel yargılar kapsam dışında.",
    ),
    InjectionType(
        "number_words", "Bir tamsayı, yanlış değerin yazısıyla değişir (\"two\", \"iki\")",
        inject_number_words,
        "Yazıyla yazılan değer tesadüfen başka bir iddiada geçiyor; ya da belirsiz kelime "
        "(TR \"bir\", EN \"one\") sayılabilir bir isimden önce gelmediği için sayı sayılmıyor.",
    ),
    InjectionType(
        "sentence_start_fabricated", "Başa uydurma isimli cümle eklenir (\"Quintana scores.\")",
        inject_sentence_start_fabricated,
        "Cümle başındaki tek büyük harfli kelime isim olarak değerlendirilmiyor (cümle başı "
        "büyük harfi normal). Kadroda olmayan tek kelimelik isim bu konumda fark edilmiyor.",
    ),
)


# --- ölçüm ---------------------------------------------------------------------------


@dataclass
class TypeResult:
    spec: InjectionType
    applicable: int = 0
    caught_before: int = 0
    caught_after: int = 0
    by_lint: int = 0
    by_verify: int = 0
    missed_example: tuple[str, str] | None = None  # (orijinal, enjekte) — düzeltme sonrası kaçan
    miss_notes: Counter[str] = field(default_factory=Counter)

    def rate(self, caught: int) -> float:
        return caught / self.applicable if self.applicable else 0.0


@dataclass
class EvalReport:
    corpus: list[tuple[int, str | None]]
    samples: int
    results: list[TypeResult] = field(default_factory=list)


def _rng(moment: Moment, type_name: str, lang: str) -> random.Random:
    digest = hashlib.sha256(f"{moment.id}|{type_name}|{lang}".encode()).hexdigest()
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
                samples.append(Sample(events, roster, players, teams, m, lang, d.text, d.claims))
    return samples, all_players


def run_eval(
    corpus: Sequence[tuple[int, str | None]] = FULL_CORPUS,
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
) -> EvalReport:
    samples, all_players = build_samples(corpus)
    before = replace(config, lint_number_words=False)
    report = EvalReport(list(corpus), len(samples))
    for spec in INJECTION_TYPES:
        result = TypeResult(spec)
        for s in samples:
            inj = spec.inject(s, _rng(s.moment, spec.name, s.lang), all_players)
            if inj is None:
                continue
            result.applicable += 1
            items_b, _, _ = check_draft(inj.text, inj.claims, s.events, s.roster, before, s.lang)
            items, issues, verdicts = check_draft(inj.text, inj.claims, s.events, s.roster, config, s.lang)
            result.caught_before += bool(items_b)
            result.caught_after += bool(items)
            result.by_lint += bool(issues)
            result.by_verify += any(not v.ok for v in verdicts)
            if not items and spec.name != "control":
                if result.missed_example is None:
                    result.missed_example = (s.text, inj.text)
                if inj.note:
                    result.miss_notes[inj.note] += 1
        report.results.append(result)
    return report


# --- rapor ---------------------------------------------------------------------------


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def render_table(report: EvalReport) -> str:
    lines = [
        "| Tür | Enjeksiyon | N | Önce | Sonra | Lint | Verify |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in report.results:
        lines.append(
            f"| `{r.spec.name}` | {r.spec.description} | {r.applicable} | "
            f"{_pct(r.rate(r.caught_before))} | {_pct(r.rate(r.caught_after))} | "
            f"{_pct(r.rate(r.by_lint))} | {_pct(r.rate(r.by_verify))} |"
        )
    return "\n".join(lines)


def uncaught(report: EvalReport) -> list[TypeResult]:
    return [r for r in report.results if r.spec.name != "control" and r.caught_after < r.applicable]


def render_markdown(report: EvalReport) -> str:
    control = next(r for r in report.results if r.spec.name == "control")
    corpus = ", ".join(f"{sc or 'senaryosuz'}/{seed}" for seed, sc in report.corpus)
    out = [
        "# Enjeksiyon değerlendirmesi",
        "",
        "Anlatım hattının (text_lint + verify_claim) kontrollü hataları yakalama oranı. "
        "Bu dosya `python -m eval.inject` ile üretilir; elle düzenlemeyin.",
        "",
        "## Yöntem",
        "",
        "- Başlangıç: template anlatıcının doğru taslakları (metin + iddialar), tüm momentler, EN ve TR.",
        f"- Derlem: {len(report.corpus)} maç, {report.samples} taslak. Maçlar: {corpus}.",
        "- Her hata türü her taslağa deterministik olarak (moment id + tür + dil seed'li) enjekte edilir; "
        "uygulanamadığı taslaklar (örn. metinde oyuncu adı yoksa) N'ye girmez.",
        "- **Yakalandı** = `check_draft` en az bir lint ya da verify hatası döndürdü; pipeline bu durumda "
        "taslağı yayınlamaz, geri bildirimle yeniden dener ya da template yedeğine düşer.",
        "- **Önce** = yazıyla sayı denetimi kapalı (`lint_number_words=False`), **Sonra** = açık (mevcut "
        "varsayılan). Lint/Verify sütunları düzeltme sonrası, hangi katmanın uyardığını gösterir "
        "(ikisi birden uyarabilir).",
        "",
        "## Sonuçlar",
        "",
        render_table(report),
        "",
        f"Yanlış alarm (control): {control.caught_after}/{control.applicable}.",
        "",
        "## Yakalanmayan türler",
        "",
    ]
    misses = uncaught(report)
    if not misses:
        out.append("Yok: tüm türler %100 yakalandı.")
    for r in misses:
        out += [
            f"### `{r.spec.name}`: {_pct(r.rate(r.caught_after))} yakalandı "
            f"({r.applicable - r.caught_after}/{r.applicable} kaçtı)",
            "",
            f"**Neden:** {r.spec.miss_reason}",
            "",
        ]
        if r.miss_notes:
            out += ["Kaçış dağılımı:", ""]
            out += [f"- {note}: {n}" for note, n in sorted(r.miss_notes.items(), key=lambda kv: (-kv[1], kv[0]))]
            out.append("")
        if r.missed_example:
            original, injected = r.missed_example
            out += ["Örnek:", "", f"- Orijinal: {original}", f"- Enjekte: {injected}", ""]
    out += [
        "## Yapılan düzeltme",
        "",
        "Yalnızca yazıyla yazılmış sayılar lint'e eklendi (EN zero–twenty, TR sıfır–yirmi, "
        "\"on bir\" gibi çok kelimeliler dahil). Kural rakamla yazılmış tamsayıyla aynı: değer bir "
        "iddiada geçmeli. Sayı dışında da sık kullanılan kelimeler (TR \"bir\", \"yedi\", \"altı\"; "
        "EN \"one\") yalnızca ardından sayılabilir bir isim (gol, şut, goal, shot…) gelirse sayı "
        "sayılır. Diğer açıklar bilinçli olarak kapatılmadı.",
        "",
        "## Yeniden üretme",
        "",
        "```",
        ".venv/bin/python -m eval.inject",
        "```",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Anlatım hattı enjeksiyon değerlendirmesi")
    parser.add_argument("--quick", action="store_true", help="Küçük derlem")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)

    report = run_eval(QUICK_CORPUS if args.quick else FULL_CORPUS)
    print(render_table(report))
    misses = uncaught(report)
    print("\nYakalanmayan türler: " + (", ".join(r.spec.name for r in misses) or "yok"))
    if not args.no_write:
        Path(args.out).write_text(render_markdown(report), encoding="utf-8")
        print(f"Yazıldı: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
