"""File-based narration cache (data/cache/, not tracked by git).

Key = hash of the moment content + persona + language + prompt_version.
The narrator identity enters the key through prompt_version.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from app.analytics.moments import Moment

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def moment_hash(moment: Moment) -> str:
    return hashlib.sha256(_canonical(moment.to_dict()).encode("utf-8")).hexdigest()


def cache_key(moment: Moment, persona: str, language: str, prompt_version: str) -> str:
    raw = f"{moment_hash(moment)}|{persona}|{language}|{prompt_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class NarrationCache:
    def __init__(self, root: str | os.PathLike[str] = DEFAULT_CACHE_DIR) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        """None if the entry is missing or unreadable (miss)."""
        try:
            data = json.loads(self._path(key).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def put(self, key: str, record: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(key)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(_canonical(record) + "\n", encoding="utf-8")
        os.replace(tmp, path)
