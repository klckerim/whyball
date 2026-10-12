"""JSON girdi / JSON çıktı araç arayüzü (ileride MCP sunucusu bunları sarmalayacak).

Her araç bir dict alır, bir dict döner ve hata fırlatmaz:
  başarı: {"ok": true, "result": {...}}
  hata:   {"ok": false, "error": {"code": ..., "message": ...}}

Maç bağlamı "events" (olay dict listesi) ya da "match_path" (yalnızca repo
data/ altı) ile verilir.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

from app.analytics import metrics_at
from app.generator.models import Event, read_jsonl

from .claims import COMPARISONS, KINDS, METRIC_KINDS, Claim, MatchTime, Subject, measure, verify_claim
from .text_lint import Roster, lint_text

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"

Payload = dict[str, Any]


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _tool(fn: Callable[[Payload], Payload]) -> Callable[[Payload], Payload]:
    @wraps(fn)
    def wrapper(payload: Payload) -> Payload:
        try:
            return {"ok": True, "result": fn(payload)}
        except ToolError as e:
            return {"ok": False, "error": {"code": e.code, "message": e.message}}
        except (KeyError, TypeError, ValueError) as e:
            return {"ok": False, "error": {"code": "invalid_input", "message": repr(e)}}

    return wrapper


def _events(payload: Payload) -> list[Event]:
    if "events" in payload:
        return [Event.from_dict(d) for d in payload["events"]]
    if "match_path" in payload:
        path = Path(payload["match_path"])
        path = (path if path.is_absolute() else REPO_ROOT / path).resolve()
        if not path.is_relative_to(DATA_DIR.resolve()):
            raise ToolError("forbidden_path", "match_path data/ altında olmalı")
        if not path.is_file():
            raise ToolError("not_found", f"{payload['match_path']} bulunamadı")
        return read_jsonl(path)
    raise ToolError("missing_match", "'events' ya da 'match_path' gerekli")


@_tool
def verify_claim_tool(payload: Payload) -> Payload:
    r = verify_claim(Claim.from_dict(payload["claim"]), _events(payload))
    return {"ok": r.ok, "reason": r.reason, "actual": r.actual}


@_tool
def measure_tool(payload: Payload) -> Payload:
    metric = payload["metric"]
    kind = METRIC_KINDS.get(metric)
    if kind is None:
        raise ToolError("unknown_metric", f"Bilinmeyen metrik: {metric!r}")
    subject = Subject(**payload.get("subject", {}))
    if kind != "count" and subject.team not in ("home", "away"):
        raise ToolError("invalid_subject", f"{metric} için subject.team gerekli")
    events = _events(payload)
    m = measure(metric, subject, MatchTime(*payload["start"]), MatchTime(*payload["end"]), events)
    match_id = events[0].match_id
    return {"metric": metric, "kind": kind, "value": m.value,
            "counted_event_ids": [f"{match_id}#{s}" for s in m.counted]}


@_tool
def metrics_at_tool(payload: Payload) -> Payload:
    snap = metrics_at(
        _events(payload),
        until_seq=payload.get("until_seq"),
        until_minute=payload.get("until_minute"),
    )
    return {"seq": snap.seq, "period": snap.period, "minute": snap.minute,
            "second": snap.second, **snap.summary()}


@_tool
def lint_text_tool(payload: Payload) -> Payload:
    events = _events(payload)
    claims = [Claim.from_dict(c) for c in payload.get("claims", [])]
    return lint_text(
        payload["text"], claims, Roster.from_events(events), language=payload.get("language")
    ).to_dict()


@_tool
def list_metrics_tool(payload: Payload) -> Payload:
    return {"metrics": dict(METRIC_KINDS), "kinds": list(KINDS), "comparisons": list(COMPARISONS)}


TOOLS: dict[str, Callable[[Payload], Payload]] = {
    "verify_claim": verify_claim_tool,
    "measure": measure_tool,
    "metrics_at": metrics_at_tool,
    "lint_text": lint_text_tool,
    "list_metrics": list_metrics_tool,
}
