"""eval/verifier_smoke.py: the draft selection and the summary (no model)."""

from eval.verifier_smoke import CLASSES, select, summary


def test_selection_gives_guard_accepted_drafts_of_distinct_moments_per_class_and_clean_ones():
    drafts, notes = select(2)
    assert set(drafts) == {*CLASSES, "clean"} and notes == []
    for kind, items in drafts.items():
        assert len(items) == 2 and all(d.guard.ok and d.guard.text for d in items)
        assert len({(d.sample.events[0].match_id, d.sample.moment.id) for d in items}) == 2
    assert all(d.tag is None for d in drafts["clean"]) and all(d.tag for d in drafts["role_reversed"])


def test_summary_counts_rejections_code_matches_and_false_alarms():
    rows = [
        {"kind": "role_reversed", "verdict": "reject", "codes": ["role_reversed"]},
        {"kind": "role_reversed", "verdict": "reject", "codes": ["other_semantic"]},
        {"kind": "role_reversed", "verdict": "pass", "codes": []},
        {"kind": "clean", "verdict": "reject", "codes": ["unsupported_statement"]},
        {"kind": "clean", "verdict": "pass", "codes": []},
        {"kind": "clean", "verdict": "error", "codes": []},
    ]
    text = "\n".join(summary(rows))
    assert "role_reversed         2/3" in text and "false alarms on clean drafts: 1/3" in text
