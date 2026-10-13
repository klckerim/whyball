"""CLI: python -m app.generator --seed 42 [--scenario late_comeback] [--out match.jsonl]"""

from __future__ import annotations

import argparse
import sys

from . import SCENARIOS, generate_match, write_jsonl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seeded synthetic match event stream (JSONL)")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS))
    parser.add_argument("--out", help="Output file (stdout if omitted)")
    args = parser.parse_args(argv)

    events = generate_match(args.seed, args.scenario)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fp:
            write_jsonl(events, fp)
    else:
        write_jsonl(events, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
