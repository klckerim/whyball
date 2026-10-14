"""Verifier smoke test: ONLY the Verifier agent on injected drafts, no Analyst, no Narrator.

For each class the code Guard misses (wrong_slot_binding, role_reversed, event_wrong_claim) the first N injected v5 drafts
(distinct moments, Guard-accepted: the Verifier only ever sees drafts the Guard accepted) and N clean drafts of the same
corpus. Prints caught/total per class, whether the code matched, and false alarms on the clean ones; counts only.

    .venv/bin/python -m eval.verifier_smoke --select-only          # the drafts, no model call
    .venv/bin/python -m eval.verifier_smoke --n 4 --clean 8 --yes --out docs/VERIFIER_SMOKE.json   # LIVE: 4+4+4+8 calls

The drafts are a DEVELOPMENT SET: the file says so, and P4's held-out set must exclude them (`meta.development_set`).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.agents import tools
from app.agents.guard import guard_check
from app.agents.limits import AgentsConfig, CallBudget
from app.agents.state import GuardResult
from app.agents.trace import Stopwatch
from app.agents.verifier import VERIFIER_VERSION, VerifierAgent
from app.explain.config import DEFAULT_EXPLAIN_CONFIG
from eval.inject import FULL_CORPUS, INJECTION_TYPES, Sample, _rng, build_samples

CLASSES = ("wrong_slot_binding", "role_reversed", "event_wrong_claim")
SPECS = {t.name: t for t in INJECTION_TYPES}


@dataclass(frozen=True)
class Draft:
    kind: str  # class name or "clean"
    sample: Sample
    template: str
    guard: GuardResult
    tag: str | None


def has_metric(d: Draft, metric: str) -> bool:
    return any(c.metric == metric for c in d.guard.claims)


def select(n: int, n_clean: int | None = None, min_pressure: int = 2) -> tuple[dict[str, list[Draft]], list[str]]:
    """First `n` Guard-accepted drafts per class, one per moment (moment types varied first), plus `n_clean` clean drafts
    (default `n`), of which at least `min_pressure` state a pressure_balance claim."""
    samples, all_players = build_samples(FULL_CORPUS)
    out: dict[str, list[Draft]] = {}
    notes: list[str] = []
    for kind in (*CLASSES, "clean"):
        picked: list[Draft] = []
        seen_moments: set[tuple[str, str]] = set()
        types_seen: Counter[str] = Counter()
        want = n_clean if (kind == "clean" and n_clean is not None) else n
        pool = []
        for s in samples:
            d = s.slot5
            if d is None or d.menu is None:
                continue
            if kind == "clean":
                template, tag = d.template, None
            else:
                inject = SPECS[kind].injector("v5")
                inj = inject(s, _rng(s.moment, kind, s.lang, "v5"), all_players) if inject else None
                if inj is None:
                    continue
                template, tag = inj.text, inj.tag
            g = asyncio.run(guard_check(template, d.menu, d.ctx, DEFAULT_EXPLAIN_CONFIG))
            if g.ok:
                pool.append(Draft(kind, s, template, g, tag))
        if kind == "clean":  # the pressure_balance drafts first (distinct moments)
            for dr in pool:
                key = (dr.sample.events[0].match_id, dr.sample.moment.id)
                if sum(has_metric(p, "pressure_balance") for p in picked) >= min_pressure:
                    break
                if has_metric(dr, "pressure_balance") and key not in seen_moments:
                    seen_moments.add(key)
                    types_seen[dr.sample.moment.type] += 1
                    picked.append(dr)
        # vary the moment type first, then take in corpus order; one draft per moment id
        for round_ in range(want * 4):
            for dr in pool:
                m = dr.sample.moment
                if len(picked) >= want:
                    break
                key = (m.id, dr.sample.events[0].match_id)
                if key in seen_moments or types_seen[m.type] > round_:
                    continue
                seen_moments.add(key)
                types_seen[m.type] += 1
                picked.append(dr)
        if len(picked) < want:
            notes.append(f"{kind}: only {len(picked)} Guard-accepted drafts found")
        out[kind] = picked
    return out, notes


async def run(drafts: dict[str, list[Draft]], client, model: str) -> list[dict]:
    budget = CallBudget(100)
    rows = []
    for kind, items in drafts.items():
        for dr in items:
            s = dr.sample
            agent = VerifierAgent(s.events, client, budget=budget, model_tag=model, agents=AgentsConfig())
            res = await agent.verify(s.moment, dr.guard, s.slot5.ctx, s.slot5.menu, attempt=1, clock=Stopwatch())
            step = res.steps[0]
            issues = step.output.get("issues", []) if res.verdict != "error" else []
            rows.append({
                "kind": kind, "moment": s.moment.id, "moment_type": s.moment.type, "tag": dr.tag, "text": dr.guard.text,
                "verdict": res.verdict, "codes": [i["code"] for i in issues], "issues": issues,
                "error": step.output.get("reason") if res.verdict == "error" else None,
                "tokens": step.to_dict()["tokens"], "duration_ms": step.duration_ms,
            })
    return rows


def summary(rows: list[dict]) -> list[str]:
    lines = ["class                 rejected/total   code matched   passed   errors"]
    for kind in (*CLASSES, "clean"):
        r = [x for x in rows if x["kind"] == kind]
        rej = sum(x["verdict"] == "reject" for x in r)
        match = sum(x["verdict"] == "reject" and kind in x["codes"] for x in r)
        lines.append(f"{kind:<21} {rej}/{len(r):<13} {match if kind != 'clean' else '-':<14} "
                     f"{sum(x['verdict'] == 'pass' for x in r):<8} {sum(x['verdict'] == 'error' for x in r)}")
    clean = [x for x in rows if x["kind"] == "clean"]
    lines.append(f"false alarms on clean drafts: {sum(x['verdict'] == 'reject' for x in clean)}/{len(clean)}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=4, help="drafts per injected class")
    ap.add_argument("--clean", type=int, default=8, help="clean drafts (at least 2 with a pressure_balance claim)")
    ap.add_argument("--select-only", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    drafts, notes = select(args.n, args.clean)
    for kind, items in drafts.items():
        for dr in items:
            print(f"[{kind}] {dr.sample.moment.id} {dr.sample.moment.type}  tag={dr.tag}\n    {dr.guard.text}")
    for n in notes:
        print("note:", n)
    if args.select_only:
        return 0
    if not args.yes:
        print("a live run needs --yes", file=sys.stderr)
        return 2
    from app.agents.run import live_client

    client, model = live_client()
    rows = asyncio.run(run(drafts, client, model))
    print("\n" + "\n".join(summary(rows)))
    if args.out:
        args.out.write_text(json.dumps({"meta": {"verifier_version": VERIFIER_VERSION, "model": model, "n": args.n, "clean": args.clean,
                                         "development_set": True,
                                         "note": "development set: these drafts are excluded from P4's held-out set",
                                         "drafts": [{"kind": k, "match": d.sample.events[0].match_id, "moment": d.sample.moment.id}
                                                    for k, items in drafts.items() for d in items]},
                                        "rows": rows}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
