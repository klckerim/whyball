# LLM anlatım ölçümü (gerçek model)

Bu dosya `python -m eval.llm_run` çalıştırmasının ham çıktısından (`docs/LLM_RUN.json`) üretilir; elle düzenlemeyin.

- Model: `gpt-5-mini` · Prompt sürümü: `foundry-v4:gpt-5-mini` · Dil: `en` · Reasoning çabası: `low`
- Çalıştırma: 2026-10-13T11:22:01+00:00 – 2026-10-13T11:30:45+00:00 (UTC)
- Ayarlar: çalıştırma (maç) başına en fazla 60 çağrı, `max_output_tokens` 4000, çağrı zaman aşımı 60 sn, en fazla 2 yeniden deneme, önbellek kapalı
- Her taslak lint + yer tutucu bağlama + verify_claim'den geçti; geçmeyen yayınlanmadı ve template yedeğine düştü. Yayınlanan LLM metinlerinde somut değerleri kod render etti.

## Özet

| Maç | Moment | İlk denemede geçen | Yeniden denemeyle geçen | Yedeğe düşen | Çağrı | Token giriş / çıkış | Reasoning (çıkışın %'si) | Ort. süre | Medyan | Maks. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red_card_swing_seed42 | 9 | 5 (55.6%) | 2 (22.2%) | 2 (22.2%) | 16 | 45402 / 28129 | 19456 (69.2%) | 14.1 sn | 14.0 sn | 19.3 sn |
| dominant_loss_seed7 | 5 | 3 (60.0%) | 0 (0.0%) | 2 (40.0%) | 9 | 25889 / 15543 | 10368 (66.7%) | 14.1 sn | 13.9 sn | 16.1 sn |
| natural_seed100 | 8 | 4 (50.0%) | 4 (50.0%) | 0 (0.0%) | 13 | 35533 / 19926 | 13696 (68.7%) | 13.2 sn | 11.7 sn | 20.8 sn |
| **Toplam** | 22 | 12 (54.5%) | 6 (27.3%) | 4 (18.2%) | 38 | 106824 / 63598 | 43520 (68.4%) | 13.8 sn | 13.5 sn | 20.8 sn |

## Yedeğe düşen momentler

| Maç | Moment | Tip | Dakika | Yedek sebebi | Deneme bazında ret kodları |
|---|---|---|---|---|---|
| red_card_swing_seed42 | M009 | pressure_shift | 81' | `max_retries_exceeded` | #1: `evidence_mismatch`×2; #2: `evidence_mismatch`×2, `invalid_subject`; #3: `raw_entity` |
| red_card_swing_seed42 | M010 | goal | 84' | `max_retries_exceeded` | #1: `evidence_mismatch`; #2: `evidence_mismatch`×2; #3: `evidence_mismatch` |
| dominant_loss_seed7 | M003 | dominance_without_reward | 45+1' | `max_retries_exceeded` | #1: `evidence_mismatch`; #2: `evidence_mismatch`; #3: `evidence_mismatch` |
| dominant_loss_seed7 | M009 | penalty | 70' | `max_retries_exceeded` | #1: `evidence_mismatch`×2; #2: `raw_entity`, `evidence_mismatch`; #3: `evidence_mismatch` |

Yedeğe düşen momentlerde ret kodu sıklığı: `evidence_mismatch`×15, `invalid_subject`, `raw_entity`×2

## Yeniden denemeyle geçen momentler

| Maç | Moment | Tip | Deneme | Reddedilen denemeler |
|---|---|---|---:|---|
| red_card_swing_seed42 | M003 | score_change | 2 | #1: `invalid_subject` |
| red_card_swing_seed42 | M012 | pressure_shift | 3 | #1: `evidence_mismatch`; #2: `evidence_mismatch` |
| natural_seed100 | M007 | score_change | 3 | #1: `invalid_subject`; #2: `invalid_subject` |
| natural_seed100 | M009 | dominance_without_reward | 2 | #1: `raw_entity` |
| natural_seed100 | M010 | goal | 2 | #1: `invalid_subject` |
| natural_seed100 | M011 | score_change | 2 | #1: `invalid_subject` |

## İstemci hataları

Yok.

## Moment ayrıntıları

### red_card_swing_seed42

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M002 | goal | 22' | llm | 1 | Murek Brestani scored at 22', making it 1–0. Brannoch FC have had 55% of the ball since kickoff. | `{event:m-42-red_card_swing#127}, making it {score}. {home} have had {value:c3} of the ball since kickoff.` |
| M003 | score_change | 22' | llm | 2 | Murek Brestani scored at 22', making it 1–0. Possession since kickoff: Brannoch FC have had 55% of the ball. | `{event:m-42-red_card_swing#127}, making it {score}. Possession since kickoff: {home} have had {value:c2} of the ball.` |
| M005 | red_card | 38' | llm | 1 | Orvik Belmaro was sent off at 38'. Brannoch FC have had 54% of the ball since kickoff. | `{event:m-42-red_card_swing#213}. {home} have had {value:c2} of the ball since kickoff.` |
| M007 | goal | 61' | llm | 1 | Davel Selvado scored at 61', making it 1–1. They have had 49% of the ball since kickoff. | `{event:m-42-red_card_swing#359}, making it {score}. They have had {value:c2} of the ball since kickoff.` |
| M008 | score_change | 61' | llm | 1 | Davel Selvado scored at 61', making it Brannoch FC 1–1 Morvane Athletic. Possession since kickoff is 51% for Brannoch FC. | `{event:m-42-red_card_swing#359}, making it {score_named}. Possession since kickoff is {value:c3} for {home}.` |
| M009 | pressure_shift | 81' | template_fallback | 3 | 81' — Brannoch FC take control: pressure balance +0.83 in their favour. Shots since 71': Brannoch FC 2, Morvane Athletic 0. | — |
| M010 | goal | 84' | template_fallback | 3 | 84' — Murek Ymberto scores for Morvane Athletic. Brannoch FC 1–2 Morvane Athletic. | — |
| M011 | score_change | 84' | llm | 1 | Murek Ymberto scored at 84', making it 1–2. They have had 50% of the ball since kickoff. | `{event:m-42-red_card_swing#494}, making it {score}. They have had {value:c2} of the ball since kickoff.` |
| M012 | pressure_shift | 90+1' | llm | 3 | Possession has been 51% for Morvane Athletic since kickoff. The territorial share is 71% and Pernat Dremmet completed a pass at 89'. They have pressure balance of +1.00. | `Possession has been {value:c1} for {away} since kickoff. The territorial share is {value:c2} and {event:m-42-red_card_swing#521}. They have {label:c3} of {value:c3}.` |

### dominant_loss_seed7

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M003 | dominance_without_reward | 45+1' | template_fallback | 3 | 45+1' — Vellorin FC dominate without reward: since 25' they have had 58% of the ball and a 4–0 lead in shots, yet the score is Vellorin FC 0–0 Tessdal Athletic. | — |
| M005 | goal | 57' | llm | 1 | Nolvek Ilvanto scored at 57', making it 0–1. Possession since kickoff: Vellorin FC have had 61% of the ball. | `{event:m-7-dominant_loss#350}, making it {score}. Possession since kickoff: {home} have had {value:c2} of the ball.` |
| M006 | score_change | 57' | llm | 1 | Nolvek Ilvanto scored at 57', making it 0–1. Vellorin FC have had 61% of the ball since kickoff. | `{event:m-7-dominant_loss#350}, making it {score}. {home} have had {value:c2} of the ball since kickoff.` |
| M008 | dominance_without_reward | 66' | llm | 1 | Korin Zerimek had a shot blocked at 66'. They registered 5 shots between 58' and 66', and Vellorin FC have had 62% of the ball since kickoff. | `{event:m-7-dominant_loss#408}. They registered {value:c1} {label:c1} between {start:c1} and {minute:c1}, and {home} have had {value:c2} of the ball since kickoff.` |
| M009 | penalty | 70' | template_fallback | 3 | 70' — Penalty for Vellorin FC, but Alvezo Hazulov sees the kick saved. | — |

### natural_seed100

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M001 | red_card | 14' | llm | 1 | Iveno Gundrel was sent off at 14'. Isteven United have had 51% of the ball since kickoff. | `{event:m-100#84}. {away} have had {value:c2} of the ball since kickoff.` |
| M004 | goal | 29' | llm | 1 | Hesko Ilvanto scored at 29', making it 1–0. At 29' Tessdal Wanderers have had 58% of the ball since kickoff. | `{event:m-100#175}, making it {score}. At {minute:c3} {home} have had {value:c3} of the ball since kickoff.` |
| M005 | score_change | 29' | llm | 1 | Hesko Ilvanto scored at 29', making it 1–0. Possession has been 58% for Tessdal Wanderers since kickoff. | `{event:m-100#175}, making it {score}. Possession has been {value:c2} for {home} since kickoff.` |
| M006 | goal | 51' | llm | 1 | Quenlo Pelvisto scored at 51', making it 1–1. Possession has been 51% for Tessdal Wanderers since kickoff. | `{event:m-100#317}, making it {score}. Possession has been {value:c3} for {home} since kickoff.` |
| M007 | score_change | 51' | llm | 3 | Quenlo Pelvisto scored at 51', making it 1–1. Tessdal Wanderers have had 51% of the ball since kickoff. | `{event:m-100#317}, making it {score}. {home} have had {value:c3} of the ball since kickoff.` |
| M009 | dominance_without_reward | 79' | llm | 2 | Rastin Ymberto shot off target at 79'. The Tessdal Wanderers have had 54% of the ball since kickoff, with pressure balance at +1.00. | `{event:m-100#478}. The {home} have had {value:c2} of the ball since kickoff, with {label:c3} at {value:c3}.` |
| M010 | goal | 90+1' | llm | 2 | Brisko Ymberto scored at 90+1' by Brisko Ymberto, making it 2–1. Possession since kickoff: Tessdal Wanderers have had 52% of the ball. | `{event:m-100#550} by {player:h03}, making it {score}. Possession since kickoff: {home} have had {value:c3} of the ball.` |
| M011 | score_change | 90+1' | llm | 2 | Brisko Ymberto scored at 90+1', making it 2–1. | `{event:m-100#550}, making it {score}.` |
