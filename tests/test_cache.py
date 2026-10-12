from app.explain.cache import NarrationCache, cache_key, moment_hash
from app.explain.narrator import FakeNarrator, TemplateNarrator
from app.explain.pipeline import run_match, run_moment
from tests.explain_helpers import match, moment_case


def test_same_input_calls_narrator_once(tmp_path):
    events, moment = moment_case("goal")
    cache, narrator = NarrationCache(tmp_path), FakeNarrator(events, "correct")
    first = run_moment(moment, narrator, events, cache=cache)
    second = run_moment(moment, narrator, events, cache=cache)

    assert narrator.calls == 1
    assert (first.cache_hit, second.cache_hit) == (False, True)
    assert (second.text, second.claims, second.verification) == (first.text, first.claims, first.verification)
    assert (second.source, second.attempts) == (first.source, first.attempts)
    assert [s["step"] for s in first.trace][0] == "cache" and not first.trace[0]["hit"]
    assert first.trace[-1]["step"] == "cache_store"
    assert [s["step"] for s in second.trace] == ["cache"] and second.trace[0]["hit"]


def test_prompt_version_change_regenerates(tmp_path):
    events, moment = moment_case("goal")
    cache, narrator = NarrationCache(tmp_path), FakeNarrator(events, "correct")
    run_moment(moment, narrator, events, cache=cache)
    assert not run_moment(moment, narrator, events, cache=cache, prompt_version="v2").cache_hit
    assert narrator.calls == 2
    assert run_moment(moment, narrator, events, cache=cache, prompt_version="v2").cache_hit
    assert narrator.calls == 2


def test_persona_and_language_are_part_of_key(tmp_path):
    events, moment = moment_case("goal")
    cache, narrator = NarrationCache(tmp_path), FakeNarrator(events, "correct")
    run_moment(moment, narrator, events, cache=cache)
    run_moment(moment, narrator, events, cache=cache, persona="analyst")
    run_moment(moment, narrator, events, cache=cache, language="tr")
    assert narrator.calls == 3


def test_corrupt_cache_entry_is_a_miss(tmp_path):
    events, moment = moment_case("goal")
    cache, narrator = NarrationCache(tmp_path), FakeNarrator(events, "correct")
    key = cache_key(moment, "neutral", "en", narrator.prompt_version)
    (tmp_path / f"{key}.json").write_text("{not json", encoding="utf-8")
    record = run_moment(moment, narrator, events, cache=cache)
    assert not record.cache_hit and narrator.calls == 1
    assert cache.get(key)["text"] == record.text  # bozuk kayıt üzerine yazıldı


def test_fallback_results_are_not_cached(tmp_path):
    events, moment = moment_case("goal")
    cache, narrator = NarrationCache(tmp_path), FakeNarrator(events, "wrong_number")
    for _ in range(2):
        assert run_moment(moment, narrator, events, cache=cache).source == "template_fallback"
    assert narrator.calls == 6
    assert list(tmp_path.iterdir()) == []


def test_narrators_do_not_share_entries(tmp_path):
    events, moment = moment_case("goal")
    cache = NarrationCache(tmp_path)
    run_moment(moment, TemplateNarrator(events), events, cache=cache)
    fake = FakeNarrator(events, "correct")
    assert not run_moment(moment, fake, events, cache=cache).cache_hit
    assert fake.calls == 1


def test_whole_match_second_run_is_all_hits(tmp_path):
    events, _ = match(7, "dominant_loss")
    cache, narrator = NarrationCache(tmp_path), FakeNarrator(events, "correct")
    first = run_match(events, narrator, cache=cache)
    calls = narrator.calls
    second = run_match(events, narrator, cache=cache)
    assert narrator.calls == calls == len(first)
    assert all(r.cache_hit for _, r in second)


def test_moment_hash_and_key_components():
    events, moments = match(42, "red_card_swing")
    hashes = [moment_hash(m) for m in moments]
    assert hashes == [moment_hash(m) for m in moments]
    assert len(set(hashes)) == len(hashes)
    m = moments[0]
    keys = {
        cache_key(m, "neutral", "en", "v1"),
        cache_key(m, "analyst", "en", "v1"),
        cache_key(m, "neutral", "tr", "v1"),
        cache_key(m, "neutral", "en", "v2"),
        cache_key(moments[1], "neutral", "en", "v1"),
    }
    assert len(keys) == 5
