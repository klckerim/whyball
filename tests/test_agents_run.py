"""P2 / 3g: the CLI, the estimate and the run file that `app.publish` reads (dry run: no model, no network)."""

import json
from pathlib import Path

import pytest

from app.agents import run as run_mod
from app.agents.run import baseline_tokens, estimate, format_estimate, main
from app.agents.state import Flags
from app.generator.freeze import demo_paths
from app.publish.store import PublishError, build, outputs, DEFAULT_OUT_DIR, DEFAULT_REPORT

RED = "red_card_swing_seed42"
RED_PATH = [p for p in demo_paths() if p[2].stem == RED]


def run_cli(tmp_path, *args):
    out = tmp_path / "run.json"
    code = main(["--dry-run", "--out", str(out), *args])
    return code, out


def test_a_dry_run_runs_every_moment_of_a_match_and_writes_a_run_file(tmp_path, capsys):
    code, out = run_cli(tmp_path, "--match", RED, "--moments", "all")
    text = capsys.readouterr().out
    assert code == 0 and out.exists()
    data = json.loads(out.read_text())
    moments = data["runs"][-1]["matches"][0]["moments"]
    assert len(moments) == 9 and text.count("attempts=") == 9
    assert data["meta"]["dry_run"] is True and data["meta"]["analyst_version"] == "analyst-v1"
    assert data["meta"]["verifier_version"] == "verifier-v1" and data["meta"]["flags"] == {"analyst": True, "verifier": True}
    for m in moments:
        assert m["trace"][-1]["step"] == "finalize" and m["verification"]["guard"] is True
        assert {"id", "type", "source", "template", "text", "attempts", "verification", "trace"} <= set(m)


def test_featured_runs_only_the_selected_moments(tmp_path):
    _, out = run_cli(tmp_path, "--match", RED, "--moments", "featured")
    assert len(json.loads(out.read_text())["runs"][-1]["matches"][0]["moments"]) == 6


def test_the_flags_reach_the_workflow(tmp_path):
    _, out = run_cli(tmp_path, "--match", RED, "--no-analyst", "--no-verifier")
    for m in json.loads(out.read_text())["runs"][-1]["matches"][0]["moments"]:
        steps = [s["step"] for s in m["trace"]]
        assert "analyst" not in steps and "verify" not in steps
        assert m["verification"] == {"guard": True, "verifier": "not_run", "attempts": 1, "label_source": "guard_only"}


def test_without_out_a_dry_run_writes_nothing(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["--dry-run", "--match", RED]) == 0
    assert list(tmp_path.iterdir()) == []


def test_a_dry_run_file_is_never_published(tmp_path):
    _, out = run_cli(tmp_path, "--match", RED)
    with pytest.raises(PublishError, match="dry run"):
        build(out, RED_PATH)


def test_a_run_file_of_real_traces_publishes_end_to_end(tmp_path):
    """The dry run's traces and verifications pass the store's consistency checks once it is not marked dry."""
    _, out = run_cli(tmp_path, "--match", RED, "--moments", "all")
    data = json.loads(out.read_text())
    data["meta"]["dry_run"] = False  # only to exercise the store; a real file is never edited
    out.write_text(json.dumps(data))
    result = build(out, RED_PATH)
    store = result.stores[0]
    assert len(store.moments) == 9
    cards_with_trace = [c for c in store.moments if c.trace]
    assert len(cards_with_trace) == 9 and all(c.verification.verifier == "passed" for c in cards_with_trace)
    assert {c.source for c in store.moments} == {"llm"}  # the agent run wrote model cards for every moment
    assert all(c.verification.label_source == "llm" for c in store.moments)
    assert "## Verification and trace" in outputs(result, DEFAULT_OUT_DIR, DEFAULT_REPORT)[DEFAULT_REPORT]


def test_the_estimate_is_derived_from_the_measured_run_and_says_what_it_assumes():
    base = baseline_tokens()
    assert base["calls"] >= 40 and 1000 < base["input"] < 5000
    e = estimate(25, Flags(), base)
    assert e["calls_worst"] == 25 * (1 + 3 * 2) and e["calls_typical"] < e["calls_worst"]
    assert e["input_tokens_typical"] == round(e["calls_typical"] * base["input"])
    text = format_estimate(e, 3)
    assert "not measured" in text and "docs/LLM_RUN.json" in text
    off = estimate(25, Flags(analyst=False, verifier=False), base)
    assert off["calls_worst"] == 25 * 3 and off["calls_typical"] < e["calls_typical"]


def test_estimate_only_stops_before_any_client(capsys, monkeypatch):
    monkeypatch.setattr(run_mod, "live_client", lambda: pytest.fail("a client was built"))
    assert main(["--estimate", "--match", "all", "--moments", "all"]) == 0
    assert "estimate for 25 moments" in capsys.readouterr().out


def test_a_live_run_needs_a_confirmation(monkeypatch, capsys):
    monkeypatch.setattr(run_mod, "live_client", lambda: pytest.fail("a client was built"))
    monkeypatch.setattr("sys.stdin", open("/dev/null"))
    assert main(["--match", RED]) == 2
    assert "needs --yes" in capsys.readouterr().err
