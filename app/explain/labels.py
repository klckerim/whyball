"""Readable metric names ({label:} placeholder, template narrator, model record).

Countable labels agree with the number (EN "1 shot" / "2 shots"). Penalty labels are from the
side of the team taking the penalty ("penalty taken and saved"), not the goalkeeper's.

`pressure_balance` is measured over a rolling window (the last `pressure_window_min` minutes
played); its name states that window. The number in the window is not a claim but a constant from
the analytics config: text_lint masks these code-written phrases before the number check
(`window_phrases`). The verifier does not check the window.
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


# EN singular forms (when the value is 1).
SINGULAR_EN: dict[str, str] = {
    "goals": "goal", "score": "goal", "shots": "shot", "shots_on_target": "shot on target",
    "corners": "corner", "fouls": "foul", "yellow_cards": "yellow card", "red_cards": "red card",
    "penalties_scored": "penalty scored", "penalties_saved": "penalty taken and saved",
    "penalties_missed": "penalty missed", "substitutions": "substitution",
    "players_on_pitch": "player on the pitch",
}


def metric_label(metric: str, language: str, value: float | None = None) -> str:
    """Readable name; with `value`, it agrees with the number (only when written right after the value)."""
    if language == "en" and value is not None and abs(value) == 1 and metric in SINGULAR_EN:
        return SINGULAR_EN[metric]
    labels = METRIC_LABELS.get(language, METRIC_LABELS["en"])
    return labels.get(metric, metric.replace("_", " "))


# Fixed labels that contain a number (per language); text_lint masks them.
WINDOW_PHRASES = tuple(
    label for labels in METRIC_LABELS.values() for label in labels.values() if re.search(r"\d", label)
)
WINDOW_PHRASE_RE = re.compile("|".join(re.escape(p) for p in WINDOW_PHRASES), re.IGNORECASE)


def window_phrase_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in WINDOW_PHRASE_RE.finditer(text)]
