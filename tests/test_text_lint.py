from dataclasses import replace

import pytest

from app.analytics import detect_moments
from app.explain import DEFAULT_EXPLAIN_CONFIG, Claim, MatchTime, Subject
from app.explain.narrator import TemplateNarrator
from app.explain.text_lint import Roster, lint_text
from app.generator import generate_match
from app.generator.freeze import DEMO_DIR, demo_filename
from app.generator.models import read_jsonl

EVENTS = read_jsonl(DEMO_DIR / demo_filename("red_card_swing", 42))
ROSTER = Roster.from_events(EVENTS)
TEAMS = EVENTS[0].data["teams"]
HOME, AWAY = TEAMS["home"]["name"], TEAMS["away"]["name"]
GOAL = next(m for m in detect_moments(EVENTS) if m.type == "goal")
DRAFT = TemplateNarrator(EVENTS).narrate(GOAL, "neutral", "en")


def _claim(kind="count", team="home", player=None, value=1, start=(1, 22, 0), end=(1, 22, 0)):
    return Claim(kind, Subject(team, player), "goals", "eq", value, MatchTime(*start), MatchTime(*end), ())


def _codes(result):
    return [(i.code, i.fragment) for i in result.issues]


# --- her şey desteklenmiş metin ----------------------------------------------------


def test_template_draft_is_fully_supported():
    result = lint_text(DRAFT.text, DRAFT.claims, ROSTER)
    assert result.ok, _codes(result)


@pytest.mark.parametrize("seed,scenario", [(42, "late_comeback"), (7, "dominant_loss"), (100, None)])
@pytest.mark.parametrize("lang", ["en"])
def test_all_template_drafts_pass(seed, scenario, lang):
    events = generate_match(seed, scenario)
    narrator, roster = TemplateNarrator(events), Roster.from_events(events)
    for m in detect_moments(events):
        d = narrator.narrate(m, "neutral", lang)
        result = lint_text(d.text, d.claims, roster)
        assert result.ok, (m.type, d.text, _codes(result))


# --- iddiasız sayı ------------------------------------------------------------------


def test_number_without_claim_is_rejected():
    text = f"{DRAFT.text} {HOME} have 7 corners."
    result = lint_text(text, DRAFT.claims, ROSTER)
    assert _codes(result) == [("unsupported_number", "7")]
    issue = result.issues[0]
    assert text[issue.start : issue.end] == "7" and issue.kind == "integer"


def test_pressure_window_phrase_is_not_a_claim_number():
    pressure = next(m for m in detect_moments(EVENTS) if m.type == "pressure_shift")
    for lang, phrase in (("en", "over the last 10 minutes of play"),):
        d = TemplateNarrator(EVENTS).narrate(pressure, "neutral", lang)
        assert phrase in d.text
        assert lint_text(d.text, d.claims, ROSTER, language=lang).ok
    # Pencere ifadesi dışında yazılan aynı sayı hâlâ iddiasız.
    text = f"{d.text} {HOME} have pressed for 10 minutes."
    assert ("unsupported_number", "10") in _codes(lint_text(text, d.claims, ROSTER, language="en"))


# --- iddiasız isim -------------------------------------------------------------------


def test_known_name_without_claim_is_rejected():
    scorer = GOAL.detail["player"]
    bystander = next(p for p in TEAMS["away"]["lineup"] if p != scorer)
    result = lint_text(f"{DRAFT.text} {bystander} was booked.", DRAFT.claims, ROSTER)
    assert _codes(result) == [("unsupported_name", bystander)]


def test_team_without_claim_is_rejected():
    claims = [_claim(team="home", player=GOAL.detail["player"])]
    result = lint_text(f"22' — {GOAL.detail['player']} scores against {AWAY}.", claims, ROSTER)
    assert _codes(result) == [("unsupported_name", AWAY)]


# --- uydurma isim ----------------------------------------------------------------------


def test_fabricated_name_is_rejected():
    result = lint_text(f"{DRAFT.text} Arlo Quintana was everywhere.", DRAFT.claims, ROSTER)
    assert _codes(result) == [("unknown_name", "Arlo Quintana")]


def test_fabricated_single_word_mid_sentence_is_rejected():
    result = lint_text(f"{DRAFT.text} The ball reached Zorvak.", DRAFT.claims, ROSTER)
    assert _codes(result) == [("unknown_name", "Zorvak")]


def test_sentence_start_capitalized_word_is_fine():
    assert lint_text(f"{DRAFT.text} What a moment.", DRAFT.claims, ROSTER).ok


# --- takma adlar ve sayı biçimleri ------------------------------------------------------


def test_surname_and_city_aliases_are_recognised():
    player = GOAL.detail["player"]
    surname, city = player.split()[-1], HOME.rsplit(" ", 1)[0]
    claims = [_claim(team="home", player=player)]
    assert lint_text(f"22' — {player} scores for {city}.", claims, ROSTER).ok
    # Yalnızca soyad reddedilir (aynı soyad iki takımda olabilir); v2 davranışı bayrakla.
    assert _codes(lint_text(f"22' — {surname} scores for {city}.", claims, ROSTER)) == [("bare_surname", surname)]
    v2 = replace(DEFAULT_EXPLAIN_CONFIG, lint_bare_surname=False)
    assert lint_text(f"22' — {surname} scores for {city}.", claims, ROSTER, v2).ok
    other = next(p for p in TEAMS["away"]["lineup"] if p.split()[-1] != surname)
    result = lint_text(f"22' — {other.split()[-1]} scores.", claims, ROSTER, v2)
    assert _codes(result) == [("unsupported_name", other.split()[-1])]


def test_bare_surname_shared_across_teams_is_rejected():
    # Her demo maçında iki takımda ortak soyad var; yalnızca soyad hangi oyuncu olduğunu belirlemez.
    home = {p.split()[-1]: p for p in [*TEAMS["home"]["lineup"], *TEAMS["home"]["bench"]]}
    away = {p.split()[-1]: p for p in [*TEAMS["away"]["lineup"], *TEAMS["away"]["bench"]]}
    surname = sorted(home.keys() & away.keys())[0]
    claims = [_claim(team="home", player=home[surname])]
    assert ("bare_surname", surname) in _codes(lint_text(f"{surname} was everywhere.", claims, ROSTER))
    assert lint_text(f"{home[surname]} was everywhere.", claims, ROSTER).ok


def test_minute_formats():
    claims = [_claim(start=(1, 45, 0), end=(1, 45, 30))]
    assert lint_text("45+1' — something happened.", claims, ROSTER).ok
    assert _codes(lint_text("45+2' — something happened.", claims, ROSTER)) == [
        ("unsupported_number", "45+2'")
    ]


def test_percent_and_decimal():
    ratio = Claim("ratio", Subject("home"), "possession", "approx", 0.58,
                  MatchTime(1, 0, 0), MatchTime(1, 30, 0), ())
    state = Claim("state", Subject("home"), "pressure_balance", "approx", 0.83,
                  MatchTime(1, 0, 0), MatchTime(1, 30, 0), ())
    assert lint_text("58% possession, balance +0.83.", [ratio, state], ROSTER).ok
    result = lint_text("60% possession, balance +0.90.", [ratio, state], ROSTER)
    assert _codes(result) == [("unsupported_number", "60%"), ("unsupported_number", "+0.90")]


# --- yazıyla sayılar (EN, 0-20) -------------------------------------------------------


def _goals(value, team="home"):
    return [_claim(team=team, value=value)]


@pytest.mark.parametrize(
    "text,lang",
    [
        ("22' — two goals for the home side.", "en"),
        ("22' — Two goals in total.", "en"),
    ],
)
def test_supported_number_words(text, lang):
    assert lint_text(text, _goals(2), ROSTER, language=lang).ok


@pytest.mark.parametrize(
    "text,lang,fragment",
    [
        ("22' — three goals for the home side.", "en", "three"),
        ("22' — one goal for the home side.", "en", "one"),
    ],
)
def test_unsupported_number_words(text, lang, fragment):
    result = lint_text(text, _goals(2), ROSTER, language=lang)
    assert [(i.code, i.fragment, i.kind) for i in result.issues] == [("unsupported_number", fragment, "word")]


@pytest.mark.parametrize(
    "text,lang",
    [
        ("22' — It was one of those days.", "en"),
        ("22' — The goal came on the break.", "en"),  # EN "on" sayı değil
    ],
)
def test_ambiguous_words_without_count_noun_are_not_numbers(text, lang):
    assert lint_text(text, _goals(2), ROSTER, language=lang).ok


def test_unspecified_language_lints_as_english():
    assert lint_text("22' — The goal came on the break.", _goals(2), ROSTER).ok
    assert not lint_text("22' — three goals.", _goals(2), ROSTER).ok


def test_number_words_can_be_disabled():
    from dataclasses import replace as dc_replace

    from app.explain import DEFAULT_EXPLAIN_CONFIG

    off = dc_replace(DEFAULT_EXPLAIN_CONFIG, lint_number_words=False)
    assert lint_text("22' — three goals.", _goals(2), ROSTER, off, language="en").ok


@pytest.mark.parametrize("lang", ["en"])
def test_template_drafts_pass_with_language(lang):
    narrator = TemplateNarrator(EVENTS)
    for m in detect_moments(EVENTS):
        d = narrator.narrate(m, "neutral", lang)
        result = lint_text(d.text, d.claims, ROSTER, language=lang)
        assert result.ok, (m.type, d.text, _codes(result))
