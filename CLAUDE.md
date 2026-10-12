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
- Test: pytest -q (henüz yok)

## Scope freeze: 24 Ekim akşamı. Sonrasında yeni özellik yok.
