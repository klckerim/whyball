# LLM anlatım ölçümü (gerçek model)

Bu dosya `python -m eval.llm_run` çalıştırmasının ham çıktısından (`docs/LLM_RUN.json`) üretilir; elle düzenlemeyin.

- Model: `gpt-5-mini` · Prompt sürümü: `foundry-v3:gpt-5-mini` · Dil: `en` · Reasoning çabası: `low`
- Çalıştırma: 2026-10-12T19:45:26+00:00 – 2026-10-12T19:53:09+00:00 (UTC)
- Ayarlar: çalıştırma (maç) başına en fazla 60 çağrı, `max_output_tokens` 4000, çağrı zaman aşımı 60 sn, en fazla 2 yeniden deneme, önbellek kapalı
- Her taslak lint + yer tutucu bağlama + verify_claim'den geçti; geçmeyen yayınlanmadı ve template yedeğine düştü. Yayınlanan LLM metinlerinde somut değerleri kod render etti.

## Özet

| Maç | Moment | İlk denemede geçen | Yeniden denemeyle geçen | Yedeğe düşen | Çağrı | Token giriş / çıkış | Reasoning (çıkışın %'si) | Ort. süre | Medyan | Maks. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red_card_swing_seed42 | 9 | 6 (66.7%) | 2 (22.2%) | 1 (11.1%) | 14 | 33484 / 21711 | 14016 (64.6%) | 12.4 sn | 12.3 sn | 16.3 sn |
| dominant_loss_seed7 | 5 | 1 (20.0%) | 3 (60.0%) | 1 (20.0%) | 11 | 27563 / 18336 | 11712 (63.9%) | 13.7 sn | 14.4 sn | 18.9 sn |
| natural_seed100 | 8 | 5 (62.5%) | 3 (37.5%) | 0 (0.0%) | 12 | 28452 / 16837 | 10688 (63.5%) | 11.5 sn | 11.1 sn | 17.0 sn |
| **Toplam** | 22 | 12 (54.5%) | 8 (36.4%) | 2 (9.1%) | 37 | 89499 / 56884 | 36416 (64.0%) | 12.5 sn | 12.4 sn | 18.9 sn |

## Yedeğe düşen momentler

| Maç | Moment | Tip | Dakika | Yedek sebebi | Deneme bazında ret kodları |
|---|---|---|---|---|---|
| red_card_swing_seed42 | M012 | pressure_shift | 90+1' | `max_retries_exceeded` | #1: `evidence_mismatch`; #2: `evidence_mismatch`; #3: `evidence_mismatch` |
| dominant_loss_seed7 | M003 | dominance_without_reward | 45+1' | `max_retries_exceeded` | #1: `raw_number`; #2: `unknown_placeholder`, `evidence_mismatch`; #3: `evidence_mismatch` |

Yedeğe düşen momentlerde ret kodu sıklığı: `evidence_mismatch`×5, `raw_number`, `unknown_placeholder`

## Yeniden denemeyle geçen momentler

| Maç | Moment | Tip | Deneme | Reddedilen denemeler |
|---|---|---|---:|---|
| red_card_swing_seed42 | M008 | score_change | 2 | #1: `invalid_subject` |
| red_card_swing_seed42 | M010 | goal | 3 | #1: `evidence_mismatch`, `missing_evidence`; #2: `evidence_mismatch` |
| dominant_loss_seed7 | M005 | goal | 2 | #1: `evidence_mismatch` |
| dominant_loss_seed7 | M008 | dominance_without_reward | 3 | #1: `evidence_mismatch`; #2: `evidence_mismatch`, `invalid_subject` |
| dominant_loss_seed7 | M009 | penalty | 2 | #1: `unbound_placeholder` |
| natural_seed100 | M001 | red_card | 2 | #1: `invalid_subject` |
| natural_seed100 | M005 | score_change | 2 | #1: `missing_evidence` |
| natural_seed100 | M009 | dominance_without_reward | 3 | #1: `evidence_mismatch`×2; #2: `raw_number`, `evidence_mismatch`×2 |

## İstemci hataları

Yok.

## Moment ayrıntıları

### red_card_swing_seed42

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M002 | goal | 22' | llm | 1 | Murek Brestani scored at 22', making it Brannoch FC 1–0 Morvane Athletic. Brannoch FC have had 55% of the ball since kickoff. | `{player:h09} scored at {minute:c1}, making it {score}. {home} have had {value:c3} of the ball since kickoff.` |
| M003 | score_change | 22' | llm | 1 | Murek Brestani scored for Brannoch FC at 22', making it Brannoch FC 1–0 Morvane Athletic. Brannoch FC have had 55% of the ball and show a +0.33 pressure balance. | `{player:h09} scored for {home} at {minute:c1}, making it {score}. {home} have had {value:c4} of the ball and show a {value:c5} {label:c5}.` |
| M005 | red_card | 38' | llm | 1 | Orvik Belmaro was sent off at 38', leaving Brannoch FC with Brannoch FC 1–0 Morvane Athletic. Morvane Athletic have had 46% of the ball since kickoff. | `{player:h08} was sent off at {minute:c1}, leaving {home} with {score}. {away} have had {value:c2} of the ball since kickoff.` |
| M007 | goal | 61' | llm | 1 | Davel Selvado scored at 61', making it Brannoch FC 1–1 Morvane Athletic. Brannoch FC have had 51% of the ball while Morvane Athletic lead the pressure balance at +1.00. | `{player:a06} scored at {minute:c1}, making it {score}. {home} have had {value:c2} of the ball while {away} lead the pressure balance at {value:c3}.` |
| M008 | score_change | 61' | llm | 2 | Davel Selvado scored for Morvane Athletic at 61', making it Brannoch FC 1–1 Morvane Athletic. Morvane Athletic have had 49% of the ball since kickoff. | `{player:a06} scored for {away} at {minute:c1}, making it {score}. {away} have had {value:c2} of the ball since kickoff.` |
| M009 | pressure_shift | 81' | llm | 1 | Murek Brestani had 2 shots for Brannoch FC at 80', and Brannoch FC had 50% of the ball; the score was Brannoch FC 1–1 Morvane Athletic. | `{player:h09} had {value:c2} {label:c2} for {home} at {minute:c2}, and {home} had {value:c4} of the ball; the score was {score}.` |
| M010 | goal | 84' | llm | 3 | Murek Ymberto scored for Morvane Athletic at 84', making it Brannoch FC 1–2 Morvane Athletic. | `{player:a11} scored for {away} at {minute:c1}, making it {score}.` |
| M011 | score_change | 84' | llm | 1 | Murek Ymberto scored for Morvane Athletic at 84', making it Brannoch FC 1–2 Morvane Athletic. | `{player:a11} scored for {away} at {minute:c1}, making it {score}.` |
| M012 | pressure_shift | 90+1' | template_fallback | 3 | 90+1' — Morvane Athletic take control: pressure balance +1.00 in their favour. Shots since 80': Morvane Athletic 1, Brannoch FC 0. | — |

### dominant_loss_seed7

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M003 | dominance_without_reward | 45+1' | template_fallback | 3 | 45+1' — Vellorin FC dominate without reward: 58% of possession and 4–0 shots since 25', yet the score is Vellorin FC 0–0 Tessdal Athletic. | — |
| M005 | goal | 57' | llm | 2 | Nolvek Ilvanto scored at 57', making it Vellorin FC 0–1 Tessdal Athletic. | `{player:a08} scored at {minute:c1}, making it {score}.` |
| M006 | score_change | 57' | llm | 1 | Nolvek Ilvanto scored for Tessdal Athletic at 57', making it Vellorin FC 0–1 Tessdal Athletic. Vellorin FC have had 61% of the ball and pressure balance is +1.00 for Tessdal Athletic. | `{player:a08} scored for {away} at {minute:c1}, making it {score}. {home} have had {value:c4} of the ball and {label:c5} is {value:c5} for {away}.` |
| M008 | dominance_without_reward | 66' | llm | 3 | Alvezo Hazulov registered 2 of the shots between 58' and 66'. Vellorin FC have had 62% of the ball and remain behind at Vellorin FC 0–1 Tessdal Athletic. | `{player:h02} registered {value:c1} of the shots between {start:c1} and {minute:c1}. {home} have had {value:c2} of the ball and remain behind at {score}.` |
| M009 | penalty | 70' | llm | 2 | Alvezo Hazulov saved a penalty at 70', keeping the score Vellorin FC 0–1 Tessdal Athletic. Vellorin FC have had 62% of the ball since kickoff. | `{player:h02} saved a penalty at {minute:c1}, keeping the score {score}. {home} have had {value:c3} of the ball since kickoff.` |

### natural_seed100

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M001 | red_card | 14' | llm | 2 | Iveno Gundrel was shown a red card at 14', leaving the match at Tessdal Wanderers 0–0 Isteven United. Isteven United have had 51% of the ball up to that point. | `{player:a08} was shown a red card at {minute:c1}, leaving the match at {score}. {away} have had {value:c3} of the ball up to that point.` |
| M004 | goal | 29' | llm | 1 | Hesko Ilvanto scored for Tessdal Wanderers at 29', making it Tessdal Wanderers 1–0 Isteven United. | `{player:h02} scored for {home} at {minute:c1}, making it {score}.` |
| M005 | score_change | 29' | llm | 2 | Hesko Ilvanto scored at 29', putting Tessdal Wanderers in front as Tessdal Wanderers 1–0 Isteven United. Tessdal Wanderers have had 58% of the ball since kick-off. | `{player:h02} scored at {minute:c1}, putting {home} in front as {score}. {home} have had {value:c2} of the ball since kick-off.` |
| M006 | goal | 51' | llm | 1 | Quenlo Pelvisto levelled the match at 51', making it Tessdal Wanderers 1–1 Isteven United. | `{player:a07} levelled the match at {minute:c1}, making it {score}.` |
| M007 | score_change | 51' | llm | 1 | Quenlo Pelvisto scored for Isteven United at 51', making it Tessdal Wanderers 1–1 Isteven United. Isteven United have had 49% of the ball since kickoff and show a pressure balance of +0.07. | `{player:a07} scored for {away} at {minute:c1}, making it {score}. {away} have had {value:c3} of the ball since kickoff and show a {label:c4} of {value:c4}.` |
| M009 | dominance_without_reward | 79' | llm | 3 | Rastin Ymberto took a shot off target at 79', leaving it Tessdal Wanderers 1–1 Isteven United. Tessdal Wanderers have had 54% of the ball since kickoff. | `{player:h07} took a shot off target at {minute:c1}, leaving it {score}. {home} have had {value:c2} of the ball since kickoff.` |
| M010 | goal | 90+1' | llm | 1 | Brisko Ymberto scored deep into stoppage, making it Tessdal Wanderers 2–1 Isteven United at 90+1'. Tessdal Wanderers have had 52% of the ball. | `{player:h03} scored deep into stoppage, making it {score} at {minute:c3}. {home} have had {value:c2} of the ball.` |
| M011 | score_change | 90+1' | llm | 1 | Brisko Ymberto scored for Tessdal Wanderers at 90+1', making it Tessdal Wanderers 2–1 Isteven United. Tessdal Wanderers have had 52% of the ball up to that point. | `{player:h03} scored for {home} at {minute:c1}, making it {score}. {home} have had {value:c3} of the ball up to that point.` |
