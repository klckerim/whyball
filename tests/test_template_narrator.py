from dataclasses import replace

import pytest

from app.analytics import detect_moments
from app.explain import MatchTime, build_narration, narrate
from app.explain.claims import KICKOFF
from app.explain.template_narrator import LANGS
from app.generator import EventType, generate_match
from app.generator.freeze import demo_paths
from app.generator.models import read_jsonl


def _find(seed, scenario, pred):
    events = generate_match(seed, scenario)
    moment = next(m for m in detect_moments(events) if pred(m))
    return events, moment, narrate(moment, events)


def _team(events, side):
    return events[0].data["teams"][side]["name"]


def _assert_published(narration, must_contain):
    failures = [
        (c.describe(), r.reason)
        for s, rs in zip(narration.sentences, narration.results)
        for c, r in zip(s.claims, rs) if not r.ok
    ]
    assert narration.all_verified, failures
    assert all(s.claims for s in narration.sentences)
    for lang in LANGS:
        text = narration.published(lang)
        assert text
        for needle in must_contain:
            assert needle in text, (lang, needle, text)


# --- moment tipi başına -------------------------------------------------------------


def test_goal():
    events, m, n = _find(42, "red_card_swing", lambda m: m.type == "goal")
    _assert_published(n, [m.detail["player"], _team(events, m.team), "1–0"])


def test_red_card():
    events, m, n = _find(42, "red_card_swing", lambda m: m.type == "red_card")
    _assert_published(n, [m.detail["player"], _team(events, m.team), "10"])


@pytest.mark.parametrize(
    "seed,scenario,outcome,en,tr",
    [
        (42, "late_comeback", "scored", "scores from the spot", "gole çevirdi"),
        (7, "dominant_loss", "saved", "sees the kick saved", "penaltıyı kullandı, vuruş kurtarıldı"),
    ],
)
def test_penalty(seed, scenario, outcome, en, tr):
    events, m, n = _find(
        seed, scenario, lambda m: m.type == "penalty" and m.detail["outcome"] == outcome
    )
    _assert_published(n, [m.detail["player"], _team(events, m.team)])
    assert en in n.published("en") and tr in n.published("tr")


def test_saved_penalty_keeps_taker_role_in_turkish():
    # foundry-v3 öncesi TR metni penaltıyı kullananı "kaleci" diye anıyordu (rol ters).
    _, m, n = _find(7, "dominant_loss", lambda m: m.type == "penalty" and m.detail["outcome"] == "saved")
    tr = n.published("tr")
    assert "kaleci" not in tr
    assert f"{m.detail['player']} penaltıyı kullandı" in tr


@pytest.mark.parametrize(
    "kind,en,tr",
    [
        ("opener", "open the scoring", "skoru açtı"),
        ("equalizer", "draw level", "eşitliği yakaladı"),
        ("go_ahead", "2 goals down", "2 gol gerideydi"),
    ],
)
def test_score_change(kind, en, tr):
    events, m, n = _find(
        42, "late_comeback", lambda m: m.type == "score_change" and m.detail["kind"] == kind
    )
    _assert_published(n, [_team(events, m.team)])
    assert en in n.published("en") and tr in n.published("tr")


def test_pressure_shift():
    events, m, n = _find(42, "red_card_swing", lambda m: m.type == "pressure_shift")
    _assert_published(n, [_team(events, m.team)])
    assert "pressure balance over the last 10 minutes of play is" in n.published("en")
    assert "son 10 oynanmış dakikadaki baskı dengesi" in n.published("tr")


def test_dominance_without_reward():
    events, m, n = _find(7, "dominant_loss", lambda m: m.type == "dominance_without_reward")
    _assert_published(n, [_team(events, m.team), "%"])
    assert "without reward" in n.published("en") and "sonuç alamıyor" in n.published("tr")


def test_dominance_possession_and_shots_share_one_stated_window():
    # M003 (dominant_loss/7): "58% of possession and 4–0 shots since 25'" pencereyi yalnızca şutlara bağlıyordu.
    _, m, n = _find(7, "dominant_loss", lambda m: m.type == "dominance_without_reward")
    (sentence,) = n.sentences
    poss, shots, opp = sentence.claims[:3]
    assert poss.metric == "possession" and shots.metric == opp.metric == "shots"
    assert (poss.start, poss.end) == (shots.start, shots.end) == (opp.start, opp.end)
    pct = f"{round(poss.value * 100)}%"
    en = sentence.text["en"]
    window = en.index(f"since {poss.start.minute}'")
    assert window < en.index(pct) < en.index(f"{shots.value:g}–{opp.value:g}")
    tr = sentence.text["tr"]
    assert tr.index(f"{poss.start.minute}. dakikadan bu yana") < tr.index(f"%{round(poss.value * 100)}")


# --- toplu ----------------------------------------------------------------------------


def _all_matches():
    for scenario in ("late_comeback", "red_card_swing", "dominant_loss"):
        for seed in (0, 42, 2024):
            yield generate_match(seed, scenario)
    for seed in (1, 2, 3):
        yield generate_match(seed)
    for _, _, path in demo_paths():
        yield read_jsonl(path)


def test_every_moment_in_many_matches_fully_verifies():
    total = 0
    types = set()
    for events in _all_matches():
        for m in detect_moments(events):
            n = narrate(m, events)
            assert n.all_verified, (m.id, m.type)
            total += sum(len(s.claims) for s in n.sentences)
            types.add(m.type)
    assert total > 0
    assert types == {
        "goal", "red_card", "penalty", "score_change", "pressure_shift", "dominance_without_reward"
    }


def test_every_windowed_claim_states_its_window():
    """Başlangıcı maç başı ya da olay anı olmayan her count/ratio iddiasının penceresi cümlede yazılı."""
    for events in _all_matches():
        for m in detect_moments(events):
            for s in narrate(m, events).sentences:
                for c in s.claims:
                    if c.kind == "state" or c.start == KICKOFF or c.start == c.end:
                        continue
                    assert f"since {c.start.minute}'" in s.text["en"], (m.id, c.describe())
                    assert f"{c.start.minute}. dakikadan" in s.text["tr"], (m.id, c.describe())


# --- yayın filtresi, determinizm, ileriye bakma ---------------------------------------


def test_sentence_with_failing_claim_is_not_published():
    events, m, n = _find(42, "red_card_swing", lambda m: m.type == "goal")
    first, *rest = n.sentences
    tampered = replace(first, claims=(replace(first.claims[0], value=2),))
    bad = build_narration(m, [tampered, *rest], events)
    assert not bad.all_verified
    for lang in LANGS:
        assert first.text[lang] not in bad.published(lang)
        assert rest[0].text[lang] in bad.published(lang)


def test_narration_is_deterministic():
    events = generate_match(42, "late_comeback")
    for m in detect_moments(events):
        assert narrate(m, events) == narrate(m, events)


def test_narration_ignores_events_after_moment():
    # Momentten sonraki olaylar bozulur (zaman aynı, takım/tip değişir); anlatı değişmemeli.
    events = generate_match(42, "red_card_swing")
    flip = {"home": "away", "away": "home"}
    for m in detect_moments(events):
        t = MatchTime(m.period, m.minute, m.second)
        k = next((i for i, e in enumerate(events) if MatchTime.of(e) > t), len(events))
        future = [
            replace(e, team=flip.get(e.team), type=EventType.SHOT if e.team else e.type)
            for e in events[k:]
        ]
        assert narrate(m, events[:k] + future) == narrate(m, events), m.id
