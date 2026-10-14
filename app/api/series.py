"""Metric time series for the UI (B2): `metrics_at` sampled on the continuous match clock `t`.

Each point at `t` is the snapshot after the last event at or before `t` (`metrics_at(until_seq=…)`),
from the home side's perspective, rounded like `MetricSnapshot.summary`. A point that cannot be
computed is None, never 0: pressure balance while fewer than `pressure_window_min` minutes have been
played (the window is not full yet; the moment detector skips the same span).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.analytics import metrics_at
from app.analytics.config import DEFAULT_CONFIG
from app.analytics.metrics import MetricSnapshot

from .data import Match


def _pressure_balance(s: MetricSnapshot) -> float | None:
    if s.played_seconds < DEFAULT_CONFIG.pressure_window_min * 60:
        return None
    return s.pressure_balance


# metric id (as in /api/metrics) → value of a snapshot, home perspective
SERIES_METRICS: dict[str, Callable[[MetricSnapshot], float | None]] = {
    "pressure_balance": _pressure_balance,
    "possession": lambda s: s.possession["home"],
    "field_tilt": lambda s: s.field_tilt["home"],
}


def sample_times(duration_t: int, step: int) -> list[int]:
    """0, step, 2·step, … and the final whistle."""
    ts = list(range(0, duration_t + 1, step))
    if ts[-1] != duration_t:
        ts.append(duration_t)
    return ts


def series_points(match: Match, metric: str, step: int) -> list[dict[str, Any]]:
    value_of = SERIES_METRICS[metric]
    events = match.events
    points = []
    i, last_seq = 0, None
    for t in sample_times(match.duration_t, step):
        while i < len(events) and match.t[events[i].seq] <= t:
            last_seq = events[i].seq
            i += 1
        value = None if last_seq is None else value_of(metrics_at(events, until_seq=last_seq))
        points.append({"t": t, "value": None if value is None else round(value, DEFAULT_CONFIG.summary_decimals)})
    return points
