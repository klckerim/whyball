import pytest

from app.explain.claims import KICKOFF, Claim, MatchTime, Subject, VerificationResult
from app.explain.pipeline import check_slot_draft
from app.explain.slots import (
    SlotContext,
    bind_template,
    format_value,
    lint_template,
    parse_placeholders,
    player_ids,
    render,
)
from tests.explain_helpers import match

EVENTS, MOMENTS = match(7, "dominant_loss")
GOAL = next(m for m in MOMENTS if m.type == "goal")  # 57' deplasman golü, skor 0–1
T = MatchTime(GOAL.period, GOAL.minute, GOAL.second)
REF = f"{EVENTS[0].match_id}#{GOAL.event_ids[-1]}"
TEAMS = EVENTS[0].data["teams"]
HOME, AWAY = TEAMS["home"]["name"], TEAMS["away"]["name"]
SCORER = GOAL.detail["player"]
PID = {name: pid for pid, name in player_ids(EVENTS).items()}[SCORER]
GOAL_CLAIM = Claim("count", Subject("away", SCORER), "goals", "eq", 1, T, T, (REF,))
POSS_CLAIM = Claim("ratio", Subject("home"), "possession", "approx",
                   round(GOAL.metrics["possession"]["home"], 2), KICKOFF, T, (REF,))


def ctx(lang="en"):
    return SlotContext.from_moment(GOAL, EVENTS, lang)


def codes(issues):
    return [(i.code, i.fragment) for i in issues]


# --- ayrıştırma ve bağlama ------------------------------------------------------------------


def test_player_ids_are_deterministic():
    ids = player_ids(EVENTS)
    assert ids["h01"] == TEAMS["home"]["lineup"][0] and ids["a12"] == TEAMS["away"]["bench"][0]
    assert len(ids) == 32


@pytest.mark.parametrize("bad", ["{homes}", "{player}", "{value:}", "{minute:c 1}", "{x:y}", "stray } brace"])
def test_unknown_placeholders(bad):
    _, issues = parse_placeholders(f"Text {bad}.")
    assert issues and all(i.code == "unknown_placeholder" for i in issues)


def test_bind_flags_unbound_and_duplicate_ids():
    bystander = next(pid for pid, name in player_ids(EVENTS).items() if name != SCORER)
    template = f"{{player:h99}} and {{player:{bystander}}} at {{minute:c7}}."
    _, _, issues = bind_template(template, (GOAL_CLAIM, POSS_CLAIM), ("c1", "c1"), ctx())
    found = codes(issues)
    assert ("unbound_placeholder", "{player:h99}") in found  # kadroda yok
    assert ("unbound_placeholder", f"{{player:{bystander}}}") in found  # iddia öznesi değil
    assert ("unbound_placeholder", "{minute:c7}") in found
    assert ("duplicate_claim_id", "c1") in found


def test_score_placeholder_adds_verified_score_claims():
    claims, ids, issues = bind_template("{score}", (GOAL_CLAIM,), ("c1",), ctx())
    assert not issues
    assert ids == ("c1", "score_home", "score_away")
    assert [(c.subject.team, c.value, c.end) for c in claims[1:]] == [("home", 0, T), ("away", 1, T)]


# --- şablon lint -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "template,code,fragment",
    [
        ("{player:%s} scored at 57'." % PID, "raw_number", "57"),
        ("{home} have two shots.", "raw_number", "two"),
        (f"{SCORER} scored.", "raw_entity", SCORER),
        (f"{{player:{PID}}} scored for {AWAY}.", "raw_entity", AWAY),
        ("It came from Arlo Quintana.", "raw_entity", "Arlo Quintana"),
        ("{player:%s} scored for the home side." % PID, "raw_side_label", "home"),
        ("{home} lead on field_tilt.", "raw_metric_name", "field_tilt"),
    ],
)
def test_lint_rejects_raw_values(template, code, fragment):
    assert (code, fragment) in codes(lint_template(template, ctx()).issues)


def test_lint_rejects_turkish_side_labels_and_number_words():
    found = codes(lint_template("Deplasman ekibi üç şut attı.", ctx("tr")).issues)
    assert ("raw_side_label", "Deplasman") in found and ("raw_number", "üç") in found


def test_clean_template_passes_lint():
    template = "{player:%s} scored for {away} at {minute:c1}, making it {score}." % PID
    assert lint_template(template, ctx()).ok


# --- render ----------------------------------------------------------------------------------


def _render(template, claims, ids, lang="en"):
    c = ctx(lang)
    items, _, results, bound, bound_ids = check_slot_draft(template, claims, ids, c)
    assert not items, items
    return render(template, bound, bound_ids, results, c)


def test_away_goal_score_rendered_home_first_from_state():
    template = "{player:%s} scored for {away} at {minute:c1}, making it {score}." % PID
    assert _render(template, (GOAL_CLAIM,), ("c1",)) == (
        f"{SCORER} scored for {AWAY} at 57', making it {HOME} 0–1 {AWAY}."
    )


@pytest.mark.parametrize("lang,expected", [("en", "61%"), ("tr", "%61")])
def test_percent_and_label_rendering(lang, expected):
    text = _render("{home}: {value:c2} {label:c2}.", (GOAL_CLAIM, POSS_CLAIM), ("c1", "c2"), lang)
    label = "possession" if lang == "en" else "topa sahip olma"
    assert text == f"{HOME}: {expected} {label}."


def test_value_uses_verified_actual_not_model_value():
    # İddia 0.61 ≈ gerçek 0.609…; render doğrulanmış gerçek değerden yuvarlar.
    c = ctx()
    claims, ids, _ = bind_template("{value:c2}", (GOAL_CLAIM, POSS_CLAIM), ("c1", "c2"), c)
    verdicts = (VerificationResult(True, "ok", 1), VerificationResult(True, "ok", 0.6049))
    assert render("{value:c2}", claims, ids, verdicts, c) == "60%"


@pytest.mark.parametrize(
    "metric,value,lang,expected",
    [("pressure_balance", 0.833, "en", "+0.83"), ("pressure_balance", -0.5, "en", "-0.50"),
     ("min_score_margin", -2, "en", "2"), ("shots", 5.0, "en", "5"), ("field_tilt", 0.316, "tr", "%32")],
)
def test_format_value(metric, value, lang, expected):
    assert format_value(metric, value, lang) == expected


def test_minute_and_start_rendering_in_stoppage_time():
    stoppage = Claim("count", Subject("home"), "shots", "eq", 0, MatchTime(1, 40, 0), MatchTime(1, 46, 30), ())
    c = ctx()
    out = render("{start:c1}–{minute:c1}", (stoppage,), ("c1",), (VerificationResult(True, "ok", 0),), c)
    assert out == "40'–45+2'"
