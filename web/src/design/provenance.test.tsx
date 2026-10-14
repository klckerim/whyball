// UI truthfulness contract (UI_SPEC §7): T2 on every real fixture card, T1 as a source scan.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { matchFixtures, metricsFixture } from "../test/fixtures";
import { SentenceText } from "./SentenceText";
import { scanJsx } from "../test/jsxScan";
import { eventId, Fact, NO_DATA } from "./Fact";
import { ALLOWED } from "./provenance.allow";

afterEach(cleanup);

const cards = matchFixtures.flatMap((m) => m.moments.map((moment) => ({ match: m, moment })));
const claims = cards.flatMap(({ match, moment }) => moment.claims.map((claim) => ({ match, moment, claim })));
const evidence = claims.flatMap(({ match, claim }) => claim.evidence.map((ev) => ({ match, ev })));

describe("T2: Fact carries an id from the payload and the exact value", () => {
  it("has real fixture data to check", () => {
    expect(matchFixtures.length).toBeGreaterThan(0);
    expect(claims.length).toBeGreaterThan(0);
    expect(evidence.length).toBeGreaterThan(0);
  });

  it.each(claims.map((c) => [c.moment.id, c.claim.id, c] as const))("%s claim %s", (_, __, { moment, claim }) => {
    const { container } = render(<Fact claim={claim} />);
    const el = container.querySelector("[data-claim-id]")!;
    expect(moment.claims.map((c) => c.id)).toContain(el.getAttribute("data-claim-id"));
    expect(el.textContent).toBe(claim.display);
    expect(container.textContent).toBe(claim.display);
  });

  it("renders every evidence event field from the payload", () => {
    for (const { match, ev } of evidence) {
      expect(ev.id).toBe(eventId(match.detail.event_match_id, ev.seq));
      for (const field of ["minute_label", "player", "team"] as const) {
        const { container, unmount } = render(<Fact event={ev} field={field} teams={match.detail.teams} />);
        const el = container.querySelector("[data-event-id]")!;
        expect(el.getAttribute("data-event-id")).toBe(ev.id);
        const value = ev[field];
        const expected = value === null ? NO_DATA : field === "team" ? match.detail.teams[value as "home" | "away"] : value;
        expect(el.textContent).toBe(expected);
        expect(el.hasAttribute("data-missing")).toBe(value === null);
        unmount();
      }
    }
  });

  it("renders a timeline event through its built id", () => {
    const { detail } = matchFixtures[0]!;
    const goal = detail.timeline.find((e) => e.type === "goal")!;
    const { container } = render(<Fact event={{ ...goal, id: eventId(detail.event_match_id, goal.seq) }} field="player" />);
    expect(container.querySelector("[data-event-id]")!.getAttribute("data-event-id")).toBe(`${detail.event_match_id}#${goal.seq}`);
    expect(container.textContent).toBe(goal.player);
  });

  it("renders the score of an event from its own score field", () => {
    for (const { detail, events } of matchFixtures) {
      for (const e of events.filter((x) => x.type === "goal")) {
        const ev = { ...e, id: eventId(detail.event_match_id, e.seq) };
        for (const [field, side] of [["score_home", "home"], ["score_away", "away"]] as const) {
          const { container, unmount } = render(<Fact event={ev} field={field} />);
          expect(container.querySelector("[data-event-id]")!.getAttribute("data-event-id")).toBe(ev.id);
          expect(container.textContent).toBe(String(e.score[side]));
          unmount();
        }
      }
    }
  });

  it("renders the other claim fields (window, subject, label) from the claim and keeps its id", () => {
    for (const { match, claim } of claims) {
      for (const field of ["start", "end", "player", "team", "label"] as const) {
        const { container, unmount } = render(<Fact claim={claim} field={field} teams={match.detail.teams} />);
        const el = container.querySelector("[data-claim-id]")!;
        expect(el.getAttribute("data-claim-id")).toBe(claim.id);
        const raw = claim[field];
        const expected = raw === null ? NO_DATA : field === "team" ? match.detail.teams[raw as "home" | "away"] : raw;
        expect(el.textContent).toBe(expected);
        expect(el.hasAttribute("data-missing")).toBe(raw === null);
        unmount();
      }
    }
  });

  it("renders every metric's rolling window length from /api/metrics", () => {
    const claim = claims[0]!.claim;
    for (const info of metricsFixture.metrics) {
      const { container, unmount } = render(<Fact claim={claim} window={info.window} />);
      expect(container.textContent).toBe(info.window.minutes == null ? NO_DATA : String(info.window.minutes));
      expect(container.querySelector("[data-claim-id]")!.getAttribute("data-claim-id")).toBe(claim.id);
      unmount();
    }
  });

  it("renders the recorded checks of every card with its card id", () => {
    for (const { moment } of cards) {
      for (const field of ["lint_issues", "claims_total", "claims_verified"] as const) {
        const { container, unmount } = render(<Fact checks={moment.checks} cardId={moment.id} field={field} />);
        const el = container.querySelector("[data-card-id]")!;
        expect(el.getAttribute("data-card-id")).toBe(moment.id);
        expect(el.textContent).toBe(String(moment.checks[field]));
        unmount();
      }
    }
  });

  it.each(cards.map((c) => [c.moment.id, c.moment] as const))("%s: the sentence is its segments, claim values are Facts", (_, moment) => {
    for (const interactive of [false, true]) {
      const { container, unmount } = render(<p><SentenceText segments={moment.segments} claims={moment.claims} interactive={interactive} /></p>);
      expect(container.textContent).toBe(moment.text);
      const shown = [...container.querySelectorAll("[data-claim-id]")].map((el) => [el.getAttribute("data-claim-id"), el.textContent]);
      expect(shown).toEqual(moment.segments.filter((s) => s.claim_id).map((s) => [s.claim_id, s.text]));
      for (const [id, text] of shown) expect(moment.claims.find((c) => c.id === id)!.display).toBe(text);
      unmount();
    }
  });

  it("draws a segment that names an unknown claim as plain text, not as a fact", () => {
    const { container } = render(<p><SentenceText segments={[{ text: "9", claim_id: "nope" }]} claims={[]} /></p>);
    expect(container.querySelector("[data-claim-id]")).toBeNull();
    expect(container.textContent).toBe("9");
  });

  it("never shows a missing value as zero", () => {
    const { container } = render(<Fact event={{ id: "e#1", player: null }} field="player" missing="no player" />);
    expect(container.textContent).toBe("no player");
    cleanup();
    const score = render(<Fact event={{ id: "e#1" }} field="score_home" />);
    expect(score.container.textContent).toBe(NO_DATA);
  });
});

// T1: every UI directory of src (the old UI is gone).
const sources = import.meta.glob<string>(
  ["/src/{app,api,design,stage,proof,breakit,method,overlay,state}/**/*.tsx", "!/src/**/*.test.tsx"],
  { query: "?raw", import: "default", eager: true },
);

describe("T1: no hand-written numbers in JSX", () => {
  const findings = Object.entries(sources).flatMap(([path, text]) => scanJsx(path.replace(/^\/src\//, ""), text));
  const allowed = (f: { file: string; snippet: string }) => ALLOWED.some((a) => a.file === f.file && a.snippet === f.snippet);

  it("scans the new UI sources", () => {
    expect(Object.keys(sources)).toContain("/src/design/Fact.tsx");
    for (const f of ["/src/stage/ScoreBug.tsx", "/src/stage/LowerThird.tsx", "/src/stage/Pitch.tsx", "/src/stage/OnAir.tsx",
      "/src/proof/Receipt.tsx", "/src/proof/EvidenceList.tsx", "/src/proof/MomentRail.tsx", "/src/design/SentenceText.tsx",
      "/src/app/App.tsx", "/src/app/MatchView.tsx", "/src/app/Transport.tsx", "/src/app/Timeline.tsx", "/src/app/TopBar.tsx"]) {
      expect(Object.keys(sources)).toContain(f);
    }
  });

  it("finds nothing outside the allow-list", () => {
    expect(findings.filter((f) => !allowed(f))).toEqual([]);
  });

  it("has no stale allow-list entries", () => {
    expect(ALLOWED.filter((a) => !findings.some((f) => f.file === a.file && f.snippet === a.snippet))).toEqual([]);
  });
});

describe("T1 scanner", () => {
  const rules = (src: string) => scanJsx("x.tsx", src).map((f) => [f.rule, f.snippet]);

  it.each([
    ["const a = <p>Shots: 3</p>;", [["jsx-text", "Shots: 3"]]],
    ["const a = <p>{3}</p>;", [["jsx-expression", "3"]]],
    ["const a = <p>{ok ? '2 shots' : 'none'}</p>;", [["jsx-expression", "'2 shots'"]]],
    ["const a = <p>{`${n} of 90`}</p>;", [["jsx-expression", "of 90"]]],
    ["const a = <p>{n + 1}</p>;", [["jsx-expression", "1"]]],
    ['const a = <i title="45 min" />;', [["text-attribute", '"45 min"']]],
    ["const a = <i aria-label={`${n} 90`} />;", [["text-attribute", "90"]]],
  ])("flags %s", (src, expected) => {
    expect(rules(src)).toEqual(expected);
  });

  it.each([
    "const a = (x: number) => x > 1 && <b>Hi</b>;",
    'const a = <h2 className="h2 col-3" data-n={2} style={{ gap: 8 }}>Title</h2>;',
    "const a = <p><Fact claim={c} /> shots</p>;",
    "const a = <ul>{xs.map((x) => <li key={x.id}>{x.label}</li>)}</ul>;",
  ])("allows %s", (src) => {
    expect(rules(src)).toEqual([]);
  });
});
