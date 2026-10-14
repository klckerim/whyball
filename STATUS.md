# STATUS

Updated 2026-10-14. Project rules and commands: [CLAUDE.md](CLAUDE.md). UI v2: [UI_SPEC](docs/UI_SPEC.md), [DESIGN](docs/DESIGN.md).

## Frozen
- Scope freeze: evening of 24 October. No new features after that (CLAUDE.md).
- Synthetic seeded data only; fixtures change only via `app.generator.freeze` ([datasheet](docs/DATASHEET.md)).
- LLM only in the Explain stage; unverified sentences are never published (max 2 retries, then template).
- API response shapes: only additive changes (U0: timeline `x`/`y`, `squads`; U1: card `checks`, events, series).

## Done
- Generator, analytics and moment detector, selector, claim verifier, template narrator, lint, cache.
- Foundry narrator foundry-v2 → v5.2 (claim menu); 3 live runs, 0/45 fallbacks ([LLM_RUN](docs/LLM_RUN.md)).
- Injection eval across v2–v5.2 ([EVAL](docs/EVAL.md)); human review labels in `docs/human_review*.csv`.
- Publication store replays the last run ([DEMO_NARRATION](docs/DEMO_NARRATION.md)).
- FastAPI: matches, moments, events, metric series, SSE replay, `/healthz`; serves the UI with deep links.
- Repo hygiene: README skeleton, CI workflow (pytest, Vitest + build, gitleaks), this file.
- U0 (UI v2 foundation, no screens): UI_SPEC + DESIGN log; `/healthz`, `/api/metrics`, timeline `x`/`y`,
  `squads`; OpenAPI → `web/src/api/schema.gen.ts` + drift checks; `web/test-fixtures/` from the real API;
  `<Fact>` + T1/T2 tests; `web/src/design/tokens.css` (light/dark, stage always dark); fonts; Radix.
- U1 (7 commits): new UI is the shipped one: shell, routes, On Air stage, transport, timeline, pressure
  band, dwell; card `checks` recorded at publish; old UI at `/legacy` until U2. Screens reviewed (3 shots).

## In progress
- 7 U1 commits on `master` only, not pushed; U0 and tag `llm-baseline-v2` are on origin. CI not checked here.

## Next
- Push U1; confirm CI. Then U2: Proof (Receipt, moment rail), value spans in the card text, delete old UI.
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
- Eval and run samples are small (15 moments per run, 3 runs); one data point per prompt version.
- Stored card red_card_swing 90+1' mentions an 84' goal that none of its claims cover.
- Tests (2026-10-14, uncached): pytest 622, Vitest 438, `npm run smoke` 3; initial JS 109.4 KB gzip.
- Card text has no value spans: lower third draws it as one plain block, numbers in it are not `<Fact>`.
- 390 px: pitch is small, close timeline glyphs overlap near full time (mobile polish, U5).
- After `app.publish`, rerun `python -m app.api.fixtures` (pytest fails until then, by design).
- Two of the three demo matches share one run id and one prompt version.
- `.env.example` is tracked on purpose and matches the `\.env` hygiene grep; not opened (deny rule).

## Deploy state
- Target: Azure Container Apps, one container (API + built UI). `/healthz` exists (U0).
- CI (`.github/workflows/ci.yml`) tests and scans only. Not started: no Dockerfile, no infra files.
- Needs `web/dist` built before the image; keys stay in `.env`, never committed.

## Commands
All in [CLAUDE.md](CLAUDE.md). Daily: `.venv/bin/pytest -q`, `cd web && npm test`, `node web/tools/shots/shots.mjs`.

## Mentor summary
- Commits (U1): d8b7c1f checks per card · 50f0082 series/events/SPA · f4ef868 clock+dwell · 7676e01 Seal/
  SourceBadge/TypeGlyph · ff1aa8e stage · fb597b1 shell/routes/transport · b21c525 shots + review fixes.
- Tests: pytest 622 (+24), Vitest 438 (+105), smoke 3; gate script checks exit codes, Vitest uncached.
- provenance.allow.ts: 0 entries. Three scan hits were fixed in code (two logic literals hoisted out of JSX;
  "Proof arrives in U2" reworded without a digit, deviating from your wording).
- Card schema gaps: verification now recorded (`checks`); sentence/value spans still missing (U2 open item).
- Not via `<Fact>`: picker team names (`<option>` cannot hold markup), the "whole match in about N s" hint
  (computed from the duration), minute labels inside accessible names.
- JS: 109.4 KB gzip initial (budget 250); old UI is a separate lazy chunk.
- Deviation: the step-4 commit first went in with one failing test (my command checked grep's exit code,
  not Vitest's); amended before anything else; every commit since passes through the gate script.
- TODO(verify): none.
- Look-alike to the forbidden list: blue home dot/band on a near-navy stage; accent is yellow, not cyan.
- Screenshots: notes/shots/u1/{1440x900-dark,1920x1080-light,390x844-dark}.png (no scroll, no console errors).
- Next: push U1 and check CI, then U2 (Proof, value spans, remove the old UI).
