"""Web test fixtures from the real API over the publication store (no hand-written data).

    .venv/bin/python -m app.api.fixtures           # rewrite web/test-fixtures/
    .venv/bin/python -m app.api.fixtures --check   # exit 1 if the fixtures are stale

One file per match ({match_id}.json: the summary, detail and moments responses), metrics.json
(GET /api/metrics) and manifest.json: the sha256 of each source store file and of each fixture file.
Rerun after `python -m app.publish` or an API response change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from .main import REPO_ROOT, create_app

FIXTURES_DIR = REPO_ROOT / "web" / "test-fixtures"
COMMAND = ".venv/bin/python -m app.api.fixtures"


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _sha256(text: str | bytes) -> str:
    return hashlib.sha256(text.encode("utf-8") if isinstance(text, str) else text).hexdigest()


def render(data_dir: Path = REPO_ROOT / "data") -> dict[str, str]:
    """File name → content."""
    files: dict[str, str] = {}
    sources: dict[str, str] = {}
    with TestClient(create_app(data_dir=data_dir, static_dir=data_dir / "no-ui")) as client:
        for summary in client.get("/api/matches").json():
            match_id = summary["id"]
            files[f"{match_id}.json"] = _dump({
                "summary": summary,
                "detail": client.get(f"/api/matches/{match_id}").json(),
                "moments": client.get(f"/api/matches/{match_id}/moments").json(),
            })
            store = data_dir / "demo_narration" / f"{match_id}.json"
            sources[f"data/demo_narration/{store.name}"] = _sha256(store.read_bytes())
        files["metrics.json"] = _dump(client.get("/api/metrics").json())
    files["manifest.json"] = _dump({
        "generator": COMMAND,
        "sources": sources,
        "files": {name: _sha256(text) for name, text in files.items()},
    })
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the fixtures are stale")
    parser.add_argument("--out", type=Path, default=FIXTURES_DIR)
    args = parser.parse_args(argv)
    files = render()
    if args.check:
        on_disk = {p.name for p in args.out.glob("*.json")} if args.out.is_dir() else set()
        stale = sorted(
            name for name, text in files.items()
            if not (args.out / name).is_file() or (args.out / name).read_text(encoding="utf-8") != text
        ) + sorted(on_disk - set(files))
        if stale:
            print(f"stale fixtures {stale}: run {COMMAND}", file=sys.stderr)
            return 1
        return 0
    args.out.mkdir(parents=True, exist_ok=True)
    for old in set(args.out.glob("*.json")) - {args.out / n for n in files}:
        old.unlink()
    for name, text in files.items():
        (args.out / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
