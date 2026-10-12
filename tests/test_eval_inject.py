from functools import cache

from eval.inject import INJECTION_TYPES, QUICK_CORPUS, render_markdown, render_table, run_eval, uncaught


@cache
def _report():
    return run_eval(QUICK_CORPUS)


def _row(name):
    return next(r for r in _report().results if r.spec.name == name)


def test_every_injection_type_applies_somewhere():
    assert [r.spec.name for r in _report().results] == [t.name for t in INJECTION_TYPES]
    assert all(r.applicable > 0 for r in _report().results)


def test_control_has_no_false_alarms():
    control = _row("control")
    assert control.caught_before == control.caught_after == 0


def test_number_words_fix_improves_catch_rate():
    row = _row("number_words")
    assert row.caught_before == 0
    assert row.caught_after > 0


def test_claim_tampering_is_caught_by_verify():
    row = _row("number_text_and_claim")
    assert row.by_verify > 0 and row.caught_after >= row.by_verify


def test_known_gaps_are_reported_as_uncaught():
    names = {r.spec.name for r in uncaught(_report())}
    assert {"unsupported_sentence_qualitative", "sentence_start_fabricated"} <= names
    assert "control" not in names


def test_report_is_deterministic_and_complete():
    first = render_markdown(_report())
    assert render_markdown(run_eval(QUICK_CORPUS)) == first
    table = render_table(_report())
    for spec in INJECTION_TYPES:
        assert f"`{spec.name}`" in table
    assert "## Yakalanmayan türler" in first and "## Yapılan düzeltme" in first
