"""The tool interface of the agents: the ONLY module of `app/agents` that calls the deterministic explain code.

Today each tool is a direct async function over `app.explain`. In P3 this file is replaced by an MCP client
with the same function names and shapes; agents and the Guard import their tools from here and nowhere else
(tests/test_agents_tools.py scans for it). Tools never call a model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.analytics.moments import Moment
from app.explain.claims import Claim, VerificationResult
from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.menu import ClaimMenu, build_menu
from app.explain.narrator import FeedbackItem
from app.explain.pipeline import check_menu_draft
from app.explain.slots import SlotContext, render_parts
from app.explain.template_narrator import Part, join_sentences
from app.explain.template_narrator import narrate as template_narrate
from app.explain.text_lint import LintIssue, Roster, lint_text
from app.generator.models import Event


@dataclass(frozen=True)
class TemplateCheck:
    """Everything the checks said about one placeholder template (menu draft)."""

    items: tuple[FeedbackItem, ...]  # empty: green
    lint_issues: tuple[LintIssue, ...]
    verification: tuple[VerificationResult, ...]
    claims: tuple[Claim, ...]
    claim_ids: tuple[str, ...]
    text: str | None  # rendered by code; None unless the template passed
    parts: tuple[Part, ...]


def slot_context(moment: Moment, events: Sequence[Event], language: str = "en") -> SlotContext:
    return SlotContext.from_moment(moment, events, language)


async def menu_for(
    moment: Moment, events: Sequence[Event], config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> ClaimMenu:
    """The verified claim menu of a moment (claims that do not verify are not on it)."""
    return build_menu(moment, events, config)


async def check_template(
    template: str, menu: ClaimMenu, ctx: SlotContext, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> TemplateCheck:
    """Template lint, placeholder and menu binding, verify_claim on every bound claim; on green also the
    rendered text and its parts. The numbers and events in the text come from this call only."""
    items, issues, results, claims, ids = check_menu_draft(template, menu, ctx, config)
    if items:
        return TemplateCheck(tuple(items), issues, results, claims, ids, None, ())
    parts = render_parts(template, claims, ids, results, ctx, menu.clause_templates(ctx.language))
    return TemplateCheck((), issues, results, claims, ids, "".join(p.text for p in parts), parts)


@dataclass(frozen=True)
class FallbackCard:
    """The labelled template narration: only sentences whose claims verify and that pass lint."""

    text: str
    parts: tuple[Part, ...]
    claims: tuple[Claim, ...]
    verification: tuple[VerificationResult, ...]
    published_sentences: int
    total_sentences: int


async def template_fallback(
    moment: Moment, events: Sequence[Event], config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG, language: str = "en"
) -> FallbackCard:
    """The same fallback `pipeline.run_moment` publishes after its last retry."""
    roster = Roster.from_events(events)
    narration = template_narrate(moment, events, config)
    published, claims, results = [], [], []
    for i, sentence in enumerate(narration.sentences):
        text = sentence.text[language]
        if narration.sentence_ok(i) and lint_text(text, sentence.claims, roster, config, language).ok:
            published.append(sentence)
            claims += sentence.claims
            results += narration.results[i]
    text, _, parts = join_sentences(published, language)
    return FallbackCard(text, parts, tuple(claims), tuple(results), len(published), len(narration.sentences))


def template_claim_ids(claims: Sequence[Claim]) -> tuple[str, ...]:
    """Ids for claims that have no menu id: metric + side, numbered when repeated. The same rule as the publication
    store's (tests/test_agents_tools.py keeps them equal); the store cannot import this package."""
    ids: list[str] = []
    for c in claims:
        base = c.metric if c.subject.team is None else f"{c.metric}_{c.subject.team}"
        cid, n = base, 1
        while cid in ids:
            n += 1
            cid = f"{base}_{n}"
        ids.append(cid)
    return tuple(ids)
