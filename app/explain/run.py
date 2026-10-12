"""CLI: anlatım hattını çalıştırır, her momentin sonucunu ve izini yazar.

python -m app.explain.run --input data/demo/red_card_swing_seed42.jsonl --narrator fake:wrong_number
python -m app.explain.run --seed 42 --scenario late_comeback --narrator template --lang tr --no-cache
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from typing import Any

from app.generator import SCENARIOS, generate_match
from app.generator.models import read_jsonl

from .cache import DEFAULT_CACHE_DIR, NarrationCache
from .narrator import FAKE_MODES, make_narrator
from .pipeline import run_match
from .template_narrator import LANGS


def format_step(step: dict[str, Any]) -> str:
    a, kind = step["attempt"], step["step"]
    if kind == "cache":
        return f"cache {'HIT' if step['hit'] else 'MISS'}"
    if kind == "narrate" and not step["ok"]:
        return f"#{a} narrate {step['narrator']} FAIL {step['error']}: {step['message']}"
    if kind == "narrate":
        fb = f" (feedback: {', '.join(step['feedback'])})" if step["feedback"] else ""
        return f"#{a} narrate {step['narrator']} -> {step['claims']} claims{fb}"
    if kind == "lint":
        if step["ok"]:
            return f"#{a} lint OK"
        return f"#{a} lint FAIL " + ", ".join(f"{i['code']} '{i['fragment']}'" for i in step["issues"])
    if kind == "verify":
        failed = [r for r in step["results"] if not r["ok"]]
        if not failed:
            return f"#{a} verify OK ({len(step['results'])} claims)"
        return f"#{a} verify FAIL " + ", ".join(f"{r['reason']} claim[{r['claim_index']}]" for r in failed)
    if kind == "feedback":
        tail = "retry" if step["will_retry"] else "max retries reached"
        return f"#{a} feedback {', '.join(step['codes'])} -> {tail}"
    if kind == "accept":
        return f"#{a} accept (source={step['source']})"
    if kind == "cache_store":
        return "cache STORE"
    if kind == "fallback":
        return (f"fallback template [{step['reason']}] ({step['published_sentences']}/"
                f"{step['total_sentences']} sentences published)")
    return str(step)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Anlatım hattını çalıştır")
    parser.add_argument("--input", help="JSONL olay dosyası")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS))
    parser.add_argument(
        "--narrator", default="template",
        help=f"template | foundry | fake:<mod> ({', '.join(FAKE_MODES)})",
    )
    parser.add_argument("--persona")
    parser.add_argument("--lang", choices=LANGS, default="en")
    parser.add_argument("--all", action="store_true", help="Seçimi atla, tüm momentler")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--prompt-version")
    args = parser.parse_args(argv)

    if args.input:
        events = read_jsonl(args.input)
    elif args.seed is not None:
        events = generate_match(args.seed, args.scenario)
    else:
        parser.error("--input ya da --seed gerekli")
    try:
        narrator = make_narrator(args.narrator, events)
    except ValueError as e:
        parser.error(str(e))
    cache = None if args.no_cache else NarrationCache(args.cache_dir)
    usage = getattr(narrator, "usage", None)
    if usage is not None:  # LLM anlatıcı: her çağrının token ve süresi stderr'e
        logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)
        logging.getLogger("whyball.llm").setLevel(logging.INFO)

    try:
        results = run_match(
            events, narrator, persona=args.persona, language=args.lang, select=not args.all,
            cache=cache, prompt_version=args.prompt_version,
        )
    finally:
        close = getattr(narrator, "close", None)
        if close:
            close()
    out = sys.stdout
    for m, r in results:
        short_id = m.id.rsplit("-", 1)[-1]
        cache_state = "off" if cache is None else ("hit" if r.cache_hit else "miss")
        out.write(f"{short_id}  {m.period}H {m.minute:02d}:{m.second:02d}  {m.type}\n")
        out.write(f"  source={r.source}  attempts={r.attempts}  cache={cache_state}  ok={r.ok}\n")
        out.write(f"  text: {r.text or '(boş)'}\n")
        for step in r.trace:
            out.write(f"    {format_step(step)}\n")
        out.write("\n")
    by_source = Counter(r.source for _, r in results)
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_source.items()))
    hits = sum(r.cache_hit for _, r in results)
    out.write(f"Moment: {len(results)} · {summary} · cache hit: {hits}\n")
    if usage is not None:
        tokens_in = sum(u.input_tokens or 0 for u in usage)
        tokens_out = sum(u.output_tokens or 0 for u in usage)
        avg_ms = sum(u.latency_ms for u in usage) / len(usage) if usage else 0
        out.write(
            f"LLM çağrı: {len(usage)} · token: {tokens_in} giriş + {tokens_out} çıkış "
            f"· ortalama süre: {avg_ms / 1000:.1f} sn\n"
        )
    budget_hits = [r for _, r in results if r.trace and r.trace[-1].get("reason") == "budget_exceeded"]
    if budget_hits:
        limit = getattr(getattr(narrator, "config", None), "llm_max_calls_per_run", "?")
        out.write(
            f"UYARI: LLM çağrı bütçesi aşıldı ({limit}/{limit}): "
            f"{len(budget_hits)} moment yedeğe düştü\n"
        )
    return 0 if all(r.ok for _, r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
