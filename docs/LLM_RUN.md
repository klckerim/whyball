# LLM narration measurement (real model)

This file is built from the raw output of a `python -m eval.llm_run` run (`docs/LLM_RUN.json`); do not edit it by hand.

- Model: `gpt-5-mini` · Prompt version: `foundry-v5.2:gpt-5-mini` · Language: `en` · Reasoning effort: `low`
- Run: 2026-10-13T14:59:53+00:00 – 2026-10-13T15:05:08+00:00 (UTC), 3 runs (same prompt)
- Settings: at most 60 calls per run (match), `max_output_tokens` 4000, call timeout 60 s, at most 2 retries, cache off
- Every draft went through lint + placeholder binding + verify_claim; a draft that failed was not published and fell back to the template. Code rendered the concrete values in the published LLM texts.

## Summary

### Run 1 (2026-10-13T14:59:53+00:00 – 2026-10-13T15:01:22+00:00)

| Match | Moment | Passed first try | Passed after retry | Fell back | Calls | Tokens in / out | Reasoning (% of output) | Avg. duration | Median | Max. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red_card_swing_seed42 | 6 | 5 (83.3%) | 1 (16.7%) | 0 (0.0%) | 7 | 16605 / 3509 | 3008 (85.7%) | 5.2 sn | 6.2 sn | 6.5 sn |
| dominant_loss_seed7 | 4 | 3 (75.0%) | 1 (25.0%) | 0 (0.0%) | 5 | 12406 / 1498 | 1216 (81.2%) | 4.3 sn | 5.0 sn | 5.2 sn |
| natural_seed100 | 5 | 5 (100.0%) | 0 (0.0%) | 0 (0.0%) | 5 | 11546 / 2495 | 2112 (84.6%) | 6.0 sn | 5.5 sn | 10.4 sn |
| **Total** | 15 | 13 (86.7%) | 2 (13.3%) | 0 (0.0%) | 17 | 40557 / 7502 | 6336 (84.5%) | 5.2 sn | 5.1 sn | 10.4 sn |

### Run 2 (2026-10-13T15:01:22+00:00 – 2026-10-13T15:02:48+00:00)

| Match | Moment | Passed first try | Passed after retry | Fell back | Calls | Tokens in / out | Reasoning (% of output) | Avg. duration | Median | Max. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red_card_swing_seed42 | 6 | 6 (100.0%) | 0 (0.0%) | 0 (0.0%) | 6 | 14263 / 2874 | 2496 (86.8%) | 6.1 sn | 6.6 sn | 10.0 sn |
| dominant_loss_seed7 | 4 | 3 (75.0%) | 1 (25.0%) | 0 (0.0%) | 5 | 11728 / 2001 | 1600 (80.0%) | 4.5 sn | 4.2 sn | 6.8 sn |
| natural_seed100 | 5 | 5 (100.0%) | 0 (0.0%) | 0 (0.0%) | 5 | 11546 / 1795 | 1408 (78.4%) | 5.2 sn | 5.4 sn | 6.5 sn |
| **Total** | 15 | 14 (93.3%) | 1 (6.7%) | 0 (0.0%) | 16 | 37537 / 6670 | 5504 (82.5%) | 5.3 sn | 5.0 sn | 10.0 sn |

### Run 3 (2026-10-13T15:02:48+00:00 – 2026-10-13T15:05:08+00:00)

| Match | Moment | Passed first try | Passed after retry | Fell back | Calls | Tokens in / out | Reasoning (% of output) | Avg. duration | Median | Max. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red_card_swing_seed42 | 6 | 5 (83.3%) | 1 (16.7%) | 0 (0.0%) | 7 | 14296 / 3215 | 2816 (87.6%) | 13.3 sn | 5.9 sn | 60.0 sn |
| dominant_loss_seed7 | 4 | 4 (100.0%) | 0 (0.0%) | 0 (0.0%) | 4 | 9651 / 1553 | 1280 (82.4%) | 4.2 sn | 3.7 sn | 6.2 sn |
| natural_seed100 | 5 | 5 (100.0%) | 0 (0.0%) | 0 (0.0%) | 5 | 11546 / 2965 | 2560 (86.3%) | 6.1 sn | 7.0 sn | 7.1 sn |
| **Total** | 15 | 14 (93.3%) | 1 (6.7%) | 0 (0.0%) | 16 | 35493 / 7733 | 6656 (86.1%) | 8.8 sn | 6.1 sn | 60.0 sn |

### Fallbacks per run

| Run | Moments | Fell back | Rejected attempts | evidence_mismatch |
|---|---:|---:|---:|---:|
| 1 | 15 | 0 | 2 | 0 |
| 2 | 15 | 0 | 1 | 0 |
| 3 | 15 | 0 | 1 | 0 |
| **Total** | 45 | 0 | 4 | 0 |

## Version comparison: foundry-v3, foundry-v4, foundry-v4.1, foundry-v5, foundry-v5.1, foundry-v5.2

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
| foundry-v5.2 · run 1 | 15 | 13 | 2 | 0 | 17 | 2 | 0 | 7502 |
| foundry-v5.2 · run 2 | 15 | 14 | 1 | 0 | 16 | 1 | 0 | 6670 |
| foundry-v5.2 · run 3 | 15 | 14 | 1 | 0 | 16 | 1 | 0 | 7733 |
| **foundry-v5.2 · total (3 runs)** | 45 | 41 | 4 | 0 | 49 | 4 | 0 | 21905 |

Rejected attempts with `evidence_mismatch`, per moment type (all runs of the version; number of runs in parentheses):

| Moment type | foundry-v3 (1) | foundry-v4 (1) | foundry-v4.1 (3) | foundry-v5 (3) | foundry-v5.1 (1) | foundry-v5.2 (3) |
|---|---:|---:|---:|---:|---:|---:|
| dominance_without_reward | 6 | 3 | 11 | 0 | 0 | 0 |
| goal | 3 | 3 | 16 | 0 | 0 | 0 |
| penalty | 0 | 3 | 0 | 0 | 0 | 0 |
| pressure_shift | 3 | 4 | 9 | 0 | 0 | 0 |
| red_card | 0 | 0 | 0 | 0 | 0 | 0 |
| score_change | 0 | 0 | 0 | 0 | 0 | 0 |

## Rejection code frequency

Codes in rejected attempts, average per run (an attempt can have more than one code).

| Code | foundry-v3 (1 runs) | foundry-v4 (1 runs) | foundry-v4.1 (3 runs) | foundry-v5 (3 runs) | foundry-v5.1 (1 runs) | foundry-v5.2 (3 runs) |
|---|---:|---:|---:|---:|---:|---:|
| `evidence_mismatch` | 14 | 17 | 13 | 0 | 0 | 0 |
| `invalid_subject` | 3 | 6 | 2.3 | 0 | 0 | 0 |
| `article_team` | 0 | 0 | 2.3 | 0.3 | 0 | 1 |
| `raw_entity` | 0 | 3 | 0.7 | 0 | 0 | 0 |
| `raw_number` | 2 | 0 | 1 | 0 | 0 | 0 |
| `missing_evidence` | 2 | 0 | 0 | 0 | 0 | 0 |
| `unknown_placeholder` | 1 | 0 | 0.3 | 0 | 0 | 0 |
| `raw_metric_name` | 0 | 0 | 0.3 | 0 | 0 | 0 |
| `sentence_start` | 0 | 0 | 0.3 | 0 | 0 | 0 |
| `timeout` | 0 | 0 | 0 | 0 | 0 | 0.3 |
| `unbound_placeholder` | 1 | 0 | 0 | 0 | 0 | 0 |

## Main claim usage per card type

Share of published LLM texts (all runs) that use the card's main claim, for the menu versions. The claim is used when a placeholder refers to it (a clause, value, `{event:}` or `{score}`/`{score_named}`), measured on the model template against today's menu. Rows follow the foundry-v5.2 definition: dominance needs possession, shot balance and score; pressure needs pressure and shot balance; a goal that changed the match state needs the score (v5: its goal card; v5's separate score_change cards are left out). Fallback cards are not in the shares (the template states every main claim).

| Card | Main claim | foundry-v5 (3 runs) | foundry-v5.1 | foundry-v5.2 (3 runs) |
|---|---|---:|---:|---:|
| dominance_without_reward | possession | 9/9 (100%) | 3/3 (100%) | 9/9 (100%) |
| dominance_without_reward | shot balance | 9/9 (100%) | 3/3 (100%) | 9/9 (100%) |
| dominance_without_reward | score | 7/9 (78%) | 0/3 (0%) | 9/9 (100%) |
| pressure_shift | pressure balance | 6/6 (100%) | 2/2 (100%) | 6/6 (100%) |
| pressure_shift | shot balance | 3/6 (50%) | 0/2 (0%) | 6/6 (100%) |
| goal (match state change) | goal | 21/21 (100%) | 7/7 (100%) | 21/21 (100%) |
| goal (match state change) | score | 10/21 (48%) | 7/7 (100%) | 21/21 (100%) |
| red_card | sending-off | 6/6 (100%) | 2/2 (100%) | 6/6 (100%) |
| penalty | penalty | 3/3 (100%) | 1/1 (100%) | 3/3 (100%) |
| **Fallback cards** | | 0 | 0 | 0 |

## Side by side: the same moments, version by version

Published text; the last run for multi-run versions. *(fallback)* = template fallback. Rows are matched by match, time and moment type (ids are renumbered between versions). Before foundry-v5.1 a goal that changed the match state also had a separate `score_change` card; those cards have no row here, the goal row shows the earlier goal card.

| Moment | Type | foundry-v3 | foundry-v4 | foundry-v4.1 | foundry-v5 | foundry-v5.1 | foundry-v5.2 |
|---|---|---|---|---|---|---|---|
| red_card_swing M002 | goal | Murek Brestani scored at 22', making it Brannoch FC 1–0 Morvane Athletic. Brannoch FC have had 55% of the ball since kickoff. | Murek Brestani scored at 22', making it 1–0. Brannoch FC have had 55% of the ball since kickoff. | Murek Brestani scored at 22', making it 1–0. Possession: Brannoch FC have had 55% of the ball since kickoff. | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. The score is Brannoch FC 1–0 Morvane Athletic. | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. The score is Brannoch FC 1–0 Morvane Athletic. |
| red_card_swing M004 | red_card | Orvik Belmaro was sent off at 38', leaving Brannoch FC with Brannoch FC 1–0 Morvane Athletic. Morvane Athletic have had 46% of the ball since kickoff. | Orvik Belmaro was sent off at 38'. Brannoch FC have had 54% of the ball since kickoff. | Orvik Belmaro was sent off at 38'. Possession for Brannoch FC since kickoff is 54%, red cards for Brannoch FC is 1 and at 38' the goal margin for Brannoch FC is 1. | Orvik Belmaro was sent off at 38', and Brannoch FC are down to 10 players on the pitch. | Orvik Belmaro was sent off at 38', and Brannoch FC are down to 10 players on the pitch. | Orvik Belmaro was sent off at 38', and Brannoch FC are down to 10 players on the pitch. |
| red_card_swing M006 | goal | Davel Selvado scored at 61', making it Brannoch FC 1–1 Morvane Athletic. Brannoch FC have had 51% of the ball while Morvane Athletic lead the pressure balance at +1.00. | Davel Selvado scored at 61', making it 1–1. They have had 49% of the ball since kickoff. | Davel Selvado scored at 61', making it 1–1. Morvane Athletic have had 71% of the territorial share since kickoff. | Davel Selvado scored at 61', and the score is Brannoch FC 1–1 Morvane Athletic. | Davel Selvado scored at 61', and Morvane Athletic drew level. The score is Brannoch FC 1–1 Morvane Athletic. | Davel Selvado scored at 61', and Morvane Athletic drew level. The score is Brannoch FC 1–1 Morvane Athletic. |
| red_card_swing M007 | pressure_shift | Murek Brestani had 2 shots for Brannoch FC at 80', and Brannoch FC had 50% of the ball; the score was Brannoch FC 1–1 Morvane Athletic. | *(fallback)* 81' — Brannoch FC take control: pressure balance +0.83 in their favour. Shots since 71': Brannoch FC 2, Morvane Athletic 0. | At Murek Brestani had a shot saved at 79', Brannoch FC have had 50% possession since kickoff. The pressure balance over the last 10 minutes of play for Brannoch FC is +0.83. | Brannoch FC lead the pressure balance over the last 10 minutes of play at +0.83, and Brannoch FC have had 2 shots to Morvane Athletic's 0 since 71'. | Brannoch FC lead the pressure balance over the last 10 minutes of play at +0.83, and Kesmir Ilvanto came on for Quenlo Faskoli at 81'. | Brannoch FC lead the pressure balance over the last 10 minutes of play at +0.83, and Brannoch FC have had 2 shots to Morvane Athletic's 0 since 71'. |
| red_card_swing M008 | goal | Murek Ymberto scored for Morvane Athletic at 84', making it Brannoch FC 1–2 Morvane Athletic. | *(fallback)* 84' — Murek Ymberto scores for Morvane Athletic. Brannoch FC 1–2 Morvane Athletic. | Murek Ymberto scored at 84', making it 1–2. Morvane Athletic have had 69% of the territorial share since kickoff. | Murek Ymberto scored at 84', and the score is Brannoch FC 1–2 Morvane Athletic. Morvane Athletic have had 50% of the ball since kickoff. | Murek Ymberto scored at 84', and the score is Brannoch FC 1–2 Morvane Athletic. Morvane Athletic went ahead after being 1 goal down, and Morvane Athletic have had 50% of the ball since kickoff. | Murek Ymberto scored at 84', and Morvane Athletic went ahead after being 1 goal down. The score is Brannoch FC 1–2 Morvane Athletic and Morvane Athletic have had 50% of the ball since kickoff. |
| red_card_swing M009 | pressure_shift | *(fallback)* 90+1' — Morvane Athletic take control: pressure balance +1.00 in their favour. Shots since 80': Morvane Athletic 1, Brannoch FC 0. | Possession has been 51% for Morvane Athletic since kickoff. The territorial share is 71% and Pernat Dremmet completed a pass at 89'. They have pressure balance of +1.00. | *(fallback)* 90+1' — Morvane Athletic take control: pressure balance over the last 10 minutes of play is +1.00 in their favour. Shots since 80': Morvane Athletic 1, Brannoch FC 0. | Murek Ymberto scored at 84', and Morvane Athletic lead the pressure balance over the last 10 minutes of play at +1.00. | Murek Ymberto scored at 84', and Morvane Athletic lead the pressure balance over the last 10 minutes of play at +1.00. | Murek Ymberto scored at 84', and Morvane Athletic lead the pressure balance over the last 10 minutes of play at +1.00, and Morvane Athletic have had 1 shot to Brannoch FC's 0 since 80'. |
| dominant_loss M003 | dominance_without_reward | *(fallback)* 45+1' — Vellorin FC dominate without reward: 58% of possession and 4–0 shots since 25', yet the score is Vellorin FC 0–0 Tessdal Athletic. | *(fallback)* 45+1' — Vellorin FC dominate without reward: since 25' they have had 58% of the ball and a 4–0 lead in shots, yet the score is Vellorin FC 0–0 Tessdal Athletic. | Ombar Belmaro shot off target at 45+1'. Possession Vellorin FC have had 61% of the ball since kickoff. | Since 25' Vellorin FC have had 58% of the ball and a 4–0 lead in shots. The score is Vellorin FC 0–0 Tessdal Athletic. | Ombar Belmaro shot off target at 45+1', and since 25' Vellorin FC have had 58% of the ball and a 4–0 lead in shots. | Since 25' Vellorin FC have had 58% of the ball and a 4–0 lead in shots, yet the score is Vellorin FC 0–0 Tessdal Athletic. |
| dominant_loss M005 | goal | Nolvek Ilvanto scored at 57', making it Vellorin FC 0–1 Tessdal Athletic. | Nolvek Ilvanto scored at 57', making it 0–1. Possession since kickoff: Vellorin FC have had 61% of the ball. | Nolvek Ilvanto scored at 57', making it Vellorin FC 0–1 Tessdal Athletic. Possession: Vellorin FC have had 61% of the ball since kickoff. | Nolvek Ilvanto scored at 57', and Tessdal Athletic have had 39% of the ball since kickoff. The score is Vellorin FC 0–1 Tessdal Athletic. | Nolvek Ilvanto scored at 57', and the score is Vellorin FC 0–1 Tessdal Athletic. | Nolvek Ilvanto scored at 57', and the score is Vellorin FC 0–1 Tessdal Athletic. |
| dominant_loss M007 | dominance_without_reward | Alvezo Hazulov registered 2 of the shots between 58' and 66'. Vellorin FC have had 62% of the ball and remain behind at Vellorin FC 0–1 Tessdal Athletic. | Korin Zerimek had a shot blocked at 66'. They registered 5 shots between 58' and 66', and Vellorin FC have had 62% of the ball since kickoff. | Korin Zerimek had a shot blocked at 66'. At 66', Vellorin FC have had 62% of the ball since kickoff and the score is 0–1. | Since 46' Vellorin FC have had 71% of the ball and a 5–1 lead in shots, yet the score is Vellorin FC 0–1 Tessdal Athletic. | Since 46' Vellorin FC have had 71% of the ball and a 5–1 lead in shots. Nolvek Ilvanto scored at 57'. | Since 46' Vellorin FC have had 71% of the ball and a 5–1 lead in shots, yet the score is Vellorin FC 0–1 Tessdal Athletic. |
| dominant_loss M008 | penalty | Alvezo Hazulov saved a penalty at 70', keeping the score Vellorin FC 0–1 Tessdal Athletic. Vellorin FC have had 62% of the ball since kickoff. | *(fallback)* 70' — Penalty for Vellorin FC, but Alvezo Hazulov sees the kick saved. | Alvezo Hazulov's penalty was saved at 70'. Possession since kickoff has been 62% for Vellorin FC, and Vellorin FC have 1 penalties saved. | Alvezo Hazulov's penalty was saved at 70', and Vellorin FC have had 62% of the ball since kickoff. | Alvezo Hazulov's penalty was saved at 70', and Vellorin FC have had 62% of the ball since kickoff. The score is Vellorin FC 0–1 Tessdal Athletic. | Alvezo Hazulov's penalty was saved at 70', and Vellorin FC have had 62% of the ball since kickoff. |
| natural M001 | red_card | Iveno Gundrel was shown a red card at 14', leaving the match at Tessdal Wanderers 0–0 Isteven United. Isteven United have had 51% of the ball up to that point. | Iveno Gundrel was sent off at 14'. Isteven United have had 51% of the ball since kickoff. | Iveno Gundrel was sent off at 14'. Isteven United have had 51% possession since kickoff and the match is 0–0. | Iveno Gundrel was sent off at 14'. Isteven United are down to 10 players on the pitch, and Isteven United have had 51% of the ball since kickoff. | Iveno Gundrel was sent off at 14', and Isteven United are down to 10 players on the pitch. | Iveno Gundrel was sent off at 14'. Isteven United are down to 10 players on the pitch, and Isteven United have had 51% of the ball since kickoff. |
| natural M004 | goal | Hesko Ilvanto scored for Tessdal Wanderers at 29', making it Tessdal Wanderers 1–0 Isteven United. | Hesko Ilvanto scored at 29', making it 1–0. At 29' Tessdal Wanderers have had 58% of the ball since kickoff. | Hesko Ilvanto scored at 29', making it 1–0. Possession: Tessdal Wanderers have had 58% of the ball since kickoff. | Hesko Ilvanto scored at 29', and Tessdal Wanderers have had 58% of the ball since kickoff. | Hesko Ilvanto scored at 29', and Tessdal Wanderers have had 58% of the ball since kickoff. The score is Tessdal Wanderers 1–0 Isteven United. | Hesko Ilvanto scored at 29', and Tessdal Wanderers opened the scoring. The score is Tessdal Wanderers 1–0 Isteven United. |
| natural M005 | goal | Quenlo Pelvisto levelled the match at 51', making it Tessdal Wanderers 1–1 Isteven United. | Quenlo Pelvisto scored at 51', making it 1–1. Possession has been 51% for Tessdal Wanderers since kickoff. | Quenlo Pelvisto scored at 51', making it 1–1. Possession for Isteven United since kickoff is 49%. | Quenlo Pelvisto scored at 51', and the score is Tessdal Wanderers 1–1 Isteven United. | Quenlo Pelvisto scored at 51', and the score is Tessdal Wanderers 1–1 Isteven United. Isteven United have had 49% of the ball since kickoff. | Quenlo Pelvisto scored at 51', and Isteven United have had 49% of the ball since kickoff. The score is Tessdal Wanderers 1–1 Isteven United, and Isteven United drew level. |
| natural M007 | dominance_without_reward | Rastin Ymberto took a shot off target at 79', leaving it Tessdal Wanderers 1–1 Isteven United. Tessdal Wanderers have had 54% of the ball since kickoff. | Rastin Ymberto shot off target at 79'. The Tessdal Wanderers have had 54% of the ball since kickoff, with pressure balance at +1.00. | At 79' Rastin Ymberto shot off target at 79'. Possession Tessdal Wanderers have had 54% of the ball since kickoff. | Rastin Ymberto shot off target at 79', and since 59' Tessdal Wanderers have had 61% of the ball and a 4–0 lead in shots. | Since 59' Tessdal Wanderers have had 61% of the ball and a 4–0 lead in shots, and Rastin Ymberto shot off target at 79'. | Since 59' Tessdal Wanderers have had 61% of the ball and a 4–0 lead in shots, yet the score is Tessdal Wanderers 1–1 Isteven United. |
| natural M008 | goal | Brisko Ymberto scored deep into stoppage, making it Tessdal Wanderers 2–1 Isteven United at 90+1'. Tessdal Wanderers have had 52% of the ball. | Brisko Ymberto scored at 90+1' by Brisko Ymberto, making it 2–1. Possession since kickoff: Tessdal Wanderers have had 52% of the ball. | *(fallback)* 90+1' — Brisko Ymberto scores for Tessdal Wanderers. Tessdal Wanderers 2–1 Isteven United. | Brisko Ymberto scored at 90+1', and Tessdal Wanderers have had 52% of the ball since kickoff. The score is Tessdal Wanderers 2–1 Isteven United. | Brisko Ymberto scored at 90+1', and Tessdal Wanderers went ahead. The score is Tessdal Wanderers 2–1 Isteven United. | Brisko Ymberto scored at 90+1', and Tessdal Wanderers went ahead. Tessdal Wanderers have had 52% of the ball since kickoff, and the score is Tessdal Wanderers 2–1 Isteven United. |

## evidence_mismatch: cited and counted events

No `evidence_mismatch` rejections in this run (foundry-v5: code builds the claims and their evidence, the model links no events). Earlier versions' breakdown can be re-rendered from the archived JSONs.

## Live firing of the foundry-v4.1 / v5 / v5.1 / v5.2 rules

This rule only = the rule was the attempt's only rejection reason (no other lint or verify error): without the rule it would have been published. A correct rejection if it is the pattern the rule targets, otherwise a false alarm; drafts below.

| Rule | Attempts fired | This rule only | Fragments |
|---|---:|---:|---|
| `event_type_not_allowed` | 0 | 0 | — |
| `player_repeat` | 0 | 0 | — |
| `article_team` | 3 | 3 | `The {clause:score}`×2, `The {clause:dominance}`×1 |
| `sentence_start` | 0 | 0 | — |
| `unknown_claim_id` | 0 | 0 | — |
| `sentence_without_claim` | 0 | 0 | — |
| `missing_primary_claim` | 0 | 0 | — |
| `minute_repeat` | 0 | 0 | — |
| `team_repeat` | 0 | 0 | — |

Drafts rejected by a new rule alone:

- `article_team`: `{event:m-42-red_card_swing#359}, and {clause:equalizer}. The {clause:score}.`
- `article_team`: `The {clause:dominance}, yet {clause:score}.`
- `article_team`: `{event:m-7-dominant_loss#428}, and {clause:possession}. The {clause:score}.`

## Moments that fell back

None.

## Moments that passed after a retry

| Run | Match | Moment | Type | Attempts | Rejected attempts |
|---|---|---|---|---:|---|
| 1 | red_card_swing_seed42 | M006 | goal | 2 | #1: `article_team` |
| 1 | dominant_loss_seed7 | M007 | dominance_without_reward | 2 | #1: `article_team` |
| 2 | dominant_loss_seed7 | M008 | penalty | 2 | #1: `article_team` |
| 3 | red_card_swing_seed42 | M008 | goal | 2 | #1: `timeout` |

## Rejected drafts

| Run | Match | Moment | Type | Attempt | Rejection codes | Model template | Rejection message |
|---|---|---|---|---:|---|---|---|
| 1 | red_card_swing_seed42 | M006 | goal | 1 | `article_team` | `{event:m-42-red_card_swing#359}, and {clause:equalizer}. The {clause:score}.` | lint article_team 'The {clause:score}' |
| 1 | dominant_loss_seed7 | M007 | dominance_without_reward | 1 | `article_team` | `The {clause:dominance}, yet {clause:score}.` | lint article_team 'The {clause:dominance}' |
| 2 | dominant_loss_seed7 | M008 | penalty | 1 | `article_team` | `{event:m-7-dominant_loss#428}, and {clause:possession}. The {clause:score}.` | lint article_team 'The {clause:score}' |
| 3 | red_card_swing_seed42 | M008 | goal | 1 | `timeout` | — | LLM did not respond within 60 s |

## Client errors

| Run | Match | Moment | Call | Result | Message |
|---|---|---|---:|---|---|
| 3 | red_card_swing_seed42 | M008 | 5 | `timeout` | LLM did not respond within 60 s |

## Moment details

### Run 1 · red_card_swing_seed42

| Moment | Type | Minute | Source | Attempts | Published text | Model template |
|---|---|---|---|---:|---|---|
| M002 | goal | 22' | llm | 1 | Murek Brestani scored at 22', and the score is Brannoch FC 1–0 Morvane Athletic. Brannoch FC have had 55% of the ball since kickoff. | `{event:m-42-red_card_swing#127}, and {clause:score}. {clause:possession}.` |
| M004 | red_card | 38' | llm | 1 | Orvik Belmaro was sent off at 38', and Brannoch FC are down to 10 players on the pitch. | `{event:m-42-red_card_swing#213}, and {clause:players}.` |
| M006 | goal | 61' | llm | 2 | Davel Selvado scored at 61', and Morvane Athletic drew level, the score is Brannoch FC 1–1 Morvane Athletic. | `{event:m-42-red_card_swing#359}, and {clause:equalizer}, {clause:score}.` |
| M007 | pressure_shift | 81' | llm | 1 | Brannoch FC lead the pressure balance over the last 10 minutes of play at +0.83, and Brannoch FC have had 2 shots to Morvane Athletic's 0 since 71'. | `{clause:pressure}, and {clause:shots}.` |
| M008 | goal | 84' | llm | 1 | Murek Ymberto scored at 84', and Morvane Athletic went ahead after being 1 goal down. The score is Brannoch FC 1–2 Morvane Athletic. | `{event:m-42-red_card_swing#494}, and {clause:go_ahead}. {clause:score}.` |
| M009 | pressure_shift | 90+1' | llm | 1 | Morvane Athletic lead the pressure balance over the last 10 minutes of play at +1.00, and Morvane Athletic have had 1 shot to Brannoch FC's 0 since 80'. | `{clause:pressure}, and {clause:shots}.` |

### Run 1 · dominant_loss_seed7

| Moment | Type | Minute | Source | Attempts | Published text | Model template |
|---|---|---|---|---:|---|---|
| M003 | dominance_without_reward | 45+1' | llm | 1 | Since 25' Vellorin FC have had 58% of the ball and a 4–0 lead in shots, yet the score is Vellorin FC 0–0 Tessdal Athletic. | `{clause:dominance}, yet {clause:score}.` |
| M005 | goal | 57' | llm | 1 | Nolvek Ilvanto scored at 57', and the score is Vellorin FC 0–1 Tessdal Athletic. Tessdal Athletic have had 39% of the ball since kickoff. | `{event:m-7-dominant_loss#350}, and {clause:score}. {clause:possession}.` |
| M007 | dominance_without_reward | 66' | llm | 2 | Since 46' Vellorin FC have had 71% of the ball and a 5–1 lead in shots, yet the score is Vellorin FC 0–1 Tessdal Athletic. | `{clause:dominance}, yet {clause:score}.` |
| M008 | penalty | 70' | llm | 1 | Alvezo Hazulov's penalty was saved at 70', and Vellorin FC have had 62% of the ball since kickoff. | `{event:m-7-dominant_loss#428}, and {clause:possession}.` |

### Run 1 · natural_seed100

| Moment | Type | Minute | Source | Attempts | Published text | Model template |
|---|---|---|---|---:|---|---|
| M001 | red_card | 14' | llm | 1 | Iveno Gundrel was sent off at 14', and Isteven United are down to 10 players on the pitch. | `{event:m-100#84}, and {clause:players}.` |
| M004 | goal | 29' | llm | 1 | Hesko Ilvanto scored at 29', and the score is Tessdal Wanderers 1–0 Isteven United. | `{event:m-100#175}, and {clause:score}.` |
| M005 | goal | 51' | llm | 1 | Quenlo Pelvisto scored at 51', and Isteven United drew level. The score is Tessdal Wanderers 1–1 Isteven United, and Isteven United have had 49% of the ball since kickoff. | `{event:m-100#317}, and {clause:equalizer}. {clause:score}, and {clause:possession}.` |
| M007 | dominance_without_reward | 79' | llm | 1 | Since 59' Tessdal Wanderers have had 61% of the ball and a 4–0 lead in shots, yet the score is Tessdal Wanderers 1–1 Isteven United. | `{clause:dominance}, yet {clause:score}.` |
| M008 | goal | 90+1' | llm | 1 | Brisko Ymberto scored at 90+1', and Tessdal Wanderers went ahead. The score is Tessdal Wanderers 2–1 Isteven United. | `{event:m-100#550}, and {clause:go_ahead}. {clause:score}.` |

### Run 2 · red_card_swing_seed42

| Moment | Type | Minute | Source | Attempts | Published text | Model template |
|---|---|---|---|---:|---|---|
| M002 | goal | 22' | llm | 1 | Murek Brestani scored at 22', and the score is Brannoch FC 1–0 Morvane Athletic. | `{event:m-42-red_card_swing#127}, and {clause:score}.` |
| M004 | red_card | 38' | llm | 1 | Orvik Belmaro was sent off at 38', and Brannoch FC are down to 10 players on the pitch. The score is Brannoch FC 1–0 Morvane Athletic. | `{event:m-42-red_card_swing#213}, and {clause:players}. {clause:score}.` |
| M006 | goal | 61' | llm | 1 | Davel Selvado scored at 61'. The score is Brannoch FC 1–1 Morvane Athletic, and Morvane Athletic have had 49% of the ball since kickoff. | `{event:m-42-red_card_swing#359}. {clause:score}, and {clause:possession}.` |
| M007 | pressure_shift | 81' | llm | 1 | Brannoch FC lead the pressure balance over the last 10 minutes of play at +0.83, and Brannoch FC have had 2 shots to Morvane Athletic's 0 since 71'. | `{clause:pressure}, and {clause:shots}.` |
| M008 | goal | 84' | llm | 1 | Murek Ymberto scored at 84', and Morvane Athletic went ahead after being 1 goal down. The score is Brannoch FC 1–2 Morvane Athletic. | `{event:m-42-red_card_swing#494}, and {clause:go_ahead}. {clause:score}.` |
| M009 | pressure_shift | 90+1' | llm | 1 | Murek Ymberto scored at 84', and Morvane Athletic lead the pressure balance over the last 10 minutes of play at +1.00, and Morvane Athletic have had 1 shot to Brannoch FC's 0 since 80'. | `{event:m-42-red_card_swing#493}, and {clause:pressure}, and {clause:shots}.` |

### Run 2 · dominant_loss_seed7

| Moment | Type | Minute | Source | Attempts | Published text | Model template |
|---|---|---|---|---:|---|---|
| M003 | dominance_without_reward | 45+1' | llm | 1 | Since 25' Vellorin FC have had 58% of the ball and a 4–0 lead in shots, yet the score is Vellorin FC 0–0 Tessdal Athletic. | `{clause:dominance}, yet {clause:score}.` |
| M005 | goal | 57' | llm | 1 | Nolvek Ilvanto scored at 57', and Tessdal Athletic opened the scoring. The score is Vellorin FC 0–1 Tessdal Athletic, and Tessdal Athletic have had 39% of the ball since kickoff. | `{event:m-7-dominant_loss#350}, and {clause:opener}. {clause:score}, and {clause:possession}.` |
| M007 | dominance_without_reward | 66' | llm | 1 | Since 46' Vellorin FC have had 71% of the ball and a 5–1 lead in shots, yet the score is Vellorin FC 0–1 Tessdal Athletic. | `{clause:dominance}, yet {clause:score}.` |
| M008 | penalty | 70' | llm | 2 | Alvezo Hazulov's penalty was saved at 70', and Vellorin FC have had 62% of the ball since kickoff. | `{event:m-7-dominant_loss#428}, and {clause:possession}.` |

### Run 2 · natural_seed100

| Moment | Type | Minute | Source | Attempts | Published text | Model template |
|---|---|---|---|---:|---|---|
| M001 | red_card | 14' | llm | 1 | Iveno Gundrel was sent off at 14', and Isteven United are down to 10 players on the pitch. | `{event:m-100#84}, and {clause:players}.` |
| M004 | goal | 29' | llm | 1 | Hesko Ilvanto scored at 29', and the score is Tessdal Wanderers 1–0 Isteven United. Tessdal Wanderers have had 58% of the ball since kickoff. | `{event:m-100#175}, and {clause:score}. {clause:possession}.` |
| M005 | goal | 51' | llm | 1 | Quenlo Pelvisto scored at 51', and Isteven United drew level. The score is Tessdal Wanderers 1–1 Isteven United. | `{event:m-100#317}, and {clause:equalizer}. {clause:score}.` |
| M007 | dominance_without_reward | 79' | llm | 1 | Since 59' Tessdal Wanderers have had 61% of the ball and a 4–0 lead in shots, yet the score is Tessdal Wanderers 1–1 Isteven United. | `{clause:dominance}, yet {clause:score}.` |
| M008 | goal | 90+1' | llm | 1 | Brisko Ymberto scored at 90+1', and the score is Tessdal Wanderers 2–1 Isteven United. Tessdal Wanderers have had 52% of the ball since kickoff, while Tessdal Wanderers went ahead. | `{event:m-100#550}, and {clause:score}. {clause:possession}, while {clause:go_ahead}.` |

### Run 3 · red_card_swing_seed42

| Moment | Type | Minute | Source | Attempts | Published text | Model template |
|---|---|---|---|---:|---|---|
| M002 | goal | 22' | llm | 1 | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. The score is Brannoch FC 1–0 Morvane Athletic. | `{event:m-42-red_card_swing#127}, and {clause:possession}. {clause:score}.` |
| M004 | red_card | 38' | llm | 1 | Orvik Belmaro was sent off at 38', and Brannoch FC are down to 10 players on the pitch. | `{event:m-42-red_card_swing#213}, and {clause:players}.` |
| M006 | goal | 61' | llm | 1 | Davel Selvado scored at 61', and Morvane Athletic drew level. The score is Brannoch FC 1–1 Morvane Athletic. | `{event:m-42-red_card_swing#359}, and {clause:equalizer}. {clause:score}.` |
| M007 | pressure_shift | 81' | llm | 1 | Brannoch FC lead the pressure balance over the last 10 minutes of play at +0.83, and Brannoch FC have had 2 shots to Morvane Athletic's 0 since 71'. | `{clause:pressure}, and {clause:shots}.` |
| M008 | goal | 84' | llm | 2 | Murek Ymberto scored at 84', and Morvane Athletic went ahead after being 1 goal down. The score is Brannoch FC 1–2 Morvane Athletic and Morvane Athletic have had 50% of the ball since kickoff. | `{event:m-42-red_card_swing#494}, and {clause:go_ahead}. {clause:score} and {clause:possession}.` |
| M009 | pressure_shift | 90+1' | llm | 1 | Murek Ymberto scored at 84', and Morvane Athletic lead the pressure balance over the last 10 minutes of play at +1.00, and Morvane Athletic have had 1 shot to Brannoch FC's 0 since 80'. | `{event:m-42-red_card_swing#493}, and {clause:pressure}, and {clause:shots}.` |

### Run 3 · dominant_loss_seed7

| Moment | Type | Minute | Source | Attempts | Published text | Model template |
|---|---|---|---|---:|---|---|
| M003 | dominance_without_reward | 45+1' | llm | 1 | Since 25' Vellorin FC have had 58% of the ball and a 4–0 lead in shots, yet the score is Vellorin FC 0–0 Tessdal Athletic. | `{clause:dominance}, yet {clause:score}.` |
| M005 | goal | 57' | llm | 1 | Nolvek Ilvanto scored at 57', and the score is Vellorin FC 0–1 Tessdal Athletic. | `{event:m-7-dominant_loss#350}, and {clause:score}.` |
| M007 | dominance_without_reward | 66' | llm | 1 | Since 46' Vellorin FC have had 71% of the ball and a 5–1 lead in shots, yet the score is Vellorin FC 0–1 Tessdal Athletic. | `{clause:dominance}, yet {clause:score}.` |
| M008 | penalty | 70' | llm | 1 | Alvezo Hazulov's penalty was saved at 70', and Vellorin FC have had 62% of the ball since kickoff. | `{event:m-7-dominant_loss#428}, and {clause:possession}.` |

### Run 3 · natural_seed100

| Moment | Type | Minute | Source | Attempts | Published text | Model template |
|---|---|---|---|---:|---|---|
| M001 | red_card | 14' | llm | 1 | Iveno Gundrel was sent off at 14'. Isteven United are down to 10 players on the pitch, and Isteven United have had 51% of the ball since kickoff. | `{event:m-100#84}. {clause:players}, and {clause:possession}.` |
| M004 | goal | 29' | llm | 1 | Hesko Ilvanto scored at 29', and Tessdal Wanderers opened the scoring. The score is Tessdal Wanderers 1–0 Isteven United. | `{event:m-100#175}, and {clause:opener}. {clause:score}.` |
| M005 | goal | 51' | llm | 1 | Quenlo Pelvisto scored at 51', and Isteven United have had 49% of the ball since kickoff. The score is Tessdal Wanderers 1–1 Isteven United, and Isteven United drew level. | `{event:m-100#317}, and {clause:possession}. {clause:score}, and {clause:equalizer}.` |
| M007 | dominance_without_reward | 79' | llm | 1 | Since 59' Tessdal Wanderers have had 61% of the ball and a 4–0 lead in shots, yet the score is Tessdal Wanderers 1–1 Isteven United. | `{clause:dominance}, yet {clause:score}.` |
| M008 | goal | 90+1' | llm | 1 | Brisko Ymberto scored at 90+1', and Tessdal Wanderers went ahead. Tessdal Wanderers have had 52% of the ball since kickoff, and the score is Tessdal Wanderers 2–1 Isteven United. | `{event:m-100#550}, and {clause:go_ahead}. {clause:possession}, and {clause:score}.` |
