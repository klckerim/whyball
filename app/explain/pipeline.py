"""Narration pipeline: moment → narrator → text_lint + verify_claim → (retry with
feedback) → accept, or the labelled template fallback.

CLAUDE.md: an unverified sentence is never published; at most `max_retries` retries,
then the template fallback.

Measurement mode: `on_attempt` hands every attempt (draft, rejection codes, verify results) to
the caller. This record stays with the caller only; rejected drafts are never written to
`NarrationRecord` (trace included) or to the cache.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from typing import Any

from app.analytics import detect_moments
from app.analytics.moments import Moment
from app.generator.models import Event

from .cache import NarrationCache, cache_key
from .claims import Claim, VerificationResult, verify_claim
from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from .menu import ClaimMenu, bind_menu
from .narrator import Draft, Feedback, FeedbackItem, Narrator, NarratorError
from .selector import select_moments
from .slots import SlotContext, bind_template, lint_template, render_parts
from .template_narrator import Part
from .template_narrator import join_sentences
from .template_narrator import narrate as template_narrate
from .template_narrator import require_language
from .text_lint import LintIssue, Roster, lint_text


@dataclass(frozen=True)
class NarrationRecord:
    moment_id: str
    moment_type: str
    persona: str
    language: str
    text: str
    claims: tuple[Claim, ...]
    verification: tuple[VerificationResult, ...]
    lint_issues: tuple[LintIssue, ...]
    attempts: int  # number of narrator calls
    source: str  # "llm" | "template" | "template_fallback"
    cache_hit: bool
    cache_key: str | None
    trace: tuple[dict[str, Any], ...]
    template: str | None = None  # pre-render template of a slot-based draft
    # `text` in pieces; a piece with a claim index states that claim's value. Empty: not recorded.
    parts: tuple[Part, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.lint_issues and all(r.ok for r in self.verification)

    def to_dict(self) -> dict[str, Any]:
        return {
            "moment_id": self.moment_id,
            "moment_type": self.moment_type,
            "persona": self.persona,
            "language": self.language,
            "text": self.text,
            "claims": [c.to_dict() for c in self.claims],
            "verification": [asdict(r) for r in self.verification],
            "lint_issues": [i.to_dict() for i in self.lint_issues],
            "attempts": self.attempts,
            "source": self.source,
            "cache_hit": self.cache_hit,
            "cache_key": self.cache_key,
            "trace": list(self.trace),
            "template": self.template,
            "parts": [[p.text, p.claim] for p in self.parts],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NarrationRecord:
        return cls(
            moment_id=d["moment_id"],
            moment_type=d["moment_type"],
            persona=d["persona"],
            language=d["language"],
            text=d["text"],
            claims=tuple(Claim.from_dict(c) for c in d["claims"]),
            verification=tuple(VerificationResult(**r) for r in d["verification"]),
            lint_issues=tuple(LintIssue(**i) for i in d["lint_issues"]),
            attempts=d["attempts"],
            source=d["source"],
            cache_hit=d["cache_hit"],
            cache_key=d["cache_key"],
            trace=tuple(d["trace"]),
            template=d.get("template"),
            parts=tuple(Part(t, c) for t, c in d.get("parts", [])),
        )


@dataclass(frozen=True)
class AttemptLog:
    """One narrator attempt (measurement mode). Empty `items` means the attempt was accepted."""

    moment: Moment
    attempt: int
    draft: Draft | None  # None on a narrator error
    error: NarratorError | None
    items: tuple[FeedbackItem, ...]
    lint_issues: tuple[LintIssue, ...]
    verification: tuple[VerificationResult, ...]
    claims: tuple[Claim, ...]  # bound claims (automatic score claims included)
    claim_ids: tuple[str, ...]

    @property
    def accepted(self) -> bool:
        return self.error is None and not self.items


AttemptHook = Callable[[AttemptLog], None]


def check_draft(
    text: str,
    claims: Sequence[Claim],
    events: Sequence[Event],
    roster: Roster,
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
    language: str | None = None,
) -> tuple[list[FeedbackItem], tuple[LintIssue, ...], tuple[VerificationResult, ...]]:
    """Whether a draft can be published: empty list = green. (feedback items, lint, verify)"""
    items: list[FeedbackItem] = []
    if not text.strip():
        items.append(FeedbackItem("draft", "empty_text"))
    if not claims:
        items.append(FeedbackItem("draft", "no_claims"))
    lint = lint_text(text, claims, roster, config, language)
    items += [FeedbackItem("lint", i.code, fragment=i.fragment) for i in lint.issues]
    results = tuple(verify_claim(c, events, config) for c in claims)
    items += [
        FeedbackItem("verify", r.reason, claim_index=i) for i, r in enumerate(results) if not r.ok
    ]
    return items, lint.issues, results


def check_slot_draft(
    template: str,
    claims: Sequence[Claim],
    claim_ids: Sequence[str],
    ctx: SlotContext,
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
) -> tuple[
    list[FeedbackItem], tuple[LintIssue, ...], tuple[VerificationResult, ...],
    tuple[Claim, ...], tuple[str, ...],
]:
    """Slot draft: template lint + placeholder binding + verify (automatic score claims included)."""
    items: list[FeedbackItem] = []
    if not template.strip():
        items.append(FeedbackItem("draft", "empty_text"))
    if not claims:
        items.append(FeedbackItem("draft", "no_claims"))
    bound_claims, bound_ids, bind_issues = bind_template(template, claims, claim_ids, ctx)
    issues = tuple(sorted(
        (*lint_template(template, ctx, config).issues, *bind_issues), key=lambda i: (i.start, i.code)
    ))
    items += [FeedbackItem("lint", i.code, fragment=i.fragment) for i in issues]
    results = tuple(verify_claim(c, ctx.events, config) for c in bound_claims)
    items += [
        FeedbackItem("verify", r.reason, claim_index=i) for i, r in enumerate(results) if not r.ok
    ]
    return items, issues, results, bound_claims, bound_ids


def check_menu_draft(
    template: str,
    menu: ClaimMenu,
    ctx: SlotContext,
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
) -> tuple[
    list[FeedbackItem], tuple[LintIssue, ...], tuple[VerificationResult, ...],
    tuple[Claim, ...], tuple[str, ...],
]:
    """Menu draft: template lint + menu binding + v5 rules + verify (menu claims are already verified)."""
    items: list[FeedbackItem] = []
    if not template.strip():
        items.append(FeedbackItem("draft", "empty_text"))
    bound_claims, bound_ids, bind_issues = bind_menu(template, menu, ctx, config)
    if template.strip() and not bound_claims:
        items.append(FeedbackItem("draft", "no_claims"))
    issues = tuple(sorted(
        (*lint_template(template, ctx, config).issues, *bind_issues), key=lambda i: (i.start, i.code)
    ))
    items += [FeedbackItem("lint", i.code, fragment=i.fragment) for i in issues]
    results = tuple(verify_claim(c, ctx.events, config) for c in bound_claims)
    items += [
        FeedbackItem("verify", r.reason, claim_index=i) for i, r in enumerate(results) if not r.ok
    ]
    return items, issues, results, bound_claims, bound_ids


def run_moment(
    moment: Moment,
    narrator: Narrator,
    events: Sequence[Event],
    *,
    persona: str | None = None,
    language: str = "en",
    cache: NarrationCache | None = None,
    prompt_version: str | None = None,
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
    on_attempt: AttemptHook | None = None,
) -> NarrationRecord:
    require_language(language)
    persona = persona or config.default_persona
    version = prompt_version or narrator.prompt_version
    roster = Roster.from_events(events)
    trace: list[dict[str, Any]] = []

    def record(**fields: Any) -> NarrationRecord:
        return NarrationRecord(
            moment_id=moment.id, moment_type=moment.type, persona=persona, language=language,
            cache_hit=False, cache_key=key, trace=tuple(trace), **fields,
        )

    key = None
    if cache is not None:
        key = cache_key(moment, persona, language, version)
        stored = cache.get(key)
        cached = None
        if stored is not None:
            try:
                cached = NarrationRecord.from_dict(stored)
            except (KeyError, TypeError, ValueError):
                cached = None  # corrupt entry: miss
        trace.append({"attempt": 0, "step": "cache", "ok": cached is not None,
                      "hit": cached is not None, "key": key})
        if cached is not None:
            return replace(cached, cache_hit=True, cache_key=key, trace=tuple(trace))

    max_attempts = 1 + config.max_retries
    feedback: Feedback | None = None
    fallback_reason = "max_retries_exceeded"
    attempts = 0
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        feedback_codes = list(feedback.codes) if feedback else []
        try:
            draft = narrator.narrate(moment, persona, language, feedback)
        except NarratorError as e:
            trace.append({"attempt": attempt, "step": "narrate", "ok": False, "narrator": narrator.name,
                          "claims": 0, "feedback": feedback_codes, "error": e.code, "message": str(e)})
            if on_attempt is not None:
                on_attempt(AttemptLog(moment, attempt, None, e, (), (), (), (), ()))
            if not e.retryable:
                fallback_reason = e.code
                break
            feedback = Feedback(attempt, (FeedbackItem("narrator", e.code, fragment=str(e)[:200]),))
            trace.append({"attempt": attempt, "step": "feedback", "ok": False,
                          "codes": list(feedback.codes), "will_retry": attempt < max_attempts})
            continue
        trace.append({"attempt": attempt, "step": "narrate", "ok": True, "narrator": narrator.name,
                      "claims": len(draft.claims), "feedback": feedback_codes})
        if draft.menu is not None:
            ctx = SlotContext.from_moment(moment, events, language)
            items, issues, results, claims_out, ids_out = check_menu_draft(
                draft.template or "", draft.menu, ctx, config
            )
        elif draft.template is not None:
            ctx = SlotContext.from_moment(moment, events, language)
            items, issues, results, claims_out, ids_out = check_slot_draft(
                draft.template, draft.claims, draft.claim_ids, ctx, config
            )
        else:
            items, issues, results = check_draft(draft.text, draft.claims, events, roster, config, language)
            claims_out, ids_out = draft.claims, draft.claim_ids
        if on_attempt is not None:
            on_attempt(AttemptLog(moment, attempt, draft, None, tuple(items), tuple(issues), results,
                                  tuple(claims_out), tuple(ids_out)))
        trace.append({"attempt": attempt, "step": "lint", "ok": not issues,
                      "issues": [{"code": i.code, "fragment": i.fragment} for i in issues]})
        trace.append({"attempt": attempt, "step": "verify", "ok": all(r.ok for r in results),
                      "results": [{"claim_index": i, "ok": r.ok, "reason": r.reason}
                                  for i, r in enumerate(results)]})
        if not items:
            trace.append({"attempt": attempt, "step": "accept", "ok": True, "source": narrator.source})
            if cache is not None:
                trace.append({"attempt": attempt, "step": "cache_store", "ok": True, "key": key})
            text, parts = draft.text, draft.parts or ((Part(draft.text),) if draft.text else ())
            if draft.template is not None:
                clauses = draft.menu.clause_templates(language) if draft.menu is not None else None
                parts = render_parts(draft.template, claims_out, ids_out, results, ctx, clauses)
                text = "".join(p.text for p in parts)
            rec = record(text=text, claims=claims_out, verification=results, lint_issues=(),
                         attempts=attempt, source=narrator.source, template=draft.template, parts=parts)
            if cache is not None:
                cache.put(key, rec.to_dict())
            return rec
        feedback = Feedback(attempt, tuple(items))
        trace.append({"attempt": attempt, "step": "feedback", "ok": False,
                      "codes": list(feedback.codes), "will_retry": attempt < max_attempts})

    # Labelled template fallback: only sentences whose claims verify and that pass lint.
    narration = template_narrate(moment, events, config)
    published = []
    claims: list[Claim] = []
    results_out: list[VerificationResult] = []
    for i, sentence in enumerate(narration.sentences):
        text = sentence.text[language]
        if narration.sentence_ok(i) and lint_text(text, sentence.claims, roster, config, language).ok:
            published.append(sentence)
            claims += sentence.claims
            results_out += narration.results[i]
    text, _, parts = join_sentences(published, language)
    trace.append({"attempt": attempts, "step": "fallback", "ok": True,
                  "reason": fallback_reason, "narrator": "template",
                  "published_sentences": len(published), "total_sentences": len(narration.sentences)})
    final_lint = lint_text(text, claims, roster, config, language)
    return record(text=text, claims=tuple(claims), verification=tuple(results_out),
                  lint_issues=final_lint.issues, attempts=attempts, source="template_fallback", parts=parts)


def run_match(
    events: Sequence[Event],
    narrator: Narrator,
    *,
    persona: str | None = None,
    language: str = "en",
    select: bool = True,
    cache: NarrationCache | None = None,
    prompt_version: str | None = None,
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
    on_attempt: AttemptHook | None = None,
) -> list[tuple[Moment, NarrationRecord]]:
    require_language(language)
    moments = detect_moments(events)
    if select:
        moments = select_moments(moments, config)
    return [
        (m, run_moment(m, narrator, events, persona=persona, language=language, cache=cache,
                       prompt_version=prompt_version, config=config, on_attempt=on_attempt))
        for m in moments
    ]
