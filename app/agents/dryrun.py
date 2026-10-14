"""A client that answers like a well-behaved model, with no network: for `--dry-run` and smoke tests.

Analyst: every claim id and a plain note. Narrator: a template of ready clauses covering the moment's primary claims (a
different, smaller choice on each retry). Verifier: pass. It reads only the moment record, like the real agents.
"""

from __future__ import annotations

import json
import re

from app.explain.llm_narrator import ChatResult


def _record(messages: list[dict[str, str]]) -> dict:
    return json.JSONDecoder().raw_decode(messages[1]["content"])[0]


def _attempt(messages: list[dict[str, str]]) -> int:
    m = re.search(r"Previous attempt (\d+) was rejected", messages[1]["content"])
    return int(m.group(1)) + 1 if m else 1


def pick_clauses(record: dict, attempt: int) -> list[str]:
    clauses = record["clauses"]
    primary = {c["id"] for c in record["claims_menu"] if c.get("primary")}
    chosen: list[str] = []
    covered: set[str] = set()
    for c in clauses:
        if primary - covered and primary & set(c["claims"]):
            chosen.append(c["id"])
            covered |= set(c["claims"])
    if not chosen and clauses:
        chosen = [clauses[0]["id"]]
    if attempt == 2:
        chosen = chosen[:2]
    if attempt >= 3:
        chosen = chosen[:1]
    return chosen


class DryRunClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, messages, *, response_model, max_tokens, reasoning_effort=None) -> ChatResult:
        name = response_model.__name__
        self.calls.append(name)
        record = _record(messages)
        if name == "AnalystOut":
            text = json.dumps({"claim_ids": [c["id"] for c in record["claims_menu"]],
                               "context_note": "a moment worth explaining in plain words"})
        elif name == "VerifierOut":
            text = json.dumps({"ok": True, "issues": []})
        else:
            ids = pick_clauses(record, _attempt(messages))
            text = json.dumps({"text": ", and ".join("{clause:%s}" % i for i in ids) + "."})
        return ChatResult(text, input_tokens=0, output_tokens=0, reasoning_tokens=0)
