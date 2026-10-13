# Enjeksiyon değerlendirmesi: foundry-v2 ↔ foundry-v3 ↔ foundry-v4 ↔ foundry-v4.1 ↔ foundry-v5

Bu dosya `python -m eval.inject` ile üretilir; elle düzenlemeyin.

## Yöntem

- Başlangıç: template anlatıcının doğru taslakları (metin + iddialar), tüm momentler, EN ve TR.
- Derlem: 28 maç, 624 taslak. Maçlar: red_card_swing/42, dominant_loss/7, senaryosuz/100, late_comeback/0, late_comeback/1, late_comeback/2, late_comeback/3, late_comeback/4, red_card_swing/0, red_card_swing/1, red_card_swing/2, red_card_swing/3, red_card_swing/4, dominant_loss/0, dominant_loss/1, dominant_loss/2, dominant_loss/3, dominant_loss/4, senaryosuz/0, senaryosuz/1, senaryosuz/2, senaryosuz/3, senaryosuz/4, senaryosuz/5, senaryosuz/6, senaryosuz/7, senaryosuz/8, senaryosuz/9.
- **v2 (serbest metin)**: model metni ve iddiaları serbest yazar; denetim text_lint + verify_claim (v2 kuralları: yalnızca-soyad denetimi kapalı).
- **v3 (slot)**: model somut değer yazmaz; yer tutuculu şablon + iddialar yazar, değerleri kod doğrulanmış iddialardan render eder. Denetim: şablon lint (yer tutucu dışında rakam/sayı kelimesi/isim/home-away/ham metrik adı yasak) + yer tutucu bağlama + verify_claim (v3 kuralları).
- **v4 (slot + {event:} + sıkı lint)**: olay bilgisi yalnızca `{event:<id>}` ile gelir (kod olayın standart ifadesini veriden üretir; olay bir iddianın dayanağı olmalı), metrik adları `{label:}` ile; `{score}` takım adsız "1–0", `{score_named}` takım adlı. Lint ek olarak olay tipi / rol sözcüklerini, izinli listede olmayan cümle başlarını, bağlamdan bağımsız yazıyla sayıları ve moment tipinin desteklemediği nitel abartıyı reddeder.
- **v4.1**: v4 tabanı, ek kurallar: `{event:}` yalnızca moment tipinin izinli olay tiplerinden (pas, çalım, ofsayt, faul, korner, kurtarış seçilemez), aynı cümlede `{event:X}` ile X'in oyuncusunun `{player:}`'ı birlikte yazılamaz, takım yer tutucusundan önce "the" yazılamaz, izinli cümle başı listesinden "They" çıktı (zamirler listeye girmez).
- **v5 (claim menüsü)**: iddiaları kod kurar ve doğrular (`app/explain/menu.py`); model iddia ve olay bağlamaz, yalnızca menü id'lerini (`{value:}`, `{minute:}`, `{start:}`, `{label:}`, `{clause:}`, menü kanıtı olan `{event:}`, `{score}`) kullanır. Ek kurallar: menüde olmayan id, menü iddiasına dayanmayan cümle, dominance/pressure momentinde ana iddianın kullanılmaması ve bir cümlede aynı dakikanın iki kez geçmesi reddedilir; izinli cümle başı EN yalnızca "The". Model iddia yazmadığı için iddiayı değiştiren enjeksiyonlar (`number_text_and_claim`) v5'te "—".
- Tabanlar: v3 `slotify` 624/624, v4 `slotify_v4` 624/624, v5 `slotify_v5` 624/624 taslak temiz çevrildi (v4 tabanı hem v4 hem v4.1 kurallarından geçer); sütunlar bunlar üzerinden ölçülür.
- Her hata türü her yaklaşımın kendi biçiminde, aynı anlamda enjekte edilir (moment + tür + dil + sürüm seed'li). Uygulanamayan taslak N'ye girmez; "—" o yaklaşımda karşılığı olmayan tür. "(yeni, v4)" / "(yeni, v4.1)" işaretli türler o sürümle eklendi.
- **Yakalandı** = denetim en az bir hata döndürdü; pipeline bu durumda taslağı yayınlamaz.

## Sonuçlar

| Tür | Enjeksiyon | v2 N | v2 yakalama | v3 N | v3 yakalama | v4 N | v4 yakalama | v4.1 N | v4.1 yakalama | v5 N | v5 yakalama |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `control` | Değişiklik yok (yanlış alarm ölçümü) | 624 | 0.0% | 624 | 0.0% | 624 | 0.0% | 624 | 0.0% | 624 | 0.0% |
| `number_text` | Bir sayı yanlış yazılır (v3/v4: yer tutucu yerine ham sayı) | 624 | 88.5% | 624 | 100.0% | 316 | 100.0% | 316 | 100.0% | 316 | 100.0% |
| `number_text_and_claim` | İddia değeri yanlış (v2: metin de birlikte) | 482 | 98.5% | 624 | 97.8% | 624 | 97.9% | 624 | 97.9% | — | — |
| `player_swap` | Oyuncu, aynı maçtan iddiasız başka bir oyuncuyla değişir (v4: tabanda {player:} yok, karşılığı `event_wrong_claim`) | 232 | 100.0% | 232 | 100.0% | — | — | — | — | — | — |
| `foreign_player` | Oyuncu, başka maçın oyuncusuyla değişir (v3/v4: ham ad) | 232 | 94.8% | 232 | 100.0% | 360 | 100.0% | 360 | 100.0% | 360 | 100.0% |
| `unsupported_sentence_number` | İddiasız, sayı içeren yeni cümle | 624 | 100.0% | 624 | 100.0% | 624 | 100.0% | 624 | 100.0% | 624 | 100.0% |
| `unsupported_sentence_qualitative` | İddiasız, nitel yeni cümle ("were the better side") | 624 | 0.0% | 624 | 0.0% | 624 | 0.0% | 624 | 0.0% | 624 | 100.0% |
| `number_words` | Yanlış sayı yazıyla ("two", "iki") | 480 | 57.9% | 316 | 57.0% | 316 | 100.0% | 316 | 100.0% | 316 | 100.0% |
| `sentence_start_fabricated` | Başa uydurma isimli cümle ("Quintana scores.") | 624 | 0.0% | 624 | 0.0% | 624 | 100.0% | 624 | 100.0% | 624 | 100.0% |
| `score_order_reversed` | Skor sırası ters (deplasman–ev sahibi) | 150 | 0.0% | 150 | 100.0% | 240 | 100.0% | 240 | 100.0% | 240 | 100.0% |
| `raw_side_label` | Takım adı yerine ham "home/away" etiketi | 624 | 0.0% | 624 | 100.0% | 316 | 100.0% | 316 | 100.0% | 316 | 100.0% |
| `free_number` | Serbest yazılmış sayı: başka bir iddianın değeri yanlış yere yazılır | 428 | 0.0% | 298 | 100.0% | 298 | 100.0% | 298 | 100.0% | 298 | 100.0% |
| `wrong_slot_binding` | Yer tutucu yanlış iddiaya bağlanır (iki referans yer değiştirir) | — | — | 264 | 0.0% | 264 | 0.0% | 264 | 0.0% | 264 | 0.0% |
| `role_reversed` (yeni, v4) | Rol ters: olay cümlesi oyuncunun ters rolüyle yazılır (penaltıyı kullanan "saved a penalty") | 232 | 0.0% | 232 | 0.0% | 232 | 64.2% | 232 | 64.2% | 232 | 72.0% |
| `event_wrong_claim` (yeni, v4) | Yanlış iddiaya bağlı yer tutucu: olay başka bir gerçek olaya bağlanır (v4: {event:} başka olay; v2/v3: olay cümlesinin oyuncusu o olayın oyuncusu) | 135 | 100.0% | 138 | 100.0% | 248 | 95.2% | 248 | 95.2% | 248 | 80.2% |
| `sentence_start_fabricated_name` (yeni, v4) | Rastgele bir cümle sınırına uydurma adla, olay sözcüğü ve sayı içermeyen cümle ("Ravello pressed high.") | 624 | 0.0% | 624 | 0.0% | 624 | 100.0% | 624 | 100.0% | 624 | 100.0% |
| `qualitative_overstatement` (yeni, v4) | Moment tipinin desteklemediği nitel abartı cümlesi (bağımsız yazılmış listeden) | 624 | 0.0% | 624 | 0.0% | 624 | 54.5% | 624 | 54.5% | 624 | 100.0% |
| `player_repeat` (yeni, v4.1) | Oyuncu tekrarı: olay cümlesine olayın oyuncusu yeniden eklenir ("scored at 90+1' by X"; v4/v4.1: {event:} + aynı oyuncunun {player:}) | 232 | 0.0% | 150 | 0.0% | 232 | 0.0% | 232 | 100.0% | 232 | 100.0% |
| `unknown_menu_id` (yeni, v5) | Tanımsız id'ye başvuru: bir iddia yer tutucusu iddialarda / menüde olmayan bir id'ye bağlanır (v5: makul görünen `possession_since_kickoff`) | — | — | 624 | 100.0% | 580 | 100.0% | 580 | 100.0% | 580 | 100.0% |

Yanlış alarm (control): v2 0/624, v3 0/624, v4 0/624, v4.1 0/624, v5 0/624.

Not: yazıyla-sayı denetimi kapalıyken v2'nin `number_words` yakalaması 0.0%.

Not (v5): `unsupported_sentence_qualitative` ve `qualitative_overstatement` taslağa *ayrı bir cümle* olarak eklenir; v5 bunları `sentence_without_claim` ile yakalar (cümlede menü iddiası yok). Aynı yargı menü iddiasına dayanan bir cümlenin içine yazılırsa ("{clause:possession}, and {home} were the better side") v5 de geçirir: nitel yargının kendisi hâlâ denetlenmiyor.

## Verifier ajanının hedefi

Deterministik denetimin (lint + yer tutucu bağlama + verify_claim) kaçırdığı hata türleri, sürüm başına. Bunlar kural listesiyle kapatılamayan, cümlenin anlamına bakmayı gerektiren açıklar; bir Verifier ajanının hedeflemesi gereken liste budur. Güncel sürüm (foundry-v4.1) en üstte.

### Yakalanmayan türler: foundry-v5 (claim menüsü + yan cümleler)

#### `wrong_slot_binding`: 0.0% yakalandı (264/264 kaçtı)

**Neden:** Menü id'si doğru ve doğrulanmış, ama cümlede yanlış yerde: menü bir {value:}'nun hangi takıma / hangi söze ait olduğunu bilmiyor ("{home} {value:shots_against}"). Yalnızca {value:} yerleştiren şablonlarda ölçülür; {clause:} kullanan şablonda takas edilecek değer yok, değerleri yan cümleyi kod yazar.

Örnek:

- Orijinal: `{minute:pressure} — {home} take control: {label:pressure} {value:pressure} in their favour. {label:shots_for} since {start:shots_for}: {home} {value:shots_for}, {away} {value:shots_against}.`
- Enjekte: `{minute:pressure} — {home} take control: {label:pressure} {value:shots_for} in their favour. {label:shots_for} since {start:shots_for}: {home} {value:pressure}, {away} {value:shots_against}.`

#### `role_reversed`: 72.0% yakalandı (65/232 kaçtı)

**Neden:** Ters rol, olay sözcüğü yasak listesinde olmayan bir fiille yazıldığında ("kept it out", "victim of the challenge", "topu çizgiden çıkardı") yakalanmıyor; yakalama sözlüğe dayanıyor.

Kaçan ifadeler / adlar: `kept it out at m`×28, `topu çizgiden çıkardı (m)`×24, `was the victim of the challenge at m`×5, `kept the kick out at m`×4, `sert müdahaleye maruz kaldı (m)`×4

Örnek:

- Orijinal: `{event:m-42-red_card_swing#213}. {home} sahada {value:players} kişi kaldı.`
- Enjekte: `{player:h08} sert müdahaleye maruz kaldı ({minute:sent_off}). {home} sahada {value:players} kişi kaldı.`

#### `event_wrong_claim`: 80.2% yakalandı (49/248 kaçtı)

**Neden:** Menü kanıtları eksiksiz olduğu için (ör. maç başından beri tüm goller) yanlış olay çoğu zaman bir menü iddiasının kanıtı; {event:} bağlama kuralı cümledeki rolü değil kanıt üyeliğini denetler.

Kaçan ifadeler / adlar: `goal, bir iddianın kanıtı`×49

Örnek:

- Orijinal: `{event:m-42-red_card_swing#494}, making it {score_named}.`
- Enjekte: `{event:m-42-red_card_swing#359}, making it {score_named}.`

### Yakalanmayan türler: foundry-v4.1 (+ olay tipi izin listesi, oyuncu tekrarı, zamir/artikel)

#### `number_text_and_claim`: 97.9% yakalandı (13/624 kaçtı)

**Neden:** Gevşetilmiş eşitsizlik iddiası (`score_margin lte 0` → `lte 1`) hâlâ doğru kalıyor. Verify değerin doğruluğunu ölçer, sınırın sıkılığını değil.

Örnek:

- Orijinal: `{minute:c1} — {home} dominate without reward: since {start:c1} they have had {value:c1} of the ball and a {value:c2}–{value:c3} lead in {label:c2}, yet the score is {score_named}.`
- Enjekte: `{minute:c1} — {home} dominate without reward: since {start:c1} they have had {value:c1} of the ball and a {value:c2}–{value:c3} lead in {label:c2}, yet the score is {score_named}.`

#### `unsupported_sentence_qualitative`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümle yer tutucuyla başlıyor, sayı ve olay sözcüğü yok; "were the better side" nitel abartı listesinde değil (abartı değil, yargı). Nitel yargılar v4'te de kapsam dışında.

Örnek:

- Orijinal: `{minute:c1} — {home} take control: {label:c1} {value:c1} in their favour. {label:c2} since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `{minute:c1} — {home} take control: {label:c1} {value:c1} in their favour. {label:c2} since {start:c2}: {home} {value:c2}, {away} {value:c3}. {home} were the better side.`

#### `wrong_slot_binding`: 0.0% yakalandı (264/264 kaçtı)

**Neden:** Her yer tutucu doğru türde ve doğrulanmış bir iddiaya bağlı; hangi iddianın cümlede nereye ait olduğu denetlenmiyor. v4'te de açık.

Örnek:

- Orijinal: `{minute:c1} — {home} take control: {label:c1} {value:c1} in their favour. {label:c2} since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `{minute:c1} — {home} take control: {label:c1} {value:c1} in their favour. {label:c2} since {start:c2}: {home} {value:c3}, {away} {value:c2}.`

#### `role_reversed`: 64.2% yakalandı (83/232 kaçtı)

**Neden:** Ters rol, olay sözcüğü yasak listesinde olmayan bir fiille yazıldığında ("kept it out", "victim of the challenge", "topu çizgiden çıkardı") yakalanmıyor; yakalama sözlüğe dayanıyor.

Kaçan ifadeler / adlar: `kept it out at m`×35, `topu çizgiden çıkardı (m)`×33, `kept the kick out at m`×7, `sert müdahaleye maruz kaldı (m)`×5, `was the victim of the challenge at m`×3

Örnek:

- Orijinal: `{event:m-42-red_card_swing#359}; skor {score_named}.`
- Enjekte: `{player:a06} topu çizgiden çıkardı ({minute:c1}); skor {score_named}.`

#### `event_wrong_claim`: 95.2% yakalandı (12/248 kaçtı)

**Neden:** Seçilen yanlış olay başka bir iddianın kanıtıysa {event:} bağlama kuralından geçiyor (yalnızca "bir iddianın kanıtı" olması aranıyor, cümledeki rolüyle eşleşmesi değil).

Kaçan ifadeler / adlar: `goal, bir iddianın kanıtı`×12

Örnek:

- Orijinal: `{event:m-0-late_comeback#542}, making it {score}. {home} had been {value:c3} down.`
- Enjekte: `{event:m-0-late_comeback#106}, making it {score}. {home} had been {value:c3} down.`

#### `qualitative_overstatement`: 54.5% yakalandı (284/624 kaçtı)

**Neden:** İfade nitel abartı listesinde yok (liste sabit; eş anlamlı ve deyimler kaçar).

Kaçan ifadeler / adlar: `ders verir gibi oynadı.`×40, `were in total command.`×40, `durdurulamaz göründü.`×36, `put on a masterclass.`×36, `rakibini ezdi geçti.`×36, `gösteri yaptı.`×33, `ran the show.`×32, `sahada fırtına gibi esti.`×31

Örnek:

- Orijinal: `{minute:c1} — Baskı {home} tarafına geçti: {label:c1} {value:c1}. {start:c2}–{minute:c2} arası {label:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `{minute:c1} — Baskı {home} tarafına geçti: {label:c1} {value:c1}. {start:c2}–{minute:c2} arası {label:c2}: {home} {value:c2}, {away} {value:c3}. {home} durdurulamaz göründü.`

### Yakalanmayan türler: foundry-v4 (slot + {event:} + sıkı lint)

#### `number_text_and_claim`: 97.9% yakalandı (13/624 kaçtı)

**Neden:** Gevşetilmiş eşitsizlik iddiası (`score_margin lte 0` → `lte 1`) hâlâ doğru kalıyor. Verify değerin doğruluğunu ölçer, sınırın sıkılığını değil.

Örnek:

- Orijinal: `{minute:c1} — {home} dominate without reward: since {start:c1} they have had {value:c1} of the ball and a {value:c2}–{value:c3} lead in {label:c2}, yet the score is {score_named}.`
- Enjekte: `{minute:c1} — {home} dominate without reward: since {start:c1} they have had {value:c1} of the ball and a {value:c2}–{value:c3} lead in {label:c2}, yet the score is {score_named}.`

#### `unsupported_sentence_qualitative`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümle yer tutucuyla başlıyor, sayı ve olay sözcüğü yok; "were the better side" nitel abartı listesinde değil (abartı değil, yargı). Nitel yargılar v4'te de kapsam dışında.

Örnek:

- Orijinal: `{minute:c1} — {home} take control: {label:c1} {value:c1} in their favour. {label:c2} since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `{minute:c1} — {home} take control: {label:c1} {value:c1} in their favour. {label:c2} since {start:c2}: {home} {value:c2}, {away} {value:c3}. {home} were the better side.`

#### `wrong_slot_binding`: 0.0% yakalandı (264/264 kaçtı)

**Neden:** Her yer tutucu doğru türde ve doğrulanmış bir iddiaya bağlı; hangi iddianın cümlede nereye ait olduğu denetlenmiyor. v4'te de açık.

Örnek:

- Orijinal: `{minute:c1} — {home} take control: {label:c1} {value:c1} in their favour. {label:c2} since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `{minute:c1} — {home} take control: {label:c1} {value:c1} in their favour. {label:c2} since {start:c2}: {home} {value:c3}, {away} {value:c2}.`

#### `role_reversed`: 64.2% yakalandı (83/232 kaçtı)

**Neden:** Ters rol, olay sözcüğü yasak listesinde olmayan bir fiille yazıldığında ("kept it out", "victim of the challenge", "topu çizgiden çıkardı") yakalanmıyor; yakalama sözlüğe dayanıyor.

Kaçan ifadeler / adlar: `kept it out at m`×35, `topu çizgiden çıkardı (m)`×33, `kept the kick out at m`×7, `sert müdahaleye maruz kaldı (m)`×5, `was the victim of the challenge at m`×3

Örnek:

- Orijinal: `{event:m-42-red_card_swing#359}; skor {score_named}.`
- Enjekte: `{player:a06} topu çizgiden çıkardı ({minute:c1}); skor {score_named}.`

#### `event_wrong_claim`: 95.2% yakalandı (12/248 kaçtı)

**Neden:** Seçilen yanlış olay başka bir iddianın kanıtıysa {event:} bağlama kuralından geçiyor (yalnızca "bir iddianın kanıtı" olması aranıyor, cümledeki rolüyle eşleşmesi değil).

Kaçan ifadeler / adlar: `goal, bir iddianın kanıtı`×12

Örnek:

- Orijinal: `{event:m-0-late_comeback#542}, making it {score}. {home} had been {value:c3} down.`
- Enjekte: `{event:m-0-late_comeback#106}, making it {score}. {home} had been {value:c3} down.`

#### `qualitative_overstatement`: 54.5% yakalandı (284/624 kaçtı)

**Neden:** İfade nitel abartı listesinde yok (liste sabit; eş anlamlı ve deyimler kaçar).

Kaçan ifadeler / adlar: `ders verir gibi oynadı.`×40, `were in total command.`×40, `durdurulamaz göründü.`×36, `put on a masterclass.`×36, `rakibini ezdi geçti.`×36, `gösteri yaptı.`×33, `ran the show.`×32, `sahada fırtına gibi esti.`×31

Örnek:

- Orijinal: `{minute:c1} — Baskı {home} tarafına geçti: {label:c1} {value:c1}. {start:c2}–{minute:c2} arası {label:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `{minute:c1} — Baskı {home} tarafına geçti: {label:c1} {value:c1}. {start:c2}–{minute:c2} arası {label:c2}: {home} {value:c2}, {away} {value:c3}. {home} durdurulamaz göründü.`

#### `player_repeat`: 0.0% yakalandı (232/232 kaçtı)

**Neden:** {player:} oyuncusu bir iddianın öznesi, yer tutucu bağlanıyor; {event:} ifadesinin oyuncuyu zaten andığı denetlenmiyor (v4'ün açığı).

Kaçan ifadeler / adlar: `goal`×164, `penalty`×44, `red_card`×24

Örnek:

- Orijinal: `{event:m-42-red_card_swing#127}, making it {score_named}.`
- Enjekte: `{event:m-42-red_card_swing#127} by {player:h09}, making it {score_named}.`

### Yakalanmayan türler: foundry-v3 (slot)

#### `number_text_and_claim`: 97.8% yakalandı (14/624 kaçtı)

**Neden:** Gevşetilmiş eşitsizlik iddiası (`score_margin lte 0` → `lte 1`) hâlâ doğru kalıyor. Verify değerin doğruluğunu ölçer, sınırın sıkılığını değil.

Örnek:

- Orijinal: `{minute:c1} — {home} üstün ama sonuç alamıyor: {start:c1}. dakikadan bu yana {value:c1} topa sahip olma ve {value:c2}–{value:c3} şut, skor ise {score}.`
- Enjekte: `{minute:c1} — {home} üstün ama sonuç alamıyor: {start:c1}. dakikadan bu yana {value:c1} topa sahip olma ve {value:c2}–{value:c3} şut, skor ise {score}.`

#### `unsupported_sentence_qualitative`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümlede ne sayı ne yeni bir isim var; nitel yargılar lint ve verify'ın kapsamı dışında.

Örnek:

- Orijinal: `{minute:c1} — {home} take control: {label:c1} is {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `{minute:c1} — {home} take control: {label:c1} is {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}. {home} were the better side.`

#### `number_words`: 57.0% yakalandı (136/316 kaçtı)

**Neden:** Belirsiz kelime (TR "bir", EN "one") ardından sayılabilir bir isim gelmediği için sayı sayılmıyor ("bir ara", "one of" gibi kullanımlarda yanlış alarmı önlemek için).

Örnek:

- Orijinal: `{minute:c1} — {home} take control: {label:c1} is {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `{minute:c1} — {home} take control: {label:c1} is {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} one.`

#### `sentence_start_fabricated`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümle başındaki tek büyük harfli kelime isim sayılmıyor (cümle başı büyük harfi normal); kadroda olmayan tek kelimelik isim bu konumda fark edilmiyor.

Örnek:

- Orijinal: `{minute:c1} — {home} take control: {label:c1} is {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `Quintana scores. {minute:c1} — {home} take control: {label:c1} is {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}.`

#### `wrong_slot_binding`: 0.0% yakalandı (264/264 kaçtı)

**Neden:** Her yer tutucu doğru türde ve doğrulanmış bir iddiaya bağlı; hangi iddianın cümlede nereye ait olduğu denetlenmiyor. (v3'ün açığı)

Örnek:

- Orijinal: `{minute:c1} — {home} take control: {label:c1} is {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `{minute:c1} — {home} take control: {label:c1} is {value:c2} in their favour. Shots since {start:c2}: {home} {value:c1}, {away} {value:c3}.`

#### `role_reversed`: 0.0% yakalandı (232/232 kaçtı)

**Neden:** Ad iddianın öznesi ve dakika doğru; lint ve verify olayın rolünü (kim attı / kim kurtardı) bilmiyor.

Kaçan ifadeler / adlar: `kept it out at m`×41, `topu çizgiden çıkardı (m)`×33, `şutu kurtardı (m)`×27, `golü engelleyemedi (m)`×22, `conceded at m`×21, `saved the shot at m`×20, `penaltı kurtardı (m)`×10, `saved a penalty at m`×10, `kept the kick out at m`×9, `penaltıda gole izin vermedi (m)`×7, `sert müdahaleye maruz kaldı (m)`×7, `vuruşu çeldi (m)`×5, `was the victim of the challenge at m`×5, `was brought down and saw a rival dismissed at m`×4, `drew a red card at m`×3, `stopped the spot-kick at m`×3, `yerde kaldı, rakibi oyundan atıldı (m)`×3, `rakibine kırmızı kart gördürdü (m)`×2

Örnek:

- Orijinal: `{minute:c1} — {player:h09} scores for {home}. {score}.`
- Enjekte: `{player:h09} kept it out at {minute:c1}. {score}.`

#### `sentence_start_fabricated_name`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümle başındaki tek büyük harfli kelime isim sayılmıyor (cümle başı büyük harfi normal); kadroda olmayan tek kelimelik isim bu konumda fark edilmiyor.

Kaçan ifadeler / adlar: `Marisk`×94, `Albrecz`×79, `Ravello`×79, `Fernhal`×76, `Telvano`×76, `Okonde`×75, `Dusko`×73, `Quintara`×72

Örnek:

- Orijinal: `{minute:c1} — {home} take control: {label:c1} is {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `Dusko looked sharp. {minute:c1} — {home} take control: {label:c1} is {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}.`

#### `qualitative_overstatement`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümlede ne sayı ne yeni bir isim var; nitel yargılar lint ve verify'ın kapsamı dışında.

Kaçan ifadeler / adlar: `ders verir gibi oynadı.`×43, `durdurulamaz göründü.`×42, `ran the show.`×42, `were relentless.`×41, `sahada fırtına gibi esti.`×38, `were in total command.`×37, `gösteri yaptı.`×36, `rakibini ezdi geçti.`×36, `were stunning.`×36, `were utterly dominant.`×36, `çok daha fazlasını hak etti.`×34, `pushed on deep into stoppage time.`×33, `inanılmaz oynadı.`×32, `deserved more.`×31, `put on a masterclass.`×31, `uzatmaların son saniyelerinde bastırdı.`×30, `completely took control.`×25, `oyunun kontrolünü tamamen ele aldı.`×21

Örnek:

- Orijinal: `{minute:c1} — {home} take control: {label:c1} is {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}.`
- Enjekte: `{minute:c1} — {home} take control: {label:c1} is {value:c1} in their favour. Shots since {start:c2}: {home} {value:c2}, {away} {value:c3}. {home} were utterly dominant.`

#### `player_repeat`: 0.0% yakalandı (150/150 kaçtı)

**Neden:** Ad bir iddianın öznesi, ikinci kez anılması yeni bir sayı ya da isim getirmiyor; aynı cümlede tekrar denetlenmiyor.

Kaçan ifadeler / adlar: `goal`×82, `penalty`×44, `red_card`×24

Örnek:

- Orijinal: `{minute:c1} — {player:h09} scores for {home}. {score}.`
- Enjekte: `{minute:c1} — {player:h09} scores for {home} by {player:h09}. {score}.`

### Yakalanmayan türler: foundry-v2 (serbest metin)

#### `number_text`: 88.5% yakalandı (72/624 kaçtı)

**Neden:** Lint sayının hangi iddiaya ait olduğuna değil, herhangi bir iddiada geçip geçmediğine bakar; yanlış yerdeki doğru-görünen sayı geçer.

Örnek:

- Orijinal: `22' — Murek Brestani scores for Brannoch FC. Brannoch FC 1–0 Morvane Athletic.`
- Enjekte: `22' — Murek Brestani scores for Brannoch FC. Brannoch FC 1–1 Morvane Athletic.`

#### `number_text_and_claim`: 98.5% yakalandı (7/482 kaçtı)

**Neden:** Gevşetilmiş eşitsizlik iddiası (`score_margin lte 0` → `lte 1`) hâlâ doğru kalıyor.

Örnek:

- Orijinal: `34' — Morvane Rovers üstün ama sonuç alamıyor: 14. dakikadan bu yana %60 topa sahip olma ve 5–1 şut, skor ise Kelvara United 1–0 Morvane Rovers.`
- Enjekte: `34' — Morvane Rovers üstün ama sonuç alamıyor: 14. dakikadan bu yana %60 topa sahip olma ve 5–1 şut, skor ise Kelvara United 1–1 Morvane Rovers.`

#### `foreign_player`: 94.8% yakalandı (12/232 kaçtı)

**Neden:** Yabancı oyuncunun soyadı iddiadaki oyuncuyla aynı; soyad takma ad olarak destekli, ad "—" sonrası cümle başında.

Örnek:

- Orijinal: `89' — Nolvek Selvado scores for Drunmark Rovers. Drunmark Rovers 3–2 Ostmere United.`
- Enjekte: `89' — Tamsel Selvado scores for Drunmark Rovers. Drunmark Rovers 3–2 Ostmere United.`

#### `unsupported_sentence_qualitative`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümlede ne sayı ne yeni bir isim var; nitel yargılar lint ve verify'ın kapsamı dışında.

Örnek:

- Orijinal: `13' — Brannoch FC take control: pressure balance over the last 10 minutes of play is +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`
- Enjekte: `13' — Brannoch FC take control: pressure balance over the last 10 minutes of play is +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0. Brannoch FC were the better side.`

#### `number_words`: 57.9% yakalandı (202/480 kaçtı)

**Neden:** Belirsiz kelime (TR "bir", EN "one") ardından sayılabilir bir isim gelmediği için sayı sayılmıyor ("bir ara", "one of" gibi kullanımlarda yanlış alarmı önlemek için). Ya da Lint sayının hangi iddiaya ait olduğuna değil, herhangi bir iddiada geçip geçmediğine bakar; yanlış yerdeki doğru-görünen sayı geçer.

Örnek:

- Orijinal: `22' — Gol! Murek Brestani (Brannoch FC) ağları buldu. Skor: Brannoch FC 1–0 Morvane Athletic.`
- Enjekte: `22' — Gol! Murek Brestani (Brannoch FC) ağları buldu. Skor: Brannoch FC 1–bir Morvane Athletic.`

#### `sentence_start_fabricated`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümle başındaki tek büyük harfli kelime isim sayılmıyor (cümle başı büyük harfi normal); kadroda olmayan tek kelimelik isim bu konumda fark edilmiyor.

Örnek:

- Orijinal: `13' — Brannoch FC take control: pressure balance over the last 10 minutes of play is +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`
- Enjekte: `Quintana scores. 13' — Brannoch FC take control: pressure balance over the last 10 minutes of play is +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`

#### `score_order_reversed`: 0.0% yakalandı (150/150 kaçtı)

**Neden:** Her iki skor rakamı da bir skor iddiasında geçiyor; lint sırayı bilmiyor.

Örnek:

- Orijinal: `22' — Murek Brestani scores for Brannoch FC. Brannoch FC 1–0 Morvane Athletic.`
- Enjekte: `22' — Murek Brestani scores for Brannoch FC. Brannoch FC 0–1 Morvane Athletic.`

#### `raw_side_label`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Küçük harfli "home side" ne sayı ne isim; v2 lint'i etiketleri denetlemiyor.

Örnek:

- Orijinal: `13' — Brannoch FC take control: pressure balance over the last 10 minutes of play is +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`
- Enjekte: `13' — the home side take control: pressure balance over the last 10 minutes of play is +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`

#### `free_number`: 0.0% yakalandı (428/428 kaçtı)

**Neden:** Lint sayının hangi iddiaya ait olduğuna değil, herhangi bir iddiada geçip geçmediğine bakar; yanlış yerdeki doğru-görünen sayı geçer.

Örnek:

- Orijinal: `13' — Brannoch FC take control: pressure balance over the last 10 minutes of play is +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`
- Enjekte: `13' — Brannoch FC take control: pressure balance over the last 10 minutes of play is +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 1.`

#### `role_reversed`: 0.0% yakalandı (232/232 kaçtı)

**Neden:** Ad iddianın öznesi ve dakika doğru; lint ve verify olayın rolünü (kim attı / kim kurtardı) bilmiyor.

Kaçan ifadeler / adlar: `topu çizgiden çıkardı (m)`×35, `saved the shot at m`×31, `şutu kurtardı (m)`×30, `kept it out at m`×28, `conceded at m`×23, `golü engelleyemedi (m)`×17, `penaltı kurtardı (m)`×10, `kept the kick out at m`×9, `saved a penalty at m`×7, `penaltıda gole izin vermedi (m)`×6, `stopped the spot-kick at m`×6, `vuruşu çeldi (m)`×6, `drew a red card at m`×5, `rakibine kırmızı kart gördürdü (m)`×4, `sert müdahaleye maruz kaldı (m)`×4, `was brought down and saw a rival dismissed at m`×4, `yerde kaldı, rakibi oyundan atıldı (m)`×4, `was the victim of the challenge at m`×3

Örnek:

- Orijinal: `22' — Murek Brestani scores for Brannoch FC. Brannoch FC 1–0 Morvane Athletic.`
- Enjekte: `Murek Brestani conceded at 22'. Brannoch FC 1–0 Morvane Athletic.`

#### `sentence_start_fabricated_name`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümle başındaki tek büyük harfli kelime isim sayılmıyor (cümle başı büyük harfi normal); kadroda olmayan tek kelimelik isim bu konumda fark edilmiyor.

Kaçan ifadeler / adlar: `Ravello`×91, `Quintara`×84, `Telvano`×83, `Marisk`×80, `Dusko`×75, `Okonde`×75, `Fernhal`×70, `Albrecz`×66

Örnek:

- Orijinal: `13' — Brannoch FC take control: pressure balance over the last 10 minutes of play is +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`
- Enjekte: `Fernhal looked sharp. 13' — Brannoch FC take control: pressure balance over the last 10 minutes of play is +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`

#### `qualitative_overstatement`: 0.0% yakalandı (624/624 kaçtı)

**Neden:** Cümlede ne sayı ne yeni bir isim var; nitel yargılar lint ve verify'ın kapsamı dışında.

Kaçan ifadeler / adlar: `were stunning.`×46, `pushed on deep into stoppage time.`×45, `were relentless.`×45, `çok daha fazlasını hak etti.`×44, `were utterly dominant.`×41, `gösteri yaptı.`×40, `rakibini ezdi geçti.`×40, `sahada fırtına gibi esti.`×40, `uzatmaların son saniyelerinde bastırdı.`×36, `put on a masterclass.`×33, `ran the show.`×30, `ders verir gibi oynadı.`×29, `inanılmaz oynadı.`×29, `deserved more.`×28, `durdurulamaz göründü.`×28, `oyunun kontrolünü tamamen ele aldı.`×26, `were in total command.`×26, `completely took control.`×18

Örnek:

- Orijinal: `13' — Brannoch FC take control: pressure balance over the last 10 minutes of play is +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.`
- Enjekte: `13' — Brannoch FC take control: pressure balance over the last 10 minutes of play is +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0. Brannoch FC were relentless.`

#### `player_repeat`: 0.0% yakalandı (232/232 kaçtı)

**Neden:** Ad bir iddianın öznesi, ikinci kez anılması yeni bir sayı ya da isim getirmiyor; aynı cümlede tekrar denetlenmiyor.

Kaçan ifadeler / adlar: `goal`×164, `penalty`×44, `red_card`×24

Örnek:

- Orijinal: `22' — Murek Brestani scores for Brannoch FC. Brannoch FC 1–0 Morvane Athletic.`
- Enjekte: `22' — Murek Brestani scores for Brannoch FC by Murek Brestani. Brannoch FC 1–0 Morvane Athletic.`

## Yeni türlerde uygulanan ifadeler (tüm sürümler)

- `role_reversed` v2: yakalanan —; kaçan `topu çizgiden çıkardı (m)`×35, `saved the shot at m`×31, `şutu kurtardı (m)`×30, `kept it out at m`×28, `conceded at m`×23, `golü engelleyemedi (m)`×17, `penaltı kurtardı (m)`×10, `kept the kick out at m`×9, `saved a penalty at m`×7, `penaltıda gole izin vermedi (m)`×6, `stopped the spot-kick at m`×6, `vuruşu çeldi (m)`×6, `drew a red card at m`×5, `rakibine kırmızı kart gördürdü (m)`×4, `sert müdahaleye maruz kaldı (m)`×4, `was brought down and saw a rival dismissed at m`×4, `yerde kaldı, rakibi oyundan atıldı (m)`×4, `was the victim of the challenge at m`×3
- `role_reversed` v3: yakalanan —; kaçan `kept it out at m`×41, `topu çizgiden çıkardı (m)`×33, `şutu kurtardı (m)`×27, `golü engelleyemedi (m)`×22, `conceded at m`×21, `saved the shot at m`×20, `penaltı kurtardı (m)`×10, `saved a penalty at m`×10, `kept the kick out at m`×9, `penaltıda gole izin vermedi (m)`×7, `sert müdahaleye maruz kaldı (m)`×7, `vuruşu çeldi (m)`×5, `was the victim of the challenge at m`×5, `was brought down and saw a rival dismissed at m`×4, `drew a red card at m`×3, `stopped the spot-kick at m`×3, `yerde kaldı, rakibi oyundan atıldı (m)`×3, `rakibine kırmızı kart gördürdü (m)`×2
- `role_reversed` v4: yakalanan `saved the shot at m`×26, `golü engelleyemedi (m)`×25, `şutu kurtardı (m)`×24, `conceded at m`×21, `penaltı kurtardı (m)`×14, `saved a penalty at m`×8, `stopped the spot-kick at m`×7, `was brought down and saw a rival dismissed at m`×7, `penaltıda gole izin vermedi (m)`×5, `yerde kaldı, rakibi oyundan atıldı (m)`×5, `vuruşu çeldi (m)`×3, `drew a red card at m`×2, `rakibine kırmızı kart gördürdü (m)`×2; kaçan `kept it out at m`×35, `topu çizgiden çıkardı (m)`×33, `kept the kick out at m`×7, `sert müdahaleye maruz kaldı (m)`×5, `was the victim of the challenge at m`×3
- `role_reversed` v4.1: yakalanan `saved the shot at m`×26, `golü engelleyemedi (m)`×25, `şutu kurtardı (m)`×24, `conceded at m`×21, `penaltı kurtardı (m)`×14, `saved a penalty at m`×8, `stopped the spot-kick at m`×7, `was brought down and saw a rival dismissed at m`×7, `penaltıda gole izin vermedi (m)`×5, `yerde kaldı, rakibi oyundan atıldı (m)`×5, `vuruşu çeldi (m)`×3, `drew a red card at m`×2, `rakibine kırmızı kart gördürdü (m)`×2; kaçan `kept it out at m`×35, `topu çizgiden çıkardı (m)`×33, `kept the kick out at m`×7, `sert müdahaleye maruz kaldı (m)`×5, `was the victim of the challenge at m`×3
- `role_reversed` v5: yakalanan `golü engelleyemedi (m)`×34, `saved the shot at m`×32, `şutu kurtardı (m)`×24, `conceded at m`×22, `stopped the spot-kick at m`×10, `vuruşu çeldi (m)`×9, `penaltıda gole izin vermedi (m)`×8, `saved a penalty at m`×8, `was brought down and saw a rival dismissed at m`×6, `penaltı kurtardı (m)`×5, `rakibine kırmızı kart gördürdü (m)`×4, `yerde kaldı, rakibi oyundan atıldı (m)`×4, `drew a red card at m`×1; kaçan `kept it out at m`×28, `topu çizgiden çıkardı (m)`×24, `was the victim of the challenge at m`×5, `kept the kick out at m`×4, `sert müdahaleye maruz kaldı (m)`×4
- `event_wrong_claim` v2: yakalanan `goal, kanıt değil`×91, `foul, kanıt değil`×44; kaçan —
- `event_wrong_claim` v3: yakalanan `goal, kanıt değil`×94, `foul, kanıt değil`×44; kaçan —
- `event_wrong_claim` v4: yakalanan `goal, kanıt değil`×154, `foul, kanıt değil`×68, `penalty, kanıt değil`×14; kaçan `goal, bir iddianın kanıtı`×12
- `event_wrong_claim` v4.1: yakalanan `goal, kanıt değil`×154, `foul, kanıt değil`×68, `penalty, kanıt değil`×14; kaçan `goal, bir iddianın kanıtı`×12
- `event_wrong_claim` v5: yakalanan `goal, kanıt değil`×117, `foul, kanıt değil`×68, `penalty, kanıt değil`×14; kaçan `goal, bir iddianın kanıtı`×49
- `sentence_start_fabricated_name` v2: yakalanan —; kaçan `Ravello`×91, `Quintara`×84, `Telvano`×83, `Marisk`×80, `Dusko`×75, `Okonde`×75, `Fernhal`×70, `Albrecz`×66
- `sentence_start_fabricated_name` v3: yakalanan —; kaçan `Marisk`×94, `Albrecz`×79, `Ravello`×79, `Fernhal`×76, `Telvano`×76, `Okonde`×75, `Dusko`×73, `Quintara`×72
- `sentence_start_fabricated_name` v4: yakalanan `Albrecz`×90, `Quintara`×88, `Fernhal`×81, `Marisk`×78, `Dusko`×77, `Ravello`×73, `Okonde`×71, `Telvano`×66; kaçan —
- `sentence_start_fabricated_name` v4.1: yakalanan `Albrecz`×90, `Quintara`×88, `Fernhal`×81, `Marisk`×78, `Dusko`×77, `Ravello`×73, `Okonde`×71, `Telvano`×66; kaçan —
- `sentence_start_fabricated_name` v5: yakalanan `Ravello`×85, `Fernhal`×80, `Quintara`×79, `Telvano`×77, `Albrecz`×76, `Marisk`×76, `Okonde`×76, `Dusko`×75; kaçan —
- `qualitative_overstatement` v2: yakalanan —; kaçan `were stunning.`×46, `pushed on deep into stoppage time.`×45, `were relentless.`×45, `çok daha fazlasını hak etti.`×44, `were utterly dominant.`×41, `gösteri yaptı.`×40, `rakibini ezdi geçti.`×40, `sahada fırtına gibi esti.`×40, `uzatmaların son saniyelerinde bastırdı.`×36, `put on a masterclass.`×33, `ran the show.`×30, `ders verir gibi oynadı.`×29, `inanılmaz oynadı.`×29, `deserved more.`×28, `durdurulamaz göründü.`×28, `oyunun kontrolünü tamamen ele aldı.`×26, `were in total command.`×26, `completely took control.`×18
- `qualitative_overstatement` v3: yakalanan —; kaçan `ders verir gibi oynadı.`×43, `durdurulamaz göründü.`×42, `ran the show.`×42, `were relentless.`×41, `sahada fırtına gibi esti.`×38, `were in total command.`×37, `gösteri yaptı.`×36, `rakibini ezdi geçti.`×36, `were stunning.`×36, `were utterly dominant.`×36, `çok daha fazlasını hak etti.`×34, `pushed on deep into stoppage time.`×33, `inanılmaz oynadı.`×32, `deserved more.`×31, `put on a masterclass.`×31, `uzatmaların son saniyelerinde bastırdı.`×30, `completely took control.`×25, `oyunun kontrolünü tamamen ele aldı.`×21
- `qualitative_overstatement` v4: yakalanan `were stunning.`×49, `çok daha fazlasını hak etti.`×40, `pushed on deep into stoppage time.`×39, `inanılmaz oynadı.`×37, `were utterly dominant.`×37, `uzatmaların son saniyelerinde bastırdı.`×33, `were relentless.`×31, `deserved more.`×27, `oyunun kontrolünü tamamen ele aldı.`×26, `completely took control.`×21; kaçan `ders verir gibi oynadı.`×40, `were in total command.`×40, `durdurulamaz göründü.`×36, `put on a masterclass.`×36, `rakibini ezdi geçti.`×36, `gösteri yaptı.`×33, `ran the show.`×32, `sahada fırtına gibi esti.`×31
- `qualitative_overstatement` v4.1: yakalanan `were stunning.`×49, `çok daha fazlasını hak etti.`×40, `pushed on deep into stoppage time.`×39, `inanılmaz oynadı.`×37, `were utterly dominant.`×37, `uzatmaların son saniyelerinde bastırdı.`×33, `were relentless.`×31, `deserved more.`×27, `oyunun kontrolünü tamamen ele aldı.`×26, `completely took control.`×21; kaçan `ders verir gibi oynadı.`×40, `were in total command.`×40, `durdurulamaz göründü.`×36, `put on a masterclass.`×36, `rakibini ezdi geçti.`×36, `gösteri yaptı.`×33, `ran the show.`×32, `sahada fırtına gibi esti.`×31
- `qualitative_overstatement` v5: yakalanan `durdurulamaz göründü.`×44, `deserved more.`×41, `ran the show.`×41, `were relentless.`×39, `çok daha fazlasını hak etti.`×39, `ders verir gibi oynadı.`×38, `sahada fırtına gibi esti.`×38, `were in total command.`×38, `gösteri yaptı.`×37, `inanılmaz oynadı.`×36, `pushed on deep into stoppage time.`×34, `were utterly dominant.`×34, `rakibini ezdi geçti.`×32, `put on a masterclass.`×31, `uzatmaların son saniyelerinde bastırdı.`×30, `were stunning.`×29, `completely took control.`×25, `oyunun kontrolünü tamamen ele aldı.`×18; kaçan —
- `player_repeat` v2: yakalanan —; kaçan `goal`×164, `penalty`×44, `red_card`×24
- `player_repeat` v3: yakalanan —; kaçan `goal`×82, `penalty`×44, `red_card`×24
- `player_repeat` v4: yakalanan —; kaçan `goal`×164, `penalty`×44, `red_card`×24
- `player_repeat` v4.1: yakalanan `goal`×164, `penalty`×44, `red_card`×24; kaçan —
- `player_repeat` v5: yakalanan `goal`×164, `penalty`×44, `red_card`×24; kaçan —
- `unknown_menu_id` v3: yakalanan `minute`×624; kaçan —
- `unknown_menu_id` v4: yakalanan `minute`×264, `score`×264, `value`×52; kaçan —
- `unknown_menu_id` v4.1: yakalanan `minute`×264, `score`×264, `value`×52; kaçan —
- `unknown_menu_id` v5: yakalanan `minute`×264, `score`×264, `value`×52; kaçan —

## v4 / v4.1 lint kuralları ve yanlış alarm

Kural başına, kuralın tetiklendiği taslak oranı (v4.1 kurallarıyla; cümle başı satırı v4.1 izinli listesiyle). Temiz taslaklarda (template, v3 slot, v4 slot tabanı) her tetiklenme yanlış alarmdır. Gerçek LLM çıktıları: foundry-v2'nin yayınlanan serbest metinleri ve foundry-v3'ün kabul edilen şablonları (EN, adlar ve sayılar yer tutucu sayılır); bunlarda sayı kelimesi, uydurma ad yok, yani cümle başı ve sayı kelimesi tetiklenmesi yanlış alarmdır. foundry-v4 sütunu v4'ün kabul ettiği şablonlar: v4.1 kuralları bu çıktılardaki bulgulardan ("They …", "The {home}", "… by {player:}", pas olayı) yazıldı, bu sütundaki tetiklenmeler hedeflenen yakalamalardır. Nitel abartı tetiklenmesinin doğru olup olmadığı insan etiketiyle karşılaştırılır (aşağıda). "Olay sözcüğü" satırı yanlış alarm değil, politika: v4'te olay ve metrik adları serbest yazılamaz.

| Kural | Template taslakları (ham metin) | v3 slot şablonları (temiz) | v4 slot tabanı (temiz) | Gerçek LLM, foundry-v2 serbest metin | Gerçek LLM, foundry-v3 şablon | Gerçek LLM, foundry-v4 şablon |
|---|---:|---:|---:|---:|---:|---:|
| Cümle başı (izinli liste) | 138/624 (22.1%) | 138/624 (22.1%) | 0/624 (0.0%) | 3/22 (13.6%) | 0/20 (0.0%) | 4/18 (22.2%) |
| Yazıyla sayı (bağlamsız) | 14/624 (2.2%) | 14/624 (2.2%) | 0/624 (0.0%) | 0/22 (0.0%) | 0/20 (0.0%) | 0/18 (0.0%) |
| Nitel abartı | 0/624 (0.0%) | 0/624 (0.0%) | 0/624 (0.0%) | 0/22 (0.0%) | 1/20 (5.0%) | 0/18 (0.0%) |
| Yalnızca soyad (text_lint) | 0/624 (0.0%) | — | — | 0/22 (0.0%) | — | — |
| Olay sözcüğü (politika) | 571/624 (91.5%) | 571/624 (91.5%) | 0/624 (0.0%) | 18/22 (81.8%) | 19/20 (95.0%) | 0/18 (0.0%) |
| {event:} olay tipi izin listesi (v4.1) | 0/624 (0.0%) | 0/624 (0.0%) | 0/624 (0.0%) | 0/22 (0.0%) | 0/20 (0.0%) | 1/18 (5.6%) |
| Oyuncu tekrarı (v4.1) | 0/624 (0.0%) | 0/624 (0.0%) | 0/624 (0.0%) | 0/22 (0.0%) | 0/20 (0.0%) | 1/18 (5.6%) |
| Takım adından önce "the" (v4.1) | 0/624 (0.0%) | 0/624 (0.0%) | 0/624 (0.0%) | 0/22 (0.0%) | 0/20 (0.0%) | 1/18 (5.6%) |

Tetiklenen parçalar (taslak başına sayım):

- Cümle başı (izinli liste) · Template taslakları (ham metin): `Shots`×110, `Bir`×14, `They`×14
- Yazıyla sayı (bağlamsız) · Template taslakları (ham metin): `Bir`×14
- Olay sözcüğü (politika) · Template taslakları (ham metin): `Shots`×110, `şutlar`×110, `scores`×89, `Gol`×82, `scoring`×28, `Penalty`×22, `penaltı`×22, `penaltıyı`×22, `shots`×22, `şut`×22, `level`×19, `gol`×14, `kurtarıldı`×14, `saved`×14, `vuruş`×14, `atıldı`×12, `kartla`×12, `sent off`×12, `goal`×9, `gole`×7, `goals`×5, `kaçırdı`×1, `misses`×1
- Cümle başı (izinli liste) · v3 slot şablonları (temiz): `Shots`×110, `Bir`×14, `They`×14
- Yazıyla sayı (bağlamsız) · v3 slot şablonları (temiz): `Bir`×14
- Olay sözcüğü (politika) · v3 slot şablonları (temiz): `Shots`×110, `şutlar`×110, `scores`×89, `Gol`×82, `scoring`×28, `Penalty`×22, `penaltı`×22, `penaltıyı`×22, `shots`×22, `şut`×22, `level`×19, `gol`×14, `kurtarıldı`×14, `saved`×14, `vuruş`×14, `atıldı`×12, `kartla`×12, `sent off`×12, `goal`×9, `gole`×7, `goals`×5, `kaçırdı`×1, `misses`×1
- Cümle başı (izinli liste) · Gerçek LLM, foundry-v2 serbest metin: `Home`×2, `away`×1
- Olay sözcüğü (politika) · Gerçek LLM, foundry-v2 serbest metin: `scored`×13, `shots`×2, `card`×1, `equalised`×1, `penalty`×1, `saved`×1
- Nitel abartı · Gerçek LLM, foundry-v3 şablon: `deep into`×1
- Olay sözcüğü (politika) · Gerçek LLM, foundry-v3 şablon: `scored`×13, `card`×1, `levelled`×1, `penalty`×1, `saved`×1, `sent off`×1, `shot`×1, `shots`×1
- Cümle başı (izinli liste) · Gerçek LLM, foundry-v4 şablon: `They`×4
- {event:} olay tipi izin listesi (v4.1) · Gerçek LLM, foundry-v4 şablon: `{event:m-42-red_card_swing#521}`×1
- Oyuncu tekrarı (v4.1) · Gerçek LLM, foundry-v4 şablon: `{player:h03}`×1
- Takım adından önce "the" (v4.1) · Gerçek LLM, foundry-v4 şablon: `The {home}`×1

### foundry-v4.1 değişikliklerinin yanlış alarmı

Temiz veri setlerinde v4.1'in eklediği reddetmeler (yeni kurallar + "They"ın izinli listeden çıkması; v4 kurallarıyla zaten reddedilenler sayılmaz):

| Veri seti | Yanlış alarm | Parçalar |
|---|---:|---|
| Template taslakları (ham metin) | 14/624 (2.2%) | `They`×14 |
| v3 slot şablonları (temiz) | 14/624 (2.2%) | `They`×14 |
| v4 slot tabanı (temiz) | 0/624 (0.0%) | — |
| Gerçek LLM, foundry-v2 serbest metin | 0/22 (0.0%) | — |
| Gerçek LLM, foundry-v3 şablon | 0/20 (0.0%) | — |

Template taslaklarındaki "They" tetiklenmesi template anlatıcının "They had been … down" cümlesinden geliyor; yedek metin v4.1 slot lint'inden değil text_lint'ten geçtiği için yayını etkilemez. foundry-v2/v3 çıktılarında "They" ile başlayan cümle yoktu; foundry-v4'ün kabul ettiği şablonlarda "They …" ile başlayan cümleler (yukarıdaki tabloda foundry-v4 sütunu) artık reddedilir. Bunlar olgusal olarak doğru olabilir (v4 çıktıları insan etiketlenmedi), yani zamir kuralının bilinçli bir maliyeti: zamirin hangi takımı gösterdiği metinden okunamıyor, model {home}/{away} yazmaya yönlendirilir.

### foundry-v5 izinli cümle başı değişikliğinin etkisi

"At" (dakikayı cümle başına taşır: "At 29' … since kickoff") ve "Possession" (metrik adı; `{label:}`/`{clause:}` ile gelir) listeden çıktı; EN listesi artık yalnızca "The". Bu değişiklikle yeni reddedilen taslaklar (v4.1 listesiyle zaten reddedilenler sayılmaz):

| Veri seti | Yeni ret | Parçalar |
|---|---:|---|
| Template taslakları (ham metin) | 0/624 (0.0%) | — |
| v3 slot şablonları (temiz) | 0/624 (0.0%) | — |
| v4 slot tabanı (temiz) | 0/624 (0.0%) | — |
| Gerçek LLM, foundry-v2 serbest metin | 3/22 (13.6%) | `At`×2, `Possession`×1 |
| Gerçek LLM, foundry-v3 şablon | 0/20 (0.0%) | — |
| Gerçek LLM, foundry-v4 şablon | 8/18 (44.4%) | `Possession`×7, `At`×1 |

Temiz setlerde (template, slot tabanları) tetiklenme yok. Gerçek LLM satırlarındaki tetiklenmeler olgusal olarak doğru olabilecek cümlelerdir ("Possession since kickoff: …", "At 29' …"); bunlar kuralın bilinçli maliyeti, v5'te aynı bilgi `{clause:possession}` ile gelir.

Template ve v3 satırlarında cümle başı ve sayı kelimesi tetiklenmeleri template anlatıcının kendi kalıplarından geliyor (EN "Shots since …", TR "Bir ara … gerideydi"). Bu kelimeler listeye bilerek alınmadı: "Shots" olay sözcüğü (v4'te metrik adı `{label:}` ile gelir), "Bir" sayı kelimesi. Template yedeği v4 slot lint'inden değil text_lint'ten geçtiği için bu, yayınlanan yedek metinleri etkilemez; "Bir ara" bağlamsız sayı kelimesi kuralının gerçek bir yanlış alarmıdır.

Nitel abartı kuralının gerçek LLM çıktılarında tetiklendiği metinler ve insan etiketi: `m-100-M010` (deep into) → misleading.

### İzinli cümle başı listesi

Liste temiz taslaklardan çıkarıldı (`eval/lint_rates.py` `derive_frozen`): template anlatıcının 624 taslağı + gerçek LLM çıktıları (42 metin; foundry-v3'te yalnızca insan etiketi `correct` olanlar). Cümlenin yer tutucuyla başlamayan ilk kelimesi alınır; home/away, zamir (foundry-v4.1: "They" çıktı), sayı kelimesi, olay sözcüğü ve abartı ifadeleri listeye girmez. Sonuç `config.py`'ye donduruldu: EN `The`; TR `Skor`.

Liste ölçüldüğü veriyi içerdiği için yukarıdaki oran iyimser. Dış-örneklem tahmini: liste yalnızca template taslaklarından çıkarılsaydı (EN —; TR Skor) gerçek LLM çıktılarındaki 59 cümleden 7 tanesi (11.9%) reddedilirdi: `At`×2, `Home`×2, `Possession`×1, `The`×1, `away`×1.

## Nitel abartı yasak listesi (v4 lint)

Sabit liste (`app/explain/phrases.py` `OVERSTATEMENT`). Yer tutucu dışındaki metinde eşleşen ifade, moment tipi desteklemiyorsa reddedilir (`overstatement`). Destekleyen tipler yalnızca momentin kendi kanıtıdır: "dominate" bir `dominance_without_reward` momentinde, "take control" bir `pressure_shift` momentinde dedektörün eşiğiyle desteklenir. Liste foundry-v3 insan etiketindeki "deep into stoppage" bulgusundan ve genel futbol abartı sözlüğünden yazıldı; enjeksiyondaki abartı cümleleri ayrı yazıldı (bkz. kaçan ifadeler).

| Dil | İfade (regex, `…` = devamı) | Destekleyen moment tipi |
|---|---|---|
| en | `deep into` | — |
| en | `dominat… · dominance` | dominance_without_reward |
| en | `(take · takes · took · taking · seiz… · in) control` | pressure_shift |
| en | `momentum` | pressure_shift |
| en | `on top` | dominance_without_reward, pressure_shift |
| en | `stunning · sensational · incredible · brilliant · superb · spectacular · magnificent · dramatic · thrilling` | — |
| en | `relentless… · siege · battered · bombard… · r[au]n riot · rampant` | — |
| en | `against the run of play` | — |
| en | `last[- ]gasp · at the death · dying (seconds · minutes)` | — |
| en | `winner · winning goal · sealed · clinch… · decisive · crucial · killer` | — |
| en | `totally · completely · utterly · absolutely` | — |
| en | `comfortabl… · cruis… · stroll…` | — |
| en | `deserv… · undeserv…` | — |
| tr | `domine… · hükmet… · ezici · üstünlük kur…` | dominance_without_reward |
| tr | `kontrol…` | pressure_shift |
| tr | `muhteşem · inanılmaz · harika · mükemmel · nefes kesen · dramatik · çılgın` | — |
| tr | `son nefes… · son saniye… · uzatmaların derin… · derinlerinde` | — |
| tr | `galibiyet golü · maçı kopar… · fişi çek… · kritik` | — |
| tr | `tamamen · kesinlikle · bütünüyle` | — |
| tr | `rahat…` | — |
| tr | `hak e[dt]…` | — |
| tr | `abluka…` | — |

## Şablon pencere denetimi (template anlatıcı)

Her iddianın penceresi ve pencereli (başlangıcı ne maç başı ne olay anı) iddiaların cümlede yazılı olup olmadığı (EN "since X'" ve TR "X. dakikadan").

| Moment tipi | Metrik | Tür | Pencere | İddia | Pencere metinde |
|---|---|---|---|---:|---:|
| dominance_without_reward | possession | ratio | pencere (X' → an) | 22 | 22/22 |
| dominance_without_reward | score | state | maç başı → an | 44 | — |
| dominance_without_reward | score_margin | state | maç başı → an | 22 | — |
| dominance_without_reward | shots | count | pencere (X' → an) | 44 | 44/44 |
| goal | goals | count | olay anı | 82 | — |
| goal | score | state | maç başı → an | 164 | — |
| penalty | penalties_missed | count | olay anı | 1 | — |
| penalty | penalties_saved | count | olay anı | 14 | — |
| penalty | penalties_scored | count | olay anı | 7 | — |
| pressure_shift | pressure_balance | state | kayan pencere (son oynanmış dakikalar) | 110 | 110/110 |
| pressure_shift | shots | count | maç başı → an | 6 | — |
| pressure_shift | shots | count | pencere (X' → an) | 214 | 214/214 |
| red_card | players_on_pitch | state | maç başı → an | 12 | — |
| red_card | red_cards | count | olay anı | 12 | — |
| score_change | goals | count | olay anı | 36 | — |
| score_change | min_score_margin | state | maç başı → an | 14 | — |
| score_change | score | state | maç başı → an | 56 | — |
| score_change | score_margin | state | maç başı → an | 36 | — |

Bulgular:

- `dominance_without_reward`: possession ve şut iddiaları zaten aynı pencereden (`dominance_context_minutes`); hata EN cümlesindeydi ("58% of possession and 4–0 shots since 25'" pencereyi yalnızca şutlara bağlıyordu). Düzeltme: pencere iki değerden önce yazılıyor ("since 25' they have had 58% of the ball and a 4–0 lead in shots"). TR cümlesi pencereyi zaten başa koyuyordu.
- `pressure_shift`: `pressure_balance` iddiası `start = maç başı` taşıyor, ama `measure` başlangıcı yok sayıyor; metrik son 10 oynanmış dakikanın kayan penceresi. foundry-v4.1: metriğin okunur adı pencereyi yazıyor ("pressure balance over the last 10 minutes of play" / "son 10 oynanmış dakikadaki baskı dengesi"; `app/explain/labels.py`, pencere `AnalyticsConfig.pressure_window_min`'den). Bu sabit ifade iddia değil: text_lint onu sayı denetiminden önce maskeler, doğrulayıcıya pencere desteği eklenmedi. Şut sayımı ise maç saatine göre `_since` penceresinden geliyor ve devre başında kırpılıyor; 13/110 baskı momentinde şut penceresi 10 dakikadan kısa (ör. `m-42-red_card_swing-M006`: "45' — Morvane Athletic take control: pressure balance over the last 10 minutes of play is +0.67 in their favour. Shots since 45': Morvane Athletic 0, Brannoch FC 0.", pencere 31 sn). Bu durumda iki değer farklı pencerelerden geliyor (oynanmış dakika ↔ maç saati); şut penceresi metinde yazılı olduğu için okur ikisini ayırabilir.
- `dominance_without_reward`: 3/22 momentte pencere devre başında kırpılmış (dedektör oynanmış süreyle 20 dakika geriye bakıyor; anlatı maç saatiyle). Metin kırpılmış pencerenin başlangıcını yazdığı için yanıltıcı değil, ama dedektörün değeriyle (moment.detail) birebir aynı değil.
- `goal`, `red_card`, `penalty`, `score_change`: iddialar olay anı ya da maç başı → an; ayrı pencere yok.

## İnsan etiketleri: foundry-v3 (ham sayılar)

Kaynak: `docs/human_review.foundry-v3.csv` (22 metin; llm: 20, template_fallback: 2), kaynak bilgisi `docs/LLM_RUN.foundry-v3.json`'dan. Bir metin birden fazla etiket alabilir (ör. correct + dull).

| Etiket | Toplam | llm | template_fallback | Momentler |
|---|---:|---:|---:|---|
| `correct` | 16 | 15 | 1 | … |
| `wrong_fact` | 1 | 1 | 0 | 7-dominant_loss M009 |
| `misleading` | 5 | 4 | 1 | 42-red_card_swing M005, 42-red_card_swing M009, 7-dominant_loss M003, 100 M009, 100 M010 |
| `dull` | 8 | 8 | 0 | 42-red_card_swing M003, 42-red_card_swing M008, 42-red_card_swing M011, 7-dominant_loss M006, 100 M005, 100 M007, 100 M009, 100 M011 |

## Yeniden üretme

```
.venv/bin/python -m eval.inject
```
