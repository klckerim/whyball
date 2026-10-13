"""Real LLM measurement: narrates the three demo matches with FoundryNarrator and builds the report.

    python -m eval.llm_run [--lang en] [--repeat 3]   # calls the model → docs/LLM_RUN.json + .md + human_review.csv
    python -m eval.llm_run --from-json docs/LLM_RUN.json   # re-render only

The report (docs/LLM_RUN.md) and the human review sheet (docs/human_review.csv) are always
built from the raw run output (JSON); they are never written by hand. The cache is not
used: every moment really goes to the model.

Measurement mode: each attempt's draft, rejection codes and rejection message (pipeline `on_attempt`)
are written only to this JSON; they never enter the cache or the published record. For
`evidence_mismatch` rejections, the events the claim cited and the verifier counted are stored with their types.

JSON format: `{"meta": {...}, "runs": [{"started_at", "finished_at", "matches"}]}`;
the old single-run format (`{"meta", "matches"}`) is read too. The version comparison is read
from the archived earlier versions (docs/LLM_RUN.foundry-v3.json, -v4.json).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.analytics.moments import Moment
from app.explain.claims import KICKOFF, Claim, MatchTime, measure, parse_ref
from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.pipeline import AttemptLog, NarrationRecord, run_match
from app.explain.template_narrator import fmt_minute
from app.generator.freeze import demo_paths
from app.generator.models import Event, read_jsonl

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
DEFAULT_JSON = DOCS / "LLM_RUN.json"
DEFAULT_MD = DOCS / "LLM_RUN.md"
DEFAULT_CSV = DOCS / "human_review.csv"
BASELINES = {
    "foundry-v3": DOCS / "LLM_RUN.foundry-v3.json",
    "foundry-v4": DOCS / "LLM_RUN.foundry-v4.json",
    "foundry-v4.1": DOCS / "LLM_RUN.foundry-v4.1.json",
}
REVIEW_COLUMNS = ("moment_id", "text", "correct", "wrong_fact", "misleading", "dull")
# Rules added / changed in foundry-v4.1 / v5 (live firing table)
NEW_RULES = ("event_type_not_allowed", "player_repeat", "article_team", "sentence_start",
             "unknown_claim_id", "sentence_without_claim", "missing_primary_claim", "minute_repeat")


# --- attempt record ------------------------------------------------------------------------------


def _event_types(refs: Sequence[str], by_seq: dict[int, Event]) -> list[dict[str, Any]]:
    out = []
    for ref in refs:
        try:
            _, seq = parse_ref(ref)
        except ValueError:
            out.append({"id": ref, "type": None})
            continue
        e = by_seq.get(seq)
        out.append({"id": ref, "type": e.type.value if e else None})
    return out


def _window(claim: Claim) -> str:
    if claim.start == claim.end:
        return "at the event"
    if claim.start == KICKOFF:
        return "kickoff → now"
    return f"window ({fmt_minute(claim.start.period, claim.start.minute)} → " \
           f"{fmt_minute(claim.end.period, claim.end.minute)})"


def verify_failures(log: AttemptLog, events: Sequence[Event]) -> list[dict[str, Any]]:
    """Rejected claims; for evidence_mismatch, the cited and counted events with their types."""
    by_seq = {e.seq: e for e in events}
    match_id = events[0].match_id
    out = []
    for i, (claim, result) in enumerate(zip(log.claims, log.verification)):
        if result.ok:
            continue
        entry: dict[str, Any] = {
            "claim_id": log.claim_ids[i] if i < len(log.claim_ids) else f"#{i}",
            "reason": result.reason,
            "actual": result.actual,
            "claim": claim.to_dict(),
            "window": _window(claim),
        }
        if result.reason == "evidence_mismatch":
            counted = measure(claim.metric, claim.subject, claim.start, claim.end, events).counted
            entry["cited"] = _event_types(claim.event_ids, by_seq)
            entry["counted"] = _event_types([f"{match_id}#{s}" for s in counted], by_seq)
        out.append(entry)
    return out


def _refs(items: Sequence[dict[str, Any]]) -> str:
    return "[" + ", ".join(f"#{r['id'].rsplit('#', 1)[-1]} {r['type']}" for r in items) + "]"


def describe_rejection(log: AttemptLog, failures: Sequence[dict[str, Any]]) -> str:
    """Readable rejection message; filled for every rejected attempt."""
    if log.error is not None:
        return str(log.error) or log.error.code
    parts = [f"draft {i.code}" for i in log.items if i.source == "draft"]
    parts += [f"lint {i.code} {i.fragment!r}" for i in log.lint_issues]
    for f in failures:
        claim = Claim.from_dict(f["claim"])
        text = f"verify {f['claim_id']} {f['reason']}: {claim.describe()}"
        if f["reason"] == "evidence_mismatch":
            text += f"; cited {_refs(f['cited'])} counted {_refs(f['counted'])}"
        elif f["actual"] is not None:
            text += f"; actual {f['actual']:g}"
        parts.append(text)
    return " | ".join(parts) or "rejected"


def attempt_entry(log: AttemptLog, events: Sequence[Event]) -> dict[str, Any]:
    if log.error is not None:
        return {"attempt": log.attempt, "codes": [log.error.code], "message": describe_rejection(log, []),
                "template": None, "text": None, "claims": [], "lint": [], "verify_failures": []}
    failures = verify_failures(log, events)
    draft = log.draft
    return {
        "attempt": log.attempt,
        "codes": [i.code for i in log.items],
        "message": describe_rejection(log, failures),
        "template": draft.template if draft else None,
        "text": draft.text if draft and draft.template is None else None,
        "claims": [{"id": cid, **c.to_dict()} for cid, c in zip(log.claim_ids, log.claims)],
        "lint": [{"code": i.code, "fragment": i.fragment} for i in log.lint_issues],
        "verify_failures": failures,
    }


def _trace_message(record: NarrationRecord, attempt: int) -> str:
    """Without an attempt record (old call), the rejection message comes from the trace: lint fragments + verify reasons."""
    parts = []
    for step in record.trace:
        if step.get("attempt") != attempt:
            continue
        if step["step"] == "lint":
            parts += [f"lint {i['code']} {i['fragment']!r}" for i in step["issues"]]
        elif step["step"] == "verify":
            parts += [f"verify claim[{r['claim_index']}] {r['reason']}" for r in step["results"] if not r["ok"]]
    return " | ".join(parts) or "rejected"


def rejections(record: NarrationRecord) -> list[dict[str, Any]]:
    """Rejection codes and message per attempt (from the trace; no draft text)."""
    by_attempt: dict[int, dict[str, Any]] = {}
    for step in record.trace:
        if step["step"] == "narrate" and not step["ok"]:
            by_attempt[step["attempt"]] = {
                "attempt": step["attempt"], "codes": [step["error"]], "message": step.get("message"),
            }
        elif step["step"] == "feedback":
            entry = by_attempt.setdefault(step["attempt"], {"attempt": step["attempt"], "message": None})
            entry["codes"] = list(step["codes"])
            if entry["message"] is None:
                entry["message"] = _trace_message(record, step["attempt"])
    return [by_attempt[a] for a in sorted(by_attempt)]


def collect_match(
    match_id: str,
    results: Sequence[tuple[Moment, NarrationRecord]],
    usage: Sequence[Any],
    attempts: Sequence[AttemptLog] | None = None,
    events: Sequence[Event] | None = None,
) -> dict[str, Any]:
    """With `attempts` (measurement mode), every rejected attempt is stored with its draft."""
    logs: dict[str, list[AttemptLog]] = defaultdict(list)
    for log in attempts or ():
        logs[log.moment.id].append(log)
    moments = []
    for m, r in results:
        fallback = r.source == "template_fallback"
        if attempts is not None and events is not None:
            rejected = [attempt_entry(log, events) for log in logs[m.id] if not log.accepted]
        else:
            rejected = rejections(r)
        moments.append({
            "id": m.id,
            "type": m.type,
            "period": m.period,
            "minute": m.minute,
            "second": m.second,
            "source": r.source,
            "attempts": r.attempts,
            "ok": r.ok,
            "text": r.text,
            "template": r.template,
            "fallback_reason": r.trace[-1].get("reason") if fallback else None,
            "rejections": rejected,
        })
    return {
        "match_id": match_id,
        "moments": moments,
        "usage": [asdict(u) if not isinstance(u, dict) else u for u in usage],
    }


# --- aggregation -------------------------------------------------------------------------------


def runs_of(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Runs; the old single-run format is a one-element list."""
    if "runs" in run:
        return run["runs"]
    return [{"started_at": run["meta"].get("started_at"), "finished_at": run["meta"].get("finished_at"),
             "matches": run["matches"]}]


def _rejected(matches: Sequence[dict[str, Any]]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    return [(m["match_id"], mo, r) for m in matches for mo in m["moments"] for r in mo["rejections"]]


def summarize(match: dict[str, Any]) -> dict[str, Any]:
    moments, usage = match["moments"], match["usage"]
    latencies = [u["latency_ms"] for u in usage]
    output = sum(u["output_tokens"] or 0 for u in usage)
    reasoning = sum(u.get("reasoning_tokens") or 0 for u in usage)
    rejected = [r for mo in moments for r in mo["rejections"]]
    return {
        "moments": len(moments),
        "first_try": sum(m["source"] != "template_fallback" and m["attempts"] == 1 for m in moments),
        "after_retry": sum(m["source"] != "template_fallback" and m["attempts"] > 1 for m in moments),
        "fallback": sum(m["source"] == "template_fallback" for m in moments),
        "calls": len(usage),
        "rejected": len(rejected),
        "evidence_mismatch": sum("evidence_mismatch" in r["codes"] for r in rejected),
        "input_tokens": sum(u["input_tokens"] or 0 for u in usage),
        "output_tokens": output,
        "reasoning_tokens": reasoning,
        "latencies": latencies,
    }


def _total(summaries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    keys = ("moments", "first_try", "after_retry", "fallback", "calls", "rejected", "evidence_mismatch",
            "input_tokens", "output_tokens", "reasoning_tokens")
    total: dict[str, Any] = {k: sum(s[k] for s in summaries) for k in keys}
    total["latencies"] = [ms for s in summaries for ms in s["latencies"]]
    return total


def run_total(run: dict[str, Any]) -> dict[str, Any]:
    return _total([summarize(m) for m in run["matches"]])


# --- report ---------------------------------------------------------------------------------


def _share(n: int, total: int) -> str:
    return f"{n} ({n / total * 100:.1f}%)" if total else "0"


def _sec(ms: float) -> str:
    return f"{ms / 1000:.1f} sn"


def _minute(m: dict[str, Any]) -> str:
    if m["period"] == 1 and m["minute"] >= 45:
        return f"45+{m['minute'] - 44}'"
    if m["period"] == 2 and m["minute"] >= 90:
        return f"90+{m['minute'] - 89}'"
    return f"{m['minute']}'"


def _codes(codes: Sequence[str]) -> str:
    counts = Counter(codes)
    return ", ".join(f"`{c}`" + (f"×{n}" if n > 1 else "") for c, n in counts.items())


def _cell(text: str | None) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def _short(moment_id: str) -> str:
    return moment_id.rsplit("-", 1)[-1]


def _types(items: Sequence[dict[str, Any]]) -> str:
    counts = Counter(r["type"] for r in items)
    return ", ".join(f"{t}×{n}" for t, n in sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))) or "—"


def _diff(a: Sequence[dict[str, Any]], b: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Events in a but not in b (by id)."""
    ids = {r["id"] for r in b}
    return [r for r in a if r["id"] not in ids]


def _summary_table(rows: Sequence[tuple[str, dict[str, Any]]]) -> list[str]:
    out = [
        "| Match | Moment | Passed first try | Passed after retry | Fell back | Calls "
        "| Tokens in / out | Reasoning (% of output) | Avg. duration | Median | Max. |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, s in rows:
        n, lat = s["moments"], s["latencies"]
        ratio = s["reasoning_tokens"] / s["output_tokens"] * 100 if s["output_tokens"] else 0.0
        out.append(
            f"| {name} | {n} | {_share(s['first_try'], n)} | {_share(s['after_retry'], n)} | "
            f"{_share(s['fallback'], n)} | {s['calls']} | {s['input_tokens']} / {s['output_tokens']} | "
            f"{s['reasoning_tokens']} ({ratio:.1f}%) | "
            f"{_sec(statistics.fmean(lat)) if lat else '—'} | "
            f"{_sec(statistics.median(lat)) if lat else '—'} | {_sec(max(lat)) if lat else '—'} |"
        )
    return out


def _version_rows(label: str, run: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    runs = runs_of(run)
    totals = [run_total(r) for r in runs]
    if len(runs) == 1:
        return [(label, totals[0])]
    rows = [(f"{label} · run {i}", t) for i, t in enumerate(totals, start=1)]
    return [*rows, (f"**{label} · total ({len(runs)} runs)**", _total(totals))]


def render_comparison(run: dict[str, Any], baselines: dict[str, dict[str, Any]]) -> list[str]:
    version = run["meta"]["prompt_version"].split(":", 1)[0]
    rows = [r for label, base in baselines.items() for r in _version_rows(label, base)]
    rows += _version_rows(version, run)
    out = [
        f"## Version comparison: {', '.join([*baselines, version])}",
        "",
        "Earlier versions come from the archived raw outputs (`docs/LLM_RUN.<version>.json`). Rejected = an attempt "
        "that was not published; the `evidence_mismatch` column counts rejected attempts with that code.",
        "",
        "| Version / run | Moments | First try | After retry | Fell back | Calls | Rejected attempts "
        "| evidence_mismatch | Tokens out |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, s in rows:
        out.append(f"| {name} | {s['moments']} | {s['first_try']} | {s['after_retry']} | {s['fallback']} | "
                   f"{s['calls']} | {s['rejected']} | {s['evidence_mismatch']} | {s['output_tokens']} |")
    # evidence_mismatch per moment type
    types = sorted({mo["type"] for r in [run, *baselines.values()] for rr in runs_of(r)
                    for m in rr["matches"] for mo in m["moments"]})
    labels = [*baselines, version]
    counts = {
        label: Counter(mo["type"] for rr in runs_of(r) for _, mo, rej in _rejected(rr["matches"])
                       if "evidence_mismatch" in rej["codes"])
        for label, r in [*baselines.items(), (version, run)]
    }
    n_runs = {label: len(runs_of(r)) for label, r in [*baselines.items(), (version, run)]}
    out += [
        "",
        "Rejected attempts with `evidence_mismatch`, per moment type (all runs of the version; "
        "number of runs in parentheses):",
        "",
        "| Moment type | " + " | ".join(f"{label} ({n_runs[label]})" for label in labels) + " |",
        "|---|" + "---:|" * len(labels),
    ]
    for t in types:
        out.append(f"| {t} | " + " | ".join(str(counts[label][t]) for label in labels) + " |")
    return out


def render_code_frequency(run: dict[str, Any], baselines: dict[str, dict[str, Any]]) -> list[str]:
    """Rejection code frequency per version (average per run; number of codes in rejected attempts)."""
    version = run["meta"]["prompt_version"].split(":", 1)[0]
    versions = [*baselines.items(), (version, run)]
    counts = {
        label: Counter(c for rr in runs_of(r) for _, _, rej in _rejected(rr["matches"]) for c in rej["codes"])
        for label, r in versions
    }
    n_runs = {label: len(runs_of(r)) for label, r in versions}
    codes = sorted({c for cnt in counts.values() for c in cnt}, key=lambda c: (-sum(cnt[c] for cnt in counts.values()), c))
    out = [
        "## Rejection code frequency",
        "",
        "Codes in rejected attempts, average per run (an attempt can have more than one code).",
        "",
        "| Code | " + " | ".join(f"{label} ({n_runs[label]} runs)" for label, _ in versions) + " |",
        "|---|" + "---:|" * len(versions),
    ]
    for code in codes:
        cells = [f"{counts[label][code] / n_runs[label]:.1f}".rstrip("0").rstrip(".") if counts[label][code] else "0"
                 for label, _ in versions]
        out.append(f"| `{code}` | " + " | ".join(cells) + " |")
    return [*out, ""]


def render_side_by_side(run: dict[str, Any], baselines: dict[str, dict[str, Any]]) -> list[str]:
    """Published text of the same moments, version by version (last run for multi-run versions)."""
    version = run["meta"]["prompt_version"].split(":", 1)[0]
    versions = [*baselines.items(), (version, run)]
    texts: dict[str, dict[str, tuple[str, str]]] = {}
    for label, r in versions:
        for m in runs_of(r)[-1]["matches"]:
            for mo in m["moments"]:
                texts.setdefault(mo["id"], {})[label] = (mo["source"], mo["text"])
    order = [(m["match_id"], mo) for m in runs_of(run)[-1]["matches"] for mo in m["moments"]]
    out = [
        "## Side by side: the same moments, version by version",
        "",
        "Published text; the last run for multi-run versions. *(fallback)* = template fallback.",
        "",
        "| Moment | Type | " + " | ".join(label for label, _ in versions) + " |",
        "|---|---|" + "---|" * len(versions),
    ]
    for match_id, mo in order:
        cells = []
        for label, _ in versions:
            source, text = texts.get(mo["id"], {}).get(label, (None, None))
            mark = "*(fallback)* " if source == "template_fallback" else ""
            cells.append(f"{mark}{_cell(text)}" if text is not None else "—")
        out.append(f"| {match_id.split('_seed')[0]} {_short(mo['id'])} | {mo['type']} | " + " | ".join(cells) + " |")
    return [*out, ""]


def render_evidence_groups(run: dict[str, Any]) -> list[str]:
    """evidence_mismatch rejections: which events the model cited for which claim, and what the verifier counted."""
    groups: Counter[tuple[str, ...]] = Counter()
    examples: list[str] = []
    for rr in runs_of(run):
        for _, mo, rej in _rejected(rr["matches"]):
            if len(examples) < 6 and any(f["reason"] == "evidence_mismatch" for f in rej.get("verify_failures", [])):
                examples.append(f"- `{_short(mo['id'])}` ({mo['type']}) #{rej['attempt']}: "
                                f"`{_cell(rej.get('template'))}` → {_cell(rej['message'])}")
            for f in rej.get("verify_failures", []):
                if f["reason"] != "evidence_mismatch":
                    continue
                c = f["claim"]
                claim = f"{c['kind']} {c['metric']} {c['subject']['team'] or '—'}" + (
                    " + player" if c["subject"]["player"] else "")
                groups[(mo["type"], claim, f["window"], _types(f["cited"]), _types(f["counted"]),
                         _types(_diff(f["counted"], f["cited"])), _types(_diff(f["cited"], f["counted"])))] += 1
    out = ["## evidence_mismatch: cited and counted events", ""]
    if not groups:
        return [*out, "No `evidence_mismatch` rejections in this run (foundry-v5: code builds the claims and their evidence, "
                      "the model links no events). Earlier versions' breakdown can be re-rendered from the archived JSONs.", ""]
    out += [
        "Each row is a group of rejected claims. Cited = the model's `event_ids`; counted = the events the verifier "
        "counted for the same subject, metric and range. Missing = counted but not cited, extra = cited "
        "but not counted.",
        "",
        "| Moment type | Claim | Range | Cited | Counted | Missing | Extra | Count |",
        "|---|---|---|---|---|---|---|---:|",
    ]
    for key, n in sorted(groups.items(), key=lambda kv: (-kv[1], kv[0])):
        out.append("| " + " | ".join(_cell(k) for k in key) + f" | {n} |")
    by_type = Counter()
    for key, n in groups.items():
        by_type[key[0]] += n
    out += ["", "Per moment type (rejected claims): " + ", ".join(
        f"{t} {n}" for t, n in by_type.most_common()) + ".", "", "Example rejection messages:", "", *examples, ""]
    return out


def render_rule_hits(run: dict[str, Any]) -> list[str]:
    """Live firing of the v4.1 rules: attempts that contain the rule, and attempts rejected by that rule alone."""
    rejected = [rej for rr in runs_of(run) for _, _, rej in _rejected(rr["matches"]) if "lint" in rej]
    out = [
        "## Live firing of the foundry-v4.1 / v5 rules",
        "",
        "This rule only = the rule was the attempt's only rejection reason (no other lint or verify error): "
        "without the rule it would have been published. A correct rejection if it is the pattern the rule targets, "
        "otherwise a false alarm; drafts below.",
        "",
        "| Rule | Attempts fired | This rule only | Fragments |",
        "|---|---:|---:|---|",
    ]
    only: list[tuple[str, dict[str, Any]]] = []
    for rule in NEW_RULES:
        hits = [rej for rej in rejected if rule in rej["codes"]]
        alone = [rej for rej in hits if set(rej["codes"]) == {rule}]
        only += [(rule, rej) for rej in alone]
        fragments = Counter(i["fragment"] for rej in hits for i in rej["lint"] if i["code"] == rule)
        out.append(f"| `{rule}` | {len(hits)} | {len(alone)} | "
                   f"{', '.join(f'`{_cell(f)}`×{n}' for f, n in fragments.most_common(8)) or '—'} |")
    if only:
        out += ["", "Drafts rejected by a new rule alone:", ""]
        out += [f"- `{rule}`: `{_cell(rej['template'])}`" for rule, rej in only]
    return [*out, ""]


def render_report(run: dict[str, Any], baselines: dict[str, dict[str, Any]] | None = None) -> str:
    meta = run["meta"]
    runs = runs_of(run)
    current = meta["prompt_version"].split(":", 1)[0]
    baselines = {label: b for label, b in (baselines or {}).items() if label != current}

    out = [
        "# LLM narration measurement (real model)",
        "",
        "This file is built from the raw output of a `python -m eval.llm_run` run (`docs/LLM_RUN.json`); "
        "do not edit it by hand.",
        "",
        f"- Model: `{meta['model']}` · Prompt version: `{meta['prompt_version']}` · Language: `{meta['lang']}` "
        f"· Reasoning effort: `{meta.get('reasoning_effort') or 'default'}`",
        f"- Run: {meta['started_at']} – {meta['finished_at']} (UTC)"
        + (f", {len(runs)} runs (same prompt)" if len(runs) > 1 else ""),
        f"- Settings: at most {meta['max_calls_per_run']} calls per run (match), "
        f"`max_output_tokens` {meta['max_tokens']}, call timeout {meta['timeout_s']:g} s, "
        f"at most {meta['max_retries']} retries, cache off",
        "- Every draft went through lint + placeholder binding + verify_claim; a draft that failed was not published "
        "and fell back to the template. Code rendered the concrete values in the published LLM texts.",
        "",
        "## Summary",
        "",
    ]
    totals = []
    for i, rr in enumerate(runs, start=1):
        summaries = [summarize(m) for m in rr["matches"]]
        totals.append(_total(summaries))
        if len(runs) > 1:
            out += [f"### Run {i} ({rr['started_at']} – {rr['finished_at']})", ""]
        rows = [(m["match_id"], s) for m, s in zip(rr["matches"], summaries)]
        out += _summary_table([*rows, ("**Total**", totals[-1])])
        out.append("")
    if len(runs) > 1:
        out += ["### Fallbacks per run", "",
                "| Run | Moments | Fell back | Rejected attempts | evidence_mismatch |", "|---|---:|---:|---:|---:|"]
        for i, t in enumerate(totals, start=1):
            out.append(f"| {i} | {t['moments']} | {t['fallback']} | {t['rejected']} | {t['evidence_mismatch']} |")
        grand = _total(totals)
        out += [f"| **Total** | {grand['moments']} | {grand['fallback']} | {grand['rejected']} | "
                f"{grand['evidence_mismatch']} |", ""]

    out += [*render_comparison(run, baselines), ""]
    out += render_code_frequency(run, baselines)
    out += render_side_by_side(run, baselines)
    out += render_evidence_groups(run)
    out += render_rule_hits(run)

    multi = len(runs) > 1
    run_col = "Run | " if multi else ""
    run_sep = "---|" if multi else ""

    def tag(i: int) -> str:
        return f"{i} | " if multi else ""

    out += ["## Moments that fell back", ""]
    fallbacks = [(i, m["match_id"], mo) for i, rr in enumerate(runs, start=1) for m in rr["matches"]
                 for mo in m["moments"] if mo["source"] == "template_fallback"]
    if not fallbacks:
        out.append("None.")
    else:
        out += [f"| {run_col}Match | Moment | Type | Minute | Fallback reason | Rejection codes per attempt |",
                f"|{run_sep}---|---|---|---|---|---|"]
        for i, match_id, mo in fallbacks:
            per_attempt = "; ".join(f"#{r['attempt']}: {_codes(r['codes'])}" for r in mo["rejections"])
            out.append(f"| {tag(i)}{match_id} | {_short(mo['id'])} | {mo['type']} | {_minute(mo)} | "
                       f"`{mo['fallback_reason']}` | {per_attempt} |")
        all_codes = Counter(c for _, _, mo in fallbacks for r in mo["rejections"] for c in r["codes"])
        out += ["", "Rejection code frequency in moments that fell back: " + _codes(list(all_codes.elements()))]

    out += ["", "## Moments that passed after a retry", ""]
    retried = [(i, m["match_id"], mo) for i, rr in enumerate(runs, start=1) for m in rr["matches"]
               for mo in m["moments"] if mo["source"] != "template_fallback" and mo["attempts"] > 1]
    if not retried:
        out.append("None.")
    else:
        out += [f"| {run_col}Match | Moment | Type | Attempts | Rejected attempts |", f"|{run_sep}---|---|---|---:|---|"]
        for i, match_id, mo in retried:
            per_attempt = "; ".join(f"#{r['attempt']}: {_codes(r['codes'])}" for r in mo["rejections"])
            out.append(f"| {tag(i)}{match_id} | {_short(mo['id'])} | {mo['type']} | {mo['attempts']} | {per_attempt} |")

    drafts = [(i, match_id, mo, rej) for i, rr in enumerate(runs, start=1)
              for match_id, mo, rej in _rejected(rr["matches"]) if "template" in rej]
    if drafts:
        out += ["", "## Rejected drafts", "",
                f"| {run_col}Match | Moment | Type | Attempt | Rejection codes | Model template | Rejection message |",
                f"|{run_sep}---|---|---|---:|---|---|---|"]
        for i, match_id, mo, rej in drafts:
            draft = rej.get("template") or rej.get("text")
            out.append(f"| {tag(i)}{match_id} | {_short(mo['id'])} | {mo['type']} | {rej['attempt']} | "
                       f"{_codes(rej['codes'])} | {f'`{_cell(draft)}`' if draft else '—'} | "
                       f"{_cell(rej['message'])} |")

    out += ["", "## Client errors", ""]
    errors = [(i, m["match_id"], u) for i, rr in enumerate(runs, start=1) for m in rr["matches"]
              for u in m["usage"] if u.get("error")]
    if not errors:
        out.append("None.")
    else:
        out += [f"| {run_col}Match | Moment | Call | Result | Message |", f"|{run_sep}---|---|---:|---|---|"]
        for i, match_id, u in errors:
            out.append(f"| {tag(i)}{match_id} | {_short(u['moment_id'])} | {u['call']} | `{u['outcome']}` | "
                       f"{_cell(u['error'])} |")

    out += ["", "## Moment details", ""]
    for i, rr in enumerate(runs, start=1):
        for m in rr["matches"]:
            title = f"Run {i} · {m['match_id']}" if multi else m["match_id"]
            out += [f"### {title}", "",
                    "| Moment | Type | Minute | Source | Attempts | Published text | Model template |",
                    "|---|---|---|---|---:|---|---|"]
            for mo in m["moments"]:
                template = f"`{_cell(mo.get('template'))}`" if mo.get("template") else "—"
                out.append(f"| {_short(mo['id'])} | {mo['type']} | {_minute(mo)} | {mo['source']} | "
                           f"{mo['attempts']} | {_cell(mo['text'])} | {template} |")
            out.append("")
    return "\n".join(out)


def load_baselines(paths: dict[str, Path] = BASELINES) -> dict[str, dict[str, Any]]:
    return {label: json.loads(p.read_text(encoding="utf-8")) for label, p in paths.items() if p.exists()}


# --- human review --------------------------------------------------------------------


def review_rows(run: dict[str, Any]) -> list[dict[str, str]]:
    """Published texts of the last run."""
    last = runs_of(run)[-1]
    return [
        {"moment_id": mo["id"], "text": mo["text"], "correct": "", "wrong_fact": "", "misleading": "", "dull": ""}
        for m in last["matches"] for mo in m["moments"] if mo["text"]
    ]


def _has_annotations(path: Path) -> bool:
    with path.open(encoding="utf-8", newline="") as fp:
        return any(
            (row.get(col) or "").strip()
            for row in csv.DictReader(fp) for col in REVIEW_COLUMNS[2:]
        )


def write_human_review(run: dict[str, Any], path: Path, stamp: str | None = None) -> Path:
    """Writes the CSV; never overwrites a hand-filled file (writes a timestamped one next to it)."""
    target = path
    if path.exists() and _has_annotations(path):
        stamp = stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = path.with_name(f"{path.stem}.{stamp}{path.suffix}")
        print(f"WARNING: {path} was filled in by hand; not overwritten → {target}", file=sys.stderr)
    with target.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(review_rows(run))
    return target


# --- run ----------------------------------------------------------------------------


def run_once(lang: str, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG) -> tuple[dict[str, Any], str, str]:
    """One run over the three demo matches; (run, model, prompt version)."""
    from app.explain.llm_narrator import foundry_narrator_from_env

    started = datetime.now(UTC).isoformat(timespec="seconds")
    matches, model, prompt_version = [], None, None
    for _, _, path in demo_paths():
        events = read_jsonl(path)
        narrator = foundry_narrator_from_env(events, config)
        model, prompt_version = narrator.model_tag, narrator.prompt_version
        print(f"== {path.stem}", file=sys.stderr)
        logs: list[AttemptLog] = []
        try:
            results = run_match(events, narrator, language=lang, cache=None, config=config,
                                on_attempt=logs.append)
        finally:
            narrator.close()
        matches.append(collect_match(path.stem, results, narrator.usage, logs, events))
    finished = datetime.now(UTC).isoformat(timespec="seconds")
    return {"started_at": started, "finished_at": finished, "matches": matches}, model, prompt_version


def run_live(lang: str, repeat: int = 1, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG) -> dict[str, Any]:
    started = datetime.now(UTC).isoformat(timespec="seconds")
    runs, model, prompt_version = [], None, None
    for i in range(1, repeat + 1):
        print(f"### run {i}/{repeat}", file=sys.stderr)
        one, model, prompt_version = run_once(lang, config)
        runs.append(one)
    return {
        "meta": {
            "model": model,
            "prompt_version": prompt_version,
            "lang": lang,
            "repeats": repeat,
            "started_at": started,
            "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "max_calls_per_run": config.llm_max_calls_per_run,
            "max_tokens": config.llm_max_tokens,
            "timeout_s": config.llm_timeout_s,
            "max_retries": config.max_retries,
            "reasoning_effort": config.llm_reasoning_effort,
        },
        "runs": runs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure the three demo matches with the real LLM")
    parser.add_argument("--lang", choices=("en",), default="en")
    parser.add_argument("--repeat", type=int, default=1, help="Number of runs with the same prompt")
    parser.add_argument("--from-json", help="Re-render from this raw output without calling the model")
    parser.add_argument("--out-json", default=str(DEFAULT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_MD))
    parser.add_argument("--out-csv", default=str(DEFAULT_CSV))
    args = parser.parse_args(argv)

    if args.from_json:
        run = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    else:
        logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)
        logging.getLogger("whyball.llm").setLevel(logging.INFO)
        run = run_live(args.lang, args.repeat)
        Path(args.out_json).write_text(
            json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Written: {args.out_json}", file=sys.stderr)
    Path(args.out_md).write_text(render_report(run, load_baselines()), encoding="utf-8")
    csv_path = write_human_review(run, Path(args.out_csv))
    print(f"Written: {args.out_md}, {csv_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
