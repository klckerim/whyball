"""Demo fixture'larını yeniden üretir: python -m app.generator.freeze

Sadece üretici bilerek değiştiyse çalıştırılmalı. tests/test_demo_fixtures.py
repodaki dosyaların üretici çıktısıyla bayt bayt aynı olduğunu doğrular.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from . import generate_match, write_jsonl

DEMO_DIR = Path(__file__).resolve().parents[2] / "data" / "demo"
DEMO_MATCHES: tuple[tuple[str | None, int], ...] = (
    ("red_card_swing", 42),
    ("dominant_loss", 7),
    (None, 100),
)


def demo_filename(scenario: str | None, seed: int) -> str:
    return f"{scenario or 'natural'}_seed{seed}.jsonl"


def demo_paths(out_dir: Path = DEMO_DIR) -> list[tuple[str | None, int, Path]]:
    return [(sc, seed, out_dir / demo_filename(sc, seed)) for sc, seed in DEMO_MATCHES]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Demo fixture'larını yeniden üret")
    parser.add_argument("--out-dir", type=Path, default=DEMO_DIR)
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print("| Dosya | Senaryo | Seed | Skor (home-away) | Olay | SHA-256 |")
    print("|---|---|---|---|---|---|")
    for scenario, seed, path in demo_paths(args.out_dir):
        events = generate_match(seed, scenario)
        with open(path, "w", encoding="utf-8", newline="\n") as fp:
            write_jsonl(events, fp)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        score = events[-1].score
        print(
            f"| `{path.name}` | {scenario or '—'} | {seed} "
            f"| {score['home']}-{score['away']} | {len(events)} | `{digest[:12]}` |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
