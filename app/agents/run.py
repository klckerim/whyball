"""CLI: runs the agent workflow over the demo matches and writes a run file.

    python -m app.agents.run --match red_card_swing_seed42 --moments featured --dry-run
    python -m app.agents.run --match all --moments all --out docs/AGENT_RUN.json          # LIVE: spends tokens

`--dry-run` calls no model (a scripted client that reads the same moment records). Without it the run is LIVE: the
call and token estimate is printed first and a typed confirmation is required (`--yes` skips it, for the user's own
scripts). `--estimate` prints the estimate and stops. Prints one line per moment: attempts, source, verification,
duration, tokens.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.analytics import detect_moments
from app.explain.config import DEFAULT_EXPLAIN_CONFIG
from app.explain.llm_narrator import PROMPT_VERSION
from app.explain.selector import select_moments
from app.generator.freeze import demo_paths
from app.generator.models import read_jsonl

from .analyst import ANALYST_VERSION
from .dryrun import DryRunClient
from .limits import DEFAULT_AGENTS_CONFIG, AgentsConfig, CallBudget
from .runfile import append_run, moment_entry, token_totals, usage_rows, write_run
from .state import Flags
from .verifier import VERIFIER_VERSION
from .workflow import AgentWorkflow, CardOutcome

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_RUN = REPO_ROOT / "docs" / "LLM_RUN.json"
DEFAULT_OUT = REPO_ROOT / "docs" / "AGENT_RUN.json"


def baseline_tokens(path: Path = BASELINE_RUN) -> dict[str, float]:
    """Mean tokens and latency of one Narrator call, from the last measured run (docs/LLM_RUN.json usage rows)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [u for r in data["runs"] for m in r["matches"] for u in m["usage"] if u.get("input_tokens")]
    n = len(rows)
    return {"calls": n, "input": sum(u["input_tokens"] for u in rows) / n, "output": sum(u["output_tokens"] for u in rows) / n,
            "latency_ms": sum(u["latency_ms"] for u in rows) / n}


def estimate(n_moments: int, flags: Flags, base: dict[str, float] | None = None, agents: AgentsConfig = DEFAULT_AGENTS_CONFIG) -> dict[str, Any]:
    """Calls and tokens for `n_moments` cards. Typical: every agent once per card plus the measured retry share;
    worst: three attempts of Narrator and Verifier. Analyst and Verifier tokens are NOT measured yet: they are taken
    as one Narrator call each (an upper bound for the analyst, a rough guess for the verifier)."""
    base = base or baseline_tokens()
    per_call_in, per_call_out = base["input"], base["output"]
    analyst = 1 if flags.analyst else 0
    verifier = 1 if flags.verifier else 0
    typical_attempts = 1.1  # LLM_RUN: 4 of 45 moments needed a second attempt (a bit under 10 %)
    typical = n_moments * (analyst + typical_attempts * (1 + verifier))
    worst = n_moments * (analyst + agents.max_attempts * (1 + verifier))
    return {
        "moments": n_moments, "calls_typical": round(typical), "calls_worst": worst,
        "input_tokens_typical": round(typical * per_call_in), "output_tokens_typical": round(typical * per_call_out),
        "input_tokens_worst": round(worst * per_call_in), "output_tokens_worst": round(worst * per_call_out),
        "seconds_typical_sequential": round(typical * base["latency_ms"] / 1000),
        "basis": f"{int(base['calls'])} Narrator calls of docs/LLM_RUN.json: {per_call_in:.0f} in / {per_call_out:.0f} out "
                 f"(reasoning included) / {base['latency_ms']:.0f} ms on average",
    }


def format_estimate(e: dict[str, Any], concurrency: int) -> str:
    return (
        f"estimate for {e['moments']} moments: {e['calls_typical']} calls typical, {e['calls_worst']} at worst\n"
        f"  tokens typical: {e['input_tokens_typical']:,} in / {e['output_tokens_typical']:,} out; "
        f"worst: {e['input_tokens_worst']:,} in / {e['output_tokens_worst']:,} out\n"
        f"  time typical: about {e['seconds_typical_sequential'] // max(concurrency, 1)} s with {concurrency} cards in flight\n"
        f"  basis: {e['basis']}; analyst and verifier tokens assumed equal to a narrator call (not measured yet)"
    )


def card_line(moment_id: str, minute_label: str, mtype: str, o: CardOutcome) -> str:
    card = o.card
    v = card.verification
    toks = sum((s.tokens.input or 0) + (s.tokens.output or 0) for s in o.trace if s.tokens)
    dur = max((s.started_ms + s.duration_ms for s in o.trace), default=0)
    extras = []
    if any(s.step == "analyst_fallback" for s in o.trace):
        extras.append("analyst_fallback")
    if any(s.step == "verifier_error" for s in o.trace):
        extras.append("verifier_error")
    if any(s.step == "workflow_error" for s in o.trace):
        extras.append("workflow_error")
    return (f"{moment_id[-4:]}  {minute_label:>6}  {mtype:<24} attempts={v.attempts} source={card.source:<17} "
            f"verifier={v.verifier:<19} label={v.label_source:<17} {dur / 1000:6.1f}s {toks:>6} tok"
            + (f"  [{', '.join(extras)}]" if extras else ""))


def live_client():
    """FoundryChatClientAdapter from FOUNDRY_PROJECT_ENDPOINT / FOUNDRY_MODEL (environment or .env), like the narrator."""
    from app.explain.credential import make_credential
    from app.explain.llm_narrator import FoundryChatClientAdapter

    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        load_dotenv()
    endpoint, model = os.environ.get("FOUNDRY_PROJECT_ENDPOINT"), os.environ.get("FOUNDRY_MODEL")
    if not endpoint or not model:
        raise SystemExit("FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL are required for a live run")
    return FoundryChatClientAdapter(project_endpoint=endpoint, model=model, credential=make_credential()), model


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


async def run_matches(
    stems: list[str], mode: str, flags: Flags, client: Any, model_tag: str, agents: AgentsConfig, out_lines: list[str],
    stopped: list[str], stop_on_trouble: bool = False,
) -> tuple[list[dict[str, Any]], list[CardOutcome], CallBudget]:
    budget = CallBudget(agents.max_calls_per_run)
    matches, outcomes = [], []
    for _, _, path in demo_paths():
        if path.stem not in stems:
            continue
        events = read_jsonl(path)
        moments = detect_moments(events)
        if mode == "featured":
            moments = select_moments(moments, DEFAULT_EXPLAIN_CONFIG)
        wf = AgentWorkflow(events, client, flags=flags, agents=agents, model_tag=model_tag, budget=budget)
        results = await wf.run_cards(moments, stop_on_trouble=stop_on_trouble)
        out_lines.append(f"\n{path.stem}: {len(moments)} moments")
        done = [(m, o) for m, o in zip(moments, results) if o is not None]
        for m, o in zip(moments, results):
            from app.explain.template_narrator import fmt_minute
            out_lines.append("  " + (card_line(m.id, fmt_minute(m.period, m.minute), m.type, o) if o
                                     else f"{m.id[-4:]}  not started (run stopped)"))
        matches.append({"match_id": path.stem, "moments": [moment_entry(m, o) for m, o in done],
                        "usage": usage_rows(wf.narrator.usage)})
        outcomes += [o for _, o in done]
        if wf.trouble:
            stopped.append(wf.trouble)
            break
    return matches, outcomes, budget


def main(argv: list[str] | None = None) -> int:
    ids = [p.stem for _, _, p in demo_paths()]
    ap = argparse.ArgumentParser(description="Run the agent workflow over demo matches")
    ap.add_argument("--match", default="all", help="a demo match id or 'all': " + ", ".join(ids))
    ap.add_argument("--moments", choices=("featured", "all"), default="featured")
    ap.add_argument("--no-analyst", action="store_true")
    ap.add_argument("--no-verifier", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="no model call: a scripted client")
    ap.add_argument("--estimate", action="store_true", help="print the call/token estimate and stop")
    ap.add_argument("--yes", action="store_true", help="live run without the typed confirmation")
    ap.add_argument("--out", type=Path, help=f"run file (live default: {DEFAULT_OUT.relative_to(REPO_ROOT)}; dry run: none)")
    ap.add_argument("--append", action="store_true", help="add these matches to an existing run file (same model and flags)")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_AGENTS_CONFIG.max_concurrent_cards)
    args = ap.parse_args(argv)

    stems = ids if args.match == "all" else [args.match]
    if any(s not in ids for s in stems):
        ap.error(f"unknown match {args.match!r}")
    flags = Flags(analyst=not args.no_analyst, verifier=not args.no_verifier)
    agents = AgentsConfig(max_concurrent_cards=args.concurrency)

    n = 0
    for _, _, path in demo_paths():
        if path.stem in stems:
            ms = detect_moments(read_jsonl(path))
            n += len(select_moments(ms, DEFAULT_EXPLAIN_CONFIG)) if args.moments == "featured" else len(ms)
    est = estimate(n, flags, agents=agents)
    if not args.dry_run:
        print(format_estimate(est, args.concurrency))
    if args.estimate:
        return 0

    if args.dry_run:
        client, model = DryRunClient(), "dry-run"
        out = args.out
    else:
        if not args.yes:
            if not sys.stdin.isatty():
                print("a live run needs --yes (or an interactive confirmation)", file=sys.stderr)
                return 2
            if input(f"LIVE run: about {est['calls_typical']} model calls. Type 'run' to start: ").strip() != "run":
                print("not started")
                return 1
        client, model = live_client()
        out = args.out or DEFAULT_OUT

    started = _now()
    t0 = time.perf_counter()
    lines: list[str] = []
    stopped: list[str] = []
    matches, outcomes, budget = asyncio.run(run_matches(
        stems, args.moments, flags, client, model, agents, lines, stopped, stop_on_trouble=not args.dry_run))
    wall = time.perf_counter() - t0
    print("\n".join(lines))
    totals = token_totals(outcomes)
    by_source = {s: sum(o.card.source == s for o in outcomes) for s in ("llm", "template_fallback")}
    guard_only = sum(o.card.verification.label_source == "guard_only" for o in outcomes)
    print(f"\n{len(outcomes)} cards in {wall:.1f} s · calls {budget.calls} · tokens in {totals['in']:,} / out {totals['out']:,} "
          f"· sources {by_source} · guard-only {guard_only} · analyst fallbacks "
          f"{sum(any(s.step == 'analyst_fallback' for s in o.trace) for o in outcomes)} · verifier rejects "
          f"{sum(s.step == 'verify' and s.output.get('verdict') == 'reject' for o in outcomes for s in o.trace)}")
    if stopped:
        print(f"\nSTOPPED at the first trouble: {stopped[0]}")
    if out:
        meta = {
            "started_at": started, "finished_at": _now(), "lang": "en", "model": model,
            "prompt_version": f"{PROMPT_VERSION}:{model}", "analyst_version": ANALYST_VERSION,
            "verifier_version": VERIFIER_VERSION, "flags": asdict(flags), "moments": args.moments,
            "dry_run": args.dry_run, "calls": budget.calls, "tokens": totals, "wall_seconds": round(wall, 1),
            "max_calls_per_run": agents.max_calls_per_run, "max_attempts": agents.max_attempts,
            "timeouts_s": {"narrator": agents.narrator_timeout_s, "analyst": agents.analyst_timeout_s,
                           "verifier": agents.verifier_timeout_s},
        }
        if stopped:  # a stopped run is kept for diagnosis, in a file `app.publish` refuses
            meta["stopped"] = stopped[0]
            out = out.with_suffix(".stopped.json")
        elif args.append and out.exists():
            started, meta = append_run(out, meta, matches)
            matches = []
        if matches or not (args.append and out.exists() and not stopped):
            write_run(out, meta, started, meta["finished_at"], matches)
        print(f"run file: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
