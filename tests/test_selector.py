import random
from dataclasses import replace

import pytest

from app.analytics import Moment, detect_moments
from app.explain import DEFAULT_EXPLAIN_CONFIG, select_moments
from app.generator import generate_match
from app.generator.freeze import demo_paths
from app.generator.models import read_jsonl

STRICT = replace(DEFAULT_EXPLAIN_CONFIG, min_importance=1.01, max_per_window=0)
MATCHES = [
    (seed, scenario)
    for scenario in (None, "late_comeback", "red_card_swing", "dominant_loss")
    for seed in (0, 42, 2024)
]


def _match_moments():
    for seed, scenario in MATCHES:
        yield detect_moments(generate_match(seed, scenario))
    for _, _, path in demo_paths():
        yield detect_moments(read_jsonl(path))


def _m(k, mtype, minute, importance, period=None):
    return Moment(
        id=f"t-M{k:03d}", type=mtype, period=period or (1 if minute < 45 else 2),
        minute=minute, second=0, at_seq=k, importance=importance,
        event_ids=(k,), team="home", detail={}, metrics={},
    )


# --- goals and red cards --------------------------------------------------------


@pytest.mark.parametrize("config", [DEFAULT_EXPLAIN_CONFIG, STRICT], ids=["default", "strict"])
def test_goals_and_red_cards_are_never_dropped(config):
    for moments in _match_moments():
        selected = {m.id for m in select_moments(moments, config)}
        for m in moments:
            if m.type in ("goal", "red_card"):
                assert m.id in selected, m


def test_goals_and_red_cards_kept_regardless_of_importance_and_cap():
    moments = [_m(i, "goal", 30, 0.0) for i in range(5)] + [_m(10, "red_card", 31, 0.0)]
    assert select_moments(moments, STRICT) == moments


# --- threshold and window quota -------------------------------------------------------


def test_low_importance_pressure_shifts_are_dropped():
    low, high = _m(1, "pressure_shift", 20, 0.45), _m(2, "pressure_shift", 80, 0.6)
    assert select_moments([low, high]) == [high]


def test_real_low_importance_pressure_shifts_are_dropped():
    dropped = 0
    for moments in _match_moments():
        selected = select_moments(moments)
        for m in selected:
            if m.type == "pressure_shift":
                assert m.importance >= DEFAULT_EXPLAIN_CONFIG.min_importance
        dropped += sum(
            m.type == "pressure_shift" and m not in selected for m in moments
        )
    assert dropped > 0


def test_window_cap_keeps_most_important():
    goal = _m(0, "goal", 31, 0.7)
    shifts = [_m(i, "pressure_shift", 30 + i, imp) for i, imp in
              enumerate([0.55, 0.9, 0.6, 0.8, 0.7], start=1)]
    next_window = _m(9, "pressure_shift", 40, 0.55)
    selected = select_moments([goal, *shifts, next_window])
    assert [m.importance for m in selected if m.type == "pressure_shift" and m.minute < 40] == [
        0.9, 0.8, 0.7
    ]
    assert goal in selected and next_window in selected


def test_windows_are_per_period():
    first_half_stoppage = _m(1, "pressure_shift", 46, 0.6, period=1)
    second_half_start = _m(2, "pressure_shift", 46, 0.6, period=2)
    cfg = replace(DEFAULT_EXPLAIN_CONFIG, max_per_window=1)
    assert select_moments([first_half_stoppage, second_half_start], cfg) == [
        first_half_stoppage, second_half_start
    ]


def test_tie_break_prefers_earlier_moment():
    a, b = _m(1, "pressure_shift", 30, 0.6), _m(2, "pressure_shift", 31, 0.6)
    cfg = replace(DEFAULT_EXPLAIN_CONFIG, max_per_window=1)
    assert select_moments([b, a], cfg) == [a]


def test_real_matches_respect_window_cap():
    cfg = DEFAULT_EXPLAIN_CONFIG
    for moments in _match_moments():
        per_window: dict[tuple[int, int], int] = {}
        for m in select_moments(moments):
            if m.type not in cfg.always_keep:
                key = (m.period, m.minute // cfg.window_minutes)
                per_window[key] = per_window.get(key, 0) + 1
        assert all(n <= cfg.max_per_window for n in per_window.values())


# --- determinism ------------------------------------------------------------------


def test_selection_is_deterministic_and_pure():
    for moments in _match_moments():
        original = list(moments)
        first = select_moments(moments)
        assert select_moments(moments) == first
        shuffled = list(moments)
        random.Random(0).shuffle(shuffled)
        assert select_moments(shuffled) == first
        assert moments == original
        assert [m.at_seq for m in first] == sorted(m.at_seq for m in first)
