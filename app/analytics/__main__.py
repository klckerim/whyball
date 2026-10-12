"""CLI: python -m app.analytics --scenario red_card_swing --seed 42 [--jsonl]
       python -m app.analytics --input data/demo/natural_seed100.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys

from app.generator import SCENARIOS, generate_match
from app.generator.models import read_jsonl

from .moments import Moment, detect_moments


def _score(s: dict[str, int]) -> str:
    return f"{s['home']}-{s['away']}"


def _headline(m: Moment) -> str:
    d = m.detail
    if m.type == "goal":
        return f"{d['player']}  {_score(d['score'])}"
    if m.type == "red_card":
        return f"{d['player']} ({d['reason']})"
    if m.type == "penalty":
        return f"{d['player']} ({d['outcome']})"
    if m.type == "score_change":
        flag = " (from_behind)" if d.get("from_behind") else ""
        return f"{d['kind']}{flag}  {_score(d['score'])}"
    if m.type == "pressure_shift":
        return f"{d['from'] or '-'} -> {d['to']}  balance {d['balance']:+.2f}"
    if m.type == "dominance_without_reward":
        s = d["shots"]
        return (
            f"shots {s[m.team]}-{s[next(k for k in s if k != m.team)]}"
            f"  possession {d['possession']:.0%}  score {_score(d['score'])}"
        )
    return ""


def format_moment(m: Moment) -> str:
    short_id = m.id.rsplit("-", 1)[-1]
    return (
        f"{short_id}  {m.period}H {m.minute:02d}:{m.second:02d}  {m.type:<24}  "
        f"imp={m.importance:.2f}  {m.team or '-':<4}  {_headline(m)}  "
        f"events={list(m.event_ids)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maç akışından momentleri çıkar")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS))
    parser.add_argument("--input", help="JSONL olay dosyası (seed/senaryo yerine)")
    parser.add_argument("--jsonl", action="store_true", help="Momentleri JSON satırı olarak yaz")
    args = parser.parse_args(argv)

    if args.input:
        events = read_jsonl(args.input)
    elif args.seed is not None:
        events = generate_match(args.seed, args.scenario)
    else:
        parser.error("--seed ya da --input gerekli")

    for m in detect_moments(events):
        if args.jsonl:
            line = json.dumps(m.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        else:
            line = format_moment(m)
        sys.stdout.write(line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
