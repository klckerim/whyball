from app.explain.config import DEFAULT_EXPLAIN_CONFIG
from eval.inject import FULL_CORPUS
from eval.lint_rates import derive_frozen, human_review_counts, start_words


def test_frozen_sentence_starts_match_derivation():
    derived = derive_frozen(FULL_CORPUS)
    assert DEFAULT_EXPLAIN_CONFIG.sentence_start_allowed_en == derived["en"]
    assert DEFAULT_EXPLAIN_CONFIG.sentence_start_allowed_tr == derived["tr"]


def test_start_words_skip_placeholders_and_turkish_ordinals():
    assert [w for *_, w in start_words("{home} lead. The rest. {start:c1}. dakikadan bu yana.")] == ["The"]


def test_human_review_counts_v3():
    counts = human_review_counts()
    assert counts["total"] == 22
    totals = {label: sum(c[label] for c in counts["by_source"].values()) for label in ("correct", "wrong_fact", "misleading", "dull")}
    assert totals == {"correct": 16, "wrong_fact": 1, "misleading": 5, "dull": 8}
    assert counts["ids"]["wrong_fact"] == ["m-7-dominant_loss-M009"]
