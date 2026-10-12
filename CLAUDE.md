# WhyBall
Çok ajanlı futbol maç anlatıcısı. Her iddia deterministik metriklerle doğrulanır.

## Stack
Python + FastAPI, Vite + React + TS, SQLite, Azure Container Apps.

## Kurallar
- LLM sadece Explain aşamasında. Analytics ve moment detector LLM kullanmaz.
- Verifier'dan geçmeyen cümle yayınlanmaz. Max 2 yeniden deneme, sonra template fallback.
- Veri sentetik ve seed'li. Gerçek kulüp ve oyuncu adı yok.
- Sır commit etme. Anahtarlar .env içinde.
- Her değişiklikten sonra testler çalışmalı.

## Komutlar
- Kurulum: python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
- Test: .venv/bin/pytest -q
- Maç üret: .venv/bin/python -m app.generator --seed 42 [--scenario late_comeback|red_card_swing|dominant_loss] [--out match.jsonl]
- Fixture'ları yeniden üret: .venv/bin/python -m app.generator.freeze (sadece üretici bilerek değiştiyse; sonra docs/DATASHEET.md tablosunu güncelle)
- Momentler: .venv/bin/python -m app.analytics --scenario red_card_swing --seed 42 [--jsonl] (ya da --input data/demo/<dosya>.jsonl)
- Anlatı + doğrulama: .venv/bin/python -m app.explain --input data/demo/red_card_swing_seed42.jsonl [--lang en|tr|both] [--all]
- Anlatım hattı: .venv/bin/python -m app.explain.run --input data/demo/<dosya>.jsonl --narrator template|fake:<mod> [--lang en|tr] [--no-cache] (önbellek: data/cache/, git'e girmez)
- Enjeksiyon değerlendirmesi: .venv/bin/python -m eval.inject [--quick] (docs/EVAL.md'yi yeniden yazar)
- LLM anlatıcı (opsiyonel): .venv/bin/pip install -e ".[llm]"; FOUNDRY_PROJECT_ENDPOINT ve FOUNDRY_MODEL ortam değişkeni olarak (.env otomatik yüklenmez, örn. set -a; source .env); --narrator foundry
- Foundry bağlantı testi: az login; .venv/bin/pip install -e ".[llm]"; .venv/bin/python -m app.llm.hello

## Scope freeze: 24 Ekim akşamı. Sonrasında yeni özellik yok.
