"""Writes the API's OpenAPI schema to web/openapi.json, the input of the web type generator.

    .venv/bin/python -m app.api.openapi           # rewrite web/openapi.json
    .venv/bin/python -m app.api.openapi --check   # exit 1 if the committed file is stale

After an API model change: run this, then `cd web && npm run gen:api` (web/src/api/schema.gen.ts).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .main import REPO_ROOT, create_app

OPENAPI_PATH = REPO_ROOT / "web" / "openapi.json"


def render() -> str:
    """The schema as stable text: sorted keys, two-space indent, trailing newline."""
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed schema is stale")
    parser.add_argument("--out", type=Path, default=OPENAPI_PATH)
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        if not args.out.is_file() or args.out.read_text(encoding="utf-8") != text:
            print(f"{args.out} is stale: run python -m app.api.openapi", file=sys.stderr)
            return 1
        return 0
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
