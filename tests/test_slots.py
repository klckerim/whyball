from dataclasses import replace

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
from app.explain.config import DEFAULT_EXPLAIN_CONFIG
from app.explain.phrases import event_phrase
from app.explain.template_narrator import fmt_minute
from app.generator import generate_match
from app.generator.freeze import demo_paths
from app.generator.models import read_jsonl
from tests.explain_helpers import match

V3_RULES = replace(
    DEFAULT_EXPLAIN_CONFIG, slot_event_words=False, slot_sentence_start=False,
    slot_strict_number_words=False, slot_overstatement=False,
)

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
    assert lint_template("{event:%s}, making it {score}." % REF, ctx()).ok
    assert lint_template("{player:%s} was everywhere for {away} at {minute:c1}." % PID, ctx()).ok


def test_v3_template_passes_with_v3_rules_only():
    template = "{player:%s} scored for {away} at {minute:c1}, making it {score}." % PID
    assert lint_template(template, ctx(), V3_RULES).ok
    assert codes(lint_template(template, ctx()).issues) == [("event_word", "scored")]


# --- render ----------------------------------------------------------------------------------


def _render(template, claims, ids, lang="en"):
    c = ctx(lang)
    items, _, results, bound, bound_ids = check_slot_draft(template, claims, ids, c)
    assert not items, items
    return render(template, bound, bound_ids, results, c)


def test_away_goal_score_rendered_home_first_from_state():
    template = "{event:%s}, making it {score_named}." % REF
    assert _render(template, (GOAL_CLAIM,), ("c1",)) == f"{SCORER} scored at 57', making it {HOME} 0–1 {AWAY}."
    assert _render("{event:%s}, making it {score}." % REF, (GOAL_CLAIM,), ("c1",)) == (
        f"{SCORER} scored at 57', making it 0–1."
    )


def test_placeholder_at_sentence_start_is_capitalized():
    text = _render("{home} lead. {label:c2} is {value:c2}.", (GOAL_CLAIM, POSS_CLAIM), ("c1", "c2"))
    assert text == f"{HOME} lead. Possession is 61%."


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


# --- {event:} olay ifadeleri ------------------------------------------------------------------

# (tip, varyant) → (EN, TR); {p} oyuncu, {m} dakika, {in} oyuna giren, {team} takım.
EXPECTED_PHRASES = {
    ("goal", None): ("{p} scored at {m}", "{p} gol attı ({m})"),
    ("shot", "goal"): ("{p} scored at {m}", "{p} gol attı ({m})"),
    ("shot", "saved"): ("{p} had a shot saved at {m}", "{p} şut çekti, kurtarıldı ({m})"),
    ("shot", "blocked"): ("{p} had a shot blocked at {m}", "{p} şut çekti, rakibe çarptı ({m})"),
    ("shot", "off_target"): ("{p} shot off target at {m}", "{p} şut çekti, isabet bulmadı ({m})"),
    ("penalty", "scored"): ("{p} scored a penalty at {m}", "{p} penaltıyı gole çevirdi ({m})"),
    ("penalty", "saved"): ("{p}'s penalty was saved at {m}", "{p} penaltı kullandı, vuruş kurtarıldı ({m})"),
    ("penalty", "missed"): ("{p} missed a penalty at {m}", "{p} penaltıyı kaçırdı ({m})"),
    ("red_card", "straight_red"): ("{p} was sent off at {m}", "{p} kırmızı kartla oyundan atıldı ({m})"),
    ("red_card", "second_yellow"): ("{p} was sent off for a second yellow at {m}",
                                    "{p} ikinci sarı karttan oyundan atıldı ({m})"),
    ("yellow_card", None): ("{p} was booked at {m}", "{p} sarı kart gördü ({m})"),
    ("foul", None): ("{p} committed a foul at {m}", "{p} faul yaptı ({m})"),
    ("corner", None): ("{p} took a corner at {m}", "{p} korner kullandı ({m})"),
    ("pass", "success"): ("{p} completed a pass at {m}", "{p} pas verdi ({m})"),
    ("pass", "fail"): ("{p} lost the ball with a pass at {m}", "{p} pas denedi, top rakibe geçti ({m})"),
    ("dribble", "success"): ("{p} beat a defender at {m}", "{p} rakibini geçti ({m})"),
    ("dribble", "fail"): ("{p} was dispossessed at {m}", "{p} top kaybetti ({m})"),
    ("offside", None): ("{p} was caught offside at {m}", "{p} ofsayta düştü ({m})"),
    ("substitution", None): ("{in} came on for {p} at {m}", "{in}, {p} yerine oyuna girdi ({m})"),
    ("save", None): ("{team} made a save at {m}", "{team} kurtarış yaptı ({m})"),
}


def _variant(e):
    if e.type.value == "red_card":
        return (e.data or {}).get("reason")
    return e.outcome if e.type.value in ("shot", "penalty", "pass", "dribble") else None


def _corpus():
    for scenario in ("late_comeback", "red_card_swing", "dominant_loss", None):
        for seed in range(6):
            yield generate_match(seed, scenario)


def _first_events():
    found = {}
    for events in _corpus():
        for e in events:
            found.setdefault((e.type.value, _variant(e)), (e, events))
    return found


FIRST = _first_events()


@pytest.mark.parametrize("key", sorted(EXPECTED_PHRASES, key=str))
def test_event_phrase_per_type_and_outcome(key):
    assert key in FIRST, f"derlemde örnek yok: {key}"
    e, events = FIRST[key]
    teams = {side: events[0].data["teams"][side]["name"] for side in ("home", "away")}
    values = {"p": e.player, "m": fmt_minute(e.period, e.minute), "in": (e.data or {}).get("player_in"),
              "team": teams.get(e.team)}
    en, tr = EXPECTED_PHRASES[key]
    assert event_phrase(e, teams, "en") == en.format(**values)
    assert event_phrase(e, teams, "tr") == tr.format(**values)


@pytest.mark.parametrize("etype", ["match_meta", "kickoff", "half_time", "full_time"])
def test_non_narratable_events_have_no_phrase(etype):
    e, events = next(v for k, v in FIRST.items() if k[0] == etype)
    assert event_phrase(e, {"home": "H", "away": "A"}, "en") is None


def test_saved_penalty_phrase_never_names_the_goalkeeper():
    for events in _corpus():
        for i, e in enumerate(events):
            if e.type.value != "penalty" or e.outcome != "saved":
                continue
            keeper = next(x for x in events[i + 1:] if x.type.value == "save").player
            teams = {side: events[0].data["teams"][side]["name"] for side in ("home", "away")}
            for lang in ("en", "tr"):
                phrase = event_phrase(e, teams, lang)
                assert keeper not in phrase and keeper.split()[-1] not in phrase
                assert phrase.startswith(e.player)  # özne her zaman penaltıyı kullanan


def test_event_phrases_in_demo_matches_name_only_their_own_player():
    for _, _, path in demo_paths():
        events = read_jsonl(path)
        teams = {side: events[0].data["teams"][side]["name"] for side in ("home", "away")}
        names = set(player_ids(events).values())
        for e in events:
            for lang in ("en", "tr"):
                phrase = event_phrase(e, teams, lang)
                if phrase is None:
                    continue
                own = {e.player, (e.data or {}).get("player_in")} if e.type.value != "save" else set()
                assert {n for n in names if n in phrase} <= own, (e.seq, phrase)


def test_event_must_be_evidence_of_a_claim():
    c = ctx()
    _, _, issues = bind_template("{event:%s}." % REF, (POSS_CLAIM,), ("c1",), c)  # POSS_CLAIM REF'i kanıt sayıyor
    assert issues == []
    other = next(e for e in EVENTS if e.type.value == "shot" and e.seq < GOAL.event_ids[-1])
    ref = f"{EVENTS[0].match_id}#{other.seq}"
    _, _, issues = bind_template("{event:%s}." % ref, (GOAL_CLAIM,), ("c1",), c)
    assert codes(issues) == [("event_not_evidence", "{event:%s}" % ref)]
    _, _, issues = bind_template("{event:m-other#5}.", (GOAL_CLAIM,), ("c1",), c)
    assert codes(issues) == [("unbound_placeholder", "{event:m-other#5}")]
    meta = f"{EVENTS[0].match_id}#0"
    tagged = replace(GOAL_CLAIM, event_ids=(meta,))
    _, _, issues = bind_template("{event:%s}." % meta, (tagged,), ("c1",), c)
    assert codes(issues) == [("unsupported_event", "{event:%s}" % meta)]


def test_role_reversal_cannot_be_written():
    # v3'te yayınlanan hata (dominant_loss M009): penaltıyı kullanan "saved a penalty" diye anıldı.
    found = codes(lint_template("{player:%s} saved a penalty at {minute:c1}." % PID, ctx()).issues)
    assert ("event_word", "saved") in found and ("event_word", "penalty") in found
    tr = codes(lint_template("{player:%s} penaltı kurtardı." % PID, ctx("tr")).issues)
    assert ("event_word", "penaltı") in tr and ("event_word", "kurtardı") in tr


# --- v4 lint kuralları ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "template,lang,fragment",
    [("Ravello pressed high. {home} lead.", "en", "Ravello"),
     ("{home} lead. Quintana was everywhere.", "en", "Quintana"),
     ("Kesinlikle {home} önde.", "tr", "Kesinlikle")],
)
def test_sentence_must_start_with_placeholder_or_allowed_word(template, lang, fragment):
    found = codes(lint_template(template, ctx(lang)).issues)
    assert ("sentence_start", fragment) in found
    assert not any(code == "sentence_start" for code, _ in codes(lint_template(template, ctx(lang), V3_RULES).issues))


def test_turkish_ordinal_dot_is_not_a_sentence_break():
    assert lint_template("{start:c1}. dakikadan bu yana {home} önde.", ctx("tr")).ok


@pytest.mark.parametrize("template,lang,word", [
    ("{home} were one of the sides in it.", "en", "one"),
    ("{home} bir ara önde.", "tr", "bir"),
])
def test_number_words_are_rejected_regardless_of_context(template, lang, word):
    assert ("raw_number", word) in codes(lint_template(template, ctx(lang)).issues)
    assert lint_template(template, ctx(lang), V3_RULES).ok


def test_overstatement_needs_moment_type_support():
    assert ("overstatement", "deep into") in codes(lint_template("{event:%s} deep into the half." % REF, ctx()).issues)
    assert ("overstatement", "take control") in codes(lint_template("{home} take control.", ctx()).issues)
    pressure = replace(ctx(), moment_type="pressure_shift")
    assert lint_template("{home} take control.", pressure).ok
    dominance = replace(ctx(), moment_type="dominance_without_reward")
    assert lint_template("{home} dominate without reward.", dominance).ok
    assert not lint_template("{home} dominate without reward.", pressure).ok
