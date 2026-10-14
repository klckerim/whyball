# STATUS

Updated 2026-10-14. Project rules and commands: [CLAUDE.md](CLAUDE.md). UI: [UI_SPEC](docs/UI_SPEC.md), design log [DESIGN](docs/DESIGN.md).

## Frozen
- Scope freeze: evening of 24 October. No new features after that (CLAUDE.md).
- Synthetic seeded data only (fixtures change only via `app.generator.freeze`, [datasheet](docs/DATASHEET.md)).
- LLM only in the Explain stage. Guard (code) rejects first; the Verifier agent can only reject; 3 attempts, then template.
- foundry-v5.2 Narrator prompt and slot language are frozen (hash-pinned in tests, as are analyst-v1 and verifier-v1).
- API shapes: additive only (U0 `x`/`y`, `squads`; U1 `checks`, events, series; U2 `segments`; P2 `verification`, stored `trace`, `trace` SSE, `start_used`).

## Done
- Generator, analytics, moment detector, selector, claim verifier, template narrator, lint, cache, foundry-v2..v5.2 ([LLM_RUN](docs/LLM_RUN.md)), injection eval ([EVAL](docs/EVAL.md)).
- FastAPI (matches, moments, events, series, SSE incl. stored trace, `/healthz`, deep links); CI (pytest, Vitest + build, gitleaks, docker).
- UI: U0 foundation, U1 On Air, U2 Proof (Receipt, evidence pitch, Flip), old UI deleted. P1: image, guard, frozen API surface, deployed.
- P2 (this round, 21 commits): agent workflow on Agent Framework core 1.19.0 / foundry 1.13.1 (newest at least 14 days old). Analyst, Narrator
  (wrapped), Guard (code), Verifier; immutable state, 3-attempt edges, fallbacks, flags `analyst`/`verifier`, stored trace + `verification`
  on every card. The published store is the agent run ([AGENT_RUN](docs/AGENT_RUN.md)); offline CLI `python -m app.agents.run`.
  The service never imports agents (tests, CI step, `.dockerignore`); the image has no Agent Framework.

## In progress
- Everything on `master` is local until pushed; origin has U0 and tag `llm-baseline-v2` (the user pushed the P2 3a commit; CI was green then).

## Next
- Push; confirm CI. Redeploy (DEPLOY 8.1) to serve U2 + P2 (the live app still runs the P1 build).
- U3: show the trace (trace tape, Rejected takes, Red pen, Method); the seal label (`checker.ts`) changes when the trace is visible.
- P3: MCP client replaces `app/agents/tools.py`. P4: arms A/B/C measurement on a held-out set (not [DEVELOPMENT_SET](docs/DEVELOPMENT_SET.md)).
- Open API decision: `score`, `score_margin`, `players_on_pitch` still say `claim_range` (now with `start_used: false`).

## Decisions (with reason)
- CI pins actions to commit SHAs on Node 24 LTS; gitleaks-action needs no license key (personal repo).
- Claim menu (v5): the model picks menu ids, code builds the numbers. Segments come from the code that writes the text (D26).
- Replays use the stored publication, no live model call: the demo is deterministic and free. SSE trace is stored, not run (D37, D40).
- Agents: roles, state, limits, closed Verifier codes, D6 (Verifier failure labels, never blocks), arms A/B/C: DESIGN D32-D40.
- Verifier is shown each metric's window and definition and each clause's claims and meaning; an unlocated span is still a rejection.
- Analyst note: digits and cardinal numbers banned, ordinary words allowed; a clause id expands to its claims.
- Seal reads the card's `checks` and says "Checked by code" (one constant, `web/src/design/checker.ts`).

## Open risks / known limits
- Agent evidence is thin: 15 cards x 4 runs, 3 demo matches. Verifier smoke (development set): 12/12 injected rejected, 0/8 clean flagged;
  real cards: 0 true rejections, 2 false alarms (before the record fixes). No claim about agent value before P4.
- The Verifier gave different verdicts on identical input once (natural M008). 9 of 15 published texts differ from the pre-agent store
  (Narrator composition and Analyst narrowing, none from a Verifier rejection).
- dominant_loss M005 text has no scorer or minute (dull candidate, P4 labelling). Stored card red_card_swing 90+1' mentions an uncovered 84' goal.
- Minutes, names and event phrases inside a card sentence are plain text, not `<Fact>` (D26). 390 px stage pitch small (U5).
- Tests (2026-10-14, uncached): pytest 972, Vitest 415, `npm run smoke` 7; initial JS 113.7 KB gzip. After `app.publish` rerun `app.api.fixtures`.
- Price per token unknown (cost only in tokens). `.env.example` is tracked; never opened.

## Deploy state
- Azure Container Apps, one container, Sweden Central ([DEPLOY](docs/DEPLOY.md)); live address and first deploy in README / DEPLOY.
- Image: digest-pinned, non-root; `python -m app.serve` refuses to start if `app.publish --check` (now over AGENT_RUN.json) fails; CI scans it.
- Local image (U2 + P2 build): `smoke_remote.py` ALL PASSED incl. trace SSE and `verification` checks; no `agent_framework`, no `app/agents` inside.

## Mentor summary
- Commits P2: spike + 3a-3g (2fa6242..1d314d9), CLI, canary and reruns, smoke test, publish switch (this commit); two U2 fixes before them.
- Tests: pytest 972, Vitest 415, smoke 7 (+ remote smoke: trace-sse, verification); JS 113.7 KB (unchanged).
- Spike: cycles + conditional edges work; state is deep-copied (immutable state, read-modify-write); one workflow per run; failures propagate (caught).
- Pins: core 1.19.0, foundry 1.13.1, openai 1.14.4 (1.20+/1.14.x were younger than 14 days); findings re-verified on them.
- Live runs: 167 calls, 287.8k tokens in / 54.3k out across canary, rerun, two 15-card runs and 2 smoke runs. Final: 15 llm cards, 0 fallback,
  1 Analyst fallback, 0 Verifier rejections, 67.6 s, 83.3k/15.0k tokens. Analyst + Verifier are ~55% of input tokens.
- Deviations: self-written estimate; `app/agents` kept out of the image; stray `human_review.<ts>.csv` from a re-render deleted.
- TODO(verify): token prices; whether `claim_end` window kind should replace `claim_range` for state metrics in the API.
- First signs (not results): Verifier caught 12/12 injected drafts on a small development set; Analyst narrowing changed 2 texts by dropping possession.
