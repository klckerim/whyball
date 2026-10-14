"""Contracts between the Python side and the web UI source that the TypeScript tests cannot see."""

import re
from pathlib import Path

from app.analytics.moments import MOMENT_TYPES

WEB = Path(__file__).resolve().parents[1] / "web" / "src"


def test_every_moment_type_has_a_glyph():
    source = (WEB / "design" / "TypeGlyph.tsx").read_text(encoding="utf-8")
    block = source[source.index("export const MOMENT_TYPES"):source.index("};", source.index("export const MOMENT_TYPES"))]
    keys = re.findall(r"^\s+(\w+): \{ label:", block, re.M)
    assert sorted(keys) == sorted(MOMENT_TYPES)
