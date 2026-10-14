"""Verifier agent (verifier-v1): checks the MEANING of a draft the Guard already accepted. It can only reject.

The Guard (code) proves numbers, names, events and slots. What it cannot prove is meaning: a value placed on the
wrong team, a role reversed, an event cited for something it is not evidence of, hype no claim supports, a connector
that contradicts the claims (docs/EVAL.md, "Target for the Verifier agent"). The Verifier reads the final sentence,
how each number is tied to a claim, the claims and the evidence events, and returns a closed verdict:

    {ok: bool, issues: [{code, span, reason}]}      code from CODES; ok=true only with no issues

It does NOT see the Narrator's reasoning, earlier drafts or the placeholder template. It returns no text and no number:
a rejection becomes coded Feedback for the Narrator, and the Guard's verdict is never changed by it. If the Verifier fails
(error, timeout, malformed or inconsistent verdict) the card is not blocked: the workflow publishes the Guard-passed
draft labelled "guard-verified only" (design decision D6) and the trace holds `verifier_error`.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.analytics.moments import Moment
from app.explain.claims import Claim, parse_ref
from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.labels import metric_label
from app.explain.llm_narrator import ChatClient, ChatResult
from app.explain.narrator import BudgetExceeded, Feedback, FeedbackItem
from app.explain.phrases import event_phrase
from app.explain.slots import SlotContext, format_value
from app.explain.template_narrator import fmt_minute
from app.generator.models import Event

from .limits import DEFAULT_AGENTS_CONFIG, AgentsConfig, CallBudget
from .state import FeedbackEntry, FeedbackRecord, GuardResult
from .trace import Stopwatch, Tokens, TraceStep

VERIFIER_VERSION = "verifier-v1"
Code = Literal[
    "wrong_slot_binding", "role_reversed", "event_wrong_claim", "qualitative_unsupported",
    "unsupported_statement", "misleading_connector", "other_semantic",
]
CODES: tuple[str, ...] = Code.__args__  # type: ignore[attr-defined]
# The injection classes of eval/inject.py each code answers (the ones the deterministic check misses, plus the
# qualitative ones it only catches as a separate sentence).
EVAL_CLASSES: dict[str, tuple[str, ...]] = {
    "wrong_slot_binding": ("wrong_slot_binding", "player_swap", "score_order_reversed"),
    "role_reversed": ("role_reversed",),
    "event_wrong_claim": ("event_wrong_claim",),
    "qualitative_unsupported": ("qualitative_overstatement", "unsupported_sentence_qualitative"),
    "unsupported_statement": ("unsupported_sentence_number",),
    "misleading_connector": (),
    "other_semantic": (),
}
REASON_MAX_CHARS = 200

VERIFIER_PROMPT = """You are the meaning checker of a football narration team (synthetic data). A writer produced ONE \
short text about a moment. Code has already proved every number, name, minute and event in it: each number was \
rendered from a verified claim. You do NOT re-check numbers. You check whether the text MEANS what the verified \
facts say.

You get: the final text, its pieces (a piece with a claim_id is the value of that claim), the claims it rests on \
(subject, window, value) and the evidence events (type, minute, team, player). Use only these. You see nothing else \
about how the text was written.

Reject ONLY for a real problem, with one issue per problem and a code from this closed list:
- wrong_slot_binding: a value or label is attached to the wrong team, player or wording (for example one team's \
shots written as the other team's).
- role_reversed: a player's role in an event is turned around (the one who conceded is said to have scored, the one \
who was sent off is said to have done something else).
- event_wrong_claim: an event is cited as evidence for something it does not show (a different role or a different \
claim).
- qualitative_unsupported: a judgement or hype ("deserved", "dominant", "stunning", "decisive") that no claim supports.
- unsupported_statement: the text states something that no listed claim or event covers.
- misleading_connector: a connector ("yet", "while", "but", "so", "and") implies a relation the claims contradict \
(for example "yet" where the facts do not conflict).
- other_semantic: any other way the text's meaning differs from the facts.

Rules:
- "span" is the exact words from the text that are wrong (a substring of text). "reason" is one short sentence \
without digits.
- Do not reject for style, length or word choice. Do not suggest a rewrite. Do not write or change any number or text.
- If nothing is wrong answer {{"ok": true, "issues": []}}. "ok": true needs an empty issues list; "ok": false needs at \
least one issue.

Respond only with JSON: {{"ok": <bool>, "issues": [{{"code": "...", "span": "...", "reason": "..."}}]}}."""


class IssueOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Code
    span: str = Field(min_length=1)
    reason: str = Field(max_length=REASON_MAX_CHARS)


class VerifierOut(BaseModel):
    """The Verifier's whole answer. No field for text or numbers: it cannot edit, only reject."""

    model_config = ConfigDict(extra="forbid")
    ok: bool
    issues: list[IssueOut]


class VerdictError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def check_verdict(out: VerifierOut, text: str) -> VerifierOut:
    """Consistency the schema cannot express: ok agrees with the issues, and every span is in the text."""
    if out.ok and out.issues:
        raise VerdictError("ok_with_issues", "ok=true with issues")
    if not out.ok and not out.issues:
        raise VerdictError("reject_without_issue", "ok=false without an issue")
    for issue in out.issues:
        if issue.span not in text:
            raise VerdictError("span_not_in_text", f"span {issue.span[:40]!r} is not in the text")
    return out


# --- the record the Verifier reads -------------------------------------------------------------------------


def _claim_record(cid: str, claim: Claim, ctx: SlotContext) -> dict:
    return {
        "id": cid,
        "metric": metric_label(claim.metric, ctx.language),
        "team": ctx.teams.get(claim.subject.team) if claim.subject.team else None,
        "player": claim.subject.player,
        "value": format_value(claim.metric, claim.value, ctx.language),
        "from": fmt_minute(claim.start.period, claim.start.minute),
        "to": fmt_minute(claim.end.period, claim.end.minute),
        "evidence": list(claim.event_ids),
    }


def verifier_record(moment: Moment, guard: GuardResult, events: Sequence[Event], ctx: SlotContext) -> dict:
    """Final text, pieces, the used claims and their evidence events. Nothing of the Narrator's work."""
    if not guard.ok or guard.text is None:
        raise ValueError("the Verifier reads only drafts the Guard accepted")
    by_seq = {e.seq: e for e in events}
    refs = list(dict.fromkeys(r for c in guard.claims for r in c.event_ids))
    record_events = []
    for ref in refs:
        e = by_seq.get(parse_ref(ref)[1])
        if e is None:
            continue
        record_events.append({
            "id": ref, "type": e.type.value, "minute": fmt_minute(e.period, e.minute),
            "team": ctx.teams.get(e.team) if e.team else None, "player": e.player,
            "phrase": event_phrase(e, ctx.teams, ctx.language),
        })
    return {
        "moment": {"type": moment.type, "team": ctx.teams.get(moment.team) if moment.team else None},
        "teams": {"home": ctx.teams["home"], "away": ctx.teams["away"]},
        "text": guard.text,
        "pieces": [{"text": p.text, "claim_id": None if p.claim is None else guard.claim_ids[p.claim]}
                   for p in guard.parts],
        "claims": [_claim_record(cid, c, ctx) for cid, c in zip(guard.claim_ids, guard.claims)],
        "events": record_events,
    }


# --- the agent ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifyResult:
    verdict: Literal["pass", "reject", "error"]
    feedback: FeedbackRecord | None  # on reject: the issues as coded feedback for the Narrator
    steps: tuple[TraceStep, ...]

    def narrator_feedback(self, attempt: int) -> Feedback | None:
        if self.feedback is None:
            return None
        return Feedback(attempt, tuple(e.to_item() for e in self.feedback.entries))


class VerifierAgent:
    name = "verifier"

    def __init__(
        self,
        events: Sequence[Event],
        client: ChatClient,
        *,
        budget: CallBudget,
        config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
        agents: AgentsConfig = DEFAULT_AGENTS_CONFIG,
        model_tag: str = "",
    ) -> None:
        self.events, self.client, self.budget = events, client, budget
        self.config, self.agents, self.model_tag = config, agents, model_tag

    def messages(self, moment: Moment, guard: GuardResult, ctx: SlotContext) -> list[dict[str, str]]:
        record = verifier_record(moment, guard, self.events, ctx)
        return [
            {"role": "system", "content": VERIFIER_PROMPT},
            {"role": "user", "content": json.dumps(record, ensure_ascii=False, sort_keys=True)},
        ]

    async def verify(
        self, moment: Moment, guard: GuardResult, ctx: SlotContext, *, attempt: int, clock: Stopwatch
    ) -> VerifyResult:
        """One Verifier call. Never raises for a model/client failure: an `error` verdict carries a `verifier_error` step."""
        started = clock.start()
        input_ref = f"drafts[{attempt}]"

        def step(kind: str, status: str, output: dict, result: ChatResult | None = None) -> TraceStep:
            started_ms, duration_ms = clock.span(started)
            tokens = Tokens(result.input_tokens, result.output_tokens, result.reasoning_tokens) if result else None
            return TraceStep.make(kind, "verifier", attempt=attempt, started_ms=started_ms, duration_ms=duration_ms,
                                  input_ref=input_ref, output=output, tokens=tokens, model=self.model_tag or None,
                                  status=status)

        def error(status: str, reason: str, message: str, result: ChatResult | None = None) -> VerifyResult:
            return VerifyResult("error", None, (step("verifier_error", status, {"reason": reason, "message": message[:200]}, result),))

        try:
            self.budget.take()
        except BudgetExceeded as e:
            return error("error", e.code, str(e))
        timeout = self.agents.verifier_timeout_s
        call = self.client.complete(
            self.messages(moment, guard, ctx), response_model=VerifierOut, max_tokens=self.agents.verifier_max_tokens,
            reasoning_effort=self.config.llm_reasoning_effort,
        )
        try:
            result = await asyncio.wait_for(call, timeout)
        except TimeoutError:
            return error("timeout", "timeout", f"no answer within {timeout:g} s")
        except Exception as e:  # noqa: BLE001 - a client failure never blocks the card
            return error("error", "client_error", repr(e))
        try:
            out = VerifierOut.model_validate_json(result.text)
        except ValidationError as e:
            return error("error", "invalid_output", f"{e.error_count()} schema errors: {e.errors()[0]['type']}", result)
        try:
            check_verdict(out, guard.text or "")
        except VerdictError as e:
            return error("error", e.code, str(e), result)
        if out.ok:
            return VerifyResult("pass", None, (step("verify", "ok", {"verdict": "pass", "issues": []}, result),))
        entries = tuple(
            FeedbackEntry("verifier", i.code, f"{i.span} ({i.reason})"[:240]) for i in out.issues
        )
        issues = [{"code": i.code, "span": i.span, "reason": i.reason} for i in out.issues]
        return VerifyResult("reject", FeedbackRecord(attempt, entries), (step("verify", "ok", {"verdict": "reject", "issues": issues}, result),))
