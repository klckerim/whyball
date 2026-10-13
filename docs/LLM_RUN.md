# LLM anlatım ölçümü (gerçek model)

Bu dosya `python -m eval.llm_run` çalıştırmasının ham çıktısından (`docs/LLM_RUN.json`) üretilir; elle düzenlemeyin.

- Model: `gpt-5-mini` · Prompt sürümü: `foundry-v4.1:gpt-5-mini` · Dil: `en` · Reasoning çabası: `low`
- Çalıştırma: 2026-10-13T12:11:38+00:00 – 2026-10-13T12:35:52+00:00 (UTC), 3 koşu (aynı prompt)
- Ayarlar: çalıştırma (maç) başına en fazla 60 çağrı, `max_output_tokens` 4000, çağrı zaman aşımı 60 sn, en fazla 2 yeniden deneme, önbellek kapalı
- Her taslak lint + yer tutucu bağlama + verify_claim'den geçti; geçmeyen yayınlanmadı ve template yedeğine düştü. Yayınlanan LLM metinlerinde somut değerleri kod render etti.

## Özet

### Koşu 1 (2026-10-13T12:11:38+00:00 – 2026-10-13T12:19:30+00:00)

| Maç | Moment | İlk denemede geçen | Yeniden denemeyle geçen | Yedeğe düşen | Çağrı | Token giriş / çıkış | Reasoning (çıkışın %'si) | Ort. süre | Medyan | Maks. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red_card_swing_seed42 | 9 | 6 (66.7%) | 2 (22.2%) | 1 (11.1%) | 14 | 40724 / 20054 | 13632 (68.0%) | 14.4 sn | 12.7 sn | 33.4 sn |
| dominant_loss_seed7 | 5 | 3 (60.0%) | 1 (20.0%) | 1 (20.0%) | 9 | 27803 / 15052 | 10752 (71.4%) | 15.1 sn | 13.5 sn | 25.3 sn |
| natural_seed100 | 8 | 7 (87.5%) | 0 (0.0%) | 1 (12.5%) | 10 | 28516 / 14482 | 10112 (69.8%) | 13.5 sn | 13.8 sn | 16.2 sn |
| **Toplam** | 22 | 16 (72.7%) | 3 (13.6%) | 3 (13.6%) | 33 | 97043 / 49588 | 34496 (69.6%) | 14.3 sn | 13.5 sn | 33.4 sn |

### Koşu 2 (2026-10-13T12:19:30+00:00 – 2026-10-13T12:27:35+00:00)

| Maç | Moment | İlk denemede geçen | Yeniden denemeyle geçen | Yedeğe düşen | Çağrı | Token giriş / çıkış | Reasoning (çıkışın %'si) | Ort. süre | Medyan | Maks. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red_card_swing_seed42 | 9 | 5 (55.6%) | 2 (22.2%) | 2 (22.2%) | 16 | 47622 / 24317 | 16384 (67.4%) | 14.8 sn | 13.9 sn | 19.3 sn |
| dominant_loss_seed7 | 5 | 3 (60.0%) | 2 (40.0%) | 0 (0.0%) | 8 | 24484 / 11803 | 8000 (67.8%) | 13.3 sn | 13.0 sn | 17.3 sn |
| natural_seed100 | 8 | 6 (75.0%) | 2 (25.0%) | 0 (0.0%) | 11 | 31627 / 14952 | 10240 (68.5%) | 12.9 sn | 12.9 sn | 18.7 sn |
| **Toplam** | 22 | 14 (63.6%) | 6 (27.3%) | 2 (9.1%) | 35 | 103733 / 51072 | 34624 (67.8%) | 13.8 sn | 13.4 sn | 19.3 sn |

### Koşu 3 (2026-10-13T12:27:35+00:00 – 2026-10-13T12:35:52+00:00)

| Maç | Moment | İlk denemede geçen | Yeniden denemeyle geçen | Yedeğe düşen | Çağrı | Token giriş / çıkış | Reasoning (çıkışın %'si) | Ort. süre | Medyan | Maks. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red_card_swing_seed42 | 9 | 6 (66.7%) | 2 (22.2%) | 1 (11.1%) | 14 | 41302 / 23321 | 16512 (70.8%) | 14.8 sn | 13.4 sn | 24.9 sn |
| dominant_loss_seed7 | 5 | 3 (60.0%) | 2 (40.0%) | 0 (0.0%) | 8 | 24507 / 13218 | 9024 (68.3%) | 16.1 sn | 14.7 sn | 26.2 sn |
| natural_seed100 | 8 | 6 (75.0%) | 1 (12.5%) | 1 (12.5%) | 12 | 34098 / 16756 | 11456 (68.4%) | 13.4 sn | 11.9 sn | 27.7 sn |
| **Toplam** | 22 | 15 (68.2%) | 5 (22.7%) | 2 (9.1%) | 34 | 99907 / 53295 | 36992 (69.4%) | 14.6 sn | 13.3 sn | 27.7 sn |

### Koşu başına yedeğe düşen

| Koşu | Moment | Yedeğe düşen | Reddedilen deneme | evidence_mismatch |
|---|---:|---:|---:|---:|
| 1 | 22 | 3 | 14 | 10 |
| 2 | 22 | 2 | 15 | 15 |
| 3 | 22 | 2 | 14 | 11 |
| **Toplam** | 66 | 7 | 43 | 36 |

## Sürüm karşılaştırması: foundry-v3, foundry-v4, foundry-v4.1

Önceki sürümler arşivlenen ham çıktılardan (`docs/LLM_RUN.<sürüm>.json`). Ret = yayınlanmayan deneme; `evidence_mismatch` sütunu bu kodu içeren reddedilen deneme sayısı.

| Sürüm / koşu | Moment | İlk denemede | Yeniden denemeyle | Yedeğe düşen | Çağrı | Reddedilen deneme | evidence_mismatch | Token çıkış |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| foundry-v3 | 22 | 12 | 8 | 2 | 37 | 17 | 12 | 56884 |
| foundry-v4 | 22 | 12 | 6 | 4 | 38 | 20 | 13 | 63598 |
| foundry-v4.1 · koşu 1 | 22 | 16 | 3 | 3 | 33 | 14 | 10 | 49588 |
| foundry-v4.1 · koşu 2 | 22 | 14 | 6 | 2 | 35 | 15 | 15 | 51072 |
| foundry-v4.1 · koşu 3 | 22 | 15 | 5 | 2 | 34 | 14 | 11 | 53295 |
| **foundry-v4.1 · toplam (3 koşu)** | 66 | 45 | 14 | 7 | 102 | 43 | 36 | 153955 |

`evidence_mismatch` içeren reddedilen denemeler, moment tipine göre (sürümün tüm koşuları; parantezde koşu sayısı):

| Moment tipi | foundry-v3 (1) | foundry-v4 (1) | foundry-v4.1 (3) |
|---|---:|---:|---:|
| dominance_without_reward | 6 | 3 | 11 |
| goal | 3 | 3 | 16 |
| penalty | 0 | 3 | 0 |
| pressure_shift | 3 | 4 | 9 |
| red_card | 0 | 0 | 0 |
| score_change | 0 | 0 | 0 |

## evidence_mismatch: bağlanan ve sayılan olaylar

Her satır bir reddedilen iddia grubu. Bağlanan = modelin `event_ids`'i; sayılan = doğrulayıcının aynı özne, metrik ve aralıkta saydığı olaylar. Eksik = sayılan ama bağlanmayan, fazla = bağlanan ama sayılmayan.

| Moment tipi | İddia | Aralık | Bağlanan | Sayılan | Eksik | Fazla | Adet |
|---|---|---|---|---|---|---|---:|
| goal | count goals away | maç başı → an | goal×1, shot×1 | goal×2 | goal×1 | shot×1 | 7 |
| dominance_without_reward | count shots home | maç başı → an | shot×4 | shot×9 | shot×5 | — | 6 |
| goal | count goals home | maç başı → an | goal×1, shot×1 | goal×2 | goal×1 | shot×1 | 6 |
| pressure_shift | count goals away + oyuncu | olay anı | shot×1 | goal×1 | goal×1 | shot×1 | 4 |
| dominance_without_reward | count shots home | maç başı → an | shot×5 | shot×15 | shot×10 | — | 3 |
| goal | count goals home + oyuncu | maç başı → an | goal×1, shot×1 | goal×1 | — | shot×1 | 2 |
| pressure_shift | count shots home | maç başı → an | shot×2 | shot×5 | shot×3 | — | 2 |
| pressure_shift | count shots home + oyuncu | maç başı → an | shot×2 | shot×3 | shot×1 | — | 2 |
| dominance_without_reward | count shots home | maç başı → an | shot×4 | shot×16 | shot×12 | — | 1 |
| dominance_without_reward | count shots_on_target home | maç başı → an | shot×2 | shot×7 | shot×5 | — | 1 |
| goal | count goals away + oyuncu | maç başı → an | goal×1, shot×1 | goal×1 | — | shot×1 | 1 |
| goal | count goals away + oyuncu | olay anı | goal×1, shot×1 | goal×1 | — | shot×1 | 1 |
| goal | count shots home | maç başı → an | goal×1, shot×1 | shot×2 | shot×1 | goal×1 | 1 |
| pressure_shift | count goals away + oyuncu | maç başı → an | shot×1 | goal×1 | goal×1 | shot×1 | 1 |
| pressure_shift | count shots_on_target home | maç başı → an | shot×1 | shot×3 | shot×2 | — | 1 |

Moment tipine göre (reddedilen iddia): goal 18, dominance_without_reward 11, pressure_shift 10.

Örnek ret mesajları:

- `M010` (goal) #1: `{event:m-42-red_card_swing#494}, making it {score}. {away} have had {value:c3} of the territorial share since kickoff.` → verify c1 evidence_mismatch: count goals team=away [1H 00:00–2H 84:00] eq 2 refs=[m-42-red_card_swing#493, m-42-red_card_swing#494]; cited [#493 shot, #494 goal] counted [#359 goal, #494 goal]
- `M010` (goal) #2: `{event:m-42-red_card_swing#494}, making it {score}. {player:a11} has {value:c2} of the {label:c2} for {away}.` → verify c1 evidence_mismatch: count goals team=away [1H 00:00–2H 84:00] eq 2 refs=[m-42-red_card_swing#493, m-42-red_card_swing#494]; cited [#493 shot, #494 goal] counted [#359 goal, #494 goal] \| verify c2 evidence_mismatch: count goals team=away player=Murek Ymberto [1H 00:00–2H 84:00] eq 2 refs=[m-42-red_card_swing#493, m-42-red_card_swing#494]; cited [#493 shot, #494 goal] counted [#494 goal]
- `M010` (goal) #3: `{event:m-42-red_card_swing#494}, making it {score}. {away} have had {value:c2} of the ball since kickoff.` → verify c1 evidence_mismatch: count goals team=away [1H 00:00–2H 84:00] eq 2 refs=[m-42-red_card_swing#493, m-42-red_card_swing#494]; cited [#493 shot, #494 goal] counted [#359 goal, #494 goal]
- `M012` (pressure_shift) #2: `{event:m-42-red_card_swing#493}, making it {score}. {away} have had {value:c4} of the ball since kickoff.` → verify c1 evidence_mismatch: count goals team=away player=Murek Ymberto [2H 84:00–2H 84:00] eq 1 refs=[m-42-red_card_swing#493]; cited [#493 shot] counted [#494 goal]
- `M003` (dominance_without_reward) #1: `{event:m-7-dominant_loss#269} At halftime {home} have had {value:c2} of the ball since kickoff and {label:c1} count is {value:c1}.` → lint raw_entity 'At' \| verify c1 evidence_mismatch: count shots team=home [1H 00:00–1H 45:33] eq 4 refs=[m-7-dominant_loss#173, m-7-dominant_loss#197, m-7-dominant_loss#258, m-7-dominant_loss#269]; cited [#173 shot, #197 shot, #258 shot, #269 shot] counted [#42 shot, #54 shot, #57 shot, #65 shot, #68 shot, #173 shot, #197 shot, #258 shot, #269 shot]
- `M003` (dominance_without_reward) #2: `{event:m-7-dominant_loss#269}. The {home} have had {value:c2} of the ball since kickoff and {label:c3} is {value:c3}.` → lint article_team 'The {home}' \| verify c1 evidence_mismatch: count shots team=home [1H 00:00–1H 45:33] eq 4 refs=[m-7-dominant_loss#173, m-7-dominant_loss#197, m-7-dominant_loss#258, m-7-dominant_loss#269]; cited [#173 shot, #197 shot, #258 shot, #269 shot] counted [#42 shot, #54 shot, #57 shot, #65 shot, #68 shot, #173 shot, #197 shot, #258 shot, #269 shot]

## foundry-v4.1 kurallarının canlı tetiklenmesi

Yalnız bu kural = denemenin tek ret nedeni bu kuraldı (başka lint ya da verify hatası yok): kural olmasa yayınlanacaktı. Kuralın hedeflediği kalıpsa doğru ret, değilse yanlış alarm; taslaklar aşağıda.

| Kural | Tetiklenen deneme | Yalnız bu kural | Parçalar |
|---|---:|---:|---|
| `event_type_not_allowed` | 0 | 0 | — |
| `player_repeat` | 0 | 0 | — |
| `article_team` | 7 | 2 | `The {home}`×4, `The {away}`×3 |
| `sentence_start` | 1 | 0 | `m`×1 |

Yalnız yeni kural yüzünden reddedilen taslaklar:

- `article_team`: `{event:m-42-red_card_swing#493}, making it {score}. The {away} have had {value:c2} of the ball since kickoff.`
- `article_team`: `{event:m-100#175}, making it {score}. The {home} have had {value:c2} of the ball since kickoff.`

## Yedeğe düşen momentler

| Koşu | Maç | Moment | Tip | Dakika | Yedek sebebi | Deneme bazında ret kodları |
|---|---|---|---|---|---|---|
| 1 | red_card_swing_seed42 | M010 | goal | 84' | `max_retries_exceeded` | #1: `evidence_mismatch`; #2: `evidence_mismatch`×2; #3: `evidence_mismatch` |
| 1 | dominant_loss_seed7 | M003 | dominance_without_reward | 45+1' | `max_retries_exceeded` | #1: `raw_entity`, `evidence_mismatch`; #2: `article_team`, `evidence_mismatch`; #3: `raw_entity`, `unknown_placeholder` |
| 1 | natural_seed100 | M010 | goal | 90+1' | `max_retries_exceeded` | #1: `evidence_mismatch`; #2: `invalid_subject`; #3: `evidence_mismatch`×2 |
| 2 | red_card_swing_seed42 | M009 | pressure_shift | 81' | `max_retries_exceeded` | #1: `sentence_start`, `raw_number`×2, `raw_metric_name`, `evidence_mismatch`; #2: `article_team`, `evidence_mismatch`; #3: `evidence_mismatch`×2 |
| 2 | red_card_swing_seed42 | M010 | goal | 84' | `max_retries_exceeded` | #1: `article_team`, `evidence_mismatch`; #2: `evidence_mismatch`; #3: `evidence_mismatch` |
| 3 | red_card_swing_seed42 | M012 | pressure_shift | 90+1' | `max_retries_exceeded` | #1: `article_team`; #2: `evidence_mismatch`, `invalid_subject`; #3: `evidence_mismatch`, `invalid_subject` |
| 3 | natural_seed100 | M010 | goal | 90+1' | `max_retries_exceeded` | #1: `evidence_mismatch`; #2: `evidence_mismatch`; #3: `evidence_mismatch` |

Yedeğe düşen momentlerde ret kodu sıklığı: `evidence_mismatch`×21, `raw_entity`×2, `article_team`×4, `unknown_placeholder`, `invalid_subject`×3, `sentence_start`, `raw_number`×2, `raw_metric_name`

## Yeniden denemeyle geçen momentler

| Koşu | Maç | Moment | Tip | Deneme | Reddedilen denemeler |
|---|---|---|---|---:|---|
| 1 | red_card_swing_seed42 | M008 | score_change | 2 | #1: `invalid_subject` |
| 1 | red_card_swing_seed42 | M012 | pressure_shift | 3 | #1: `invalid_subject`; #2: `evidence_mismatch` |
| 1 | dominant_loss_seed7 | M008 | dominance_without_reward | 3 | #1: `evidence_mismatch`; #2: `raw_number`, `evidence_mismatch` |
| 2 | red_card_swing_seed42 | M002 | goal | 2 | #1: `evidence_mismatch`, `invalid_subject` |
| 2 | red_card_swing_seed42 | M012 | pressure_shift | 3 | #1: `evidence_mismatch`; #2: `evidence_mismatch` |
| 2 | dominant_loss_seed7 | M003 | dominance_without_reward | 3 | #1: `evidence_mismatch`; #2: `evidence_mismatch` |
| 2 | dominant_loss_seed7 | M008 | dominance_without_reward | 2 | #1: `evidence_mismatch` |
| 2 | natural_seed100 | M009 | dominance_without_reward | 2 | #1: `evidence_mismatch` |
| 2 | natural_seed100 | M010 | goal | 3 | #1: `evidence_mismatch`; #2: `evidence_mismatch` |
| 3 | red_card_swing_seed42 | M009 | pressure_shift | 2 | #1: `evidence_mismatch` |
| 3 | red_card_swing_seed42 | M010 | goal | 3 | #1: `evidence_mismatch`; #2: `article_team`, `evidence_mismatch` |
| 3 | dominant_loss_seed7 | M003 | dominance_without_reward | 3 | #1: `evidence_mismatch`; #2: `evidence_mismatch` |
| 3 | dominant_loss_seed7 | M008 | dominance_without_reward | 2 | #1: `article_team`, `evidence_mismatch` |
| 3 | natural_seed100 | M005 | score_change | 3 | #1: `article_team`; #2: `invalid_subject` |

## Reddedilen taslaklar

| Koşu | Maç | Moment | Tip | Deneme | Ret kodları | Model şablonu | Ret mesajı |
|---|---|---|---|---:|---|---|---|
| 1 | red_card_swing_seed42 | M008 | score_change | 1 | `invalid_subject` | `{event:m-42-red_card_swing#359}, making it {score}.` | verify c2 invalid_subject: state score all [1H 00:00–2H 61:00] eq 1 refs=[m-42-red_card_swing#359] |
| 1 | red_card_swing_seed42 | M010 | goal | 1 | `evidence_mismatch` | `{event:m-42-red_card_swing#494}, making it {score}. {away} have had {value:c3} of the territorial share since kickoff.` | verify c1 evidence_mismatch: count goals team=away [1H 00:00–2H 84:00] eq 2 refs=[m-42-red_card_swing#493, m-42-red_card_swing#494]; cited [#493 shot, #494 goal] counted [#359 goal, #494 goal] |
| 1 | red_card_swing_seed42 | M010 | goal | 2 | `evidence_mismatch`×2 | `{event:m-42-red_card_swing#494}, making it {score}. {player:a11} has {value:c2} of the {label:c2} for {away}.` | verify c1 evidence_mismatch: count goals team=away [1H 00:00–2H 84:00] eq 2 refs=[m-42-red_card_swing#493, m-42-red_card_swing#494]; cited [#493 shot, #494 goal] counted [#359 goal, #494 goal] \| verify c2 evidence_mismatch: count goals team=away player=Murek Ymberto [1H 00:00–2H 84:00] eq 2 refs=[m-42-red_card_swing#493, m-42-red_card_swing#494]; cited [#493 shot, #494 goal] counted [#494 goal] |
| 1 | red_card_swing_seed42 | M010 | goal | 3 | `evidence_mismatch` | `{event:m-42-red_card_swing#494}, making it {score}. {away} have had {value:c2} of the ball since kickoff.` | verify c1 evidence_mismatch: count goals team=away [1H 00:00–2H 84:00] eq 2 refs=[m-42-red_card_swing#493, m-42-red_card_swing#494]; cited [#493 shot, #494 goal] counted [#359 goal, #494 goal] |
| 1 | red_card_swing_seed42 | M012 | pressure_shift | 1 | `invalid_subject` | `{event:m-42-red_card_swing#493}, making it {score}. {away} have had {value:c2} of the ball since kickoff.` | verify c1 invalid_subject: state score all [1H 00:00–2H 90:05] eq 2 refs=[m-42-red_card_swing#493] |
| 1 | red_card_swing_seed42 | M012 | pressure_shift | 2 | `evidence_mismatch` | `{event:m-42-red_card_swing#493}, making it {score}. {away} have had {value:c4} of the ball since kickoff.` | verify c1 evidence_mismatch: count goals team=away player=Murek Ymberto [2H 84:00–2H 84:00] eq 1 refs=[m-42-red_card_swing#493]; cited [#493 shot] counted [#494 goal] |
| 1 | dominant_loss_seed7 | M003 | dominance_without_reward | 1 | `raw_entity`, `evidence_mismatch` | `{event:m-7-dominant_loss#269} At halftime {home} have had {value:c2} of the ball since kickoff and {label:c1} count is {value:c1}.` | lint raw_entity 'At' \| verify c1 evidence_mismatch: count shots team=home [1H 00:00–1H 45:33] eq 4 refs=[m-7-dominant_loss#173, m-7-dominant_loss#197, m-7-dominant_loss#258, m-7-dominant_loss#269]; cited [#173 shot, #197 shot, #258 shot, #269 shot] counted [#42 shot, #54 shot, #57 shot, #65 shot, #68 shot, #173 shot, #197 shot, #258 shot, #269 shot] |
| 1 | dominant_loss_seed7 | M003 | dominance_without_reward | 2 | `article_team`, `evidence_mismatch` | `{event:m-7-dominant_loss#269}. The {home} have had {value:c2} of the ball since kickoff and {label:c3} is {value:c3}.` | lint article_team 'The {home}' \| verify c1 evidence_mismatch: count shots team=home [1H 00:00–1H 45:33] eq 4 refs=[m-7-dominant_loss#173, m-7-dominant_loss#197, m-7-dominant_loss#258, m-7-dominant_loss#269]; cited [#173 shot, #197 shot, #258 shot, #269 shot] counted [#42 shot, #54 shot, #57 shot, #65 shot, #68 shot, #173 shot, #197 shot, #258 shot, #269 shot] |
| 1 | dominant_loss_seed7 | M003 | dominance_without_reward | 3 | `raw_entity`, `unknown_placeholder` | `{home} have had {value:c1} of the ball since kickoff. {event:m-7-dominant_loss#269} At {minute:c2} {home} have had {value:c2} {label:c2} between {start:c2} and {end:c2}.` | lint raw_entity 'At' \| lint unknown_placeholder '{end:c2}' |
| 1 | dominant_loss_seed7 | M008 | dominance_without_reward | 1 | `evidence_mismatch` | `{event:m-7-dominant_loss#408}. {home} have had {value:c2} of the ball since kickoff, {label:c1} are {value:c1} and the {label:c3} is {value:c3}.` | verify c1 evidence_mismatch: count shots team=home [1H 00:00–2H 66:57] eq 5 refs=[m-7-dominant_loss#358, m-7-dominant_loss#364, m-7-dominant_loss#396, m-7-dominant_loss#405, m-7-dominant_loss#408]; cited [#358 shot, #364 shot, #396 shot, #405 shot, #408 shot] counted [#42 shot, #54 shot, #57 shot, #65 shot, #68 shot, #173 shot, #197 shot, #258 shot, #269 shot, #275 shot, #358 shot, #364 shot, #396 shot, #405 shot, #408 shot] |
| 1 | dominant_loss_seed7 | M008 | dominance_without_reward | 2 | `raw_number`, `evidence_mismatch` | `Possession {label:c1} is {value:c1} for {home}. {event:m-7-dominant_loss#408}, with {home} having {value:c2} {label:c2} in the last twenty minutes and {value:c3} {label:c3}; {home} are {value:c4} {label:c4}.` | lint raw_number 'twenty' \| verify c3 evidence_mismatch: count shots_on_target team=home [1H 00:00–2H 66:57] eq 2 refs=[m-7-dominant_loss#358, m-7-dominant_loss#396]; cited [#358 shot, #396 shot] counted [#42 shot, #65 shot, #68 shot, #197 shot, #275 shot, #358 shot, #396 shot] |
| 1 | natural_seed100 | M010 | goal | 1 | `evidence_mismatch` | `{event:m-100#550}, making it {score}. Possession {home} have had {value:c3} of the ball since kickoff.` | verify c1 evidence_mismatch: count goals team=home [1H 00:00–2H 90:13] eq 2 refs=[m-100#549, m-100#550]; cited [#549 shot, #550 goal] counted [#175 goal, #550 goal] |
| 1 | natural_seed100 | M010 | goal | 2 | `invalid_subject` | `{event:m-100#550}, making it {score}. {home} have had {value:c3} of the ball since kickoff.` | verify c2 invalid_subject: state score all [1H 00:00–2H 90:13] eq 2 refs=[m-100#550] |
| 1 | natural_seed100 | M010 | goal | 3 | `evidence_mismatch`×2 | `{event:m-100#550}, making it {score}. Possession has been {value:c2} for {home} since kickoff.` | verify c1 evidence_mismatch: count goals team=home [1H 00:00–2H 90:13] eq 2 refs=[m-100#549, m-100#550]; cited [#549 shot, #550 goal] counted [#175 goal, #550 goal] \| verify c4 evidence_mismatch: count goals team=home player=Brisko Ymberto [1H 00:00–2H 90:13] eq 2 refs=[m-100#549, m-100#550]; cited [#549 shot, #550 goal] counted [#550 goal] |
| 2 | red_card_swing_seed42 | M002 | goal | 1 | `evidence_mismatch`, `invalid_subject` | `{event:m-42-red_card_swing#127}, making it {score}. {home} have had {value:c3} of the ball since kickoff.` | verify c2 evidence_mismatch: count shots team=home [1H 00:00–1H 22:00] eq 2 refs=[m-42-red_card_swing#126, m-42-red_card_swing#127]; cited [#126 shot, #127 goal] counted [#57 shot, #126 shot] \| verify c4 invalid_subject: state score all [1H 00:00–1H 22:00] eq 1 refs=[m-42-red_card_swing#127] |
| 2 | red_card_swing_seed42 | M009 | pressure_shift | 1 | `sentence_start`, `raw_number`×2, `raw_metric_name`, `evidence_mismatch` | `m-42-red_card_swing#464. At {minute:c2} the score was {score_named}.` | lint sentence_start 'm' \| lint raw_number '42' \| lint raw_metric_name 'red_card_swing' \| lint raw_number '464' \| verify c1 evidence_mismatch: count shots team=home [1H 00:00–2H 81:14] eq 2 refs=[m-42-red_card_swing#464, m-42-red_card_swing#468]; cited [#464 shot, #468 shot] counted [#57 shot, #126 shot, #294 shot, #464 shot, #468 shot] |
| 2 | red_card_swing_seed42 | M009 | pressure_shift | 2 | `article_team`, `evidence_mismatch` | `{event:m-42-red_card_swing#464}. The {player:h09} have had {value:c1} {label:c1} since kickoff. The {home} have had {value:c2} {label:c2} since kickoff, and {label:c3} is {value:c3}.` | lint article_team 'The {home}' \| verify c1 evidence_mismatch: count shots team=home player=Murek Brestani [1H 00:00–2H 81:14] eq 2 refs=[m-42-red_card_swing#464, m-42-red_card_swing#468]; cited [#464 shot, #468 shot] counted [#126 shot, #464 shot, #468 shot] |
| 2 | red_card_swing_seed42 | M009 | pressure_shift | 3 | `evidence_mismatch`×2 | `{event:m-42-red_card_swing#464}, and that was {value:c1} {label:c1} for {home}. {home} have had {value:c2} of the ball since kickoff, and {label:c3} is {value:c3}.` | verify c1 evidence_mismatch: count shots_on_target team=home [1H 00:00–2H 81:14] eq 1 refs=[m-42-red_card_swing#464]; cited [#464 shot] counted [#57 shot, #126 shot, #464 shot] \| verify c4 evidence_mismatch: count shots team=home player=Murek Brestani [1H 00:00–2H 81:14] eq 2 refs=[m-42-red_card_swing#464, m-42-red_card_swing#468]; cited [#464 shot, #468 shot] counted [#126 shot, #464 shot, #468 shot] |
| 2 | red_card_swing_seed42 | M010 | goal | 1 | `article_team`, `evidence_mismatch` | `{event:m-42-red_card_swing#494}, making it {score}. The {away} have had {value:c2} of the territorial share since kickoff.` | lint article_team 'The {away}' \| verify c1 evidence_mismatch: count goals team=away player=Murek Ymberto [2H 84:00–2H 84:00] eq 2 refs=[m-42-red_card_swing#493, m-42-red_card_swing#494]; cited [#493 shot, #494 goal] counted [#494 goal] |
| 2 | red_card_swing_seed42 | M010 | goal | 2 | `evidence_mismatch` | `{event:m-42-red_card_swing#494}, making it {score}. {away} have had {value:c2} of the ball since kickoff.` | verify c1 evidence_mismatch: count goals team=away [1H 00:00–2H 84:00] eq 2 refs=[m-42-red_card_swing#493, m-42-red_card_swing#494]; cited [#493 shot, #494 goal] counted [#359 goal, #494 goal] |
| 2 | red_card_swing_seed42 | M010 | goal | 3 | `evidence_mismatch` | `{event:m-42-red_card_swing#494}, making it {score}. {away} have had {value:c2} of the {label:c2} since kickoff.` | verify c1 evidence_mismatch: count goals team=away [1H 00:00–2H 84:00] eq 2 refs=[m-42-red_card_swing#493, m-42-red_card_swing#494]; cited [#493 shot, #494 goal] counted [#359 goal, #494 goal] |
| 2 | red_card_swing_seed42 | M012 | pressure_shift | 1 | `evidence_mismatch` | `{event:m-42-red_card_swing#493}, making it {score}. Possession has been {value:c3} for {away} since kickoff.` | verify c1 evidence_mismatch: count goals team=away player=Murek Ymberto [2H 84:00–2H 84:00] eq 1 refs=[m-42-red_card_swing#493]; cited [#493 shot] counted [#494 goal] |
| 2 | red_card_swing_seed42 | M012 | pressure_shift | 2 | `evidence_mismatch` | `{event:m-42-red_card_swing#493}, making it {score}. {away} have had {value:c2} of the ball since kickoff.` | verify c1 evidence_mismatch: count goals team=away player=Murek Ymberto [2H 84:00–2H 84:00] eq 1 refs=[m-42-red_card_swing#493]; cited [#493 shot] counted [#494 goal] |
| 2 | dominant_loss_seed7 | M003 | dominance_without_reward | 1 | `evidence_mismatch` | `{event:m-7-dominant_loss#269}, with the score still {score}. {home} have had {value:c2} of the ball since kickoff.` | verify c1 evidence_mismatch: count shots team=home [1H 00:00–1H 45:33] eq 4 refs=[m-7-dominant_loss#173, m-7-dominant_loss#197, m-7-dominant_loss#258, m-7-dominant_loss#269]; cited [#173 shot, #197 shot, #258 shot, #269 shot] counted [#42 shot, #54 shot, #57 shot, #65 shot, #68 shot, #173 shot, #197 shot, #258 shot, #269 shot] |
| 2 | dominant_loss_seed7 | M003 | dominance_without_reward | 2 | `evidence_mismatch` | `{event:m-7-dominant_loss#269}, making it {score}. {home} have had {value:c2} of the ball since kickoff and have registered {value:c1} {label:c1}.` | verify c1 evidence_mismatch: count shots team=home [1H 00:00–1H 45:33] eq 4 refs=[m-7-dominant_loss#173, m-7-dominant_loss#197, m-7-dominant_loss#258, m-7-dominant_loss#269]; cited [#173 shot, #197 shot, #258 shot, #269 shot] counted [#42 shot, #54 shot, #57 shot, #65 shot, #68 shot, #173 shot, #197 shot, #258 shot, #269 shot] |
| 2 | dominant_loss_seed7 | M008 | dominance_without_reward | 1 | `evidence_mismatch` | `{event:m-7-dominant_loss#408}. Possession since kickoff for {home} is {value:c2} and {label:c1} are {value:c1}.` | verify c1 evidence_mismatch: count shots team=home [1H 00:00–2H 66:57] eq 5 refs=[m-7-dominant_loss#358, m-7-dominant_loss#364, m-7-dominant_loss#396, m-7-dominant_loss#405, m-7-dominant_loss#408]; cited [#358 shot, #364 shot, #396 shot, #405 shot, #408 shot] counted [#42 shot, #54 shot, #57 shot, #65 shot, #68 shot, #173 shot, #197 shot, #258 shot, #269 shot, #275 shot, #358 shot, #364 shot, #396 shot, #405 shot, #408 shot] |
| 2 | natural_seed100 | M009 | dominance_without_reward | 1 | `evidence_mismatch` | `{event:m-100#478}, leaving it {score}. Possession for {home} since kickoff is {value:c1}.` | verify c2 evidence_mismatch: count shots team=home [1H 00:00–2H 79:01] eq 4 refs=[m-100#420, m-100#425, m-100#452, m-100#478]; cited [#420 shot, #425 shot, #452 shot, #478 shot] counted [#174 shot, #205 shot, #221 shot, #232 shot, #239 shot, #244 shot, #254 shot, #267 shot, #325 shot, #334 shot, #338 shot, #346 shot, #420 shot, #425 shot, #452 shot, #478 shot] |
| 2 | natural_seed100 | M010 | goal | 1 | `evidence_mismatch` | `{event:m-100#550}, making it {score}. Possession for {home} has been {value:c3} since kickoff.` | verify c1 evidence_mismatch: count goals team=home [1H 00:00–2H 90:13] eq 2 refs=[m-100#549, m-100#550]; cited [#549 shot, #550 goal] counted [#175 goal, #550 goal] |
| 2 | natural_seed100 | M010 | goal | 2 | `evidence_mismatch` | `{event:m-100#550}, making it {score}. {home} have had {value:c2} of the ball since kickoff.` | verify c1 evidence_mismatch: count goals team=home [1H 00:00–2H 90:13] eq 2 refs=[m-100#549, m-100#550]; cited [#549 shot, #550 goal] counted [#175 goal, #550 goal] |
| 3 | red_card_swing_seed42 | M009 | pressure_shift | 1 | `evidence_mismatch` | `At {event:m-42-red_card_swing#464}, the score remained {score}. {home} have had {value:c2} of the ball since kickoff and have had {value:c1} {label:c1}.` | verify c1 evidence_mismatch: count shots team=home [1H 00:00–2H 81:14] eq 2 refs=[m-42-red_card_swing#464, m-42-red_card_swing#468]; cited [#464 shot, #468 shot] counted [#57 shot, #126 shot, #294 shot, #464 shot, #468 shot] |
| 3 | red_card_swing_seed42 | M010 | goal | 1 | `evidence_mismatch` | `{event:m-42-red_card_swing#494}, making it {score}. {away} have had {value:c3} of the {label:c3} since kickoff.` | verify c1 evidence_mismatch: count goals team=away [1H 00:00–2H 84:00] eq 2 refs=[m-42-red_card_swing#493, m-42-red_card_swing#494]; cited [#493 shot, #494 goal] counted [#359 goal, #494 goal] |
| 3 | red_card_swing_seed42 | M010 | goal | 2 | `article_team`, `evidence_mismatch` | `{event:m-42-red_card_swing#494}, making it {score}. The {away} have had {value:c3} of {label:c3} since kickoff.` | lint article_team 'The {away}' \| verify c1 evidence_mismatch: count goals team=away [1H 00:00–2H 84:00] eq 2 refs=[m-42-red_card_swing#493, m-42-red_card_swing#494]; cited [#493 shot, #494 goal] counted [#359 goal, #494 goal] |
| 3 | red_card_swing_seed42 | M012 | pressure_shift | 1 | `article_team` | `{event:m-42-red_card_swing#493}, making it {score}. The {away} have had {value:c2} of the ball since kickoff.` | lint article_team 'The {away}' |
| 3 | red_card_swing_seed42 | M012 | pressure_shift | 2 | `evidence_mismatch`, `invalid_subject` | `{event:m-42-red_card_swing#493}, making it {score}. Possession has been {value:c3} for {away} since kickoff.` | verify c1 evidence_mismatch: count goals team=away player=Murek Ymberto [2H 84:00–2H 84:00] eq 1 refs=[m-42-red_card_swing#493]; cited [#493 shot] counted [#494 goal] \| verify c2 invalid_subject: state score all [1H 00:00–2H 90:05] eq 2 refs=[m-42-red_card_swing#493] |
| 3 | red_card_swing_seed42 | M012 | pressure_shift | 3 | `evidence_mismatch`, `invalid_subject` | `{event:m-42-red_card_swing#493}, making it {score_named}. {away} have had {value:c3} of the ball since kickoff.` | verify c1 evidence_mismatch: count goals team=away player=Murek Ymberto [1H 00:00–2H 84:00] eq 1 refs=[m-42-red_card_swing#493]; cited [#493 shot] counted [#494 goal] \| verify c2 invalid_subject: state score all [1H 00:00–2H 90:05] eq 2 refs=[m-42-red_card_swing#493] |
| 3 | dominant_loss_seed7 | M003 | dominance_without_reward | 1 | `evidence_mismatch` | `{event:m-7-dominant_loss#269}, leaving it {score}. At {minute:c1} {home} have had {value:c2} of the ball since kickoff and have had {value:c1} {label:c1}.` | verify c1 evidence_mismatch: count shots team=home [1H 00:00–1H 45:33] eq 4 refs=[m-7-dominant_loss#173, m-7-dominant_loss#197, m-7-dominant_loss#258, m-7-dominant_loss#269]; cited [#173 shot, #197 shot, #258 shot, #269 shot] counted [#42 shot, #54 shot, #57 shot, #65 shot, #68 shot, #173 shot, #197 shot, #258 shot, #269 shot] |
| 3 | dominant_loss_seed7 | M003 | dominance_without_reward | 2 | `evidence_mismatch` | `{event:m-7-dominant_loss#269}, the score remained {score}. {home} have had {value:c2} of the ball since kickoff and have registered {value:c1} {label:c1}.` | verify c1 evidence_mismatch: count shots team=home [1H 00:00–1H 45:33] eq 4 refs=[m-7-dominant_loss#173, m-7-dominant_loss#197, m-7-dominant_loss#258, m-7-dominant_loss#269]; cited [#173 shot, #197 shot, #258 shot, #269 shot] counted [#42 shot, #54 shot, #57 shot, #65 shot, #68 shot, #173 shot, #197 shot, #258 shot, #269 shot] |
| 3 | dominant_loss_seed7 | M008 | dominance_without_reward | 1 | `article_team`, `evidence_mismatch` | `{event:m-7-dominant_loss#408}. The {home} have had {value:c1} {label:c1} and {label:c2} is {value:c2}; {label:c3} is {value:c3} and the score is {score}.` | lint article_team 'The {home}' \| verify c1 evidence_mismatch: count shots team=home [1H 00:00–2H 66:57] eq 5 refs=[m-7-dominant_loss#358, m-7-dominant_loss#364, m-7-dominant_loss#396, m-7-dominant_loss#405, m-7-dominant_loss#408]; cited [#358 shot, #364 shot, #396 shot, #405 shot, #408 shot] counted [#42 shot, #54 shot, #57 shot, #65 shot, #68 shot, #173 shot, #197 shot, #258 shot, #269 shot, #275 shot, #358 shot, #364 shot, #396 shot, #405 shot, #408 shot] |
| 3 | natural_seed100 | M005 | score_change | 1 | `article_team` | `{event:m-100#175}, making it {score}. The {home} have had {value:c2} of the ball since kickoff.` | lint article_team 'The {home}' |
| 3 | natural_seed100 | M005 | score_change | 2 | `invalid_subject` | `{event:m-100#175}, making it {score}. Possession {home} have had {value:c2} of the ball since kickoff.` | verify c3 invalid_subject: state score all [1H 00:00–1H 29:28] eq 1 refs=[m-100#175] |
| 3 | natural_seed100 | M010 | goal | 1 | `evidence_mismatch` | `{event:m-100#550}, making it {score}. At {minute:c1} {home} have had {value:c3} of the ball since kickoff.` | verify c1 evidence_mismatch: count goals team=home [1H 00:00–2H 90:13] eq 2 refs=[m-100#549, m-100#550]; cited [#549 shot, #550 goal] counted [#175 goal, #550 goal] |
| 3 | natural_seed100 | M010 | goal | 2 | `evidence_mismatch` | `{event:m-100#550}, making it {score}. {home} have had {value:c2} of the ball since kickoff.` | verify c1 evidence_mismatch: count goals team=home player=Brisko Ymberto [1H 00:00–2H 90:13] eq 2 refs=[m-100#549, m-100#550]; cited [#549 shot, #550 goal] counted [#550 goal] |
| 3 | natural_seed100 | M010 | goal | 3 | `evidence_mismatch` | `{event:m-100#550}, making it {score}. {home} have had {value:c3} of the ball since kickoff.` | verify c1 evidence_mismatch: count goals team=home [1H 00:00–2H 90:13] eq 2 refs=[m-100#549, m-100#550]; cited [#549 shot, #550 goal] counted [#175 goal, #550 goal] |

## İstemci hataları

Yok.

## Moment ayrıntıları

### Koşu 1 · red_card_swing_seed42

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M002 | goal | 22' | llm | 1 | Murek Brestani scored at 22', making it 1–0. Brannoch FC have had 55% of the ball since kickoff. | `{event:m-42-red_card_swing#127}, making it {score}. {home} have had {value:c2} of the ball since kickoff.` |
| M003 | score_change | 22' | llm | 1 | Murek Brestani scored at 22', making it 1–0. Brannoch FC have had 55% of the ball since kickoff. | `{event:m-42-red_card_swing#127}, making it {score}. {home} have had {value:c3} of the ball since kickoff.` |
| M005 | red_card | 38' | llm | 1 | Orvik Belmaro was sent off at 38', making it 1–0. Brannoch FC have had 54% of the ball since kickoff and the goal margin is 1. | `{event:m-42-red_card_swing#213}, making it {score}. {home} have had {value:c2} of the ball since kickoff and the {label:c3} is {value:c3}.` |
| M007 | goal | 61' | llm | 1 | Davel Selvado scored at 61', making it 1–1. Morvane Athletic have had 71% of the ball since kickoff. | `{event:m-42-red_card_swing#359}, making it {score}. {away} have had {value:c2} of the ball since kickoff.` |
| M008 | score_change | 61' | llm | 2 | Davel Selvado scored at 61', making it 1–1. Morvane Athletic have had 49% of the ball since kickoff. | `{event:m-42-red_card_swing#359}, making it {score}. {away} have had {value:c2} of the ball since kickoff.` |
| M009 | pressure_shift | 81' | llm | 1 | Murek Brestani had a shot saved at 79'. Possession has been 50% for Brannoch FC since kickoff. | `{event:m-42-red_card_swing#464}. Possession has been {value:c2} for {home} since kickoff.` |
| M010 | goal | 84' | template_fallback | 3 | 84' — Murek Ymberto scores for Morvane Athletic. Brannoch FC 1–2 Morvane Athletic. | — |
| M011 | score_change | 84' | llm | 1 | Murek Ymberto scored at 84', making it 1–2. Morvane Athletic have had 50% of the ball since kickoff. | `{event:m-42-red_card_swing#494}, making it {score}. {away} have had {value:c3} of the ball since kickoff.` |
| M012 | pressure_shift | 90+1' | llm | 3 | Murek Ymberto scored at 84'. Possession Morvane Athletic have had 51% of the ball since kickoff. The pressure balance over the last 10 minutes of play is +1.00. | `{event:m-42-red_card_swing#493}. Possession {away} have had {value:c1} of the ball since kickoff. The {label:c2} is {value:c2}.` |

### Koşu 1 · dominant_loss_seed7

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M003 | dominance_without_reward | 45+1' | template_fallback | 3 | 45+1' — Vellorin FC dominate without reward: since 25' they have had 58% of the ball and a 4–0 lead in shots, yet the score is Vellorin FC 0–0 Tessdal Athletic. | — |
| M005 | goal | 57' | llm | 1 | Nolvek Ilvanto scored at 57', making it 0–1. Possession since kickoff has been 61% for Vellorin FC. The pressure balance over the last 10 minutes of play for Tessdal Athletic is +1.00. | `{event:m-7-dominant_loss#350}, making it {score}. Possession since kickoff has been {value:c2} for {home}. The {label:c4} for {away} is {value:c4}.` |
| M006 | score_change | 57' | llm | 1 | Nolvek Ilvanto scored at 57', making it 0–1. Tessdal Athletic have had 39% of the ball since kickoff. | `{event:m-7-dominant_loss#350}, making it {score}. {away} have had {value:c3} of the ball since kickoff.` |
| M008 | dominance_without_reward | 66' | llm | 3 | Possession 62% for Vellorin FC since kickoff. Korin Zerimek had a shot blocked at 66', and the score is 0–1. | `Possession {value:c2} for {home} since kickoff. {event:m-7-dominant_loss#408}, and the score is {score}.` |
| M009 | penalty | 70' | llm | 1 | Alvezo Hazulov's penalty was saved at 70', leaving it 0–1. Vellorin FC have had 62% of the ball since kickoff. | `{event:m-7-dominant_loss#428}, leaving it {score}. {home} have had {value:c2} of the ball since kickoff.` |

### Koşu 1 · natural_seed100

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M001 | red_card | 14' | llm | 1 | Iveno Gundrel was sent off at 14'. Isteven United have had 51% of the ball since kickoff. | `{event:m-100#84}. {away} have had {value:c2} of the ball since kickoff.` |
| M004 | goal | 29' | llm | 1 | Hesko Ilvanto scored at 29', making it 1–0. Tessdal Wanderers have had 58% of the ball since kickoff. | `{event:m-100#175}, making it {score}. {home} have had {value:c2} of the ball since kickoff.` |
| M005 | score_change | 29' | llm | 1 | Hesko Ilvanto scored at 29', making it 1–0. Tessdal Wanderers have had 58% of the ball since kickoff. | `{event:m-100#175}, making it {score}. {home} have had {value:c2} of the ball since kickoff.` |
| M006 | goal | 51' | llm | 1 | Quenlo Pelvisto scored at 51', making it 1–1. Isteven United have had 49% of the ball since kickoff. | `{event:m-100#317}, making it {score}. {away} have had {value:c2} of the ball since kickoff.` |
| M007 | score_change | 51' | llm | 1 | Quenlo Pelvisto scored at 51', making it 1–1. Possession since kickoff has been 51% for Tessdal Wanderers. | `{event:m-100#317}, making it {score}. Possession since kickoff has been {value:c3} for {home}.` |
| M009 | dominance_without_reward | 79' | llm | 1 | At Rastin Ymberto shot off target at 79', Tessdal Wanderers continue to dominate without reward. Possession for Tessdal Wanderers since kickoff is 54%. | `At {event:m-100#478}, {home} continue to dominate without reward. Possession for {home} since kickoff is {value:c2}.` |
| M010 | goal | 90+1' | template_fallback | 3 | 90+1' — Brisko Ymberto scores for Tessdal Wanderers. Tessdal Wanderers 2–1 Isteven United. | — |
| M011 | score_change | 90+1' | llm | 1 | Brisko Ymberto scored at 90+1', making it 2–1. Tessdal Wanderers have had 52% of the ball since kickoff. | `{event:m-100#550}, making it {score}. {home} have had {value:c2} of the ball since kickoff.` |

### Koşu 2 · red_card_swing_seed42

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M002 | goal | 22' | llm | 2 | Murek Brestani scored at 22'. Brannoch FC have had 55% of the ball since kickoff. | `{event:m-42-red_card_swing#127}. {home} have had {value:c2} of the ball since kickoff.` |
| M003 | score_change | 22' | llm | 1 | Murek Brestani scored at 22', making it 1–0. Possession has been 55% for Brannoch FC since kickoff. The pressure balance over the last 10 minutes of play is +0.33. | `{event:m-42-red_card_swing#127}, making it {score}. Possession has been {value:c2} for {home} since kickoff. The {label:c4} is {value:c4}.` |
| M005 | red_card | 38' | llm | 1 | Orvik Belmaro was sent off at 38'. Morvane Athletic have had 46% of the ball since kickoff. The pressure balance over the last 10 minutes of play for Morvane Athletic is +0.54. | `{event:m-42-red_card_swing#213}. {away} have had {value:c2} of the ball since kickoff. The {label:c3} for {away} is {value:c3}.` |
| M007 | goal | 61' | llm | 1 | Davel Selvado scored at 61', making it 1–1. | `{event:m-42-red_card_swing#359}, making it {score}.` |
| M008 | score_change | 61' | llm | 1 | Davel Selvado scored at 61', making it 1–1. Possession Morvane Athletic have had 49% of the ball since kickoff. | `{event:m-42-red_card_swing#359}, making it {score}. Possession {away} have had {value:c3} of the ball since kickoff.` |
| M009 | pressure_shift | 81' | template_fallback | 3 | 81' — Brannoch FC take control: pressure balance over the last 10 minutes of play is +0.83 in their favour. Shots since 71': Brannoch FC 2, Morvane Athletic 0. | — |
| M010 | goal | 84' | template_fallback | 3 | 84' — Murek Ymberto scores for Morvane Athletic. Brannoch FC 1–2 Morvane Athletic. | — |
| M011 | score_change | 84' | llm | 1 | Murek Ymberto scored at 84', making it 1–2. Morvane Athletic have had 50% of the ball since kickoff (possession). | `{event:m-42-red_card_swing#494}, making it {score}. {away} have had {value:c3} of the ball since kickoff ({label:c3}).` |
| M012 | pressure_shift | 90+1' | llm | 3 | Murek Ymberto scored at 84', making it 1–2. Possession Morvane Athletic have had 51% of the ball since kickoff. The pressure balance over the last 10 minutes of play for Morvane Athletic is +1.00. | `{event:m-42-red_card_swing#493}, making it {score}. Possession {away} have had {value:c2} of the ball since kickoff. The {label:c3} for {away} is {value:c3}.` |

### Koşu 2 · dominant_loss_seed7

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M003 | dominance_without_reward | 45+1' | llm | 3 | Ombar Belmaro shot off target at 45+1' as it remains 0–0. Possession Vellorin FC have had 61% of the ball since kickoff. The pressure balance over the last 10 minutes of play is +1.00. | `{event:m-7-dominant_loss#269} as it remains {score}. Possession {home} have had {value:c2} of the ball since kickoff. The {label:c3} is {value:c3}.` |
| M005 | goal | 57' | llm | 1 | Nolvek Ilvanto scored at 57', making it 0–1. Vellorin FC have had 61% of the ball since kickoff. | `{event:m-7-dominant_loss#350}, making it {score}. {home} have had {value:c3} of the ball since kickoff.` |
| M006 | score_change | 57' | llm | 1 | Nolvek Ilvanto scored at 57'. Possession possession has Vellorin FC at 61% since kickoff. | `{event:m-7-dominant_loss#350}. Possession {label:c2} has {home} at {value:c2} since kickoff.` |
| M008 | dominance_without_reward | 66' | llm | 2 | Korin Zerimek had a shot blocked at 66'. Possession since kickoff for Vellorin FC is 62% of the ball according to possession. | `{event:m-7-dominant_loss#408}. Possession since kickoff for {home} is {value:c1} of the ball according to {label:c1}.` |
| M009 | penalty | 70' | llm | 1 | Alvezo Hazulov's penalty was saved at 70', leaving the score 0–1. Vellorin FC have had 62% of the ball since kickoff. | `{event:m-7-dominant_loss#428}, leaving the score {score}. {home} have had {value:c2} of the ball since kickoff.` |

### Koşu 2 · natural_seed100

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M001 | red_card | 14' | llm | 1 | Iveno Gundrel was sent off at 14'. Isteven United have had 51% of the ball since kickoff and the score is 0–0. | `{event:m-100#84}. {away} have had {value:c2} of the ball since kickoff and the score is {score}.` |
| M004 | goal | 29' | llm | 1 | Hesko Ilvanto scored at 29', making it 1–0. Possession since kickoff has been 58% for Tessdal Wanderers. | `{event:m-100#175}, making it {score}. Possession since kickoff has been {value:c3} for {home}.` |
| M005 | score_change | 29' | llm | 1 | Hesko Ilvanto scored at 29', making it 1–0. Tessdal Wanderers have had 58% of the ball since kickoff. | `{event:m-100#175}, making it {score}. {home} have had {value:c2} of the ball since kickoff.` |
| M006 | goal | 51' | llm | 1 | Quenlo Pelvisto scored at 51', making it 1–1. Tessdal Wanderers have had 51% of the ball since kickoff. | `{event:m-100#317}, making it {score}. {home} have had {value:c3} of the ball since kickoff.` |
| M007 | score_change | 51' | llm | 1 | Quenlo Pelvisto scored at 51', making it 1–1. Tessdal Wanderers have had 51% of the ball since kickoff. | `{event:m-100#317}, making it {score}. {home} have had {value:c2} of the ball since kickoff.` |
| M009 | dominance_without_reward | 79' | llm | 2 | Rastin Ymberto shot off target at 79', leaving it 1–1. At 79' Tessdal Wanderers have had 54% of the ball since kickoff. | `{event:m-100#478}, leaving it {score}. At {minute:c2} {home} have had {value:c2} of the ball since kickoff.` |
| M010 | goal | 90+1' | llm | 3 | Brisko Ymberto scored at 90+1', making it 2–1. | `{event:m-100#550}, making it {score}.` |
| M011 | score_change | 90+1' | llm | 1 | Brisko Ymberto scored at 90+1', making it 2–1. | `{event:m-100#550}, making it {score}.` |

### Koşu 3 · red_card_swing_seed42

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M002 | goal | 22' | llm | 1 | Murek Brestani scored at 22', making it 1–0. Possession: Brannoch FC have had 55% of the ball since kickoff. | `{event:m-42-red_card_swing#127}, making it {score}. Possession: {home} have had {value:c3} of the ball since kickoff.` |
| M003 | score_change | 22' | llm | 1 | Murek Brestani scored at 22', making it 1–0. Brannoch FC have had 55% of the ball since kickoff. | `{event:m-42-red_card_swing#127}, making it {score}. {home} have had {value:c3} of the ball since kickoff.` |
| M005 | red_card | 38' | llm | 1 | Orvik Belmaro was sent off at 38'. Possession for Brannoch FC since kickoff is 54%, red cards for Brannoch FC is 1 and at 38' the goal margin for Brannoch FC is 1. | `{event:m-42-red_card_swing#213}. Possession for {home} since kickoff is {value:c2}, {label:c1} for {home} is {value:c1} and at {minute:c3} the {label:c3} for {home} is {value:c3}.` |
| M007 | goal | 61' | llm | 1 | Davel Selvado scored at 61', making it 1–1. Morvane Athletic have had 71% of the territorial share since kickoff. | `{event:m-42-red_card_swing#359}, making it {score}. {away} have had {value:c2} of the {label:c2} since kickoff.` |
| M008 | score_change | 61' | llm | 1 | Davel Selvado scored at 61', making it 1–1. Possession since kickoff has been 49% for Morvane Athletic. The pressure balance over the last 10 minutes of play for Morvane Athletic is +1.00. | `{event:m-42-red_card_swing#359}, making it {score}. Possession since kickoff has been {value:c3} for {away}. The {label:c4} for {away} is {value:c4}.` |
| M009 | pressure_shift | 81' | llm | 2 | At Murek Brestani had a shot saved at 79', Brannoch FC have had 50% possession since kickoff. The pressure balance over the last 10 minutes of play for Brannoch FC is +0.83. | `At {event:m-42-red_card_swing#464}, {home} have had {value:c1} {label:c1} since kickoff. The {label:c2} for {home} is {value:c2}.` |
| M010 | goal | 84' | llm | 3 | Murek Ymberto scored at 84', making it 1–2. Morvane Athletic have had 69% of the territorial share since kickoff. | `{event:m-42-red_card_swing#494}, making it {score}. {away} have had {value:c2} of the {label:c2} since kickoff.` |
| M011 | score_change | 84' | llm | 1 | Murek Ymberto scored at 84', making it 1–2. Morvane Athletic have had 50% of the ball since kickoff. | `{event:m-42-red_card_swing#494}, making it {score}. {away} have had {value:c2} of the ball since kickoff.` |
| M012 | pressure_shift | 90+1' | template_fallback | 3 | 90+1' — Morvane Athletic take control: pressure balance over the last 10 minutes of play is +1.00 in their favour. Shots since 80': Morvane Athletic 1, Brannoch FC 0. | — |

### Koşu 3 · dominant_loss_seed7

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M003 | dominance_without_reward | 45+1' | llm | 3 | Ombar Belmaro shot off target at 45+1'. Possession Vellorin FC have had 61% of the ball since kickoff. | `{event:m-7-dominant_loss#269}. Possession {home} have had {value:c2} of the ball since kickoff.` |
| M005 | goal | 57' | llm | 1 | Nolvek Ilvanto scored at 57', making it Vellorin FC 0–1 Tessdal Athletic. Possession: Vellorin FC have had 61% of the ball since kickoff. | `{event:m-7-dominant_loss#350}, making it {score_named}. Possession: {home} have had {value:c2} of the ball since kickoff.` |
| M006 | score_change | 57' | llm | 1 | Nolvek Ilvanto scored at 57', making it 0–1. Possession: Vellorin FC have had 61% of the ball since kickoff. | `{event:m-7-dominant_loss#350}, making it {score}. Possession: {home} have had {value:c2} of the ball since kickoff.` |
| M008 | dominance_without_reward | 66' | llm | 2 | Korin Zerimek had a shot blocked at 66'. At 66', Vellorin FC have had 62% of the ball since kickoff and the score is 0–1. | `{event:m-7-dominant_loss#408}. At {minute:c2}, {home} have had {value:c1} of the ball since kickoff and the score is {score}.` |
| M009 | penalty | 70' | llm | 1 | Alvezo Hazulov's penalty was saved at 70'. Possession since kickoff has been 62% for Vellorin FC, and Vellorin FC have 1 penalties saved. | `{event:m-7-dominant_loss#428}. Possession since kickoff has been {value:c2} for {home}, and {home} have {value:c1} {label:c1}.` |

### Koşu 3 · natural_seed100

| Moment | Tip | Dakika | Kaynak | Deneme | Yayınlanan metin | Model şablonu |
|---|---|---|---|---:|---|---|
| M001 | red_card | 14' | llm | 1 | Iveno Gundrel was sent off at 14'. Isteven United have had 51% possession since kickoff and the match is 0–0. | `{event:m-100#84}. {away} have had {value:c2} {label:c2} since kickoff and the match is {score}.` |
| M004 | goal | 29' | llm | 1 | Hesko Ilvanto scored at 29', making it 1–0. Possession: Tessdal Wanderers have had 58% of the ball since kickoff. | `{event:m-100#175}, making it {score}. Possession: {home} have had {value:c3} of the ball since kickoff.` |
| M005 | score_change | 29' | llm | 3 | Hesko Ilvanto scored at 29', making it 1–0. Tessdal Wanderers have had 58% of the ball since kickoff. | `{event:m-100#175}, making it {score}. {home} have had {value:c2} of the ball since kickoff.` |
| M006 | goal | 51' | llm | 1 | Quenlo Pelvisto scored at 51', making it 1–1. Possession for Isteven United since kickoff is 49%. | `{event:m-100#317}, making it {score}. Possession for {away} since kickoff is {value:c2}.` |
| M007 | score_change | 51' | llm | 1 | Quenlo Pelvisto scored at 51', making it 1–1. Possession has been 51% for Tessdal Wanderers since kickoff. | `{event:m-100#317}, making it {score}. Possession has been {value:c3} for {home} since kickoff.` |
| M009 | dominance_without_reward | 79' | llm | 1 | At 79' Rastin Ymberto shot off target at 79'. Possession Tessdal Wanderers have had 54% of the ball since kickoff. | `At {minute:c1} {event:m-100#478}. Possession {home} have had {value:c2} of the ball since kickoff.` |
| M010 | goal | 90+1' | template_fallback | 3 | 90+1' — Brisko Ymberto scores for Tessdal Wanderers. Tessdal Wanderers 2–1 Isteven United. | — |
| M011 | score_change | 90+1' | llm | 1 | Brisko Ymberto scored at 90+1', making it 2–1. Tessdal Wanderers have had 52% of the ball since kickoff. | `{event:m-100#550}, making it {score}. {home} have had {value:c3} of the ball since kickoff.` |
