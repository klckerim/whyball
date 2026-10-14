"""docs/development_set.json lists what P4's held-out set must exclude; it must cover what the runs and the smoke test used."""

import json
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
DEV = json.loads((DOCS / "development_set.json").read_text(encoding="utf-8"))


def _pairs(items):
    return {(i["match"], i["moment"]) for i in items}


def test_the_smoke_drafts_are_all_in_the_development_set():
    smoke = json.loads((DOCS / "VERIFIER_SMOKE.json").read_text(encoding="utf-8"))
    assert smoke["meta"]["development_set"] is True
    assert _pairs(smoke["meta"]["drafts"]) == _pairs(DEV["verifier_smoke_drafts"])


def test_every_card_of_the_agent_runs_is_in_the_development_set():
    for name in ("AGENT_RUN.json", "AGENT_RUN_canary.json", "archive/AGENT_RUN_rerun1.json", "archive/AGENT_RUN_run2.json"):
        path = DOCS / name
        if not path.exists():
            continue
        run = json.loads(path.read_text(encoding="utf-8"))["runs"][-1]
        got = {(m["match_id"], c["id"]) for m in run["matches"] for c in m["moments"]}
        assert got <= _pairs(DEV["featured_cards"]), name


def test_the_markdown_names_the_json_and_the_rule():
    text = (DOCS / "DEVELOPMENT_SET.md").read_text(encoding="utf-8")
    assert "development_set.json" in text and "held-out" in text
