"""Guard: the deterministic gate between a draft and publication. Code, not a model.

It wraps the checks the pipeline already runs on a menu draft (text lint, placeholder and menu binding, the
foundry-v5 menu rules, `verify_claim` on every bound claim) and, when they pass, renders the text. A draft the
Guard rejects is never published, whatever any agent says; its rejection becomes coded Feedback for the Narrator.
Behaviour is the pipeline's (tests/test_agents_guard.py compares them on the stored drafts).
"""

from __future__ import annotations

from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.menu import ClaimMenu
from app.explain.slots import SlotContext

from . import tools
from .state import GuardResult


__all__ = ["GuardResult", "guard_check"]


async def guard_check(
    template: str, menu: ClaimMenu, ctx: SlotContext, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> GuardResult:
    check = await tools.check_template(template, menu, ctx, config)
    ok = not check.items and all(r.ok for r in check.verification) and bool(check.claims) and check.text is not None
    return GuardResult(
        ok=ok, template=template, items=check.items, lint_codes=tuple(i.code for i in check.lint_issues),
        claims=check.claims, claim_ids=check.claim_ids, verification=check.verification,
        text=check.text if ok else None, parts=check.parts if ok else (),
    )
