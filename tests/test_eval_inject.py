from functools import cache

from eval.inject import INJECTION_TYPES, QUICK_CORPUS, render_markdown, render_table, run_eval, uncaught

NEW_TYPES = ("score_order_reversed", "raw_side_label", "free_number")


@cache
def _report():
    return run_eval(QUICK_CORPUS)


def _row(name):
    return next(r for r in _report().results if r.spec.name == name)


def test_every_injection_type_is_measured():
    assert [r.spec.name for r in _report().results] == [t.name for t in INJECTION_TYPES]
    for r in _report().results:
        assert r.v3.applicable > 0
        assert r.v2.applicable > 0 or r.spec.v2 is None


def test_all_drafts_slotify_and_control_has_no_false_alarms():
    report = _report()
    assert report.slotified == report.samples
    control = _row("control")
    assert control.v2.caught == control.v3.caught == 0


def test_new_types_are_caught_by_slots_but_not_free_text():
    for name in NEW_TYPES:
        row = _row(name)
        assert row.v3.rate == 1.0, name
        assert row.v2.rate < row.v3.rate, name


def test_claim_tampering_caught_in_both():
    row = _row("number_text_and_claim")
    assert row.v2.rate > 0.9 and row.v3.rate > 0.9


def test_known_gaps_are_reported():
    v2 = {r.spec.name for r in uncaught(_report(), "v2")}
    v3 = {r.spec.name for r in uncaught(_report(), "v3")}
    assert {"unsupported_sentence_qualitative", "sentence_start_fabricated"} <= v2 & v3
    assert "wrong_slot_binding" in v3 and "control" not in v2 | v3


def test_report_is_deterministic_and_complete():
    first = render_markdown(_report())
    assert render_markdown(run_eval(QUICK_CORPUS)) == first
    table = render_table(_report())
    for spec in INJECTION_TYPES:
        assert f"`{spec.name}`" in table
    assert "| v2 yakalama |" in table.splitlines()[0] and "v3 yakalama" in table
    assert "## Yakalanmayan türler: foundry-v2" in first and "## Yakalanmayan türler: foundry-v3" in first
