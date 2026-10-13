"""Metriklerin okunur adları ({label:} yer tutucusu, template anlatıcı, model kaydı).

Sayılabilir etiketler sayıyla uyumlu çekilir (EN "1 shot" / "2 shots"). Penaltı etiketleri penaltıyı kullanan takım açısındandır ("penalty taken and
saved"), kaleci açısından okunamaz.

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
    return f"pressure balance over the last {n} minutes of play"


METRIC_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "goals": "goals", "shots": "shots", "shots_on_target": "shots on target",
        "corners": "corners", "fouls": "fouls", "yellow_cards": "yellow cards",
        "red_cards": "red cards", "penalties_scored": "penalties scored",
        "penalties_saved": "penalties taken and saved", "penalties_missed": "penalties missed",
        "substitutions": "substitutions", "possession": "possession",
        "field_tilt": "territorial share", "score": "goals", "score_margin": "goal margin",
        "min_score_margin": "largest deficit", "players_on_pitch": "players on the pitch",
        "pressure_balance": _pressure_label("en"),
    },
}


# EN tekil biçimler (değer 1 iken).
SINGULAR_EN: dict[str, str] = {
    "goals": "goal", "score": "goal", "shots": "shot", "shots_on_target": "shot on target",
    "corners": "corner", "fouls": "foul", "yellow_cards": "yellow card", "red_cards": "red card",
    "penalties_scored": "penalty scored", "penalties_saved": "penalty taken and saved",
    "penalties_missed": "penalty missed", "substitutions": "substitution",
    "players_on_pitch": "player on the pitch",
}


def metric_label(metric: str, language: str, value: float | None = None) -> str:
    """Okunur ad; `value` verilirse sayıyla uyumlu (yalnızca değerin hemen ardından yazıldığında)."""
    if language == "en" and value is not None and abs(value) == 1 and metric in SINGULAR_EN:
        return SINGULAR_EN[metric]
    labels = METRIC_LABELS.get(language, METRIC_LABELS["en"])
    return labels.get(metric, metric.replace("_", " "))


# Sayı içeren sabit etiketler (dil başına); text_lint bunları maskeler.
WINDOW_PHRASES = tuple(
    label for labels in METRIC_LABELS.values() for label in labels.values() if re.search(r"\d", label)
)
WINDOW_PHRASE_RE = re.compile("|".join(re.escape(p) for p in WINDOW_PHRASES), re.IGNORECASE)


def window_phrase_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in WINDOW_PHRASE_RE.finditer(text)]
