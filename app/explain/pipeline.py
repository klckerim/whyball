"""Anlatım hattı: moment → anlatıcı → text_lint + verify_claim → (geri bildirimle
yeniden deneme) → kabul ya da etiketli template yedeği.

CLAUDE.md: doğrulanmayan cümle yayınlanmaz; en fazla `max_retries` yeniden
deneme, sonra template fallback.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from typing import Any

from app.analytics import detect_moments
from app.analytics.moments import Moment
from app.generator.models import Event

from .cache import NarrationCache, cache_key
from .claims import Claim, VerificationResult, verify_claim
from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from .narrator import Feedback, FeedbackItem, Narrator
from .selector import select_moments
from .template_narrator import narrate as template_narrate
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
    attempts: int  # anlatıcı çağrısı sayısı
    source: str  # "llm" | "template" | "template_fallback"
    cache_hit: bool
    cache_key: str | None
    trace: tuple[dict[str, Any], ...]

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
        )


def _check(
    text: str, claims: Sequence[Claim], events: Sequence[Event], roster: Roster, config: ExplainConfig
) -> tuple[list[FeedbackItem], tuple[LintIssue, ...], tuple[VerificationResult, ...]]:
    items: list[FeedbackItem] = []
    if not text.strip():
        items.append(FeedbackItem("draft", "empty_text"))
    if not claims:
        items.append(FeedbackItem("draft", "no_claims"))
    lint = lint_text(text, claims, roster, config)
    items += [FeedbackItem("lint", i.code, fragment=i.fragment) for i in lint.issues]
    results = tuple(verify_claim(c, events, config) for c in claims)
    items += [
        FeedbackItem("verify", r.reason, claim_index=i) for i, r in enumerate(results) if not r.ok
    ]
    return items, lint.issues, results


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
) -> NarrationRecord:
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
                cached = None  # bozuk kayıt: miss
        trace.append({"attempt": 0, "step": "cache", "ok": cached is not None,
                      "hit": cached is not None, "key": key})
        if cached is not None:
            return replace(cached, cache_hit=True, cache_key=key, trace=tuple(trace))

    max_attempts = 1 + config.max_retries
    feedback: Feedback | None = None
    for attempt in range(1, max_attempts + 1):
        draft = narrator.narrate(moment, persona, language, feedback)
        trace.append({"attempt": attempt, "step": "narrate", "ok": True, "narrator": narrator.name,
                      "claims": len(draft.claims), "feedback": list(feedback.codes) if feedback else []})
        items, issues, results = _check(draft.text, draft.claims, events, roster, config)
        trace.append({"attempt": attempt, "step": "lint", "ok": not issues,
                      "issues": [{"code": i.code, "fragment": i.fragment} for i in issues]})
        trace.append({"attempt": attempt, "step": "verify", "ok": all(r.ok for r in results),
                      "results": [{"claim_index": i, "ok": r.ok, "reason": r.reason}
                                  for i, r in enumerate(results)]})
        if not items:
            trace.append({"attempt": attempt, "step": "accept", "ok": True, "source": narrator.source})
            if cache is not None:
                trace.append({"attempt": attempt, "step": "cache_store", "ok": True, "key": key})
            rec = record(text=draft.text, claims=draft.claims, verification=results,
                         lint_issues=(), attempts=attempt, source=narrator.source)
            if cache is not None:
                cache.put(key, rec.to_dict())
            return rec
        feedback = Feedback(attempt, tuple(items))
        trace.append({"attempt": attempt, "step": "feedback", "ok": False,
                      "codes": list(feedback.codes), "will_retry": attempt < max_attempts})

    # Etiketli template yedeği: yalnızca iddiaları doğrulanan ve lint'ten geçen cümleler.
    narration = template_narrate(moment, events, config)
    text_parts: list[str] = []
    claims: list[Claim] = []
    results_out: list[VerificationResult] = []
    for i, sentence in enumerate(narration.sentences):
        text = sentence.text[language]
        if narration.sentence_ok(i) and lint_text(text, sentence.claims, roster, config).ok:
            text_parts.append(text)
            claims += sentence.claims
            results_out += narration.results[i]
    text = " ".join(text_parts)
    trace.append({"attempt": max_attempts, "step": "fallback", "ok": True,
                  "reason": "max_retries_exceeded", "narrator": "template",
                  "published_sentences": len(text_parts), "total_sentences": len(narration.sentences)})
    final_lint = lint_text(text, claims, roster, config)
    return record(text=text, claims=tuple(claims), verification=tuple(results_out),
                  lint_issues=final_lint.issues, attempts=max_attempts, source="template_fallback")


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
) -> list[tuple[Moment, NarrationRecord]]:
    moments = detect_moments(events)
    if select:
        moments = select_moments(moments, config)
    return [
        (m, run_moment(m, narrator, events, persona=persona, language=language, cache=cache,
                       prompt_version=prompt_version, config=config))
        for m in moments
    ]
