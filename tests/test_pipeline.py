import json

import pytest

from app.explain import select_moments
from app.explain.narrator import FakeNarrator, InvalidNarratorOutput, TemplateNarrator
from app.explain.pipeline import NarrationRecord, run_match, run_moment
from app.explain.template_narrator import narrate as template_narrate
from tests.explain_helpers import MOMENT_TYPES, match, moment_case

FAILING_MODES = {
    "wrong_number": "value_mismatch",
    "foreign_event": "foreign_event",
    "hallucinated_name": "unknown_name",
    "unsupported_sentence": "unsupported_number",
}
LANGS = ("en",)


def _steps(record):
    return [s["step"] for s in record.trace]


def _assert_publishable(record):
    assert record.ok
    assert record.text
    assert record.claims and all(r.ok for r in record.verification)
    assert len(record.claims) == len(record.verification)
    assert record.lint_issues == ()


# --- ilk denemede geçen --------------------------------------------------------------


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("mtype", MOMENT_TYPES)
def test_correct_passes_on_first_attempt(mtype, lang):
    events, moment = moment_case(mtype)
    narrator = FakeNarrator(events, "correct")
    record = run_moment(moment, narrator, events, language=lang)
    assert (record.attempts, record.source, narrator.calls) == (1, "llm", 1)
    assert _steps(record) == ["narrate", "lint", "verify", "accept"]
    _assert_publishable(record)


def test_template_narrator_is_labelled_template():
    events, moment = moment_case("goal")
    record = run_moment(moment, TemplateNarrator(events), events)
    assert (record.attempts, record.source) == (1, "template")
    _assert_publishable(record)


# --- retry ile düzelen ------------------------------------------------------------------


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("mtype", MOMENT_TYPES)
def test_fixes_after_feedback_succeeds_on_retry(mtype, lang):
    events, moment = moment_case(mtype)
    narrator = FakeNarrator(events, "fixes_after_feedback")
    record = run_moment(moment, narrator, events, language=lang)
    assert (record.attempts, record.source, narrator.calls) == (2, "llm", 2)
    assert _steps(record) == [
        "narrate", "lint", "verify", "feedback", "narrate", "lint", "verify", "accept"
    ]
    feedback = record.trace[3]
    assert feedback["attempt"] == 1 and "value_mismatch" in feedback["codes"] and feedback["will_retry"]
    assert record.trace[4]["feedback"] == feedback["codes"]
    assert record.trace[2]["ok"] is False and record.trace[6]["ok"] is True
    _assert_publishable(record)


# --- yedeğe düşen ------------------------------------------------------------------------


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("mtype", MOMENT_TYPES)
@pytest.mark.parametrize("mode", FAILING_MODES)
def test_failing_modes_fall_back_to_labelled_template(mode, mtype, lang):
    events, moment = moment_case(mtype)
    narrator = FakeNarrator(events, mode)
    record = run_moment(moment, narrator, events, language=lang)

    assert (record.attempts, record.source, narrator.calls) == (3, "template_fallback", 3)
    assert _steps(record) == ["narrate", "lint", "verify", "feedback"] * 3 + ["fallback"]
    feedbacks = [s for s in record.trace if s["step"] == "feedback"]
    assert [f["attempt"] for f in feedbacks] == [1, 2, 3]
    assert all(FAILING_MODES[mode] in f["codes"] for f in feedbacks)
    assert [f["will_retry"] for f in feedbacks] == [True, True, False]
    assert record.trace[-1]["reason"] == "max_retries_exceeded"

    assert record.text == template_narrate(moment, events).published(lang)
    _assert_publishable(record)


# --- ölçüm modu: deneme kaydı ---------------------------------------------------------------


def test_on_attempt_sees_every_draft_but_record_and_cache_do_not(tmp_path):
    from app.explain.cache import NarrationCache

    events, moment = moment_case("goal")
    logs = []
    cache = NarrationCache(tmp_path)
    record = run_moment(moment, FakeNarrator(events, "wrong_number"), events, cache=cache,
                        on_attempt=logs.append)
    assert [log.attempt for log in logs] == [1, 2, 3]
    assert all(not log.accepted and log.draft is not None for log in logs)
    assert all("value_mismatch" in [i.code for i in log.items] for log in logs)
    assert all(len(log.claims) == len(log.verification) for log in logs)
    stored = json.dumps(record.to_dict()) + "".join(p.read_text() for p in tmp_path.rglob("*") if p.is_file())
    assert logs[0].draft.text not in stored  # reddedilen taslak yayına ve önbelleğe girmez


def test_on_attempt_reports_accepted_and_narrator_errors():
    events, moment = moment_case("goal")
    logs = []
    run_moment(moment, FakeNarrator(events, "fixes_after_feedback"), events, on_attempt=logs.append)
    assert [log.accepted for log in logs] == [False, True]

    class Broken(FakeNarrator):
        def narrate(self, *args, **kwargs):
            raise InvalidNarratorOutput("bozuk JSON")

    logs = []
    run_moment(moment, Broken(events, "correct"), events, on_attempt=logs.append)
    assert len(logs) == 3 and all(log.error is not None and log.draft is None for log in logs)


# --- kayıt ve maç düzeyi ------------------------------------------------------------------


def test_record_round_trips_through_json():
    events, moment = moment_case("score_change")
    record = run_moment(moment, FakeNarrator(events, "fixes_after_feedback"), events)
    assert NarrationRecord.from_dict(json.loads(json.dumps(record.to_dict()))) == record


def test_run_match_narrates_selected_moments():
    events, moments = match(42, "red_card_swing")
    results = run_match(events, FakeNarrator(events, "correct"))
    assert [m for m, _ in results] == select_moments(moments)
    assert all(r.source == "llm" and r.ok for _, r in results)


def test_only_english_is_accepted():
    events, moment = moment_case("goal")
    with pytest.raises(ValueError, match="only 'en' is supported"):
        run_moment(moment, TemplateNarrator(events), events, language="tr")
    with pytest.raises(ValueError, match="only 'en' is supported"):
        run_match(events, TemplateNarrator(events), language="tr")


@pytest.mark.parametrize("cli", ["app.explain.__main__", "app.explain.run"])
def test_cli_rejects_non_english_language(cli, capsys):
    import importlib

    main = importlib.import_module(cli).main
    with pytest.raises(SystemExit) as exc:
        main(["--input", "data/demo/red_card_swing_seed42.jsonl", "--lang", "tr"])
    assert exc.value.code == 2
    assert "--lang" in capsys.readouterr().err
