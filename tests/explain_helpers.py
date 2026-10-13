"""Shared helpers for the explain tests: a sample moment of each moment type."""

from functools import cache

from app.analytics import detect_moments
from app.generator import generate_match

# moment case (a moment type or a sub-case) → (seed, scenario, extra condition)
MOMENT_SOURCES = {
    "goal": (42, "red_card_swing", None),
    "red_card": (42, "red_card_swing", None),
    "penalty": (42, "late_comeback", None),
    # A goal that changed the match state, from behind (score change sub-label: go_ahead + deficit).
    "goal_from_behind": (42, "late_comeback", lambda m: m.detail.get("score_change", {}).get("from_behind")),
    "pressure_shift": (42, "red_card_swing", None),
    "dominance_without_reward": (7, "dominant_loss", None),
}
MOMENT_TYPES = tuple(MOMENT_SOURCES)  # moment types and sub-cases
MOMENT_KINDS = {"goal_from_behind": "goal"}  # sub-case → moment type


@cache
def match(seed, scenario):
    events = generate_match(seed, scenario)
    return events, detect_moments(events)


def moment_case(case):
    seed, scenario, cond = MOMENT_SOURCES[case]
    events, moments = match(seed, scenario)
    mtype = MOMENT_KINDS.get(case, case)
    moment = next(m for m in moments if m.type == mtype and (cond is None or cond(m)))
    return events, moment
