import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from app.generator import SCENARIOS, EventType, ForcedEvent, generate_match, to_jsonl
from app.generator.engine import LINEUP_SIZE, PITCH_LENGTH, PITCH_WIDTH, SIDES
from app.generator.names import FIRST_NAMES, LAST_NAMES, TEAM_CITIES

ROOT = Path(__file__).resolve().parent.parent
SEEDS = [0, 1, 42, 2024, 987654321]
SCENARIO_SEEDS = [0, 42, 2024]
# Seeds without a scenario + each scenario × a few seeds
ALL_CASES = [(s, None) for s in SEEDS] + [
    (s, name) for name in sorted(SCENARIOS) for s in SCENARIO_SEEDS
]
FORCED_TYPE = {
    "goal": EventType.GOAL,
    "red_card": EventType.RED_CARD,
    "penalty": EventType.PENALTY,
}


def _run_cli(seed: int, hash_seed: str, *extra: str) -> bytes:
    env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, "-m", "app.generator", "--seed", str(seed), *extra],
        cwd=ROOT, env=env, capture_output=True, check=True,
    )
    return result.stdout


# --- determinism -----------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_same_seed_same_output(seed):
    assert to_jsonl(generate_match(seed)) == to_jsonl(generate_match(seed))


@pytest.mark.parametrize("scenario", [None, "late_comeback"])
def test_same_seed_same_output_across_processes(scenario):
    extra = ("--scenario", scenario) if scenario else ()
    a = _run_cli(42, "1", *extra)
    b = _run_cli(42, "2", *extra)
    assert a == b
    assert a.decode("utf-8") == to_jsonl(generate_match(42, scenario))


def test_cli_writes_file(tmp_path):
    out = tmp_path / "match.jsonl"
    subprocess.run(
        [sys.executable, "-m", "app.generator", "--seed", "7", "--out", str(out)],
        cwd=ROOT, check=True,
    )
    assert out.read_text(encoding="utf-8") == to_jsonl(generate_match(7))


def test_different_seed_different_output():
    assert to_jsonl(generate_match(42)) != to_jsonl(generate_match(43))


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_scenario_same_seed_same_output(name):
    assert to_jsonl(generate_match(42, name)) == to_jsonl(generate_match(42, name))
    assert to_jsonl(generate_match(42, SCENARIOS[name])) == to_jsonl(generate_match(42, name))


def test_scenarios_differ_from_each_other():
    outputs = {to_jsonl(generate_match(42, name)) for name in [None, *SCENARIOS]}
    assert len(outputs) == len(SCENARIOS) + 1


# --- stream integrity ----------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_jsonl_lines_are_valid_json(seed):
    lines = to_jsonl(generate_match(seed)).splitlines()
    assert lines
    for line in lines:
        assert isinstance(json.loads(line), dict)


@pytest.mark.parametrize("seed,scenario", ALL_CASES)
def test_stream_is_consistent(seed, scenario):
    events = generate_match(seed, scenario)

    assert [e.seq for e in events] == list(range(len(events)))
    assert len({e.match_id for e in events}) == 1

    times = [(e.period, e.minute * 60 + e.second) for e in events]
    assert times == sorted(times)

    assert events[0].type is EventType.MATCH_META
    assert events[0].data["scenario"] == scenario
    assert events[1].type is EventType.KICKOFF
    assert events[-1].type is EventType.FULL_TIME
    assert sum(e.type is EventType.HALF_TIME for e in events) == 1
    assert sum(e.type is EventType.FULL_TIME for e in events) == 1

    goals = {"home": 0, "away": 0}
    for e in events:
        if e.type is EventType.GOAL:
            goals[e.team] += 1
        assert e.score == goals
    assert events[-1].score == goals

    for e in events:
        if e.x is not None:
            assert 0.0 <= e.x <= PITCH_LENGTH
            assert 0.0 <= e.y <= PITCH_WIDTH


@pytest.mark.parametrize("seed,scenario", ALL_CASES)
def test_names_are_synthetic(seed, scenario):
    events = generate_match(seed, scenario)
    teams = events[0].data["teams"]

    rostered = set()
    for side in SIDES:
        city = teams[side]["name"].rsplit(" ", 1)[0]
        assert city in TEAM_CITIES
        rostered.update(teams[side]["lineup"], teams[side]["bench"])
    assert teams["home"]["name"] != teams["away"]["name"]

    for name in rostered:
        first, last = name.split(" ", 1)
        assert first in FIRST_NAMES
        assert last in LAST_NAMES

    for e in events:
        if e.player is not None:
            assert e.player in rostered
        if e.type is EventType.SUBSTITUTION:
            assert e.data["player_in"] in rostered


# --- squad integrity ---------------------------------------------------------


@pytest.mark.parametrize("seed,scenario", ALL_CASES)
def test_departed_players_never_reappear(seed, scenario):
    events = generate_match(seed, scenario)
    teams = events[0].data["teams"]
    bench = {side: set(teams[side]["bench"]) for side in SIDES}
    appeared: set[str] = set()
    gone: set[str] = set()

    for e in events:
        if e.player is not None:
            assert e.player not in gone, f"seq {e.seq}: {e.player} had already left the pitch"
            appeared.add(e.player)
        if e.type is EventType.SUBSTITUTION:
            sub_in = e.data["player_in"]
            assert sub_in in bench[e.team]
            assert sub_in not in appeared and sub_in not in gone
            bench[e.team].remove(sub_in)
            gone.add(e.player)
        elif e.type is EventType.RED_CARD:
            gone.add(e.player)


@pytest.mark.parametrize("seed,scenario", ALL_CASES)
def test_at_most_eleven_on_pitch(seed, scenario):
    events = generate_match(seed, scenario)
    teams = events[0].data["teams"]
    on_pitch = {side: set(teams[side]["lineup"]) for side in SIDES}

    for e in events:
        if e.player is not None:
            assert e.player in on_pitch[e.team], f"seq {e.seq}: {e.player} is not on the pitch"
        if e.type is EventType.SUBSTITUTION:
            on_pitch[e.team].remove(e.player)
            on_pitch[e.team].add(e.data["player_in"])
        elif e.type is EventType.RED_CARD:
            on_pitch[e.team].remove(e.player)
        for side in SIDES:
            assert len(on_pitch[side]) <= LINEUP_SIZE


# --- statistical realism -------------------------------------------------

# Per-match average; kept deliberately wide, the aim is to catch obvious drift.
STAT_RANGES = {
    EventType.GOAL: (1.5, 4.0),
    EventType.SHOT: (12, 30),
    EventType.CORNER: (3, 12),
    EventType.YELLOW_CARD: (2, 7),
    EventType.RED_CARD: (0.03, 0.25),
    EventType.PENALTY: (0.05, 0.6),
}


def test_averages_over_200_seeds_are_realistic():
    n = 200
    counts = Counter()
    for seed in range(n):
        counts.update(e.type for e in generate_match(seed))
    for etype, (lo, hi) in STAT_RANGES.items():
        avg = counts[etype] / n
        assert lo <= avg <= hi, f"{etype.value}: per match {avg:.3f}, expected {lo}–{hi}"


# --- scenarios ---------------------------------------------------------------


@pytest.mark.parametrize("seed", SCENARIO_SEEDS)
@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_scenario_forced_events_present(name, seed):
    scenario = SCENARIOS[name]
    events = generate_match(seed, name)
    for f in scenario.forced:
        hits = [
            e for e in events
            if e.type is FORCED_TYPE[f.kind]
            and e.team == f.team
            and e.period == f.period
            and f.minute <= e.minute <= f.minute + 1
            and (f.outcome is None or e.outcome == f.outcome)
        ]
        assert hits, f"{name} seed={seed}: forced event missing: {f}"
    assert events[-1].score == scenario.final_score


def test_dominant_loss_home_dominates_but_loses():
    # In a single match the share moves by ±0.04 (attack chains are long); hence the average.
    shares, shots = [], Counter()
    for seed in range(50):
        events = generate_match(seed, "dominant_loss")
        touches = Counter(
            e.team for e in events if e.type in (EventType.PASS, EventType.DRIBBLE)
        )
        shares.append(touches["home"] / (touches["home"] + touches["away"]))
        shots.update(e.team for e in events if e.type is EventType.SHOT)
        assert events[-1].score["home"] < events[-1].score["away"]
    assert sum(shares) / len(shares) > 0.58
    assert min(shares) > 0.5
    assert shots["home"] > 3 * shots["away"]


def test_unknown_scenario_raises():
    with pytest.raises(ValueError, match="Unknown scenario"):
        generate_match(42, "no_such_scenario")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"minute": 95, "kind": "goal", "team": "home"},
        {"minute": 10, "kind": "own_goal", "team": "home"},
        {"minute": 10, "kind": "goal", "team": "neutral"},
        {"minute": 10, "kind": "penalty", "team": "home"},
        {"minute": 10, "kind": "goal", "team": "home", "outcome": "scored"},
    ],
)
def test_forced_event_validation(kwargs):
    with pytest.raises(ValueError):
        ForcedEvent(**kwargs)
