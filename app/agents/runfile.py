"""The run file an agent run writes (docs/AGENT_RUN.json): the shape of docs/LLM_RUN.json that `app.publish` reads, plus each
card's verification and trace. `app.publish` replays the accepted drafts through the current Guard before storing them."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.analytics.moments import Moment

from .workflow import CardOutcome


def moment_entry(moment: Moment, outcome: CardOutcome) -> dict[str, Any]:
    card = outcome.card
    return {
        "id": moment.id, "type": moment.type, "period": moment.period, "minute": moment.minute, "second": moment.second,
        "source": card.source, "template": card.template, "text": card.text, "ok": bool(card.text),
        "attempts": card.verification.attempts, "verification": card.verification.to_dict(),
        "trace": [s.to_dict() for s in outcome.trace],
    }


def token_totals(outcomes: Sequence[CardOutcome]) -> dict[str, int]:
    totals = {"in": 0, "out": 0, "reasoning": 0}
    for o in outcomes:
        for s in o.trace:
            if s.tokens:
                totals["in"] += s.tokens.input or 0
                totals["out"] += s.tokens.output or 0
                totals["reasoning"] += s.tokens.reasoning or 0
    return totals


def write_run(path: Path, meta: dict[str, Any], started_at: str, finished_at: str,
              matches: list[dict[str, Any]]) -> None:
    data = {"meta": meta, "runs": [{"started_at": started_at, "finished_at": finished_at, "matches": matches}]}
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def usage_rows(usage: Sequence[Any]) -> list[dict[str, Any]]:
    return [asdict(u) for u in usage]


def append_run(path: Path, meta: dict[str, Any], matches: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """Adds `matches` to the run file at `path` (written by the same model, prompt and flags) and rewrites it. Returns the
    run's start time and the merged meta (calls, tokens and wall time summed)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    old, run = data["meta"], data["runs"][-1]
    for key in ("model", "prompt_version", "analyst_version", "verifier_version", "flags", "moments", "dry_run"):
        if old.get(key) != meta.get(key):
            raise SystemExit(f"cannot append: {key} differs ({old.get(key)!r} vs {meta.get(key)!r})")
    have = {m["match_id"] for m in run["matches"]}
    clash = have & {m["match_id"] for m in matches}
    if clash:
        raise SystemExit(f"cannot append: {sorted(clash)} are already in {path.name}")
    merged = dict(meta)
    merged["started_at"] = old["started_at"]
    merged["calls"] = old["calls"] + meta["calls"]
    merged["wall_seconds"] = round(old["wall_seconds"] + meta["wall_seconds"], 1)
    merged["tokens"] = {k: old["tokens"][k] + meta["tokens"][k] for k in meta["tokens"]}
    data = {"meta": merged, "runs": [{"started_at": old["started_at"], "finished_at": meta["finished_at"],
                                      "matches": [*run["matches"], *matches]}]}
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return old["started_at"], merged
