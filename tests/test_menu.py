"""Claim menu (foundry-v5): verified candidate claims, clauses and menu rules."""

from functools import cache

import pytest

from app.analytics import detect_moments
from app.explain.claims import VerificationResult, measure, verify_claim
from app.explain.labels import metric_label
from app.explain.menu import build_menu, preview
from app.explain.pipeline import check_menu_draft
from app.explain.slots import SlotContext, render
from app.explain.template_narrator import narrate as template_narrate
from app.explain.text_lint import Roster, lint_text
from app.generator import generate_match
from app.generator.freeze import demo_paths
from app.generator.models import read_jsonl
from eval.inject import FULL_CORPUS
from tests.explain_helpers import moment_case

LANGS = ("en",)


@cache
def _matches():
    """The 3 demo matches (frozen fixtures) + the 28 matches of the injection corpus."""
    out = [read_jsonl(path) for _, _, path in demo_paths()]
    out += [generate_match(seed, scenario) for seed, scenario in FULL_CORPUS]
    return out


@cache
def _menus():
    return [(events, m, build_menu(m, events)) for events in _matches() for m in detect_moments(events)]


def _key(c):
    return (c.metric, c.kind, c.subject, c.start, c.end)


# --- menu: verified and complete ------------------------------------------------------------


def test_corpus_covers_demo_and_injection_matches():
    assert len(_matches()) == 3 + 28 == 31
    assert len(_menus()) > 250


def test_every_menu_claim_verifies():
    for events, m, menu in _menus():
        for mc in menu.claims:
            result = verify_claim(mc.claim, events)
            assert result.ok, (m.id, mc.id, result.reason)


def test_count_evidence_is_complete_including_counts_from_kickoff():
    from_kickoff = 0
    for events, m, menu in _menus():
        for mc in menu.claims:
            c = mc.claim
            if c.kind != "count":
                continue
            counted = measure(c.metric, c.subject, c.start, c.end, events).counted
            assert {int(r.rsplit("#", 1)[1]) for r in c.event_ids} == set(counted), (m.id, mc.id)
            from_kickoff += mc.window == "since_kickoff" and len(counted) > 1
    assert from_kickoff > 0  # the "since kickoff" counts v4.1 missed are on the menu with full evidence


def test_menu_keeps_every_template_claim_type():
    for events, m, menu in _menus():
        keys = {_key(c.claim) for c in menu.claims}
        for s in template_narrate(m, events).sentences:
            for c in s.claims:
                assert _key(c) in keys, (m.id, c.describe())


def test_field_tilt_is_not_on_the_menu():
    assert not any(mc.claim.metric == "field_tilt" for _, _, menu in _menus() for mc in menu.claims)


def test_primary_claims_for_dominance_pressure_and_score_change():
    for _, m, menu in _menus():
        if m.type == "dominance_without_reward":
            assert menu.primary == (frozenset({"possession"}), frozenset({"shots_for", "shots_against"}))
        elif m.type == "pressure_shift":
            assert menu.primary == (frozenset({"pressure"}),)
        elif m.type == "goal" and "score_change" in m.detail:
            assert menu.primary == (frozenset({"score_home", "score_away"}),)
        else:
            assert menu.primary == ()


def test_goal_with_score_change_carries_the_sub_label_clause():
    seen = set()
    for _, m, menu in _menus():
        if m.type != "goal":
            continue
        change = m.detail.get("score_change")
        clauses = menu.clause_by_id
        if change is None:
            assert not {"opener", "equalizer", "go_ahead", "margin"} & (set(clauses) | set(menu.by_id)), m.id
            continue
        kind = change["kind"]
        seen.add(kind)
        # The sub-label clause rests on the margin, never on the score: it cannot stand in for the score.
        assert "margin" in clauses[kind].claim_ids and not {"score_home", "score_away"} & set(clauses[kind].claim_ids)
        assert "score" in clauses and ("deficit" in clauses[kind].claim_ids) == bool(change.get("from_behind"))
    assert seen == {"opener", "equalizer", "go_ahead"}


@pytest.mark.parametrize("lang", LANGS)
def test_every_claim_has_a_clause_that_renders_and_passes_text_lint(lang):
    for events, m, menu in _menus():
        covered = {cid for c in menu.clauses for cid in c.claim_ids}
        assert {c.id for c in menu.claims} <= covered, m.id
        ctx = SlotContext.from_moment(m, events, lang)
        roster = Roster.from_events(events)
        texts = preview(menu, ctx)
        by_id = menu.by_id
        for clause in menu.clauses:
            text = texts[clause.id]
            assert "{" not in text and text, (m.id, clause.id, text)
            claims = [by_id[i] for i in clause.claim_ids]
            result = lint_text(text, claims, roster, language=lang)
            assert result.ok, (m.id, clause.id, text, [(i.code, i.fragment) for i in result.issues])


# --- label grammar ------------------------------------------------------------------------


@pytest.mark.parametrize("metric,one,many", [
    ("shots", "shot", "shots"),
    ("goals", "goal", "goals"),
    ("red_cards", "red card", "red cards"),
    ("players_on_pitch", "player on the pitch", "players on the pitch"),
    ("penalties_saved", "penalty taken and saved", "penalties taken and saved"),
    ("penalties_scored", "penalty scored", "penalties scored"),
])
def test_english_count_labels_agree_with_value(metric, one, many):
    assert metric_label(metric, "en", 1) == one
    assert metric_label(metric, "en", 2) == metric_label(metric, "en", 0) == many
    assert metric_label(metric, "en") == many


def test_penalty_labels_read_from_taker():
    assert "saved" in metric_label("penalties_saved", "en") and "taken" in metric_label("penalties_saved", "en")


def test_label_agrees_only_right_after_its_value():
    events, m = moment_case("pressure_shift")
    menu = build_menu(m, events)
    ctx = SlotContext.from_moment(m, events, "en")
    ids = tuple(c.id for c in menu.claims)
    claims = tuple(c.claim for c in menu.claims)
    one = tuple(VerificationResult(True, "ok", 1.0) for _ in claims)
    text = render("{value:shots_for} {label:shots_for}; a lead in {label:shots_for}.", claims, ids, one, ctx)
    assert text == "1 shot; a lead in shots."


# --- menu draft rules -------------------------------------------------------------------


def _check(mtype, template, lang="en"):
    events, m = moment_case(mtype)
    menu = build_menu(m, events)
    ctx = SlotContext.from_moment(m, events, lang)
    items, issues, results, claims, ids = check_menu_draft(template, menu, ctx)
    return [(i.code, i.fragment) for i in items], results, ids, (events, m, menu)


def test_clause_template_is_accepted_and_binds_menu_claims():
    codes, results, ids, _ = _check("goal", "{clause:goal}, and {clause:score}.")
    assert codes == [] and set(ids) == {"goal", "score_home", "score_away"}
    assert all(r.ok for r in results)


def test_unknown_menu_id_is_rejected():
    codes, *_ = _check("goal", "{clause:goal} with {value:c1}, {clause:nope}.")
    assert ("unknown_claim_id", "{value:c1}") in codes and ("unknown_claim_id", "{clause:nope}") in codes


def test_sentence_without_menu_fact_is_rejected():
    codes, *_ = _check("goal", "{clause:goal}, and {clause:score}. {home} looked lively.")
    assert [c for c, _ in codes] == ["sentence_without_claim"]


def test_primary_claim_is_required_for_dominance_and_pressure():
    codes, *_ = _check("dominance_without_reward", "{clause:score}.")
    assert {f for c, f in codes if c == "missing_primary_claim"} == {"possession", "shots_against,shots_for"}
    assert _check("dominance_without_reward", "{clause:dominance}, yet {clause:score}.")[0] == []
    assert ("missing_primary_claim", "pressure") in _check("pressure_shift", "{clause:shots}.")[0]
    assert _check("pressure_shift", "{clause:pressure}, and {clause:shots}.")[0] == []


def test_score_is_required_for_a_goal_that_changed_the_match_state():
    missing = ("missing_primary_claim", "score_away,score_home")
    assert missing in _check("goal_from_behind", "{clause:goal}, and {clause:possession}.")[0]
    assert missing in _check("goal_from_behind", "{clause:goal}, and {clause:go_ahead}.")[0]  # sub-label is not the score
    for template in ("{clause:go_ahead}, and {clause:score}.", "{clause:goal}, making it {score}.",
                     "{clause:goal}: {score_named}."):
        assert _check("goal_from_behind", template)[0] == [], template


def test_same_team_more_than_twice_in_one_sentence_is_rejected():
    # goal: a home goal; {clause:goal}, {clause:possession} and {score_named} each name the home team.
    codes, *_ = _check("goal", "{clause:goal}, {clause:possession}, and {clause:score}.")
    assert ("team_repeat", "{home}") in codes
    assert _check("goal", "{clause:goal}, and {clause:score}. {clause:possession}.")[0] == []
    assert ("team_repeat", "{home}") in _check("goal", "{home} lead, {clause:goal}, and {clause:score}.")[0]
    assert _check("goal", "{home} lead, {clause:goal}, and {score}.")[0] == []


def test_same_minute_twice_in_one_sentence_is_rejected():
    events, m = moment_case("goal_from_behind")
    ref = f"{events[0].match_id}#{m.event_ids[-1]}"
    codes, *_ = _check("goal_from_behind", "{event:%s} at {minute:goal}, and {clause:score}." % ref)
    assert "minute_repeat" in [c for c, _ in codes]
    codes, *_ = _check("dominance_without_reward", "{clause:possession}, and {clause:shots}.")
    assert "minute_repeat" in [c for c, _ in codes]  # two clauses write the same window start
    codes, *_ = _check("goal_from_behind", "{event:%s}, and {clause:score}. {clause:go_ahead} at {minute:goal}." % ref)
    assert "minute_repeat" not in [c for c, _ in codes]


def test_menu_drafts_never_produce_evidence_mismatch():
    for template in ("{clause:goal}, and {clause:score}.", "{value:team_goals} {label:team_goals}.",
                     "{clause:possession} with {value:nope}."):
        _, results, _, _ = _check("goal", template)
        assert all(r.reason != "evidence_mismatch" for r in results)


def test_known_gap_judgement_inside_a_grounded_sentence_passes():
    """Documented gap (EVAL.md "Target for the Verifier agent"): a qualitative judgement passes inside a grounded sentence."""
    codes, *_ = _check("goal", "{clause:score}, and {home} were the better side.")
    assert codes == []


def test_rendered_menu_drafts_pass_text_lint_end_to_end():
    from app.explain.llm_narrator import FoundryNarrator
    from app.explain.pipeline import run_match
    from tests.test_llm_narrator import FakeChatClient, responder

    for _, _, path in demo_paths():
        events = read_jsonl(path)
        roster = Roster.from_events(events)
        for m, r in run_match(events, FoundryNarrator(events, FakeChatClient(responder(events)))):
            assert (r.source, r.attempts) == ("llm", 1), m.id
            assert lint_text(r.text, r.claims, roster, language="en").ok, (m.id, r.text)
