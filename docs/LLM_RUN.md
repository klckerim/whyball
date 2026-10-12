# LLM anlatım ölçümü (gerçek model)

Bu dosya `python -m eval.llm_run` çalıştırmasının ham çıktısından (`docs/LLM_RUN.json`) üretilir; elle düzenlemeyin.

- Model: `gpt-5-mini` · Prompt sürümü: `foundry-v2:gpt-5-mini` · Dil: `en`
- Çalıştırma: 2026-10-12T19:06:34+00:00 – 2026-10-12T19:16:52+00:00 (UTC)
- Ayarlar: çalıştırma (maç) başına en fazla 60 çağrı, `max_output_tokens` 4000, çağrı zaman aşımı 60 sn, en fazla 2 yeniden deneme, önbellek kapalı
- Her taslak text_lint + verify_claim'den geçti; geçmeyen yayınlanmadı ve template yedeğine düştü.

## Özet

| Maç | Moment | İlk denemede geçen | Yeniden denemeyle geçen | Yedeğe düşen | Çağrı | Token giriş / çıkış (reasoning) | Ort. süre | Maks. süre |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| red_card_swing_seed42 | 9 | 6 (66.7%) | 3 (33.3%) | 0 (0.0%) | 13 | 22567 / 35637 (29952) | 22.5 sn | 28.6 sn |
| dominant_loss_seed7 | 5 | 3 (60.0%) | 2 (40.0%) | 0 (0.0%) | 7 | 11512 / 14298 (12480) | 19.3 sn | 27.9 sn |
| natural_seed100 | 8 | 7 (87.5%) | 1 (12.5%) | 0 (0.0%) | 9 | 16391 / 24482 (21312) | 21.1 sn | 27.7 sn |
| **Toplam** | 22 | 16 (72.7%) | 6 (27.3%) | 0 (0.0%) | 29 | 50470 / 74417 (63744) | 21.3 sn | 28.6 sn |

## Yedeğe düşen momentler

Yok.

## Moment ayrıntıları

### red_card_swing_seed42

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin |
|---|---|---|---|---:|---|
| M002 | goal | 22' | llm | 1 | Murek Brestani scored for home to make it 1-0 at 22'. |
| M003 | score_change | 22' | llm | 1 | Murek Brestani scored at 22' to make it 1-0. Home possession is 0.555. |
| M005 | red_card | 38' | llm | 2 | Orvik Belmaro was shown a red card at 38'. The score was 1-0. |
| M007 | goal | 61' | llm | 1 | Davel Selvado scored to make it 1-1 at 61'. |
| M008 | score_change | 61' | llm | 1 | Davel Selvado scored at 61' to make it 1-1 for the away team. |
| M009 | pressure_shift | 81' | llm | 2 | At 81' the score was 1-1 and home had field_tilt 0.316. |
| M010 | goal | 84' | llm | 3 | Murek Ymberto scored for the away side to make it 2-1 at 84'. |
| M011 | score_change | 84' | llm | 1 | Murek Ymberto scored to make it 2-1 at 84'. |
| M012 | pressure_shift | 90+1' | llm | 1 | away lead 2-1 at 90'; possession 0.508 for away. |

### dominant_loss_seed7

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin |
|---|---|---|---|---:|---|
| M003 | dominance_without_reward | 45+1' | llm | 1 | Vellorin FC had 0.609 possession and the score was 0-0 at 45'. |
| M005 | goal | 57' | llm | 2 | Nolvek Ilvanto scored at 57' to make it 1-0. |
| M006 | score_change | 57' | llm | 2 | Nolvek Ilvanto scored to make it 1-0 at 57'. |
| M008 | dominance_without_reward | 66' | llm | 1 | At 66' home had 5 shots. |
| M009 | penalty | 70' | llm | 1 | Alvezo Hazulov had a penalty saved at 70', leaving the score 1-0. |

### natural_seed100

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin |
|---|---|---|---|---:|---|
| M001 | red_card | 14' | llm | 1 | Iveno Gundrel was shown a straight red at 14' and the score remained 0-0. |
| M004 | goal | 29' | llm | 1 | Hesko Ilvanto scored in the 29' to make it 1-0. |
| M005 | score_change | 29' | llm | 1 | Hesko Ilvanto scored at 29' to make it 1-0. |
| M006 | goal | 51' | llm | 1 | Quenlo Pelvisto scored to make it 1-1 at 51'. |
| M007 | score_change | 51' | llm | 1 | Quenlo Pelvisto equalised at 51' to make it 1-1. |
| M009 | dominance_without_reward | 79' | llm | 2 | Home had 4 shots between 70' and 79'. Possession to this point was 0.543 and the score was 1-1 at 79'. |
| M010 | goal | 90+1' | llm | 1 | Brisko Ymberto scored for the home side at 90' to make the score 2-1. |
| M011 | score_change | 90+1' | llm | 1 | Brisko Ymberto scored at 90' to make it 2-1 for the home team. |
