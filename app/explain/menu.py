"""Claim menu (foundry-v5): code builds and verifies the claims, the model only picks.

For each moment, candidate claims are generated deterministically and pass `verify_claim`;
for count claims the evidence list is every event the verifier counted (counts since
kickoff included). The model builds no claims and links no events: in its template it only
uses menu ids through placeholders (`{value:<id>}`, `{minute:<id>}`, `{start:<id>}`, `{label:<id>}`,
`{clause:<id>}`, `{event:<id>}` for menu evidence, `{score}`). An id not on the menu is rejected.

Clauses (`{clause:<id>}`): a natural-language fragment written by code for each claim ("{home} have
had {value:possession} of the ball since kickoff"); the model uses it as is or joins clauses with a
conjunction. Clause templates do not go through lint (code writes them); the rendered text goes
through text_lint (tests/test_menu.py).

Metric left off the menu: field_tilt ("territorial share"). It comes in the same form as possession
(a percentage) with the same "ball/territory" connotation; readers confuse the two, and it is the
primary claim of no moment type. It stays a metric in the verifier.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.analytics.config import DEFAULT_CONFIG as ANALYTICS_CONFIG
from app.analytics.metrics import other, stated
from app.analytics.moments import Moment
from app.generator.models import Event

from .claims import KICKOFF, Claim, MatchTime, Subject, VerificationResult, measure, parse_ref, verify_claim
from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from .labels import metric_label
from .phrases import selectable
from .slots import (
    SCORE_IDS,
    SlotContext,
    format_value,
    parse_placeholders,
    player_ids,
    render,
    template_sentences,
)
from .template_narrator import _Context, _since, fmt_minute
from .text_lint import LintIssue

CLAIM_SLOTS = ("value", "minute", "start", "label")
# Placeholders that ground a sentence in a menu claim ({label:} alone carries no value).
GROUNDING = ("value", "minute", "start", "clause", "event", "score", "score_named")


@dataclass(frozen=True)
class MenuClaim:
    id: str
    claim: Claim

    @property
    def window(self) -> str:
        c = self.claim
        if c.metric == "pressure_balance":
            return "rolling"  # last minutes played (stated in the label)
        if c.start == c.end:
            return "event"
        return "since_kickoff" if c.start == KICKOFF else "window"


@dataclass(frozen=True)
class MenuClause:
    id: str
    claim_ids: tuple[str, ...]
    text: dict[str, str]  # language → placeholder template ({home}/{away}, menu ids)


@dataclass(frozen=True)
class ClaimMenu:
    moment_id: str
    claims: tuple[MenuClaim, ...]
    clauses: tuple[MenuClause, ...]
    # The moment type's primary claims: at least one claim from each group must be used in a sentence.
    primary: tuple[frozenset[str], ...] = ()

    @property
    def by_id(self) -> dict[str, Claim]:
        return {c.id: c.claim for c in self.claims}

    @property
    def clause_by_id(self) -> dict[str, MenuClause]:
        return {c.id: c for c in self.clauses}

    def clause_templates(self, language: str) -> dict[str, str]:
        return {c.id: c.text.get(language, c.text["en"]) for c in self.clauses}

    def evidence_owner(self, ref: str) -> str | None:
        """The first menu claim that counts the event as evidence."""
        return next((c.id for c in self.claims if ref in c.claim.event_ids), None)


# --- menu building ------------------------------------------------------------------------------


class _Builder:
    def __init__(self, moment: Moment, events: Sequence[Event], config: ExplainConfig) -> None:
        self.c = _Context(moment, events, config)
        self.m = moment
        self.side = moment.team
        self.opp = other(moment.team) if moment.team in ("home", "away") else None
        self.claims: list[MenuClaim] = []
        self.clauses: list[MenuClause] = []
        self.pid = {name: pid for pid, name in player_ids(events).items()}

    def add(self, cid: str, claim: Claim, en: str | None = None) -> None:
        self.claims.append(MenuClaim(cid, claim))
        if en is not None:
            self.clause(cid, (cid,), en)

    def clause(self, cid: str, claim_ids: tuple[str, ...], en: str) -> None:
        def sides(t: str) -> str:
            t = t.replace("{T}", "{" + self.side + "}")
            return t.replace("{O}", "{" + self.opp + "}") if self.opp else t
        self.clauses.append(MenuClause(cid, claim_ids, {"en": sides(en)}))

    def player(self, name: str) -> str:
        return "{player:" + self.pid[name] + "}"

    def score(self) -> None:
        anchor = [self.m.at_seq]
        for side in ("home", "away"):
            value = self.c.measured("score", side)
            self.add(SCORE_IDS[side], self.c.state("score", side, "eq", value, anchor))
        self.clause("score", (SCORE_IDS["home"], SCORE_IDS["away"]), "the score is {score_named}")

    def possession(self, start: MatchTime = KICKOFF) -> None:
        value = stated(self.c.measured("possession", self.side, start))
        claim = Claim("ratio", Subject(self.side), "possession", "approx", value, start, self.c.t,
                      (self.c.ref(self.m.at_seq),))
        if start == KICKOFF:
            self.add("possession", claim, "{T} have had {value:possession} of the ball since kickoff")
        else:
            self.add("possession", claim, "{T} have had {value:possession} of the ball since {start:possession}")

    def margin(self, cid: str, claim: Claim) -> None:
        v = claim.value
        if v > 0:
            en = "{T} lead by {value:%s}" % cid
        elif v == 0:
            en = "the sides are level"
        else:
            en = "{T} are behind"
        self.add(cid, claim, en)


# Sub-label clause of a goal that changed the match state; it rests on the margin, not on the score
# (the score itself stays a separate, mandatory claim group).
_CHANGE_CLAUSES = {
    "opener": "{T} opened the scoring",
    "equalizer": "{T} drew level",
    "go_ahead": "{T} went ahead",
}
# from_behind (detector): the team trailed at some earlier point, not necessarily just before this goal (the score
# before it was level), so the clause never reads as "was down just before".
_FROM_BEHIND_CLAUSE = "{T} came from behind to take the lead, having trailed by {value:deficit} %s earlier in the match"


def _goal(b: _Builder) -> None:
    player = b.m.detail["player"]
    b.add("goal", b.c.count("goals", Subject(b.side, player), b.c.t),
          f"{b.player(player)} scored for {{T}}")
    b.add("team_goals", b.c.count("goals", Subject(b.side), KICKOFF),
          "{T} have scored {value:team_goals} {label:team_goals} so far")
    change = b.m.detail.get("score_change")
    if change is not None:
        _score_change(b, change)
    b.score()
    b.possession()


def _score_change(b: _Builder, change: dict) -> None:
    kind = change["kind"]
    goal_seq = b.m.event_ids[-1]
    margin = b.c.measured("score_margin", b.side)
    b.add("margin", b.c.state("score_margin", b.side, "eq", margin, [goal_seq]))
    # An opener: the team's only goal so far and a one-goal lead.
    claim_ids = ("team_goals", "margin") if kind == "opener" else ("margin",)
    en = _CHANGE_CLAUSES[kind]
    if change.get("from_behind"):
        deficit = change["max_deficit"]
        conceded = measure("goals", Subject(b.opp), KICKOFF, b.c.t, b.c.events).counted
        b.add("deficit", b.c.state("min_score_margin", b.side, "eq", -deficit, conceded))
        claim_ids += ("deficit",)
        en = _FROM_BEHIND_CLAUSE % ("goal" if deficit == 1 else "goals")
    b.clause(kind, claim_ids, en)


def _red_card(b: _Builder) -> None:
    player = b.m.detail["player"]
    b.add("sent_off", b.c.count("red_cards", Subject(b.side, player), b.c.t),
          f"{b.player(player)} of {{T}} was sent off")
    team_reds = measure("red_cards", Subject(b.side), KICKOFF, b.c.t, b.c.events).counted
    left = b.c.measured("players_on_pitch", b.side)
    b.add("players", b.c.state("players_on_pitch", b.side, "eq", left, team_reds),
          "{T} are down to {value:players} {label:players}")
    b.score()
    b.possession()


_PENALTY_CLAUSES = {
    "scored": "{p} scored a penalty for {T}",
    "saved": "{p}'s penalty for {T} was saved",
    "missed": "{p} missed a penalty for {T}",
}


def _penalty(b: _Builder) -> None:
    player, outcome = b.m.detail["player"], b.m.detail["outcome"]
    en = _PENALTY_CLAUSES[outcome].replace("{p}", b.player(player))
    b.add("penalty", b.c.count(f"penalties_{outcome}", Subject(b.side, player), b.c.t), en)
    b.score()
    b.possession()


def _shots(b: _Builder, start: MatchTime, lead_form: bool) -> None:
    shots = b.c.count("shots", Subject(b.side), start)
    opp = b.c.count("shots", Subject(b.opp), start)
    b.add("shots_for", shots)
    b.add("shots_against", opp)
    ids = ("shots_for", "shots_against")
    if lead_form:
        verb = "lead" if shots.value > opp.value else ("trail" if shots.value < opp.value else "are level at")
        en = f"{{T}} {verb} {{value:shots_for}}–{{value:shots_against}} in {{label:shots_for}} since {{start:shots_for}}"
    else:
        en = ("{T} have had {value:shots_for} {label:shots_for} to {O}'s {value:shots_against} "
              "since {start:shots_for}")
    b.clause("shots", ids, en)


def _pressure_shift(b: _Builder) -> None:
    balance = stated(b.c.measured("pressure_balance", b.side))
    b.add("pressure", b.c.state("pressure_balance", b.side, "approx", balance, b.m.event_ids),
          "{T} lead the {label:pressure} at {value:pressure}")
    _shots(b, _since(b.c.t, b.c.config.context_minutes), lead_form=False)
    b.score()


def _dominance(b: _Builder) -> None:
    start = b.c.detector_window(ANALYTICS_CONFIG.dominance_window_min)  # the moment detail's window
    b.possession(start)
    _shots(b, start, lead_form=True)
    # Both primary claims share one window: it is written once (two clauses side by side repeat the minute).
    shots, opp = (next(c.claim.value for c in b.claims if c.id == i) for i in ("shots_for", "shots_against"))
    balance = "a {v}–{o} lead" if shots > opp else ("a {v}–{o} deficit" if shots < opp else "level at {v}–{o}")
    balance = balance.format(v="{value:shots_for}", o="{value:shots_against}")
    b.clause("dominance", ("possession", "shots_for", "shots_against"),
             "since {start:possession} {T} have had {value:possession} of the ball and "
             + balance + " in {label:shots_for}")
    b.score()
    margin = b.c.measured("score_margin", b.side)
    b.margin("margin", b.c.state("score_margin", b.side, "eq", margin, [b.m.at_seq]))


BUILDERS = {
    "goal": _goal,
    "red_card": _red_card,
    "penalty": _penalty,
    "pressure_shift": _pressure_shift,
    "dominance_without_reward": _dominance,
}
SCORE_GROUP = frozenset(SCORE_IDS.values())
SHOTS_GROUP = frozenset({"shots_for", "shots_against"})
# foundry-v5.2: a dominance card states the score (without it the "without reward" is lost) and a pressure card
# states the window's shot balance.
PRIMARY: dict[str, tuple[frozenset[str], ...]] = {
    "dominance_without_reward": (frozenset({"possession"}), SHOTS_GROUP, SCORE_GROUP),
    "pressure_shift": (frozenset({"pressure"}), SHOTS_GROUP),
}


def primary_groups(moment: Moment) -> tuple[frozenset[str], ...]:
    """Claim groups the moment must use; a goal that changed the match state must state the score."""
    if moment.type == "goal" and "score_change" in moment.detail:
        return (SCORE_GROUP,)
    return PRIMARY.get(moment.type, ())


def build_menu(
    moment: Moment, events: Sequence[Event], config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> ClaimMenu:
    """Verified candidate claims and clauses for the moment. A claim that does not verify stays off the menu."""
    b = _Builder(moment, events, config)
    BUILDERS[moment.type](b)
    ok = {c.id for c in b.claims if verify_claim(c.claim, events, config).ok}
    claims = tuple(c for c in b.claims if c.id in ok)
    clauses = tuple(c for c in b.clauses if set(c.claim_ids) <= ok)
    primary = tuple(g & ok for g in primary_groups(moment) if g & ok)
    return ClaimMenu(moment.id, claims, clauses, primary)


# --- readable form for the model record ---------------------------------------------------------------


def preview(menu: ClaimMenu, ctx: SlotContext) -> dict[str, str]:
    """Rendered clauses (an example for the model)."""
    ids = tuple(c.id for c in menu.claims)
    claims = tuple(c.claim for c in menu.claims)
    verdicts = tuple(VerificationResult(True, "ok", c.value) for c in claims)
    templates = menu.clause_templates(ctx.language)
    return {cid: render(t, claims, ids, verdicts, ctx, templates) for cid, t in templates.items()}


def menu_record(menu: ClaimMenu, ctx: SlotContext) -> dict[str, list[dict]]:
    pid = {name: p for p, name in ctx.players.items()}
    claims = []
    for mc in menu.claims:
        c = mc.claim
        claims.append({
            "id": mc.id,
            "kind": c.kind,
            "metric": c.metric,
            "team": c.subject.team,
            "player": pid.get(c.subject.player) if c.subject.player else None,
            "window": mc.window,
            "start": fmt_minute(c.start.period, c.start.minute),
            "end": fmt_minute(c.end.period, c.end.minute),
            "value": format_value(c.metric, c.value, ctx.language),
            "label": metric_label(c.metric, ctx.language),
            "evidence": list(c.event_ids),
            "primary": any(mc.id in g for g in menu.primary),
        })
    texts = preview(menu, ctx)
    clauses = [{"id": c.id, "claims": list(c.claim_ids), "text": texts[c.id]} for c in menu.clauses]
    return {"claims_menu": claims, "clauses": clauses}


def evidence_events(menu: ClaimMenu, events: Sequence[Event]) -> list[Event]:
    """Evidence events of the menu claims (ordered, deduplicated)."""
    by_seq = {e.seq: e for e in events}
    seqs = sorted({parse_ref(r)[1] for c in menu.claims for r in c.claim.event_ids})
    return [by_seq[s] for s in seqs if s in by_seq]


# --- menu draft: binding and v5 rules ---------------------------------------------------------


def _minutes(template: str, menu: ClaimMenu, ctx: SlotContext, seen: frozenset[str] = frozenset()) -> list[str]:
    """Minutes the template writes when rendered (clauses included)."""
    by_id, clauses = menu.by_id, menu.clause_templates(ctx.language)
    out: list[str] = []
    for ph in parse_placeholders(template)[0]:
        if ph.kind in ("minute", "start") and ph.arg in by_id:
            t = by_id[ph.arg].end if ph.kind == "minute" else by_id[ph.arg].start
            out.append(fmt_minute(t.period, t.minute))
        elif ph.kind == "event":
            e = ctx.event(ph.arg)
            if e is not None and ctx.phrase(ph.arg):
                out.append(fmt_minute(e.period, e.minute))
        elif ph.kind == "clause" and ph.arg in clauses and ph.arg not in seen:
            out += _minutes(clauses[ph.arg], menu, ctx, seen | {ph.arg})
    return out


def _teams(template: str, menu: ClaimMenu, ctx: SlotContext, seen: frozenset[str] = frozenset()) -> list[str]:
    """Sides the template names when rendered ({score_named} names both; clauses included)."""
    clauses = menu.clause_templates(ctx.language)
    out: list[str] = []
    for ph in parse_placeholders(template)[0]:
        if ph.kind in ("home", "away"):
            out.append(ph.kind)
        elif ph.kind == "score_named":
            out += ["home", "away"]
        elif ph.kind == "clause" and ph.arg in clauses and ph.arg not in seen:
            out += _teams(clauses[ph.arg], menu, ctx, seen | {ph.arg})
    return out


def bind_menu(
    template: str, menu: ClaimMenu, ctx: SlotContext, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> tuple[tuple[Claim, ...], tuple[str, ...], list[LintIssue]]:
    """Binds placeholders to the menu; (bound claims, ids, issues)."""
    placeholders, issues = parse_placeholders(template)
    by_id, clauses = menu.by_id, menu.clause_by_id
    subjects = {c.claim.subject.player for c in menu.claims if c.claim.subject.player}
    used: list[str] = []

    for ph in placeholders:
        if ph.kind in CLAIM_SLOTS:
            if ph.arg in by_id:
                used.append(ph.arg)
            else:
                issues.append(LintIssue("unknown_claim_id", ph.raw, ph.start, ph.end, "placeholder"))
        elif ph.kind == "clause":
            if ph.arg in clauses:
                used += clauses[ph.arg].claim_ids
            else:
                issues.append(LintIssue("unknown_claim_id", ph.raw, ph.start, ph.end, "placeholder"))
        elif ph.kind == "event":
            owner = menu.evidence_owner(ph.arg)
            if ctx.event(ph.arg) is None:
                issues.append(LintIssue("unbound_placeholder", ph.raw, ph.start, ph.end, "placeholder"))
            elif ctx.phrase(ph.arg) is None:
                issues.append(LintIssue("unsupported_event", ph.raw, ph.start, ph.end, "placeholder"))
            elif owner is None:
                issues.append(LintIssue("event_not_evidence", ph.raw, ph.start, ph.end, "placeholder"))
            else:
                used.append(owner)
        elif ph.kind == "player":
            name = ctx.players.get(ph.arg)
            if name is None or name not in subjects:
                issues.append(LintIssue("unbound_placeholder", ph.raw, ph.start, ph.end, "placeholder"))
        elif ph.kind in ("score", "score_named"):
            if all(SCORE_IDS[s] in by_id for s in ("home", "away")):
                used += [SCORE_IDS["home"], SCORE_IDS["away"]]
            else:
                issues.append(LintIssue("unbound_placeholder", ph.raw, ph.start, ph.end, "placeholder"))

    issues += menu_rule_issues(template, menu, ctx, config)
    ids = tuple(dict.fromkeys(used))
    return tuple(by_id[i] for i in ids), ids, issues


def _referenced(placeholders, menu: ClaimMenu) -> set[str]:
    """Menu claims the placeholders refer to (clauses and event owners included)."""
    clauses = menu.clause_by_id
    out: set[str] = set()
    for ph in placeholders:
        if ph.kind in CLAIM_SLOTS:
            out.add(ph.arg)
        elif ph.kind == "clause" and ph.arg in clauses:
            out |= set(clauses[ph.arg].claim_ids)
        elif ph.kind == "event":
            owner = menu.evidence_owner(ph.arg)
            if owner:
                out.add(owner)
        elif ph.kind in ("score", "score_named"):
            out |= {SCORE_IDS["home"], SCORE_IDS["away"]}
    return out


def _repeat_exempt(ph, menu: ClaimMenu, mode: str) -> bool:
    """Placeholders whose team names `team_repeat` does not count (`ExplainConfig.slot_team_repeat_exempt`)."""
    if mode == "none":
        return False
    if ph.kind == "score_named" or (ph.kind == "clause" and ph.arg == "score"):
        return True
    if mode == "score+primary" and ph.kind == "clause" and ph.arg in menu.clause_by_id:
        ids = set(menu.clause_by_id[ph.arg].claim_ids)
        return any(ids & group for group in menu.primary if group != SCORE_GROUP)
    return False


def team_counts(placeholders, menu: ClaimMenu, ctx: SlotContext, mode: str) -> list[str]:
    """Sides one sentence's placeholders name, as `team_repeat` counts them."""
    return [side for ph in placeholders if not _repeat_exempt(ph, menu, mode) for side in _teams(ph.raw, menu, ctx)]


def menu_rule_issues(
    template: str, menu: ClaimMenu, ctx: SlotContext, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> list[LintIssue]:
    """Each sentence rests on a menu claim; the primary claim is used; a minute appears once per sentence;
    a team is named at most `slot_team_repeat_max` times per sentence (foundry-v5.2: the score line does
    not count, see `slot_team_repeat_exempt`)."""
    placeholders = parse_placeholders(template)[0]
    issues: list[LintIssue] = []
    for start, end in template_sentences(template):
        inside = [ph for ph in placeholders if start <= ph.start < end]
        text = template[start:end].strip()
        if config.slot_sentence_claim and text and not any(ph.kind in GROUNDING for ph in inside):
            issues.append(LintIssue("sentence_without_claim", text[:60], start, end, "placeholder"))
        if config.slot_minute_repeat:
            seen: set[str] = set()
            for ph in inside:
                for minute in _minutes(ph.raw, menu, ctx):
                    if minute in seen:
                        issues.append(LintIssue("minute_repeat", ph.raw, ph.start, ph.end, "minute"))
                    seen.add(minute)
        if config.slot_team_repeat_max:
            sides = team_counts(inside, menu, ctx, config.slot_team_repeat_exempt)
            for side in ("home", "away"):
                if sides.count(side) > config.slot_team_repeat_max:
                    issues.append(LintIssue("team_repeat", "{%s}" % side, start, end, "name"))
    if config.slot_primary_claim and template.strip():
        used = _referenced(placeholders, menu)
        for group in menu.primary:
            if not used & group:
                issues.append(LintIssue("missing_primary_claim", ",".join(sorted(group)), 0, 0, "placeholder"))
    return issues
