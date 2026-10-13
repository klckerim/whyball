# Enjeksiyon değerlendirmesi: foundry-v2 (serbest metin) ↔ foundry-v3 (slot)

Bu dosya `python -m eval.inject` ile üretilir; elle düzenlemeyin.

## Yöntem

- Başlangıç: template anlatıcının doğru taslakları (metin + iddialar), tüm momentler, EN ve TR.
- Derlem: 28 maç, 624 taslak. Maçlar: red_card_swing/42, dominant_loss/7, senaryosuz/100, late_comeback/0, late_comeback/1, late_comeback/2, late_comeback/3, late_comeback/4, red_card_swing/0, red_card_swing/1, red_card_swing/2, red_card_swing/3, red_card_swing/4, dominant_loss/0, dominant_loss/1, dominant_loss/2, dominant_loss/3, dominant_loss/4, senaryosuz/0, senaryosuz/1, senaryosuz/2, senaryosuz/3, senaryosuz/4, senaryosuz/5, senaryosuz/6, senaryosuz/7, senaryosuz/8, senaryosuz/9.
- **v2 (serbest metin)**: model metni ve iddiaları serbest yazar; denetim text_lint + verify_claim.
- **v3 (slot)**: model somut değer yazmaz; yer tutuculu şablon + iddialar yazar, değerleri kod doğrulanmış iddialardan ve olay anındaki maç durumundan render eder. Denetim: şablon lint (yer tutucu dışında rakam/sayı kelimesi/isim/home-away/ham metrik adı yasak) + yer tutucu bağlama + verify_claim.
- v3 tabanı: taslaklar deterministik olarak slot şablonuna çevrildi (`slotify`); 624/624 taslak temiz çevrildi, v3 sütunu bunlar üzerinden ölçülür.
- Her hata türü iki yaklaşımın kendi biçiminde, aynı anlamda enjekte edilir (moment + tür + dil seed'li). Uygulanamayan taslak N'ye girmez; "—" o yaklaşımda karşılığı olmayan tür.
- **Yakalandı** = denetim en az bir hata döndürdü; pipeline bu durumda taslağı yayınlamaz.

## Sonuçlar

| Tür | Enjeksiyon | v2 N | v2 yakalama | v3 N | v3 yakalama |
|---|---|---:|---:|---:|---:|
| `control` | Değişiklik yok (yanlış alarm ölçümü) | 624 | 0.0% | 624 | 0.0% |
| `number_text` | Bir sayı yanlış yazılır (v3: yer tutucu yerine ham sayı) | 624 | 88.5% | 624 | 100.0% |
| `number_text_and_claim` | İddia değeri yanlış (v2: metin de birlikte) | 482 | 98.5% | 624 | 97.8% |
| `player_swap` | Oyuncu, aynı maçtan iddiasız başka bir oyuncuyla değişir | 232 | 100.0% | 232 | 100.0% |
| `foreign_player` | Oyuncu, başka maçın oyuncusuyla değişir (v3: ham ad) | 232 | 94.8% | 232 | 100.0% |
| `unsupported_sentence_number` | İddiasız, sayı içeren yeni cümle | 624 | 100.0% | 624 | 100.0% |
| `unsupported_sentence_qualitative` | İddiasız, nitel yeni cümle | 624 | 0.0% | 624 | 0.0% |
| `number_words` | Yanlış sayı yazıyla ("two", "iki") | 480 | 58.3% | 316 | 58.9% |
| `sentence_start_fabricated` | Başa uydurma isimli cümle ("Quintana scores.") | 624 | 0.0% | 624 | 0.0% |
| `score_order_reversed` | Skor sırası ters (deplasman–ev sahibi) | 150 | 0.0% | 150 | 100.0% |
| `raw_side_label` | Takım adı yerine ham "home/away" etiketi | 624 | 0.0% | 624 | 100.0% |
| `free_number` | Serbest yazılmış sayı: başka bir iddianın değeri yanlış yere yazılır | 428 | 0.0% | 298 | 100.0% |
| `wrong_slot_binding` | Yer tutucu yanlış iddiaya bağlanır (iki referans yer değiştirir) | — | — | 264 | 0.0% |

Yanlış alarm (control): v2 0/624, v3 0/624.

Not: yazıyla-sayı denetimi (önceki tek lint düzeltmesi) kapalıyken v2'nin `number_words` yakalaması 0.0%.

## Yakalanmayan türler: foundry-v2 (serbest metin)

### `number_text`: 88.5% yakalandı (72/624 kaçtı)

**Neden:** Lint sayının hangi iddiaya ait olduğuna değil, herhangi bir iddiada geçip geçmediğine bakar; yanlış yerdeki doğru-görünen sayı geçer.

Örnek:

- Orijinal: `22' — Murek Brestani scores for Brannoch FC. Brannoch FC 1–0 Morvane Athletic.`
- Enjekte: `22' — Murek Brestani scores for Brannoch FC. Brannoch FC 1–1 Morvane Athletic.`

### `number_text_and_claim`: 98.5% yakalandı (7/482 kaçtı)

**Neden:** Gevşetilmiş eşitsizlik iddiası (`score_margin lte 0` → `lte 1`) hâlâ doğru kalıyor.

Örnek:

- Orijinal: `34' — Morvane Rovers üstün ama sonuç alamıyor: 14. dakikadan bu yana %60 topa sahip olma ve 5–1 şut, skor ise Kelvara United 1–0 Morvane Rovers.`
- Enjekte: `34' — Morvane Rovers üstün ama sonuç alamıyor: 14. dakikadan bu yana %60 topa sahip olma ve 5–1 şut, skor ise Kelvara United 1–1 Morvane Rovers.`

### `foreign_player`: 94.8% yakalandı (12/232 kaçtı)

**Neden:** Yabancı oyuncunun soyadı iddiadaki oyuncuyla aynı; soyad takma ad olarak destekli, ad "—" sonrası cümle başında.

Örnek:

- Orijinal: `89' — Nolvek Selvado scores for Drunmark Rovers. Drunmark Rovers 3–2 Ostmere United.`
- Enjekte: `89' — Tamsel Selvado scores for Drunmark Rovers. Drunmark Rovers 3–2 Ostmere United.`

### `unsupported_sentence_qualitative`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümlede ne sayı ne yeni bir isim var; nitel yargılar lint ve verify'ın kapsamı dışında.

Örnek:

- Orijinal: `13' — Brannoch FC take control: pressure balance +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`
- Enjekte: `13' — Brannoch FC take control: pressure balance +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0. Brannoch FC were the better side.`

### `number_words`: 58.3% yakalandı (200/480 kaçtı)

**Neden:** Belirsiz kelime (TR "bir", EN "one") ardından sayılabilir bir isim gelmediği için sayı sayılmıyor ("bir ara", "one of" gibi kullanımlarda yanlış alarmı önlemek için). Ya da Lint sayının hangi iddiaya ait olduğuna değil, herhangi bir iddiada geçip geçmediğine bakar; yanlış yerdeki doğru-görünen sayı geçer.

Örnek:

- Orijinal: `22' — Gol! Murek Brestani (Brannoch FC) ağları buldu. Skor: Brannoch FC 1–0 Morvane Athletic.`
- Enjekte: `22' — Gol! Murek Brestani (Brannoch FC) ağları buldu. Skor: Brannoch FC 1–bir Morvane Athletic.`

### `sentence_start_fabricated`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümle başındaki tek büyük harfli kelime isim sayılmıyor (cümle başı büyük harfi normal); kadroda olmayan tek kelimelik isim bu konumda fark edilmiyor.

Örnek:

- Orijinal: `13' — Brannoch FC take control: pressure balance +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`
- Enjekte: `Quintana scores. 13' — Brannoch FC take control: pressure balance +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`

### `score_order_reversed`: 0.0% yakalandı (150/150 kaçtı)

**Neden:** Her iki skor rakamı da bir skor iddiasında geçiyor; lint sırayı bilmiyor.

Örnek:

- Orijinal: `22' — Murek Brestani scores for Brannoch FC. Brannoch FC 1–0 Morvane Athletic.`
- Enjekte: `22' — Murek Brestani scores for Brannoch FC. Brannoch FC 0–1 Morvane Athletic.`

### `raw_side_label`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Küçük harfli "home side" ne sayı ne isim; v2 lint'i etiketleri denetlemiyor.

Örnek:

- Orijinal: `13' — Brannoch FC take control: pressure balance +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`
- Enjekte: `13' — the home side take control: pressure balance +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`

### `free_number`: 0.0% yakalandı (428/428 kaçtı)

**Neden:** Lint sayının hangi iddiaya ait olduğuna değil, herhangi bir iddiada geçip geçmediğine bakar; yanlış yerdeki doğru-görünen sayı geçer.

Örnek:

- Orijinal: `13' — Brannoch FC take control: pressure balance +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`
- Enjekte: `13' — Brannoch FC take control: pressure balance +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 1.`

## Yakalanmayan türler: foundry-v3 (slot)

### `number_text_and_claim`: 97.8% yakalandı (14/624 kaçtı)

**Neden:** Gevşetilmiş eşitsizlik iddiası (`score_margin lte 0` → `lte 1`) hâlâ doğru kalıyor; verify değerin doğruluğunu ölçer, sınırın sıkılığını değil.

Örnek:

- Orijinal: `{minute:c1} — {home} üstün ama sonuç alamıyor: {start:c1}. dakikadan bu yana {value:c1} topa sahip olma ve {value:c2}–{value:c3} şut, skor ise {score}.`
- Enjekte: `{minute:c1} — {home} üstün ama sonuç alamıyor: {start:c1}. dakikadan bu yana {value:c1} topa sahip olma ve {value:c2}–{value:c3} şut, skor ise {score}.`

### `unsupported_sentence_qualitative`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümlede ne sayı ne yeni bir isim var; nitel yargılar lint ve verify'ın kapsamı dışında.

Örnek:

- Orijinal: `{minute:c1} — {home} take control: pressure balance {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `{minute:c1} — {home} take control: pressure balance {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}. {home} were the better side.`

### `number_words`: 58.9% yakalandı (130/316 kaçtı)

**Neden:** Belirsiz kelime (TR "bir", EN "one") ardından sayılabilir bir isim gelmediği için sayı sayılmıyor ("bir ara", "one of" gibi kullanımlarda yanlış alarmı önlemek için).

Örnek:

- Orijinal: `{minute:c1} — {home} take control: pressure balance {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `{minute:c1} — {home} take control: pressure balance {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} one.`

### `sentence_start_fabricated`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümle başındaki tek büyük harfli kelime isim sayılmıyor (cümle başı büyük harfi normal); kadroda olmayan tek kelimelik isim bu konumda fark edilmiyor.

Örnek:

- Orijinal: `{minute:c1} — {home} take control: pressure balance {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `Quintana scores. {minute:c1} — {home} take control: pressure balance {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}.`

### `wrong_slot_binding`: 0.0% yakalandı (264/264 kaçtı)

**Neden:** Her yer tutucu doğru türde ve doğrulanmış bir iddiaya bağlı; hangi iddianın cümlede nereye ait olduğu denetlenmiyor (v3'ün yeni açığı).

Örnek:

- Orijinal: `{minute:c1} — {home} take control: pressure balance {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `{minute:c1} — {home} take control: pressure balance {value:c2} in their favour. Shots since {start:c2}: {home} {value:c1}, {away} {value:c3}.`

## Yeniden üretme

```
.venv/bin/python -m eval.inject
```
