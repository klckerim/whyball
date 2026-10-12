"""Gerçek LLM ölçümü: üç demo maçı FoundryNarrator ile anlatır ve raporu üretir.

    python -m eval.llm_run [--lang en]           # modeli çağırır → docs/LLM_RUN.json + .md
    python -m eval.llm_run --from-json docs/LLM_RUN.json   # yalnızca yeniden render

Rapor (docs/LLM_RUN.md) her zaman ham çalıştırma çıktısından (JSON) üretilir;
elle yazılmaz. Önbellek kullanılmaz: her moment gerçekten modele gider.
"""

from __future__ import annotations

import argparse
import json
import logging
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


# --- toplama -------------------------------------------------------------------------------


def rejections(record: NarrationRecord) -> list[dict[str, Any]]:
    """Deneme bazında ret kodları: feedback kodları ya da (geri bildirimsiz) anlatıcı hatası."""
    by_attempt: dict[int, list[str]] = {}
    for step in record.trace:
        if step["step"] == "feedback":
            by_attempt[step["attempt"]] = list(step["codes"])
        elif step["step"] == "narrate" and not step["ok"]:
            by_attempt.setdefault(step["attempt"], [step["error"]])
    return [{"attempt": a, "codes": codes} for a, codes in sorted(by_attempt.items())]


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
    return {
        "moments": len(moments),
        "first_try": sum(m["source"] != "template_fallback" and m["attempts"] == 1 for m in moments),
        "after_retry": sum(m["source"] != "template_fallback" and m["attempts"] > 1 for m in moments),
        "fallback": sum(m["source"] == "template_fallback" for m in moments),
        "calls": len(usage),
        "input_tokens": sum(u["input_tokens"] or 0 for u in usage),
        "output_tokens": sum(u["output_tokens"] or 0 for u in usage),
        "reasoning_tokens": sum(u.get("reasoning_tokens") or 0 for u in usage),
        "avg_ms": sum(latencies) / len(latencies) if latencies else 0.0,
        "max_ms": max(latencies) if latencies else 0,
    }


def _total(summaries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    keys = ("moments", "first_try", "after_retry", "fallback", "calls",
            "input_tokens", "output_tokens", "reasoning_tokens")
    total = {k: sum(s[k] for s in summaries) for k in keys}
    weighted = sum(s["avg_ms"] * s["calls"] for s in summaries)
    total["avg_ms"] = weighted / total["calls"] if total["calls"] else 0.0
    total["max_ms"] = max((s["max_ms"] for s in summaries), default=0)
    return total


# --- rapor ---------------------------------------------------------------------------------


def _share(n: int, total: int) -> str:
    return f"{n} ({n / total * 100:.1f}%)" if total else "0"


def _minute(m: dict[str, Any]) -> str:
    if m["period"] == 1 and m["minute"] >= 45:
        return f"45+{m['minute'] - 44}'"
    if m["period"] == 2 and m["minute"] >= 90:
        return f"90+{m['minute'] - 89}'"
    return f"{m['minute']}'"


def _codes(codes: Sequence[str]) -> str:
    counts = Counter(codes)
    return ", ".join(f"`{c}`" + (f"×{n}" if n > 1 else "") for c, n in counts.items())


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
        f"- Model: `{meta['model']}` · Prompt sürümü: `{meta['prompt_version']}` · Dil: `{meta['lang']}`",
        f"- Çalıştırma: {meta['started_at']} – {meta['finished_at']} (UTC)",
        f"- Ayarlar: çalıştırma (maç) başına en fazla {meta['max_calls_per_run']} çağrı, "
        f"`max_output_tokens` {meta['max_tokens']}, çağrı zaman aşımı {meta['timeout_s']:g} sn, "
        f"en fazla {meta['max_retries']} yeniden deneme, önbellek kapalı",
        "- Her taslak text_lint + verify_claim'den geçti; geçmeyen yayınlanmadı ve template yedeğine düştü.",
        "",
        "## Özet",
        "",
        "| Maç | Moment | İlk denemede geçen | Yeniden denemeyle geçen | Yedeğe düşen | Çağrı "
        "| Token giriş / çıkış (reasoning) | Ort. süre | Maks. süre |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, s in rows:
        n = s["moments"]
        out.append(
            f"| {name} | {n} | {_share(s['first_try'], n)} | {_share(s['after_retry'], n)} | "
            f"{_share(s['fallback'], n)} | {s['calls']} | {s['input_tokens']} / {s['output_tokens']} "
            f"({s['reasoning_tokens']}) | {s['avg_ms'] / 1000:.1f} sn | {s['max_ms'] / 1000:.1f} sn |"
        )

    out += ["", "## Yedeğe düşen momentler", ""]
    fallbacks = [(m["match_id"], mo) for m in run["matches"] for mo in m["moments"]
                 if mo["source"] == "template_fallback"]
    if not fallbacks:
        out.append("Yok.")
    else:
        out += [
            "| Maç | Moment | Tip | Dakika | Yedek sebebi | Deneme bazında ret kodları |",
            "|---|---|---|---|---|---|",
        ]
        for match_id, mo in fallbacks:
            per_attempt = "; ".join(f"#{r['attempt']}: {_codes(r['codes'])}" for r in mo["rejections"])
            out.append(
                f"| {match_id} | {mo['id'].rsplit('-', 1)[-1]} | {mo['type']} | {_minute(mo)} | "
                f"`{mo['fallback_reason']}` | {per_attempt} |"
            )
        all_codes = Counter(c for _, mo in fallbacks for r in mo["rejections"] for c in r["codes"])
        out += ["", "Yedeğe düşen momentlerde ret kodu sıklığı: " + _codes(list(all_codes.elements()))]

    out += ["", "## Moment ayrıntıları", ""]
    for m in run["matches"]:
        out += [f"### {m['match_id']}", "", "| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin |",
                "|---|---|---|---|---:|---|"]
        for mo in m["moments"]:
            text = mo["text"].replace("|", "\\|")
            out.append(
                f"| {mo['id'].rsplit('-', 1)[-1]} | {mo['type']} | {_minute(mo)} | {mo['source']} | "
                f"{mo['attempts']} | {text} |"
            )
        out.append("")
    return "\n".join(out)


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
        },
        "matches": matches,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gerçek LLM ile üç demo maç ölçümü")
    parser.add_argument("--lang", choices=("en", "tr"), default="en")
    parser.add_argument("--from-json", help="Modeli çağırmadan bu ham çıktıdan yeniden render et")
    parser.add_argument("--out-json", default=str(DEFAULT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_MD))
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
    print(f"Yazıldı: {args.out_md}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
