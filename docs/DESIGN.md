# Design decision log

Every UI design decision with its reason and source. **[standard]** = taken from a cited standard
(source linked); **[design]** = our own parameter, not a standard. Spec: [UI_SPEC.md](UI_SPEC.md).
Newest entries at the bottom.

## D1. Safe areas [standard]
- Graphics stay inside the **graphics-safe** area: **5 %** from each edge. Critical action stays inside
  the **action-safe** area: **3.5 %** from each edge.
- Source: EBU R 095 "Safe areas for 16:9 television production", version 1.1, June 2017,
  <https://tech.ebu.ch/publications/r095> (checked 2026-10-14: "the action safe area is 3.5%",
  "the graphics safe area is 5%", per edge).
- At the 1920×1080 design size: graphics-safe inset 96 px horizontal / 54 px vertical; action-safe 67.2 px / 37.8 px.

## D2. Flashes and motion
- [standard] Nothing flashes more than three times in any one second. Source: WCAG 2.2, SC 2.3.1
  "Three Flashes or Below Threshold", Level A,
  <https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html> (checked 2026-10-14).
- [design] Transitions are fades/slides of at most 400 ms, no strobe, disabled under
  `prefers-reduced-motion`. The 400 ms cap is our parameter, not part of the standard.

## D3. Contrast thresholds [standard]
- Text ≥ 4.5:1 (WCAG 2.2 SC 1.4.3, AA); indicators, focus rings and interactive borders ≥ 3:1
  (WCAG 2.2 SC 1.4.11, AA). Meaning is never carried by colour alone (SC 1.4.1).
- Enforced by `web/src/design/tokens.test.ts` for every token pair in both themes.

## D4. Dark and light themes, always-dark stage [design]
- Default follows `prefers-color-scheme`; a manual switch is stored in `localStorage` inside try/catch
  (blocked storage: the choice lasts for the page only).
- The program stage uses separate `--stage-*` tokens that are dark in both themes: it represents the
  broadcast picture, the app frame around it follows the theme.

## D5. Home and away are not told apart by colour [design]
- Home/away luminance ratio is 1.13 (dark) and 1.06 (light): too close for colour-blind viewers.
- Home: filled circle; away: ring/square; the team name label is always next to the mark.

## D6. Broadcast readability parameters [design]
- 16:9 frame at 1920×1080; body ≥ 32 px and numbers ≥ 56 px at 1080p; dwell `max(4 s, reading time)`;
  60 fps target. These are our parameters, not a standard; checked in U5.

## D7. No invented data on screen [design]
- Every number, name and time goes through `<Fact>`, which carries `data-claim-id` or `data-event-id`
  (contract T1/T2 in UI_SPEC §7). A source scan bans digits in JSX outside an explicit allow-list
  (`web/src/design/provenance.allow.ts`). It parses TSX with Vite's own `parseAst` (rolldown/oxc), so
  `x > 1 && <b/>` is not mistaken for JSX text; old UI files are not scanned.
- Reason: the product's only promise is that every published value is verified; the UI must not be the
  place where an unverified number appears.

## D8. Test fixtures come from the publication store [design]
- `web/test-fixtures/` is written by `python -m app.api.fixtures` from the real API over
  `data/demo_narration/`; a manifest holds the source store and fixture sha256. Hand-written sample data
  is not allowed (contract T7).

## D9. Metric definitions live in backend code [design]
- `/api/metrics` serves label, definition and window per metric. Labels already existed
  (`app/explain/labels.py`); definitions are written next to them from the `measure()` code, and a
  test keeps the set equal to the metric registry. The UI writes no definition (contract T5).

## D10. Generated API types through an isolated tool package [design]
- `openapi-typescript` 7.13.0 declares peer `typescript ^5.x` and uses the TypeScript JS compiler API.
  The web app uses TypeScript 7.0.2 (native compiler, no classic JS API), so a plain dev dependency
  fails with a peer conflict.
- The generator lives in `web/tools/openapi-gen/` with its own lockfile (openapi-typescript 7.13.0,
  typescript 5.9.3). The app keeps TS 7. Drift is checked on both sides: pytest compares
  `web/openapi.json` with the app, `npm run check:api` compares the generated TS with the JSON.

## D11. Token values [design, checked against D3]
- `web/src/design/tokens.css` uses the UI_SPEC §6 starting values unchanged: every pair passed in both
  themes (lowest text pair: light `--away` on `--surface-2` 4.67; lowest mark: dark `--control-border` on
  `--surface-2` 3.44).
- Added beyond the spec table: `--border` (decorative, light `#d5dce6`, dark `#263241`, not contrast-checked),
  `--focus` (light = `--accent-ink`, dark = `--accent`), dark `--accent-ink` = `--accent` (yellow is
  readable as text on dark), `--stage-*` = the dark palette, defined once on `:root`.
- Light `--accent` is a fill only (1.33:1 on the light background); text on it uses `--accent-fg`.
- The test also fails when a colour token is not in any checked pair (except `--border` and the
  `--accent` fill), so a new token cannot skip the check.

## D12. Self-hosted fonts [design; licence checked]
- Barlow Condensed (display, numbers: 600/700) and Inter (UI text: 400/600), latin subset only, from
  `@fontsource/barlow-condensed` 5.3.0 and `@fontsource/inter` 5.3.0 (exact pins), bundled by Vite: no CDN,
  no viewer data to a third party, works offline. Entry: `web/src/design/fonts.css`.
- Licence: both packages declare `OFL-1.1` and ship the full SIL Open Font License 1.1 text with the
  upstream copyright (Inter: "Copyright 2016 The Inter Project Authors"; Barlow: "Copyright 2017 The
  Barlow Project Authors"). Copied unchanged to `web/licenses/` (checked 2026-10-14).

## D13. Radix UI primitives [design; licence checked]
- Only the five primitives UI v2 needs, exact pins: `@radix-ui/react-tabs` 1.2.1, `-dialog` 1.3.1,
  `-tooltip` 1.4.1, `-toggle-group` 1.2.1, `-popover` 1.3.1. Unstyled: keyboard, focus and ARIA come from
  Radix, the look from our tokens, so the UI does not read as a stock kit.
- Licence (checked 2026-10-14 in the installed packages): all 31 `@radix-ui/*` packages declare MIT and the
  five direct ones ship an MIT LICENSE file. The 13 other transitive packages are MIT, except `tslib`
  (0BSD, permissive).
- `web/src/design/radix.smoke.test.tsx` checks each primitive under our React version (jsdom needs a
  ResizeObserver stub for the popper-based Tooltip and Popover).

## D14. Replay clock model [design]
- The On Air stage plays the fetched events (`GET /api/matches/{id}/events`) with a client clock
  (`web/src/state/clock.ts`, `playback.ts`), not the SSE replay: seek and scrub are exact, and tests run
  with fake timers. The SSE replay stays the machine-readable feed for `/overlay` and outside consumers (U5).
- One 100 ms timer moves the clock by wall-clock dt × speed and drives the dwell countdown.

## D15. Replay speeds [design]
- Speed = match seconds per wall-clock second, the same unit as the replay API `speed`.
  `1×` = 60 (one match minute per second, a 90-minute match in 90 s), `Fast` = 120 (45 s),
  `Faster` = 300 (18 s). The UI shows the wall time computed from the match's own duration, not a
  rounded "90 minutes".

## D16. Lower-third dwell [design parameter, not a standard]
- A card stays on screen for `max(4 s, characters / 15 per second)` (UI_SPEC B6; `READING_CPS` = 15 in
  `web/src/state/dwell.ts`). Counted in wall-clock time while playing; pausing stops it. Several cards:
  FIFO. Seeking clears the queue; previous/next shows that card at once.

## D17. Ball marker and trail [design parameters]
- Position only from events that carry `x, y`; a null position is never drawn (not at 0,0). Before the
  first positioned event: "no location".
- Between two positioned events the marker moves in a straight line (visual only, labelled "synthetic
  feed visualization"), unless they are more than 8 s apart (`BALL.gapS`) or the next one is a kickoff:
  then it holds at the last position. `prefers-reduced-motion`: no interpolation, the marker jumps.
- Trail: positioned events of the last 12 match seconds, at most 6, cut at a gap and at a kickoff.

## D18. Narrow layout breakpoint [design parameter]
- Below 768 px wide the lower third leaves the stage and becomes a panel under it; the stage keeps the
  score bug, the SYNTHETIC DATA mark and the seal. At that width a lower third scaled into the 16:9 frame
  would be too small to read.

## D19. Touch targets and keyboard seek [design parameters]
- Buttons, tabs, speed choices, the match picker and the timeline track are at least 44 × 44 px. Moment
  glyph buttons on the timeline are 28 × 44 px so close moments stay separate; previous/next moment
  buttons reach the same cards at full size.
- Timeline keys: ←/→ 30 match seconds, PageUp/PageDown 5 minutes, Home/End kickoff and final whistle.

## D20. JS budget [design parameter]
- Initial JS ≤ 250 KB gzip. Measured after U1: 109.4 KB gzip (`index-*.js`, 340.9 KB raw); the old UI
  is a separate 8.6 KB gzip chunk loaded only on `/legacy`. Fonts are separate woff2 files.

## D21. Seal source
- The seal reads the card's own `checks` (lint issues, claims total, claims verified), written by
  `build_match` at publish time from the `run_moment` result. Missing or failing checks show "Not
  verified". Before U1 no card recorded this; the store only held passing cards by construction.

## D22. Event stream endpoint
- `GET /api/matches/{id}/events` returns every event (match_meta included) in the timeline shape. The
  match detail timeline holds only goals, cards and whistles, too few for a ball marker.
- Team names on the score bug are tied to the match_meta event (seq 0) through `<Fact>`.

## D23. Default match and open state [design]
- `/` shows the first match the API lists. A match opens paused: on the deep-linked `?moment=`, else at
  `?t=` (seconds on the continuous clock), else on the first model-written (`llm`) card, so the first
  view shows a full lower third rather than an empty kickoff.

## D24. Old UI isolation
- The old UI stays at `/legacy` until U2, loaded with `React.lazy` together with its own global CSS.
  CSS loaded by a lazy chunk is not removed on client-side navigation, so `/legacy` is reached only by a
  full page load (typed URL or plain link); the new UI never shares a document with the old CSS.
