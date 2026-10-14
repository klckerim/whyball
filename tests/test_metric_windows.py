"""Every metric's window, as /api/metrics serves it, against what `claims.measure` does and what the Verifier is shown."""

import asyncio

import pytest

from app.agents import tools
from app.agents.guard import guard_check
from app.agents.verifier import _claim_record, verifier_record
from app.api.main import METRICS
from app.explain.claims import COUNT_METRICS, METRIC_KINDS, Claim, MatchTime, Subject, measure
from app.explain.labels import METRIC_DEFINITIONS, METRICS_IGNORING_START, metric_window
from app.explain.menu import build_menu
from app.generator import generate_match
from app.generator.models import EventType
from tests.explain_helpers import moment_case

API = {m.id: m for m in METRICS.metrics}
POOL = [generate_match(s, sc) for sc in ("late_comeback", "red_card_swing", "dominant_loss", None) for s in range(4)]
END = MatchTime(2, 90, 0)
STARTS = [MatchTime(1, 0, 0), MatchTime(1, 30, 0), MatchTime(2, 50, 0), MatchTime(2, 75, 0)]


def test_there_are_eighteen_metrics_and_the_registry_serves_all_of_them():
    assert len(METRIC_KINDS) == 18 == len(API) == len(METRIC_DEFINITIONS)


@pytest.mark.parametrize("metric", METRIC_KINDS)
def test_the_window_in_the_code_registry_is_the_one_the_api_serves(metric):
    kind, minutes = metric_window(metric)
    assert (API[metric].window.type, API[metric].window.minutes) == (kind, minutes)


def _start_changes_the_value(metric: str) -> bool:
    """Whether the claim's start matters to `measure`, shown on real matches."""
    for events in POOL:
        for team in ("home", "away"):
            subject = Subject(team)
            if METRIC_KINDS[metric] == "count":
                pred = COUNT_METRICS[metric]
                for e in events:
                    if pred(e) and e.team == team:  # start just before / just after a counted event
                        t = MatchTime.of(e)
                        after = MatchTime(t.period, t.minute, min(t.second + 1, 59)) if t.second < 59 else MatchTime(t.period, t.minute + 1, 0)
                        if measure(metric, subject, t, END, events).value != measure(metric, subject, after, END, events).value:
                            return True
            elif len({measure(metric, subject, s, END, events).value for s in STARTS}) > 1:
                return True
    return False


@pytest.mark.parametrize("metric", METRIC_KINDS)
def test_metrics_the_record_gives_no_from_for_do_not_use_the_start(metric):
    assert _start_changes_the_value(metric) == (metric not in METRICS_IGNORING_START)


def test_the_four_metrics_that_ignore_the_start():
    assert METRICS_IGNORING_START == {"score", "score_margin", "players_on_pitch", "pressure_balance"}
    assert {m for m, a in API.items() if a.window.type == "rolling"} == {"pressure_balance"}


@pytest.fixture(scope="module")
def ctx_events():
    events, moment = moment_case("goal")
    return events, moment, tools.slot_context(moment, events)


@pytest.mark.parametrize("metric", METRIC_KINDS)
def test_the_verifier_is_shown_each_metrics_window_and_definition_from_the_api(metric, ctx_events):
    events, moment, ctx = ctx_events
    claim = Claim(METRIC_KINDS[metric], Subject("home"), metric, "eq", 1.0, MatchTime(1, 0, 0), MatchTime(1, 22, 0), ())
    rec = _claim_record("c", claim, ctx)
    assert rec["window"] == {"type": API[metric].window.type, "minutes": API[metric].window.minutes}
    assert rec["definition"] == API[metric].definition
    assert ("from" in rec) == (metric not in METRICS_IGNORING_START) and rec["to"] == "22'"


def test_the_pressure_claim_no_longer_shows_a_range_that_contradicts_its_label():
    events, moment = moment_case("pressure_shift")
    menu = build_menu(moment, events)
    ctx = tools.slot_context(moment, events)
    g = asyncio.run(guard_check("{clause:pressure}, and {clause:shots}.", menu, ctx))
    assert g.ok
    rec = verifier_record(moment, g, events, ctx)
    pressure = next(c for c in rec["claims"] if c["id"] == "pressure")
    assert "from" not in pressure and pressure["window"] == {"type": "rolling", "minutes": 10.0}
    assert "last 10 minutes" in pressure["definition"]
    shots = next(c for c in rec["claims"] if c["id"] == "shots_for")
    assert "from" in shots  # a count over a range keeps its range
