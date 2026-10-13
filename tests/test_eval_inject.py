from functools import cache

from eval.inject import INJECTION_TYPES, QUICK_CORPUS, VARIANTS, render_markdown, render_table, run_eval, uncaught

SLOT_TYPES = ("score_order_reversed", "raw_side_label", "free_number")
V4_TYPES = ("sentence_start_fabricated", "sentence_start_fabricated_name", "number_words")


@cache
def _report():
    return run_eval(QUICK_CORPUS)


def _row(name):
    return next(r for r in _report().results if r.spec.name == name)


def test_every_injection_type_is_measured():
    assert [r.spec.name for r in _report().results] == [t.name for t in INJECTION_TYPES]
    for r in _report().results:
        for variant in VARIANTS:
            injector = getattr(r.spec, variant)
            assert getattr(r, variant).applicable > 0 or injector is None, (r.spec.name, variant)


def test_all_drafts_slotify_and_control_has_no_false_alarms():
    report = _report()
    assert report.slotified == report.slotified_v4 == report.samples
    control = _row("control")
    assert control.v2.caught == control.v3.caught == control.v4.caught == 0


def test_slot_types_are_caught_by_slots_but_not_free_text():
    for name in SLOT_TYPES:
        row = _row(name)
        assert row.v3.rate == row.v4.rate == 1.0, name
        assert row.v2.rate < row.v3.rate, name


def test_v4_rules_close_v3_gaps():
    for name in V4_TYPES:
        row = _row(name)
        assert row.v4.rate == 1.0 and row.v3.rate < 1.0, name


def test_role_reversal_and_overstatement_improve_but_misses_are_reported():
    for name in ("role_reversed", "qualitative_overstatement"):
        row = _row(name)
        assert row.v2.rate == row.v3.rate == 0.0, name
        assert 0.0 < row.v4.rate < 1.0, name  # bilerek listede olmayan ifadeler kaçar
        assert row.v4.missed_tags, name


def test_claim_tampering_caught_everywhere():
    row = _row("number_text_and_claim")
    assert min(row.v2.rate, row.v3.rate, row.v4.rate) > 0.9


def test_known_gaps_are_reported():
    gaps = {v: {r.spec.name for r in uncaught(_report(), v)} for v in VARIANTS}
    assert {"unsupported_sentence_qualitative", "sentence_start_fabricated"} <= gaps["v2"] & gaps["v3"]
    assert {"wrong_slot_binding", "unsupported_sentence_qualitative"} <= gaps["v4"]
    assert "control" not in gaps["v2"] | gaps["v3"] | gaps["v4"]


def test_report_is_deterministic_and_complete():
    first = render_markdown(_report())
    assert render_markdown(run_eval(QUICK_CORPUS)) == first
    table = render_table(_report())
    for spec in INJECTION_TYPES:
        assert f"`{spec.name}`" in table
    assert "| v2 yakalama |" in table.splitlines()[0] and "v4 yakalama" in table
    for title in ("foundry-v2", "foundry-v3", "foundry-v4"):
        assert f"## Yakalanmayan türler: {title}" in first
    for section in ("## v4 lint kuralları ve yanlış alarm", "## Nitel abartı yasak listesi",
                    "## Şablon pencere denetimi", "## İnsan etiketleri: foundry-v3"):
        assert section in first
