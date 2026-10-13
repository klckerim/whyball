"""Gerçek LLM ölçümü: üç demo maçı FoundryNarrator ile anlatır ve raporu üretir.

    python -m eval.llm_run [--lang en]           # modeli çağırır → docs/LLM_RUN.json + .md + human_review.csv
    python -m eval.llm_run --from-json docs/LLM_RUN.json   # yalnızca yeniden render

Rapor (docs/LLM_RUN.md) ve insan değerlendirme tablosu (docs/human_review.csv)
her zaman ham çalıştırma çıktısından (JSON) üretilir; elle yazılmaz. Önbellek
kullanılmaz: her moment gerçekten modele gider.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import statistics
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.analytics.moments import Moment
from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.pipeline import NarrationRecord, run_match
from app.generator.freeze import demo_paths
from app.generator.models import read_jsonl

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = REPO_ROOT / "docs" / "LLM_RUN.json"
DEFAULT_MD = REPO_ROOT / "docs" / "LLM_RUN.md"
DEFAULT_CSV = REPO_ROOT / "docs" / "human_review.csv"
REVIEW_COLUMNS = ("moment_id", "text", "correct", "wrong_fact", "misleading", "dull")


# --- toplama -------------------------------------------------------------------------------


def rejections(record: NarrationRecord) -> list[dict[str, Any]]:
    """Deneme bazında ret kodları ve (varsa) anlatıcı hata mesajı."""
    by_attempt: dict[int, dict[str, Any]] = {}
    for step in record.trace:
        if step["step"] == "narrate" and not step["ok"]:
            by_attempt[step["attempt"]] = {
                "attempt": step["attempt"], "codes": [step["error"]], "message": step.get("message"),
            }
        elif step["step"] == "feedback":
            entry = by_attempt.setdefault(step["attempt"], {"attempt": step["attempt"], "message": None})
            entry["codes"] = list(step["codes"])
    return [by_attempt[a] for a in sorted(by_attempt)]


def collect_match(
    match_id: str, results: Sequence[tuple[Moment, NarrationRecord]], usage: Sequence[Any]
) -> dict[str, Any]:
    moments = []
    for m, r in results:
        fallback = r.source == "template_fallback"
        moments.append({
            "id": m.id,
            "type": m.type,
            "period": m.period,
            "minute": m.minute,
            "second": m.second,
            "source": r.source,
            "attempts": r.attempts,
            "ok": r.ok,
            "text": r.text,
            "template": r.template,
            "fallback_reason": r.trace[-1].get("reason") if fallback else None,
            "rejections": rejections(r),
        })
    return {
        "match_id": match_id,
        "moments": moments,
        "usage": [asdict(u) if not isinstance(u, dict) else u for u in usage],
    }


def summarize(match: dict[str, Any]) -> dict[str, Any]:
    moments, usage = match["moments"], match["usage"]
    latencies = [u["latency_ms"] for u in usage]
    output = sum(u["output_tokens"] or 0 for u in usage)
    reasoning = sum(u.get("reasoning_tokens") or 0 for u in usage)
    return {
        "moments": len(moments),
        "first_try": sum(m["source"] != "template_fallback" and m["attempts"] == 1 for m in moments),
        "after_retry": sum(m["source"] != "template_fallback" and m["attempts"] > 1 for m in moments),
        "fallback": sum(m["source"] == "template_fallback" for m in moments),
        "calls": len(usage),
        "input_tokens": sum(u["input_tokens"] or 0 for u in usage),
        "output_tokens": output,
        "reasoning_tokens": reasoning,
        "latencies": latencies,
    }


def _total(summaries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    keys = ("moments", "first_try", "after_retry", "fallback", "calls",
            "input_tokens", "output_tokens", "reasoning_tokens")
    total: dict[str, Any] = {k: sum(s[k] for s in summaries) for k in keys}
    total["latencies"] = [ms for s in summaries for ms in s["latencies"]]
    return total


# --- rapor ---------------------------------------------------------------------------------


def _share(n: int, total: int) -> str:
    return f"{n} ({n / total * 100:.1f}%)" if total else "0"


def _sec(ms: float) -> str:
    return f"{ms / 1000:.1f} sn"


def _minute(m: dict[str, Any]) -> str:
    if m["period"] == 1 and m["minute"] >= 45:
        return f"45+{m['minute'] - 44}'"
    if m["period"] == 2 and m["minute"] >= 90:
        return f"90+{m['minute'] - 89}'"
    return f"{m['minute']}'"


def _codes(codes: Sequence[str]) -> str:
    counts = Counter(codes)
    return ", ".join(f"`{c}`" + (f"×{n}" if n > 1 else "") for c, n in counts.items())


def _cell(text: str | None) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def _short(moment_id: str) -> str:
    return moment_id.rsplit("-", 1)[-1]


def render_report(run: dict[str, Any]) -> str:
    meta = run["meta"]
    summaries = [summarize(m) for m in run["matches"]]
    rows = [(m["match_id"], s) for m, s in zip(run["matches"], summaries)]
    rows.append(("**Toplam**", _total(summaries)))

    out = [
        "# LLM anlatım ölçümü (gerçek model)",
        "",
        "Bu dosya `python -m eval.llm_run` çalıştırmasının ham çıktısından (`docs/LLM_RUN.json`) "
        "üretilir; elle düzenlemeyin.",
        "",
        f"- Model: `{meta['model']}` · Prompt sürümü: `{meta['prompt_version']}` · Dil: `{meta['lang']}` "
        f"· Reasoning çabası: `{meta.get('reasoning_effort') or 'varsayılan'}`",
        f"- Çalıştırma: {meta['started_at']} – {meta['finished_at']} (UTC)",
        f"- Ayarlar: çalıştırma (maç) başına en fazla {meta['max_calls_per_run']} çağrı, "
        f"`max_output_tokens` {meta['max_tokens']}, çağrı zaman aşımı {meta['timeout_s']:g} sn, "
        f"en fazla {meta['max_retries']} yeniden deneme, önbellek kapalı",
        "- Her taslak lint + yer tutucu bağlama + verify_claim'den geçti; geçmeyen yayınlanmadı ve "
        "template yedeğine düştü. Yayınlanan LLM metinlerinde somut değerleri kod render etti.",
        "",
        "## Özet",
        "",
        "| Maç | Moment | İlk denemede geçen | Yeniden denemeyle geçen | Yedeğe düşen | Çağrı "
        "| Token giriş / çıkış | Reasoning (çıkışın %'si) | Ort. süre | Medyan | Maks. |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, s in rows:
        n, lat = s["moments"], s["latencies"]
        ratio = s["reasoning_tokens"] / s["output_tokens"] * 100 if s["output_tokens"] else 0.0
        out.append(
            f"| {name} | {n} | {_share(s['first_try'], n)} | {_share(s['after_retry'], n)} | "
            f"{_share(s['fallback'], n)} | {s['calls']} | {s['input_tokens']} / {s['output_tokens']} | "
            f"{s['reasoning_tokens']} ({ratio:.1f}%) | "
            f"{_sec(statistics.fmean(lat)) if lat else '—'} | "
            f"{_sec(statistics.median(lat)) if lat else '—'} | {_sec(max(lat)) if lat else '—'} |"
        )

    out += ["", "## Yedeğe düşen momentler", ""]
    fallbacks = [(m["match_id"], mo) for m in run["matches"] for mo in m["moments"]
                 if mo["source"] == "template_fallback"]
    if not fallbacks:
        out.append("Yok.")
    else:
        out += ["| Maç | Moment | Tip | Dakika | Yedek sebebi | Deneme bazında ret kodları |",
                "|---|---|---|---|---|---|"]
        for match_id, mo in fallbacks:
            per_attempt = "; ".join(f"#{r['attempt']}: {_codes(r['codes'])}" for r in mo["rejections"])
            out.append(f"| {match_id} | {_short(mo['id'])} | {mo['type']} | {_minute(mo)} | "
                       f"`{mo['fallback_reason']}` | {per_attempt} |")
        all_codes = Counter(c for _, mo in fallbacks for r in mo["rejections"] for c in r["codes"])
        out += ["", "Yedeğe düşen momentlerde ret kodu sıklığı: " + _codes(list(all_codes.elements()))]

    out += ["", "## Yeniden denemeyle geçen momentler", ""]
    retried = [(m["match_id"], mo) for m in run["matches"] for mo in m["moments"]
               if mo["source"] != "template_fallback" and mo["attempts"] > 1]
    if not retried:
        out.append("Yok.")
    else:
        out += ["| Maç | Moment | Tip | Deneme | Reddedilen denemeler |", "|---|---|---|---:|---|"]
        for match_id, mo in retried:
            per_attempt = "; ".join(f"#{r['attempt']}: {_codes(r['codes'])}" for r in mo["rejections"])
            out.append(f"| {match_id} | {_short(mo['id'])} | {mo['type']} | {mo['attempts']} | {per_attempt} |")

    out += ["", "## İstemci hataları", ""]
    errors = [(m["match_id"], u) for m in run["matches"] for u in m["usage"] if u.get("error")]
    if not errors:
        out.append("Yok.")
    else:
        out += ["| Maç | Moment | Çağrı | Sonuç | Mesaj |", "|---|---|---:|---|---|"]
        for match_id, u in errors:
            out.append(f"| {match_id} | {_short(u['moment_id'])} | {u['call']} | `{u['outcome']}` | "
                       f"{_cell(u['error'])} |")

    out += ["", "## Moment ayrıntıları", ""]
    for m in run["matches"]:
        out += [f"### {m['match_id']}", "",
                "| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |",
                "|---|---|---|---|---:|---|---|"]
        for mo in m["moments"]:
            template = f"`{_cell(mo.get('template'))}`" if mo.get("template") else "—"
            out.append(f"| {_short(mo['id'])} | {mo['type']} | {_minute(mo)} | {mo['source']} | "
                       f"{mo['attempts']} | {_cell(mo['text'])} | {template} |")
        out.append("")
    return "\n".join(out)


# --- insan değerlendirmesi --------------------------------------------------------------------


def review_rows(run: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"moment_id": mo["id"], "text": mo["text"], "correct": "", "wrong_fact": "", "misleading": "", "dull": ""}
        for m in run["matches"] for mo in m["moments"] if mo["text"]
    ]


def _has_annotations(path: Path) -> bool:
    with path.open(encoding="utf-8", newline="") as fp:
        return any(
            (row.get(col) or "").strip()
            for row in csv.DictReader(fp) for col in REVIEW_COLUMNS[2:]
        )


def write_human_review(run: dict[str, Any], path: Path, stamp: str | None = None) -> Path:
    """CSV yazar; elle doldurulmuş bir dosyanın üzerine yazmaz (yanına zaman damgalı yazar)."""
    target = path
    if path.exists() and _has_annotations(path):
        stamp = stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = path.with_name(f"{path.stem}.{stamp}{path.suffix}")
        print(f"UYARI: {path} elle doldurulmuş; üzerine yazılmadı → {target}", file=sys.stderr)
    with target.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(review_rows(run))
    return target


# --- çalıştırma ----------------------------------------------------------------------------


def run_live(lang: str, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG) -> dict[str, Any]:
    from app.explain.llm_narrator import foundry_narrator_from_env

    started = datetime.now(UTC).isoformat(timespec="seconds")
    matches, model, prompt_version = [], None, None
    for _, _, path in demo_paths():
        events = read_jsonl(path)
        narrator = foundry_narrator_from_env(events, config)
        model, prompt_version = narrator.model_tag, narrator.prompt_version
        print(f"== {path.stem}", file=sys.stderr)
        try:
            results = run_match(events, narrator, language=lang, cache=None, config=config)
        finally:
            narrator.close()
        matches.append(collect_match(path.stem, results, narrator.usage))
    return {
        "meta": {
            "model": model,
            "prompt_version": prompt_version,
            "lang": lang,
            "started_at": started,
            "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "max_calls_per_run": config.llm_max_calls_per_run,
            "max_tokens": config.llm_max_tokens,
            "timeout_s": config.llm_timeout_s,
            "max_retries": config.max_retries,
            "reasoning_effort": config.llm_reasoning_effort,
        },
        "matches": matches,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gerçek LLM ile üç demo maç ölçümü")
    parser.add_argument("--lang", choices=("en", "tr"), default="en")
    parser.add_argument("--from-json", help="Modeli çağırmadan bu ham çıktıdan yeniden render et")
    parser.add_argument("--out-json", default=str(DEFAULT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_MD))
    parser.add_argument("--out-csv", default=str(DEFAULT_CSV))
    args = parser.parse_args(argv)

    if args.from_json:
        run = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    else:
        logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)
        logging.getLogger("whyball.llm").setLevel(logging.INFO)
        run = run_live(args.lang)
        Path(args.out_json).write_text(
            json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Yazıldı: {args.out_json}", file=sys.stderr)
    Path(args.out_md).write_text(render_report(run), encoding="utf-8")
    csv_path = write_human_review(run, Path(args.out_csv))
    print(f"Yazıldı: {args.out_md}, {csv_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
