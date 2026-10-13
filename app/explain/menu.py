"""Claim menüsü (foundry-v5): iddiaları kod kurar ve doğrular, model yalnızca seçer.

Her moment için aday iddialar deterministik olarak üretilir ve `verify_claim`'den geçer;
count iddialarında kanıt listesi doğrulayıcının saydığı olayların tamamıdır (maç başından
sayımlar dahil). Model iddia kurmaz, olay bağlamaz: şablonda yalnızca menüdeki id'leri
yer tutucularla kullanır (`{value:<id>}`, `{minute:<id>}`, `{start:<id>}`, `{label:<id>}`,
`{clause:<id>}`, menü kanıtı olan `{event:<id>}`, `{score}`). Menüde olmayan id reddedilir.

Yan cümleler (`{clause:<id>}`): her iddia için kodun yazdığı doğal dil parçası ("{home} have
had {value:possession} of the ball since kickoff"); model aynen kullanır ya da bağlaçla
birleştirir. Yan cümle şablonları lint'ten geçmez (kod yazar), render sonrası metin
text_lint'ten geçer (tests/test_menu.py).

Menüye girmeyen metrik: field_tilt ("territorial share"). Possession ile aynı biçimde
(yüzde) ve aynı "top/alan" çağrışımıyla gelir; okur ikisini karıştırır, hiçbir moment tipinin
ana iddiası değildir. Doğrulayıcıda metrik olarak kalır.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.analytics.metrics import other
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
# Bir cümleyi bir menü iddiasına dayandıran yer tutucular ({label:} tek başına değer taşımaz).
GROUNDING = ("value", "minute", "start", "clause", "event", "score", "score_named")


@dataclass(frozen=True)
class MenuClaim:
    id: str
    claim: Claim

    @property
    def window(self) -> str:
        c = self.claim
        if c.metric == "pressure_balance":
            return "rolling"  # son oynanmış dakikalar (etikette yazılı)
        if c.start == c.end:
            return "event"
        return "since_kickoff" if c.start == KICKOFF else "window"


@dataclass(frozen=True)
class MenuClause:
    id: str
    claim_ids: tuple[str, ...]
    text: dict[str, str]  # dil → yer tutuculu şablon ({home}/{away}, menü id'leri)


@dataclass(frozen=True)
class ClaimMenu:
    moment_id: str
    claims: tuple[MenuClaim, ...]
    clauses: tuple[MenuClause, ...]
    # Moment tipinin ana iddiaları: her gruptan en az bir iddia cümlede kullanılmalı.
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
        """Olayı kanıt sayan ilk menü iddiası."""
        return next((c.id for c in self.claims if ref in c.claim.event_ids), None)


# --- menü kurulumu ------------------------------------------------------------------------------


class _Builder:
    def __init__(self, moment: Moment, events: Sequence[Event], config: ExplainConfig) -> None:
        self.c = _Context(moment, events, config)
        self.m = moment
        self.side = moment.team
        self.opp = other(moment.team) if moment.team in ("home", "away") else None
        self.claims: list[MenuClaim] = []
        self.clauses: list[MenuClause] = []
        self.pid = {name: pid for pid, name in player_ids(events).items()}

    def add(self, cid: str, claim: Claim, en: str | None = None, tr: str | None = None) -> None:
        self.claims.append(MenuClaim(cid, claim))
        if en is not None:
            self.clause(cid, (cid,), en, tr or en)

    def clause(self, cid: str, claim_ids: tuple[str, ...], en: str, tr: str) -> None:
        def sides(t: str) -> str:
            t = t.replace("{T}", "{" + self.side + "}")
            return t.replace("{O}", "{" + self.opp + "}") if self.opp else t
        self.clauses.append(MenuClause(cid, claim_ids, {"en": sides(en), "tr": sides(tr)}))

    def player(self, name: str) -> str:
        return "{player:" + self.pid[name] + "}"

    def score(self) -> None:
        anchor = [self.m.at_seq]
        for side in ("home", "away"):
            value = self.c.measured("score", side)
            self.add(SCORE_IDS[side], self.c.state("score", side, "eq", value, anchor))
        self.clause("score", (SCORE_IDS["home"], SCORE_IDS["away"]), "the score is {score_named}", "skor {score_named}")

    def possession(self, start: MatchTime = KICKOFF) -> None:
        value = round(self.c.measured("possession", self.side, start), 2)
        claim = Claim("ratio", Subject(self.side), "possession", "approx", value, start, self.c.t,
                      (self.c.ref(self.m.at_seq),))
        if start == KICKOFF:
            self.add("possession", claim, "{T} have had {value:possession} of the ball since kickoff",
                     "{T} maç başından bu yana topun {value:possession} kadarına sahip")
        else:
            self.add("possession", claim, "{T} have had {value:possession} of the ball since {start:possession}",
                     "{start:possession} sonrası {T} topun {value:possession} kadarına sahip")

    def margin(self, cid: str, claim: Claim) -> None:
        v = claim.value
        if v > 0:
            en, tr = "{T} lead by {value:%s}" % cid, "{T} {value:%s} farkla önde" % cid
        elif v == 0:
            en, tr = "the sides are level", "taraflar eşit"
        else:
            en, tr = "{T} are behind", "{T} geride"
        self.add(cid, claim, en, tr)


def _goal(b: _Builder) -> None:
    player = b.m.detail["player"]
    b.add("goal", b.c.count("goals", Subject(b.side, player), b.c.t),
          f"{b.player(player)} scored for {{T}}", f"{b.player(player)} {{T}} adına gol attı")
    b.add("team_goals", b.c.count("goals", Subject(b.side), KICKOFF),
          "{T} have scored {value:team_goals} {label:team_goals} so far",
          "{T} şu ana kadar {value:team_goals} {label:team_goals} attı")
    b.score()
    b.possession()


def _score_change(b: _Builder) -> None:
    d = b.m.detail
    goal_seq = b.m.event_ids[-1]
    b.add("goals", b.c.count("goals", Subject(b.side), b.c.t),
          "{T} scored at {minute:goals}", "{T} {minute:goals} itibarıyla gol buldu")
    margin = b.c.measured("score_margin", b.side)
    b.margin("margin", b.c.state("score_margin", b.side, "eq", margin, [goal_seq]))
    if d.get("from_behind"):
        deficit = d["max_deficit"]
        conceded = measure("goals", Subject(b.opp), KICKOFF, b.c.t, b.c.events).counted
        goals = "goal" if deficit == 1 else "goals"
        b.add("deficit", b.c.state("min_score_margin", b.side, "eq", -deficit, conceded),
              "{T} had been {value:deficit} %s down" % goals, "{T} bir ara {value:deficit} farkla gerideydi")
    b.score()
    b.possession()


def _red_card(b: _Builder) -> None:
    player = b.m.detail["player"]
    b.add("sent_off", b.c.count("red_cards", Subject(b.side, player), b.c.t),
          f"{b.player(player)} of {{T}} was sent off", f"{{T}} oyuncusu {b.player(player)} oyundan atıldı")
    team_reds = measure("red_cards", Subject(b.side), KICKOFF, b.c.t, b.c.events).counted
    left = b.c.measured("players_on_pitch", b.side)
    b.add("players", b.c.state("players_on_pitch", b.side, "eq", left, team_reds),
          "{T} are down to {value:players} {label:players}", "{T} sahada {value:players} kişi kaldı")
    b.score()
    b.possession()


_PENALTY_CLAUSES = {
    "scored": ("{p} scored a penalty for {T}", "{p} {T} adına penaltıyı gole çevirdi"),
    "saved": ("{p}'s penalty for {T} was saved", "{T} adına penaltıyı {p} kullandı, vuruş kurtarıldı"),
    "missed": ("{p} missed a penalty for {T}", "{p} {T} adına penaltıyı kaçırdı"),
}


def _penalty(b: _Builder) -> None:
    player, outcome = b.m.detail["player"], b.m.detail["outcome"]
    en, tr = (t.replace("{p}", b.player(player)) for t in _PENALTY_CLAUSES[outcome])
    b.add("penalty", b.c.count(f"penalties_{outcome}", Subject(b.side, player), b.c.t), en, tr)
    b.score()
    b.possession()


def _shots(b: _Builder, start: MatchTime, lead_form: bool) -> None:
    shots = b.c.count("shots", Subject(b.side), start)
    opp = b.c.count("shots", Subject(b.opp), start)
    b.add("shots_for", shots)
    b.add("shots_against", opp)
    ids = ("shots_for", "shots_against")
    tr = "{start:shots_for} sonrası {label:shots_for} sayısında {T} {value:shots_for}, {O} {value:shots_against}"
    if lead_form:
        verb = "lead" if shots.value > opp.value else ("trail" if shots.value < opp.value else "are level at")
        en = f"{{T}} {verb} {{value:shots_for}}–{{value:shots_against}} in {{label:shots_for}} since {{start:shots_for}}"
    else:
        en = ("{T} have had {value:shots_for} {label:shots_for} to {O}'s {value:shots_against} "
              "since {start:shots_for}")
    b.clause("shots", ids, en, tr)


def _pressure_shift(b: _Builder) -> None:
    balance = round(b.c.measured("pressure_balance", b.side), 2)
    b.add("pressure", b.c.state("pressure_balance", b.side, "approx", balance, b.m.event_ids),
          "{T} lead the {label:pressure} at {value:pressure}",
          "{label:pressure} {value:pressure} ile {T} lehine")
    _shots(b, _since(b.c.t, b.c.config.context_minutes), lead_form=False)
    b.score()


def _dominance(b: _Builder) -> None:
    start = _since(b.c.t, b.c.config.dominance_context_minutes)
    b.possession(start)
    _shots(b, start, lead_form=True)
    # İki ana iddia aynı pencereden: pencere bir kez yazılır (iki yan cümle yan yana dakikayı tekrarlar).
    shots, opp = (next(c.claim.value for c in b.claims if c.id == i) for i in ("shots_for", "shots_against"))
    balance = "a {v}–{o} lead" if shots > opp else ("a {v}–{o} deficit" if shots < opp else "level at {v}–{o}")
    balance = balance.format(v="{value:shots_for}", o="{value:shots_against}")
    b.clause("dominance", ("possession", "shots_for", "shots_against"),
             "since {start:possession} {T} have had {value:possession} of the ball and "
             + balance + " in {label:shots_for}",
             "{start:possession} sonrası {T} topun {value:possession} kadarına sahip, {label:shots_for} "
             "sayısında {value:shots_for}–{value:shots_against}")
    b.score()
    margin = b.c.measured("score_margin", b.side)
    b.margin("margin", b.c.state("score_margin", b.side, "eq", margin, [b.m.at_seq]))


BUILDERS = {
    "goal": _goal,
    "score_change": _score_change,
    "red_card": _red_card,
    "penalty": _penalty,
    "pressure_shift": _pressure_shift,
    "dominance_without_reward": _dominance,
}
PRIMARY: dict[str, tuple[frozenset[str], ...]] = {
    "dominance_without_reward": (frozenset({"possession"}), frozenset({"shots_for", "shots_against"})),
    "pressure_shift": (frozenset({"pressure"}),),
}


def build_menu(
    moment: Moment, events: Sequence[Event], config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> ClaimMenu:
    """Momentin doğrulanmış aday iddiaları ve yan cümleleri. Doğrulanmayan iddia menüye girmez."""
    b = _Builder(moment, events, config)
    BUILDERS[moment.type](b)
    ok = {c.id for c in b.claims if verify_claim(c.claim, events, config).ok}
    claims = tuple(c for c in b.claims if c.id in ok)
    clauses = tuple(c for c in b.clauses if set(c.claim_ids) <= ok)
    primary = tuple(g & ok for g in PRIMARY.get(moment.type, ()) if g & ok)
    return ClaimMenu(moment.id, claims, clauses, primary)


# --- model kaydı için okunur biçim ---------------------------------------------------------------


def preview(menu: ClaimMenu, ctx: SlotContext) -> dict[str, str]:
    """Yan cümlelerin render edilmiş hali (modele örnek)."""
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
    """Menü iddialarının kanıt olayları (sıralı, tekrarsız)."""
    by_seq = {e.seq: e for e in events}
    seqs = sorted({parse_ref(r)[1] for c in menu.claims for r in c.claim.event_ids})
    return [by_seq[s] for s in seqs if s in by_seq]


# --- menü taslağı: bağlama ve v5 kuralları ---------------------------------------------------------


def _minutes(template: str, menu: ClaimMenu, ctx: SlotContext, seen: frozenset[str] = frozenset()) -> list[str]:
    """Şablonun render edildiğinde yazacağı dakikalar (yan cümleler dahil)."""
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


def bind_menu(
    template: str, menu: ClaimMenu, ctx: SlotContext, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> tuple[tuple[Claim, ...], tuple[str, ...], list[LintIssue]]:
    """Yer tutucuları menüye bağlar; (bağlanan iddialar, id'ler, sorunlar)."""
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
    """Yer tutucuların başvurduğu menü iddiaları (yan cümleler ve olay sahipleri dahil)."""
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


def menu_rule_issues(
    template: str, menu: ClaimMenu, ctx: SlotContext, config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG
) -> list[LintIssue]:
    """Her cümle bir menü iddiasına dayanır; ana iddia kullanılır; bir cümlede aynı dakika bir kez."""
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
    if config.slot_primary_claim and template.strip():
        used = _referenced(placeholders, menu)
        for group in menu.primary:
            if not used & group:
                issues.append(LintIssue("missing_primary_claim", ",".join(sorted(group)), 0, 0, "placeholder"))
    return issues
