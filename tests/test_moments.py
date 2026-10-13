import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from app.analytics import DEFAULT_CONFIG, MOMENT_TYPES, MatchTracker, MomentDetector, detect_moments
from app.generator import SCENARIOS, EventType, generate_match
from app.generator.freeze import DEMO_DIR, demo_filename

ROOT = Path(__file__).resolve().parent.parent
SCENARIO_SEEDS = {
    "late_comeback": [0, 42, 2024],
    "red_card_swing": [0, 42, 2024],  # 42: demo fixture
    "dominant_loss": [0, 7, 42, 2024],  # 7: demo fixture
}
CASES = [(s, None) for s in (0, 42, 100)] + [
    (s, name) for name, seeds in sorted(SCENARIO_SEEDS.items()) for s in seeds
]


def _of(moments, mtype, team=None):
    return [m for m in moments if m.type == mtype and (team is None or m.team == team)]


def _near(m, minute):
    # A forced event at its exact minute; an earlier goal celebration can shift it by at most +1 min.
    return minute <= m.minute <= minute + 1


def _changes(moments):
    """Goal cards that changed the match state (score change sub-label)."""
    return [m for m in _of(moments, "goal") if "score_change" in m.detail]


def _score_changes(moments):
    return [(m.detail["score_change"]["kind"], m.team, m.minute) for m in _changes(moments)]


def _assert_score_changes(moments, expected):
    actual = _score_changes(moments)
    assert len(actual) == len(expected), actual
    for (kind, team, minute), m in zip(expected, _changes(moments)):
        assert (m.detail["score_change"]["kind"], m.team) == (kind, team), actual
        assert _near(m, minute), actual


# --- general invariants ------------------------------------------------------


@pytest.mark.parametrize("seed,scenario", CASES)
def test_moments_do_not_look_ahead(seed, scenario):
    events = generate_match(seed, scenario)
    full = detect_moments(events)
    for n in (50, 150, len(events) // 2, len(events) - 20, len(events)):
        assert detect_moments(events[:n]) == [m for m in full if m.at_seq <= n - 1], f"N={n}"


@pytest.mark.parametrize("seed,scenario", CASES)
def test_moment_invariants(seed, scenario):
    events = generate_match(seed, scenario)
    moments = detect_moments(events)
    assert moments
    assert len({m.id for m in moments}) == len(moments)
    for m in moments:
        assert m.type in MOMENT_TYPES
        assert 0.0 <= m.importance <= 1.0
        assert m.event_ids, m
        assert all(0 <= i <= m.at_seq for i in m.event_ids), m
        anchor = events[m.at_seq]
        assert (anchor.period, anchor.minute, anchor.second) == (m.period, m.minute, m.second)
    assert [m.at_seq for m in moments] == sorted(m.at_seq for m in moments)

    goals = [e for e in events if e.type is EventType.GOAL]
    assert [m.event_ids[-1] for m in _of(moments, "goal")] == [e.seq for e in goals]
    reds = [e.seq for e in events if e.type is EventType.RED_CARD]
    assert [m.at_seq for m in _of(moments, "red_card")] == reds
    pens = [e.seq for e in events if e.type is EventType.PENALTY]
    assert [m.at_seq for m in _of(moments, "penalty")] == pens
    # One card per goal event: no other moment is anchored on a goal.
    goal_seqs = {e.seq for e in goals}
    assert all(m.type == "goal" for m in moments if m.at_seq in goal_seqs)


@pytest.mark.parametrize("seed,scenario", CASES)
def test_goal_card_importance_is_the_max_of_goal_and_score_change(seed, scenario):
    events = generate_match(seed, scenario)
    detector = MomentDetector()
    for e in events:
        detector.process(e)
    for m in _of(detector.moments, "goal"):
        e = events[m.at_seq]
        goal = detector._importance("goal", e)
        change = m.detail.get("score_change")
        if change is None:
            assert m.importance == goal
        else:
            score_change = detector._importance("score_change", e, change.get("from_behind", False))
            assert m.importance == max(goal, score_change)


@pytest.mark.parametrize("seed,scenario", CASES)
def test_moments_are_deterministic(seed, scenario):
    assert detect_moments(generate_match(seed, scenario)) == detect_moments(
        generate_match(seed, scenario)
    )


# --- scenario expectations ----------------------------------------------------


@pytest.mark.parametrize("seed", SCENARIO_SEEDS["late_comeback"])
def test_late_comeback(seed):
    moments = detect_moments(generate_match(seed, "late_comeback"))

    goals = _of(moments, "goal")
    expected = [(18, "away"), (52, "away"), (74, "home"), (83, "home"), (89, "home")]
    assert [m.team for m in goals] == [team for _, team in expected]
    assert all(_near(m, minute) for m, (minute, _) in zip(goals, expected))

    assert any(_near(m, 83) and m.detail["outcome"] == "scored" for m in _of(moments, "penalty", "home"))

    _assert_score_changes(
        moments, [("opener", "away", 18), ("equalizer", "home", 83), ("go_ahead", "home", 89)]
    )
    winner = _changes(moments)[-1]
    assert winner.detail["score_change"]["from_behind"] is True
    assert winner.detail["score_change"]["max_deficit"] == 2
    assert all(m.importance < winner.importance for m in moments if m is not winner)


@pytest.mark.parametrize("seed", SCENARIO_SEEDS["red_card_swing"])
def test_red_card_swing(seed):
    events = generate_match(seed, "red_card_swing")
    moments = detect_moments(events)

    reds = [m for m in _of(moments, "red_card", "home") if _near(m, 38)]
    assert len(reds) == 1 and reds[0].detail["reason"] == "straight_red"

    _assert_score_changes(
        moments, [("opener", "home", 22), ("equalizer", "away", 61), ("go_ahead", "away", 84)]
    )
    winner = _changes(moments)[-1]
    assert winner.detail["score_change"]["from_behind"] is True
    assert winner.detail["score_change"]["max_deficit"] == 1

    assert any(m.at_seq > reds[0].at_seq for m in _of(moments, "pressure_shift", "away"))


def test_red_card_swing_pressure_tilts_to_away_after_red():
    # At the moment level, "shift to away after the red card" holds in ~90% of 200 seeds
    # (away is sometimes already dominant before the red). The effect at the metric level is solid.
    c = DEFAULT_CONFIG
    frac = {"pre": {"home": 0, "away": 0, "n": 0}, "post": {"home": 0, "away": 0, "n": 0}}
    for seed in range(50):
        events = generate_match(seed, "red_card_swing")
        red = next(
            e.seq for e in events
            if e.type is EventType.RED_CARD and e.team == "home" and e.minute == 38
        )
        tracker = MatchTracker()
        for e in events:
            tracker.update(e)
            if tracker.played < c.pressure_window_min * 60:
                continue
            b = tracker.pressure_balance()
            bucket = frac["post" if e.seq > red else "pre"]
            bucket["n"] += 1
            bucket["home"] += b >= c.shift_enter
            bucket["away"] += b <= -c.shift_enter
    post_away = frac["post"]["away"] / frac["post"]["n"]
    post_home = frac["post"]["home"] / frac["post"]["n"]
    pre_away = frac["pre"]["away"] / frac["pre"]["n"]
    assert post_away > 1.5 * post_home
    assert post_away > pre_away


@pytest.mark.parametrize("seed", SCENARIO_SEEDS["dominant_loss"])
def test_dominant_loss(seed):
    moments = detect_moments(generate_match(seed, "dominant_loss"))

    goals = _of(moments, "goal")
    assert len(goals) == 1 and goals[0].team == "away" and _near(goals[0], 57)
    _assert_score_changes(moments, [("opener", "away", 57)])
    assert any(_near(m, 70) and m.detail["outcome"] == "saved" for m in _of(moments, "penalty", "home"))

    assert _of(moments, "dominance_without_reward", "home")
    assert not _of(moments, "dominance_without_reward", "away")


# --- the config is really used -------------------------------------------


def test_thresholds_come_from_config():
    events = generate_match(7, "dominant_loss")
    strict = replace(DEFAULT_CONFIG, dominance_shot_margin=99, shift_enter=1.01)
    moments = detect_moments(events, strict)
    assert not _of(moments, "dominance_without_reward")
    assert not _of(moments, "pressure_shift")
    assert _of(detect_moments(events), "dominance_without_reward")


# --- CLI ----------------------------------------------------------------------


def _cli(*args: str) -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "app.analytics", *args],
        cwd=ROOT, capture_output=True, check=True, text=True, encoding="utf-8",
    )
    return result.stdout.splitlines()


def test_cli_prints_one_line_per_moment():
    moments = detect_moments(generate_match(42, "red_card_swing"))
    lines = _cli("--scenario", "red_card_swing", "--seed", "42")
    assert len(lines) == len(moments)
    for line, m in zip(lines, moments):
        assert line.startswith(m.id.rsplit("-", 1)[-1])
        assert m.type in line


def test_cli_jsonl_and_input_file():
    moments = detect_moments(generate_match(42, "red_card_swing"))
    from_seed = _cli("--scenario", "red_card_swing", "--seed", "42", "--jsonl")
    from_file = _cli("--input", str(DEMO_DIR / demo_filename("red_card_swing", 42)), "--jsonl")
    assert from_seed == from_file
    assert [json.loads(line) for line in from_seed] == [m.to_dict() for m in moments]
