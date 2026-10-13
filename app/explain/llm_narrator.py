"""LLM anlatıcı: Microsoft Foundry üzerinde Narrator protokolü.

İstemci enjekte edilir (`ChatClient` protokolü). Agent Framework'e özgü tek
yer `FoundryChatClientAdapter`'dır; testler sahte istemci kullanır.

Modele yalnızca moment kaydı verilir (momentin dayanak olayları, o anki
metrikler, kadro). Model somut değer yazmaz: metin yer tutuculu bir şablondur
(bkz. slots.py), gerçek değerleri pipeline doğrulanmış iddialardan render eder.
Çıktı her moment için üretilen kapalı bir JSON şemasına zorlanır: iddia türü,
metrik, karşılaştırma ve oyuncu id'si enum'dur; dayanak olay id'leri yalnızca
verilen olaylardan seçilebilir.

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
from .labels import METRIC_LABELS
from .phrases import event_phrase, selectable
from .slots import player_ids

PROMPT_VERSION = "foundry-v4.1"
INSTALL_HINT = "FoundryNarrator için: pip install -e '.[llm]' (agent-framework-foundry, azure-identity)"
logger = logging.getLogger("whyball.llm")
SIDES = ("home", "away")


# --- moment kaydı --------------------------------------------------------------------------


def _time(period: int, minute: int, second: int) -> dict[str, int]:
    return {"period": period, "minute": minute, "second": second}


def moment_record(moment: Moment, events: Sequence[Event], language: str = "en") -> dict[str, Any]:
    """Modelin görebileceği tek bilgi: moment, dayanak olayları, o anki metrikler, kadro."""
    match_id = events[0].match_id
    by_seq = {e.seq: e for e in events}
    ids = player_ids(events)
    id_of = {name: pid for pid, name in ids.items()}
    teams = {side: events[0].data["teams"][side]["name"] for side in SIDES}
    record_events = []
    for seq in dict.fromkeys(moment.event_ids):
        e = by_seq[seq]
        record_events.append({
            "id": f"{match_id}#{seq}",
            "type": e.type.value,
            "time": _time(e.period, e.minute, e.second),
            "team": e.team,
            "player": id_of.get(e.player) if e.player else None,
            "outcome": e.outcome,
            "score_after": e.score,
            "phrase": event_phrase(e, teams, language),  # {event:<id>} bu metne render edilir
            "selectable": selectable(e, moment.type),  # {event:} yalnızca bu olaylar için
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
            side: [{"id": pid, "name": name} for pid, name in ids.items() if pid[0] == side[0]]
            for side in SIDES
        },
        "metric_labels": METRIC_LABELS.get(language, METRIC_LABELS["en"]),
    }


# --- kapalı çıktı şeması ------------------------------------------------------------------


class TimeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: int
    minute: int
    second: int


def draft_model_for(event_ids: Sequence[str], players: Sequence[str]) -> type[BaseModel]:
    """Bu moment için kapalı şema: event_ids yalnızca verilen olaylardan, oyuncu kadro id'lerinden.

    `text` yer tutuculu şablondur; her iddianın şablonda başvurulan bir `id`'si vardır.

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
        id=(str, ...),
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


def parse_draft(model: type[BaseModel], raw: str, players: dict[str, str]) -> Draft:
    """Model çıktısı → slot taslağı. Oyuncu id'leri doğrulayıcı için ada çevrilir."""
    out: Any = model.model_validate_json(raw)
    claims = tuple(
        Claim(
            c.kind,
            Subject(c.subject.team, players[c.subject.player] if c.subject.player else None),
            c.metric, c.comparison, c.value,
            MatchTime(c.start.period, c.start.minute, c.start.second),
            MatchTime(c.end.period, c.end.minute, c.end.second),
            tuple(c.event_ids),
        )
        for c in out.claims
    )
    return Draft(out.text, claims, template=out.text, claim_ids=tuple(c.id for c in out.claims))


# --- istemci katmanı --------------------------------------------------------------------


@dataclass(frozen=True)
class ChatResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None


class ChatClient(Protocol):
    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        response_model: type[BaseModel],
        max_tokens: int,
        reasoning_effort: str | None = None,
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
    `text.format`'a çevirir; `reasoning={"effort": ...}` (`OpenAIChatOptions.reasoning`,
    Foundry'de `FoundryChatOptions = OpenAIChatOptions`) akıl yürütme çabasını ayarlar. `usage_details` bir TypedDict'tir (agent-framework-core 1.21):
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
        self,
        messages: list[dict[str, str]],
        *,
        response_model: type[BaseModel],
        max_tokens: int,
        reasoning_effort: str | None = None,
    ) -> ChatResult:
        options: dict[str, Any] = {"max_tokens": max_tokens, "response_format": response_model}
        if reasoning_effort:
            options["reasoning"] = {"effort": reasoning_effort}
        response = await self._client.get_response(
            [self._message(m["role"], m["content"]) for m in messages], options=options
        )
        usage = getattr(response, "usage_details", None)
        return ChatResult(
            text=getattr(response, "text", "") or "",
            input_tokens=_usage_value(usage, "input_token_count"),
            output_tokens=_usage_value(usage, "output_token_count"),
            reasoning_tokens=_usage_value(usage, "reasoning_output_token_count"),
        )


# --- prompt -----------------------------------------------------------------------------

SYSTEM_PROMPT = """You narrate one moment of a synthetic football match for WhyBall. You write a \
TEMPLATE with placeholders plus CLAIMS. Code fills every concrete value from verified claims and the \
match data; a deterministic verifier rejects anything unverifiable.

Use ONLY the moment record in the user message (moment, metrics_at_moment, events, squads, \
metric_labels). No outside knowledge. Do not invent facts.

Write {language_name}: 1-2 short, natural sentences, persona: {persona}.

Events come ONLY from {{event:<event id>}}: code renders the event's standard phrase, shown in \
events[].phrase (e.g. "Murek Brestani was sent off at 38'"). You write only connecting words and plain \
comments around placeholders. NEVER name an event type or a player's role yourself: no words such as \
{event_words}. Metric names come from {{label:<claim_id>}}.

NEVER write digits, number words (not even "{one_word}"), team names, player names, minutes, scores, \
the words "home"/"away" (or "ev sahibi"/"deplasman"), or metric identifiers such as field_tilt. \
Use placeholders:
- {{event:<event id>}}: an event's phrase; copy the id exactly from events[].id. Only events with \
"selectable": true may be used (passes, dribbles, offsides, fouls, corners never), and the event must be \
in the event_ids of one of your claims.
- {{home}}, {{away}}: team names. Always name a team with these placeholders: never refer to a team with a \
pronoun ("they", "their", "them") and never put an article before it (not "the {{home}}").
- {{score}}: the score at this moment as digits in home-away order, e.g. "1–0" (no team names).
- {{score_named}}: the same score with both team names, e.g. "Brannoch FC 1–0 Morvane Athletic". It \
already names both teams, so never attach a team placeholder to it.
- {{player:<id>}}: a player by squad id (e.g. h07), rendered as the full name; that player must be the \
subject of one of your claims. An {{event:}} phrase already names its player: never add that player's \
{{player:}} in the same sentence (no "{{event:...}} by {{player:...}}").
- {{minute:<claim_id>}}: the end minute of a claim; {{start:<claim_id>}}: its start minute.
- {{value:<claim_id>}}: the verified value of a claim (code formats percentages and signs).
- {{label:<claim_id>}}: the readable name of a claim's metric (see metric_labels).
{sentence_rule}
Stay factual: no hype or judgement such as {overstatement}. Exception: "dominate" only for a \
dominance_without_reward moment, "take control"/"momentum" only for a pressure_shift moment.

Examples:
- "{{event:<goal event id>}}, making it {{score}}." with claim c1 = count goals, subject = the scorer's \
team and squad id, start = end = the goal's time, event_ids = [the goal event].
- "{{home}} have had {{value:c2}} of the ball since kickoff." with claim c2 = ratio possession, subject \
home, start = kickoff, end = moment time, value from metrics_at_moment.

Claims. Each claim has a unique short id (c1, c2, ...). Times are {{period, minute, second}}; \
start <= end; end must not be later than the moment time.
- count: number of events of that metric for the subject in [start, end]. event_ids must list \
exactly ALL counted events, so only make count claims fully backed by the given events.
- ratio (possession, field_tilt): the subject team's share 0..1 in [start, end]. Use start = kickoff, \
end = moment time and the value from metrics_at_moment; cite at least one given event in the range.
- state: the value at end. score; score_margin (team minus opponent); min_score_margin (worst \
margin from start to end); players_on_pitch; pressure_balance (-1..1 from the subject team's view; \
metrics_at_moment.pressure_balance is from home's view, negate it for away). Use start = kickoff and \
cite at least one given event in the range.
Metrics and their kind: {metrics}.
Comparisons: {comparisons}. Use "eq" for exact integers and "approx" for decimals (tolerance 0.005).
subject.team is "home" or "away"; subject.player is a squad id or null.

Respond only with JSON matching the schema."""

# Prompt'taki okunur listeler; denetimin kendisi phrases.py sözlükleriyle yapılır.
EVENT_WORD_EXAMPLES = {
    "en": "goal, scored, shot, saved, penalty, missed, sent off, card, booked, foul, corner, offside, "
          "substitute, equalised, levelled, conceded, assist, header, keeper",
    "tr": "gol, şut, penaltı, kurtardı, kaçırdı, kart, atıldı, faul, korner, ofsayt, eşitledi, kaleci, "
          "asist, vuruş",
}
OVERSTATEMENT_EXAMPLES = {
    "en": '"deep into stoppage", "dominate", "take control", "stunning", "dramatic", "relentless", '
          '"against the run of play", "last-gasp", "winner", "decisive", "completely", "comfortably", "deserved"',
    "tr": '"domine etti", "ezici", "kontrolü ele aldı", "muhteşem", "inanılmaz", "dramatik", "son nefeste", '
          '"galibiyet golü", "kritik", "tamamen", "rahat", "hak etti"',
}
ONE_WORD = {"en": "one", "tr": "bir"}
FEEDBACK_HINTS = {
    "event_word": "describe events only with {event:<id>} and metric names with {label:<claim_id>}",
    "event_not_evidence": "an {event:} must be one of the event_ids of your claims",
    "unsupported_event": "this event type has no phrase; cite a different event",
    "sentence_start": "start every sentence with a placeholder or an allowed word",
    "overstatement": "remove the hype/judgement wording",
    "raw_number": "use placeholders instead of digits or number words",
    "event_type_not_allowed": "use {event:} only for events with \"selectable\": true",
    "player_repeat": "the {event:} phrase already names this player; remove the {player:} from that sentence",
    "article_team": "write {home}/{away} without \"the\"",
}


def sentence_rule(language: str, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG) -> str:
    words = config.sentence_start_allowed_tr if language == "tr" else config.sentence_start_allowed_en
    if not words:
        return "Every sentence must start with a placeholder."
    return "Every sentence must start with a placeholder or one of: " + ", ".join(
        f'"{w}"' for w in words
    ) + "."


LANGUAGE_NAMES = {"en": "English", "tr": "Turkish"}


def build_messages(
    moment: Moment,
    events: Sequence[Event],
    persona: str,
    language: str,
    feedback: Feedback | None = None,
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
) -> list[dict[str, str]]:
    lang = language if language in EVENT_WORD_EXAMPLES else "en"
    system = SYSTEM_PROMPT.format(
        language_name=LANGUAGE_NAMES.get(language, language),
        persona=persona,
        event_words=EVENT_WORD_EXAMPLES[lang],
        one_word=ONE_WORD[lang],
        sentence_rule=sentence_rule(lang, config),
        overstatement=OVERSTATEMENT_EXAMPLES[lang],
        metrics=", ".join(f"{m} ({k})" for m, k in METRIC_KINDS.items()),
        comparisons=", ".join(COMPARISONS),
    )
    user = json.dumps(moment_record(moment, events, language), ensure_ascii=False, sort_keys=True)
    if feedback is not None:
        lines = [f"Previous attempt {feedback.attempt} was rejected. Fix every issue:"]
        for item in feedback.items:
            line = f"- [{item.source}] {item.code}"
            if item.claim_index is not None:
                line += f" claim[{item.claim_index}]"
            if item.fragment:
                line += f" fragment={item.fragment!r}"
            if item.code in FEEDBACK_HINTS:
                line += f" ({FEEDBACK_HINTS[item.code]})"
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
    error: str | None = None  # hata mesajı (istemci, zaman aşımı, şema)


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
        self._players = player_ids(events)  # id → ad
        # Kalıcı loop: senkron pipeline'dan çağrılır, istemci tek loop'a bağlı kalır.
        self._loop = asyncio.new_event_loop()

    def close(self) -> None:
        if not self._loop.is_closed():
            self._loop.close()

    def response_model(self, moment: Moment) -> type[BaseModel]:
        match_id = self.events[0].match_id
        return draft_model_for([f"{match_id}#{s}" for s in moment.event_ids], list(self._players))

    def _record(
        self, moment: Moment, outcome: str, started: float, result: ChatResult | None,
        error: str | None = None,
    ) -> None:
        rec = UsageRecord(
            call=self.calls,
            moment_id=moment.id,
            outcome=outcome,
            input_tokens=result.input_tokens if result else None,
            output_tokens=result.output_tokens if result else None,
            reasoning_tokens=result.reasoning_tokens if result else None,
            latency_ms=round((time.perf_counter() - started) * 1000),
            error=error,
        )
        self.usage.append(rec)
        logger.info(
            "llm_call call=%d moment=%s outcome=%s input_tokens=%s output_tokens=%s "
            "reasoning_tokens=%s latency_ms=%d%s",
            rec.call, rec.moment_id, rec.outcome, rec.input_tokens, rec.output_tokens,
            rec.reasoning_tokens, rec.latency_ms, f" error={error!r}" if error else "",
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
        messages = build_messages(moment, self.events, persona, language, feedback, cfg)
        started = time.perf_counter()
        call = self.client.complete(
            messages, response_model=model, max_tokens=cfg.llm_max_tokens,
            reasoning_effort=cfg.llm_reasoning_effort,
        )
        try:
            result = self._loop.run_until_complete(asyncio.wait_for(call, cfg.llm_timeout_s))
        except TimeoutError:
            message = f"LLM {cfg.llm_timeout_s:g} sn içinde yanıt vermedi"
            self._record(moment, "timeout", started, None, message)
            raise NarratorTimeout(message) from None
        except Exception as e:
            message = f"LLM istemci hatası: {e!r}"
            self._record(moment, "client_error", started, None, message)
            raise NarratorError(message) from e
        try:
            draft = parse_draft(model, result.text, self._players)
        except ValidationError as e:
            first = e.errors()[0]
            message = (
                f"Şemaya uymayan yanıt ({e.error_count()} hata): {first['type']} at "
                f"{'.'.join(map(str, first['loc'])) or '<root>'}"
            )
            self._record(moment, "invalid_output", started, result, message)
            raise InvalidNarratorOutput(message) from None
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
