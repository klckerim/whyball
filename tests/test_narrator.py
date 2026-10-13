import pytest

from app.explain import verify_claim
from app.explain.narrator import (
    FAKE_MODES,
    FakeNarrator,
    Feedback,
    FeedbackItem,
    Narrator,
    TemplateNarrator,
    make_narrator,
)
from app.explain.text_lint import Roster, lint_text
from tests.explain_helpers import MOMENT_TYPES, moment_case

EXPECTED = {
    "correct": None,
    "wrong_number": ("verify", "value_mismatch"),
    "foreign_event": ("verify", "foreign_event"),
    "hallucinated_name": ("lint", "unknown_name"),
    "unsupported_sentence": ("lint", "unsupported_number"),
    "fixes_after_feedback": ("verify", "value_mismatch"),  # without feedback
}


def _problems(draft, events):
    lint = {("lint", i.code) for i in lint_text(draft.text, draft.claims, Roster.from_events(events)).issues}
    verify = {("verify", r.reason) for r in (verify_claim(c, events) for c in draft.claims) if not r.ok}
    return lint | verify


def test_narrators_satisfy_protocol():
    events, _ = moment_case("goal")
    assert isinstance(TemplateNarrator(events), Narrator)
    for mode in FAKE_MODES:
        assert isinstance(FakeNarrator(events, mode), Narrator)


@pytest.mark.parametrize("mtype", MOMENT_TYPES)
@pytest.mark.parametrize("mode", FAKE_MODES)
def test_fake_mode_produces_expected_problem(mode, mtype):
    events, moment = moment_case(mtype)
    for lang in ("en",):
        problems = _problems(FakeNarrator(events, mode).narrate(moment, "neutral", lang), events)
        if EXPECTED[mode] is None:
            assert not problems
        else:
            assert EXPECTED[mode] in problems, problems


@pytest.mark.parametrize("mtype", MOMENT_TYPES)
def test_fixes_after_feedback_returns_correct_draft_when_given_feedback(mtype):
    events, moment = moment_case(mtype)
    feedback = Feedback(1, (FeedbackItem("verify", "value_mismatch", claim_index=0),))
    fixed = FakeNarrator(events, "fixes_after_feedback").narrate(moment, "neutral", "en", feedback)
    assert fixed == TemplateNarrator(events).narrate(moment, "neutral", "en")


def test_fake_counts_calls_and_is_deterministic():
    events, moment = moment_case("goal")
    narrator = FakeNarrator(events, "wrong_number")
    first = narrator.narrate(moment, "neutral", "en")
    assert narrator.narrate(moment, "neutral", "en") == first
    assert narrator.calls == 2


def test_make_narrator():
    events, _ = moment_case("goal")
    assert isinstance(make_narrator("template", events), TemplateNarrator)
    fake = make_narrator("fake:hallucinated_name", events)
    assert isinstance(fake, FakeNarrator) and fake.mode == "hallucinated_name"
    for bad in ("gpt", "fake:", "fake:nonsense"):
        with pytest.raises(ValueError):
            make_narrator(bad, events)
