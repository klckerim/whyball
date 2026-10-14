# WhyBall: one container, API + built UI. Build: docker build -t whyball .  Run: docker run -p 8000:8000 whyball
# Base images are pinned by digest (multi-arch index); bump on purpose, see docs/DEPLOY.md.

# --- Stage 1: the web UI. Node 24 is the version CI uses (.github/workflows/ci.yml).
FROM node:24-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20 AS web
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- Stage 2: the API. Runtime dependencies are pinned in deploy/constraints.txt.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    WHYBALL_DATA_DIR=/app/data \
    WHYBALL_STATIC_DIR=/app/web/dist
WORKDIR /app

# Editable install on purpose: the code finds data/ and docs/ relative to the package directory.
COPY pyproject.toml ./
COPY deploy/constraints.txt deploy/constraints.txt
COPY app/ app/
RUN pip install -e ".[monitor]" -c deploy/constraints.txt

# Demo data, the publication store, and the two docs files `python -m app.publish --check` compares.
COPY data/demo/ data/demo/
COPY data/demo_narration/ data/demo_narration/
COPY docs/LLM_RUN.json docs/DEMO_NARRATION.md docs/
COPY --from=web /build/web/dist web/dist

RUN useradd --system --uid 10001 --no-create-home whyball
USER whyball

EXPOSE 8000
CMD ["python", "-m", "app.serve"]
