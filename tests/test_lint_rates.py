from app.explain.config import DEFAULT_EXPLAIN_CONFIG
from eval.inject import FULL_CORPUS
from eval.lint_rates import derive_frozen, human_review_counts, start_words


def test_frozen_sentence_starts_match_derivation():
    derived = derive_frozen(FULL_CORPUS)
    assert DEFAULT_EXPLAIN_CONFIG.sentence_start_allowed_en == derived["en"]


def test_human_review_counts_v3():
    counts = human_review_counts()
    assert counts["total"] == 22
    totals = {label: sum(c[label] for c in counts["by_source"].values()) for label in ("correct", "wrong_fact", "misleading", "dull")}
    assert totals == {"correct": 16, "wrong_fact": 1, "misleading": 5, "dull": 8}
    assert counts["ids"]["wrong_fact"] == ["m-7-dominant_loss-M009"]


def test_pronouns_never_enter_the_allowed_starts():
    from eval.lint_rates import PRONOUNS, Text, derive_sentence_starts

    texts = [Text("t", "en", "m", "goal", "They lead. {home} lead.")]
    assert derive_sentence_starts(texts) == {"en": ()}
    assert "they" in PRONOUNS["en"]


def test_v41_rules_fire_on_foundry_v4_findings():
    from eval.lint_rates import fired, llm_v4_outputs

    texts = {t.moment_id: t for t in llm_v4_outputs()}
    assert fired(texts["m-42-red_card_swing-M012"], "event_type") == ["{event:m-42-red_card_swing#521}"]
    assert fired(texts["m-100-M010"], "player_repeat") == ["{player:h03}"]
    assert fired(texts["m-100-M009"], "article_team") == ["The {home}"]
    assert "They" in fired(texts["m-42-red_card_swing-M007"], "sentence_start")
