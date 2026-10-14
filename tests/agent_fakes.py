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
