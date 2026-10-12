import json
from dataclasses import replace

import pytest

from app.analytics import MatchTracker
from app.explain import Claim, MatchTime, Subject, event_ref, verify_claim
from app.explain.claims import KICKOFF
from app.generator import EventType
from app.generator.freeze import DEMO_DIR, demo_filename
from app.generator.models import read_jsonl

EVENTS = read_jsonl(DEMO_DIR / demo_filename("red_card_swing", 42))
OTHER = read_jsonl(DEMO_DIR / demo_filename(None, 100))
GOALS = [e for e in EVENTS if e.type is EventType.GOAL]  # 22' home, 61' away, 84' away
RED = next(e for e in EVENTS if e.type is EventType.RED_CARD)  # 38' home
T = MatchTime.of


def _corrupt(e):
    flipped = {"home": "away", "away": "home"}.get(e.team)
    return replace(e, team=flipped, type=EventType.SHOT if e.team else e.type)


def _refs(events):
    return tuple(event_ref(e) for e in events)


def _until(t):
    return [e for e in EVENTS if T(e) <= t]


def _first_goal_claim(**changes):
    g = GOALS[0]
    claim = Claim(
        "count", Subject(g.team, g.player), "goals", "eq", 1, T(g), T(g), (event_ref(g),)
    )
    return replace(claim, **changes)


def _possession_claim(value):
    touches = [e for e in _until(T(RED)) if e.type in (EventType.PASS, EventType.DRIBBLE)]
    share = sum(e.team == "home" for e in touches) / len(touches)
    claim = Claim(
        "ratio", Subject("home"), "possession", "approx", round(share, 2),
        KICKOFF, T(RED), (event_ref(RED),),
    )
    return replace(claim, value=value) if value is not None else claim


def _shots_claim(team, end):
    shots = [e for e in EVENTS if e.type is EventType.SHOT and e.team == team and T(e) <= end]
    return Claim("count", Subject(team), "shots", "eq", len(shots), KICKOFF, end, _refs(shots))


# --- doğru iddialar geçer ------------------------------------------------------------


def test_true_claims_pass():
    tracker = MatchTracker()
    for e in _until(T(GOALS[2])):
        tracker.update(e)
    claims = [
        _first_goal_claim(),
        _shots_claim("home", T(RED)),
        _shots_claim("away", T(GOALS[2])),
        Claim("count", Subject("home"), "red_cards", "eq", 1, KICKOFF, T(RED), (event_ref(RED),)),
        Claim("count", Subject("away"), "goals", "eq", 0, KICKOFF, T(RED), ()),
        _possession_claim(None),
        Claim("state", Subject("away"), "score", "eq", 2, KICKOFF, T(GOALS[2]), (event_ref(GOALS[2]),)),
        Claim("state", Subject("home"), "score_margin", "lt", 0, KICKOFF, T(GOALS[2]), (event_ref(GOALS[2]),)),
        Claim("state", Subject("away"), "min_score_margin", "eq", -1, KICKOFF, T(GOALS[2]), (event_ref(GOALS[0]),)),
        Claim(
            "state", Subject("away"), "pressure_balance", "approx",
            round(-tracker.pressure_balance(), 2), KICKOFF, T(GOALS[2]), (event_ref(GOALS[2]),),
        ),
    ]
    for claim in claims:
        result = verify_claim(claim, EVENTS)
        assert result.ok, (claim.describe(), result)


# --- bozulmuş sayı reddedilir ---------------------------------------------------------


@pytest.mark.parametrize(
    "claim",
    [
        _first_goal_claim(value=2),
        _first_goal_claim(comparison="gt"),
        _possession_claim(0.99),
        Claim("state", Subject("away"), "score", "eq", 3, KICKOFF, T(GOALS[2]), (event_ref(GOALS[2]),)),
    ],
    ids=["count", "comparison", "ratio", "state"],
)
def test_tampered_number_is_rejected(claim):
    result = verify_claim(claim, EVENTS)
    assert not result.ok and result.reason == "value_mismatch"


# --- başka maçtan event id reddedilir --------------------------------------------------


def test_event_id_from_another_match_is_rejected():
    other_goal = next(e for e in OTHER if e.type is EventType.GOAL)
    assert verify_claim(_first_goal_claim(event_ids=(event_ref(other_goal),)), EVENTS).reason == "foreign_event"
    # Aynı seq, farklı maç kimliği: seq tek başına yetmez.
    same_seq = f"{OTHER[0].match_id}#{GOALS[0].seq}"
    assert verify_claim(_first_goal_claim(event_ids=(same_seq,)), EVENTS).reason == "foreign_event"


# --- gelecekteki olaya dayanan iddia reddedilir ------------------------------------------


def test_claim_citing_future_event_is_rejected():
    # 38'deki iddia, 61'deki gole dayanıyor.
    claim = Claim(
        "count", Subject("away"), "goals", "eq", 1, KICKOFF, T(RED), (event_ref(GOALS[1]),)
    )
    assert verify_claim(claim, EVENTS).reason == "future_event"
    state = Claim("state", Subject("away"), "score", "eq", 1, KICKOFF, T(RED), (event_ref(GOALS[1]),))
    assert verify_claim(state, EVENTS).reason == "future_event"


def test_future_events_are_not_counted():
    # Dayanak göstermeden "38'e kadar away 1 gol" iddiası: 61' golü görülmez.
    claim = Claim("count", Subject("away"), "goals", "eq", 1, KICKOFF, T(RED), ())
    result = verify_claim(claim, EVENTS)
    assert result.reason == "value_mismatch" and result.actual == 0


@pytest.mark.parametrize(
    "claim",
    [_first_goal_claim(end=T(RED)), _possession_claim(None), _shots_claim("home", T(RED))],
    ids=["count", "ratio", "count-many"],
)
def test_verification_ignores_everything_after_end(claim):
    # Gelecek olaylar bozulur (zaman aynı, takım/tip değişir); sonuç değişmemeli.
    k = next(i for i, e in enumerate(EVENTS) if T(e) > claim.end)
    spliced = EVENTS[:k] + [_corrupt(e) for e in EVENTS[k:]]
    assert verify_claim(claim, spliced) == verify_claim(claim, EVENTS)
    assert verify_claim(claim, EVENTS).ok


# --- diğer ret nedenleri -----------------------------------------------------------------


@pytest.mark.parametrize(
    "claim,reason",
    [
        (_first_goal_claim(metric="xg"), "unknown_metric"),
        (_first_goal_claim(kind="ratio"), "kind_mismatch"),
        (_first_goal_claim(comparison="about"), "invalid_comparison"),
        (_first_goal_claim(start=T(RED)), "invalid_range"),
        (_first_goal_claim(subject=Subject("neutral")), "invalid_subject"),
        (replace(_possession_claim(None), subject=Subject()), "invalid_subject"),
        (replace(_possession_claim(None), event_ids=()), "missing_evidence"),
        (_first_goal_claim(event_ids=(f"{EVENTS[0].match_id}#99999",)), "unknown_event"),
        (_first_goal_claim(event_ids=("not-a-ref",)), "unknown_event"),
        (_first_goal_claim(start=T(RED), end=T(GOALS[2])), "evidence_out_of_range"),
        (replace(_shots_claim("home", T(RED)), event_ids=_shots_claim("home", T(RED)).event_ids[1:]), "evidence_mismatch"),
    ],
)
def test_invalid_claims_are_rejected(claim, reason):
    assert verify_claim(claim, EVENTS).reason == reason


def test_claim_round_trips_through_json():
    claim = _possession_claim(None)
    assert Claim.from_dict(json.loads(json.dumps(claim.to_dict()))) == claim
