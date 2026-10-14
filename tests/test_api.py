import json

import pytest
from fastapi.testclient import TestClient

from app.api import replay as replay_module
from app.api.data import match_clock
from app.analytics.config import DEFAULT_CONFIG
from app.api.main import create_app
from app.explain.claims import COMPARISONS, KINDS, METRIC_KINDS
from app.explain.labels import METRIC_LABELS
from app.generator.models import EventType, read_jsonl
from app.publish.store import DEFAULT_OUT_DIR

MATCH = "red_card_swing_seed42"
STORE = json.loads((DEFAULT_OUT_DIR / f"{MATCH}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    static = tmp_path_factory.mktemp("static")
    (static / "index.html").write_text('<!doctype html><div id="root"></div>', encoding="utf-8")
    with TestClient(create_app(static_dir=static)) as c:
        yield c


def parse_sse(text):
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_matches(client):
    body = client.get("/api/matches").json()
    assert [m["id"] for m in body] == ["dominant_loss_seed7", "natural_seed100", "red_card_swing_seed42"]
    red = body[2]
    assert red["teams"] == STORE["teams"] and red["final_score"] == STORE["final_score"]
    assert red["moments"] == len(STORE["moments"])
    assert red["sources"] == {"llm": 6, "template": 3, "template_fallback": 0}


def test_match_detail(client):
    d = client.get(f"/api/matches/{MATCH}").json()
    assert d["run_id"] == STORE["run_id"]
    assert [p["period"] for p in d["periods"]] == [1, 2]
    assert d["periods"][0]["end_t"] == d["periods"][1]["start_t"]
    assert d["duration_t"] == d["periods"][1]["end_t"]
    goals = [e for e in d["timeline"] if e["type"] == "goal"]
    assert [(e["minute_label"], e["score"]) for e in goals] == [
        ("22'", {"home": 1, "away": 0}), ("61'", {"home": 1, "away": 1}), ("84'", {"home": 1, "away": 2})]
    assert [e["t"] for e in d["timeline"]] == sorted(e["t"] for e in d["timeline"])


TIMELINE_FIELDS = {"seq", "t", "period", "minute", "second", "minute_label", "type", "team", "player",
                   "outcome", "score"}


def test_timeline_carries_ball_position(client):
    timeline = client.get(f"/api/matches/{MATCH}").json()["timeline"]
    assert all(TIMELINE_FIELDS | {"x", "y"} == set(e) for e in timeline)  # B1 adds x, y; nothing else changes
    goals = [e for e in timeline if e["type"] == "goal"]
    cards = [e for e in timeline if e["type"] in ("red_card", "yellow_card")]
    assert goals and cards
    assert all(0 <= e["x"] <= 105 and 0 <= e["y"] <= 68 for e in goals)
    assert all(e["x"] is None and e["y"] is None for e in cards)


def test_replay_events_carry_ball_position(client):
    items = parse_sse(client.get(f"/api/matches/{MATCH}/replay", params={"speed": 0}).text)
    events = [d for kind, d in items if kind == "match_event"]
    by_seq = client.app.state.matches[MATCH].by_seq
    assert all((d["x"], d["y"]) == (by_seq[d["seq"]].x, by_seq[d["seq"]].y) for d in events)
    assert any(d["x"] is not None for d in events)


@pytest.mark.parametrize("match_id", ["dominant_loss_seed7", "natural_seed100", "red_card_swing_seed42"])
def test_match_detail_squads(client, match_id):
    d = client.get(f"/api/matches/{match_id}").json()
    store = json.loads((DEFAULT_OUT_DIR / f"{match_id}.json").read_text(encoding="utf-8"))
    meta = read_jsonl(DEFAULT_OUT_DIR.parent.parent / store["events_file"])[0]
    assert meta.type is EventType.MATCH_META
    assert d["squads"] == meta.data["teams"]
    names = {p for side in d["squads"].values() for p in side["lineup"] + side["bench"]}
    assert {e["player"] for e in d["timeline"] if e["player"]} <= names


def test_metrics(client):
    body = client.get("/api/metrics").json()
    assert [m["id"] for m in body["metrics"]] == list(METRIC_KINDS)
    assert body["kinds"] == list(KINDS) and body["comparisons"] == list(COMPARISONS)
    for m in body["metrics"]:
        assert m["kind"] == METRIC_KINDS[m["id"]]
        assert m["label"] == METRIC_LABELS["en"][m["id"]]
        assert m["definition"].strip()
        if m["id"] == "pressure_balance":
            assert m["window"] == {"type": "rolling", "minutes": DEFAULT_CONFIG.pressure_window_min, "start_used": False}
            assert f"{DEFAULT_CONFIG.pressure_window_min:g} minutes" in m["definition"]
        else:
            start_used = m["id"] not in ("score", "score_margin", "players_on_pitch")
            assert m["window"] == {"type": "claim_range", "minutes": None, "start_used": start_used}


def test_metrics_matches_the_tool_api(client):
    from app.explain.tool_api import list_metrics_tool

    tool = list_metrics_tool({})["result"]
    body = client.get("/api/metrics").json()
    assert {m["id"]: m["kind"] for m in body["metrics"]} == tool["metrics"]
    assert (body["kinds"], body["comparisons"]) == (tool["kinds"], tool["comparisons"])


def test_healthz(client):
    r = client.get("/healthz")  # outside /api, and not shadowed by the static UI mount
    assert r.status_code == 200 and r.json() == {"ok": True, "matches": 3}


def test_moments(client):
    body = client.get(f"/api/matches/{MATCH}/moments").json()
    assert [m["id"] for m in body] == [m["id"] for m in STORE["moments"]]
    for m, stored in zip(body, STORE["moments"]):
        for c in m["claims"]:
            for ev in c["evidence"]:
                ev.pop("x"), ev.pop("y")
        assert {k: v for k, v in m.items() if k != "t"} == stored
    assert [m["t"] for m in body] == sorted(m["t"] for m in body)


def test_evidence_carries_pitch_position(client):
    body = client.get(f"/api/matches/{MATCH}/moments").json()
    evidence = {ev["type"]: ev for m in body for c in m["claims"] for ev in c["evidence"]}
    shot = evidence["shot"]
    assert 0 <= shot["x"] <= 105 and 0 <= shot["y"] <= 68
    assert evidence["red_card"]["x"] is None and evidence["red_card"]["y"] is None


@pytest.mark.parametrize("path", ["/api/matches/nope", "/api/matches/nope/moments", "/api/matches/nope/replay"])
def test_unknown_match(client, path):
    assert client.get(path).status_code == 404


def test_match_clock_continues_after_half_time(client):
    events = client.app.state.matches[MATCH].events
    t = match_clock(events)
    half = next(e for e in events if e.type is EventType.HALF_TIME)
    second_half = next(e for e in events if e.period == 2)
    assert (second_half.minute, second_half.second) == (45, 0)
    assert t[second_half.seq] == t[half.seq]
    assert [t[e.seq] for e in events] == sorted(t[e.seq] for e in events)


def test_replay_stream(client):
    r = client.get(f"/api/matches/{MATCH}/replay", params={"speed": 0})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    items = parse_sse(r.text)
    assert items[-1][0] == "end"
    events = [d for kind, d in items if kind == "match_event"]
    assert all(d["type"] != "match_meta" for d in events)
    assert [(d["t"], d["seq"]) for d in events] == sorted((d["t"], d["seq"]) for d in events)
    moments = [(i, d) for i, (kind, d) in enumerate(items) if kind == "moment"]
    assert [d["id"] for _, d in moments] == [m["id"] for m in STORE["moments"]]
    for i, d in moments:  # a card follows the event that triggered it
        before = next(x for kind, x in reversed(items[:i]) if kind == "match_event")
        assert before["seq"] == d["at_seq"] and d["t"] == before["t"]


def test_replay_from_t(client):
    items = parse_sse(client.get(f"/api/matches/{MATCH}/replay", params={"speed": 0, "from_t": 3600}).text)
    events = [d for kind, d in items if kind == "match_event"]
    assert events and min(d["t"] for d in events) >= 3600
    assert all(d["t"] >= 3600 for kind, d in items if kind == "moment")
    assert {d["id"] for kind, d in items if kind == "moment"} == {
        m["id"] for m in client.get(f"/api/matches/{MATCH}/moments").json() if m["t"] >= 3600}


@pytest.mark.parametrize("params", [{"speed": -1}, {"speed": 100000}, {"from_t": -5}, {"speed": "fast"}])
def test_replay_rejects_bad_params(client, params):
    assert client.get(f"/api/matches/{MATCH}/replay", params=params).status_code == 422


def test_replay_waits_by_speed(client, monkeypatch):
    waits = []

    async def record(seconds):
        waits.append(seconds)

    monkeypatch.setattr(replay_module, "_sleep", record)
    items = parse_sse(client.get(f"/api/matches/{MATCH}/replay", params={"speed": 60, "from_t": 5400}).text)
    ts = [d["t"] for kind, d in items if kind == "match_event"]
    gaps = [b - a for a, b in zip(ts, ts[1:]) if b > a]
    assert waits == pytest.approx([g / 60 for g in gaps])
    assert sum(waits) == pytest.approx((ts[-1] - ts[0]) / 60)


def test_lifespan_http_client(tmp_path):
    app = create_app(static_dir=tmp_path)
    with TestClient(app):
        http = app.state.http
        assert not http.is_closed
    assert http.is_closed


def test_static_ui_served(client):
    r = client.get("/")
    assert r.status_code == 200 and '<div id="root">' in r.text


def test_ui_not_built(tmp_path):
    with TestClient(create_app(static_dir=tmp_path / "missing")) as c:
        r = c.get("/")
        assert r.status_code == 503 and "npm run build" in r.text
        assert c.get("/api/health").json() == {"ok": True}


def test_stale_store_is_refused(tmp_path):
    import shutil

    from app.api.data import DataError
    from app.publish.store import REPO_ROOT

    shutil.copytree(REPO_ROOT / "data" / "demo", tmp_path / "demo")
    (tmp_path / "demo_narration").mkdir()
    stale = dict(STORE, events_sha256="0" * 64)
    (tmp_path / "demo_narration" / f"{MATCH}.json").write_text(json.dumps(stale), encoding="utf-8")
    with pytest.raises(DataError, match="python -m app.publish"):
        with TestClient(create_app(data_dir=tmp_path, static_dir=tmp_path)):
            pass


# --- events, series, deep links (UI v2 B9, B2) -------------------------------------------------------


def test_events_endpoint_is_the_whole_stream(client):
    body = client.get(f"/api/matches/{MATCH}/events").json()
    m = client.app.state.matches[MATCH]
    assert [e["seq"] for e in body] == [e.seq for e in m.events]
    assert body[0]["type"] == "match_meta"
    assert all((e["x"], e["y"], e["t"]) == (m.by_seq[e["seq"]].x, m.by_seq[e["seq"]].y, m.t[e["seq"]]) for e in body)
    timeline = client.get(f"/api/matches/{MATCH}").json()["timeline"]
    by_seq = {e["seq"]: e for e in body}
    assert all(by_seq[e["seq"]] == e for e in timeline)
    assert client.get("/api/matches/nope/events").status_code == 404


@pytest.mark.parametrize("metric", ["pressure_balance", "possession", "field_tilt"])
def test_series_matches_metrics_at(client, metric):
    from app.analytics import metrics_at
    from app.api.series import sample_times

    url = f"/api/matches/{MATCH}/series"
    r1 = client.get(url, params={"metric": metric, "step": 120})
    r2 = client.get(url, params={"metric": metric, "step": 120})
    assert r1.status_code == 200 and r1.content == r2.content  # deterministic
    body = r1.json()
    m = client.app.state.matches[MATCH]
    assert [p["t"] for p in body["points"]] == sample_times(m.duration_t, 120)
    assert body["points"][-1]["t"] == m.duration_t
    assert body["perspective"] == "home" and body["step"] == 120
    info = {i["id"]: i for i in client.get("/api/metrics").json()["metrics"]}[metric]
    assert (body["label"], body["definition"]) == (info["label"], info["definition"])
    for p in body["points"]:
        last = max((e for e in m.events if m.t[e.seq] <= p["t"]), key=lambda e: e.seq)
        snap = metrics_at(m.events, until_seq=last.seq)
        expected = {"pressure_balance": snap.pressure_balance, "possession": snap.possession["home"],
                    "field_tilt": snap.field_tilt["home"]}[metric]
        if metric == "pressure_balance" and snap.played_seconds < DEFAULT_CONFIG.pressure_window_min * 60:
            assert p["value"] is None  # window not full: not computable, never 0
        else:
            assert p["value"] == round(expected, DEFAULT_CONFIG.summary_decimals)


def test_series_windows(client):
    pb = client.get(f"/api/matches/{MATCH}/series", params={"metric": "pressure_balance"}).json()
    assert pb["window"] == {"type": "rolling", "minutes": DEFAULT_CONFIG.pressure_window_min, "start_used": False}
    assert any(p["value"] is None for p in pb["points"]) and any(p["value"] is not None for p in pb["points"])
    share = client.get(f"/api/matches/{MATCH}/series", params={"metric": "possession"}).json()
    assert share["window"] == {"type": "cumulative", "minutes": None, "start_used": False}
    assert all(p["value"] is not None for p in share["points"])


@pytest.mark.parametrize("params,status", [
    ({"metric": "goals"}, 404), ({"metric": "nope"}, 404), ({}, 422),
    ({"metric": "possession", "step": 5}, 422), ({"metric": "possession", "step": 901}, 422),
    ({"metric": "possession", "step": "x"}, 422),
])
def test_series_rejects_bad_requests(client, params, status):
    assert client.get(f"/api/matches/{MATCH}/series", params=params).status_code == status
    assert client.get("/api/matches/nope/series", params={"metric": "possession"}).status_code == 404


@pytest.mark.parametrize("path", ["/match/red_card_swing_seed42", "/match/nope", "/match/x/y"])
def test_deep_links_get_the_ui(client, path):
    r = client.get(path)
    assert r.status_code == 200 and '<div id="root">' in r.text


@pytest.mark.parametrize("path", ["/missing.js", "/assets/x.png", "/api/nope", "/api/matches/nope/x"])
def test_missing_files_and_api_paths_stay_404(client, path):
    assert client.get(path).status_code == 404


# --- the stored agent trace is replayed, never run (P2) -------------------------------------------------------


def _store_with_trace(tmp_path):
    import shutil

    data = tmp_path / "data"
    shutil.copytree(DEFAULT_OUT_DIR.parent / "demo", data / "demo")
    (data / "demo_narration").mkdir()
    store = json.loads((DEFAULT_OUT_DIR / f"{MATCH}.json").read_text(encoding="utf-8"))
    card = next(m for m in store["moments"] if m["source"] == "llm")
    card["trace"] = [
        {"step": s, "agent": a, "attempt": 1, "started_ms": i, "duration_ms": 2, "input_ref": "x", "output": {},
         "tokens": {"in": None, "out": None, "reasoning": None}, "model": None, "status": "ok"}
        for i, (s, a) in enumerate([("narrate", "narrator"), ("guard", "guard"), ("finalize", "workflow")])
    ]
    (data / "demo_narration" / f"{MATCH}.json").write_text(json.dumps(store), encoding="utf-8")
    return data, card


def test_the_replay_sends_a_stored_trace_after_its_card(tmp_path):
    data, card = _store_with_trace(tmp_path)
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html>", encoding="utf-8")
    with TestClient(create_app(data_dir=data, static_dir=static)) as c:
        events = parse_sse(c.get(f"/api/matches/{MATCH}/replay", params={"speed": 0}).text)
    names = [n for n, _ in events]
    assert set(names) == {"match_event", "moment", "trace", "end"} and names[-1] == "end"
    at = names.index("moment") if False else next(i for i, (n, d) in enumerate(events) if n == "moment" and d["id"] == card["id"])
    follow = events[at + 1:at + 4]
    assert [n for n, _ in follow] == ["trace"] * 3
    assert [d["step"] for _, d in follow] == ["narrate", "guard", "finalize"]
    assert [d["n"] for _, d in follow] == [0, 1, 2] and all(d["moment_id"] == card["id"] for _, d in follow)
    # the store holds a trace for every model card (the agent run): the stream sends exactly the stored steps
    store = json.loads((data / "demo_narration" / f"{MATCH}.json").read_text())
    assert sum(n == "trace" for n in names) == sum(len(m["trace"]) for m in store["moments"])


def test_the_published_replay_carries_every_stored_trace_step_after_its_card(client):
    events = parse_sse(client.get(f"/api/matches/{MATCH}/replay", params={"speed": 0}).text)
    cards = {m["id"]: m for m in STORE["moments"]}
    traces = [(d["moment_id"], d["n"], d["step"]) for n, d in events if n == "trace"]
    assert traces == [(m["id"], i, s["step"]) for m in STORE["moments"] for i, s in enumerate(m["trace"])]
    assert traces  # the published store is an agent run
    # a trace step follows its own card's moment event; match events and moments keep their order
    order = [(n, d.get("id") or d.get("moment_id")) for n, d in events if n in ("moment", "trace")]
    for i, (n, mid) in enumerate(order):
        if n == "trace":
            assert order[i - 1][1] == mid and mid in cards


def test_the_replay_of_a_store_without_traces_is_unchanged(tmp_path):
    import shutil

    data = tmp_path / "data"
    shutil.copytree(DEFAULT_OUT_DIR.parent / "demo", data / "demo")
    (data / "demo_narration").mkdir()
    store = json.loads((DEFAULT_OUT_DIR / f"{MATCH}.json").read_text(encoding="utf-8"))
    for m in store["moments"]:
        m["trace"] = []
    (data / "demo_narration" / f"{MATCH}.json").write_text(json.dumps(store), encoding="utf-8")
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html>", encoding="utf-8")
    with TestClient(create_app(data_dir=data, static_dir=static)) as c:
        names = {n for n, _ in parse_sse(c.get(f"/api/matches/{MATCH}/replay", params={"speed": 0}).text)}
    assert names == {"match_event", "moment", "end"}


def test_a_moment_carries_its_verification(client):
    for m in client.get(f"/api/matches/{MATCH}/moments").json():
        assert set(m["verification"]) == {"guard", "verifier", "attempts", "label_source"}
        assert m["trace"] == [] or all("step" in s for s in m["trace"])
