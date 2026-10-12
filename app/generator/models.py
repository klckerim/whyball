"""Olay şeması ve JSONL serileştirme."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, TextIO

SCHEMA_VERSION = 1


class EventType(Enum):
    MATCH_META = "match_meta"
    KICKOFF = "kickoff"
    PASS = "pass"
    DRIBBLE = "dribble"
    SHOT = "shot"
    GOAL = "goal"
    SAVE = "save"
    FOUL = "foul"
    YELLOW_CARD = "yellow_card"
    RED_CARD = "red_card"
    CORNER = "corner"
    OFFSIDE = "offside"
    SUBSTITUTION = "substitution"
    HALF_TIME = "half_time"
    FULL_TIME = "full_time"


@dataclass(frozen=True, slots=True)
class Event:
    match_id: str
    seq: int
    period: int
    minute: int
    second: int
    type: EventType
    team: str | None = None  # "home" | "away"
    player: str | None = None
    x: float | None = None  # 0..105, home takımı x=105 yönüne hücum eder
    y: float | None = None  # 0..68
    outcome: str | None = None
    score: dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        return d


def _dumps(event: Event) -> str:
    return json.dumps(
        event.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def to_jsonl(events: Iterable[Event]) -> str:
    return "".join(_dumps(e) + "\n" for e in events)


def write_jsonl(events: Iterable[Event], fp: TextIO) -> None:
    for e in events:
        fp.write(_dumps(e) + "\n")
