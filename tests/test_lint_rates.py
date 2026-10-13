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


def test_team_repeat_counts_team_names_per_sentence():
    from eval.lint_rates import llm_published, team_repeats

    texts = {t.raw: t for t in llm_published("foundry-v4.1")}
    hit = next(raw for raw in texts if raw.startswith("Orvik Belmaro was sent off at 38'. Possession for"))
    assert team_repeats(hit, texts[hit].roster, 2) == ["{home}"]
    assert team_repeats(hit, texts[hit].roster, 3) == []
    # The same names split over two sentences do not fire.
    first, rest = hit.split(". ", 1)
    assert team_repeats(rest.replace(", red cards", ". Red cards"), texts[hit].roster, 2) == []


def test_team_repeat_can_leave_out_the_score_line():
    from eval.lint_rates import llm_published, team_repeats

    # foundry-v5.2 (slot_team_repeat_exempt="score"): the score line's names do not count.
    texts = {t.raw: t for t in llm_published("foundry-v5.1")}
    raw = next(r for r in texts if r.startswith("Murek Ymberto scored at 84'"))
    roster = texts[raw].roster
    tripled = raw.replace("Morvane Athletic went ahead", "Morvane Athletic lead, Morvane Athletic went ahead")
    assert team_repeats(tripled, roster, 2) == ["{away}"]
    first = "Morvane Athletic lead, and the score is Brannoch FC 1–2 Morvane Athletic and Morvane Athletic push."
    assert team_repeats(first, roster, 2) == ["{away}"]
    assert team_repeats(first, roster, 2, exclude_score=True) == []


def test_menu_drafts_replay_archived_templates_against_todays_menu():
    from eval.lint_rates import menu_drafts

    v5 = menu_drafts("foundry-v5")  # legacy ids: score_change cards are skipped, goal cards keep their state change
    assert v5 and all(d.moment.type != "score_change" for d in v5)
    assert any(d.state_change for d in v5 if d.moment.type == "goal")
    v51 = menu_drafts("foundry-v5.1")
    assert len(v51) == 15 and {d.run for d in v51} == {1}
