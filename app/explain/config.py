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
    full_squad: int = 11  # meta'da kadro yoksa players_on_pitch için

    # --- anlatım hattı ---
    max_retries: int = 2  # ilk denemeden sonra; sonra template yedeği
    default_persona: str = "neutral"
    template_prompt_version: str = "template-v1"

    # --- text lint ---
    lint_allowed_capitalized: tuple[str, ...] = ()  # cümle ortasında serbest büyük harfli kelimeler
    lint_percent_tolerance: float = 0.5  # metindeki tam yüzde ile ratio iddiası arasındaki fark
    lint_number_words: bool = True  # yazıyla sayılar (EN/TR, 0-20) da denetlensin

    # --- LLM anlatıcı güvenliği ---
    llm_timeout_s: float = 60.0  # çağrı başına (reasoning modeli)
    llm_max_tokens: int = 4000  # yanıt token üst sınırı; reasoning token'larını da kapsar
    llm_max_calls_per_run: int = 60  # anlatıcı örneği (çalıştırma) başına toplam çağrı


DEFAULT_EXPLAIN_CONFIG = ExplainConfig()
