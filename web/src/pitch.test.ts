import { describe, expect, it } from "vitest";

import { PITCH, spreadOverlaps, toPitch, VIEWBOX } from "./pitch";

const { pad } = PITCH;

describe("toPitch", () => {
  it("maps event metres onto the padded SVG with y flipped", () => {
    expect(toPitch(0, 0)).toEqual({ cx: pad, cy: pad + 68 }); // home goal line, bottom touchline
    expect(toPitch(105, 68)).toEqual({ cx: pad + 105, cy: pad }); // the end home attacks, top
    expect(toPitch(52.5, 34)).toEqual({ cx: pad + 52.5, cy: pad + 34 }); // centre spot
    expect(toPitch(96.5, 30.1)).toEqual({ cx: pad + 96.5, cy: pad + 37.9 });
  });

  it("clamps to the pitch and returns null without a position", () => {
    expect(toPitch(-4, 80)).toEqual({ cx: pad, cy: pad });
    expect(toPitch(null, 10)).toBeNull();
    expect(toPitch(10, undefined)).toBeNull();
    expect(toPitch(Number.NaN, 10)).toBeNull();
  });

  it("has a viewBox that holds the padded pitch", () => {
    expect(VIEWBOX).toBe(`0 0 ${105 + 2 * pad} ${68 + 2 * pad}`);
  });
});

describe("spreadOverlaps", () => {
  it("fans out points on one spot and leaves others alone", () => {
    const pts = [
      { id: "a", cx: 55.5, cy: 37 },
      { id: "b", cx: 55.5, cy: 37 },
      { id: "c", cx: 55.6, cy: 37.1 },
      { id: "d", cx: 20, cy: 10 },
    ];
    const out = spreadOverlaps(pts, 2);
    expect(out.map((p) => p.id)).toEqual(["a", "b", "c", "d"]);
    expect(out[3]).toEqual(pts[3]);
    for (const p of out.slice(0, 3)) expect(Math.hypot(p.cx - 55.5, p.cy - 37)).toBeCloseTo(2);
    const keys = new Set(out.slice(0, 3).map((p) => `${p.cx.toFixed(2)},${p.cy.toFixed(2)}`));
    expect(keys.size).toBe(3);
  });
});
