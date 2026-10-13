"""CLI: python -m app.explain --input data/demo/red_card_swing_seed42.jsonl [--lang en] [--all]
       python -m app.explain --seed 42 --scenario red_card_swing
"""

from __future__ import annotations

import argparse
import sys

from app.analytics import detect_moments
from app.generator import SCENARIOS, generate_match
from app.generator.models import read_jsonl

from .selector import select_moments
from .template_narrator import LANGS, narrate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Momentleri seç, anlat ve iddiaları doğrula")
    parser.add_argument("--input", help="JSONL olay dosyası")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS))
    parser.add_argument("--lang", choices=LANGS, default="en")
    parser.add_argument("--all", action="store_true", help="Seçimi atla, tüm momentleri anlat")
    args = parser.parse_args(argv)

    if args.input:
        events = read_jsonl(args.input)
    elif args.seed is not None:
        events = generate_match(args.seed, args.scenario)
    else:
        parser.error("--input ya da --seed gerekli")

    langs = (args.lang,)
    moments = detect_moments(events)
    chosen = moments if args.all else select_moments(moments)
    out = sys.stdout
    total = passed = 0
    for m in chosen:
        n = narrate(m, events)
        short_id = m.id.rsplit("-", 1)[-1]
        out.write(f"{short_id}  {m.period}H {m.minute:02d}:{m.second:02d}  {m.type}  imp={m.importance:.2f}\n")
        for lang in langs:
            out.write(f"  [{lang.upper()}] {n.published(lang) or '(yayınlanacak cümle yok)'}\n")
        for sentence, results in zip(n.sentences, n.results):
            for claim, r in zip(sentence.claims, results):
                total += 1
                passed += r.ok
                status = "PASS" if r.ok else f"FAIL ({r.reason}, actual={r.actual})"
                out.write(f"    {status}  {claim.describe()}\n")
        out.write("\n")
    out.write(
        f"Seçilen moment: {len(chosen)}/{len(moments)} · doğrulanan iddia: {passed}/{total}\n"
    )
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
