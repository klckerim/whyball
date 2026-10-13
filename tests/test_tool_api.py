import json
from dataclasses import replace

import pytest

from app.analytics import detect_moments, metrics_at
from app.explain import Subject, measure, verify_claim
from app.explain.claims import KICKOFF, MatchTime
from app.explain.narrator import TemplateNarrator
from app.explain.text_lint import Roster, lint_text
from app.explain.tool_api import TOOLS
from app.generator.freeze import DEMO_DIR, demo_filename
from app.generator.models import read_jsonl

MATCH_PATH = "data/demo/red_card_swing_seed42.jsonl"
EVENTS = read_jsonl(DEMO_DIR / demo_filename("red_card_swing", 42))
MOMENT = next(m for m in detect_moments(EVENTS) if m.type == "goal" and "score_change" in m.detail)
DRAFT = TemplateNarrator(EVENTS).narrate(MOMENT, "neutral", "en")
END = MatchTime.of(EVENTS[-1])


def _call(name, payload):
    """Payload and result round-trip through JSON."""
    out = TOOLS[name](json.loads(json.dumps(payload)))
    assert json.loads(json.dumps(out)) == out
    return out


@pytest.mark.parametrize(
    "match", [{"match_path": MATCH_PATH}, {"events": [e.to_dict() for e in EVENTS]}],
    ids=["path", "events"],
)
def test_verify_claim_round_trip(match):
    for claim in DRAFT.claims:
        out = _call("verify_claim", {**match, "claim": claim.to_dict()})
        direct = verify_claim(claim, EVENTS)
        assert out == {"ok": True, "result": {"ok": direct.ok, "reason": direct.reason, "actual": direct.actual}}
    tampered = replace(DRAFT.claims[0], value=DRAFT.claims[0].value + 1)
    out = _call("verify_claim", {**match, "claim": tampered.to_dict()})
    assert out["ok"] and out["result"]["ok"] is False and out["result"]["reason"] == "value_mismatch"


def test_measure_round_trip():
    out = _call("measure", {"match_path": MATCH_PATH, "metric": "goals", "subject": {"team": "away"},
                            "start": list(KICKOFF), "end": list(END)})
    direct = measure("goals", Subject("away"), KICKOFF, END, EVENTS)
    assert out["ok"] and out["result"]["value"] == direct.value
    assert out["result"]["counted_event_ids"] == [f"{EVENTS[0].match_id}#{s}" for s in direct.counted]
    ratio = _call("measure", {"match_path": MATCH_PATH, "metric": "possession", "subject": {"team": "home"},
                              "start": list(KICKOFF), "end": list(END)})
    assert ratio["result"]["value"] == measure("possession", Subject("home"), KICKOFF, END, EVENTS).value


def test_metrics_at_round_trip():
    out = _call("metrics_at", {"match_path": MATCH_PATH, "until_seq": 200})
    snap = metrics_at(EVENTS, until_seq=200)
    assert out["ok"]
    assert out["result"] == {"seq": snap.seq, "period": snap.period, "minute": snap.minute,
                             "second": snap.second, **snap.summary()}


def test_lint_text_round_trip():
    bad_text = DRAFT.text + " Arlo Quintana was everywhere."
    for text in (DRAFT.text, bad_text):
        out = _call("lint_text", {"match_path": MATCH_PATH, "text": text,
                                  "claims": [c.to_dict() for c in DRAFT.claims]})
        assert out == {"ok": True, "result": lint_text(text, DRAFT.claims, Roster.from_events(EVENTS)).to_dict()}
    assert out["result"]["issues"][0]["code"] == "unknown_name"


def test_list_metrics():
    out = _call("list_metrics", {})
    assert out["result"]["metrics"]["possession"] == "ratio"
    assert "approx" in out["result"]["comparisons"]


@pytest.mark.parametrize(
    "name,payload,code",
    [
        ("measure", {"match_path": MATCH_PATH, "metric": "xg", "start": [1, 0, 0], "end": [2, 90, 0]}, "unknown_metric"),
        ("measure", {"match_path": MATCH_PATH, "metric": "possession", "start": [1, 0, 0], "end": [2, 90, 0]}, "invalid_subject"),
        ("verify_claim", {"match_path": MATCH_PATH, "claim": {"kind": "count"}}, "invalid_input"),
        ("verify_claim", {"claim": DRAFT.claims[0].to_dict()}, "missing_match"),
        ("verify_claim", {"match_path": "../CLAUDE.md", "claim": DRAFT.claims[0].to_dict()}, "forbidden_path"),
        ("verify_claim", {"match_path": "/etc/passwd", "claim": DRAFT.claims[0].to_dict()}, "forbidden_path"),
        ("verify_claim", {"match_path": "data/demo/nope.jsonl", "claim": DRAFT.claims[0].to_dict()}, "not_found"),
    ],
)
def test_errors_are_returned_as_json(name, payload, code):
    out = _call(name, payload)
    assert out["ok"] is False and out["error"]["code"] == code


def test_lint_text_rejects_non_english_language():
    out = _call("lint_text", {"match_path": MATCH_PATH, "text": DRAFT.text, "language": "tr",
                              "claims": [c.to_dict() for c in DRAFT.claims]})
    assert not out["ok"] and out["error"]["code"] == "invalid_input"
    assert "only 'en' is supported" in out["error"]["message"]
    assert _call("lint_text", {"match_path": MATCH_PATH, "text": DRAFT.text, "language": "en",
                               "claims": [c.to_dict() for c in DRAFT.claims]})["ok"]
