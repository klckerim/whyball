import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { eventId } from "../design/Fact";
import { PITCH_MARGIN } from "../design/PitchSurface";
import { SAFE_AREA } from "../design/safeArea";
import { eventAt, positioned } from "../state/match";
import { matchFixtures } from "../test/fixtures";
import { CHECKED_BY_CAPITAL } from "../design/checker";
import { LowerThird } from "./LowerThird";
import { OnAir } from "./OnAir";
import { Pitch, PITCH, toSvg } from "./Pitch";
import { ProgramStage } from "./ProgramStage";
import { ScoreBug } from "./ScoreBug";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function stubMedia(matches: Record<string, boolean>) {
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches: matches[q] ?? false,
    addEventListener() {},
    removeEventListener() {},
  }));
}

const fx = matchFixtures.find((m) => m.summary.id === "red_card_swing_seed42")!;
const meta = fx.events.find((e) => e.type === "match_meta")!;
const ids = new Set(fx.events.map((e) => eventId(fx.detail.event_match_id, e.seq)));

describe("program frame", () => {
  it("insets the content by the graphics-safe constant; guides use both constants", () => {
    render(<ProgramStage guides>content</ProgramStage>);
    expect(screen.getByTestId("graphics-safe").style.inset).toBe(`${SAFE_AREA.graphics * 100}%`);
    const guides = screen.getByTestId("guides");
    expect(guides.querySelector('[data-kind="action"]')!.getAttribute("style")).toContain(`${SAFE_AREA.action * 100}%`);
    expect(guides.querySelector('[data-kind="graphics"]')!.getAttribute("style")).toContain(`${SAFE_AREA.graphics * 100}%`);
  });

  it("has no guides unless asked", () => {
    render(<ProgramStage>content</ProgramStage>);
    expect(screen.queryByTestId("guides")).toBeNull();
  });
});

describe("score bug", () => {
  it.each(matchFixtures.map((m) => [m.summary.id, m] as const))("%s: names, marks, score and clock from events", (_, m) => {
    const mMeta = m.events.find((e) => e.type === "match_meta")!;
    for (const e of m.detail.timeline) {
      const current = eventAt(m.events, e.t)!;
      const { container, unmount } = render(<ScoreBug detail={m.detail} meta={mMeta} current={current} ended={false} />);
      const rows = container.querySelectorAll("[data-side]");
      expect([...rows].map((r) => r.getAttribute("data-side"))).toEqual(["home", "away"]);
      for (const side of ["home", "away"] as const) {
        const row = container.querySelector(`[data-side="${side}"]`)!;
        expect(row.querySelector("[data-mark]")!.getAttribute("data-mark")).toBe(side === "home" ? "dot" : "ring");
        const [name, score] = [...row.querySelectorAll("[data-event-id]")];
        expect(name!.textContent).toBe(m.detail.teams[side]);
        expect(name!.getAttribute("data-event-id")).toBe(eventId(m.detail.event_match_id, mMeta.seq));
        expect(score!.textContent).toBe(String(current.score[side]));
        expect(score!.getAttribute("data-event-id")).toBe(eventId(m.detail.event_match_id, current.seq));
      }
      expect(container.textContent).toContain(current.minute_label);
      unmount();
    }
  });

  it("marks the final whistle", () => {
    const current = eventAt(fx.events, fx.detail.duration_t)!;
    render(<ScoreBug detail={fx.detail} meta={meta} current={current} ended />);
    expect(screen.getByText("FT")).toBeTruthy();
  });
});

describe("pitch", () => {
  const points = positioned(fx.events);

  it("draws the ball only at a real position; nothing at 0,0 for a null", () => {
    for (const e of fx.events.filter((x) => x.x === null && x.type !== "match_meta")) {
      const before = [...points].reverse().find((p) => p.t <= e.t)!;
      const ball = { x: before.x, y: before.y, seq: before.seq };
      const { getByTestId, unmount } = render(<Pitch ball={ball} trail={[]} />);
      const c = getByTestId("ball");
      expect([Number(c.getAttribute("cx")), Number(c.getAttribute("cy"))]).toEqual([before.x, PITCH.h - before.y]);
      expect(ids.has(eventId(fx.detail.event_match_id, Number(c.getAttribute("data-seq"))))).toBe(true);
      unmount();
    }
  });

  it("says 'no location' when there is no position, and labels the feed as synthetic", () => {
    render(<Pitch ball={null} trail={[]} />);
    expect(screen.queryByTestId("ball")).toBeNull();
    expect(screen.getByText("no location")).toBeTruthy();
    expect(screen.getByText("synthetic feed visualization")).toBeTruthy();
  });

  it("flips y so y=0 is the bottom touchline", () => {
    expect(toSvg({ x: 10, y: 0 })).toEqual({ cx: 10, cy: PITCH.h });
  });
});

describe("lower third", () => {
  it.each(fx.moments.map((m) => [m.id, m] as const))("%s: glyph, minute, seal, source, text with claim values", (_, m) => {
    const { container } = render(<LowerThird moment={m} eventMatchId={fx.detail.event_match_id} placement="stage" />);
    const minute = container.querySelector("[data-event-id]")!;
    expect(minute.getAttribute("data-event-id")).toBe(eventId(fx.detail.event_match_id, m.at_seq));
    expect(fx.events.find((e) => e.seq === m.at_seq)!.minute_label).toBe(m.minute_label);
    expect(minute.textContent).toBe(m.minute_label);
    expect(container.querySelector("[data-verified]")!.getAttribute("data-verified")).toBe("true");
    expect(container.querySelector("[data-source]")!.getAttribute("data-source")).toBe(m.source);
    const text = container.querySelector("[data-card-id]")!;
    expect(text.getAttribute("data-card-id")).toBe(m.id);
    expect(text.textContent).toBe(m.text);
    // claim values are Facts that carry the claim id and the claim's display; the rest is plain text
    const values = [...text.querySelectorAll("[data-claim-id]")].map((el) => [el.getAttribute("data-claim-id"), el.textContent]);
    expect(values).toEqual(m.segments.filter((s) => s.claim_id).map((s) => [s.claim_id, s.text]));
  });
});

describe("On Air layout", () => {
  const shown = fx.moments.find((m) => m.type === "red_card")!;
  const props = { detail: fx.detail, events: fx.events, moments: fx.moments, t: shown.t, shownId: shown.id, guides: false };

  it("wide: the lower third is on the stage", () => {
    stubMedia({ "(min-width: 768px)": true });
    render(<OnAir {...props} />);
    const program = screen.getByTestId("program");
    expect(within(program).getByRole("region", { name: "Narration" })).toBeTruthy();
    expect(within(program).getByText("SYNTHETIC DATA")).toBeTruthy();
  });

  it("narrow: the lower third is a panel under the stage; the stage keeps bug, mark and seal", () => {
    stubMedia({ "(min-width: 768px)": false });
    render(<OnAir {...props} />);
    const program = screen.getByTestId("program");
    expect(within(program).queryByRole("region", { name: "Narration" })).toBeNull();
    expect(within(program).getByRole("group", { name: "Score" })).toBeTruthy();
    expect(within(program).getByText("SYNTHETIC DATA")).toBeTruthy();
    expect(within(program).getByRole("img", { name: new RegExp(`^${CHECKED_BY_CAPITAL}`) })).toBeTruthy();
    const panel = screen.getByRole("region", { name: "Narration" });
    expect(program.contains(panel)).toBe(false);
  });

  it("narrow, nothing on air: says so", () => {
    stubMedia({});
    render(<OnAir {...props} shownId={null} />);
    expect(screen.getByText("No card on air")).toBeTruthy();
  });

  it("reduced motion: the ball does not interpolate", () => {
    stubMedia({ "(min-width: 768px)": true, "(prefers-reduced-motion: reduce)": true });
    const points = positioned(fx.events);
    const k = points.findIndex((p, i) => points[i + 1] && points[i + 1]!.t - p.t >= 2 && points[i + 1]!.t - p.t <= 8 && points[i + 1]!.type !== "kickoff");
    const p = points[k]!;
    render(<OnAir {...props} t={p.t + 1} shownId={null} />);
    const ball = screen.getByTestId("ball");
    expect([Number(ball.getAttribute("cx")), Number(ball.getAttribute("cy"))]).toEqual([p.x, PITCH.h - p.y]);
  });
});

describe("stage pitch bounds", () => {
  it("shares the viewBox with room around the markings, so a ball on a line is not cut", () => {
    const { container } = render(<Pitch ball={{ x: PITCH.w, y: 0, seq: 1 }} trail={[]} />);
    const vb = container.querySelector("svg")!.getAttribute("viewBox")!.split(" ").map(Number) as [number, number, number, number];
    expect(vb).toEqual([-PITCH_MARGIN, -PITCH_MARGIN, PITCH.w + 2 * PITCH_MARGIN, PITCH.h + 2 * PITCH_MARGIN]);
    const ball = container.querySelector('[data-testid="ball"]')!;
    const r = Number(ball.getAttribute("r"));
    expect(Number(ball.getAttribute("cx")) + r).toBeLessThanOrEqual(vb[0] + vb[2]);
    expect(Number(ball.getAttribute("cy")) + r).toBeLessThanOrEqual(vb[1] + vb[3]);
  });
});
