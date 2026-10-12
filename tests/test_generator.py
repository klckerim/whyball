import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.generator import EventType, generate_match, to_jsonl
from app.generator.engine import PITCH_LENGTH, PITCH_WIDTH
from app.generator.names import FIRST_NAMES, LAST_NAMES, TEAM_CITIES

ROOT = Path(__file__).resolve().parent.parent
SEEDS = [0, 1, 42, 2024, 987654321]


def _run_cli(seed: int, hash_seed: str) -> bytes:
    env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, "-m", "app.generator", "--seed", str(seed)],
        cwd=ROOT, env=env, capture_output=True, check=True,
    )
    return result.stdout


@pytest.mark.parametrize("seed", SEEDS)
def test_same_seed_same_output(seed):
    assert to_jsonl(generate_match(seed)) == to_jsonl(generate_match(seed))


def test_same_seed_same_output_across_processes():
    a = _run_cli(42, hash_seed="1")
    b = _run_cli(42, hash_seed="2")
    assert a == b
    assert a.decode("utf-8") == to_jsonl(generate_match(42))


def test_cli_writes_file(tmp_path):
    out = tmp_path / "match.jsonl"
    subprocess.run(
        [sys.executable, "-m", "app.generator", "--seed", "7", "--out", str(out)],
        cwd=ROOT, check=True,
    )
    assert out.read_text(encoding="utf-8") == to_jsonl(generate_match(7))


def test_different_seed_different_output():
    assert to_jsonl(generate_match(42)) != to_jsonl(generate_match(43))


@pytest.mark.parametrize("seed", SEEDS)
def test_jsonl_lines_are_valid_json(seed):
    lines = to_jsonl(generate_match(seed)).splitlines()
    assert lines
    for line in lines:
        assert isinstance(json.loads(line), dict)


@pytest.mark.parametrize("seed", SEEDS)
def test_stream_is_consistent(seed):
    events = generate_match(seed)

    assert [e.seq for e in events] == list(range(len(events)))
    assert len({e.match_id for e in events}) == 1

    times = [(e.period, e.minute * 60 + e.second) for e in events]
    assert times == sorted(times)

    assert events[0].type is EventType.MATCH_META
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


@pytest.mark.parametrize("seed", SEEDS)
def test_names_are_synthetic(seed):
    events = generate_match(seed)
    teams = events[0].data["teams"]

    rostered = set()
    for side in ("home", "away"):
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
