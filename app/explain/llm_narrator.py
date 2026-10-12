"""LLM anlatıcı: Microsoft Foundry üzerinde Narrator protokolü.

İstemci enjekte edilir (`ChatClient` protokolü). Agent Framework'e özgü tek
yer `FoundryChatClientAdapter`'dır; testler sahte istemci kullanır, gerçek ağ
çağrısı yoktur. Model çıktısı JSON şemalı yapılandırılmış çıktıdır (`DraftOut`)
ve pipeline'da yine text_lint + verify_claim'den geçer.

Güvenlik: çağrı başına zaman aşımı, yanıt token üst sınırı, anlatıcı başına
maksimum çağrı sayısı (aşılınca `BudgetExceeded`), her çağrının token
kullanımı `whyball.llm` logger'ına ve `FoundryNarrator.usage`'a yazılır.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.analytics.moments import Moment
from app.generator.models import Event

from .claims import COMPARISONS, METRIC_KINDS, Claim, MatchTime, Subject
from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from .narrator import (
    BudgetExceeded,
    Draft,
    Feedback,
    InvalidNarratorOutput,
    NarratorError,
    NarratorTimeout,
)

PROMPT_VERSION = "foundry-v1"
INSTALL_HINT = "FoundryNarrator için: pip install -e '.[llm]' (agent-framework-foundry, azure-identity)"
logger = logging.getLogger("whyball.llm")


# --- yapılandırılmış çıktı şeması ------------------------------------------------------


class SubjectOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team: Literal["home", "away"] | None = None
    player: str | None = None


class ClaimOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["count", "ratio", "state"]
    subject: SubjectOut
    metric: str
    comparison: Literal["eq", "gte", "lte", "gt", "lt", "approx"]
    value: float
    start: list[int] = Field(min_length=3, max_length=3)  # [period, minute, second]
    end: list[int] = Field(min_length=3, max_length=3)
    event_ids: list[str]


class DraftOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    claims: list[ClaimOut]

    def to_draft(self) -> Draft:
        return Draft(
            self.text,
            tuple(
                Claim(
                    c.kind, Subject(c.subject.team, c.subject.player), c.metric, c.comparison,
                    c.value, MatchTime(*c.start), MatchTime(*c.end), tuple(c.event_ids),
                )
                for c in self.claims
            ),
        )


# --- istemci katmanı --------------------------------------------------------------------


@dataclass(frozen=True)
class ChatResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class ChatClient(Protocol):
    async def complete(
        self, messages: list[dict[str, str]], *, response_model: type[BaseModel], max_tokens: int
    ) -> ChatResult: ...


def _usage_value(usage: Any, name: str) -> int | None:
    if usage is None:
        return None
    value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
    return int(value) if value is not None else None


class FoundryChatClientAdapter:
    """Agent Framework `FoundryChatClient` üzerine ince sarmalayıcı.

    `get_response(messages, options={"max_tokens", "response_format"})` çağrılır;
    token kullanımı `response.usage_details.input_token_count/output_token_count`
    alanlarından okunur. Bu alan adları belgede doğrulanamadı: gerçek sürüme
    karşı bir kez elle doğrulanmalı (eksikse kullanım None olarak loglanır).
    """

    def __init__(
        self,
        client: Any = None,
        *,
        project_endpoint: str | None = None,
        model: str | None = None,
        credential: Any = None,
        message_factory: Callable[[str, str], Any] | None = None,
    ) -> None:
        if client is None:
            try:
                from agent_framework.foundry import FoundryChatClient
            except ImportError as e:
                raise ImportError(INSTALL_HINT) from e
            client = FoundryChatClient(
                project_endpoint=project_endpoint, model=model, credential=credential
            )
        if message_factory is None:
            try:
                from agent_framework import Message
            except ImportError as e:
                raise ImportError(INSTALL_HINT) from e

            def message_factory(role: str, text: str) -> Any:
                return Message(role=role, text=text)

        self._client = client
        self._message = message_factory

    async def complete(
        self, messages: list[dict[str, str]], *, response_model: type[BaseModel], max_tokens: int
    ) -> ChatResult:
        response = await self._client.get_response(
            [self._message(m["role"], m["content"]) for m in messages],
            options={"max_tokens": max_tokens, "response_format": response_model},
        )
        usage = getattr(response, "usage_details", None)
        return ChatResult(
            text=getattr(response, "text", "") or "",
            input_tokens=_usage_value(usage, "input_token_count"),
            output_tokens=_usage_value(usage, "output_token_count"),
        )


# --- prompt -----------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a football match narrator for WhyBall. Every statement you make is \
machine-verified against the event log; anything unverifiable is rejected.

Rules:
- Write {language_name} text, 1-3 short sentences, persona: {persona}.
- Only state facts you back with a claim. Every number and every team or player name in the text \
must appear in one of your claims (value, minute range, or subject).
- Use only team and player names given in the input. Do not invent names.
- Never refer to anything after the moment's time; claim "end" must not be later than the moment.
- event_ids must be taken from "allowed_event_ids" (format "<match_id>#<seq>").
- Claim kinds and metrics: {metrics}. Comparisons: {comparisons}.
- Count claims must list exactly the counted events as event_ids. Ratio and state claims need at \
least one event_id inside their [start, end] range. Times are [period, minute, second].
- Respond only with JSON matching the provided schema: {{"text": str, "claims": [...]}}."""

LANGUAGE_NAMES = {"en": "English", "tr": "Turkish"}


def build_messages(
    moment: Moment,
    events: Sequence[Event],
    persona: str,
    language: str,
    feedback: Feedback | None = None,
) -> list[dict[str, str]]:
    match_id = events[0].match_id
    teams = events[0].data["teams"]
    system = SYSTEM_PROMPT.format(
        language_name=LANGUAGE_NAMES.get(language, language),
        persona=persona,
        metrics=", ".join(f"{m} ({k})" for m, k in METRIC_KINDS.items()),
        comparisons=", ".join(COMPARISONS),
    )
    payload = {
        "match_id": match_id,
        "teams": {side: teams[side]["name"] for side in ("home", "away")},
        "moment": moment.to_dict(),
        "moment_time": [moment.period, moment.minute, moment.second],
        "allowed_event_ids": [f"{match_id}#{seq}" for seq in moment.event_ids],
        "kickoff_time": [1, 0, 0],
    }
    user = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if feedback is not None:
        lines = [f"Previous attempt {feedback.attempt} was rejected. Fix every issue:"]
        for item in feedback.items:
            line = f"- [{item.source}] {item.code}"
            if item.claim_index is not None:
                line += f" claim[{item.claim_index}]"
            if item.fragment:
                line += f" fragment={item.fragment!r}"
            lines.append(line)
        user += "\n\nFEEDBACK\n" + "\n".join(lines)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# --- anlatıcı ----------------------------------------------------------------------------


@dataclass(frozen=True)
class UsageRecord:
    call: int
    moment_id: str
    outcome: str  # ok | timeout | invalid_output | client_error
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


class FoundryNarrator:
    name = "foundry"
    source = "llm"

    def __init__(
        self,
        events: Sequence[Event],
        client: ChatClient,
        *,
        config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
        model_tag: str = "",
    ) -> None:
        self.events = events
        self.client = client
        self.config = config
        self.prompt_version = f"{PROMPT_VERSION}:{model_tag}" if model_tag else PROMPT_VERSION
        self.calls = 0
        self.usage: list[UsageRecord] = []
        # Kalıcı loop: senkron pipeline'dan çağrılır, istemci tek loop'a bağlı kalır.
        self._loop = asyncio.new_event_loop()

    def close(self) -> None:
        if not self._loop.is_closed():
            self._loop.close()

    def _record(self, moment: Moment, outcome: str, started: float, result: ChatResult | None) -> None:
        rec = UsageRecord(
            call=self.calls,
            moment_id=moment.id,
            outcome=outcome,
            input_tokens=result.input_tokens if result else None,
            output_tokens=result.output_tokens if result else None,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        self.usage.append(rec)
        logger.info(
            "llm_call call=%d moment=%s outcome=%s input_tokens=%s output_tokens=%s latency_ms=%d",
            rec.call, rec.moment_id, rec.outcome, rec.input_tokens, rec.output_tokens, rec.latency_ms,
        )

    def narrate(
        self, moment: Moment, persona: str, language: str, feedback: Feedback | None = None
    ) -> Draft:
        cfg = self.config
        if self.calls >= cfg.llm_max_calls_per_run:
            raise BudgetExceeded(
                f"LLM çağrı bütçesi aşıldı: {self.calls}/{cfg.llm_max_calls_per_run}"
            )
        self.calls += 1
        messages = build_messages(moment, self.events, persona, language, feedback)
        started = time.perf_counter()
        call = self.client.complete(messages, response_model=DraftOut, max_tokens=cfg.llm_max_tokens)
        try:
            result = self._loop.run_until_complete(asyncio.wait_for(call, cfg.llm_timeout_s))
        except TimeoutError:
            self._record(moment, "timeout", started, None)
            raise NarratorTimeout(f"LLM {cfg.llm_timeout_s:g} sn içinde yanıt vermedi") from None
        except Exception as e:
            self._record(moment, "client_error", started, None)
            raise NarratorError(f"LLM istemci hatası: {e!r}") from e
        try:
            draft = DraftOut.model_validate_json(result.text).to_draft()
        except ValidationError as e:
            self._record(moment, "invalid_output", started, result)
            first = e.errors()[0]
            raise InvalidNarratorOutput(
                f"Şemaya uymayan yanıt ({e.error_count()} hata): {first['type']} at "
                f"{'.'.join(map(str, first['loc'])) or '<root>'}"
            ) from None
        self._record(moment, "ok", started, result)
        return draft


def foundry_narrator_from_env(
    events: Sequence[Event], config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> FoundryNarrator:
    """FOUNDRY_PROJECT_ENDPOINT ve FOUNDRY_MODEL ortamdan (.env) okunur; sır kodda tutulmaz."""
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    model = os.environ.get("FOUNDRY_MODEL")
    if not endpoint or not model:
        raise ValueError("foundry anlatıcı için FOUNDRY_PROJECT_ENDPOINT ve FOUNDRY_MODEL gerekli")
    try:
        from azure.identity import AzureCliCredential
    except ImportError as e:
        raise ImportError(INSTALL_HINT) from e
    adapter = FoundryChatClientAdapter(
        project_endpoint=endpoint, model=model, credential=AzureCliCredential()
    )
    return FoundryNarrator(events, adapter, config=config, model_tag=model)
