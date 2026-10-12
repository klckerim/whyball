"""LLM anlatıcı: Microsoft Foundry üzerinde Narrator protokolü.

İstemci enjekte edilir (`ChatClient` protokolü). Agent Framework'e özgü tek
yer `FoundryChatClientAdapter`'dır; testler sahte istemci kullanır.

Modele yalnızca moment kaydı verilir (momentin dayanak olayları, o anki
metrikler, kadro). Çıktı her moment için üretilen kapalı bir JSON şemasına
zorlanır: iddia türü, metrik, karşılaştırma ve oyuncu enum'dur; dayanak olay
id'leri yalnızca verilen olaylardan seçilebilir. Taslak pipeline'da yine
text_lint + verify_claim'den geçer.

Güvenlik: çağrı başına zaman aşımı, yanıt token üst sınırı, anlatıcı başına
maksimum çağrı sayısı (aşılınca `BudgetExceeded`), her çağrının token
kullanımı ve süresi `whyball.llm` logger'ına ve `FoundryNarrator.usage`'a yazılır.
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

from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from app.analytics.moments import Moment
from app.generator.models import Event

from .claims import COMPARISONS, KINDS, METRIC_KINDS, Claim, MatchTime, Subject
from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from .narrator import (
    BudgetExceeded,
    Draft,
    Feedback,
    InvalidNarratorOutput,
    NarratorError,
    NarratorTimeout,
)

PROMPT_VERSION = "foundry-v2"
INSTALL_HINT = "FoundryNarrator için: pip install -e '.[llm]' (agent-framework-foundry, azure-identity)"
logger = logging.getLogger("whyball.llm")
SIDES = ("home", "away")


# --- moment kaydı --------------------------------------------------------------------------


def _time(period: int, minute: int, second: int) -> dict[str, int]:
    return {"period": period, "minute": minute, "second": second}


def moment_record(moment: Moment, events: Sequence[Event]) -> dict[str, Any]:
    """Modelin görebileceği tek bilgi: moment, dayanak olayları, o anki metrikler, kadro."""
    match_id = events[0].match_id
    by_seq = {e.seq: e for e in events}
    teams = events[0].data["teams"]
    record_events = []
    for seq in dict.fromkeys(moment.event_ids):
        e = by_seq[seq]
        record_events.append({
            "id": f"{match_id}#{seq}",
            "type": e.type.value,
            "time": _time(e.period, e.minute, e.second),
            "team": e.team,
            "player": e.player,
            "outcome": e.outcome,
            "score_after": e.score,
        })
    return {
        "match_id": match_id,
        "kickoff": _time(1, 0, 0),
        "moment": {
            "id": moment.id,
            "type": moment.type,
            "team": moment.team,
            "time": _time(moment.period, moment.minute, moment.second),
            "detail": moment.detail,
        },
        "metrics_at_moment": moment.metrics,
        "events": record_events,
        "squads": {
            side: {
                "name": teams[side]["name"],
                "lineup": teams[side]["lineup"],
                "bench": teams[side]["bench"],
            }
            for side in SIDES
        },
    }


def _squad_players(events: Sequence[Event]) -> list[str]:
    teams = events[0].data["teams"]
    return [p for side in SIDES for p in (*teams[side]["lineup"], *teams[side]["bench"])]


# --- kapalı çıktı şeması ------------------------------------------------------------------


class TimeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: int
    minute: int
    second: int


def draft_model_for(event_ids: Sequence[str], players: Sequence[str]) -> type[BaseModel]:
    """Bu moment için kapalı şema: event_ids yalnızca verilen olaylardan, oyuncu kadrodan.

    Strict structured output uyumu: tüm alanlar zorunlu (null'lanabilirler `| None`,
    varsayılan yok), ek alan yok, minItems gibi anahtar kelimeler yok.
    """
    forbid = ConfigDict(extra="forbid")
    ref = Literal[tuple(dict.fromkeys(event_ids))]  # type: ignore[valid-type]
    player = Literal[tuple(dict.fromkeys(players))]  # type: ignore[valid-type]
    subject = create_model(
        "SubjectOut", __config__=forbid,
        team=(Literal["home", "away"] | None, ...),
        player=(player | None, ...),
    )
    claim = create_model(
        "ClaimOut", __config__=forbid,
        kind=(Literal[KINDS], ...),  # type: ignore[valid-type]
        subject=(subject, ...),
        metric=(Literal[tuple(METRIC_KINDS)], ...),  # type: ignore[valid-type]
        comparison=(Literal[COMPARISONS], ...),  # type: ignore[valid-type]
        value=(float, ...),
        start=(TimeOut, ...),
        end=(TimeOut, ...),
        event_ids=(list[ref], ...),
    )
    return create_model("DraftOut", __config__=forbid, text=(str, ...), claims=(list[claim], ...))


def parse_draft(model: type[BaseModel], raw: str) -> Draft:
    out: Any = model.model_validate_json(raw)
    return Draft(
        out.text,
        tuple(
            Claim(
                c.kind, Subject(c.subject.team, c.subject.player), c.metric, c.comparison, c.value,
                MatchTime(c.start.period, c.start.minute, c.start.second),
                MatchTime(c.end.period, c.end.minute, c.end.second),
                tuple(c.event_ids),
            )
            for c in out.claims
        ),
    )


# --- istemci katmanı --------------------------------------------------------------------


@dataclass(frozen=True)
class ChatResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None


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

    `get_response(messages, options={"max_tokens", "response_format"})`: Agent Framework
    `max_tokens`'ı Responses `max_output_tokens`'a, Pydantic modelini json_schema
    `text.format`'a çevirir. `usage_details` bir TypedDict'tir (agent-framework-core 1.21):
    `input_token_count`, `output_token_count`, `reasoning_output_token_count`.
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
                return Message(role, [text])  # agent-framework-core 1.21: Message(role, contents)

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
            reasoning_tokens=_usage_value(usage, "reasoning_output_token_count"),
        )


# --- prompt -----------------------------------------------------------------------------

SYSTEM_PROMPT = """You narrate one moment of a synthetic football match for WhyBall. A deterministic \
verifier checks every claim against the full event log; text with any unverifiable claim, number or \
name is rejected and never published.

Use ONLY the moment record in the user message (moment, metrics_at_moment, events, squads). No \
outside knowledge. Do not invent facts, names or numbers.

Write {language_name} text: 1-2 short sentences, persona: {persona}.

Every number and every team or player name in the text must appear in one of your claims: as the \
claim value, as a minute of its start/end, or as its subject. Write numbers as digits, not words.
Write match minutes as 22' (stoppage time: 45+2', 90+3'), never as 22:00; scores as 1-0.

Claims. Times are {{period, minute, second}}; start <= end; end must not be later than the moment \
time.
- count: number of events of that metric for the subject in [start, end]. event_ids must list \
exactly ALL counted events, so only make count claims fully backed by the given events (for example \
the moment's own event with start = end = its time).
- ratio (possession, field_tilt): the subject team's share 0..1 in [start, end]. Use start = kickoff, \
end = moment time and the value from metrics_at_moment; cite at least one given event in the range.
- state: the value at end. score; score_margin (team minus opponent); min_score_margin (worst \
margin from start to end); players_on_pitch; pressure_balance (-1..1 from the subject team's view; \
metrics_at_moment.pressure_balance is from home's view, negate it for away). Use start = kickoff and \
cite at least one given event in the range.
Metrics and their kind: {metrics}.
Comparisons: {comparisons}. Use "eq" for exact integers and "approx" for decimals (tolerance 0.005).
subject.team is "home" or "away"; subject.player is a squad name or null.

Respond only with JSON matching the schema."""

LANGUAGE_NAMES = {"en": "English", "tr": "Turkish"}


def build_messages(
    moment: Moment,
    events: Sequence[Event],
    persona: str,
    language: str,
    feedback: Feedback | None = None,
) -> list[dict[str, str]]:
    system = SYSTEM_PROMPT.format(
        language_name=LANGUAGE_NAMES.get(language, language),
        persona=persona,
        metrics=", ".join(f"{m} ({k})" for m, k in METRIC_KINDS.items()),
        comparisons=", ".join(COMPARISONS),
    )
    user = json.dumps(moment_record(moment, events), ensure_ascii=False, sort_keys=True)
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
    reasoning_tokens: int | None
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
        self.model_tag = model_tag
        self.prompt_version = f"{PROMPT_VERSION}:{model_tag}" if model_tag else PROMPT_VERSION
        self.calls = 0
        self.usage: list[UsageRecord] = []
        self._players = _squad_players(events)
        # Kalıcı loop: senkron pipeline'dan çağrılır, istemci tek loop'a bağlı kalır.
        self._loop = asyncio.new_event_loop()

    def close(self) -> None:
        if not self._loop.is_closed():
            self._loop.close()

    def response_model(self, moment: Moment) -> type[BaseModel]:
        match_id = self.events[0].match_id
        return draft_model_for([f"{match_id}#{s}" for s in moment.event_ids], self._players)

    def _record(self, moment: Moment, outcome: str, started: float, result: ChatResult | None) -> None:
        rec = UsageRecord(
            call=self.calls,
            moment_id=moment.id,
            outcome=outcome,
            input_tokens=result.input_tokens if result else None,
            output_tokens=result.output_tokens if result else None,
            reasoning_tokens=result.reasoning_tokens if result else None,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        self.usage.append(rec)
        logger.info(
            "llm_call call=%d moment=%s outcome=%s input_tokens=%s output_tokens=%s "
            "reasoning_tokens=%s latency_ms=%d",
            rec.call, rec.moment_id, rec.outcome, rec.input_tokens, rec.output_tokens,
            rec.reasoning_tokens, rec.latency_ms,
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
        model = self.response_model(moment)
        messages = build_messages(moment, self.events, persona, language, feedback)
        started = time.perf_counter()
        call = self.client.complete(messages, response_model=model, max_tokens=cfg.llm_max_tokens)
        try:
            result = self._loop.run_until_complete(asyncio.wait_for(call, cfg.llm_timeout_s))
        except TimeoutError:
            self._record(moment, "timeout", started, None)
            raise NarratorTimeout(f"LLM {cfg.llm_timeout_s:g} sn içinde yanıt vermedi") from None
        except Exception as e:
            self._record(moment, "client_error", started, None)
            raise NarratorError(f"LLM istemci hatası: {e!r}") from e
        try:
            draft = parse_draft(model, result.text)
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
    """FOUNDRY_PROJECT_ENDPOINT ve FOUNDRY_MODEL ortamdan ya da .env'den; sır kodda tutulmaz."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        load_dotenv()
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
