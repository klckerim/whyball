# Development set (excluded from P4's held-out set)

Everything below was looked at while the agents were built and tuned (2026-10-14). P4's held-out measurement must use
**other moments**: none of these (match, moment) pairs and none of these drafts. The machine-readable list is
[development_set.json](development_set.json); `tests/test_development_set.py` keeps the two in step with the run files.

## What is in it
- **The 15 featured cards** of the three demo matches (`red_card_swing_seed42` 6, `dominant_loss_seed7` 4, `natural_seed100` 5): read
  in the canary, the reruns and the 15-card runs ([AGENT_RUN_canary.json](AGENT_RUN_canary.json),
  [AGENT_RUN_rerun1.json](archive/AGENT_RUN_rerun1.json), [AGENT_RUN_run2.json](archive/AGENT_RUN_run2.json), [AGENT_RUN.json](AGENT_RUN.json)); the Analyst and
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

## Candidates for P4 labelling ("dull" candidates and Verifier-role observations)
These are what a human label ("correct" / "dull" / ...) should look at first in P4; they are observations, not labels.
| Card | Observation (2026-10-14 runs) | Why it is a candidate |
|---|---|---|
| `dominant_loss_seed7` M005 (57') | published text: "Tessdal Athletic opened the scoring. The score is Vellorin FC 0–1 Tessdal Athletic." The previous store text named the scorer and the minute ("Nolvek Ilvanto scored at 57' ..."). | correct and verified, but under-informative: no scorer, no minute (**dull** candidate) |
| `natural_seed100` M008 (90+1') | first 15-card run: the Verifier rejected "went ahead." (`unsupported_statement`) on a code-written clause; the Narrator wrote the identical template again and the Verifier passed it | Verifier role: a false alarm and a verdict flip on the same input (before the clause meanings were added to its record) |
| `natural_seed100` M004 (29') | attempt 1 rejected by the Guard (`article_team`), attempt 2 passed | Guard, not Verifier: shows the feedback loop working |
| `natural_seed100` M001, M005; `dominant_loss_seed7` M005 | Analyst note refused (`note_has_number`) in the first 15-card run; in the latest run only natural M001 (token `one`) | Analyst role: cardinal-number rule at work |
| `natural_seed100` M008 (latest run) | text no longer contains the clause the Verifier once rejected ("went ahead") | the earlier false alarm cannot be re-tested on this card: P4 needs fresh cards for that |
