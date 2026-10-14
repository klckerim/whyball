"""Fake model client for the agent tests: scripted answers per response model, no network."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from app.explain.llm_narrator import ChatResult


@dataclass
class Sleep:
    seconds: float


class ScriptedClient:
    """Replies per response model name ("MenuDraftOut", "AnalystOut", "VerifierOut"); the last step repeats.

    A step is a str (the JSON reply), a callable(messages) -> str, a `Sleep` (the call hangs that long), or an
    Exception (raised). `calls` records every call with its response model.
    """

    def __init__(self, **scripts: list | str) -> None:
        self.scripts = {k: list(v) if isinstance(v, list) else [v] for k, v in scripts.items()}
        self.calls: list[dict] = []

    def count(self, model: str) -> int:
        return sum(c["model"] == model for c in self.calls)

    async def complete(self, messages, *, response_model, max_tokens, reasoning_effort=None):
        name = response_model.__name__
        self.calls.append({"model": name, "messages": messages, "max_tokens": max_tokens,
                           "reasoning_effort": reasoning_effort})
        script = self.scripts.get(name)
        if not script:
            raise AssertionError(f"no script for {name}")
        step = script.pop(0) if len(script) > 1 else script[0]
        if isinstance(step, Exception):
            raise step
        if isinstance(step, Sleep):
            await asyncio.sleep(step.seconds)
            return ChatResult("{}")
        text = step(messages) if callable(step) else step
        return ChatResult(text, input_tokens=321, output_tokens=87, reasoning_tokens=64)


def draft_json(template: str) -> str:
    return json.dumps({"text": template})


def passing_template(moment, events, menu=None) -> str:
    """The first one- or two-clause placeholder template the Guard accepts for the moment (primary claims need some)."""
    from app.agents import tools
    from app.agents.guard import guard_check
    from app.explain.menu import build_menu

    menu = menu or build_menu(moment, events)
    ctx = tools.slot_context(moment, events)
    ids = [c.id for c in menu.clauses]
    for template in [f"{{clause:{a}}}." for a in ids] + [f"{{clause:{a}}}, and {{clause:{b}}}." for a in ids for b in ids if a != b]:
        if asyncio.run(guard_check(template, menu, ctx)).ok:
            return template
    raise AssertionError("no passing template")


VERDICT_PASS = json.dumps({"ok": True, "issues": []})


def verdict_reject(span: str, code: str = "role_reversed", reason: str = "roles swapped") -> str:
    return json.dumps({"ok": False, "issues": [{"code": code, "span": span, "reason": reason}]})


def analyst_reply(ids, note="why it matters") -> str:
    return json.dumps({"claim_ids": list(ids), "context_note": note})
