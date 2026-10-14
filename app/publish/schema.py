"""Publication store schema: data/demo_narration/{match_id}.json.

One file per demo match; every card is a published narration that passed text_lint and
verify_claim with the current code. The API serves these models as they are.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Source = Literal["llm", "template", "template_fallback"]
SOURCES: tuple[str, ...] = ("llm", "template", "template_fallback")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceEvent(_Model):
    id: str  # "m-42-red_card_swing#127"
    seq: int
    type: str
    team: str | None
    player: str | None
    period: int
    minute: int
    second: int
    minute_label: str  # "45+2'"


class StoredClaim(_Model):
    id: str  # menu id (llm) or metric + side (template)
    kind: str
    metric: str
    label: str
    team: str | None
    player: str | None
    comparison: str
    value: float
    display: str  # the value as the text states it ("59%", "+0.83", "2")
    start: str  # minute label of the inclusive start
    end: str
    evidence: list[EvidenceEvent]


class StoredChecks(_Model):
    """What the publish pipeline checked for this card (`run_moment` result at publish time)."""

    lint_issues: int  # text_lint issues in the published text
    claims_total: int  # claims the verifier checked
    claims_verified: int  # of those, the ones verify_claim accepted


class Segment(_Model):
    """A piece of the card text. `claim_id` is set only on a piece that states a claim's value."""

    text: str
    claim_id: str | None = None


class StoredMoment(_Model):
    id: str
    period: int
    minute: int
    second: int
    minute_label: str
    at_seq: int
    type: str
    team: str | None
    importance: float
    text: str
    segments: list[Segment]  # the text in pieces: joined, they equal `text`
    source: Source
    prompt_version: str  # of the narrator that wrote the published text
    run_id: str | None  # the LLM run the card was replayed from (None for template cards)
    claims: list[StoredClaim]
    trace: list[dict[str, Any]]  # agent trace; empty in the replayed store
    checks: StoredChecks


class Teams(_Model):
    home: str
    away: str


class Score(_Model):
    home: int
    away: int


class MatchStore(_Model):
    match_id: str  # fixture name, e.g. "red_card_swing_seed42"
    event_match_id: str  # match id in the event stream, e.g. "m-42-red_card_swing"
    events_file: str  # repo-relative path of the event stream
    events_sha256: str
    teams: Teams
    final_score: Score
    run_id: str
    prompt_version: str
    moments: list[StoredMoment]
