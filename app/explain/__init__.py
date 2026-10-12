"""Explain aşaması: moment seçimi, iddia doğrulama, template anlatı (LLM yok)."""

from .claims import (
    Claim,
    MatchTime,
    Subject,
    VerificationResult,
    event_ref,
    measure,
    parse_ref,
    verify_claim,
)
from .config import DEFAULT_EXPLAIN_CONFIG, ExplainConfig
from .selector import select_moments
from .template_narrator import Narration, Sentence, build_narration, narrate

__all__ = [
    "DEFAULT_EXPLAIN_CONFIG",
    "Claim",
    "ExplainConfig",
    "MatchTime",
    "Narration",
    "Sentence",
    "Subject",
    "VerificationResult",
    "build_narration",
    "event_ref",
    "measure",
    "narrate",
    "parse_ref",
    "select_moments",
    "verify_claim",
]
