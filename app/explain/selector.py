"""Anlatılacak momentlerin seçimi (saf fonksiyon)."""

from __future__ import annotations

from collections.abc import Iterable

from app.analytics.moments import Moment

from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig


def select_moments(
    moments: Iterable[Moment], config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> list[Moment]:
    """Momentleri seçer.

    - ``always_keep`` tipleri koşulsuz tutulur ve pencere kotasına sayılmaz.
    - Diğerleri ``importance >= min_importance`` ise aday olur; her
      ``window_minutes`` dakikalık pencerede (devre bazında) önem sırasına göre
      en fazla ``max_per_window`` aday kalır.
    - Çıktı ``(at_seq, id)`` sırasındadır; girdi sırasından bağımsızdır.
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
