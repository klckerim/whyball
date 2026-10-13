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
            injector = r.spec.injector(variant)
            assert getattr(r, variant).applicable > 0 or injector is None, (r.spec.name, variant)


def test_all_drafts_slotify_and_control_has_no_false_alarms():
    report = _report()
    assert report.slotified == report.slotified_v4 == report.samples
    control = _row("control")
    assert control.v2.caught == control.v3.caught == control.v4.caught == control.v41.caught == 0


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
        assert 0.0 < row.v4.rate < 1.0, name  # phrases deliberately left off the list slip through
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
    assert "| v2 caught |" in table.splitlines()[0] and "v4.1 caught" in table
    verifier = first.index("## Target for the Verifier agent")
    for title in ("foundry-v2", "foundry-v3", "foundry-v4 (", "foundry-v4.1"):
        assert first.index(f"### Uncaught types: {title}") > verifier
    assert "\n## Uncaught types" not in first
    for section in ("## v4 / v4.1 lint rules and false alarms", "### False alarms from the foundry-v4.1 changes",
                    "## Qualitative overstatement ban list",
                    "## Template window audit", "## Human labels: foundry-v3"):
        assert section in first


def test_v41_closes_player_repeat_without_regressions():
    row = _row("player_repeat")
    assert row.v2.rate == row.v3.rate == row.v4.rate == 0.0
    assert row.v41.rate == 1.0 and row.v41.applicable > 0
    for r in _report().results:
        if r.v4.applicable:
            assert r.v41.applicable == r.v4.applicable and r.v41.caught >= r.v4.caught, r.spec.name


def test_v41_false_alarms_are_measured_on_clean_sets():
    rows = {name: (flagged, total, hits) for name, flagged, total, hits in _report().v41_false_alarms}
    flagged, total, hits = rows["Template drafts (raw text)"]
    assert total > 0 and set(hits) <= {"They"}  # only "They had been … down"
    assert rows["v4 slot base (clean)"][0] == 0


def test_v5_menu_column():
    report = _report()
    assert report.slotified_v5 == report.samples
    assert _row("control").v5.caught == 0
    assert _row("unknown_menu_id").v5.rate == 1.0
    assert _row("number_text_and_claim").v5.applicable == 0  # the model writes no claims
    assert _row("wrong_slot_binding").v5.applicable > 0 and _row("wrong_slot_binding").v5.rate == 0.0
    for name in ("unsupported_sentence_qualitative", "qualitative_overstatement"):
        assert _row(name).v5.rate == 1.0, name  # separate sentence: sentence_without_claim
    ewc = _row("event_wrong_claim")
    assert ewc.v5.rate < ewc.v41.rate  # menu evidence is broad: the wrong event is usually evidence of some claim


def test_team_repeat_rule_has_no_false_alarms_on_clean_drafts():
    report = _report()
    assert report.team_repeat_disagreements == []  # template rule == count on the rendered text
    rows = {name: (flagged, total) for name, flagged, total, _, _ in report.team_repeat}
    assert rows["v5 menu base (clean)"] == (0, report.slotified_v5) and report.slotified_v5 == report.samples
    assert rows["Template drafts (fallback text)"][0] == 0
