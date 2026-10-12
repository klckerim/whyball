# WhyBall Demo Veri Seti — Datasheet

## 1. Amaç ve kapsam

WhyBall'ın analytics, moment detector ve anlatı (explain + verifier) aşamalarını beslemek için üretilmiş **tamamen sentetik** futbol maçı olay akışları.

- Her maç bir tamsayı seed'den deterministik olarak üretilir. Aynı seed ve senaryo her ortamda bayt bayt aynı dosyayı verir.
- Takım ve oyuncu adları uydurma isim havuzlarından ([app/generator/names.py](../app/generator/names.py)) seçilir. Gerçek kulüp, oyuncu ya da maç içermez.
- Kişisel veri yoktur.

## 2. Üretim yöntemi

Kaynak: [app/generator/engine.py](../app/generator/engine.py). Üretimde LLM kullanılmaz.

- **Rastgelelik:** Tek bir `random.Random(seed)` örneği. Global `random`, saat, `uuid` ya da hash/set sırası kullanılmaz.
- **Model:** Topa sahiplik durum makinesi. Saat her adımda 2–20 sn ilerler. Topa sahip takım için ağırlıklı bir aksiyon seçilir: pas, top sürme, şut, faul, ofsayt. Topun rakip kaleye yakınlığı (`progress`) şut ve ofsayt olasılığını belirler.
  - **Şut** → gol / kurtarış / blok / aut. Blok ve kurtarış kornere dönebilir.
  - **Faul** → kart çıkabilir. Ceza sahasındaki faulün bir kısmı penaltıyla sonuçlanır.
  - **Diğer:** 2. devrede 1–3 oyuncu değişikliği. Sahadaki her eksik oyuncu top kaybı olasılığını artırır.
- **Kalibrasyon:** Senaryosuz modda, 3000 seed üzerinden maç başı ortalamalar:

  | Gol | Şut | Korner | Sarı | Kırmızı | Penaltı |
  |---|---|---|---|---|---|
  | 2.8 | 20.2 | 5.3 | 3.9 | 0.10 | 0.25 |

  Bu ortalamalar geniş aralıklarla test edilir (`test_averages_over_200_seeds_are_realistic`).
- **Determinizm güvencesi:** `tests/test_generator.py`, aynı seed'in aynı süreçte ve farklı `PYTHONHASHSEED` ile açılan ayrı süreçlerde aynı çıktıyı verdiğini doğrular. `tests/test_demo_fixtures.py`, repodaki demo dosyalarının üretici çıktısıyla SHA-256 düzeyinde aynı olduğunu doğrular.

## 3. Şema (sürüm 1)

Biçim: JSONL. Her satır bir olaydır. Anahtarlar alfabetik sıralıdır, ayraçlarda boşluk yoktur, satır sonu `\n`, kodlama UTF-8.

### Olay alanları

| Alan | Tip | Null olabilir | Anlam |
|---|---|---|---|
| `match_id` | string | hayır | `m-{seed}` ya da `m-{seed}-{senaryo}` |
| `seq` | int | hayır | 0'dan başlayan, boşluksuz sıra numarası |
| `period` | int | hayır | 1 ya da 2 |
| `minute`, `second` | int | hayır | Maç saati. 2. devre 45:00'ten başlar; uzatmalar 45+ / 90+ dakika olarak devam eder. Sıralama `(period, minute, second)` ile yapılmalı. |
| `type` | string | hayır | Olay tipi, aşağıdaki tabloya bakın |
| `team` | string | evet | `home` / `away`. Olayı yapan (faul ve kartta cezayı alan) takım |
| `player` | string | evet | Olayı yapan oyuncu |
| `x`, `y` | float | evet | Top konumu, 105×68 saha, 1 ondalık. `home` her iki devrede de x=105 yönüne hücum eder. Kart, değişiklik ve devre olaylarında null. |
| `outcome` | string | evet | Pas/top sürme: `success`/`fail`. Şut: `goal`/`saved`/`blocked`/`off_target`. Penaltı: `scored`/`saved`/`missed`. |
| `score` | object | hayır | Olay **sonrası** skor: `{"away": int, "home": int}` |
| `data` | object | evet | Tipe özel ek bilgi |

### Olay tipleri

| Tip | `team` / `player` | `data` |
|---|---|---|
| `match_meta` | null | `schema`, `seed`, `scenario`, `teams.{home,away}.{name, lineup[11], bench[5]}` (lineup[0] kaleci) |
| `kickoff` | santrayı yapan | — |
| `pass`, `dribble` | topa sahip takım | — |
| `shot` | şutu atan | — |
| `goal` | golü atan; her zaman bir `shot(goal)` ya da `penalty(scored)` olayından sonra gelir | — |
| `save` | kurtarışı yapan kaleci | — |
| `foul` | faulü yapan | — |
| `yellow_card` | kartı gören | — |
| `red_card` | oyundan atılan | `reason`: `straight_red` / `second_yellow` |
| `penalty` | penaltıyı kullanan; her zaman bir `foul` olayından sonra gelir (araya o faulün kartı girebilir) | — |
| `corner` | kornere giden takım | — |
| `offside` | ofsayta düşen | — |
| `substitution` | **çıkan** oyuncu | `player_in`: giren oyuncu |
| `half_time`, `full_time` | null | — |

### Değişmezler (testlerle güvence altında)

- `seq` boşluksuz artar. Zaman `(period, minute, second)` sırasında azalmaz.
- Akış `match_meta` → `kickoff` ile başlar, `full_time` ile biter. Tam olarak bir `half_time` vardır.
- Her olaydaki `score`, o ana kadarki `goal` olaylarının sayısına eşittir.
- Sahada hiçbir anda 11'den fazla oyuncu olmaz. Olaya karışan oyuncu o an sahadadır.
- Kırmızı kartla ya da değişiklikle çıkan oyuncu bir daha görünmez. Giren oyuncu yedekten gelir.

## 4. Senaryo modu

Kaynak: [app/generator/scenarios.py](../app/generator/scenarios.py). Senaryo, belirli dakikalarda gerçekleşecek zorunlu olayların listesidir: gol, kırmızı kart, penaltı (sonucu belirtilmiş).

> **Senaryo modunda gol ve penaltılar betiktir, kendiliğinden gol olmaz.**
> Skor yalnızca senaryodaki zorunlu olaylardan oluşur. Doğal akışta gol olacak şutlar kurtarışa, doğal penaltılar `saved` sonucuna çevrilir. Bu yüzden son skor her seed'de senaryonun öngördüğü skordur.
> Diğer her şey (pas, şut, korner, faul, kart, değişiklik) seed'e göre doğal üretilir. Senaryo maçlarında betik dışı kırmızı kart da görülebilir.

| Senaryo | Zorunlu olaylar | Sonuç | Ek ayar |
|---|---|---|---|
| `late_comeback` | away gol 18', 52' · home gol 74' · home penaltı (gol) 83' · home gol 89' | 3-2 | — |
| `red_card_swing` | home gol 22' · home kırmızı 38' · away gol 61', 84' | 1-2 | — |
| `dominant_loss` | away gol 57' · home penaltı (kurtarış) 70' | 0-1 | `turnover_factor` home 0.45 / away 1.25 · `tempo` home 0.5 |

- `turnover_factor`: pas ve top sürmede top kaybı olasılığı çarpanı. 1.0 normaldir, 1'in altı topa daha hâkim takım demektir.
- `tempo`: pas ve top sürmede ileri gidiş çarpanı. 1'in altı sabırlı oyun kurmayı temsil eder.
- **Zamanlama:** Zorunlu olay tam belirtilen dakikada (`mm:00`) gerçekleşir. Hemen önce bir gol kutlaması olduysa en fazla 1 dakika kayabilir.

## 5. Demo maçları

Konum: `data/demo/`. Bu dosyalar dondurulmuştur; üretici değişirse `tests/test_demo_fixtures.py` başarısız olur.

| Dosya | Senaryo | Seed | Takımlar (home – away) | Skor | Olay | SHA-256 (ilk 12) |
|---|---|---|---|---|---|---|
| `red_card_swing_seed42.jsonl` | red_card_swing | 42 | Brannoch FC – Morvane Athletic | 1-2 | 541 | `f3cd306f1213` |
| `dominant_loss_seed7.jsonl` | dominant_loss | 7 | Vellorin FC – Tessdal Athletic | 0-1 | 573 | `523edd6027a9` |
| `natural_seed100.jsonl` | — | 100 | Tessdal Wanderers – Isteven United | 2-1 | 568 | `8ee57c212c35` |

**red_card_swing, seed 42:** Brannoch 22'de öne geçer, 38'de direkt kırmızıyla 10 kişi kalır. Morvane 61' ve 84'teki gollerle maçı çevirir. Şut: home 5, away 15.

**dominant_loss, seed 7:** Vellorin topa hâkimdir. Pas ve top sürme payı %58, şut 28'e 1, korner 7'ye 0. Tessdal tek şutunu 57'de gole çevirir. Vellorin'in 70'teki penaltısını kaleci kurtarır.

**natural (senaryosuz), seed 100:** Isteven 14'te direkt kırmızıyla 10 kişi kalır. Tessdal 29'da öne geçer, Isteven 51'de eşitler, Tessdal 90:13'te galibiyet golünü bulur. Şut: home 19, away 4.

## 6. Bilinen sınırlamalar

- Serbest vuruş, taç ve kale vuruşu ayrı olay olarak yoktur. Faul sonrası top faule uğrayan takımda kalır.
- Taraflar devre arasında yer değiştirmez (`home` her zaman x=105 yönüne hücum eder).
- Tek bir maçta topa sahip olma payı seed'e bağlı olarak yaklaşık ±0.04 oynar. `dominant_loss` hâkimiyeti ortalamada belirgindir (%61), tek maçta %50'ye kadar düşebilir.
- Senaryo olayları tam dakika başında (`mm:00`) gerçekleşir. Doğal olaylar ise saniye düzeyinde dağılır. Bu fark betik olayları ayırt edilebilir kılar; değerlendirmede bunun bilinmesi gerekir.
- `dominant_loss`'ta zayıf takımın şut sayısı çok düşüktür (ortalama ~3, seed 7'de 1).
- Kalibrasyon sadece maç başı toplam sayılara yapılmıştır. Oyuncu bazlı dağılımlar (kimin şut attığı vb.) düzgün rastgeledir, mevki modeli yoktur.

## 7. Yeniden üretme

Üretici **bilerek** değiştirildiyse:

```
.venv/bin/python -m app.generator.freeze
```

Komut üç dosyayı yeniden yazar ve 5. bölümdeki tablonun satırlarını basar. Ardından:
1. 5. bölümdeki tabloyu ve maç hikâyelerini güncelleyin.
2. `.venv/bin/pytest -q` çalıştırın.

Tek bir maç üretmek için:

```
.venv/bin/python -m app.generator --seed 42 [--scenario late_comeback|red_card_swing|dominant_loss] [--out match.jsonl]
```
