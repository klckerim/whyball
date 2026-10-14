# STATUS

Updated 2026-10-14. Project rules and commands: [CLAUDE.md](CLAUDE.md). UI v2: [UI_SPEC](docs/UI_SPEC.md), [DESIGN](docs/DESIGN.md).

## Frozen
- Scope freeze: evening of 24 October. No new features after that (CLAUDE.md).
- Synthetic seeded data only (fixtures change only via `app.generator.freeze`, [datasheet](docs/DATASHEET.md)).
  LLM only in the Explain stage; unverified sentences are never published (max 2 retries, then template).
- API response shapes: only additive changes (U0: timeline `x`/`y`, `squads`; U1: card `checks`, events, series).

## Done
- Generator, analytics and moment detector, selector, claim verifier, template narrator, lint, cache.
- Foundry narrator foundry-v2 → v5.2 (claim menu); 3 live runs, 0/45 fallbacks ([LLM_RUN](docs/LLM_RUN.md)).
- Injection eval v2–v5.2 ([EVAL](docs/EVAL.md)); publication store replays the last run ([DEMO_NARRATION](docs/DEMO_NARRATION.md)).
- FastAPI: matches, moments, events, metric series, SSE replay, `/healthz`; serves the UI with deep links.
- Repo hygiene: README skeleton, CI workflow (pytest, Vitest + build, gitleaks, docker), this file.
- U0 (UI v2 foundation, no screens): UI_SPEC + DESIGN log; `/healthz`, `/api/metrics`, timeline `x`/`y`,
  `squads`; OpenAPI → `web/src/api/schema.gen.ts` + drift checks; `web/test-fixtures/` from the real API;
  `<Fact>` + T1/T2 tests; `web/src/design/tokens.css` (light/dark, stage always dark); fonts; Radix.
- U1 (7 commits): new UI is the shipped one: shell, routes, On Air stage, transport, timeline, pressure
  band, dwell; card `checks` recorded at publish; old UI at `/legacy` until U2. Screens reviewed (3 shots).
- P1 (8 commits): image, start-up guard, DefaultAzureCredential, frozen API surface, remote smoke test,
  CI docker job (+ `--wait` fix), [DEPLOY](docs/DEPLOY.md), optional App Insights. Deployed 2026-10-14 (the user ran `az`):
  Sweden Central, image tag p1-20261014-1822, 0.5 vCPU / 1.0 Gi, 1-2 replicas, user-assigned identity + AcrPull,
  remote smoke test ALL PASSED. Foundry role not assigned, App Insights not enabled.
  Public address: https://whyball.happyground-485eb3be.swedencentral.azurecontainerapps.io

## In progress
- 7 U1 + 8 P1 commits on `master` only, not pushed; U0 and tag `llm-baseline-v2` are on origin. CI not checked here.

## Next
- Push; confirm CI (new `docker` job). User runs DEPLOY.md, then `scripts/smoke_remote.py <url>`.
- Then U2: Proof (Receipt, moment rail), value spans in the card text, delete old UI.
- Verifier gaps listed in EVAL (below). Decide before the freeze: fix or document.
- Deploy (see Deploy state).

## Decisions (with reason)
- CI pins actions to commit SHAs, Node 24 LTS: tags can move, and 24 meets the web engines range.
- gitleaks-action without a license key: required only for organization repos; this repo is personal.
- Claim menu (v5): the model picks menu ids, code builds the numbers, so numbers cannot drift.
- Replays use the stored publication, no live model call: demo is deterministic and free.
- UI v2 decisions (themes, safe areas, fonts, Radix, Fact contract) are logged with sources in DESIGN.md.
- openapi-typescript runs from `web/tools/openapi-gen` (own lockfile, TS 5.9.3): it needs the TS 5 JS
  API, the app is on TS 7 (DESIGN D10).
- Metric definitions are written in code next to the labels (`app/explain/labels.py`), numbers from config.
- Stage plays fetched events with a client clock, not SSE (exact seek, fake-timer tests; DESIGN D14).
- Seal reads the card's own recorded `checks`; nothing else can show "Verified" (DESIGN D21).

## Open risks / known limits
- Verifier misses (foundry-v5.2, [EVAL](docs/EVAL.md)): `wrong_slot_binding` 0% caught,
  `role_reversed` 69.0%, `event_wrong_claim` 71.6%. Qualitative claims inside a grounded sentence pass.
- Eval and run samples are small (15 moments per run, 3 runs), one data point per prompt version.
- Stored card red_card_swing 90+1' mentions an 84' goal that none of its claims cover.
- Tests (2026-10-14, uncached): pytest 645, Vitest 438, `npm run smoke` 3; initial JS 109.4 KB gzip.
- Card text has no value spans: lower third draws it as one plain block, numbers in it are not `<Fact>`.
- 390 px: pitch is small, close timeline glyphs overlap near full time (mobile polish, U5).
- After `app.publish`, rerun `python -m app.api.fixtures` (pytest fails until then, by design).
- Two demo matches share one run id and prompt version. `.env.example` is tracked on purpose; not opened (deny rule).

## Deploy state
- Target: Azure Container Apps, one container, Sweden Central, own resource group. Steps: [DEPLOY](docs/DEPLOY.md).
- Image: `Dockerfile` (digest-pinned bases, non-root, `deploy/constraints.txt`); entry `python -m app.serve`
  refuses to start if `app.publish --check` fails. CI `docker` job builds it, scans for `.env`/`notes`/`.git`.
- Public and unauthenticated: no endpoint calls a model or billable resource; `tests/test_api_surface.py` locks it.
- Local checks done: image runs, `/healthz`, 3 matches, deep link, SSE progressive. Azure side: deployed, smoke ALL PASSED.

## Mentor summary
- Commits (P1): 81081a6 Dockerfile+constraints · 65116fa serve guard · 2d522b3 DefaultAzureCredential · 6b43ac5
  API surface lock · 75580ab smoke_remote · a82a470 CI docker job · 1a8d8c9 DEPLOY.md · 03b5167 App Insights.
- Tests: pytest 645 (+23), Vitest 438, smoke 3 (gate checks exit codes, Vitest uncached).
- TODO(verify), 27 marks in DEPLOY.md: JMESPath paths (`registrationState`, `ingress.fqdn`, `principalId`,
  `environmentId`, `connectionString`), `az acr list/show`, ACR Basic `--sku`, Plan B `up --registry-identity`,
  `containerapp secret set` flags, Microsoft.ContainerRegistry need, 240 s limit on streams, App Insights data.
- Your commands (titles): 1.1 login · 1.2 extension · 1.3 providers · 1.4 budget check · 2 group · 3 `up --source`
  (or 11 Plan B) · 4 size/replicas · 5 URL · 6 smoke · 7 identity+role (optional) · 13 App Insights (optional).
- Cost (0.5 vCPU/1 GiB, Sweden Central, 2026-10-14): ~17-18 USD/month low traffic, ~44 worst case; min 0 is cheaper.
- Deviations: image also copies docs/LLM_RUN.json + DEMO_NARRATION.md (the guard needs them); `pip install -e`;
  credential helper in app/explain (app/llm has no `__init__`); App Insights uses `microsoft-opentelemetry` 1.3.9,
  not `azure-monitor-opentelemetry` (Learn's current advice, syntax verified), image 264 to 343 MB.
  Slip: a local `app.serve --help` test started a server by mistake (killed).
