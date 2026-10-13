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
    lint_bare_surname: bool = True  # serbest metinde yalnızca soyadla anılan oyuncu reddedilir

    # --- slot şablonu lint (foundry-v4 kuralları; kapalıyken v3 davranışı) ---
    slot_event_words: bool = True  # olay tipi / rol sözcükleri yalnızca {event:} ile gelir
    slot_sentence_start: bool = True  # cümlenin ilk kelimesi yer tutucu ya da izinli başlangıç
    slot_strict_number_words: bool = True  # yazıyla sayı bağlamdan bağımsız yasak ("one of", "bir ara")
    slot_overstatement: bool = True  # nitel abartı listesi (moment tipi desteklemiyorsa)
    # --- foundry-v4.1 kuralları ---
    slot_event_type_allowlist: bool = True  # {event:} yalnızca moment tipinin izinli olay tiplerinden
    slot_player_repeat: bool = True  # aynı cümlede {event:X} + X'in oyuncusu için {player:} yasak
    slot_article_team: bool = True  # takım yer tutucusundan önce "the" yasak ("The {home}")
    # --- foundry-v5 claim menüsü kuralları (yalnızca menü taslağında) ---
    slot_sentence_claim: bool = True  # her cümle en az bir menü iddiasına dayanır
    slot_primary_claim: bool = True  # dominance / pressure momentinde ana iddia kullanılır
    slot_minute_repeat: bool = True  # bir cümlede aynı dakika iki kez yazılmaz
    # Temiz taslaklardan çıkarılmış cümle başı kelimeleri (eval/lint_rates.py `derive_sentence_starts`).
    # Elle düzenlemeyin; tests/test_lint_rates.py yeniden çıkarılan listeyle eşitliği denetler.
    sentence_start_allowed_en: tuple[str, ...] = ("The",)
    sentence_start_allowed_tr: tuple[str, ...] = ("Skor",)

    # --- LLM anlatıcı güvenliği ---
    llm_timeout_s: float = 60.0  # çağrı başına (reasoning modeli)
    llm_max_tokens: int = 4000  # yanıt token üst sınırı; reasoning token'larını da kapsar
    llm_max_calls_per_run: int = 60  # anlatıcı örneği (çalıştırma) başına toplam çağrı
    llm_reasoning_effort: str = "low"  # Responses reasoning.effort (none|low|medium|high)


DEFAULT_EXPLAIN_CONFIG = ExplainConfig()
