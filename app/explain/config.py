"""Explain stage thresholds. The selector, verifier and narrator read their numbers from here."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExplainConfig:
    # --- selector ---
    min_importance: float = 0.5
    window_minutes: int = 10
    max_per_window: int = 3  # for moments outside always_keep
    always_keep: tuple[str, ...] = ("goal", "red_card")

    # --- verifier ---
    approx_tolerance: float = 0.005  # values rounded to 2 decimals / a whole percent in the text
    float_epsilon: float = 1e-9  # floating-point error at the tolerance edge (0.88 - 0.875)

    # --- narrator ---
    context_minutes: int = 10  # the "since X'" range in the pressure shift sentence
    # dominance: the detector's own window (AnalyticsConfig.dominance_window_min), see _Context.detector_window
    full_squad: int = 11  # for players_on_pitch when meta has no squad

    # --- narration pipeline ---
    max_retries: int = 2  # after the first attempt; then the template fallback
    default_persona: str = "neutral"
    template_prompt_version: str = "template-v1"

    # --- text lint ---
    lint_allowed_capitalized: tuple[str, ...] = ()  # capitalized words allowed mid-sentence
    lint_percent_tolerance: float = 0.5  # gap between a whole percent in the text and a ratio claim
    lint_number_words: bool = True  # also check numbers written as words (EN, 0-20)
    lint_bare_surname: bool = True  # free text that names a player by surname only is rejected

    # --- slot template lint (foundry-v4 rules; v3 behaviour when off) ---
    slot_event_words: bool = True  # event type / role words only via {event:}
    slot_sentence_start: bool = True  # first word of a sentence is a placeholder or an allowed start
    slot_strict_number_words: bool = True  # number words banned regardless of context ("one of")
    slot_overstatement: bool = True  # qualitative overstatement list (unless the moment type supports it)
    # --- foundry-v4.1 rules ---
    slot_event_type_allowlist: bool = True  # {event:} only for event types the moment type allows
    slot_player_repeat: bool = True  # {event:X} plus a {player:} for X's player in one sentence is banned
    slot_article_team: bool = True  # "the" before a team placeholder is banned ("The {home}")
    # --- foundry-v5 claim menu rules (menu drafts only) ---
    slot_sentence_claim: bool = True  # every sentence rests on at least one menu claim
    slot_primary_claim: bool = True  # a dominance / pressure moment uses its primary claim
    slot_minute_repeat: bool = True  # the same minute is not written twice in one sentence
    # --- foundry-v5.1 rules (menu drafts only) ---
    slot_team_repeat_max: int = 2  # one team named more often than this in one sentence is rejected (0: off)
    # --- foundry-v5.2 ---
    # Team names team_repeat does not count: "none" (v5.1), "score" (the score line: {score_named},
    # {clause:score}), "score+primary" (also the primary-claim clauses). Chosen in docs/EVAL.md.
    slot_team_repeat_exempt: str = "score"
    # Sentence-start words derived from clean drafts (eval/lint_rates.py `derive_sentence_starts`).
    # Do not edit by hand; tests/test_lint_rates.py checks it equals the re-derived list.
    sentence_start_allowed_en: tuple[str, ...] = ("The",)

    # --- LLM narrator safety ---
    llm_timeout_s: float = 60.0  # per call (reasoning model)
    llm_max_tokens: int = 4000  # response token cap; includes reasoning tokens
    llm_max_calls_per_run: int = 60  # total calls per narrator instance (run)
    llm_reasoning_effort: str = "low"  # Responses reasoning.effort (none|low|medium|high)


DEFAULT_EXPLAIN_CONFIG = ExplainConfig()
