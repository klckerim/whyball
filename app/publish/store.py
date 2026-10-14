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

from .schema import SOURCES, EvidenceEvent, MatchStore, StoredChecks, StoredClaim, StoredMoment

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
    for m in moments:
        logs: list[AttemptLog] = []
        if m.id in selected:
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

        cards.append(StoredMoment(
            id=m.id, period=m.period, minute=m.minute, second=m.second,
            minute_label=fmt_minute(m.period, m.minute), at_seq=m.at_seq, type=m.type, team=m.team,
            importance=m.importance, text=rec.text, source=rec.source,
            prompt_version=prompt_version if rec.source == "llm" else config.template_prompt_version,
            run_id=None if rec.source == "template" else run_id,
            claims=_claims(rec.claims, ids, by_seq), trace=[],
            checks=StoredChecks(
                lint_issues=len(rec.lint_issues), claims_total=len(rec.verification),
                claims_verified=sum(r.ok for r in rec.verification),
            ),
        ))
    result.unused_run_cards += sorted(set(run_by_id) - selected)

    teams = events[0].data["teams"]
    return MatchStore(
        match_id=match_id, event_match_id=events[0].match_id, events_file=_rel(events_path),
        events_sha256=hashlib.sha256(events_path.read_bytes()).hexdigest(),
        teams={side: teams[side]["name"] for side in ("home", "away")},
        final_score=events[-1].score, run_id=run_id, prompt_version=prompt_version, moments=cards,
    )


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


def outputs(result: BuildResult, out_dir: Path, report: Path) -> dict[Path, str]:
    files = {out_dir / f"{s.match_id}.json": dumps(s) for s in result.stores}
    files[report] = render_report(result)
    return files
