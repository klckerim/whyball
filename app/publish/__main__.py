"""Builds the publication store: python -m app.publish [--check]

Writes data/demo_narration/{match_id}.json and the report docs/DEMO_NARRATION.md. No model is
called; the output is byte-for-byte reproducible. --check writes nothing and exits 1 when a
file is missing or differs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .store import DEFAULT_OUT_DIR, DEFAULT_REPORT, DEFAULT_RUN, PublishError, build, outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the demo narration store from the last LLM run")
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--check", action="store_true", help="Compare only; exit 1 if out of date")
    args = parser.parse_args(argv)

    try:
        result = build(args.run)
    except PublishError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    files = outputs(result, args.out_dir, args.report)
    if args.check:
        stale = [p for p, text in files.items() if not p.exists() or p.read_bytes() != text.encode("utf-8")]
        for p in stale:
            print(f"out of date: {p}", file=sys.stderr)
        return 1 if stale else 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for path, text in files.items():
        with open(path, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(text)
    for s in result.stores:
        sources = ", ".join(f"{src}={sum(m.source == src for m in s.moments)}"
                            for src in ("llm", "template", "template_fallback"))
        print(f"{s.match_id}: {len(s.moments)} cards ({sources})")
    print(f"run {result.run_id} · text diffs: {len(result.diffs)} · fallbacks: {len(result.fallbacks)} · "
          f"same-second moments: {len(result.same_second)} "
          f"(published cards affected: {sum(s.affects_card for s in result.same_second)})")
    print(f"report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
