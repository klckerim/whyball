"""Replay as Server-Sent Events: match events and moment cards in match-clock order.

Each event (the match_meta record aside) is sent as `event: match_event`; a moment card follows right after the event that
triggered it (`at_seq`) as `event: moment`; the stream ends with `event: end`. `speed` is match
seconds per wall-clock second (0: no waiting).
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

from app.explain.template_narrator import fmt_minute
from app.generator.models import Event, EventType

from .data import Match


async def _sleep(seconds: float) -> None:  # module level, so tests can record the waits
    await asyncio.sleep(seconds)


def sse(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False, sort_keys=True)}\n\n"


def event_out(e: Event, t: int) -> dict[str, Any]:
    return {
        "seq": e.seq, "t": t, "period": e.period, "minute": e.minute, "second": e.second,
        "minute_label": fmt_minute(e.period, e.minute), "type": e.type.value, "team": e.team,
        "player": e.player, "outcome": e.outcome, "score": dict(e.score), "x": e.x, "y": e.y,
    }


def moment_out(match: Match, index: int) -> dict[str, Any]:
    """The stored card plus `t`, and each evidence event's pitch position (x, y; null when the event
    has none) from the event stream, so the UI can draw the evidence on a pitch."""
    m = match.store.moments[index]
    out = {**m.model_dump(mode="json"), "t": match.t[m.at_seq]}
    for claim in out["claims"]:
        for ev in claim["evidence"]:
            e = match.by_seq[ev["seq"]]
            ev["x"], ev["y"] = e.x, e.y
    return out


async def replay(match: Match, speed: float, from_t: int = 0) -> AsyncIterator[str]:
    cards: dict[int, list[int]] = defaultdict(list)
    for i, m in enumerate(match.store.moments):
        cards[m.at_seq].append(i)
    prev: int | None = None
    last = from_t
    for e in sorted(match.events, key=lambda e: (match.t[e.seq], e.seq)):
        t = match.t[e.seq]
        if t < from_t or e.type is EventType.MATCH_META:
            continue
        if speed > 0 and prev is not None and t > prev:
            await _sleep((t - prev) / speed)
        prev = last = t
        yield sse("match_event", event_out(e, t))
        for i in cards[e.seq]:
            yield sse("moment", moment_out(match, i))
    yield sse("end", {"t": last})
