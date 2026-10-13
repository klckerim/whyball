"""Injection evaluation: how often do the foundry-v2 (free text), foundry-v3 (slot), foundry-v4
(slot + {event:} + strict lint), foundry-v4.1 (+ event type allow-list, player repeat,
pronoun/article) and foundry-v5 (claim menu: code builds the claims, the model picks from the menu)
narration approaches catch controlled errors?

It starts from the template narrator's correct drafts:
- v2: free text + claims; checked by `check_draft` (text_lint + verify_claim) with the v2 rules.
- v3: the same draft is turned deterministically into a slot template (`slotify`); checked by
  `check_slot_draft` (template lint + placeholder binding + verify_claim) with the v3 rules.
- v4: a v4 template per moment type with the same claims (`slotify_v4`: events via {event:},
  metric names via {label:}); checked by `check_slot_draft` with the v4 rules.
- v4.1: the same v4 base; checked with the v4.1 rules.
- v5: a base with menu ids (`slotify_v5`); checked by `check_menu_draft` (menu binding + v5 rules)
  with the default rules, i.e. the current version (`PROMPT_VERSION`, foundry-v5.1 rules included). The model writes no claims, so injections that change a claim are "—" in v5.
Each error type is injected in each approach's own form, with the same meaning.

    python -m eval.inject [--quick] [--out docs/EVAL.md] [--no-write]
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import random
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from app.analytics import detect_moments
from app.analytics.metrics import other
from app.analytics.moments import Moment
from app.explain.claims import KICKOFF, Claim, Subject, VerificationResult, measure
from app.explain.config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from app.explain.labels import WINDOW_PHRASES, metric_label, window_phrase_spans
from app.explain.phrases import sentence_starts
from app.explain.menu import ClaimMenu, build_menu, menu_rule_issues, team_counts
from app.explain.pipeline import check_draft, check_menu_draft, check_slot_draft
from app.explain.llm_narrator import PROMPT_VERSION
from app.explain.slots import (
    PLACEHOLDER_RE,
    SlotContext,
    parse_placeholders,
    player_ids,
    render,
    template_sentence_starts,
)
from app.explain.template_narrator import fmt_minute
from app.explain.template_narrator import narrate as template_narrate
from app.explain.text_lint import NUMBER_RE, NUMBER_WORDS, Roster
from app.generator import generate_match
from app.generator.models import Event

from . import lint_rates

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "docs" / "EVAL.md"
LANGS = ("en",)
VARIANTS = ("v2", "v3", "v4", "v41", "v5")
CURRENT = "v5"  # measured with the default rules: the current prompt version
NAMES = {"v2": "v2", "v3": "v3", "v4": "v4", "v41": "v4.1", CURRENT: PROMPT_VERSION.removeprefix("foundry-")}
TITLES = {
    "v2": "foundry-v2 (free text)", "v3": "foundry-v3 (slot)", "v4": "foundry-v4 (slot + {event:} + strict lint)",
    "v41": "foundry-v4.1 (+ event type allow-list, player repeat, pronoun/article)",
    CURRENT: f"{PROMPT_VERSION} (claim menu + clauses)",
}

# Each column is measured with its own version's rules: rules added later are switched off.
V5_CONFIG = DEFAULT_EXPLAIN_CONFIG
V41_CONFIG = replace(DEFAULT_EXPLAIN_CONFIG, sentence_start_allowed_en=("At", "Possession", "The"))
V4_CONFIG = replace(
    DEFAULT_EXPLAIN_CONFIG, slot_event_type_allowlist=False, slot_player_repeat=False, slot_article_team=False,
    sentence_start_allowed_en=("At", "Possession", "The", "They"),  # v4's frozen list
)
V3_CONFIG = replace(
    V4_CONFIG, slot_event_words=False, slot_sentence_start=False,
    slot_strict_number_words=False, slot_overstatement=False,
)
V2_CONFIG = replace(DEFAULT_EXPLAIN_CONFIG, lint_bare_surname=False)
CONFIGS = {"v2": V2_CONFIG, "v3": V3_CONFIG, "v4": V4_CONFIG, "v41": V41_CONFIG, "v5": V5_CONFIG}

# (seed, scenario): 3 demo matches + 5 seeds per scenario + 10 matches without a scenario
FULL_CORPUS = (
    [(42, "red_card_swing"), (7, "dominant_loss"), (100, None)]
    + [(s, sc) for sc in ("late_comeback", "red_card_swing", "dominant_loss") for s in range(5)]
    + [(s, None) for s in range(10)]
)
QUICK_CORPUS = [(42, "red_card_swing"), (7, "dominant_loss"), (42, "late_comeback"), (100, None)]

FABRICATED_START = {"en": "Quintana scores."}
UNSUPPORTED_NUMBER = {"en": "{team} have won {n} corners."}
UNSUPPORTED_QUALITATIVE = {"en": "{team} were the better side."}
SIDE_LABEL = {
    "en": {"home": "the home side", "away": "the away side"},
}


@dataclass(frozen=True)
class Sample:
    events: Sequence[Event]
    roster: Roster
    players: tuple[str, ...]  # this match's squad
    teams: dict[str, str]
    moment: Moment
    lang: str
    text: str
    claims: tuple[Claim, ...]
    slot: SlotDraft | None = None  # v3 base (None if slotify fails)
    slot4: SlotDraft | None = None  # v4 and v4.1 base
    slot5: SlotDraft | None = None  # v5 base (menu ids)
    sentences: tuple[str, ...] = ()  # the template narrator's sentences (raw)


@dataclass(frozen=True)
class SlotDraft:
    template: str
    claims: tuple[Claim, ...]
    claim_ids: tuple[str, ...]
    ctx: SlotContext = field(repr=False)
    event_ref: str | None = None  # v4: the {event:} event in the template
    menu: ClaimMenu | None = field(default=None, repr=False)  # v5: claim menu (claims/claim_ids from the menu)


@dataclass(frozen=True)
class Injection:
    text: str  # v2: text, v3/v4: template
    claims: tuple[Claim, ...]
    claim_ids: tuple[str, ...] = ()
    tag: str | None = None  # phrase / name used (to list the misses)


Injector = Callable[[Sample, random.Random, Sequence[str]], Injection | None]


# --- helpers ------------------------------------------------------------------------


def _fmt(v: float) -> str:
    return f"{v:g}"


def _masked(sample: Sample) -> str:
    """Text with name spans masked by spaces (same length)."""
    chars = list(sample.text)
    for m in sample.roster.pattern.finditer(sample.text):
        chars[m.start() : m.end()] = " " * (m.end() - m.start())
    for start, end in window_phrase_spans(sample.text):  # fixed window phrase: not a claim
        chars[start:end] = " " * (end - start)
    return "".join(chars)


def _splice(text: str, start: int, end: int, new: str) -> str:
    return text[:start] + new + text[end:]


def _bumped_number(m: re.Match[str]) -> str:
    g = m.groupdict()
    if g["min"] is not None:
        if g["extra"]:
            return f"{g['min']}+{int(g['extra']) + 1}'"
        return f"{int(g['min']) + 1}'"
    if g["pct"] is not None:
        return f"{int(g['pct']) + 5}%"
    if g["dec"] is not None:
        value = float(g["dec"]) + 0.10
        return f"{value:+.2f}" if g["dec"][0] in "+-" else f"{value:.2f}"
    return str(int(g["int"]) + 1)


def _unused_number(claims: Sequence[Claim]) -> int:
    used = {abs(c.value) for c in claims}
    used |= {c.start.minute for c in claims} | {c.end.minute for c in claims}
    n = 7
    while n in used:
        n += 1
    return n


def _score_re(teams: dict[str, str]) -> re.Pattern[str]:
    return re.compile(re.escape(teams["home"]) + r" (\d+)–(\d+) " + re.escape(teams["away"]))


def _swap_player(sample: Sample, rng: random.Random, pool: Sequence[str]) -> Injection | None:
    mentioned = [p for p in sample.players if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", sample.text)]
    claimed = {c.subject.player for c in sample.claims}
    candidates = [p for p in pool if p not in claimed and p not in sample.text]
    if not mentioned or not candidates:
        return None
    old, new = rng.choice(mentioned), rng.choice(candidates)
    return Injection(re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", new, sample.text), sample.claims)


# --- slotify: v3 base -----------------------------------------------------------------------


def _ids(claims: Sequence[Claim]) -> tuple[str, ...]:
    return tuple(f"c{i + 1}" for i in range(len(claims)))


def slotify(sample: Sample) -> SlotDraft | None:
    """Turns a template draft into a v3 slot template; None if it does not convert cleanly."""
    ctx = SlotContext.from_moment(sample.moment, sample.events, sample.lang)
    template = _slot_text(sample.text, sample)
    if template is None:
        return None
    ids = _ids(sample.claims)
    items, _, _, _, _ = check_slot_draft(template, sample.claims, ids, ctx, V3_CONFIG)
    return SlotDraft(template, sample.claims, ids, ctx) if not items else None


def _slot_text(raw: str, sample: Sample) -> str | None:
    """Turns raw text into v3 placeholders (names, teams, score, numbers)."""
    claims = sample.claims
    ids = _ids(claims)
    text = _score_re(sample.teams).sub("{score}", raw)
    id_of = {name: pid for pid, name in player_ids(sample.events).items()}
    for name in sorted(id_of, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", f"{{player:{id_of[name]}}}", text)
    for side in ("home", "away"):
        text = re.sub(rf"(?<!\w){re.escape(sample.teams[side])}(?!\w)", f"{{{side}}}", text)
    for cid, c in zip(ids, claims):  # fixed label with a number ("… over the last 10 minutes of play")
        label = metric_label(c.metric, sample.lang)
        if label in WINDOW_PHRASES:
            text = text.replace(label, f"{{label:{cid}}}")

    masked = PLACEHOLDER_RE.sub(lambda m: "x" * len(m.group()), text)
    out, last = [], 0
    for m in NUMBER_RE.finditer(masked):
        g = m.groupdict()
        slot = None
        if g["min"] is not None:
            minute = int(g["min"]) + (int(g["extra"]) - 1 if g["extra"] else 0)
            end = next((i for i, c in enumerate(claims) if c.end.minute == minute), None)
            start = next((i for i, c in enumerate(claims) if c.start.minute == minute), None)
            if end is not None:
                slot = f"{{minute:{ids[end]}}}"
            elif start is not None:
                slot = f"{{start:{ids[start]}}}"
        elif g["pct"] is not None:
            p = int(g["pct"])
            i = next((i for i, c in enumerate(claims) if c.kind == "ratio" and abs(c.value * 100 - p) <= 0.5), None)
            slot = f"{{value:{ids[i]}}}" if i is not None else None
        else:
            v = abs(float(g["dec"] or g["int"]))
            i = next((i for i, c in enumerate(claims) if c.kind != "ratio" and abs(abs(c.value) - v) < 0.006), None)
            slot = f"{{value:{ids[i]}}}" if i is not None else None
        if slot is None:
            return None
        out += [text[last:m.start()], slot]
        last = m.end()
    return "".join(out) + text[last:]


# --- slotify_v4: v4 base ----------------------------------------------------------------------

# A v4 template per moment type; claims in the same order as the template narrator's (c1, c2, ...).
# {E} is the event placeholder, {T}/{O} the moment's team / opponent.
V4_BASE = {
    "goal": {"en": "{E}, making it {score_named}."},
    "penalty": {"en": "{E}."},
    "red_card": {"en": "{E}. {T} are down to {value:c2} players."},
    "pressure_shift": {
        "en": "{minute:c1} — {T} take control: {label:c1} {value:c1} in their favour. "
              "{label:c2} since {start:c2}: {T} {value:c2}, {O} {value:c3}.",
    },
    "dominance_without_reward": {
        "en": "{minute:c1} — {T} dominate without reward: since {start:c1} they have had {value:c1} of the "
              "ball and a {value:c2}–{value:c3} lead in {label:c2}, yet the score is {score_named}.",
    },
}
V4_BEHIND = {"en": " {T} had been {value:%s} down."}  # % the deficit claim's id
EVENT_MOMENTS = ("goal", "penalty", "red_card")


def _event_ref(sample: Sample) -> str | None:
    if sample.moment.type not in EVENT_MOMENTS:
        return None
    return sample.claims[0].event_ids[-1]  # the counted event: goal / penalty / red card


def slotify_v4(sample: Sample) -> SlotDraft | None:
    """v4 template with the template claims; None if it fails the v4 or v4.1 rules."""
    m = sample.moment
    template = V4_BASE[m.type][sample.lang]
    if m.detail.get("score_change", {}).get("from_behind"):
        deficit = next(i for i, c in enumerate(sample.claims) if c.metric == "min_score_margin")
        template += V4_BEHIND[sample.lang] % _ids(sample.claims)[deficit]
    ref = _event_ref(sample)
    template = template.replace("{T}", "{" + m.team + "}").replace("{O}", "{" + other(m.team) + "}")
    if ref is not None:
        template = template.replace("{E}", "{event:" + ref + "}")
    ctx = SlotContext.from_moment(m, sample.events, sample.lang)
    ids = _ids(sample.claims)
    for config in (V4_CONFIG, V41_CONFIG):
        items, _, _, _, _ = check_slot_draft(template, sample.claims, ids, ctx, config)
        if items:
            return None
    return SlotDraft(template, sample.claims, ids, ctx, ref)


# --- slotify_v5: v5 base (menu ids) -----------------------------------------------------------

# V4_BASE with menu ids.
V5_BASE = {
    "goal": {"en": "{E}, making it {score_named}."},
    "penalty": {"en": "{E}."},
    "red_card": {"en": "{E}. {T} are down to {value:players} players."},
    "pressure_shift": {
        "en": "{minute:pressure} — {T} take control: {label:pressure} {value:pressure} in their favour. "
              "{label:shots_for} since {start:shots_for}: {T} {value:shots_for}, {O} {value:shots_against}.",
    },
    "dominance_without_reward": {
        "en": "{minute:possession} — {T} dominate without reward: since {start:possession} they have had "
              "{value:possession} of the ball and a {value:shots_for}–{value:shots_against} lead in "
              "{label:shots_for}, yet the score is {score_named}.",
    },
}
V5_BEHIND = {"en": " {T} had been {value:deficit} down."}


def slotify_v5(sample: Sample) -> SlotDraft | None:
    """v5 template with menu ids; None if it fails the v5 rules."""
    m = sample.moment
    menu = build_menu(m, sample.events)
    template = V5_BASE[m.type][sample.lang]
    if m.detail.get("score_change", {}).get("from_behind"):
        template += V5_BEHIND[sample.lang]
    ref = _event_ref(sample)
    template = template.replace("{T}", "{" + m.team + "}").replace("{O}", "{" + other(m.team) + "}")
    if ref is not None:
        template = template.replace("{E}", "{event:" + ref + "}")
    ctx = SlotContext.from_moment(m, sample.events, sample.lang)
    items, *_ = check_menu_draft(template, menu, ctx, V5_CONFIG)
    if items:
        return None
    ids = tuple(c.id for c in menu.claims)
    return SlotDraft(template, tuple(c.claim for c in menu.claims), ids, ctx, ref, menu)


# --- v2 injections (free text) -----------------------------------------------------------


def v2_control(s, rng, foreign):
    return Injection(s.text, s.claims)


def v2_number_text(s, rng, foreign):
    tokens = list(NUMBER_RE.finditer(_masked(s)))
    if not tokens:
        return None
    m = rng.choice(tokens)
    return Injection(_splice(s.text, m.start(), m.end(), _bumped_number(m)), s.claims)


def v2_number_text_and_claim(s, rng, foreign):
    candidates = []
    for i, c in enumerate(s.claims):
        pattern = rf"(?<![\d.]){re.escape(_fmt(abs(c.value)))}(?![\d.%])"
        if c.kind != "ratio" and re.search(pattern, _masked(s)):
            candidates.append((i, c, pattern))
    if not candidates:
        return None
    i, c, pattern = rng.choice(candidates)
    step = 1 if float(c.value).is_integer() else 0.1
    new_value = round(c.value + step, 2)
    text = re.sub(pattern, _fmt(abs(new_value)), s.text, count=1)
    claims = list(s.claims)
    claims[i] = replace(c, value=new_value)
    return Injection(text, tuple(claims))


def v2_player_swap(s, rng, foreign):
    return _swap_player(s, rng, s.players)


def v2_foreign_player(s, rng, foreign):
    return _swap_player(s, rng, [p for p in foreign if p not in s.players])


def v2_unsupported_sentence_number(s, rng, foreign):
    extra = UNSUPPORTED_NUMBER[s.lang].format(team=s.teams[s.moment.team], n=_unused_number(s.claims))
    return Injection(f"{s.text} {extra}", s.claims)


def v2_unsupported_sentence_qualitative(s, rng, foreign):
    return Injection(f"{s.text} {UNSUPPORTED_QUALITATIVE[s.lang].format(team=s.teams[s.moment.team])}", s.claims)


def v2_number_words(s, rng, foreign):
    tokens = [m for m in NUMBER_RE.finditer(_masked(s)) if m.group("int") and int(m.group("int")) < 20]
    if not tokens:
        return None
    m = rng.choice(tokens)
    return Injection(_splice(s.text, m.start(), m.end(), NUMBER_WORDS[s.lang][int(m.group("int")) + 1]), s.claims)


def v2_sentence_start_fabricated(s, rng, foreign):
    return Injection(f"{FABRICATED_START[s.lang]} {s.text}", s.claims)


def v2_score_order_reversed(s, rng, foreign):
    m = _score_re(s.teams).search(s.text)
    if not m or m.group(1) == m.group(2):
        return None
    swapped = f"{s.teams['home']} {m.group(2)}–{m.group(1)} {s.teams['away']}"
    return Injection(_splice(s.text, m.start(), m.end(), swapped), s.claims)


def v2_raw_side_label(s, rng, foreign):
    side = s.moment.team
    name = s.teams[side]
    if name not in s.text:
        return None
    return Injection(s.text.replace(name, SIDE_LABEL[s.lang][side], 1), s.claims)


def _coincidence(s: Sample, value: float) -> int | None:
    """An integer that differs from the value in the text but appears in another claim (forced coincidence)."""
    others = sorted({int(abs(c.value)) for c in s.claims if float(c.value).is_integer() and abs(c.value) != value})
    return others[0] if others else None


def v2_free_number(s, rng, foreign):
    tokens = [m for m in NUMBER_RE.finditer(_masked(s)) if m.group("int")]
    rng.shuffle(tokens)
    for m in tokens:
        other = _coincidence(s, int(m.group("int")))
        if other is not None:
            return Injection(_splice(s.text, m.start(), m.end(), str(other)), s.claims)
    return None


# --- v3 injections (slot template) ---------------------------------------------------------


def _slot(s: Sample) -> SlotDraft | None:
    return s.slot


def _placeholders(template: str, kinds: Sequence[str]):
    return [p for p in parse_placeholders(template)[0] if p.kind in kinds]


def _inj(d: SlotDraft, template: str, claims: tuple[Claim, ...] | None = None) -> Injection:
    return Injection(template, d.claims if claims is None else claims, d.claim_ids)


def _claim_of(d: SlotDraft, cid: str) -> Claim:
    return d.claims[d.claim_ids.index(cid)]


def v3_control(s, rng, foreign):
    d = _slot(s)
    return _inj(d, d.template) if d else None


def v3_number_text(s, rng, foreign):
    d = _slot(s)
    phs = _placeholders(d.template, ("value", "minute", "start")) if d else []
    if not phs:
        return None
    ph = rng.choice(phs)
    raw = str(int(abs(_claim_of(d, ph.arg).value)) + 1)
    return _inj(d, _splice(d.template, ph.start, ph.end, raw))


def v3_number_text_and_claim(s, rng, foreign):
    d = _slot(s)
    if not d:
        return None
    candidates = [i for i, c in enumerate(d.claims) if c.kind != "ratio"]
    if not candidates:
        return None
    i = rng.choice(candidates)
    c = d.claims[i]
    claims = list(d.claims)
    claims[i] = replace(c, value=round(c.value + (1 if float(c.value).is_integer() else 0.1), 2))
    return _inj(d, d.template, tuple(claims))


def v3_player_swap(s, rng, foreign):
    d = _slot(s)
    phs = _placeholders(d.template, ("player",)) if d else []
    claimed = {c.subject.player for c in d.claims} if d else set()
    candidates = [pid for pid, name in d.ctx.players.items() if name not in claimed] if d else []
    if not phs or not candidates:
        return None
    ph = rng.choice(phs)
    return _inj(d, _splice(d.template, ph.start, ph.end, f"{{player:{rng.choice(candidates)}}}"))


def v3_foreign_player(s, rng, foreign):
    d = _slot(s)
    phs = _placeholders(d.template, ("player", "event")) if d else []
    outsiders = [p for p in foreign if p not in s.players]
    if not phs or not outsiders:
        return None
    ph = rng.choice(phs)
    return _inj(d, _splice(d.template, ph.start, ph.end, rng.choice(outsiders)))


def v3_unsupported_sentence_number(s, rng, foreign):
    d = _slot(s)
    if not d:
        return None
    extra = UNSUPPORTED_NUMBER[s.lang].format(team=f"{{{s.moment.team}}}", n=_unused_number(d.claims))
    return _inj(d, f"{d.template} {extra}")


def v3_unsupported_sentence_qualitative(s, rng, foreign):
    d = _slot(s)
    if not d:
        return None
    return _inj(d, f"{d.template} {UNSUPPORTED_QUALITATIVE[s.lang].format(team='{' + s.moment.team + '}')}")


def v3_number_words(s, rng, foreign):
    d = _slot(s)
    phs = [p for p in _placeholders(d.template, ("value",)) if abs(_claim_of(d, p.arg).value) < 20] if d else []
    if not phs:
        return None
    ph = rng.choice(phs)
    word = NUMBER_WORDS[s.lang][int(abs(_claim_of(d, ph.arg).value)) + 1]
    return _inj(d, _splice(d.template, ph.start, ph.end, word))


def v3_sentence_start_fabricated(s, rng, foreign):
    d = _slot(s)
    return _inj(d, f"{FABRICATED_START[s.lang]} {d.template}") if d else None


def v3_score_order_reversed(s, rng, foreign):
    d = _slot(s)
    m = _score_re(s.teams).search(s.text)
    if not d or "{score}" not in d.template or not m or m.group(1) == m.group(2):
        return None
    return _inj(d, d.template.replace("{score}", f"{{home}} {m.group(2)}–{m.group(1)} {{away}}", 1))


def v3_raw_side_label(s, rng, foreign):
    d = _slot(s)
    slot = "{" + s.moment.team + "}"
    if not d or slot not in d.template:
        return None
    return _inj(d, d.template.replace(slot, SIDE_LABEL[s.lang][s.moment.team], 1))


def v3_free_number(s, rng, foreign):
    d = _slot(s)
    phs = _placeholders(d.template, ("value",)) if d else []
    rng.shuffle(phs)
    for ph in phs:
        other = _coincidence(s, abs(_claim_of(d, ph.arg).value))
        if other is not None:
            return _inj(d, _splice(d.template, ph.start, ph.end, str(other)))
    return None


def v3_wrong_slot_binding(s, rng, foreign):
    d = _slot(s)
    if not d:
        return None
    phs = _placeholders(d.template, ("value", "minute"))
    pairs = [
        (a, b) for i, a in enumerate(phs) for b in phs[i + 1:]
        if a.kind == b.kind and a.arg != b.arg
        and _claim_of(d, a.arg).value != _claim_of(d, b.arg).value
    ]
    if not pairs:
        return None
    a, b = rng.choice(pairs)
    t = d.template
    t = t[:b.start] + a.raw + t[b.end:]
    t = t[:a.start] + b.raw + t[a.end:]
    return _inj(d, t)


# --- v4 injections: the v3 injector on the v4 base ------------------------------------------------


def on_v4(inject: Injector) -> Injector:
    """Applies a v3 injector to the v4 base (same meaning, v4 template form)."""

    def run(s, rng, foreign):
        return inject(replace(s, slot=s.slot4), rng, foreign) if s.slot4 else None

    run.__name__ = f"v4_{inject.__name__.removeprefix('v3_')}"
    return run


def on_v5(inject: Injector | None) -> Injector | None:
    """Applies a v3/v4 injector to the v5 base. An injection that changes a claim cannot be expressed in v5
    (the model writes no claims, the menu is fixed): None."""
    if inject is None:
        return None

    def run(s, rng, foreign):
        d = s.slot5
        if d is None:
            return None
        inj = inject(replace(s, slot=d, slot4=d), rng, foreign)
        if inj is None or inj.claims != d.claims:
            return None
        return replace(inj, claim_ids=d.claim_ids)

    run.__name__ = f"v5_{inject.__name__.split('_', 1)[1]}"
    return run


def _score_at(s: Sample) -> tuple[int, int]:
    t = s.slot4.ctx.moment_time
    return tuple(int(measure("score", Subject(side), KICKOFF, t, s.events).value) for side in ("home", "away"))


def v4_score_order_reversed(s, rng, foreign):
    d = s.slot4
    if not d:
        return None
    h, a = _score_at(s)
    if h == a:
        return None
    if "{score_named}" in d.template:
        return _inj(d, d.template.replace("{score_named}", f"{{home}} {a}–{h} {{away}}", 1))
    if "{score}" in d.template:
        return _inj(d, d.template.replace("{score}", f"{a}–{h}", 1))
    return None


# --- new types (foundry-v4) --------------------------------------------------------------------

# Event sentence with a reversed role: the penalty taker "saved", the scorer "saved/conceded", the sent-off player "drew a red card".
# A few phrases per type; some deliberately contain no event word (to test the ban list).
REVERSED_ROLE = {
    "goal": {
        "en": ("{p} saved the shot at {m}", "{p} conceded at {m}", "{p} kept it out at {m}"),
    },
    "penalty": {
        "en": ("{p} saved a penalty at {m}", "{p} stopped the spot-kick at {m}", "{p} kept the kick out at {m}"),
    },
    "red_card": {
        "en": ("{p} drew a red card at {m}", "{p} was brought down and saw a rival dismissed at {m}",
               "{p} was the victim of the challenge at {m}"),
    },
}
FABRICATED_NAMES = ("Ravello", "Okonde", "Marisk", "Telvano", "Quintara", "Dusko", "Fernhal", "Albrecz")
FABRICATED_PREDICATES = {
    "en": ("{n} pressed high.", "{n} kept running.", "{n} looked sharp."),
}
# Qualitative overstatement: written independently of the lint ban list; some are not on it. (EN, supporting types)
OVERSTATED = (
    ("{t} were utterly dominant.", ("dominance_without_reward",)),
    ("{t} pushed on deep into stoppage time.", ()),
    ("{t} completely took control.", ("pressure_shift",)),
    ("{t} were stunning.", ()),
    ("{t} were relentless.", ()),
    ("{t} ran the show.", ()),
    ("{t} were in total command.", ()),
    ("{t} deserved more.", ()),
    ("{t} put on a masterclass.", ()),
)


def _role_phrase(s: Sample, rng: random.Random, p: str, m: str) -> tuple[str, str] | None:
    phrases = REVERSED_ROLE.get(s.moment.type, {}).get(s.lang)
    if not phrases:
        return None
    template = rng.choice(phrases)
    return template.format(p=p, m=m), template.format(p="X", m="m").replace("X ", "", 1)


def _pid(s: Sample, name: str) -> str:
    return {n: pid for pid, n in player_ids(s.events).items()}[name]


def v2_role_reversed(s, rng, foreign):
    if s.moment.type not in REVERSED_ROLE:
        return None
    player = s.moment.detail["player"]
    phrase = _role_phrase(s, rng, player, fmt_minute(s.moment.period, s.moment.minute))
    rest = " ".join(s.sentences[1:])
    return Injection(f"{phrase[0]}. {rest}".strip(), s.claims, tag=phrase[1])


def v3_role_reversed(s, rng, foreign):
    d = _slot(s)
    if not d or s.moment.type not in REVERSED_ROLE:
        return None
    phrase = _role_phrase(s, rng, f"{{player:{_pid(s, s.moment.detail['player'])}}}", "{minute:c1}")
    rest = _slot_text(" ".join(s.sentences[1:]), s) if len(s.sentences) > 1 else ""
    if rest is None:
        return None
    return Injection(f"{phrase[0]}. {rest}".strip(), d.claims, d.claim_ids, tag=phrase[1])


def v4_role_reversed(s, rng, foreign):
    d = s.slot4
    if not d or not d.event_ref or s.moment.type not in REVERSED_ROLE:
        return None
    phrase = _role_phrase(s, rng, f"{{player:{_pid(s, s.moment.detail['player'])}}}", "{minute:c1}")
    template = d.template.replace("{event:" + d.event_ref + "}", phrase[0], 1)
    return Injection(template, d.claims, d.claim_ids, tag=phrase[1])


def _other_event(s: Sample, rng: random.Random) -> Event | None:
    """A real event with a different phrase from the moment's event: first those in the moment record, else earlier ones of the same type."""
    d = s.slot4
    if not d or not d.event_ref:
        return None
    by_seq = {e.seq: e for e in s.events}
    own = d.ctx.event(d.event_ref)
    phrase = d.ctx.phrase(d.event_ref)
    record = [by_seq[q] for q in dict.fromkeys(s.moment.event_ids)]
    candidates = []
    for e in record:
        ref = f"{s.events[0].match_id}#{e.seq}"
        if e.seq != own.seq and d.ctx.phrase(ref) not in (None, phrase):
            candidates.append(e)
    if not candidates:
        candidates = [
            e for e in s.events
            if e.type is own.type and e.seq < own.seq
            and d.ctx.phrase(f"{s.events[0].match_id}#{e.seq}") not in (None, phrase)
        ]
    return rng.choice(candidates) if candidates else None


def _evidence_tag(s: Sample, e: Event) -> str:
    ref = f"{s.events[0].match_id}#{e.seq}"
    menu = s.slot4.menu if s.slot4 else None  # v5 (on_v5): evidence membership by the menu
    claims = [c.claim for c in menu.claims] if menu else s.claims
    cited = any(ref in c.event_ids for c in claims)
    return f"{e.type.value}, {'evidence of a claim' if cited else 'not evidence'}"


def v4_event_wrong_claim(s, rng, foreign):
    e = _other_event(s, rng)
    if e is None:
        return None
    d = s.slot4
    ref = f"{s.events[0].match_id}#{e.seq}"
    template = d.template.replace("{event:" + d.event_ref + "}", "{event:" + ref + "}", 1)
    return Injection(template, d.claims, d.claim_ids, tag=_evidence_tag(s, e))


def _wrong_player(s: Sample, rng: random.Random) -> tuple[str, str, Event] | None:
    """v2/v3 counterpart: the player of the event sentence is swapped for the player of another real event."""
    if s.moment.type not in REVERSED_ROLE:
        return None
    e = _other_event(s, rng)
    if e is None or not e.player or e.player == s.moment.detail["player"]:
        return None
    return s.moment.detail["player"], e.player, e


def v2_event_wrong_claim(s, rng, foreign):
    found = _wrong_player(s, rng)
    if found is None:
        return None
    old, new, e = found
    text = re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", new, s.text, count=1)
    return Injection(text, s.claims, tag=_evidence_tag(s, e))


def v3_event_wrong_claim(s, rng, foreign):
    d = _slot(s)
    found = _wrong_player(s, rng) if d else None
    if found is None:
        return None
    old, new, e = found
    template = d.template.replace(f"{{player:{_pid(s, old)}}}", f"{{player:{_pid(s, new)}}}", 1)
    return Injection(template, d.claims, d.claim_ids, tag=_evidence_tag(s, e))


def _insert_sentence(base: str, starts: Sequence[int], rng: random.Random, sentence: str) -> str:
    pos = rng.choice(list(starts))
    return f"{base[:pos]}{sentence} {base[pos:]}"


def _fabricated(s: Sample, rng: random.Random) -> tuple[str, str]:
    name = rng.choice(FABRICATED_NAMES)
    return rng.choice(FABRICATED_PREDICATES[s.lang]).format(n=name), name


def v2_sentence_start_fabricated_name(s, rng, foreign):
    sentence, name = _fabricated(s, rng)
    return Injection(_insert_sentence(s.text, list(sentence_starts(s.text)), rng, sentence), s.claims, tag=name)


def _slot_fabricated(d: SlotDraft | None, s: Sample, rng: random.Random) -> Injection | None:
    if not d:
        return None
    sentence, name = _fabricated(s, rng)
    starts = [pos for pos, _ in template_sentence_starts(d.template)]
    return Injection(_insert_sentence(d.template, starts, rng, sentence), d.claims, d.claim_ids, tag=name)


def v3_sentence_start_fabricated_name(s, rng, foreign):
    return _slot_fabricated(_slot(s), s, rng)


def v4_sentence_start_fabricated_name(s, rng, foreign):
    return _slot_fabricated(s.slot4, s, rng)


def _overstated(s: Sample, rng: random.Random, team: str) -> tuple[str, str]:
    options = [o for o in OVERSTATED if s.moment.type not in o[1]]
    template, _ = rng.choice(options)
    return template.format(t=team), template.replace("{t} ", "")


def v2_qualitative_overstatement(s, rng, foreign):
    sentence, tag = _overstated(s, rng, s.teams[s.moment.team])
    return Injection(f"{s.text} {sentence}", s.claims, tag=tag)


def _slot_overstated(d: SlotDraft | None, s: Sample, rng: random.Random) -> Injection | None:
    if not d:
        return None
    sentence, tag = _overstated(s, rng, "{" + s.moment.team + "}")
    return Injection(f"{d.template} {sentence}", d.claims, d.claim_ids, tag=tag)


def v3_qualitative_overstatement(s, rng, foreign):
    return _slot_overstated(_slot(s), s, rng)


def v4_qualitative_overstatement(s, rng, foreign):
    return _slot_overstated(s.slot4, s, rng)


def v5_role_reversed(s, rng, foreign):
    """Menu counterpart of v4_role_reversed: the minute comes from the menu claim that counts the event as evidence."""
    d = s.slot5
    if not d or not d.event_ref or s.moment.type not in REVERSED_ROLE:
        return None
    owner = d.menu.evidence_owner(d.event_ref)
    phrase = _role_phrase(s, rng, f"{{player:{_pid(s, s.moment.detail['player'])}}}", "{minute:" + owner + "}")
    template = d.template.replace("{event:" + d.event_ref + "}", phrase[0], 1)
    return Injection(template, d.claims, d.claim_ids, tag=phrase[1])


def _unknown_id(d: SlotDraft | None, new_id: str) -> Injection | None:
    """A claim placeholder's id is swapped for an undefined id (otherwise the score for a {value:})."""
    if d is None:
        return None
    phs = _placeholders(d.template, ("value", "minute", "start", "label", "clause"))
    if phs:
        ph = phs[0]
        return Injection(_splice(d.template, ph.start, ph.end, "{" + ph.kind + ":" + new_id + "}"),
                         d.claims, d.claim_ids, tag=ph.kind)
    for score in ("{score_named}", "{score}"):
        if score in d.template:
            return Injection(d.template.replace(score, "{value:" + new_id + "}", 1), d.claims, d.claim_ids,
                             tag="score")
    return None


def v3_unknown_id(s, rng, foreign):
    return _unknown_id(_slot(s), "c99")


def v4_unknown_id(s, rng, foreign):
    return _unknown_id(s.slot4, "c99")


def v5_unknown_id(s, rng, foreign):
    return _unknown_id(s.slot5, "possession_since_kickoff")  # plausible-looking id that is not on the menu


# --- player repeat (foundry-v4.1) -------------------------------------------------------------

REPEAT_SUFFIX = {"en": " by {p}"}


def _repeated_player(s: Sample) -> str | None:
    """The player of the event sentence; only if they are the subject of a claim (so the placeholder binds and the meaning stays)."""
    player = s.moment.detail.get("player") if s.moment.type in EVENT_MOMENTS else None
    if not player or player not in {c.subject.player for c in s.claims}:
        return None
    return player


def _into_first_sentence(text: str, starts: Sequence[int], addition: str) -> str | None:
    """Inserts `addition` right before the closing punctuation of the first sentence."""
    later = [pos for pos in starts if pos > 0]
    end = (text[:later[0]].rstrip() if later else text.rstrip())
    if not end.endswith((".", "!", "?")):
        return None
    cut = len(end) - 1
    return text[:cut] + addition + text[cut:]


def v2_player_repeat(s, rng, foreign):
    player = _repeated_player(s)
    if player is None or player not in s.sentences[0]:
        return None
    text = _into_first_sentence(s.text, list(sentence_starts(s.text)), REPEAT_SUFFIX[s.lang].format(p=player))
    return Injection(text, s.claims, tag=s.moment.type) if text else None


def v3_player_repeat(s, rng, foreign):
    d, player = _slot(s), _repeated_player(s)
    if d is None or player is None:
        return None
    pid = "{player:" + _pid(s, player) + "}"
    starts = [pos for pos, _ in template_sentence_starts(d.template)]
    first_end = min([pos for pos in starts if pos > 0], default=len(d.template))
    if pid not in d.template[:first_end]:
        return None
    template = _into_first_sentence(d.template, starts, REPEAT_SUFFIX[s.lang].format(p=pid))
    return Injection(template, d.claims, d.claim_ids, tag=s.moment.type) if template else None


def v4_player_repeat(s, rng, foreign):
    d = s.slot4
    if d is None or not d.event_ref or _repeated_player(s) is None:
        return None
    e = d.ctx.event(d.event_ref)
    if e is None or not e.player or e.player not in {c.subject.player for c in d.claims}:
        return None
    placeholder = "{event:" + d.event_ref + "}"
    pid = "{player:" + _pid(s, e.player) + "}"
    template = d.template.replace(placeholder, placeholder + REPEAT_SUFFIX[s.lang].format(p=pid), 1)
    return Injection(template, d.claims, d.claim_ids, tag=s.moment.type)


@dataclass(frozen=True)
class InjectionType:
    name: str
    description: str
    v2: Injector | None
    v3: Injector | None
    v4: Injector | None = None
    miss_v2: str = "—"
    miss_v3: str = "—"
    miss_v4: str = "—"
    new: str | None = None  # version that added the type ("v4", "v4.1")
    v41: Injector | None | str = "v4"  # "v4": same as the v4 injector (same base)
    miss_v41: str | None = None  # None: v4's reason
    v5: Injector | None | str = "v4"  # "v4": the v4 injector on the v5 base (on_v5)
    miss_v5: str | None = None  # None: v4.1's reason

    def injector(self, variant: str) -> Injector | None:
        if variant == "v41":
            return self.v4 if self.v41 == "v4" else self.v41  # type: ignore[return-value]
        if variant == "v5":
            return on_v5(self.v4) if self.v5 == "v4" else self.v5  # type: ignore[return-value]
        return getattr(self, variant)

    def miss(self, variant: str) -> str:
        if variant == "v41":
            return self.miss_v41 if self.miss_v41 is not None else self.miss_v4
        if variant == "v5":
            return self.miss_v5 if self.miss_v5 is not None else self.miss("v41")
        return getattr(self, f"miss_{variant}")


COINCIDENCE = ("Lint checks whether a number appears in any claim, not which claim it belongs to; "
               "a correct-looking number in the wrong place passes.")
QUALITATIVE = ("The sentence has no number and no new name; qualitative judgements are outside lint and verify.")
QUALITATIVE_V4 = ("The sentence starts with a placeholder and has no number or event word; \"were the better side\" "
                  "is not on the overstatement list (a judgement, not hype). Qualitative judgements stay out of scope in v4.")
SENTENCE_START = ("A single capitalized word at the sentence start is not treated as a name (capitals there are normal); "
                  "a one-word name that is not in the squad goes unnoticed in this position.")
AMBIGUOUS = ("An ambiguous word (EN \"one\") is not counted as a number unless a countable noun follows "
             "(to avoid false alarms on uses such as \"one of\").")
SLOT_BINDING = ("Every placeholder is bound to a verified claim of the right kind; where each claim belongs "
                "in the sentence is not checked.")
LOOSE_BOUND = "A loosened inequality claim (`score_margin lte 0` → `lte 1`) is still true."
NO_ROLE_CHECK = "The name is the subject of a claim and the minute is right; lint and verify do not know the event role (who scored / who saved)."
ROLE_V4 = ("A reversed role is not caught when written with a verb that is not on the event word ban list (\"kept it out\", "
           "\"victim of the challenge\"); catching it depends on the lexicon.")
WRONG_EVENT_V4 = ("If the wrong event picked is evidence of another claim, it passes the {event:} binding rule "
                  "(only being \"evidence of a claim\" is required, not matching its role in the sentence).")
WRONG_EVENT_V2V3 = ("If the new player is the subject of a claim, the name counts as supported; the event-player match is not checked.")
OVERSTATEMENT_V4 = ("The phrase is not on the overstatement list (the list is fixed; synonyms and idioms slip through).")
SLOT_BINDING_V5 = ("The menu id is right and verified but in the wrong place in the sentence: the menu does not know "
                   "which team / which words a {value:} belongs to (\"{home} {value:shots_against}\"). Measured only "
                   "on templates that place {value:}s; a template that uses {clause:} has no value to swap, "
                   "code writes the clause values.")
WRONG_EVENT_V5 = ("Since menu evidence is complete (e.g. every goal since kickoff), the wrong event is usually "
                  "evidence of some menu claim; the {event:} binding rule checks evidence membership, not the role in the sentence.")
REPEAT_V2V3 = ("The name is the subject of a claim; naming it a second time adds no new number or name; a repeat "
               "within one sentence is not checked.")
REPEAT_V4 = ("The {player:} player is the subject of a claim, so the placeholder binds; that the {event:} phrase "
             "already names the player is not checked (v4's gap).")

INJECTION_TYPES = (
    InjectionType("control", "No change (false alarm measurement)", v2_control, v3_control, on_v4(v3_control)),
    InjectionType("number_text", "A number is written wrong (v3/v4: a raw number instead of a placeholder)",
                  v2_number_text, v3_number_text, on_v4(v3_number_text), miss_v2=COINCIDENCE),
    InjectionType("number_text_and_claim", "The claim value is wrong (v2: together with the text)",
                  v2_number_text_and_claim, v3_number_text_and_claim, on_v4(v3_number_text_and_claim),
                  miss_v2=LOOSE_BOUND, miss_v3=LOOSE_BOUND + " Verify measures whether the value is right, not how tight the bound is.",
                  miss_v4=LOOSE_BOUND + " Verify measures whether the value is right, not how tight the bound is.",
                  v5=None),
    InjectionType("player_swap", "The player is swapped for another player from the same match with no claim (v4: the base has no {player:}, "
                  "its counterpart is `event_wrong_claim`)",
                  v2_player_swap, v3_player_swap, None),
    InjectionType("foreign_player", "The player is swapped for a player from another match (v3/v4: raw name)",
                  v2_foreign_player, v3_foreign_player, on_v4(v3_foreign_player),
                  miss_v2="The foreign player's surname matches the claimed player's; the surname is supported as an alias, "
                          "and the name sits at a sentence start after \"—\"."),
    InjectionType("unsupported_sentence_number", "A new sentence with a number and no claim",
                  v2_unsupported_sentence_number, v3_unsupported_sentence_number,
                  on_v4(v3_unsupported_sentence_number)),
    InjectionType("unsupported_sentence_qualitative", "A new qualitative sentence with no claim (\"were the better side\")",
                  v2_unsupported_sentence_qualitative, v3_unsupported_sentence_qualitative,
                  on_v4(v3_unsupported_sentence_qualitative),
                  miss_v2=QUALITATIVE, miss_v3=QUALITATIVE, miss_v4=QUALITATIVE_V4),
    InjectionType("number_words", "A wrong number written as a word (\"two\")",
                  v2_number_words, v3_number_words, on_v4(v3_number_words),
                  miss_v2=AMBIGUOUS + " Or: " + COINCIDENCE, miss_v3=AMBIGUOUS),
    InjectionType("sentence_start_fabricated", "A sentence with a made-up name at the start (\"Quintana scores.\")",
                  v2_sentence_start_fabricated, v3_sentence_start_fabricated,
                  on_v4(v3_sentence_start_fabricated), miss_v2=SENTENCE_START, miss_v3=SENTENCE_START),
    InjectionType("score_order_reversed", "Score order reversed (away–home)",
                  v2_score_order_reversed, v3_score_order_reversed, v4_score_order_reversed,
                  miss_v2="Both score digits appear in a score claim; lint does not know the order."),
    InjectionType("raw_side_label", "A raw \"home/away\" label instead of the team name",
                  v2_raw_side_label, v3_raw_side_label, on_v4(v3_raw_side_label),
                  miss_v2="A lowercase \"home side\" is neither a number nor a name; the v2 lint does not check labels."),
    InjectionType("free_number", "Free-written number: another claim's value is written in the wrong place",
                  v2_free_number, v3_free_number, on_v4(v3_free_number), miss_v2=COINCIDENCE),
    InjectionType("wrong_slot_binding", "A placeholder is bound to the wrong claim (two references swap places)",
                  None, v3_wrong_slot_binding, on_v4(v3_wrong_slot_binding),
                  miss_v3=SLOT_BINDING + " (v3's gap)", miss_v4=SLOT_BINDING + " Still open in v4.",
                  miss_v5=SLOT_BINDING_V5),
    InjectionType("role_reversed", "Reversed role: the event sentence is written with the player's reversed role "
                  "(the penalty taker \"saved a penalty\")",
                  v2_role_reversed, v3_role_reversed, v4_role_reversed,
                  miss_v2=NO_ROLE_CHECK, miss_v3=NO_ROLE_CHECK, miss_v4=ROLE_V4, new="v4", v5=v5_role_reversed),
    InjectionType("event_wrong_claim", "Placeholder bound to the wrong claim: the event is bound to another real event "
                  "(v4: {event:} another event; v2/v3: the event sentence's player is that event's player)",
                  v2_event_wrong_claim, v3_event_wrong_claim, v4_event_wrong_claim,
                  miss_v2=WRONG_EVENT_V2V3, miss_v3=WRONG_EVENT_V2V3, miss_v4=WRONG_EVENT_V4, new="v4",
                  miss_v5=WRONG_EVENT_V5),
    InjectionType("sentence_start_fabricated_name", "A sentence with a made-up name at a random sentence boundary, with no event word "
                  "and no number (\"Ravello pressed high.\")",
                  v2_sentence_start_fabricated_name, v3_sentence_start_fabricated_name,
                  v4_sentence_start_fabricated_name,
                  miss_v2=SENTENCE_START, miss_v3=SENTENCE_START, new="v4"),
    InjectionType("qualitative_overstatement", "A qualitative overstatement sentence the moment type does not support "
                  "(from an independently written list)",
                  v2_qualitative_overstatement, v3_qualitative_overstatement, v4_qualitative_overstatement,
                  miss_v2=QUALITATIVE, miss_v3=QUALITATIVE, miss_v4=OVERSTATEMENT_V4, new="v4"),
    InjectionType("player_repeat", "Player repeat: the event's player is added to the event sentence again "
                  "(\"scored at 90+1' by X\"; v4/v4.1: {event:} + the same player's {player:})",
                  v2_player_repeat, v3_player_repeat, v4_player_repeat,
                  miss_v2=REPEAT_V2V3, miss_v3=REPEAT_V2V3, miss_v4=REPEAT_V4, new="v4.1"),
    InjectionType("unknown_menu_id", "Reference to an undefined id: a claim placeholder is bound to an id that is not "
                  "in the claims / on the menu (v5: the plausible-looking `possession_since_kickoff`)",
                  None, v3_unknown_id, v4_unknown_id, new="v5", v5=v5_unknown_id),
)


# --- measurement ---------------------------------------------------------------------------------


@dataclass
class Stats:
    applicable: int = 0
    caught: int = 0
    missed_example: tuple[str, str] | None = None
    tags: Counter[str] = field(default_factory=Counter)  # phrase/name applied → count
    missed_tags: Counter[str] = field(default_factory=Counter)

    @property
    def rate(self) -> float | None:
        return self.caught / self.applicable if self.applicable else None


@dataclass
class TypeResult:
    spec: InjectionType
    v2: Stats = field(default_factory=Stats)
    v3: Stats = field(default_factory=Stats)
    v4: Stats = field(default_factory=Stats)
    v41: Stats = field(default_factory=Stats)
    v5: Stats = field(default_factory=Stats)


@dataclass
class EvalReport:
    corpus: list[tuple[int, str | None]]
    samples: int
    slotified: int
    slotified_v4: int = 0
    slotified_v5: int = 0
    v2_number_words_without_fix: float | None = None
    results: list[TypeResult] = field(default_factory=list)
    rule_rates: list[lint_rates.RuleRate] = field(default_factory=list)
    held_out: tuple | None = None
    llm_texts: int = 0
    # Texts where the overstatement rule fires on foundry-v3 LLM templates: (moment, fragments, human label)
    overstatement_llm: list[tuple[str, list[str], str]] = field(default_factory=list)
    # v4.1 changes ("They" removed + new rules) on clean datasets: dataset → (fired, total, fragments)
    v41_false_alarms: list[tuple[str, int, int, Counter[str]]] = field(default_factory=list)
    # v5 allowed sentence-start change ("At", "Possession" removed): same shape
    v5_false_alarms: list[tuple[str, int, int, Counter[str]]] = field(default_factory=list)
    # v5.1 team repeat rule: dataset → (fired, total, fragments, fired texts)
    team_repeat: list[tuple[str, int, int, Counter[str], list[str]]] = field(default_factory=list)
    # clean v5 menu drafts where the template rule and the count on the rendered text disagree
    team_repeat_disagreements: list[str] = field(default_factory=list)
    # foundry-v5.2 team repeat variants (TEAM_REPEAT_MODES): one row per mode
    team_repeat_variants: list[RepeatVariant] = field(default_factory=list)
    # foundry-v5.2 primary claims on archived published templates: version → (fired, total, firings)
    primary_v52: list[tuple[str, int, int, list[tuple[lint_rates.MenuDraft, str]]]] = field(default_factory=list)
    primary_v52_base: tuple[int, int] = (0, 0)  # clean v5 menu base: (fired, total)


@dataclass
class RepeatVariant:
    """One team repeat variant (exempt mode, limit) on the required minimum and the one-sentence draft space."""

    name: str
    mode: str
    limit: int
    minimum_rejected: int = 0
    minimum_total: int = 0
    minimum_examples: list[str] = field(default_factory=list)
    space_valid: int = 0  # drafts that pass every other menu rule
    space_rejected: int = 0  # ... that team_repeat rejects
    space_passed: int = 0
    space_monotone: int = 0  # passed drafts with a team named 3+ times in the rendered sentence
    space_prose_monotone: int = 0  # ... 3+ times outside the score line


def _rng(moment: Moment, type_name: str, lang: str, variant: str) -> random.Random:
    digest = hashlib.sha256(f"{moment.id}|{type_name}|{lang}|{variant}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def build_samples(corpus: Sequence[tuple[int, str | None]]) -> tuple[list[Sample], list[str]]:
    samples, all_players = [], []
    for seed, scenario in corpus:
        events = generate_match(seed, scenario)
        meta = events[0].data["teams"]
        players = tuple(p for side in ("home", "away") for p in (*meta[side]["lineup"], *meta[side]["bench"]))
        all_players += [p for p in players if p not in all_players]
        roster = Roster.from_events(events)
        teams = {side: meta[side]["name"] for side in ("home", "away")}
        for m in detect_moments(events):
            narration = template_narrate(m, events)
            claims = tuple(c for s in narration.sentences for c in s.claims)
            for lang in LANGS:
                sentences = tuple(s.text[lang] for s in narration.sentences)
                base = Sample(events, roster, players, teams, m, lang, " ".join(sentences), claims,
                              sentences=sentences)
                samples.append(replace(base, slot=slotify(base), slot4=slotify_v4(base), slot5=slotify_v5(base)))
    return samples, all_players


def _check(variant: str, s: Sample, inj: Injection, config: ExplainConfig) -> bool:
    if variant == "v2":
        items, _, _ = check_draft(inj.text, inj.claims, s.events, s.roster, config, s.lang)
    elif variant == "v5":
        items, *_ = check_menu_draft(inj.text, s.slot5.menu, s.slot5.ctx, config)
    else:
        ctx = (s.slot if variant == "v3" else s.slot4).ctx  # v4 and v4.1 share a base
        items, *_ = check_slot_draft(inj.text, inj.claims, inj.claim_ids, ctx, config)
    return bool(items)


def run_eval(
    corpus: Sequence[tuple[int, str | None]] = FULL_CORPUS,
    configs: dict[str, ExplainConfig] | None = None,
) -> EvalReport:
    configs = configs or CONFIGS
    samples, all_players = build_samples(corpus)
    report = EvalReport(list(corpus), len(samples), sum(s.slot is not None for s in samples),
                        sum(s.slot4 is not None for s in samples), sum(s.slot5 is not None for s in samples))
    for spec in INJECTION_TYPES:
        result = TypeResult(spec)
        for s in samples:
            v4_base = s.slot4.template if s.slot4 else None
            bases = {"v2": s.text, "v3": s.slot.template if s.slot else None, "v4": v4_base, "v41": v4_base,
                     "v5": s.slot5.template if s.slot5 else None}
            for variant in VARIANTS:
                inject = spec.injector(variant)
                if inject is None or bases[variant] is None:
                    continue
                rng_variant = "v4" if variant == "v41" else variant  # same base: same injection
                inj = inject(s, _rng(s.moment, spec.name, s.lang, rng_variant), all_players)
                if inj is None:
                    continue
                stats = getattr(result, variant)
                stats.applicable += 1
                caught = _check(variant, s, inj, configs[variant])
                stats.caught += caught
                if inj.tag:
                    stats.tags[inj.tag] += 1
                    if not caught:
                        stats.missed_tags[inj.tag] += 1
                if not caught and spec.name != "control" and stats.missed_example is None:
                    stats.missed_example = (bases[variant], inj.text)
        report.results.append(result)

    # Note: v2's number_words catch rate with the number-word check off (effect of the earlier fix).
    off = replace(configs["v2"], lint_number_words=False)
    nw = next(t for t in INJECTION_TYPES if t.name == "number_words")
    caught = applicable = 0
    for s in samples:
        inj = nw.v2(s, _rng(s.moment, nw.name, s.lang, "v2"), all_players)
        if inj is not None:
            applicable += 1
            caught += _check("v2", s, inj, off)
    report.v2_number_words_without_fix = caught / applicable if applicable else None

    # False alarms of the v4 / v4.1 rules: clean drafts and real LLM outputs.
    raw = [lint_rates.Text("template", s.lang, s.moment.id, s.moment.type,
                           lint_rates.to_template(s.text, s.roster), s.text, s.roster) for s in samples]
    v3_templates = [lint_rates.Text("v3-slot", s.lang, s.moment.id, s.moment.type, s.slot.template)
                    for s in samples if s.slot]
    v4_templates = [lint_rates.Text("v4-slot", s.lang, s.moment.id, s.moment.type, s.slot4.template,
                                    ctx=s.slot4.ctx) for s in samples if s.slot4]
    llm = lint_rates.llm_outputs()
    report.llm_texts = len(llm)
    clean = [
        ("Template drafts (raw text)", raw),
        ("v3 slot templates (clean)", v3_templates),
        ("v4 slot base (clean)", v4_templates),
        ("Real LLM, foundry-v2 free text", [t for t in llm if t.source == "llm-v2"]),
        ("Real LLM, foundry-v3 template", [t for t in llm if t.source == "llm-v3"]),
    ]
    datasets = [*clean, ("Real LLM, foundry-v4 template", lint_rates.llm_v4_outputs())]
    report.rule_rates = lint_rates.rule_rates(datasets, configs["v41"])
    # False alarms of the v4.1 changes: clean drafts that pass the v4 rules but fail v4.1.
    for name, texts in clean:
        hits = Counter()
        flagged = 0
        for t in texts:
            new = [f for rule in lint_rates.V41_RULES for f in lint_rates.fired(t, rule, configs["v41"])]
            old_starts = set(lint_rates.fired(t, "sentence_start", configs["v4"]))
            new += [f for f in lint_rates.fired(t, "sentence_start", configs["v41"]) if f not in old_starts]
            flagged += bool(new)
            hits.update(new)
        report.v41_false_alarms.append((name, flagged, len(texts), hits))
    for name, texts in datasets:
        hits = Counter()
        flagged = 0
        for t in texts:
            old_starts = set(lint_rates.fired(t, "sentence_start", configs["v41"]))
            new = [f for f in lint_rates.fired(t, "sentence_start", configs["v5"]) if f not in old_starts]
            flagged += bool(new)
            hits.update(new)
        report.v5_false_alarms.append((name, flagged, len(texts), hits))
    report.held_out = lint_rates.held_out_sentence_starts(raw, llm)
    _team_repeat(report, samples, configs["v5"])
    _team_repeat_variants(report, samples, configs["v5"])
    _primary_v52(report, samples, configs["v5"])
    for t in llm:
        hits = lint_rates.fired(t, "overstatement", configs["v4"])
        if hits:
            labels = [k for k in lint_rates.LABELS if t.label and (t.label.get(k) or "").strip() == "1"]
            report.overstatement_llm.append((t.moment_id, hits, ", ".join(labels) or "unlabelled"))
    return report


# foundry-v5.2 team repeat variants: (name, ExplainConfig.slot_team_repeat_exempt, slot_team_repeat_max).
TEAM_REPEAT_VARIANTS = (
    ("foundry-v5.1: everything counts, limit 2", "none", 2),
    ("A: score line and primary clauses do not count, limit 2", "score+primary", 2),
    ("B: score line does not count, limit 2", "score", 2),
    ("C: everything counts, limit 3", "none", 3),
)
# Clauses of a card's primary claims (besides the score), as the prompt suggests them.
PRIMARY_CLAUSES = {"dominance_without_reward": ("dominance",), "pressure_shift": ("pressure", "shots")}


def required_minimum(s: Sample) -> str:
    """One sentence with only what a card needs: its event, the match-state sub-label, the primary clauses and
    the score clause. A rule that rejects it contradicts the primary rule."""
    m, menu = s.moment, s.slot5.menu
    ref = _event_ref(s)
    parts = ["{event:%s}" % ref] if ref else []
    if m.type == "goal" and "score_change" in m.detail:
        parts.append("{clause:%s}" % m.detail["score_change"]["kind"])
    parts += ["{clause:%s}" % c for c in PRIMARY_CLAUSES.get(m.type, ()) if c in menu.clause_by_id]
    parts.append("{clause:score}")
    return ", and ".join(parts) + "."


def draft_space(s: Sample) -> list[str]:
    """One-sentence drafts: the card's event (if any) + 1-4 menu clauses joined with ", and"."""
    ref = _event_ref(s)
    clauses = [c.id for c in s.slot5.menu.clauses]
    out = []
    for k in range(1, 5):
        for combo in itertools.combinations(clauses, k):
            parts = (["{event:%s}" % ref] if ref else []) + ["{clause:%s}" % c for c in combo]
            out.append(", and ".join(parts) + ".")
    return out


def _team_repeat_variants(report: EvalReport, samples: Sequence[Sample], config: ExplainConfig) -> None:
    rows = [RepeatVariant(name, mode, limit) for name, mode, limit in TEAM_REPEAT_VARIANTS]
    off = replace(config, slot_team_repeat_max=0)
    for s in samples:
        if not s.slot5:
            continue
        menu, ctx = s.slot5.menu, s.slot5.ctx
        minimum = required_minimum(s)
        for row in rows:
            variant = replace(config, slot_team_repeat_exempt=row.mode, slot_team_repeat_max=row.limit)
            items, *_ = check_menu_draft(minimum, menu, ctx, variant)
            row.minimum_total += 1
            if any(i.code == "team_repeat" for i in items):
                row.minimum_rejected += 1
                row.minimum_examples.append(f"{s.moment.id} ({s.moment.type}): `{minimum}`")
        for template in draft_space(s):
            items, _, _, claims, ids = check_menu_draft(template, menu, ctx, off)
            if items:
                continue
            placeholders = parse_placeholders(template)[0]
            verdicts = tuple(VerificationResult(True, "ok", c.value) for c in claims)
            text = render(template, claims, ids, verdicts, ctx, menu.clause_templates(s.lang))
            monotone = bool(lint_rates.team_repeats(text, s.roster, 2))
            prose = bool(lint_rates.team_repeats(text, s.roster, 2, exclude_score=True))
            for row in rows:
                sides = team_counts(placeholders, menu, ctx, row.mode)
                row.space_valid += 1
                if any(sides.count(side) > row.limit for side in ("home", "away")):
                    row.space_rejected += 1
                else:
                    row.space_passed += 1
                    row.space_monotone += monotone
                    row.space_prose_monotone += prose
    report.team_repeat_variants = rows


def _primary_v52(report: EvalReport, samples: Sequence[Sample], config: ExplainConfig) -> None:
    """foundry-v5.2 primary claims (dominance: + score; pressure: + shot balance) on clean and archived drafts."""
    base = [s for s in samples if s.slot5]
    fired = sum(any(i.code == "missing_primary_claim" for i in menu_rule_issues(s.slot5.template, s.slot5.menu,
                                                                                s.slot5.ctx, config)) for s in base)
    report.primary_v52_base = (fired, len(base))
    for version in ("foundry-v5", "foundry-v5.1"):
        drafts = lint_rates.menu_drafts(version)
        hits = [(d, i.fragment) for d in drafts for i in menu_rule_issues(d.template, d.menu, d.ctx, config)
                if i.code == "missing_primary_claim"]
        report.primary_v52.append((version, len({id(d) for d, _ in hits}), len(drafts), hits))


def _team_repeat(report: EvalReport, samples: Sequence[Sample], config: ExplainConfig) -> None:
    """Firings of the team repeat rule on clean and accepted texts (every firing is a candidate false alarm)."""
    limit = config.slot_team_repeat_max
    exclude_score = config.slot_team_repeat_exempt == "score"
    menu_texts, menu_hits = [], Counter()
    for s in samples:
        if not s.slot5:
            continue
        d = s.slot5
        verdicts = tuple(VerificationResult(True, "ok", c.value) for c in d.claims)
        text = render(d.template, d.claims, d.claim_ids, verdicts, d.ctx, d.menu.clause_templates(s.lang))
        by_rule = sorted(i.fragment for i in menu_rule_issues(d.template, d.menu, d.ctx, config)
                         if i.code == "team_repeat")
        by_text = sorted(lint_rates.team_repeats(text, s.roster, limit, exclude_score))
        if by_rule != by_text:
            report.team_repeat_disagreements.append(s.moment.id)
        menu_hits.update(by_rule)
        menu_texts += [text] if by_rule else []
    report.team_repeat.append(("v5 menu base (clean)", len(menu_texts), report.slotified_v5, menu_hits, menu_texts))
    datasets = [("Template drafts (fallback text)", [(s.text, s.roster) for s in samples])]
    datasets += [(f"Real LLM, {version} published (all runs)", [(t.raw, t.roster) for t in lint_rates.llm_published(version)])
                 for version in lint_rates.PUBLISHED_RUNS]
    for name, texts in datasets:
        hits: Counter[str] = Counter()
        fired = []
        for text, roster in texts:
            found = lint_rates.team_repeats(text, roster, limit, exclude_score)
            hits.update(found)
            fired += [text] if found else []
        report.team_repeat.append((name, len(fired), len(texts), hits, fired))


# --- report ---------------------------------------------------------------------------------


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def render_table(report: EvalReport) -> str:
    head = " | ".join(f"{NAMES[v]} N | {NAMES[v]} caught" for v in VARIANTS)
    lines = [
        f"| Type | Injection | {head} |",
        "|---|---|" + "---:|---:|" * len(VARIANTS),
    ]
    for r in report.results:
        cells = []
        for variant in VARIANTS:
            st = getattr(r, variant)
            cells += [str(st.applicable or "—"), _pct(st.rate)]
        name = f"`{r.spec.name}`" + (f" (new, {r.spec.new})" if r.spec.new else "")
        lines.append(f"| {name} | {r.spec.description} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def uncaught(report: EvalReport, variant: str) -> list[TypeResult]:
    return [
        r for r in report.results
        if r.spec.name != "control" and getattr(r, variant).applicable
        and getattr(r, variant).caught < getattr(r, variant).applicable
    ]


def _tags(counter: Counter[str]) -> str:
    return ", ".join(f"`{t}`×{n}" for t, n in sorted(counter.items(), key=lambda x: (-x[1], x[0])))


def _rate_cell(flagged: int, total: int) -> str:
    return f"{flagged}/{total} ({flagged / total * 100:.1f}%)" if total else "—"


RULE_NAMES = {
    "sentence_start": "Sentence start (allowed list)",
    "number_words": "Number words (context-free)",
    "overstatement": "Qualitative overstatement",
    "bare_surname": "Surname only (text_lint)",
    "event_word": "Event word (policy)",
    "event_type": "{event:} event type allow-list (v4.1)",
    "player_repeat": "Player repeat (v4.1)",
    "article_team": "\"the\" before a team name (v4.1)",
}


def render_rule_rates(report: EvalReport) -> list[str]:
    datasets = list(dict.fromkeys(r.dataset for r in report.rule_rates))
    out = [
        "| Rule | " + " | ".join(datasets) + " |",
        "|---|" + "---:|" * len(datasets),
    ]
    by_key = {(r.dataset, r.rule): r for r in report.rule_rates}
    for rule in lint_rates.RULES:
        cells = []
        for ds in datasets:
            r = by_key.get((ds, rule))
            cells.append(_rate_cell(r.flagged, r.total) if r else "—")
        out.append(f"| {RULE_NAMES[rule]} | " + " | ".join(cells) + " |")
    out += ["", "Fragments fired (count per draft):", ""]
    for r in report.rule_rates:
        if r.examples:
            out.append(f"- {RULE_NAMES[r.rule]} · {r.dataset}: {_tags(r.examples)}")
    return out


def render_v41_false_alarms(report: EvalReport) -> list[str]:
    out = [
        "### False alarms from the foundry-v4.1 changes",
        "",
        "Rejections v4.1 adds on clean datasets (new rules + \"They\" removed from the allowed "
        "list; drafts already rejected by the v4 rules are not counted):",
        "",
        "| Dataset | False alarm | Fragments |",
        "|---|---:|---|",
    ]
    for name, flagged, total, hits in report.v41_false_alarms:
        out.append(f"| {name} | {_rate_cell(flagged, total)} | {_tags(hits) or '—'} |")
    out += [
        "",
        "The \"They\" firing in template drafts comes from the template narrator's \"They had been … down\" "
        "sentence; the fallback text goes through text_lint, not the v4.1 slot lint, so publishing is not affected. "
        "foundry-v2/v3 outputs had no sentence starting with \"They\"; sentences starting with \"They …\" in the "
        "templates foundry-v4 accepted (the foundry-v4 column in the table above) are now rejected. They may be "
        "factually correct (v4 outputs were not human-labelled), so this is a deliberate cost of the pronoun rule: "
        "the text does not show which team the pronoun refers to, and the model is steered to write {home}/{away}.",
    ]
    return out


def render_v5_sentence_starts(report: EvalReport) -> list[str]:
    out = [
        "### Effect of the foundry-v5 allowed sentence-start change",
        "",
        "\"At\" (moves the minute to the sentence start: \"At 29' … since kickoff\") and \"Possession\" (a metric name; "
        "comes via `{label:}`/`{clause:}`) left the list; the EN list is now only \"The\". Drafts newly "
        "rejected by this change (drafts already rejected with the v4.1 list are not counted):",
        "",
        "| Dataset | New rejections | Fragments |",
        "|---|---:|---|",
    ]
    for name, flagged, total, hits in report.v5_false_alarms:
        out.append(f"| {name} | {_rate_cell(flagged, total)} | {_tags(hits) or '—'} |")
    out += [
        "",
        "No firings on the clean sets (template, slot bases). The firings in the real LLM rows are sentences that "
        "may be factually correct (\"Possession since kickoff: …\", \"At 29' …\"); they are a deliberate cost "
        "of the rule, and in v5 the same information comes via `{clause:possession}`.",
    ]
    return out


def render_team_repeat(report: EvalReport) -> list[str]:
    out = [
        f"### False alarms of the {PROMPT_VERSION} team repeat rule",
        "",
        "`team_repeat` rejects a menu draft that names the same team more than "
        f"{V5_CONFIG.slot_team_repeat_max} times in one sentence (team names inside clauses count; since "
        "foundry-v5.2 the score line, `{score_named}` / `{clause:score}`, does not). "
        "Clean and already accepted texts below; every firing is a candidate false alarm "
        "(the text is correct, the rule only judges readability). Measured on the final text (team names of the "
        "squad, per sentence); on the clean menu drafts the template rule and the count on the rendered text "
        + ("agree on every draft." if not report.team_repeat_disagreements else
           f"disagree on {len(report.team_repeat_disagreements)} drafts: "
           + ", ".join(f"`{m}`" for m in report.team_repeat_disagreements) + "."),
        "",
        "| Dataset | Fired | Sides |",
        "|---|---:|---|",
    ]
    for name, flagged, total, hits, _ in report.team_repeat:
        out.append(f"| {name} | {_rate_cell(flagged, total)} | {_tags(hits) or '—'} |")
    fired = [(name, text) for name, _, _, _, texts in report.team_repeat for text in dict.fromkeys(texts)]
    if fired:
        out += ["", "Texts it fires on (distinct):", ""]
        out += [f"- {name}: \"{text}\"" for name, text in fired]
    return out


def render_team_repeat_variants(report: EvalReport) -> list[str]:
    out = [
        "### foundry-v5.2: which team names the team repeat rule counts",
        "",
        "In the foundry-v5.1 live run the score disappeared from all dominance cards; the prompt line \"count the "
        "team names inside clauses and {score_named}\" made the score the cheapest thing to drop. Variants measured "
        "on the 248 corpus moments (deterministic, no model):",
        "",
        "- *Required minimum*: one sentence with only what the card needs: its event, the match-state sub-label, "
        "the primary clauses and the score (`{clause:pressure}, and {clause:shots}, and {clause:score}.`, "
        "`{clause:dominance}, and {clause:score}.`, `{event:<goal>}, and {clause:go_ahead}, and {clause:score}.`). "
        "A rejection is a certain false alarm: the rule contradicts the primary rule.",
        "- *Draft space*: the card's event + 1–4 menu clauses joined with \", and\" (one sentence), kept only if it "
        "passes every other menu rule. *Repeats* = passed drafts whose rendered sentence names a team 3+ times "
        "(as the reader sees it, score line included); *in prose* = 3+ times outside the score line.",
        "",
        "| Variant | Required minimum rejected (false alarm) | Draft space rejected | Passed with repeats | "
        "Passed with repeats in prose |",
        "|---|---:|---:|---:|---:|",
    ]
    for v in report.team_repeat_variants:
        chosen = (v.mode, v.limit) == (V5_CONFIG.slot_team_repeat_exempt, V5_CONFIG.slot_team_repeat_max)
        name = f"**{v.name}** (chosen)" if chosen else v.name
        out.append(f"| {name} | {_rate_cell(v.minimum_rejected, v.minimum_total)} | "
                   f"{_rate_cell(v.space_rejected, v.space_valid)} | {_rate_cell(v.space_monotone, v.space_passed)} | "
                   f"{_rate_cell(v.space_prose_monotone, v.space_passed)} |")
    examples = sorted({e.split(": ", 1)[1] for v in report.team_repeat_variants for e in v.minimum_examples})
    if examples:
        out += ["", "Required minimums the rule rejects: " + "; ".join(examples) + "."]
    out += [
        "",
        "Choice: **B**. foundry-v5.1 rejects the required minimum of every pressure card that adds the score "
        "(the pressure clause, the shot clause and the score line each name the leading team). A and B never "
        "reject the required minimum and are equal on the whole draft space: every primary clause names its team "
        "once, and the drafts where A's extra exemption would matter already fail another rule (two clauses that "
        "write the same window start → `minute_repeat`). B is the narrower rule (A would also let a hand-written "
        "`{home}`/`{away}` pass next to two primary clauses), and its prompt line is one fact the model can apply "
        "(\"the score does not count\"); A's needs the model to know which clauses are primary. C (count everything, "
        "limit 3) also never rejects the minimum but lets the prose itself name a team three times "
        "(`{event}, and {clause:goal}, and {clause:team_goals}, and {clause:possession}`). The cost of B: the score "
        "line may add a third name to a sentence (\"Passed with repeats\"); the prompt line tells the model to drop an "
        "extra clause or start a new sentence instead of dropping the score.",
    ]
    return out


def render_primary_v52(report: EvalReport) -> list[str]:
    fired, total = report.primary_v52_base
    out = [
        "### foundry-v5.2: new primary claims (dominance: the score; pressure: the window's shot balance)",
        "",
        "`missing_primary_claim` now also fires when a dominance_without_reward card lacks the score "
        "(`{clause:score}`, `{score}` or `{score_named}`) or a pressure_shift card lacks the shot balance "
        f"(`{{clause:shots}}`). Clean v5 menu base: {_rate_cell(fired, total)} fired (false alarms). "
        "Archived published templates, replayed against today's menu (a firing = a published text that would now "
        "be rejected; a false alarm only if the text states the claim another way, e.g. the margin clause instead "
        "of the score):",
        "",
        "| Version (all runs) | Fired | False alarm | Firings |",
        "|---|---:|---:|---|",
    ]
    for version, n, total, hits in report.primary_v52:
        false = [d for d, frag in hits if "score" in frag and "{clause:margin}" in d.template]
        firings = "<br>".join(f"run {d.run} {d.moment.id.rsplit('-', 1)[-1]} {d.moment.type} (`{frag}`): "
                              f"\"{d.text}\"" for d, frag in hits) or "—"
        out.append(f"| {version} | {_rate_cell(n, total)} | {len(false)} | {firings} |")
    return out


def render_human_review() -> list[str]:
    counts = lint_rates.human_review_counts()
    out = ["## Human labels: foundry-v3 (raw counts)", ""]
    if counts is None:
        return [*out, "Label file not found.", ""]
    sources = sorted(counts["texts"])
    out += [
        f"Source: `docs/human_review.foundry-v3.csv` ({counts['total']} texts; "
        f"{', '.join(f'{s}: {counts['texts'][s]}' for s in sources)}), source info "
        "from `docs/LLM_RUN.foundry-v3.json`. A text can have more than one label (e.g. correct + dull).",
        "",
        "| Label | Total | " + " | ".join(sources) + " | Moments |",
        "|---|---:|" + "---:|" * len(sources) + "---|",
    ]
    for label in lint_rates.LABELS:
        per = [counts["by_source"].get(s, Counter())[label] for s in sources]
        ids = ", ".join(i.replace("m-", "").replace("-M", " M") for i in counts["ids"][label]) or "—"
        out.append(f"| `{label}` | {sum(per)} | " + " | ".join(map(str, per)) + f" | {ids if label != 'correct' else '…'} |")
    return [*out, ""]


def render_window_audit(corpus: Sequence[tuple[int, str | None]]) -> list[str]:
    audit = lint_rates.window_audit(corpus)
    out = [
        "## Template window audit (template narrator)",
        "",
        "Each claim's window, and whether windowed claims (start neither kickoff nor the event moment) state "
        "the window in the sentence (EN \"since X'\").",
        "",
        "| Moment type | Metric | Kind | Window | Claims | Window in text |",
        "|---|---|---|---|---:|---:|",
    ]
    for (mtype, metric, kind, window), (n, stated) in sorted(audit["rows"].items()):
        cell = f"{stated}/{n}" if window.startswith(("window", "rolling")) else "—"
        out.append(f"| {mtype} | {metric} | {kind} | {window} | {n} | {cell} |")
    pc, pt = audit["pressure"]
    dc, dt = audit["dominance"]
    out += [
        "",
        "Findings:",
        "",
        "- `dominance_without_reward`: the possession and shot claims already share one window "
        "(`dominance_context_minutes`); the bug was in the EN sentence (\"58% of possession and 4–0 shots since 25'\" "
        "tied the window to the shots only). Fix: the window is written before both values "
        "(\"since 25' they have had 58% of the ball and a 4–0 lead in shots\").",
        "- `pressure_shift`: the `pressure_balance` claim carries `start = kickoff`, but `measure` ignores the start; "
        "the metric is a rolling window over the last 10 minutes played. foundry-v4.1: the readable metric name states "
        f"the window (\"{metric_label('pressure_balance', 'en')}\"; "
        "`app/explain/labels.py`, window from `AnalyticsConfig.pressure_window_min`). This fixed phrase is not a claim: "
        "text_lint masks it before the number check; no window support was added to the verifier. The shot count "
        "comes from the `_since` window on the match clock and is clipped at the start of a half; "
        f"in {pc}/{pt} pressure moments the shot window is shorter than {DEFAULT_EXPLAIN_CONFIG.context_minutes} minutes"
        + (f" (e.g. `{audit['clamp_example'][0]}`: \"{audit['clamp_example'][1]}\", window "
           f"{audit['clamp_example'][2]} s)" if audit["clamp_example"] else "")
        + ". The two values then come from different windows (minutes played ↔ match clock); the shot window is "
        "stated in the text, so the reader can tell them apart.",
        f"- `dominance_without_reward`: in {dc}/{dt} moments the window is clipped at the start of a half (the detector "
        "looks back 20 minutes of play; the narration uses the match clock). The text states the clipped window's start, so "
        "it is not misleading, but it does not match the detector's value (moment.detail) exactly.",
        "- `goal`, `red_card`, `penalty`: claims are at the event or kickoff → now; no separate window.",
        "",
    ]
    return out


def render_overstatement_list() -> list[str]:
    out = [
        "## Qualitative overstatement ban list (v4 lint)",
        "",
        "Fixed list (`app/explain/phrases.py` `OVERSTATEMENT`). A phrase matched in the text outside placeholders is "
        "rejected unless the moment type supports it (`overstatement`). Supporting types are only the moment's own evidence: "
        "\"dominate\" in a `dominance_without_reward` moment and \"take control\" in a `pressure_shift` moment are "
        "supported by the detector's threshold. The list was written from the \"deep into stoppage\" finding in the foundry-v3 "
        "human labels and a general football hype lexicon; the overstatement sentences in the injections were written separately (see the misses).",
        "",
        "| Language | Phrase (regex, `…` = continuation) | Supporting moment type |",
        "|---|---|---|",
    ]
    for lang, readable, supported in lint_rates.overstatement_table():
        out.append(f"| {lang} | `{readable}` | {supported} |")
    return [*out, ""]


def render_markdown(report: EvalReport) -> str:
    control = next(r for r in report.results if r.spec.name == "control")
    corpus = ", ".join(f"{sc or 'no scenario'}/{seed}" for seed, sc in report.corpus)
    allowed_en = ", ".join(f"`{w}`" for w in DEFAULT_EXPLAIN_CONFIG.sentence_start_allowed_en)
    out = [
        "# Injection evaluation: foundry-v2 ↔ foundry-v3 ↔ foundry-v4 ↔ foundry-v4.1 ↔ foundry-v5",
        "",
        "This file is generated by `python -m eval.inject`; do not edit it by hand.",
        "",
        "## Method",
        "",
        "- Start: the template narrator's correct drafts (text + claims), all moments, EN.",
        f"- Corpus: {len(report.corpus)} matches, {report.samples} drafts. Matches: {corpus}.",
        "- **v2 (free text)**: the model writes text and claims freely; checked by text_lint + verify_claim "
        "(v2 rules: surname-only check off).",
        "- **v3 (slot)**: the model writes no concrete values; it writes a placeholder template + claims, and code "
        "renders the values from the verified claims. Check: template lint (digits/number words/names/"
        "home-away/raw metric names banned outside placeholders) + placeholder binding + verify_claim (v3 rules).",
        "- **v4 (slot + {event:} + strict lint)**: event info only comes via `{event:<id>}` (code builds the event's "
        "standard phrase from the data; the event must be evidence of a claim), metric names via `{label:}`; "
        "`{score}` is \"1–0\" without team names, `{score_named}` with them. Lint also rejects event type / role words, "
        "sentence starts not on the allowed list, number words regardless of context and qualitative "
        "overstatement the moment type does not support.",
        "- **v4.1**: the v4 base with extra rules: `{event:}` only for event types the moment type allows "
        "(passes, dribbles, offsides, fouls, corners and saves cannot be selected), `{event:X}` and X's player's "
        "`{player:}` cannot appear in the same sentence, no \"the\" before a team placeholder, \"They\" left "
        "the allowed sentence-start list (pronouns never enter the list).",
        "- **v5 (claim menu)**: code builds and verifies the claims (`app/explain/menu.py`); the model links no claims "
        "or events and only uses menu ids (`{value:}`, `{minute:}`, `{start:}`, `{label:}`, `{clause:}`, `{event:}` "
        "for menu evidence, `{score}`). Extra rules: an id not on the menu, a sentence not grounded in a menu claim, "
        "a dominance/pressure moment without its primary claim, and the same minute twice in one sentence "
        "are rejected; the only allowed EN sentence start is \"The\". The model writes no claims, so injections "
        "that change a claim (`number_text_and_claim`) are \"—\" in v5.",
        f"- Bases: v3 `slotify` {report.slotified}/{report.samples}, v4 `slotify_v4` "
        f"{report.slotified_v4}/{report.samples}, v5 `slotify_v5` {report.slotified_v5}/{report.samples} drafts "
        "converted cleanly (the v4 base passes both the v4 and v4.1 rules); the columns are measured on these.",
        "- Each error type is injected in each approach's own form, with the same meaning (seeded by moment + type + "
        "language + version). A draft the injection cannot apply to is not in N; \"—\" is a type with no counterpart in that approach. "
        "Types marked \"(new, v4)\" / \"(new, v4.1)\" were added in that version.",
        "- **Caught** = the check returned at least one error; the pipeline does not publish the draft in that case.",
        "",
        "## Results",
        "",
        render_table(report),
        "",
        "False alarms (control): " + ", ".join(
            f"{NAMES[v]} {getattr(control, v).caught}/{getattr(control, v).applicable}" for v in VARIANTS) + ".",
        "",
        f"Note: v2's `number_words` catch rate with the number-word check off is "
        f"{_pct(report.v2_number_words_without_fix)}.",
        "",
        "Note (v5): `unsupported_sentence_qualitative` and `qualitative_overstatement` are added to the draft as a *separate sentence*; "
        "v5 catches them with `sentence_without_claim` (the sentence has no menu claim). If the same judgement is written "
        "inside a sentence grounded in a menu claim (\"{clause:possession}, and {home} were the better side\"), "
        "v5 lets it through too: the qualitative judgement itself is still not checked.",
        "",
    ]
    out += [
        "## Target for the Verifier agent",
        "",
        "Error types the deterministic check (lint + placeholder binding + verify_claim) misses, per "
        "version. These are gaps a rule list cannot close; they require looking at the meaning of the sentence. This is "
        f"the list a Verifier agent should target. The current version ({PROMPT_VERSION}) comes first.",
        "",
    ]
    for variant in reversed(VARIANTS):
        out += [f"### Uncaught types: {TITLES[variant]}", ""]
        misses = uncaught(report, variant)
        if not misses:
            out += ["None: every type 100% caught.", ""]
        for r in misses:
            stats = getattr(r, variant)
            out += [
                f"#### `{r.spec.name}`: {_pct(stats.rate)} caught "
                f"({stats.applicable - stats.caught}/{stats.applicable} missed)",
                "",
                f"**Why:** {r.spec.miss(variant)}",
                "",
            ]
            if stats.missed_tags:
                out += [f"Missed phrases / names: {_tags(stats.missed_tags)}", ""]
            if stats.missed_example:
                original, injected = stats.missed_example
                out += ["Example:", "", f"- Original: `{original}`", f"- Injected: `{injected}`", ""]
    out += ["## Phrases applied in the new types (all versions)", ""]
    for r in report.results:
        if r.spec.new:
            for variant in VARIANTS:
                st = getattr(r, variant)
                if st.tags:
                    caught = st.tags - st.missed_tags
                    out.append(f"- `{r.spec.name}` {NAMES[variant]}: caught {_tags(caught) or '—'}; "
                               f"missed {_tags(st.missed_tags) or '—'}")
    allowed_from, flagged, sentences, examples = report.held_out
    out += [
        "",
        "## v4 / v4.1 lint rules and false alarms",
        "",
        "Per rule, the share of drafts on which the rule fires (with the v4.1 rules; the sentence-start row with the v4.1 "
        "allowed list). On clean drafts (template, v3 slot, v4 slot base) every firing is a false alarm. "
        "Real LLM outputs: foundry-v2's published free texts and foundry-v3's accepted "
        "templates (EN, names and numbers count as placeholders); they contain no number words and no made-up names, so "
        "sentence-start and number-word firings are false alarms. The foundry-v4 column is the templates v4 "
        "accepted: the v4.1 rules were written from findings in these outputs (\"They …\", \"The {home}\", "
        "\"… by {player:}\", a pass event), so firings in this column are intended catches. Whether an "
        "overstatement firing is right is compared with the human label (below). The \"Event word\" "
        "row is not a false alarm but policy: in v4, event and metric names cannot be written freely.",
        "",
        *render_rule_rates(report),
        "",
        *render_v41_false_alarms(report),
        "",
        *render_v5_sentence_starts(report),
        "",
        *render_team_repeat(report),
        "",
        *render_team_repeat_variants(report),
        "",
        *render_primary_v52(report),
        "",
        "In the template and v3 rows, the sentence-start firings come from the template narrator's own "
        "patterns (EN \"Shots since …\"). This word was deliberately left off "
        "the list: \"Shots\" is an event word (in v4 the metric name comes via `{label:}`). The template "
        "fallback goes through text_lint, not the v4 slot lint, so this does not affect published fallback texts.",
        "",
        "Texts where the overstatement rule fires on real LLM outputs, with the human label: "
        + ("; ".join(f"`{mid}` ({', '.join(h)}) → {label}" for mid, h, label in report.overstatement_llm) or "none")
        + ".",
        "",
        "### Allowed sentence-start list",
        "",
        f"The list was derived from clean drafts (`eval/lint_rates.py` `derive_frozen`): the template narrator's "
        f"{report.samples} drafts + real LLM outputs ({report.llm_texts} texts; for foundry-v3 only those with the human "
        "label `correct`). The first word of each sentence that does not start with a placeholder is taken; home/away, pronouns "
        "(foundry-v4.1: \"They\" removed), number words, event words and overstatement phrases never enter the list. The result is frozen in `config.py`: "
        f"EN {allowed_en}.",
        "",
        "The list contains the data it is measured on, so the rate above is optimistic. Held-out estimate: if the list "
        f"came only from template drafts (EN {', '.join(allowed_from['en']) or '—'}), {flagged} of {sentences} sentences in real LLM outputs "
        f"({_pct(flagged / sentences if sentences else None)}) would be rejected: {_tags(examples) or '—'}.",
        "",
        *render_overstatement_list(),
        *render_window_audit(report.corpus),
        *render_human_review(),
        "## Regenerate",
        "",
        "```",
        ".venv/bin/python -m eval.inject",
        "```",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Injection evaluation (v2 ↔ v3 ↔ v4 ↔ v4.1)")
    parser.add_argument("--quick", action="store_true", help="Small corpus")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)

    report = run_eval(QUICK_CORPUS if args.quick else FULL_CORPUS)
    print(render_table(report))
    print(f"\nslotify: v3 {report.slotified}/{report.samples}, v4 {report.slotified_v4}/{report.samples}, "
          f"v5 {report.slotified_v5}/{report.samples}")
    for variant in VARIANTS:
        print(f"Uncaught ({NAMES[variant]}): " + (", ".join(r.spec.name for r in uncaught(report, variant)) or "none"))
    if not args.no_write:
        Path(args.out).write_text(render_markdown(report), encoding="utf-8")
        print(f"Written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
