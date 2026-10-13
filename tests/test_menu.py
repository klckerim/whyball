"""Claim menüsü (foundry-v5): doğrulanmış aday iddialar, yan cümleler ve menü kuralları."""

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

LANGS = ("en", "tr")


@cache
def _matches():
    """3 demo maç (dondurulmuş fixture) + enjeksiyon derleminin 28 maçı."""
    out = [read_jsonl(path) for _, _, path in demo_paths()]
    out += [generate_match(seed, scenario) for seed, scenario in FULL_CORPUS]
    return out


@cache
def _menus():
    return [(events, m, build_menu(m, events)) for events in _matches() for m in detect_moments(events)]


def _key(c):
    return (c.metric, c.kind, c.subject, c.start, c.end)


# --- menü: doğrulanmış ve eksiksiz ------------------------------------------------------------


def test_corpus_covers_demo_and_injection_matches():
    assert len(_matches()) == 3 + 28 == 31
    assert len(_menus()) > 300


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
    assert from_kickoff > 0  # v4.1'in kaçırdığı "maç başından" sayımlar menüde tam kanıtla


def test_menu_keeps_every_template_claim_type():
    for events, m, menu in _menus():
        keys = {_key(c.claim) for c in menu.claims}
        for s in template_narrate(m, events).sentences:
            for c in s.claims:
                assert _key(c) in keys, (m.id, c.describe())


def test_field_tilt_is_not_on_the_menu():
    assert not any(mc.claim.metric == "field_tilt" for _, _, menu in _menus() for mc in menu.claims)


def test_primary_claims_for_dominance_and_pressure():
    for _, m, menu in _menus():
        if m.type == "dominance_without_reward":
            assert menu.primary == (frozenset({"possession"}), frozenset({"shots_for", "shots_against"}))
        elif m.type == "pressure_shift":
            assert menu.primary == (frozenset({"pressure"}),)
        else:
            assert menu.primary == ()


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


# --- etiket dilbilgisi ------------------------------------------------------------------------


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


def test_turkish_labels_stay_singular_after_numbers_and_penalties_read_from_taker():
    assert metric_label("shots", "tr", 1) == metric_label("shots", "tr", 5) == "şut"
    assert metric_label("penalties_saved", "tr") == "kullanılıp kurtarılan penaltı"
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


# --- menü taslağı kuralları -------------------------------------------------------------------


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
    codes, *_ = _check("goal", "{clause:goal}. {home} looked lively.")
    assert [c for c, _ in codes] == ["sentence_without_claim"]


def test_primary_claim_is_required_for_dominance_and_pressure():
    codes, *_ = _check("dominance_without_reward", "{clause:score}.")
    assert {f for c, f in codes if c == "missing_primary_claim"} == {"possession", "shots_against,shots_for"}
    assert _check("dominance_without_reward", "{clause:dominance}, yet {clause:score}.")[0] == []
    assert ("missing_primary_claim", "pressure") in _check("pressure_shift", "{clause:shots}.")[0]
    assert _check("pressure_shift", "{clause:pressure}, and {clause:shots}.")[0] == []


def test_same_minute_twice_in_one_sentence_is_rejected():
    events, m = moment_case("score_change")
    ref = f"{events[0].match_id}#{m.event_ids[-1]}"
    codes, *_ = _check("score_change", "{event:%s}, as {clause:goals}." % ref)
    assert "minute_repeat" in [c for c, _ in codes]
    codes, *_ = _check("dominance_without_reward", "{clause:possession}, and {clause:shots}.")
    assert "minute_repeat" in [c for c, _ in codes]  # iki yan cümle aynı pencere başını yazar
    assert "minute_repeat" not in [c for c, _ in _check("score_change", "{event:%s}. {clause:goals}." % ref)[0]]


def test_menu_drafts_never_produce_evidence_mismatch():
    for template in ("{clause:goal}, and {clause:score}.", "{value:team_goals} {label:team_goals}.",
                     "{clause:possession} with {value:nope}."):
        _, results, _, _ = _check("goal", template)
        assert all(r.reason != "evidence_mismatch" for r in results)


def test_known_gap_judgement_inside_a_grounded_sentence_passes():
    """Belgelenen açık (EVAL.md "Verifier ajanının hedefi"): nitel yargı dayanaklı cümlenin içinde geçer."""
    codes, *_ = _check("goal", "{clause:possession}, and {home} were the better side.")
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
