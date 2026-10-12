"""Explain testleri için ortak yardımcılar: her moment tipinden örnek moment."""

from functools import cache

from app.analytics import detect_moments
from app.generator import generate_match

# moment tipi → (seed, senaryo, ek koşul)
MOMENT_SOURCES = {
    "goal": (42, "red_card_swing", None),
    "red_card": (42, "red_card_swing", None),
    "penalty": (42, "late_comeback", None),
    "score_change": (42, "late_comeback", lambda m: m.detail.get("from_behind")),
    "pressure_shift": (42, "red_card_swing", None),
    "dominance_without_reward": (7, "dominant_loss", None),
}
MOMENT_TYPES = tuple(MOMENT_SOURCES)


@cache
def match(seed, scenario):
    events = generate_match(seed, scenario)
    return events, detect_moments(events)


def moment_case(mtype):
    seed, scenario, cond = MOMENT_SOURCES[mtype]
    events, moments = match(seed, scenario)
    moment = next(m for m in moments if m.type == mtype and (cond is None or cond(m)))
    return events, moment
