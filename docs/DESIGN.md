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
  (contract T1/T2 in UI_SPEC §7). A source scan bans digits in JSX outside an explicit allow-list.
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
