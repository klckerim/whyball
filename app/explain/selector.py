"""Selection of the moments to narrate (pure function)."""

from __future__ import annotations

from collections.abc import Iterable

from app.analytics.moments import Moment

from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig


def select_moments(
    moments: Iterable[Moment], config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> list[Moment]:
    """Selects moments.

    - ``always_keep`` types are kept unconditionally and do not count toward the window quota.
    - The others are candidates if ``importance >= min_importance``; in each
      ``window_minutes``-minute window (per half) at most ``max_per_window`` candidates
      remain, by importance.
    - The output is in ``(at_seq, id)`` order, independent of the input order.
    """
    moments = list(moments)
    kept = [m for m in moments if m.type in config.always_keep]
    candidates = sorted(
        (
            m for m in moments
            if m.type not in config.always_keep and m.importance >= config.min_importance
        ),
        key=lambda m: (-m.importance, m.at_seq, m.id),
    )
    windows: dict[tuple[int, int], list[Moment]] = {}
    for m in candidates:
        bucket = windows.setdefault((m.period, m.minute // config.window_minutes), [])
        if len(bucket) < config.max_per_window:
            bucket.append(m)
    chosen = kept + [m for bucket in windows.values() for m in bucket]
    return sorted(chosen, key=lambda m: (m.at_seq, m.id))
