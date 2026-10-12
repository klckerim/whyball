# Enjeksiyon değerlendirmesi

Anlatım hattının (text_lint + verify_claim) kontrollü hataları yakalama oranı. Bu dosya `python -m eval.inject` ile üretilir; elle düzenlemeyin.

## Yöntem

- Başlangıç: template anlatıcının doğru taslakları (metin + iddialar), tüm momentler, EN ve TR.
- Derlem: 28 maç, 624 taslak. Maçlar: red_card_swing/42, dominant_loss/7, senaryosuz/100, late_comeback/0, late_comeback/1, late_comeback/2, late_comeback/3, late_comeback/4, red_card_swing/0, red_card_swing/1, red_card_swing/2, red_card_swing/3, red_card_swing/4, dominant_loss/0, dominant_loss/1, dominant_loss/2, dominant_loss/3, dominant_loss/4, senaryosuz/0, senaryosuz/1, senaryosuz/2, senaryosuz/3, senaryosuz/4, senaryosuz/5, senaryosuz/6, senaryosuz/7, senaryosuz/8, senaryosuz/9.
- Her hata türü her taslağa deterministik olarak (moment id + tür + dil seed'li) enjekte edilir; uygulanamadığı taslaklar (örn. metinde oyuncu adı yoksa) N'ye girmez.
- **Yakalandı** = `check_draft` en az bir lint ya da verify hatası döndürdü; pipeline bu durumda taslağı yayınlamaz, geri bildirimle yeniden dener ya da template yedeğine düşer.
- **Önce** = yazıyla sayı denetimi kapalı (`lint_number_words=False`), **Sonra** = açık (mevcut varsayılan). Lint/Verify sütunları düzeltme sonrası, hangi katmanın uyardığını gösterir (ikisi birden uyarabilir).

## Sonuçlar

| Tür | Enjeksiyon | N | Önce | Sonra | Lint | Verify |
|---|---|---:|---:|---:|---:|---:|
| `control` | Değişiklik yok (yanlış alarm ölçümü) | 624 | 0.0% | 0.0% | 0.0% | 0.0% |
| `number_text` | Metindeki bir sayı değişir, iddialar aynı kalır | 624 | 87.7% | 87.7% | 87.7% | 0.0% |
| `number_text_and_claim` | Metin ve ilgili iddia birlikte yanlış değere değişir | 482 | 98.5% | 98.5% | 3.3% | 98.5% |
| `player_swap` | Oyuncu adı aynı maçtan iddiasız başka bir oyuncuyla değişir | 232 | 100.0% | 100.0% | 100.0% | 0.0% |
| `foreign_player` | Oyuncu adı başka maçın oyuncusuyla değişir | 232 | 96.1% | 96.1% | 96.1% | 0.0% |
| `unsupported_sentence_number` | İddiasız, sayı içeren yeni cümle eklenir | 624 | 100.0% | 100.0% | 100.0% | 0.0% |
| `unsupported_sentence_qualitative` | İddiasız, nitel yeni cümle eklenir (sayı/yeni isim yok) | 624 | 0.0% | 0.0% | 0.0% | 0.0% |
| `number_words` | Bir tamsayı, yanlış değerin yazısıyla değişir ("two", "iki") | 480 | 0.0% | 61.7% | 61.7% | 0.0% |
| `sentence_start_fabricated` | Başa uydurma isimli cümle eklenir ("Quintana scores.") | 624 | 0.0% | 0.0% | 0.0% | 0.0% |

Yanlış alarm (control): 0/624.

## Yakalanmayan türler

### `number_text`: 87.7% yakalandı (77/624 kaçtı)

**Neden:** Yeni sayı tesadüfen başka bir iddianın değeri ya da dakikasıyla aynı. Lint, sayının hangi iddiaya ait olduğuna değil, herhangi bir iddiada geçip geçmediğine bakar.

Örnek:

- Orijinal: 32' — Baskı Morvane Athletic tarafına geçti: baskı dengesi +1.00. 22. dakikadan bu yana şutlar: Morvane Athletic 2, Brannoch FC 0.
- Enjekte: 32' — Baskı Morvane Athletic tarafına geçti: baskı dengesi +1.00. 22. dakikadan bu yana şutlar: Morvane Athletic 2, Brannoch FC 1.

### `number_text_and_claim`: 98.5% yakalandı (7/482 kaçtı)

**Neden:** Değişen iddia bir eşitsizlik (`score_margin lte 0` → `lte 1`) ve gevşetilmiş hâliyle hâlâ doğru; metinde değişen sayı da bu iddianın yeni değerine denk geldiği için lint de geçiyor. Verify değerin doğruluğunu ölçer, sınırın ne kadar sıkı olduğunu değil.

Örnek:

- Orijinal: 56' — Zoryk FC dominate without reward: 58% of possession and 6–0 shots since 45', yet the score is Tessdal FC 1–0 Zoryk FC.
- Enjekte: 56' — Zoryk FC dominate without reward: 58% of possession and 6–1 shots since 45', yet the score is Tessdal FC 1–0 Zoryk FC.

### `foreign_player`: 96.1% yakalandı (9/232 kaçtı)

**Neden:** Yabancı oyuncunun soyadı iddiadaki oyuncunun soyadıyla aynı (örn. "Tamsel Selvado" ↔ "Davel Selvado"). Soyad, iddialı oyuncunun takma adı olarak destekli sayılıyor; ad ise "—" sonrası cümle başında olduğu için tek kelimelik isim denetimine girmiyor.

Örnek:

- Orijinal: 61' — Davel Selvado scores for Morvane Athletic. Brannoch FC 1–1 Morvane Athletic.
- Enjekte: 61' — Tamsel Selvado scores for Morvane Athletic. Brannoch FC 1–1 Morvane Athletic.

### `unsupported_sentence_qualitative`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümlede ne sayı ne de yeni bir isim var. Lint yalnızca sayıları ve isimleri denetler, verify_claim de yalnızca Claim listesini doğrular; nitel yargılar kapsam dışında.

Örnek:

- Orijinal: 13' — Brannoch FC take control: pressure balance +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.
- Enjekte: 13' — Brannoch FC take control: pressure balance +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0. Brannoch FC were the better side.

### `number_words`: 61.7% yakalandı (184/480 kaçtı)

**Neden:** Yazıyla yazılan değer tesadüfen başka bir iddiada geçiyor; ya da belirsiz kelime (TR "bir", EN "one") sayılabilir bir isimden önce gelmediği için sayı sayılmıyor.

Kaçış dağılımı:

- belirsiz kelime, ardında sayılabilir isim yok: 150
- değer başka bir iddiada geçiyor: 34

Örnek:

- Orijinal: 13' — Baskı Brannoch FC tarafına geçti: baskı dengesi +0.75. 3. dakikadan bu yana şutlar: Brannoch FC 1, Morvane Athletic 0.
- Enjekte: 13' — Baskı Brannoch FC tarafına geçti: baskı dengesi +0.75. 3. dakikadan bu yana şutlar: Brannoch FC 1, Morvane Athletic bir.

### `sentence_start_fabricated`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümle başındaki tek büyük harfli kelime isim olarak değerlendirilmiyor (cümle başı büyük harfi normal). Kadroda olmayan tek kelimelik isim bu konumda fark edilmiyor.

Örnek:

- Orijinal: 13' — Brannoch FC take control: pressure balance +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.
- Enjekte: Quintana scores. 13' — Brannoch FC take control: pressure balance +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.

## Yapılan düzeltme

Yalnızca yazıyla yazılmış sayılar lint'e eklendi (EN zero–twenty, TR sıfır–yirmi, "on bir" gibi çok kelimeliler dahil). Kural rakamla yazılmış tamsayıyla aynı: değer bir iddiada geçmeli. Sayı dışında da sık kullanılan kelimeler (TR "bir", "yedi", "altı"; EN "one") yalnızca ardından sayılabilir bir isim (gol, şut, goal, shot…) gelirse sayı sayılır. Diğer açıklar bilinçli olarak kapatılmadı.

## Yeniden üretme

```
.venv/bin/python -m eval.inject
```
