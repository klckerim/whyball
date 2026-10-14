"""WhyBall API and the built web UI from one process (one container).

    .venv/bin/uvicorn app.api.main:app --reload

WHYBALL_DATA_DIR (default: data/) holds demo/ and demo_narration/; WHYBALL_STATIC_DIR
(default: web/dist) is the Vite build, served at /.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.analytics.config import DEFAULT_CONFIG
from app.explain.claims import COMPARISONS, KINDS, METRIC_KINDS
from app.explain.labels import METRIC_DEFINITIONS, METRIC_LABELS
from app.publish.schema import SOURCES, EvidenceEvent, Score, StoredClaim, StoredMoment, Teams

from .data import TIMELINE_TYPES, Match, load_matches
from .replay import event_out, moment_out, replay

REPO_ROOT = Path(__file__).resolve().parents[2]
HTTP_TIMEOUT_S = 60.0
MAX_SPEED = 3600.0


class MatchSummary(BaseModel):
    id: str
    teams: Teams
    final_score: Score
    moments: int
    sources: dict[str, int]


class TimelineEvent(BaseModel):
    seq: int
    t: int
    period: int
    minute: int
    second: int
    minute_label: str
    type: str
    team: str | None
    player: str | None
    outcome: str | None
    score: Score
    x: float | None  # ball position (0..105, 0..68); null for cards, substitutions, whistles
    y: float | None


class Period(BaseModel):
    period: int
    start_t: int
    end_t: int


class Squad(BaseModel):
    name: str
    lineup: list[str]
    bench: list[str]


class Squads(BaseModel):
    home: Squad
    away: Squad


class MatchDetail(BaseModel):
    id: str
    event_match_id: str
    teams: Teams
    final_score: Score
    duration_t: int
    periods: list[Period]
    timeline: list[TimelineEvent]
    run_id: str
    prompt_version: str
    squads: Squads  # from the match_meta record


class MetricWindow(BaseModel):
    type: Literal["rolling", "claim_range"]  # rolling: the last `minutes` played before the claim end
    minutes: float | None = None


class MetricInfo(BaseModel):
    id: str
    kind: str
    label: str
    definition: str
    window: MetricWindow


class MetricsOut(BaseModel):
    metrics: list[MetricInfo]
    kinds: list[str]
    comparisons: list[str]


class Health(BaseModel):
    ok: bool
    matches: int


class EvidenceOut(EvidenceEvent):
    x: float | None = None  # pitch position from the event stream (0..105, 0..68)
    y: float | None = None


class ClaimOut(StoredClaim):
    evidence: list[EvidenceOut]


class MomentOut(StoredMoment):
    t: int
    claims: list[ClaimOut]


def _summary(m: Match) -> MatchSummary:
    s = m.store
    return MatchSummary(
        id=s.match_id, teams=s.teams, final_score=s.final_score, moments=len(s.moments),
        sources={src: sum(c.source == src for c in s.moments) for src in SOURCES},
    )


def _metric_window(metric: str) -> MetricWindow:
    if metric == "pressure_balance":
        return MetricWindow(type="rolling", minutes=DEFAULT_CONFIG.pressure_window_min)
    return MetricWindow(type="claim_range")


METRICS = MetricsOut(
    metrics=[
        MetricInfo(id=m, kind=kind, label=METRIC_LABELS["en"][m], definition=METRIC_DEFINITIONS[m],
                   window=_metric_window(m))
        for m, kind in METRIC_KINDS.items()
    ],
    kinds=list(KINDS), comparisons=list(COMPARISONS),
)


def create_app(data_dir: Path | None = None, static_dir: Path | None = None) -> FastAPI:
    data_dir = data_dir or Path(os.environ.get("WHYBALL_DATA_DIR", REPO_ROOT / "data"))
    static_dir = static_dir or Path(os.environ.get("WHYBALL_STATIC_DIR", REPO_ROOT / "web" / "dist"))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.matches = load_matches(data_dir)
        # One HTTP client for the app's lifetime, for the live narrator; nothing calls a model yet.
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
            app.state.http = client
            yield

    app = FastAPI(title="WhyBall", lifespan=lifespan)

    def get_match(request: Request, match_id: str) -> Match:
        match = request.app.state.matches.get(match_id)
        if match is None:
            raise HTTPException(404, f"unknown match: {match_id}")
        return match

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/healthz", response_model=Health)
    def healthz(request: Request) -> Health:
        return Health(ok=True, matches=len(request.app.state.matches))

    @app.get("/api/metrics", response_model=MetricsOut)
    def metrics() -> MetricsOut:
        return METRICS

    @app.get("/api/matches", response_model=list[MatchSummary])
    def matches(request: Request) -> list[MatchSummary]:
        return [_summary(m) for m in request.app.state.matches.values()]

    @app.get("/api/matches/{match_id}", response_model=MatchDetail)
    def match_detail(request: Request, match_id: str) -> MatchDetail:
        m = get_match(request, match_id)
        s = m.store
        return MatchDetail(
            id=s.match_id, event_match_id=s.event_match_id, teams=s.teams, final_score=s.final_score,
            duration_t=m.duration_t, periods=m.periods(),
            timeline=[event_out(e, m.t[e.seq]) for e in m.events if e.type in TIMELINE_TYPES],
            run_id=s.run_id, prompt_version=s.prompt_version,
            squads=Squads(**{side: Squad(**m.meta["teams"][side]) for side in ("home", "away")}),
        )

    @app.get("/api/matches/{match_id}/moments", response_model=list[MomentOut])
    def moments(request: Request, match_id: str) -> list[dict]:
        m = get_match(request, match_id)
        return [moment_out(m, i) for i in range(len(m.store.moments))]

    @app.get("/api/matches/{match_id}/replay")
    def match_replay(
        request: Request,
        match_id: str,
        speed: float = Query(60.0, ge=0, le=MAX_SPEED, description="match seconds per second; 0 = no wait"),
        from_t: int = Query(0, ge=0, description="start at this many seconds since kickoff"),
    ) -> StreamingResponse:
        m = get_match(request, match_id)
        return StreamingResponse(
            replay(m, speed, from_t), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    if (static_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")
    else:
        @app.get("/", include_in_schema=False)
        def ui_not_built() -> PlainTextResponse:
            return PlainTextResponse("UI not built: cd web && npm ci && npm run build", status_code=503)

    return app


app = create_app()
