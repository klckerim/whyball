"""Explain aşaması eşikleri. Seçici, doğrulayıcı ve anlatıcı sayıları buradan okur."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExplainConfig:
    # --- seçici ---
    min_importance: float = 0.5
    window_minutes: int = 10
    max_per_window: int = 3  # always_keep dışındaki momentler için
    always_keep: tuple[str, ...] = ("goal", "red_card")

    # --- doğrulayıcı ---
    approx_tolerance: float = 0.005  # metinde 2 ondalığa / tam yüzdeye yuvarlanan değerler
    float_epsilon: float = 1e-9  # tolerans sınırındaki kayan nokta hatası (0.88 - 0.875)

    # --- anlatıcı ---
    context_minutes: int = 10  # baskı kayması cümlesindeki "X'ten beri" aralığı
    dominance_context_minutes: int = 20
    full_squad: int = 11


DEFAULT_EXPLAIN_CONFIG = ExplainConfig()
