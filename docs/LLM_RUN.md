# LLM narration measurement (real model)

This file is built from the raw output of a `python -m eval.llm_run` run (`docs/LLM_RUN.json`); do not edit it by hand.

- Model: `gpt-5-mini` · Prompt version: `foundry-v5.1:gpt-5-mini` · Language: `en` · Reasoning effort: `low`
- Run: 2026-10-13T14:39:57+00:00 – 2026-10-13T14:41:30+00:00 (UTC)
- Settings: at most 60 calls per run (match), `max_output_tokens` 4000, call timeout 60 s, at most 2 retries, cache off
- Every draft went through lint + placeholder binding + verify_claim; a draft that failed was not published and fell back to the template. Code rendered the concrete values in the published LLM texts.

## Summary

| Match | Moment | Passed first try | Passed after retry | Fell back | Calls | Tokens in / out | Reasoning (% of output) | Avg. duration | Median | Max. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red_card_swing_seed42 | 6 | 6 (100.0%) | 0 (0.0%) | 0 (0.0%) | 6 | 14037 / 2757 | 2368 (85.9%) | 6.8 sn | 6.5 sn | 10.0 sn |
| dominant_loss_seed7 | 4 | 4 (100.0%) | 0 (0.0%) | 0 (0.0%) | 4 | 9437 / 2135 | 1920 (89.9%) | 5.9 sn | 6.2 sn | 6.7 sn |
| natural_seed100 | 5 | 5 (100.0%) | 0 (0.0%) | 0 (0.0%) | 5 | 11337 / 2214 | 1920 (86.7%) | 5.5 sn | 5.6 sn | 6.6 sn |
| **Total** | 15 | 15 (100.0%) | 0 (0.0%) | 0 (0.0%) | 15 | 34811 / 7106 | 6208 (87.4%) | 6.1 sn | 6.0 sn | 10.0 sn |

## Version comparison: foundry-v3, foundry-v4, foundry-v4.1, foundry-v5, foundry-v5.1

Earlier versions come from the archived raw outputs (`docs/LLM_RUN.<version>.json`). Rejected = an attempt that was not published; the `evidence_mismatch` column counts rejected attempts with that code.

| Version / run | Moments | First try | After retry | Fell back | Calls | Rejected attempts | evidence_mismatch | Tokens out |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| foundry-v3 | 22 | 12 | 8 | 2 | 37 | 17 | 12 | 56884 |
| foundry-v4 | 22 | 12 | 6 | 4 | 38 | 20 | 13 | 63598 |
| foundry-v4.1 · run 1 | 22 | 16 | 3 | 3 | 33 | 14 | 10 | 49588 |
| foundry-v4.1 · run 2 | 22 | 14 | 6 | 2 | 35 | 15 | 15 | 51072 |
| foundry-v4.1 · run 3 | 22 | 15 | 5 | 2 | 34 | 14 | 11 | 53295 |
| **foundry-v4.1 · total (3 runs)** | 66 | 45 | 14 | 7 | 102 | 43 | 36 | 153955 |
| foundry-v5 · run 1 | 22 | 22 | 0 | 0 | 22 | 0 | 0 | 8873 |
| foundry-v5 · run 2 | 22 | 22 | 0 | 0 | 22 | 0 | 0 | 9444 |
| foundry-v5 · run 3 | 22 | 21 | 1 | 0 | 23 | 1 | 0 | 8967 |
| **foundry-v5 · total (3 runs)** | 66 | 65 | 1 | 0 | 67 | 1 | 0 | 27284 |
| foundry-v5.1 | 15 | 15 | 0 | 0 | 15 | 0 | 0 | 7106 |

Rejected attempts with `evidence_mismatch`, per moment type (all runs of the version; number of runs in parentheses):

| Moment type | foundry-v3 (1) | foundry-v4 (1) | foundry-v4.1 (3) | foundry-v5 (3) | foundry-v5.1 (1) |
|---|---:|---:|---:|---:|---:|
| dominance_without_reward | 6 | 3 | 11 | 0 | 0 |
| goal | 3 | 3 | 16 | 0 | 0 |
| penalty | 0 | 3 | 0 | 0 | 0 |
| pressure_shift | 3 | 4 | 9 | 0 | 0 |
| red_card | 0 | 0 | 0 | 0 | 0 |
| score_change | 0 | 0 | 0 | 0 | 0 |

## Rejection code frequency

Codes in rejected attempts, average per run (an attempt can have more than one code).

| Code | foundry-v3 (1 runs) | foundry-v4 (1 runs) | foundry-v4.1 (3 runs) | foundry-v5 (3 runs) | foundry-v5.1 (1 runs) |
|---|---:|---:|---:|---:|---:|
| `evidence_mismatch` | 14 | 17 | 13 | 0 | 0 |
| `invalid_subject` | 3 | 6 | 2.3 | 0 | 0 |
| `article_team` | 0 | 0 | 2.3 | 0.3 | 0 |
| `raw_entity` | 0 | 3 | 0.7 | 0 | 0 |
| `raw_number` | 2 | 0 | 1 | 0 | 0 |
| `missing_evidence` | 2 | 0 | 0 | 0 | 0 |
| `unknown_placeholder` | 1 | 0 | 0.3 | 0 | 0 |
| `raw_metric_name` | 0 | 0 | 0.3 | 0 | 0 |
| `sentence_start` | 0 | 0 | 0.3 | 0 | 0 |
| `unbound_placeholder` | 1 | 0 | 0 | 0 | 0 |

## Side by side: the same moments, version by version

Published text; the last run for multi-run versions. *(fallback)* = template fallback. Rows are matched by match, time and moment type (ids are renumbered between versions). Before foundry-v5.1 a goal that changed the match state also had a separate `score_change` card; those cards have no row here, the goal row shows the earlier goal card.

| Moment | Type | foundry-v3 | foundry-v4 | foundry-v4.1 | foundry-v5 | foundry-v5.1 |
|---|---|---|---|---|---|---|
| red_card_swing M002 | goal | Murek Brestani scored at 22', making it Brannoch FC 1–0 Morvane Athletic. Brannoch FC have had 55% of the ball since kickoff. | Murek Brestani scored at 22', making it 1–0. Brannoch FC have had 55% of the ball since kickoff. | Murek Brestani scored at 22', making it 1–0. Possession: Brannoch FC have had 55% of the ball since kickoff. | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. The score is Brannoch FC 1–0 Morvane Athletic. |
| red_card_swing M004 | red_card | Orvik Belmaro was sent off at 38', leaving Brannoch FC with Brannoch FC 1–0 Morvane Athletic. Morvane Athletic have had 46% of the ball since kickoff. | Orvik Belmaro was sent off at 38'. Brannoch FC have had 54% of the ball since kickoff. | Orvik Belmaro was sent off at 38'. Possession for Brannoch FC since kickoff is 54%, red cards for Brannoch FC is 1 and at 38' the goal margin for Brannoch FC is 1. | Orvik Belmaro was sent off at 38', and Brannoch FC are down to 10 players on the pitch. | Orvik Belmaro was sent off at 38', and Brannoch FC are down to 10 players on the pitch. |
| red_card_swing M006 | goal | Davel Selvado scored at 61', making it Brannoch FC 1–1 Morvane Athletic. Brannoch FC have had 51% of the ball while Morvane Athletic lead the pressure balance at +1.00. | Davel Selvado scored at 61', making it 1–1. They have had 49% of the ball since kickoff. | Davel Selvado scored at 61', making it 1–1. Morvane Athletic have had 71% of the territorial share since kickoff. | Davel Selvado scored at 61', and the score is Brannoch FC 1–1 Morvane Athletic. | Davel Selvado scored at 61', and Morvane Athletic drew level. The score is Brannoch FC 1–1 Morvane Athletic. |
| red_card_swing M007 | pressure_shift | Murek Brestani had 2 shots for Brannoch FC at 80', and Brannoch FC had 50% of the ball; the score was Brannoch FC 1–1 Morvane Athletic. | *(fallback)* 81' — Brannoch FC take control: pressure balance +0.83 in their favour. Shots since 71': Brannoch FC 2, Morvane Athletic 0. | At Murek Brestani had a shot saved at 79', Brannoch FC have had 50% possession since kickoff. The pressure balance over the last 10 minutes of play for Brannoch FC is +0.83. | Brannoch FC lead the pressure balance over the last 10 minutes of play at +0.83, and Brannoch FC have had 2 shots to Morvane Athletic's 0 since 71'. | Brannoch FC lead the pressure balance over the last 10 minutes of play at +0.83, and Kesmir Ilvanto came on for Quenlo Faskoli at 81'. |
| red_card_swing M008 | goal | Murek Ymberto scored for Morvane Athletic at 84', making it Brannoch FC 1–2 Morvane Athletic. | *(fallback)* 84' — Murek Ymberto scores for Morvane Athletic. Brannoch FC 1–2 Morvane Athletic. | Murek Ymberto scored at 84', making it 1–2. Morvane Athletic have had 69% of the territorial share since kickoff. | Murek Ymberto scored at 84', and the score is Brannoch FC 1–2 Morvane Athletic. Morvane Athletic have had 50% of the ball since kickoff. | Murek Ymberto scored at 84', and the score is Brannoch FC 1–2 Morvane Athletic. Morvane Athletic went ahead after being 1 goal down, and Morvane Athletic have had 50% of the ball since kickoff. |
| red_card_swing M009 | pressure_shift | *(fallback)* 90+1' — Morvane Athletic take control: pressure balance +1.00 in their favour. Shots since 80': Morvane Athletic 1, Brannoch FC 0. | Possession has been 51% for Morvane Athletic since kickoff. The territorial share is 71% and Pernat Dremmet completed a pass at 89'. They have pressure balance of +1.00. | *(fallback)* 90+1' — Morvane Athletic take control: pressure balance over the last 10 minutes of play is +1.00 in their favour. Shots since 80': Morvane Athletic 1, Brannoch FC 0. | Murek Ymberto scored at 84', and Morvane Athletic lead the pressure balance over the last 10 minutes of play at +1.00. | Murek Ymberto scored at 84', and Morvane Athletic lead the pressure balance over the last 10 minutes of play at +1.00. |
| dominant_loss M003 | dominance_without_reward | *(fallback)* 45+1' — Vellorin FC dominate without reward: 58% of possession and 4–0 shots since 25', yet the score is Vellorin FC 0–0 Tessdal Athletic. | *(fallback)* 45+1' — Vellorin FC dominate without reward: since 25' they have had 58% of the ball and a 4–0 lead in shots, yet the score is Vellorin FC 0–0 Tessdal Athletic. | Ombar Belmaro shot off target at 45+1'. Possession Vellorin FC have had 61% of the ball since kickoff. | Since 25' Vellorin FC have had 58% of the ball and a 4–0 lead in shots. The score is Vellorin FC 0–0 Tessdal Athletic. | Ombar Belmaro shot off target at 45+1', and since 25' Vellorin FC have had 58% of the ball and a 4–0 lead in shots. |
| dominant_loss M005 | goal | Nolvek Ilvanto scored at 57', making it Vellorin FC 0–1 Tessdal Athletic. | Nolvek Ilvanto scored at 57', making it 0–1. Possession since kickoff: Vellorin FC have had 61% of the ball. | Nolvek Ilvanto scored at 57', making it Vellorin FC 0–1 Tessdal Athletic. Possession: Vellorin FC have had 61% of the ball since kickoff. | Nolvek Ilvanto scored at 57', and Tessdal Athletic have had 39% of the ball since kickoff. The score is Vellorin FC 0–1 Tessdal Athletic. | Nolvek Ilvanto scored at 57', and the score is Vellorin FC 0–1 Tessdal Athletic. |
| dominant_loss M007 | dominance_without_reward | Alvezo Hazulov registered 2 of the shots between 58' and 66'. Vellorin FC have had 62% of the ball and remain behind at Vellorin FC 0–1 Tessdal Athletic. | Korin Zerimek had a shot blocked at 66'. They registered 5 shots between 58' and 66', and Vellorin FC have had 62% of the ball since kickoff. | Korin Zerimek had a shot blocked at 66'. At 66', Vellorin FC have had 62% of the ball since kickoff and the score is 0–1. | Since 46' Vellorin FC have had 71% of the ball and a 5–1 lead in shots, yet the score is Vellorin FC 0–1 Tessdal Athletic. | Since 46' Vellorin FC have had 71% of the ball and a 5–1 lead in shots. Nolvek Ilvanto scored at 57'. |
| dominant_loss M008 | penalty | Alvezo Hazulov saved a penalty at 70', keeping the score Vellorin FC 0–1 Tessdal Athletic. Vellorin FC have had 62% of the ball since kickoff. | *(fallback)* 70' — Penalty for Vellorin FC, but Alvezo Hazulov sees the kick saved. | Alvezo Hazulov's penalty was saved at 70'. Possession since kickoff has been 62% for Vellorin FC, and Vellorin FC have 1 penalties saved. | Alvezo Hazulov's penalty was saved at 70', and Vellorin FC have had 62% of the ball since kickoff. | Alvezo Hazulov's penalty was saved at 70', and Vellorin FC have had 62% of the ball since kickoff. The score is Vellorin FC 0–1 Tessdal Athletic. |
| natural M001 | red_card | Iveno Gundrel was shown a red card at 14', leaving the match at Tessdal Wanderers 0–0 Isteven United. Isteven United have had 51% of the ball up to that point. | Iveno Gundrel was sent off at 14'. Isteven United have had 51% of the ball since kickoff. | Iveno Gundrel was sent off at 14'. Isteven United have had 51% possession since kickoff and the match is 0–0. | Iveno Gundrel was sent off at 14'. Isteven United are down to 10 players on the pitch, and Isteven United have had 51% of the ball since kickoff. | Iveno Gundrel was sent off at 14', and Isteven United are down to 10 players on the pitch. |
| natural M004 | goal | Hesko Ilvanto scored for Tessdal Wanderers at 29', making it Tessdal Wanderers 1–0 Isteven United. | Hesko Ilvanto scored at 29', making it 1–0. At 29' Tessdal Wanderers have had 58% of the ball since kickoff. | Hesko Ilvanto scored at 29', making it 1–0. Possession: Tessdal Wanderers have had 58% of the ball since kickoff. | Hesko Ilvanto scored at 29', and Tessdal Wanderers have had 58% of the ball since kickoff. | Hesko Ilvanto scored at 29', and Tessdal Wanderers have had 58% of the ball since kickoff. The score is Tessdal Wanderers 1–0 Isteven United. |
| natural M005 | goal | Quenlo Pelvisto levelled the match at 51', making it Tessdal Wanderers 1–1 Isteven United. | Quenlo Pelvisto scored at 51', making it 1–1. Possession has been 51% for Tessdal Wanderers since kickoff. | Quenlo Pelvisto scored at 51', making it 1–1. Possession for Isteven United since kickoff is 49%. | Quenlo Pelvisto scored at 51', and the score is Tessdal Wanderers 1–1 Isteven United. | Quenlo Pelvisto scored at 51', and the score is Tessdal Wanderers 1–1 Isteven United. Isteven United have had 49% of the ball since kickoff. |
| natural M007 | dominance_without_reward | Rastin Ymberto took a shot off target at 79', leaving it Tessdal Wanderers 1–1 Isteven United. Tessdal Wanderers have had 54% of the ball since kickoff. | Rastin Ymberto shot off target at 79'. The Tessdal Wanderers have had 54% of the ball since kickoff, with pressure balance at +1.00. | At 79' Rastin Ymberto shot off target at 79'. Possession Tessdal Wanderers have had 54% of the ball since kickoff. | Rastin Ymberto shot off target at 79', and since 59' Tessdal Wanderers have had 61% of the ball and a 4–0 lead in shots. | Since 59' Tessdal Wanderers have had 61% of the ball and a 4–0 lead in shots, and Rastin Ymberto shot off target at 79'. |
| natural M008 | goal | Brisko Ymberto scored deep into stoppage, making it Tessdal Wanderers 2–1 Isteven United at 90+1'. Tessdal Wanderers have had 52% of the ball. | Brisko Ymberto scored at 90+1' by Brisko Ymberto, making it 2–1. Possession since kickoff: Tessdal Wanderers have had 52% of the ball. | *(fallback)* 90+1' — Brisko Ymberto scores for Tessdal Wanderers. Tessdal Wanderers 2–1 Isteven United. | Brisko Ymberto scored at 90+1', and Tessdal Wanderers have had 52% of the ball since kickoff. The score is Tessdal Wanderers 2–1 Isteven United. | Brisko Ymberto scored at 90+1', and Tessdal Wanderers went ahead. The score is Tessdal Wanderers 2–1 Isteven United. |

## evidence_mismatch: cited and counted events

No `evidence_mismatch` rejections in this run (foundry-v5: code builds the claims and their evidence, the model links no events). Earlier versions' breakdown can be re-rendered from the archived JSONs.

## Live firing of the foundry-v4.1 / v5 / v5.1 rules

This rule only = the rule was the attempt's only rejection reason (no other lint or verify error): without the rule it would have been published. A correct rejection if it is the pattern the rule targets, otherwise a false alarm; drafts below.

| Rule | Attempts fired | This rule only | Fragments |
|---|---:|---:|---|
| `event_type_not_allowed` | 0 | 0 | — |
| `player_repeat` | 0 | 0 | — |
| `article_team` | 0 | 0 | — |
| `sentence_start` | 0 | 0 | — |
| `unknown_claim_id` | 0 | 0 | — |
| `sentence_without_claim` | 0 | 0 | — |
| `missing_primary_claim` | 0 | 0 | — |
| `minute_repeat` | 0 | 0 | — |
| `team_repeat` | 0 | 0 | — |

## Moments that fell back

None.

## Moments that passed after a retry

None.

## Client errors

None.

## Moment details

### red_card_swing_seed42

| Moment | Type | Minute | Source | Attempts | Published text | Model template |
|---|---|---|---|---:|---|---|
| M002 | goal | 22' | llm | 1 | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. The score is Brannoch FC 1–0 Morvane Athletic. | `{event:m-42-red_card_swing#127}, and {clause:possession}. {clause:score}.` |
| M004 | red_card | 38' | llm | 1 | Orvik Belmaro was sent off at 38', and Brannoch FC are down to 10 players on the pitch. | `{event:m-42-red_card_swing#213}, and {clause:players}.` |
| M006 | goal | 61' | llm | 1 | Davel Selvado scored at 61', and Morvane Athletic drew level. The score is Brannoch FC 1–1 Morvane Athletic. | `{event:m-42-red_card_swing#359}, and {clause:equalizer}. {clause:score}.` |
| M007 | pressure_shift | 81' | llm | 1 | Brannoch FC lead the pressure balance over the last 10 minutes of play at +0.83, and Kesmir Ilvanto came on for Quenlo Faskoli at 81'. | `{clause:pressure}, and {event:m-42-red_card_swing#476}.` |
| M008 | goal | 84' | llm | 1 | Murek Ymberto scored at 84', and the score is Brannoch FC 1–2 Morvane Athletic. Morvane Athletic went ahead after being 1 goal down, and Morvane Athletic have had 50% of the ball since kickoff. | `{event:m-42-red_card_swing#494}, and {clause:score}. {clause:go_ahead}, and {clause:possession}.` |
| M009 | pressure_shift | 90+1' | llm | 1 | Murek Ymberto scored at 84', and Morvane Athletic lead the pressure balance over the last 10 minutes of play at +1.00. | `{event:m-42-red_card_swing#493}, and {clause:pressure}.` |

### dominant_loss_seed7

| Moment | Type | Minute | Source | Attempts | Published text | Model template |
|---|---|---|---|---:|---|---|
| M003 | dominance_without_reward | 45+1' | llm | 1 | Ombar Belmaro shot off target at 45+1', and since 25' Vellorin FC have had 58% of the ball and a 4–0 lead in shots. | `{event:m-7-dominant_loss#269}, and {clause:dominance}.` |
| M005 | goal | 57' | llm | 1 | Nolvek Ilvanto scored at 57', and the score is Vellorin FC 0–1 Tessdal Athletic. | `{event:m-7-dominant_loss#350}, and {clause:score}.` |
| M007 | dominance_without_reward | 66' | llm | 1 | Since 46' Vellorin FC have had 71% of the ball and a 5–1 lead in shots. Nolvek Ilvanto scored at 57'. | `{clause:dominance}. {event:m-7-dominant_loss#349}.` |
| M008 | penalty | 70' | llm | 1 | Alvezo Hazulov's penalty was saved at 70', and Vellorin FC have had 62% of the ball since kickoff. The score is Vellorin FC 0–1 Tessdal Athletic. | `{event:m-7-dominant_loss#428}, and {clause:possession}. {clause:score}.` |

### natural_seed100

| Moment | Type | Minute | Source | Attempts | Published text | Model template |
|---|---|---|---|---:|---|---|
| M001 | red_card | 14' | llm | 1 | Iveno Gundrel was sent off at 14', and Isteven United are down to 10 players on the pitch. | `{event:m-100#84}, and {clause:players}.` |
| M004 | goal | 29' | llm | 1 | Hesko Ilvanto scored at 29', and Tessdal Wanderers have had 58% of the ball since kickoff. The score is Tessdal Wanderers 1–0 Isteven United. | `{event:m-100#175}, and {clause:possession}. {clause:score}.` |
| M005 | goal | 51' | llm | 1 | Quenlo Pelvisto scored at 51', and the score is Tessdal Wanderers 1–1 Isteven United. Isteven United have had 49% of the ball since kickoff. | `{event:m-100#317}, and {clause:score}. {clause:possession}.` |
| M007 | dominance_without_reward | 79' | llm | 1 | Since 59' Tessdal Wanderers have had 61% of the ball and a 4–0 lead in shots, and Rastin Ymberto shot off target at 79'. | `{clause:dominance}, and {event:m-100#478}.` |
| M008 | goal | 90+1' | llm | 1 | Brisko Ymberto scored at 90+1', and Tessdal Wanderers went ahead. The score is Tessdal Wanderers 2–1 Isteven United. | `{event:m-100#550}, and {clause:go_ahead}. {clause:score}.` |
