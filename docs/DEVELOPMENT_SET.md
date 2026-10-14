# Development set (excluded from P4's held-out set)

Everything below was looked at while the agents were built and tuned (2026-10-14). P4's held-out measurement must use
**other moments**: none of these (match, moment) pairs and none of these drafts. The machine-readable list is
[development_set.json](development_set.json); `tests/test_development_set.py` keeps the two in step with the run files.

## What is in it
- **The 15 featured cards** of the three demo matches (`red_card_swing_seed42` 6, `dominant_loss_seed7` 4, `natural_seed100` 5): read
  in the canary, the reruns and the 15-card runs ([AGENT_RUN_canary.json](AGENT_RUN_canary.json),
  [AGENT_RUN_rerun1.json](AGENT_RUN_rerun1.json), [AGENT_RUN_run2.json](AGENT_RUN_run2.json), [AGENT_RUN.json](AGENT_RUN.json)); the Analyst and
  Verifier rules below were changed after reading them.
- **The Verifier smoke-test drafts** ([VERIFIER_SMOKE.json](VERIFIER_SMOKE.json), `meta.development_set`): 4 + 4 + 4 injected and 8 clean
  drafts, from the injection corpus (seeds 42, 7, 100, 0, 3 ...). The first run ([VERIFIER_SMOKE_before_fix.json](VERIFIER_SMOKE_before_fix.json))
  is the same set.

## Observations that shaped the code (all on development material)
| Observation | Where | What changed |
|---|---|---|
| Verifier false alarm: "over the last 10 minutes of play" rejected as a wrong timeframe; the record showed `from 0'` for a rolling metric | `red_card_swing` M007 (canary) | the record carries each metric's window and definition; `from` only when the start is measured |
| Verifier false alarm: "went ahead" rejected as unsupported although a code-written clause states a verified margin; the same text passed on the second call | `natural_seed100` M008 (15-card run) | the record lists each clause with the claims it rests on and its meaning |
| Analyst answers with clause ids instead of claim ids (3 of 6 cards) | canary | a clause id is expanded to its claims; `expanded_clause_ids` in the trace |
| Analyst note refused as "contains a number" on ordinary words (2 of 15) | `dominant_loss_seed7` M005, `natural_seed100` M005 | only digits and cardinal numbers are refused; the refused token is in the trace |
| A rejection whose span is not in the text was a `verifier_error` | design | it is a rejection (`unlocated_span` in the trace, no fragment) |

## Rule for P4
A moment is in the held-out set only if its `(match_id, moment_id)` is not in `development_set.json` and its match is not one of the three
demo matches. Moments of other seeds are free.
