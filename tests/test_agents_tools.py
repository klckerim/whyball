"""P2 / 3b: the deterministic tools live in one file, so P3 can swap it for an MCP client."""

import ast
from pathlib import Path

import pytest

from app.agents import tools

AGENTS = Path(tools.__file__).parent
# Callables that are tools (they compute or check); agents and the Guard reach them through tools.py only.
TOOL_CALLABLES = {
    "build_menu", "verify_claim", "measure", "lint_text", "lint_template", "render", "render_parts",
    "check_menu_draft", "check_slot_draft", "check_draft", "bind_menu", "bind_template", "metrics_at",
    "run_moment", "template_narrate", "narrate",
}


def _imported_names(source: str) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            names |= {a.name for a in node.names}
    return names


def _modules(source: str) -> set[str]:
    out = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
        elif isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
    return out


OTHERS = [f for f in sorted(AGENTS.glob("*.py")) if f.name not in ("tools.py", "__init__.py")]


@pytest.mark.parametrize("path", OTHERS, ids=lambda p: p.name)
def test_only_tools_py_imports_the_deterministic_tool_callables(path):
    assert _imported_names(path.read_text(encoding="utf-8")) & TOOL_CALLABLES == set()


def test_tools_py_names_what_it_wraps():
    assert {"build_menu", "check_menu_draft", "render_parts"} <= _imported_names(Path(tools.__file__).read_text())


def test_tools_never_reach_a_model_or_the_agent_framework():
    mods = _modules(Path(tools.__file__).read_text(encoding="utf-8"))
    assert not any(m.startswith(("agent_framework", "app.explain.llm_narrator", "app.llm", "openai")) for m in mods)


def test_the_tool_functions_are_async_json_free_calls():
    import inspect
    assert inspect.iscoroutinefunction(tools.menu_for) and inspect.iscoroutinefunction(tools.check_template)


def test_template_claim_ids_follow_the_publication_stores_rule():
    from app.explain.narrator import TemplateNarrator
    from app.explain.pipeline import run_moment
    from app.publish.store import _template_ids
    from tests.explain_helpers import moment_case

    for case in ("goal", "dominance_without_reward", "pressure_shift", "red_card"):
        events, moment = moment_case(case)
        claims = run_moment(moment, TemplateNarrator(events), events).claims
        assert tools.template_claim_ids(claims) == _template_ids(claims)


def test_the_template_fallback_matches_the_pipelines():
    import asyncio

    from app.explain.narrator import FakeNarrator
    from app.explain.pipeline import run_moment
    from tests.explain_helpers import moment_case

    events, moment = moment_case("dominance_without_reward")
    rec = run_moment(moment, FakeNarrator(events, "wrong_number"), events)
    assert rec.source == "template_fallback"
    fb = asyncio.run(tools.template_fallback(moment, events))
    assert (fb.text, fb.parts, fb.claims) == (rec.text, rec.parts, rec.claims)
