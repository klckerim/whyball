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
- Maç üret: .venv/bin/python -m app.generator --seed 42 [--out match.jsonl]

## Scope freeze: 24 Ekim akşamı. Sonrasında yeni özellik yok.
