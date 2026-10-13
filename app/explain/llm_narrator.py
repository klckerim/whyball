"""LLM anlatıcı: Microsoft Foundry üzerinde Narrator protokolü.

İstemci enjekte edilir (`ChatClient` protokolü). Agent Framework'e özgü tek
yer `FoundryChatClientAdapter`'dır; testler sahte istemci kullanır.

foundry-v5 (claim menüsü, bkz. menu.py): iddiaları kod kurar ve doğrular. Modele
moment, doğrulanmış iddia menüsü (değer, etiket, aralık, tam kanıt listesi), kodun yazdığı
yan cümleler, kanıt olayları ve kadro verilir. Model iddia kurmaz ve olay bağlamaz:
çıktısı yalnızca yer tutuculu bir metindir (`{"text": ...}`), menü id'lerini kullanır.
Somut değerleri pipeline menüden render eder.

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
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from app.analytics.moments import Moment
from app.generator.models import Event

from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from .narrator import (
    BudgetExceeded,
    Draft,
    Feedback,
    InvalidNarratorOutput,
    NarratorError,
    NarratorTimeout,
)
from .menu import ClaimMenu, build_menu, evidence_events, menu_record
from .phrases import event_phrase, selectable
from .slots import SlotContext, player_ids
from .template_narrator import fmt_minute

PROMPT_VERSION = "foundry-v5"
INSTALL_HINT = "FoundryNarrator için: pip install -e '.[llm]' (agent-framework-foundry, azure-identity)"
logger = logging.getLogger("whyball.llm")
SIDES = ("home", "away")


# --- moment kaydı --------------------------------------------------------------------------


def _time(period: int, minute: int, second: int) -> dict[str, int]:
    return {"period": period, "minute": minute, "second": second}


def moment_record(
    moment: Moment, events: Sequence[Event], language: str = "en", menu: ClaimMenu | None = None
) -> dict[str, Any]:
    """Modelin görebileceği tek bilgi: moment, claim menüsü, yan cümleler, kanıt olayları, kadro."""
    menu = menu or build_menu(moment, events)
    ctx = SlotContext.from_moment(moment, events, language)
    match_id = events[0].match_id
    ids = player_ids(events)
    id_of = {name: pid for pid, name in ids.items()}
    record_events = [
        {
            "id": f"{match_id}#{e.seq}",
            "type": e.type.value,
            "minute": fmt_minute(e.period, e.minute),
            "team": e.team,
            "player": id_of.get(e.player) if e.player else None,
            "phrase": event_phrase(e, ctx.teams, language),  # {event:<id>} bu metne render edilir
            "selectable": selectable(e, moment.type),  # {event:} yalnızca bu olaylar için
        }
        for e in evidence_events(menu, events)
    ]
    return {
        "match_id": match_id,
        "moment": {
            "id": moment.id,
            "type": moment.type,
            "team": moment.team,
            "time": _time(moment.period, moment.minute, moment.second),
            "detail": moment.detail,
        },
        **menu_record(menu, ctx),
        "events": record_events,
        "squads": {
            side: [{"id": pid, "name": name} for pid, name in ids.items() if pid[0] == side[0]]
            for side in SIDES
        },
    }


# --- kapalı çıktı şeması ------------------------------------------------------------------


class MenuDraftOut(BaseModel):
    """Model yalnızca yer tutuculu metni döndürür; iddia ve olay bağlama alanı yok."""

    model_config = ConfigDict(extra="forbid")
    text: str


def parse_draft(raw: str, menu: ClaimMenu) -> Draft:
    """Model çıktısı → menü taslağı (iddialar menüden bağlanır)."""
    out = MenuDraftOut.model_validate_json(raw)
    return Draft(out.text, (), template=out.text, menu=menu)


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

SYSTEM_PROMPT = """You narrate one moment of a synthetic football match for WhyBall. Code has already \
built and verified every fact you may use: the claims_menu. You write a short TEMPLATE with placeholders \
that only refers to menu ids; code fills every concrete value. A deterministic checker rejects anything else.

Use ONLY the moment record in the user message (moment, claims_menu, clauses, events, squads). No outside \
knowledge. Do not invent facts. You do not create claims and you do not link events to claims.

Write {language_name}: 1-2 short, natural sentences, persona: {persona}.

Building blocks (prefer clauses):
- {{clause:<clause id>}}: a ready, verified natural-language clause from clauses[] (clauses[].text shows \
how it renders). Use clauses as they are or join two with a connector ("and", "while", "but"). Do not \
rewrite their numbers. A clause already starts with its own subject ("the score is …", a team name): \
never put "The"/"the" in front of {{clause:}}.
- {{value:<claim id>}}, {{minute:<claim id>}} (end minute), {{start:<claim id>}} (start minute), \
{{label:<claim id>}} (metric name): only ids from claims_menu[].id. Never list labels as "X for Y is N"; \
a clause reads better.
- {{event:<event id>}}: an event's standard phrase (events[].phrase); only events with "selectable": true.
- {{score}} ("1–0", home first) and {{score_named}} ("Brannoch FC 1–0 Morvane Athletic").
- {{home}}, {{away}}: team names; {{player:<squad id>}} only for a player who is the subject of a menu claim.

Rules:
- Every sentence must use at least one menu fact: a clause, value, minute, start, event or score.
- {primary_rule}
- The same minute must not appear twice in one sentence (an {{event:}} phrase and a clause may already \
contain a minute).
- An {{event:}} phrase already names its player: never add that player's {{player:}} in the same sentence.
- NEVER write digits, number words (not even "{one_word}"), team names, player names, minutes, scores, \
the words "home"/"away" (or "ev sahibi"/"deplasman"), metric identifiers, or event words such as \
{event_words}.
- Name teams only with {{home}}/{{away}}: no pronouns ("they", "their", "them"), no article ("the {{home}}").
- {sentence_rule}
- Stay factual: no hype or judgement such as {overstatement}. Exception: "dominate" only for a \
dominance_without_reward moment, "take control"/"momentum" only for a pressure_shift moment.

Examples: "{{event:<goal event id>}}, and {{clause:possession}}." · "{{clause:pressure}}, and \
{{clause:shots}}." · "{{clause:dominance}}, yet {{clause:score}}."

Respond only with JSON: {{"text": "<template>"}}."""

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
    "event_not_evidence": "an {event:} must be in the evidence of a claims_menu entry (see events[])",
    "unsupported_event": "this event type has no phrase; cite a different event",
    "sentence_start": "start every sentence with a placeholder or an allowed word",
    "overstatement": "remove the hype/judgement wording",
    "raw_number": "use placeholders instead of digits or number words",
    "event_type_not_allowed": "use {event:} only for events with \"selectable\": true",
    "player_repeat": "the {event:} phrase already names this player; remove the {player:} from that sentence",
    "article_team": "write {home}/{away} without \"the\"",
    "unknown_claim_id": "use only ids from claims_menu[].id ({value:}/{minute:}/{start:}/{label:}) or clauses[].id ({clause:})",
    "sentence_without_claim": "every sentence needs a menu fact: a {clause:}, {value:}, {minute:}, {event:} or {score}",
    "missing_primary_claim": "use the primary claims of this moment (claims_menu[].primary = true), e.g. via their clause",
    "minute_repeat": "the same minute appears twice in one sentence; drop one of them",
}

PRIMARY_RULE = {
    "dominance_without_reward": "This moment's primary claims (claims_menu[].primary = true): possession AND "
                                "the shot balance must both be used; {clause:dominance} contains both.",
    "pressure_shift": "This moment's primary claim (claims_menu[].primary = true): the pressure balance must be "
                      "used (e.g. {clause:pressure}).",
}
DEFAULT_PRIMARY_RULE = "Use the claim that describes the moment itself (its event or main clause)."


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
    menu: ClaimMenu | None = None,
) -> list[dict[str, str]]:
    lang = language if language in EVENT_WORD_EXAMPLES else "en"
    system = SYSTEM_PROMPT.format(
        language_name=LANGUAGE_NAMES.get(language, language),
        persona=persona,
        event_words=EVENT_WORD_EXAMPLES[lang],
        one_word=ONE_WORD[lang],
        sentence_rule=sentence_rule(lang, config),
        overstatement=OVERSTATEMENT_EXAMPLES[lang],
        primary_rule=PRIMARY_RULE.get(moment.type, DEFAULT_PRIMARY_RULE),
    )
    record = moment_record(moment, events, language, menu)
    user = json.dumps(record, ensure_ascii=False, sort_keys=True)
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
        self._menus: dict[str, ClaimMenu] = {}
        # Kalıcı loop: senkron pipeline'dan çağrılır, istemci tek loop'a bağlı kalır.
        self._loop = asyncio.new_event_loop()

    def close(self) -> None:
        if not self._loop.is_closed():
            self._loop.close()

    def menu(self, moment: Moment) -> ClaimMenu:
        if moment.id not in self._menus:
            self._menus[moment.id] = build_menu(moment, self.events, self.config)
        return self._menus[moment.id]

    def response_model(self, moment: Moment) -> type[BaseModel]:
        return MenuDraftOut

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
        menu = self.menu(moment)
        messages = build_messages(moment, self.events, persona, language, feedback, cfg, menu)
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
            draft = parse_draft(result.text, menu)
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
