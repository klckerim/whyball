"""Loads the publication store and the event streams; the continuous match clock `t`.

`t` is seconds since kickoff on one axis: the first half runs on the match clock, the second
half continues from the half-time whistle (its clock restarts at 45:00), so stoppage time of
the first half does not overlap the second.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.generator.models import Event, EventType, read_jsonl
from app.publish.schema import MatchStore

SECOND_HALF_CLOCK = 45 * 60
# Events shown on the timeline (score changes, cards, whistles); the replay streams every event.
TIMELINE_TYPES = frozenset({
    EventType.GOAL, EventType.PENALTY, EventType.RED_CARD, EventType.YELLOW_CARD,
    EventType.HALF_TIME, EventType.FULL_TIME,
})


class DataError(Exception):
    """The store and the event streams do not belong together."""


def match_clock(events: list[Event]) -> dict[int, int]:
    """seq → t (seconds since kickoff, continuous across the half-time break)."""
    out: dict[int, int] = {}
    half_end = 0
    for e in events:
        clock = e.minute * 60 + e.second
        t = clock if e.period == 1 else half_end + clock - SECOND_HALF_CLOCK
        if e.period == 1:
            half_end = t
        out[e.seq] = t
    return out


@dataclass(frozen=True)
class Match:
    store: MatchStore
    events: list[Event]
    t: dict[int, int]  # seq → t

    @property
    def id(self) -> str:
        return self.store.match_id

    @property
    def duration_t(self) -> int:
        return self.t[self.events[-1].seq]

    def periods(self) -> list[dict[str, int]]:
        out: dict[int, dict[str, int]] = {}
        for e in self.events:
            p = out.setdefault(e.period, {"period": e.period, "start_t": self.t[e.seq]})
            p["end_t"] = self.t[e.seq]
        return list(out.values())


def load_match(store_path: Path, demo_dir: Path) -> Match:
    store = MatchStore.model_validate_json(store_path.read_text(encoding="utf-8"))
    events_path = demo_dir / Path(store.events_file).name
    if hashlib.sha256(events_path.read_bytes()).hexdigest() != store.events_sha256:
        raise DataError(f"{store_path.name} was built from another {events_path.name}; run python -m app.publish")
    events = read_jsonl(events_path)
    return Match(store, events, match_clock(events))


def load_matches(data_dir: Path) -> dict[str, Match]:
    """Every match of data/demo_narration, keyed by match id (file order)."""
    matches = [load_match(p, data_dir / "demo") for p in sorted((data_dir / "demo_narration").glob("*.json"))]
    return {m.id: m for m in matches}
