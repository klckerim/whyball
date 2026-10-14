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
