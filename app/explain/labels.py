"""Metriklerin okunur adları ({label:} yer tutucusu, template anlatıcı, model kaydı).

`pressure_balance` kayan bir pencereden ölçülür (son `pressure_window_min` oynanmış
dakika); adı bu pencereyi yazar. Penceredeki sayı bir iddia değil, analytics
ayarından gelen sabittir: text_lint bu kod ifadelerini sayı denetiminden önce maskeler
(`window_phrases`). Doğrulayıcı pencereyi denetlemez.
"""

from __future__ import annotations

import re

from app.analytics.config import DEFAULT_CONFIG, AnalyticsConfig


def _pressure_label(language: str, config: AnalyticsConfig = DEFAULT_CONFIG) -> str:
    n = f"{config.pressure_window_min:g}"
    if language == "tr":
        return f"son {n} oynanmış dakikadaki baskı dengesi"
    return f"pressure balance over the last {n} minutes of play"


METRIC_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "goals": "goals", "shots": "shots", "shots_on_target": "shots on target",
        "corners": "corners", "fouls": "fouls", "yellow_cards": "yellow cards",
        "red_cards": "red cards", "penalties_scored": "penalties scored",
        "penalties_saved": "penalties saved", "penalties_missed": "penalties missed",
        "substitutions": "substitutions", "possession": "possession",
        "field_tilt": "territorial share", "score": "goals", "score_margin": "goal margin",
        "min_score_margin": "largest deficit", "players_on_pitch": "players on the pitch",
        "pressure_balance": _pressure_label("en"),
    },
    "tr": {
        "goals": "gol", "shots": "şut", "shots_on_target": "isabetli şut",
        "corners": "korner", "fouls": "faul", "yellow_cards": "sarı kart",
        "red_cards": "kırmızı kart", "penalties_scored": "atılan penaltı",
        "penalties_saved": "kurtarılan penaltı", "penalties_missed": "kaçan penaltı",
        "substitutions": "oyuncu değişikliği", "possession": "topa sahip olma",
        "field_tilt": "saha üstünlüğü", "score": "gol", "score_margin": "gol farkı",
        "min_score_margin": "en büyük geri kalış farkı", "players_on_pitch": "sahadaki oyuncu",
        "pressure_balance": _pressure_label("tr"),
    },
}


def metric_label(metric: str, language: str) -> str:
    labels = METRIC_LABELS.get(language, METRIC_LABELS["en"])
    return labels.get(metric, metric.replace("_", " "))


# Sayı içeren sabit etiketler (dil başına); text_lint bunları maskeler.
WINDOW_PHRASES = tuple(
    label for labels in METRIC_LABELS.values() for label in labels.values() if re.search(r"\d", label)
)
WINDOW_PHRASE_RE = re.compile("|".join(re.escape(p) for p in WINDOW_PHRASES), re.IGNORECASE)


def window_phrase_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in WINDOW_PHRASE_RE.finditer(text)]
