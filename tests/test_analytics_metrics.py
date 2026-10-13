import pytest

from app.analytics import DEFAULT_CONFIG, MatchTracker, metrics_at, pressure_index
from app.generator import SCENARIOS, Event, EventType, generate_match

CASES = [(s, None) for s in (0, 42, 100)] + [
    (s, name) for name in sorted(SCENARIOS) for s in (0, 42)
]


def _cut_points(events):
    n = len(events)
    half = next(i for i, e in enumerate(events) if e.type is EventType.HALF_TIME)
    return sorted({1, 2, half, half + 1, half + 2, n // 2, n - 1, n, *range(50, n, 50)})


# --- lookahead ----------------------------------------------------------


@pytest.mark.parametrize("seed,scenario", CASES)
def test_prefix_equals_cut_stream(seed, scenario):
    events = generate_match(seed, scenario)
    for n in _cut_points(events):
        assert metrics_at(events[:n]) == metrics_at(events, until_seq=n - 1), f"N={n}"


@pytest.mark.parametrize("minute", [0, 10, 44, 45, 46, 60, 89, 95])
def test_until_minute_equals_prefix(minute):
    events = generate_match(42)
    period = 1 if minute < 45 else 2
    prefix = [e for e in events if (e.period, e.minute) <= (period, minute)]
    assert prefix == events[: len(prefix)]
    assert metrics_at(events, until_minute=minute) == metrics_at(prefix)


def test_future_events_do_not_matter():
    events = generate_match(42)
    n = len(events) // 2
    spliced = events[:n] + generate_match(43)[n:]
    assert metrics_at(spliced, until_seq=n - 1) == metrics_at(events, until_seq=n - 1)


# --- basic correctness ---------------------------------------------------------


@pytest.mark.parametrize("seed,scenario", CASES)
def test_full_stream_sanity(seed, scenario):
    events = generate_match(seed, scenario)
    tracker = MatchTracker()
    for e in events:
        tracker.update(e)
        assert -1.0 <= tracker.pressure_balance() <= 1.0
    snap = tracker.snapshot()
    for side in ("home", "away"):
        assert snap.shots[side] == sum(
            e.type is EventType.SHOT and e.team == side for e in events
        )
    assert snap.possession["home"] + snap.possession["away"] == pytest.approx(1.0)
    assert snap.field_tilt["home"] + snap.field_tilt["away"] == pytest.approx(1.0)
    assert snap.score == events[-1].score
    assert snap.seq == events[-1].seq


def test_empty_stream():
    snap = metrics_at([])
    assert snap.seq is None
    assert snap.possession == {"home": 0.5, "away": 0.5}
    assert snap.pressure_balance == 0.0


# --- hand-built streams --------------------------------------------------


def _ev(seq, period, minute, second, etype, team=None, x=None):
    return Event(
        match_id="t", seq=seq, period=period, minute=minute, second=second,
        type=etype, team=team, x=x, y=None if x is None else 34.0,
    )


def test_final_third_entries():
    P, D = EventType.PASS, EventType.DRIBBLE
    events = [
        _ev(0, 1, 1, 0, P, "home", 50.0),   # midfield
        _ev(1, 1, 1, 5, P, "home", 72.0),   # entry (home ≥ 70)
        _ev(2, 1, 1, 9, D, "home", 80.0),   # already inside
        _ev(3, 1, 1, 15, P, "away", 60.0),  # possession changed
        _ev(4, 1, 1, 20, P, "home", 75.0),  # re-entry
        _ev(5, 1, 1, 30, P, "away", 30.0),  # away entry (away ≤ 35)
    ]
    snap = metrics_at(events)
    assert snap.final_third_entries == {"home": 2, "away": 1}
    assert snap.field_tilt["home"] == pytest.approx(2 / 3)
    assert snap.possession == {"home": 4 / 6, "away": 2 / 6}


def test_pressure_window_skips_half_time_break():
    S = EventType.SHOT
    # Shots from outside the final third: no entries counted, only w_shot is measured.
    events = [
        _ev(0, 1, 10, 0, S, "home", 60.0),            # 600 s played
        _ev(1, 1, 46, 0, S, "home", 60.0),            # 2760 s played
        _ev(2, 1, 47, 0, EventType.HALF_TIME),        # first half 2820 s
        _ev(3, 2, 45, 0, EventType.KICKOFF, "away", 52.5),
        _ev(4, 2, 50, 0, S, "away", 45.0),            # played 2820 + 300 = 3120
        _ev(5, 2, 55, 30, S, "away", 45.0),           # played 2820 + 630 = 3450
    ]
    w = DEFAULT_CONFIG.w_shot
    # At 50:00 the 10-minute window starts at 2520 s played: the 46:00 shot is inside, the 10:00 one outside.
    snap = metrics_at(events, until_seq=4)
    assert snap.played_seconds == 3120
    assert snap.pressure == {"home": w, "away": w}
    # At 55:30 the window starts at 2850 s: the first-half shots drop out.
    assert pressure_index(events) == {"home": 0.0, "away": 2 * w, "balance": -1.0}
