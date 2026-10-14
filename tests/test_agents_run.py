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


# --- stop at the first trouble, append ---------------------------------------------------------------------------


class TroubleClient:
    """A good model except for one trouble on its first Narrator call."""

    def __init__(self, trouble):
        from app.agents.dryrun import DryRunClient
        self.inner, self.trouble, self.narrated = DryRunClient(), trouble, 0

    async def complete(self, messages, *, response_model, max_tokens, reasoning_effort=None):
        if response_model.__name__ == "MenuDraftOut":
            self.narrated += 1
            if self.narrated == 1 and isinstance(self.trouble, Exception):
                raise self.trouble
            if self.narrated == 1:
                import asyncio
                await asyncio.sleep(self.trouble)
        return await self.inner.complete(messages, response_model=response_model, max_tokens=max_tokens,
                                         reasoning_effort=reasoning_effort)


def _moments(case="red_card"):
    from app.analytics import detect_moments
    from app.generator.models import read_jsonl
    events = read_jsonl(RED_PATH[0][2])
    return events, detect_moments(events)


@pytest.mark.parametrize("trouble,expected", [
    (RuntimeError("Error code: 429 - Too Many Requests"), "rate limit"),
    (0.5, "timed out"),
])
def test_the_first_429_or_timeout_stops_the_run_before_the_next_cards(trouble, expected):
    import asyncio

    from app.agents.limits import AgentsConfig
    from app.agents.workflow import AgentWorkflow

    events, moments = _moments()
    client = TroubleClient(trouble)
    wf = AgentWorkflow(events, client, agents=AgentsConfig(max_concurrent_cards=1, narrator_timeout_s=0.05), model_tag="m")
    results = asyncio.run(wf.run_cards(moments[:4], stop_on_trouble=True))
    assert results[0] is not None and results[1:] == [None, None, None]
    assert expected in wf.trouble
    assert client.narrated <= 3  # the first card may retry up to its three attempts; no other card started


def test_without_trouble_no_card_is_skipped():
    import asyncio

    from app.agents.dryrun import DryRunClient
    from app.agents.workflow import AgentWorkflow

    events, moments = _moments()
    results = asyncio.run(AgentWorkflow(events, DryRunClient(), model_tag="m").run_cards(moments[:4], stop_on_trouble=True))
    assert all(r is not None for r in results)


def test_append_adds_a_match_to_a_run_file_and_refuses_a_different_setup(tmp_path):
    out = tmp_path / "run.json"
    assert main(["--dry-run", "--out", str(out), "--match", RED]) == 0
    other = [p[2].stem for p in demo_paths() if p[2].stem != RED][0]
    assert main(["--dry-run", "--out", str(out), "--append", "--match", other]) == 0
    data = json.loads(out.read_text())
    assert [m["match_id"] for m in data["runs"][-1]["matches"]] == [RED, other]
    assert data["meta"]["calls"] > 0
    with pytest.raises(SystemExit, match="already"):
        main(["--dry-run", "--out", str(out), "--append", "--match", other])
    with pytest.raises(SystemExit, match="flags differs"):
        main(["--dry-run", "--out", str(out), "--append", "--no-verifier", "--match", "natural_seed100"])
