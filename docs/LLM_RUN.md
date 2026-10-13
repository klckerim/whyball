# LLM anlatım ölçümü (gerçek model)

Bu dosya `python -m eval.llm_run` çalıştırmasının ham çıktısından (`docs/LLM_RUN.json`) üretilir; elle düzenlemeyin.

- Model: `gpt-5-mini` · Prompt sürümü: `foundry-v5:gpt-5-mini` · Dil: `en` · Reasoning çabası: `low`
- Çalıştırma: 2026-10-13T13:16:54+00:00 – 2026-10-13T13:22:31+00:00 (UTC), 3 koşu (aynı prompt)
- Ayarlar: çalıştırma (maç) başına en fazla 60 çağrı, `max_output_tokens` 4000, çağrı zaman aşımı 60 sn, en fazla 2 yeniden deneme, önbellek kapalı
- Her taslak lint + yer tutucu bağlama + verify_claim'den geçti; geçmeyen yayınlanmadı ve template yedeğine düştü. Yayınlanan LLM metinlerinde somut değerleri kod render etti.

## Özet

### Koşu 1 (2026-10-13T13:16:54+00:00 – 2026-10-13T13:18:46+00:00)

| Maç | Moment | İlk denemede geçen | Yeniden denemeyle geçen | Yedeğe düşen | Çağrı | Token giriş / çıkış | Reasoning (çıkışın %'si) | Ort. süre | Medyan | Maks. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red_card_swing_seed42 | 9 | 9 (100.0%) | 0 (0.0%) | 0 (0.0%) | 9 | 19995 / 3338 | 2688 (80.5%) | 4.9 sn | 5.3 sn | 7.2 sn |
| dominant_loss_seed7 | 5 | 5 (100.0%) | 0 (0.0%) | 0 (0.0%) | 5 | 11446 / 1820 | 1536 (84.4%) | 4.6 sn | 4.9 sn | 6.1 sn |
| natural_seed100 | 8 | 8 (100.0%) | 0 (0.0%) | 0 (0.0%) | 8 | 17207 / 3715 | 3264 (87.9%) | 5.5 sn | 5.3 sn | 8.0 sn |
| **Toplam** | 22 | 22 (100.0%) | 0 (0.0%) | 0 (0.0%) | 22 | 48648 / 8873 | 7488 (84.4%) | 5.1 sn | 5.0 sn | 8.0 sn |

### Koşu 2 (2026-10-13T13:18:46+00:00 – 2026-10-13T13:20:41+00:00)

| Maç | Moment | İlk denemede geçen | Yeniden denemeyle geçen | Yedeğe düşen | Çağrı | Token giriş / çıkış | Reasoning (çıkışın %'si) | Ort. süre | Medyan | Maks. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red_card_swing_seed42 | 9 | 9 (100.0%) | 0 (0.0%) | 0 (0.0%) | 9 | 19995 / 3424 | 2752 (80.4%) | 5.1 sn | 5.5 sn | 6.0 sn |
| dominant_loss_seed7 | 5 | 5 (100.0%) | 0 (0.0%) | 0 (0.0%) | 5 | 11446 / 2198 | 1856 (84.4%) | 5.1 sn | 5.6 sn | 6.7 sn |
| natural_seed100 | 8 | 8 (100.0%) | 0 (0.0%) | 0 (0.0%) | 8 | 17207 / 3822 | 3328 (87.1%) | 5.5 sn | 5.6 sn | 6.7 sn |
| **Toplam** | 22 | 22 (100.0%) | 0 (0.0%) | 0 (0.0%) | 22 | 48648 / 9444 | 7936 (84.0%) | 5.2 sn | 5.6 sn | 6.7 sn |

### Koşu 3 (2026-10-13T13:20:41+00:00 – 2026-10-13T13:22:31+00:00)

| Maç | Moment | İlk denemede geçen | Yeniden denemeyle geçen | Yedeğe düşen | Çağrı | Token giriş / çıkış | Reasoning (çıkışın %'si) | Ort. süre | Medyan | Maks. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red_card_swing_seed42 | 9 | 9 (100.0%) | 0 (0.0%) | 0 (0.0%) | 9 | 19995 / 3339 | 2816 (84.3%) | 4.6 sn | 4.5 sn | 6.2 sn |
| dominant_loss_seed7 | 5 | 4 (80.0%) | 1 (20.0%) | 0 (0.0%) | 6 | 13502 / 2536 | 2112 (83.3%) | 5.0 sn | 5.0 sn | 5.5 sn |
| natural_seed100 | 8 | 8 (100.0%) | 0 (0.0%) | 0 (0.0%) | 8 | 17207 / 3092 | 2560 (82.8%) | 4.7 sn | 4.9 sn | 7.3 sn |
| **Toplam** | 22 | 21 (95.5%) | 1 (4.5%) | 0 (0.0%) | 23 | 50704 / 8967 | 7488 (83.5%) | 4.7 sn | 4.7 sn | 7.3 sn |

### Koşu başına yedeğe düşen

| Koşu | Moment | Yedeğe düşen | Reddedilen deneme | evidence_mismatch |
|---|---:|---:|---:|---:|
| 1 | 22 | 0 | 0 | 0 |
| 2 | 22 | 0 | 0 | 0 |
| 3 | 22 | 0 | 1 | 0 |
| **Toplam** | 66 | 0 | 1 | 0 |

## Sürüm karşılaştırması: foundry-v3, foundry-v4, foundry-v4.1, foundry-v5

Önceki sürümler arşivlenen ham çıktılardan (`docs/LLM_RUN.<sürüm>.json`). Ret = yayınlanmayan deneme; `evidence_mismatch` sütunu bu kodu içeren reddedilen deneme sayısı.

| Sürüm / koşu | Moment | İlk denemede | Yeniden denemeyle | Yedeğe düşen | Çağrı | Reddedilen deneme | evidence_mismatch | Token çıkış |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| foundry-v3 | 22 | 12 | 8 | 2 | 37 | 17 | 12 | 56884 |
| foundry-v4 | 22 | 12 | 6 | 4 | 38 | 20 | 13 | 63598 |
| foundry-v4.1 · koşu 1 | 22 | 16 | 3 | 3 | 33 | 14 | 10 | 49588 |
| foundry-v4.1 · koşu 2 | 22 | 14 | 6 | 2 | 35 | 15 | 15 | 51072 |
| foundry-v4.1 · koşu 3 | 22 | 15 | 5 | 2 | 34 | 14 | 11 | 53295 |
| **foundry-v4.1 · toplam (3 koşu)** | 66 | 45 | 14 | 7 | 102 | 43 | 36 | 153955 |
| foundry-v5 · koşu 1 | 22 | 22 | 0 | 0 | 22 | 0 | 0 | 8873 |
| foundry-v5 · koşu 2 | 22 | 22 | 0 | 0 | 22 | 0 | 0 | 9444 |
| foundry-v5 · koşu 3 | 22 | 21 | 1 | 0 | 23 | 1 | 0 | 8967 |
| **foundry-v5 · toplam (3 koşu)** | 66 | 65 | 1 | 0 | 67 | 1 | 0 | 27284 |

`evidence_mismatch` içeren reddedilen denemeler, moment tipine göre (sürümün tüm koşuları; parantezde koşu sayısı):

| Moment tipi | foundry-v3 (1) | foundry-v4 (1) | foundry-v4.1 (3) | foundry-v5 (3) |
|---|---:|---:|---:|---:|
| dominance_without_reward | 6 | 3 | 11 | 0 |
| goal | 3 | 3 | 16 | 0 |
| penalty | 0 | 3 | 0 | 0 |
| pressure_shift | 3 | 4 | 9 | 0 |
| red_card | 0 | 0 | 0 | 0 |
| score_change | 0 | 0 | 0 | 0 |

## Ret kodu sıklığı

Reddedilen denemelerdeki kodlar, koşu başına ortalama (bir denemede birden fazla kod olabilir).

| Kod | foundry-v3 (1 koşu) | foundry-v4 (1 koşu) | foundry-v4.1 (3 koşu) | foundry-v5 (3 koşu) |
|---|---:|---:|---:|---:|
| `evidence_mismatch` | 14 | 17 | 13 | 0 |
| `invalid_subject` | 3 | 6 | 2.3 | 0 |
| `article_team` | 0 | 0 | 2.3 | 0.3 |
| `raw_entity` | 0 | 3 | 0.7 | 0 |
| `raw_number` | 2 | 0 | 1 | 0 |
| `missing_evidence` | 2 | 0 | 0 | 0 |
| `unknown_placeholder` | 1 | 0 | 0.3 | 0 |
| `raw_metric_name` | 0 | 0 | 0.3 | 0 |
| `sentence_start` | 0 | 0 | 0.3 | 0 |
| `unbound_placeholder` | 1 | 0 | 0 | 0 |

## Yan yana: aynı momentler, sürüm sürüm

Yayınlanan metin; çok koşulu sürümlerde son koşu. *(yedek)* = template yedeği.

| Moment | Tip | foundry-v3 | foundry-v4 | foundry-v4.1 | foundry-v5 |
|---|---|---|---|---|---|
| red_card_swing M002 | goal | Murek Brestani scored at 22', making it Brannoch FC 1–0 Morvane Athletic. Brannoch FC have had 55% of the ball since kickoff. | Murek Brestani scored at 22', making it 1–0. Brannoch FC have had 55% of the ball since kickoff. | Murek Brestani scored at 22', making it 1–0. Possession: Brannoch FC have had 55% of the ball since kickoff. | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. |
| red_card_swing M003 | score_change | Murek Brestani scored for Brannoch FC at 22', making it Brannoch FC 1–0 Morvane Athletic. Brannoch FC have had 55% of the ball and show a +0.33 pressure balance. | Murek Brestani scored at 22', making it 1–0. Possession since kickoff: Brannoch FC have had 55% of the ball. | Murek Brestani scored at 22', making it 1–0. Brannoch FC have had 55% of the ball since kickoff. | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. |
| red_card_swing M005 | red_card | Orvik Belmaro was sent off at 38', leaving Brannoch FC with Brannoch FC 1–0 Morvane Athletic. Morvane Athletic have had 46% of the ball since kickoff. | Orvik Belmaro was sent off at 38'. Brannoch FC have had 54% of the ball since kickoff. | Orvik Belmaro was sent off at 38'. Possession for Brannoch FC since kickoff is 54%, red cards for Brannoch FC is 1 and at 38' the goal margin for Brannoch FC is 1. | Orvik Belmaro was sent off at 38', and Brannoch FC are down to 10 players on the pitch. |
| red_card_swing M007 | goal | Davel Selvado scored at 61', making it Brannoch FC 1–1 Morvane Athletic. Brannoch FC have had 51% of the ball while Morvane Athletic lead the pressure balance at +1.00. | Davel Selvado scored at 61', making it 1–1. They have had 49% of the ball since kickoff. | Davel Selvado scored at 61', making it 1–1. Morvane Athletic have had 71% of the territorial share since kickoff. | Davel Selvado scored at 61', and the score is Brannoch FC 1–1 Morvane Athletic. |
| red_card_swing M008 | score_change | Davel Selvado scored for Morvane Athletic at 61', making it Brannoch FC 1–1 Morvane Athletic. Morvane Athletic have had 49% of the ball since kickoff. | Davel Selvado scored at 61', making it Brannoch FC 1–1 Morvane Athletic. Possession since kickoff is 51% for Brannoch FC. | Davel Selvado scored at 61', making it 1–1. Possession since kickoff has been 49% for Morvane Athletic. The pressure balance over the last 10 minutes of play for Morvane Athletic is +1.00. | Davel Selvado scored at 61', and the score is Brannoch FC 1–1 Morvane Athletic. |
| red_card_swing M009 | pressure_shift | Murek Brestani had 2 shots for Brannoch FC at 80', and Brannoch FC had 50% of the ball; the score was Brannoch FC 1–1 Morvane Athletic. | *(yedek)* 81' — Brannoch FC take control: pressure balance +0.83 in their favour. Shots since 71': Brannoch FC 2, Morvane Athletic 0. | At Murek Brestani had a shot saved at 79', Brannoch FC have had 50% possession since kickoff. The pressure balance over the last 10 minutes of play for Brannoch FC is +0.83. | Brannoch FC lead the pressure balance over the last 10 minutes of play at +0.83, and Brannoch FC have had 2 shots to Morvane Athletic's 0 since 71'. |
| red_card_swing M010 | goal | Murek Ymberto scored for Morvane Athletic at 84', making it Brannoch FC 1–2 Morvane Athletic. | *(yedek)* 84' — Murek Ymberto scores for Morvane Athletic. Brannoch FC 1–2 Morvane Athletic. | Murek Ymberto scored at 84', making it 1–2. Morvane Athletic have had 69% of the territorial share since kickoff. | Murek Ymberto scored at 84', and the score is Brannoch FC 1–2 Morvane Athletic. Morvane Athletic have had 50% of the ball since kickoff. |
| red_card_swing M011 | score_change | Murek Ymberto scored for Morvane Athletic at 84', making it Brannoch FC 1–2 Morvane Athletic. | Murek Ymberto scored at 84', making it 1–2. They have had 50% of the ball since kickoff. | Murek Ymberto scored at 84', making it 1–2. Morvane Athletic have had 50% of the ball since kickoff. | Murek Ymberto scored at 84', and Morvane Athletic have had 50% of the ball since kickoff. |
| red_card_swing M012 | pressure_shift | *(yedek)* 90+1' — Morvane Athletic take control: pressure balance +1.00 in their favour. Shots since 80': Morvane Athletic 1, Brannoch FC 0. | Possession has been 51% for Morvane Athletic since kickoff. The territorial share is 71% and Pernat Dremmet completed a pass at 89'. They have pressure balance of +1.00. | *(yedek)* 90+1' — Morvane Athletic take control: pressure balance over the last 10 minutes of play is +1.00 in their favour. Shots since 80': Morvane Athletic 1, Brannoch FC 0. | Murek Ymberto scored at 84', and Morvane Athletic lead the pressure balance over the last 10 minutes of play at +1.00. |
| dominant_loss M003 | dominance_without_reward | *(yedek)* 45+1' — Vellorin FC dominate without reward: 58% of possession and 4–0 shots since 25', yet the score is Vellorin FC 0–0 Tessdal Athletic. | *(yedek)* 45+1' — Vellorin FC dominate without reward: since 25' they have had 58% of the ball and a 4–0 lead in shots, yet the score is Vellorin FC 0–0 Tessdal Athletic. | Ombar Belmaro shot off target at 45+1'. Possession Vellorin FC have had 61% of the ball since kickoff. | Since 25' Vellorin FC have had 58% of the ball and a 4–0 lead in shots. The score is Vellorin FC 0–0 Tessdal Athletic. |
| dominant_loss M005 | goal | Nolvek Ilvanto scored at 57', making it Vellorin FC 0–1 Tessdal Athletic. | Nolvek Ilvanto scored at 57', making it 0–1. Possession since kickoff: Vellorin FC have had 61% of the ball. | Nolvek Ilvanto scored at 57', making it Vellorin FC 0–1 Tessdal Athletic. Possession: Vellorin FC have had 61% of the ball since kickoff. | Nolvek Ilvanto scored at 57', and Tessdal Athletic have had 39% of the ball since kickoff. The score is Vellorin FC 0–1 Tessdal Athletic. |
| dominant_loss M006 | score_change | Nolvek Ilvanto scored for Tessdal Athletic at 57', making it Vellorin FC 0–1 Tessdal Athletic. Vellorin FC have had 61% of the ball and pressure balance is +1.00 for Tessdal Athletic. | Nolvek Ilvanto scored at 57', making it 0–1. Vellorin FC have had 61% of the ball since kickoff. | Nolvek Ilvanto scored at 57', making it 0–1. Possession: Vellorin FC have had 61% of the ball since kickoff. | Nolvek Ilvanto scored at 57', and Tessdal Athletic have had 39% of the ball since kickoff. |
| dominant_loss M008 | dominance_without_reward | Alvezo Hazulov registered 2 of the shots between 58' and 66'. Vellorin FC have had 62% of the ball and remain behind at Vellorin FC 0–1 Tessdal Athletic. | Korin Zerimek had a shot blocked at 66'. They registered 5 shots between 58' and 66', and Vellorin FC have had 62% of the ball since kickoff. | Korin Zerimek had a shot blocked at 66'. At 66', Vellorin FC have had 62% of the ball since kickoff and the score is 0–1. | Since 46' Vellorin FC have had 71% of the ball and a 5–1 lead in shots, yet the score is Vellorin FC 0–1 Tessdal Athletic. |
| dominant_loss M009 | penalty | Alvezo Hazulov saved a penalty at 70', keeping the score Vellorin FC 0–1 Tessdal Athletic. Vellorin FC have had 62% of the ball since kickoff. | *(yedek)* 70' — Penalty for Vellorin FC, but Alvezo Hazulov sees the kick saved. | Alvezo Hazulov's penalty was saved at 70'. Possession since kickoff has been 62% for Vellorin FC, and Vellorin FC have 1 penalties saved. | Alvezo Hazulov's penalty was saved at 70', and Vellorin FC have had 62% of the ball since kickoff. |
| natural M001 | red_card | Iveno Gundrel was shown a red card at 14', leaving the match at Tessdal Wanderers 0–0 Isteven United. Isteven United have had 51% of the ball up to that point. | Iveno Gundrel was sent off at 14'. Isteven United have had 51% of the ball since kickoff. | Iveno Gundrel was sent off at 14'. Isteven United have had 51% possession since kickoff and the match is 0–0. | Iveno Gundrel was sent off at 14'. Isteven United are down to 10 players on the pitch, and Isteven United have had 51% of the ball since kickoff. |
| natural M004 | goal | Hesko Ilvanto scored for Tessdal Wanderers at 29', making it Tessdal Wanderers 1–0 Isteven United. | Hesko Ilvanto scored at 29', making it 1–0. At 29' Tessdal Wanderers have had 58% of the ball since kickoff. | Hesko Ilvanto scored at 29', making it 1–0. Possession: Tessdal Wanderers have had 58% of the ball since kickoff. | Hesko Ilvanto scored at 29', and Tessdal Wanderers have had 58% of the ball since kickoff. |
| natural M005 | score_change | Hesko Ilvanto scored at 29', putting Tessdal Wanderers in front as Tessdal Wanderers 1–0 Isteven United. Tessdal Wanderers have had 58% of the ball since kick-off. | Hesko Ilvanto scored at 29', making it 1–0. Possession has been 58% for Tessdal Wanderers since kickoff. | Hesko Ilvanto scored at 29', making it 1–0. Tessdal Wanderers have had 58% of the ball since kickoff. | Hesko Ilvanto scored at 29', and Tessdal Wanderers have had 58% of the ball since kickoff. |
| natural M006 | goal | Quenlo Pelvisto levelled the match at 51', making it Tessdal Wanderers 1–1 Isteven United. | Quenlo Pelvisto scored at 51', making it 1–1. Possession has been 51% for Tessdal Wanderers since kickoff. | Quenlo Pelvisto scored at 51', making it 1–1. Possession for Isteven United since kickoff is 49%. | Quenlo Pelvisto scored at 51', and the score is Tessdal Wanderers 1–1 Isteven United. |
| natural M007 | score_change | Quenlo Pelvisto scored for Isteven United at 51', making it Tessdal Wanderers 1–1 Isteven United. Isteven United have had 49% of the ball since kickoff and show a pressure balance of +0.07. | Quenlo Pelvisto scored at 51', making it 1–1. Tessdal Wanderers have had 51% of the ball since kickoff. | Quenlo Pelvisto scored at 51', making it 1–1. Possession has been 51% for Tessdal Wanderers since kickoff. | Quenlo Pelvisto scored at 51', and the score is Tessdal Wanderers 1–1 Isteven United. |
| natural M009 | dominance_without_reward | Rastin Ymberto took a shot off target at 79', leaving it Tessdal Wanderers 1–1 Isteven United. Tessdal Wanderers have had 54% of the ball since kickoff. | Rastin Ymberto shot off target at 79'. The Tessdal Wanderers have had 54% of the ball since kickoff, with pressure balance at +1.00. | At 79' Rastin Ymberto shot off target at 79'. Possession Tessdal Wanderers have had 54% of the ball since kickoff. | Rastin Ymberto shot off target at 79', and since 59' Tessdal Wanderers have had 61% of the ball and a 4–0 lead in shots. |
| natural M010 | goal | Brisko Ymberto scored deep into stoppage, making it Tessdal Wanderers 2–1 Isteven United at 90+1'. Tessdal Wanderers have had 52% of the ball. | Brisko Ymberto scored at 90+1' by Brisko Ymberto, making it 2–1. Possession since kickoff: Tessdal Wanderers have had 52% of the ball. | *(yedek)* 90+1' — Brisko Ymberto scores for Tessdal Wanderers. Tessdal Wanderers 2–1 Isteven United. | Brisko Ymberto scored at 90+1', and Tessdal Wanderers have had 52% of the ball since kickoff. The score is Tessdal Wanderers 2–1 Isteven United. |
| natural M011 | score_change | Brisko Ymberto scored for Tessdal Wanderers at 90+1', making it Tessdal Wanderers 2–1 Isteven United. Tessdal Wanderers have had 52% of the ball up to that point. | Brisko Ymberto scored at 90+1', making it 2–1. | Brisko Ymberto scored at 90+1', making it 2–1. Tessdal Wanderers have had 52% of the ball since kickoff. | Brisko Ymberto scored at 90+1'. The score is Tessdal Wanderers 2–1 Isteven United, and Tessdal Wanderers have had 52% of the ball since kickoff. |

## evidence_mismatch: bağlanan ve sayılan olaylar

Bu ölçümde `evidence_mismatch` reddi yok (foundry-v5: iddiaları ve kanıtlarını kod kurar, model olay bağlamaz). Önceki sürümlerin dökümü arşivlenen JSON'lardan yeniden render edilebilir.

## foundry-v4.1 / v5 kurallarının canlı tetiklenmesi

Yalnız bu kural = denemenin tek ret nedeni bu kuraldı (başka lint ya da verify hatası yok): kural olmasa yayınlanacaktı. Kuralın hedeflediği kalıpsa doğru ret, değilse yanlış alarm; taslaklar aşağıda.

| Kural | Tetiklenen deneme | Yalnız bu kural | Parçalar |
|---|---:|---:|---|
| `event_type_not_allowed` | 0 | 0 | — |
| `player_repeat` | 0 | 0 | — |
| `article_team` | 1 | 1 | `The {clause:score}`×1 |
| `sentence_start` | 0 | 0 | — |
| `unknown_claim_id` | 0 | 0 | — |
| `sentence_without_claim` | 0 | 0 | — |
| `missing_primary_claim` | 0 | 0 | — |
| `minute_repeat` | 0 | 0 | — |

Yalnız yeni kural yüzünden reddedilen taslaklar:

- `article_team`: `{event:m-7-dominant_loss#428}, and {clause:possession}. The {clause:score}.`

## Yedeğe düşen momentler

Yok.

## Yeniden denemeyle geçen momentler

| Koşu | Maç | Moment | Tip | Deneme | Reddedilen denemeler |
|---|---|---|---|---:|---|
| 3 | dominant_loss_seed7 | M009 | penalty | 2 | #1: `article_team` |

## Reddedilen taslaklar

| Koşu | Maç | Moment | Tip | Deneme | Ret kodları | Model şablonu | Ret mesajı |
|---|---|---|---|---:|---|---|---|
| 3 | dominant_loss_seed7 | M009 | penalty | 1 | `article_team` | `{event:m-7-dominant_loss#428}, and {clause:possession}. The {clause:score}.` | lint article_team 'The {clause:score}' |

## İstemci hataları

Yok.

## Moment ayrıntıları

### Koşu 1 · red_card_swing_seed42

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M002 | goal | 22' | llm | 1 | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. | `{event:m-42-red_card_swing#127}, and {clause:possession}.` |
| M003 | score_change | 22' | llm | 1 | Murek Brestani scored at 22'. Brannoch FC lead by 1, and Brannoch FC have had 55% of the ball since kickoff. | `{event:m-42-red_card_swing#127}. {clause:margin}, and {clause:possession}.` |
| M005 | red_card | 38' | llm | 1 | Orvik Belmaro was sent off at 38', and Brannoch FC are down to 10 players on the pitch. | `{event:m-42-red_card_swing#213}, and {clause:players}.` |
| M007 | goal | 61' | llm | 1 | Davel Selvado scored at 61', and Morvane Athletic have had 49% of the ball since kickoff. | `{event:m-42-red_card_swing#359}, and {clause:possession}.` |
| M008 | score_change | 61' | llm | 1 | Davel Selvado scored at 61'. The score is Brannoch FC 1–1 Morvane Athletic, and Morvane Athletic have had 49% of the ball since kickoff. | `{event:m-42-red_card_swing#359}. {clause:score}, and {clause:possession}.` |
| M009 | pressure_shift | 81' | llm | 1 | Brannoch FC lead the pressure balance over the last 10 minutes of play at +0.83. Murek Brestani had a shot saved at 79', and Brannoch FC have had 2 shots to Morvane Athletic's 0 since 71'. | `{clause:pressure}. {event:m-42-red_card_swing#464}, and {clause:shots}.` |
| M010 | goal | 84' | llm | 1 | Murek Ymberto scored at 84', and Morvane Athletic have had 50% of the ball since kickoff. | `{event:m-42-red_card_swing#494}, and {clause:possession}.` |
| M011 | score_change | 84' | llm | 1 | Murek Ymberto scored at 84', and the score is Brannoch FC 1–2 Morvane Athletic. | `{event:m-42-red_card_swing#494}, and {clause:score}.` |
| M012 | pressure_shift | 90+1' | llm | 1 | Murek Ymberto scored at 84', and Morvane Athletic lead the pressure balance over the last 10 minutes of play at +1.00. The score is Brannoch FC 1–2 Morvane Athletic. | `{event:m-42-red_card_swing#493}, and {clause:pressure}. {clause:score}.` |

### Koşu 1 · dominant_loss_seed7

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M003 | dominance_without_reward | 45+1' | llm | 1 | Since 25' Vellorin FC have had 58% of the ball and a 4–0 lead in shots. Ombar Belmaro shot off target at 45+1', and the score is Vellorin FC 0–0 Tessdal Athletic. | `{clause:dominance}. {event:m-7-dominant_loss#269}, and {clause:score}.` |
| M005 | goal | 57' | llm | 1 | Nolvek Ilvanto scored at 57', and Tessdal Athletic have had 39% of the ball since kickoff. | `{event:m-7-dominant_loss#350}, and {clause:possession}.` |
| M006 | score_change | 57' | llm | 1 | Nolvek Ilvanto scored at 57', and Tessdal Athletic have had 39% of the ball since kickoff. | `{event:m-7-dominant_loss#350}, and {clause:possession}.` |
| M008 | dominance_without_reward | 66' | llm | 1 | Since 46' Vellorin FC have had 71% of the ball and a 5–1 lead in shots, yet the score is Vellorin FC 0–1 Tessdal Athletic. | `{clause:dominance}, yet {clause:score}.` |
| M009 | penalty | 70' | llm | 1 | Alvezo Hazulov's penalty was saved at 70', and Vellorin FC have had 62% of the ball since kickoff. | `{event:m-7-dominant_loss#428}, and {clause:possession}.` |

### Koşu 1 · natural_seed100

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M001 | red_card | 14' | llm | 1 | Iveno Gundrel was sent off at 14', and Iveno Gundrel of Isteven United was sent off. | `{event:m-100#84}, and {clause:sent_off}.` |
| M004 | goal | 29' | llm | 1 | Hesko Ilvanto scored at 29', and Tessdal Wanderers have had 58% of the ball since kickoff. | `{event:m-100#175}, and {clause:possession}.` |
| M005 | score_change | 29' | llm | 1 | Hesko Ilvanto scored at 29', and Tessdal Wanderers have had 58% of the ball since kickoff. | `{event:m-100#175}, and {clause:possession}.` |
| M006 | goal | 51' | llm | 1 | Quenlo Pelvisto scored at 51', and the score is Tessdal Wanderers 1–1 Isteven United. | `{event:m-100#317}, and {clause:score}.` |
| M007 | score_change | 51' | llm | 1 | Quenlo Pelvisto scored at 51', and the sides are level. Isteven United have had 49% of the ball since kickoff. | `{event:m-100#317}, and {clause:margin}. {clause:possession}.` |
| M009 | dominance_without_reward | 79' | llm | 1 | Since 59' Tessdal Wanderers have had 61% of the ball and a 4–0 lead in shots. The score is Tessdal Wanderers 1–1 Isteven United. | `{clause:dominance}. {clause:score}.` |
| M010 | goal | 90+1' | llm | 1 | Brisko Ymberto scored at 90+1', and the score is Tessdal Wanderers 2–1 Isteven United. Tessdal Wanderers have had 52% of the ball since kickoff. | `{event:m-100#550}, and {clause:score}. {clause:possession}.` |
| M011 | score_change | 90+1' | llm | 1 | Brisko Ymberto scored at 90+1', and the score is Tessdal Wanderers 2–1 Isteven United. | `{event:m-100#550}, and {clause:score}.` |

### Koşu 2 · red_card_swing_seed42

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M002 | goal | 22' | llm | 1 | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. | `{event:m-42-red_card_swing#127}, and {clause:possession}.` |
| M003 | score_change | 22' | llm | 1 | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. | `{event:m-42-red_card_swing#127}, and {clause:possession}.` |
| M005 | red_card | 38' | llm | 1 | Orvik Belmaro was sent off at 38', and Brannoch FC are down to 10 players on the pitch. | `{event:m-42-red_card_swing#213}, and {clause:players}.` |
| M007 | goal | 61' | llm | 1 | Davel Selvado scored at 61', and Morvane Athletic have had 49% of the ball since kickoff. | `{event:m-42-red_card_swing#359}, and {clause:possession}.` |
| M008 | score_change | 61' | llm | 1 | Davel Selvado scored at 61', and the score is Brannoch FC 1–1 Morvane Athletic. | `{event:m-42-red_card_swing#359}, and {clause:score}.` |
| M009 | pressure_shift | 81' | llm | 1 | Brannoch FC lead the pressure balance over the last 10 minutes of play at +0.83, and Brannoch FC have had 2 shots to Morvane Athletic's 0 since 71'. | `{clause:pressure}, and {clause:shots}.` |
| M010 | goal | 84' | llm | 1 | Murek Ymberto scored at 84', and Morvane Athletic have had 50% of the ball since kickoff. | `{event:m-42-red_card_swing#494}, and {clause:possession}.` |
| M011 | score_change | 84' | llm | 1 | Murek Ymberto scored at 84', and Morvane Athletic have had 50% of the ball since kickoff. | `{event:m-42-red_card_swing#494}, and {clause:possession}.` |
| M012 | pressure_shift | 90+1' | llm | 1 | Morvane Athletic lead the pressure balance over the last 10 minutes of play at +1.00, and the score is Brannoch FC 1–2 Morvane Athletic. | `{clause:pressure}, and {clause:score}.` |

### Koşu 2 · dominant_loss_seed7

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M003 | dominance_without_reward | 45+1' | llm | 1 | Ombar Belmaro shot off target at 45+1', and since 25' Vellorin FC have had 58% of the ball and a 4–0 lead in shots. | `{event:m-7-dominant_loss#269}, and {clause:dominance}.` |
| M005 | goal | 57' | llm | 1 | Nolvek Ilvanto scored at 57', and Tessdal Athletic have had 39% of the ball since kickoff. The score is Vellorin FC 0–1 Tessdal Athletic. | `{event:m-7-dominant_loss#350}, and {clause:possession}. {clause:score}.` |
| M006 | score_change | 57' | llm | 1 | Nolvek Ilvanto scored at 57', and Tessdal Athletic have had 39% of the ball since kickoff. | `{event:m-7-dominant_loss#350}, and {clause:possession}.` |
| M008 | dominance_without_reward | 66' | llm | 1 | Since 46' Vellorin FC have had 71% of the ball and a 5–1 lead in shots, but the score is Vellorin FC 0–1 Tessdal Athletic. Orvik Hazulov had a shot saved at 64'. | `{clause:dominance}, but {clause:score}. {event:m-7-dominant_loss#396}.` |
| M009 | penalty | 70' | llm | 1 | Alvezo Hazulov's penalty was saved at 70', and Vellorin FC have had 62% of the ball since kickoff. | `{event:m-7-dominant_loss#428}, and {clause:possession}.` |

### Koşu 2 · natural_seed100

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M001 | red_card | 14' | llm | 1 | Iveno Gundrel was sent off at 14', and Isteven United are down to 10 players on the pitch. | `{event:m-100#84}, and {clause:players}.` |
| M004 | goal | 29' | llm | 1 | Hesko Ilvanto scored at 29', and Tessdal Wanderers have had 58% of the ball since kickoff. | `{event:m-100#175}, and {clause:possession}.` |
| M005 | score_change | 29' | llm | 1 | Hesko Ilvanto scored at 29'. Tessdal Wanderers have had 58% of the ball since kickoff, and the score is Tessdal Wanderers 1–0 Isteven United. | `{event:m-100#175}. {clause:possession}, and {clause:score}.` |
| M006 | goal | 51' | llm | 1 | Quenlo Pelvisto scored at 51', and the score is Tessdal Wanderers 1–1 Isteven United. Isteven United have scored 1 goal so far, and Isteven United have had 49% of the ball since kickoff. | `{event:m-100#317}, and {clause:score}. {clause:team_goals}, and {clause:possession}.` |
| M007 | score_change | 51' | llm | 1 | Quenlo Pelvisto scored at 51', and the score is Tessdal Wanderers 1–1 Isteven United. | `{event:m-100#317}, and {clause:score}.` |
| M009 | dominance_without_reward | 79' | llm | 1 | Since 59' Tessdal Wanderers have had 61% of the ball and a 4–0 lead in shots, and the score is Tessdal Wanderers 1–1 Isteven United. Rastin Ymberto shot off target at 79'. | `{clause:dominance}, and {clause:score}. {event:m-100#478}.` |
| M010 | goal | 90+1' | llm | 1 | Brisko Ymberto scored at 90+1', and the score is Tessdal Wanderers 2–1 Isteven United. | `{event:m-100#550}, and {clause:score}.` |
| M011 | score_change | 90+1' | llm | 1 | Brisko Ymberto scored at 90+1', and Tessdal Wanderers have had 52% of the ball since kickoff. | `{event:m-100#550}, and {clause:possession}.` |

### Koşu 3 · red_card_swing_seed42

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M002 | goal | 22' | llm | 1 | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. | `{event:m-42-red_card_swing#127}, and {clause:possession}.` |
| M003 | score_change | 22' | llm | 1 | Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. | `{event:m-42-red_card_swing#127}, and {clause:possession}.` |
| M005 | red_card | 38' | llm | 1 | Orvik Belmaro was sent off at 38', and Brannoch FC are down to 10 players on the pitch. | `{event:m-42-red_card_swing#213}, and {clause:players}.` |
| M007 | goal | 61' | llm | 1 | Davel Selvado scored at 61', and the score is Brannoch FC 1–1 Morvane Athletic. | `{event:m-42-red_card_swing#359}, and {clause:score}.` |
| M008 | score_change | 61' | llm | 1 | Davel Selvado scored at 61', and the score is Brannoch FC 1–1 Morvane Athletic. | `{event:m-42-red_card_swing#359}, and {clause:score}.` |
| M009 | pressure_shift | 81' | llm | 1 | Brannoch FC lead the pressure balance over the last 10 minutes of play at +0.83, and Brannoch FC have had 2 shots to Morvane Athletic's 0 since 71'. | `{clause:pressure}, and {clause:shots}.` |
| M010 | goal | 84' | llm | 1 | Murek Ymberto scored at 84', and the score is Brannoch FC 1–2 Morvane Athletic. Morvane Athletic have had 50% of the ball since kickoff. | `{event:m-42-red_card_swing#494}, and {clause:score}. {clause:possession}.` |
| M011 | score_change | 84' | llm | 1 | Murek Ymberto scored at 84', and Morvane Athletic have had 50% of the ball since kickoff. | `{event:m-42-red_card_swing#494}, and {clause:possession}.` |
| M012 | pressure_shift | 90+1' | llm | 1 | Murek Ymberto scored at 84', and Morvane Athletic lead the pressure balance over the last 10 minutes of play at +1.00. | `{event:m-42-red_card_swing#493}, and {clause:pressure}.` |

### Koşu 3 · dominant_loss_seed7

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M003 | dominance_without_reward | 45+1' | llm | 1 | Since 25' Vellorin FC have had 58% of the ball and a 4–0 lead in shots. The score is Vellorin FC 0–0 Tessdal Athletic. | `{clause:dominance}. {clause:score}.` |
| M005 | goal | 57' | llm | 1 | Nolvek Ilvanto scored at 57', and Tessdal Athletic have had 39% of the ball since kickoff. The score is Vellorin FC 0–1 Tessdal Athletic. | `{event:m-7-dominant_loss#350}, and {clause:possession}. {clause:score}.` |
| M006 | score_change | 57' | llm | 1 | Nolvek Ilvanto scored at 57', and Tessdal Athletic have had 39% of the ball since kickoff. | `{event:m-7-dominant_loss#350}, and {clause:possession}.` |
| M008 | dominance_without_reward | 66' | llm | 1 | Since 46' Vellorin FC have had 71% of the ball and a 5–1 lead in shots, yet the score is Vellorin FC 0–1 Tessdal Athletic. | `{clause:dominance}, yet {clause:score}.` |
| M009 | penalty | 70' | llm | 2 | Alvezo Hazulov's penalty was saved at 70', and Vellorin FC have had 62% of the ball since kickoff. | `{event:m-7-dominant_loss#428}, and {clause:possession}.` |

### Koşu 3 · natural_seed100

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M001 | red_card | 14' | llm | 1 | Iveno Gundrel was sent off at 14'. Isteven United are down to 10 players on the pitch, and Isteven United have had 51% of the ball since kickoff. | `{event:m-100#84}. {clause:players}, and {clause:possession}.` |
| M004 | goal | 29' | llm | 1 | Hesko Ilvanto scored at 29', and Tessdal Wanderers have had 58% of the ball since kickoff. | `{event:m-100#175}, and {clause:possession}.` |
| M005 | score_change | 29' | llm | 1 | Hesko Ilvanto scored at 29', and Tessdal Wanderers have had 58% of the ball since kickoff. | `{event:m-100#175}, and {clause:possession}.` |
| M006 | goal | 51' | llm | 1 | Quenlo Pelvisto scored at 51', and the score is Tessdal Wanderers 1–1 Isteven United. | `{event:m-100#317}, and {clause:score}.` |
| M007 | score_change | 51' | llm | 1 | Quenlo Pelvisto scored at 51', and the score is Tessdal Wanderers 1–1 Isteven United. | `{event:m-100#317}, and {clause:score}.` |
| M009 | dominance_without_reward | 79' | llm | 1 | Rastin Ymberto shot off target at 79', and since 59' Tessdal Wanderers have had 61% of the ball and a 4–0 lead in shots. | `{event:m-100#478}, and {clause:dominance}.` |
| M010 | goal | 90+1' | llm | 1 | Brisko Ymberto scored at 90+1', and Tessdal Wanderers have had 52% of the ball since kickoff. The score is Tessdal Wanderers 2–1 Isteven United. | `{event:m-100#550}, and {clause:possession}. {clause:score}.` |
| M011 | score_change | 90+1' | llm | 1 | Brisko Ymberto scored at 90+1'. The score is Tessdal Wanderers 2–1 Isteven United, and Tessdal Wanderers have had 52% of the ball since kickoff. | `{event:m-100#550}. {clause:score}, and {clause:possession}.` |
