"""Builds the publication store from the last LLM run, without calling a model.

For each demo match, the moments the selector picks are replayed from the model drafts of the
last run in docs/LLM_RUN.json (the placeholder template, not the rendered text): the draft goes
through the current pipeline (`run_moment`: text_lint, menu rules, verify_claim, render) once,
without retries. A draft that no longer passes falls back to the template narration
(`template_fallback`). Moments the selector does not pick get the template narration (`template`).

Report: cards whose re-rendered text differs from what the run published, template fallbacks,
and the same-second check (a claim ends at the moment's second, so `measure` also counts events
of that second that come after the moment's own event).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from app.analytics import detect_moments
from app.analytics.moments import Moment
from app.explain.claims import Claim, measure, parse_ref
from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.labels import metric_label
from app.explain.llm_narrator import PROMPT_VERSION
from app.explain.menu import build_menu
from app.explain.narrator import Draft, Feedback, NarratorError, TemplateNarrator
from app.explain.pipeline import AttemptLog, NarrationRecord, run_moment
from app.explain.selector import select_moments
from app.explain.slots import format_value
from app.explain.template_narrator import fmt_minute
from app.generator.freeze import demo_paths
from app.generator.models import Event, read_jsonl

from .schema import (
    SOURCES, EvidenceEvent, MatchStore, Segment, StoredChecks, StoredClaim, StoredMoment, TraceStep, Verification,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = REPO_ROOT / "docs" / "LLM_RUN.json"
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "demo_narration"
DEFAULT_REPORT = REPO_ROOT / "docs" / "DEMO_NARRATION.md"
LANGUAGE = "en"


class PublishError(Exception):
    """The store cannot be built (a card that is not verified is never published)."""


class NoDraft(NarratorError):
    code = "no_draft"
    retryable = False


class MomentMismatch(NarratorError):
    code = "moment_mismatch"
    retryable = False


class ReplayNarrator:
    """Narrator protocol over the stored drafts of one run: returns the run's placeholder template as a menu
    draft, so the pipeline binds, lints, verifies and renders it with the current code."""

    name = "replay"
    source = "llm"

    def __init__(
        self, events: Sequence[Event], run_moments: Sequence[dict[str, Any]], prompt_version: str,
        config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
    ) -> None:
        self.events = events
        self.moments = {m["id"]: m for m in run_moments}
        self.prompt_version = prompt_version
        self.config = config

    def narrate(
        self, moment: Moment, persona: str, language: str, feedback: Feedback | None = None
    ) -> Draft:
        rec = self.moments.get(moment.id)
        if rec is None:
            raise NoDraft(f"the run has no card for {moment.id}")
        run_at = (rec["type"], rec["period"], rec["minute"], rec["second"])
        if run_at != (moment.type, moment.period, moment.minute, moment.second):
            raise MomentMismatch(f"the run's {moment.id} is {run_at}, the detector's is "
                                 f"{(moment.type, moment.period, moment.minute, moment.second)}")
        if rec["source"] != "llm" or not rec.get("template"):
            raise NoDraft(f"the run published no model draft for {moment.id} (source={rec['source']})")
        return Draft("", (), template=rec["template"], menu=build_menu(moment, self.events, self.config))


# --- report entries --------------------------------------------------------------------------------


@dataclass(frozen=True)
class TextDiff:
    match_id: str
    moment_id: str
    old: str
    new: str


@dataclass(frozen=True)
class Fallback:
    match_id: str
    moment_id: str
    codes: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class ClaimDrift:
    claim_id: str
    full: float  # measured with every event up to the claim's end second
    truncated: float  # measured with events up to the moment's own event (at_seq)


@dataclass(frozen=True)
class SameSecond:
    match_id: str
    moment_id: str
    moment_type: str
    minute_label: str
    selected: bool
    source: str
    later_events: tuple[str, ...]  # "#350 goal"
    menu: tuple[ClaimDrift, ...]
    published: tuple[ClaimDrift, ...]  # claims of the published card

    @property
    def affects_card(self) -> bool:
        return bool(self.published)


@dataclass(frozen=True)
class SegmentStat:
    """What the segments of one card say about its claims (report only)."""

    match_id: str
    moment_id: str
    source: str
    with_claim: int  # segments that carry a claim id
    unplaced: tuple[tuple[str, str], ...]  # (claim id, metric) of claims with no value in the sentence
    mismatched: tuple[str, ...]  # claim ids whose segment text differs from the claim's `display`
    plain_digits: int  # plain segments that contain a digit (minutes in phrases, names with digits...)


@dataclass
class BuildResult:
    run_id: str
    run_file: str
    prompt_version: str
    stores: list[MatchStore] = field(default_factory=list)
    diffs: list[TextDiff] = field(default_factory=list)
    fallbacks: list[Fallback] = field(default_factory=list)
    same_second: list[SameSecond] = field(default_factory=list)
    unused_run_cards: list[str] = field(default_factory=list)  # run cards the current selector does not pick
    segment_stats: list[SegmentStat] = field(default_factory=list)
    verifications: list[tuple[str, str, str, str]] = field(default_factory=list)  # (source, verifier, label, trace?)
    trace_dropped: list[str] = field(default_factory=list)  # run traces not stored: the current code decided otherwise


# --- building ---------------------------------------------------------------------------------------


def run_id_of(meta: dict[str, Any], run: dict[str, Any]) -> str:
    """The run file has no id; it is derived from the prompt version and the run's start time."""
    return f"{meta['prompt_version']}@{run['started_at']}"


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _template_ids(claims: Sequence[Claim]) -> tuple[str, ...]:
    """Ids for claims without a menu id: metric + side, numbered when repeated."""
    ids: list[str] = []
    for c in claims:
        base = c.metric if c.subject.team is None else f"{c.metric}_{c.subject.team}"
        cid, n = base, 1
        while cid in ids:
            n += 1
            cid = f"{base}_{n}"
        ids.append(cid)
    return tuple(ids)


def _evidence(claim: Claim, by_seq: dict[int, Event]) -> list[EvidenceEvent]:
    out = []
    for ref in claim.event_ids:
        e = by_seq[parse_ref(ref)[1]]
        out.append(EvidenceEvent(
            id=ref, seq=e.seq, type=e.type.value, team=e.team, player=e.player, period=e.period,
            minute=e.minute, second=e.second, minute_label=fmt_minute(e.period, e.minute),
        ))
    return out


def _claims(claims: Sequence[Claim], ids: Sequence[str], by_seq: dict[int, Event]) -> list[StoredClaim]:
    return [
        StoredClaim(
            id=cid, kind=c.kind, metric=c.metric, label=metric_label(c.metric, LANGUAGE),
            team=c.subject.team, player=c.subject.player, comparison=c.comparison, value=c.value,
            display=format_value(c.metric, c.value, LANGUAGE),
            start=fmt_minute(c.start.period, c.start.minute), end=fmt_minute(c.end.period, c.end.minute),
            evidence=_evidence(c, by_seq),
        )
        for cid, c in zip(ids, claims)
    ]


def _drift(claims: Sequence[Claim], ids: Sequence[str], events: Sequence[Event],
           upto: Sequence[Event]) -> tuple[ClaimDrift, ...]:
    out = []
    for cid, c in zip(ids, claims):
        full = measure(c.metric, c.subject, c.start, c.end, events)
        cut = measure(c.metric, c.subject, c.start, c.end, upto)
        if full.value != cut.value or full.counted != cut.counted:
            out.append(ClaimDrift(cid, full.value, cut.value))
    return tuple(out)


def _fallback_codes(logs: Sequence[AttemptLog]) -> tuple[tuple[str, ...], str]:
    log = logs[-1]
    if log.error is not None:
        return (log.error.code,), str(log.error)
    codes = tuple(i.code for i in log.items)
    parts = [i.code + (f" {i.fragment!r}" if i.fragment else "") for i in log.items]
    return codes, "; ".join(parts)


def build_match(
    match_id: str,
    events_path: Path,
    run_moments: Sequence[dict[str, Any]],
    run_id: str,
    prompt_version: str,
    result: BuildResult,
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
) -> MatchStore:
    events = read_jsonl(events_path)
    by_seq = {e.seq: e for e in events}
    index = {e.seq: i for i, e in enumerate(events)}
    moments = detect_moments(events)
    selected = {m.id for m in select_moments(moments, config)}
    run_by_id = {m["id"]: m for m in run_moments}
    replay = ReplayNarrator(events, run_moments, prompt_version, config)
    template = TemplateNarrator(events, config)
    once = replace(config, max_retries=0)

    cards = []
    extra_used: set[str] = set()
    for m in moments:
        logs: list[AttemptLog] = []
        # Model cards for the selected moments; an agent run can also have written cards for the others (`--moments all`).
        agent_card = "verification" in run_by_id.get(m.id, {}) and run_by_id[m.id].get("source") == "llm"
        if agent_card:
            extra_used.add(m.id)
        if m.id in selected or agent_card:
            rec = run_moment(m, replay, events, language=LANGUAGE, config=once, on_attempt=logs.append)
        else:
            rec = run_moment(m, template, events, language=LANGUAGE, config=config)
        if not rec.ok or not rec.text.strip():
            raise PublishError(f"{m.id}: the {rec.source} narration does not pass lint and verify")
        ids = _ids(rec, logs)
        if rec.source == "template_fallback":
            codes, message = _fallback_codes(logs)
            result.fallbacks.append(Fallback(match_id, m.id, codes, message))
        old = run_by_id.get(m.id, {}).get("text")
        if rec.source == "llm" and old is not None and old != rec.text:
            result.diffs.append(TextDiff(match_id, m.id, old, rec.text))

        menu = build_menu(m, events, config)
        upto = events[: index[m.at_seq] + 1]
        later = [e for e in events[index[m.at_seq] + 1:]
                 if (e.period, e.minute, e.second) == (m.period, m.minute, m.second)]
        menu_drift = _drift([c.claim for c in menu.claims], [c.id for c in menu.claims], events, upto)
        card_drift = _drift(rec.claims, ids, events, upto)
        if menu_drift or card_drift:
            result.same_second.append(SameSecond(
                match_id, m.id, m.type, _clock(m), m.id in selected, rec.source,
                tuple(f"#{e.seq} {e.type.value}" for e in later), menu_drift, card_drift,
            ))

        verification, trace = _agent_record(rec, run_by_id.get(m.id, {}), match_id, result)
        result.verifications.append((rec.source, verification.verifier, verification.label_source,
                                     "trace" if trace else "no trace"))
        claims = _claims(rec.claims, ids, by_seq)
        segments = _segments(rec, ids, claims)
        result.segment_stats.append(_segment_stat(match_id, m.id, rec.source, segments, claims))
        cards.append(StoredMoment(
            id=m.id, period=m.period, minute=m.minute, second=m.second,
            minute_label=fmt_minute(m.period, m.minute), at_seq=m.at_seq, type=m.type, team=m.team,
            importance=m.importance, text=rec.text, segments=segments, source=rec.source,
            prompt_version=prompt_version if rec.source == "llm" else config.template_prompt_version,
            run_id=None if rec.source == "template" else run_id,
            claims=claims, trace=trace, verification=verification,
            checks=StoredChecks(
                lint_issues=len(rec.lint_issues), claims_total=len(rec.verification),
                claims_verified=sum(r.ok for r in rec.verification),
            ),
        ))
    result.unused_run_cards += sorted(set(run_by_id) - selected - extra_used)

    teams = events[0].data["teams"]
    return MatchStore(
        match_id=match_id, event_match_id=events[0].match_id, events_file=_rel(events_path),
        events_sha256=hashlib.sha256(events_path.read_bytes()).hexdigest(),
        teams={side: teams[side]["name"] for side in ("home", "away")},
        final_score=events[-1].score, run_id=run_id, prompt_version=prompt_version, moments=cards,
    )


def _segments(rec: NarrationRecord, ids: Sequence[str], claims: Sequence[StoredClaim]) -> list[Segment]:
    """The card text in pieces; a piece's claim index becomes the claim id. Never published if it does not add up."""
    if "".join(p.text for p in rec.parts) != rec.text:
        raise PublishError(f"{rec.moment_id}: the text pieces do not join to the card text")
    known = {c.id for c in claims}
    out = []
    for p in rec.parts:
        cid = None if p.claim is None else ids[p.claim]
        if cid is not None and cid not in known:
            raise PublishError(f"{rec.moment_id}: a text piece names the unknown claim {cid!r}")
        out.append(Segment(text=p.text, claim_id=cid))
    return out


def _segment_stat(match_id: str, moment_id: str, source: str, segments: Sequence[Segment],
                  claims: Sequence[StoredClaim]) -> SegmentStat:
    shown = {s.claim_id for s in segments if s.claim_id}
    by_id = {c.id: c for c in claims}
    return SegmentStat(
        match_id, moment_id, source,
        with_claim=sum(s.claim_id is not None for s in segments),
        unplaced=tuple((c.id, c.metric) for c in claims if c.id not in shown),
        mismatched=tuple(s.claim_id for s in segments if s.claim_id and s.text != by_id[s.claim_id].display),
        plain_digits=sum(s.claim_id is None and any(ch.isdigit() for ch in s.text) for s in segments),
    )


MAX_ATTEMPTS = 3
DEFAULT_LABEL = {"llm": "guard_only", "template": "template", "template_fallback": "template_fallback"}


def _agent_record(rec: NarrationRecord, run_rec: dict[str, Any], match_id: str, result: BuildResult
                  ) -> tuple[Verification, list[dict[str, Any]]]:
    """Verification and trace of a card. A run that came from the agent workflow carries both; they are kept only when the
    current code publishes the same kind of card the run did (else the trace would describe another text). Cards of
    older runs and template cards get the plain defaults: Guard passed, no meaning check ran."""
    attempts = min(max(int(run_rec.get("attempts") or 1), 1), MAX_ATTEMPTS)
    default = Verification(guard=True, verifier="not_run", attempts=1 if rec.source == "template" else attempts,
                           label_source=DEFAULT_LABEL[rec.source])
    if "verification" not in run_rec and not run_rec.get("trace"):
        return default, []
    if run_rec.get("source") != rec.source:
        result.trace_dropped.append(f"{match_id}/{rec.moment_id}: run {run_rec.get('source')} → published {rec.source}")
        return default, []
    verification = Verification.model_validate(run_rec.get("verification") or default.model_dump())
    trace = [TraceStep.model_validate(s).model_dump(mode="json") for s in run_rec.get("trace", [])]
    _check_agent_record(rec, verification, trace)
    return verification, trace


def _check_agent_record(rec: NarrationRecord, v: Verification, trace: list[dict[str, Any]]) -> None:
    """A card never claims a check its trace does not show."""
    where = rec.moment_id
    if not 1 <= v.attempts <= MAX_ATTEMPTS:
        raise PublishError(f"{where}: attempts {v.attempts} outside 1..{MAX_ATTEMPTS}")
    expect = {"llm": ("llm",) if v.verifier in ("passed", "retried_then_passed") else ("guard_only",),
              "template": ("template",), "template_fallback": ("template_fallback",)}[rec.source]
    if v.label_source not in expect:
        raise PublishError(f"{where}: label_source {v.label_source!r} does not fit {rec.source}/{v.verifier}")
    if rec.source != "llm" and v.verifier != "not_run":
        raise PublishError(f"{where}: a {rec.source} card cannot carry a verifier result")
    if not trace:
        if v.verifier != "not_run":
            raise PublishError(f"{where}: verifier {v.verifier!r} without a trace")
        return
    if any(s["attempt"] > MAX_ATTEMPTS for s in trace):
        raise PublishError(f"{where}: a trace step beyond attempt {MAX_ATTEMPTS}")
    if trace[-1]["step"] != "finalize":
        raise PublishError(f"{where}: the trace does not end with finalize")
    verdicts = [s for s in trace if s["step"] == "verify" and s["output"].get("verdict") == "pass"]
    if v.verifier in ("passed", "retried_then_passed") and not verdicts:
        raise PublishError(f"{where}: verifier {v.verifier!r} without a passing verify step")
    if v.verifier == "skipped_error" and not any(s["step"] == "verifier_error" for s in trace):
        raise PublishError(f"{where}: skipped_error without a verifier_error step")
    if v.verifier == "not_run" and verdicts:
        raise PublishError(f"{where}: not_run, but the trace holds a passing verify step")


def _ids(rec: NarrationRecord, logs: Sequence[AttemptLog]) -> tuple[str, ...]:
    """Menu ids of an accepted model draft; generated ids for template narrations."""
    if rec.source == "llm":
        accepted = [log for log in logs if log.accepted]
        return accepted[-1].claim_ids
    return _template_ids(rec.claims)


def _clock(m: Moment) -> str:
    return f"{fmt_minute(m.period, m.minute)} ({m.minute:02d}:{m.second:02d})"


def build(
    run_path: Path = DEFAULT_RUN,
    demo: Sequence[tuple[str | None, int, Path]] | None = None,
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
) -> BuildResult:
    data = json.loads(Path(run_path).read_text(encoding="utf-8"))
    meta, run = data["meta"], data["runs"][-1]
    if meta.get("dry_run"):
        raise PublishError(f"{run_path} is a dry run (a scripted client, no model): it is never published")
    run_id = run_id_of(meta, run)
    result = BuildResult(run_id=run_id, run_file=_rel(Path(run_path)), prompt_version=meta["prompt_version"])
    run_matches = {m["match_id"]: m["moments"] for m in run["matches"]}
    for _, _, path in demo or demo_paths():
        match_id = path.stem
        result.stores.append(build_match(
            match_id, path, run_matches.get(match_id, []), run_id, meta["prompt_version"], result, config,
        ))
    return result


# --- output -----------------------------------------------------------------------------------------


def dumps(store: MatchStore) -> str:
    return json.dumps(store.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _drifts(items: Sequence[ClaimDrift]) -> str:
    return ", ".join(f"`{d.claim_id}` {d.full:g} → {d.truncated:g}" for d in items) or "—"


def render_report(result: BuildResult) -> str:
    base = result.prompt_version.split(":", 1)[0]
    lines = [
        "# Demo narration store",
        "",
        f"Generated by `python -m app.publish` from `{result.run_file}`, last run `{result.run_id}`. "
        "Do not edit by hand. No model is called: each selected moment replays the run's model draft "
        "(placeholder template) through the current pipeline once (text_lint, menu rules, verify_claim, "
        "render); a draft that no longer passes falls back to the template. Moments the selector does not "
        "pick get the template narration.",
        "",
        "## Cards",
        "",
        "| Match | Cards | " + " | ".join(SOURCES) + " |",
        "|---|---:|" + "---:|" * len(SOURCES),
    ]
    for s in result.stores:
        counts = [sum(m.source == src for m in s.moments) for src in SOURCES]
        lines.append(f"| `{s.match_id}` | {len(s.moments)} | " + " | ".join(map(str, counts)) + " |")
    lines += [
        "",
        "## Prompt version",
        "",
        f"Run: `{result.prompt_version}`; current code: `{PROMPT_VERSION}` — "
        + ("same." if base == PROMPT_VERSION else "**differs**: the drafts were written for another prompt."),
        "",
        "## Re-rendered text differs from the run",
        "",
        "The same draft rendered with the current code reads differently from what the run published.",
        "",
    ]
    if result.diffs:
        lines += ["| Card | Published by the run | Re-rendered now |", "|---|---|---|"]
        lines += [f"| `{d.moment_id}` | {_cell(d.old)} | {_cell(d.new)} |" for d in result.diffs]
    else:
        lines.append("None.")
    lines += ["", "## Template fallbacks", "", "Drafts that no longer pass with the current code.", ""]
    if result.fallbacks:
        lines += ["| Card | Codes | Message |", "|---|---|---|"]
        lines += [f"| `{f.moment_id}` | {', '.join(f'`{c}`' for c in f.codes)} | {_cell(f.message)} |"
                  for f in result.fallbacks]
    else:
        lines.append("None.")
    if result.unused_run_cards:
        lines += ["", "Run cards the current selector does not pick (not published from the run): "
                  + ", ".join(f"`{i}`" for i in result.unused_run_cards) + "."]
    lines += _segment_report(result)
    lines += _agent_report(result)
    affected = sum(s.affects_card for s in result.same_second)
    lines += [
        "",
        "## Same-second check",
        "",
        "A claim ends at the moment's second (`MatchTime`), so `measure` also counts events of that second that "
        "come after the moment's own event (`at_seq`). Each moment's menu claims and its published claims are "
        "measured twice, with every event up to the end second and with events up to `at_seq`; listed when the "
        "value or the counted events differ.",
        "",
    ]
    if result.same_second:
        lines += [
            "| Moment | Type | Time | Selected | Card source | Later events in the second "
            "| Menu claims (all → up to at_seq) | Published claims affected |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for s in result.same_second:
            lines.append(
                f"| `{s.moment_id}` | {s.moment_type} | {s.minute_label} | {'yes' if s.selected else 'no'} "
                f"| {s.source} | {', '.join(s.later_events) or '—'} | {_drifts(s.menu)} | {_drifts(s.published)} |"
            )
    lines += ["", f"Moments: {len(result.same_second)}; published cards affected: {affected}.", ""]
    return "\n".join(lines)


def _segment_report(result: BuildResult) -> list[str]:
    stats = result.segment_stats
    lines = [
        "",
        "## Segments",
        "",
        "Each card's text is stored in pieces (`segments`); a piece that states a claim's value carries that claim's id. "
        "The pieces are written by the code that writes the text (slot filling, template builders), never matched "
        "afterwards. Joined, they equal the card text (a card where they do not is not published).",
        "",
        "| Source | Cards | Pieces with a claim id | Claims with no value in the sentence | Piece text ≠ claim display "
        "| Plain pieces with a digit |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for src in SOURCES:
        rows = [s for s in stats if s.source == src]
        lines.append(
            f"| {src} | {len(rows)} | {sum(s.with_claim for s in rows)} | {sum(len(s.unplaced) for s in rows)} "
            f"| {sum(len(s.mismatched) for s in rows)} | {sum(s.plain_digits for s in rows)} |"
        )
    by_metric: dict[str, int] = {}
    for s in stats:
        for _, metric in s.unplaced:
            by_metric[metric] = by_metric.get(metric, 0) + 1
    lines += [
        "",
        "Claims with no value in the sentence are claims the sentence states in words (\"was sent off\" for a red "
        "card count of 1, \"scored\" for a goal count of 1, \"drew level\" for a margin); they stay in `claims` "
        "and in the Receipt, without a piece to underline: "
        + (", ".join(f"`{m}` {n}" for m, n in sorted(by_metric.items())) or "none") + ".",
    ]
    return lines


def _agent_report(result: BuildResult) -> list[str]:
    from collections import Counter

    counts = Counter(result.verifications)
    lines = [
        "",
        "## Verification and trace",
        "",
        "What ran on each published card (`verification`) and whether the agent run's trace is stored (`trace`). "
        "`label_source` `guard_only` is a model draft the Guard accepted and no meaning check covered (Verifier off or "
        "failed). Cards of runs that predate the agent workflow have no trace and no meaning check.",
        "",
        "| Source | Verifier | Label | Trace | Cards |",
        "|---|---|---|---|---:|",
    ]
    lines += [f"| {s} | {v} | {lab} | {tr} | {n} |" for (s, v, lab, tr), n in sorted(counts.items())]
    if result.trace_dropped:
        lines += ["", "Run traces not stored (the current code published another kind of card than the run did):", ""]
        lines += [f"- {t}" for t in result.trace_dropped]
    return lines


def outputs(result: BuildResult, out_dir: Path, report: Path) -> dict[Path, str]:
    files = {out_dir / f"{s.match_id}.json": dumps(s) for s in result.stores}
    files[report] = render_report(result)
    return files
