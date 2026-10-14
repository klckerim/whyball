"""P2 / 3a: the shared state is immutable, updated by read-modify-write; the trace step has a closed schema.

The in-place patterns the Agent Framework silently loses (it deep-copies stored state) are caught three ways:
frozen dataclasses (assignment raises), a walk over a populated state (no list/dict/set inside our types) and
an AST scan of app/agents for mutator calls on state values.
"""

import ast
import asyncio
import copy
import dataclasses
from pathlib import Path

import pytest
from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from app.agents import state as state_mod
from app.agents import trace as trace_mod
from app.agents.state import (
    MAX_ATTEMPTS, STATE_KEY, Briefing, DraftRecord, FeedbackEntry, FeedbackRecord, FinalCard, Flags,
    NarrationState, Verification, load, save, update,
)
from app.agents.trace import STATUSES, STEPS, Stopwatch, Tokens, TraceStep
from app.explain.menu import build_menu
from app.explain.template_narrator import Part
from tests.explain_helpers import moment_case

AGENTS_DIR = Path(state_mod.__file__).parent


def _state() -> NarrationState:
    events, moment = moment_case("goal")
    return NarrationState(moment=moment, menu=build_menu(moment, events))


def _step(**kw) -> TraceStep:
    base = dict(attempt=1, started_ms=5, duration_ms=7, input_ref="menu", output={"ids": ["a"]})
    return TraceStep.make("narrate", "narrator", **{**base, **kw})


def _populated() -> NarrationState:
    s = _state().next_attempt()
    s = s.with_briefing(Briefing(("goal", "score_home"), "a late equaliser"))
    s = s.with_draft(DraftRecord(1, "{clause:goal}", "text"))
    s = s.with_feedback(FeedbackRecord(1, (FeedbackEntry("lint", "raw_number", "3"),)))
    s = s.with_step(_step(tokens=Tokens(1, 2, 3), model="m"))
    return s.finish(FinalCard("t", (Part("t"),), (), (), (), "llm", "{x}", Verification(True, "passed", 1, "llm")))


class FakeStore:
    """A state store with the framework's copy semantics (values are deep-copied in and out)."""

    def __init__(self):
        self._d = {}

    def get_state(self, key, default=None):
        return copy.deepcopy(self._d[key]) if key in self._d else default

    def set_state(self, key, value):
        self._d[key] = copy.deepcopy(value)


# --- immutability ------------------------------------------------------------------------------------------


def _our_types():
    out = []
    for mod in (state_mod, trace_mod):
        for v in vars(mod).values():
            if dataclasses.is_dataclass(v) and v.__module__ == mod.__name__:
                out.append(v)
    return out


def test_every_state_and_trace_type_is_a_frozen_dataclass():
    types = _our_types()
    assert {t.__name__ for t in types} >= {"NarrationState", "TraceStep", "Tokens", "Briefing", "DraftRecord",
                                           "FeedbackRecord", "FeedbackEntry", "FinalCard", "Verification", "Flags"}
    for t in types:
        assert t.__dataclass_params__.frozen, f"{t.__name__} must be frozen"


def test_assigning_to_a_state_field_raises():
    s = _state()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.attempt = 5  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        _step().status = "error"  # type: ignore[misc]


def _walk(value, path="state"):
    """Our own types hold scalars, tuples and our own frozen dataclasses only."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return
    if isinstance(value, tuple):
        for i, v in enumerate(value):
            _walk(v, f"{path}[{i}]")
        return
    if dataclasses.is_dataclass(value) and type(value).__module__.startswith("app.agents"):
        for f in dataclasses.fields(value):
            _walk(getattr(value, f.name), f"{path}.{f.name}")
        return
    if dataclasses.is_dataclass(value):
        return  # moment, menu, claims, parts: existing frozen dataclasses the state only points at
    raise AssertionError(f"{path} is a {type(value).__name__}: a mutable value inside the state")


def test_a_populated_state_has_no_list_dict_or_set_in_it():
    _walk(_populated())


def test_the_walk_catches_a_mutable_field():
    @dataclasses.dataclass(frozen=True)
    class Bad:
        items: list

    Bad.__module__ = "app.agents.fake"
    with pytest.raises(AssertionError, match="list"):
        _walk(Bad([]))


def test_with_methods_return_new_states_and_leave_the_old_one_alone():
    s0 = _state()
    s1 = s0.next_attempt()
    s2 = s1.with_draft(DraftRecord(1, "t"))
    assert (s0.attempt, s1.attempt, s2.attempt) == (0, 1, 1)
    assert s0.drafts == () and s1.drafts == () and len(s2.drafts) == 1
    assert isinstance(s2.drafts, tuple) and isinstance(s2.trace, tuple)


def test_a_card_is_final_once():
    s = _populated()
    with pytest.raises(ValueError, match="already final"):
        s.finish(s.final_card)


def test_attempt_limit_is_three_and_can_retry_follows_it():
    assert MAX_ATTEMPTS == 3
    s = _state()
    flags = []
    for _ in range(MAX_ATTEMPTS):
        s = s.next_attempt()
        flags.append(s.can_retry)
    assert flags == [True, True, False]


# --- read-modify-write -------------------------------------------------------------------------------------


def test_update_is_read_modify_write_and_persists_through_a_copying_store():
    store = FakeStore()
    save(store, _state())
    update(store, lambda s: s.next_attempt())
    update(store, lambda s: s.with_step(_step()))
    got = load(store)
    assert got.attempt == 1 and len(got.trace) == 1


def test_load_needs_a_saved_state_and_update_needs_a_state_back():
    store = FakeStore()
    with pytest.raises(LookupError):
        load(store)
    save(store, _state())
    with pytest.raises(TypeError):
        update(store, lambda s: None)  # type: ignore[arg-type,return-value]


# --- the framework copies state: why in-place changes are lost -------------------------------------------


class _Start(Executor):
    def __init__(self):
        super().__init__(id="start")

    @handler
    async def go(self, n: int, ctx: WorkflowContext[int]) -> None:
        save(ctx, _state())
        ctx.set_state("plain_list", [1])
        ctx.get_state("plain_list").append(2)  # the in-place pattern the scan below forbids
        await ctx.send_message(n)


class _Middle(Executor):
    def __init__(self):
        super().__init__(id="middle")

    @handler
    async def go(self, n: int, ctx: WorkflowContext[int]) -> None:
        update(ctx, lambda s: s.next_attempt())
        update(ctx, lambda s: s.with_step(_step(input_ref="from-middle")))
        await ctx.send_message(n)


class _End(Executor):
    def __init__(self):
        super().__init__(id="end")

    @handler
    async def go(self, n: int, ctx: WorkflowContext[Never, dict]) -> None:
        s = load(ctx)
        await ctx.yield_output({"attempt": s.attempt, "refs": [t.input_ref for t in s.trace],
                                "plain_list": ctx.get_state("plain_list")})


def test_updates_survive_supersteps_in_a_real_workflow_and_in_place_changes_do_not():
    a, b, c = _Start(), _Middle(), _End()
    result = asyncio.run(WorkflowBuilder(start_executor=a).add_edge(a, b).add_edge(b, c).build().run(1))
    out = result.get_outputs()[0]
    assert out["attempt"] == 1 and out["refs"] == ["from-middle"]
    # Pinned framework behaviour: a list changed in place is lost. If this ever fails the framework changed its
    # copy semantics and DESIGN.md's state rule can be revisited.
    assert out["plain_list"] == [1]


# --- the scan ----------------------------------------------------------------------------------------------

MUTATORS = {"append", "extend", "insert", "remove", "pop", "clear", "update", "add", "discard", "setdefault",
            "sort", "reverse", "popitem"}
STATE_NAMES = {"state", "s", "st", "narration", "card"}


def _rooted_in_state(node: ast.AST) -> bool:
    """A name that holds state (`state`, `s`, ...), or `ctx.get_state(...)`, somewhere in the expression."""
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id in STATE_NAMES:
            return True
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get_state":
            return True
    return False


def in_place_state_changes(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in MUTATORS and _rooted_in_state(node.func.value):
                found.append(f"line {node.lineno}: .{node.func.attr}() on a state value")
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        for t in targets:
            if isinstance(t, (ast.Attribute, ast.Subscript)) and _rooted_in_state(t.value):
                found.append(f"line {node.lineno}: assignment into a state value")
    return found


@pytest.mark.parametrize("snippet", [
    "state.trace.append(x)",
    "ctx.get_state('k').append(1)",
    "s.drafts.extend(y)",
    "state.attempt = 2",
    "state.briefing.claim_ids[0] = 'a'",
    "s.attempt += 1",
    "ctx.get_state('k')['a'] = 1",
])
def test_the_scan_flags_in_place_changes(snippet):
    assert in_place_state_changes(snippet), snippet


@pytest.mark.parametrize("snippet", [
    "update(ctx, lambda s: s.with_draft(d))",
    "new = state.next_attempt()",
    "items = []; items.append(1)",
    "state = state.with_step(step)",
])
def test_the_scan_accepts_read_modify_write(snippet):
    assert in_place_state_changes(snippet) == []


def test_no_module_in_app_agents_changes_state_in_place():
    files = sorted(AGENTS_DIR.glob("*.py"))
    assert len(files) >= 3
    bad = {f.name: in_place_state_changes(f.read_text(encoding="utf-8")) for f in files}
    assert {k: v for k, v in bad.items() if v} == {}


# --- trace step schema --------------------------------------------------------------------------------------


def test_trace_step_has_the_documented_shape():
    d = _step(tokens=Tokens(10, 5, 3), model="gpt").to_dict()
    assert list(d) == ["step", "agent", "attempt", "started_ms", "duration_ms", "input_ref", "output", "tokens",
                       "model", "status"]
    assert d["tokens"] == {"in": 10, "out": 5, "reasoning": 3}
    assert d["output"] == {"ids": ["a"]} and d["status"] == "ok"
    assert _step().to_dict()["tokens"] == {"in": None, "out": None, "reasoning": None}


def test_trace_closed_sets():
    assert "analyst_fallback" in STEPS and "verifier_error" in STEPS and "workflow_error" in STEPS
    assert STATUSES == ("ok", "error", "timeout")
    for bad in ({"step": "dance"}, {"agent": "wizard"}, {"status": "slow"}):
        kw = {"step": "narrate", "agent": "narrator", "status": "ok", **bad}
        with pytest.raises(ValueError):
            TraceStep.make(kw.pop("step"), kw.pop("agent"), attempt=1, started_ms=0, duration_ms=0, input_ref="x",
                           **kw)
    with pytest.raises(ValueError):
        _step(duration_ms=-1)


def test_trace_output_is_a_copy_and_must_be_an_object():
    step = _step(output={"ids": ["a"]})
    step.output["ids"].append("b")  # a fresh dict: nothing stored changes
    assert step.output == {"ids": ["a"]}
    with pytest.raises(ValueError):
        TraceStep("narrate", "narrator", 1, 0, 0, "x", "[1]", None, None, "ok")


def test_stopwatch_times_steps_relative_to_the_cards_start():
    ticks = iter([100.0, 100.5, 101.25, 101.5])
    sw = Stopwatch(lambda: next(ticks))  # t0 = 100.0
    started = sw.start()  # 100.5
    assert sw.span(started) == (500, 750)  # now = 101.25
    assert sw.now_ms() == 1500  # 101.5


def test_state_key_is_one_name():
    assert STATE_KEY == "narration" and Flags() == Flags(analyst=True, verifier=True)
