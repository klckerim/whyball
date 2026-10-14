"""Sentence parts: the pieces join to the card text exactly and mark claim values by index, never by matching."""

import pytest

from app.explain.narrator import TemplateNarrator
from app.explain.pipeline import NarrationRecord, run_moment
from app.explain.template_narrator import Part, narrate
from tests.explain_helpers import MOMENT_TYPES, moment_case


def _check(rec):
    assert rec.parts, "no parts recorded"
    assert "".join(p.text for p in rec.parts) == rec.text
    assert all(p.claim is None or 0 <= p.claim < len(rec.claims) for p in rec.parts)
    assert all(p.text for p in rec.parts)
    return rec


@pytest.mark.parametrize("case", MOMENT_TYPES)
def test_template_parts_join_to_the_text(case):
    events, moment = moment_case(case)
    rec = _check(run_moment(moment, TemplateNarrator(events), events))
    assert rec.source == "template"


@pytest.mark.parametrize("case", MOMENT_TYPES)
def test_claim_parts_carry_the_claim_display(case):
    events, moment = moment_case(case)
    rec = run_moment(moment, TemplateNarrator(events), events)
    from app.explain.slots import format_value
    for p in rec.parts:
        if p.claim is not None:
            c = rec.claims[p.claim]
            assert p.text == format_value(c.metric, c.value, "en")


def test_score_sentence_marks_both_numbers():
    events, moment = moment_case("goal")
    n = narrate(moment, events)
    s = n.sentences[-1]
    marked = [(p.text, s.claims[p.claim].subject.team) for p in s.parts if p.claim is not None]
    assert [t for _, t in marked] == ["home", "away"]


def test_record_roundtrip_keeps_parts():
    events, moment = moment_case("dominance_without_reward")
    rec = run_moment(moment, TemplateNarrator(events), events)
    assert NarrationRecord.from_dict(rec.to_dict()).parts == rec.parts


def test_old_cache_entry_without_parts_loads():
    events, moment = moment_case("red_card")
    d = run_moment(moment, TemplateNarrator(events), events).to_dict()
    del d["parts"]
    assert NarrationRecord.from_dict(d).parts == ()


def test_fallback_parts_join_with_offset_claim_indices(monkeypatch):
    from app.explain.narrator import FakeNarrator
    events, moment = moment_case("dominance_without_reward")
    rec = run_moment(moment, FakeNarrator(events, "wrong_number"), events)
    assert rec.source == "template_fallback"
    _check(rec)


def test_part_is_plain_by_default():
    assert Part("x").claim is None
