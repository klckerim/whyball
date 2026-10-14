// WCAG contrast of every token pair the UI v2 uses, in both themes (docs/DESIGN.md D3).
import { describe, expect, it } from "vitest";

import tokens from "./tokens.css?raw";

type Block = Record<string, string>;

function block(selector: string): Block {
  const start = tokens.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`no block ${selector}`);
  const body = tokens.slice(tokens.indexOf("{", start) + 1, tokens.indexOf("}", start));
  return Object.fromEntries([...body.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})\s*;/gi)].map((m) => [m[1], m[2]!.toLowerCase()]));
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!;
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
}

const root = block(":root");
const darkMedia = block(':root:not([data-theme="light"])');
const darkExplicit = block(':root[data-theme="dark"]');
const stage: Block = Object.fromEntries(Object.entries(root).filter(([k]) => k.startsWith("stage-")));
const light: Block = Object.fromEntries(Object.entries(root).filter(([k]) => !k.startsWith("stage-")));
const dark: Block = darkExplicit;

const SURFACES = ["bg", "surface", "surface-2"];
const on = (fgs: string[], bgs: string[]): [string, string][] => fgs.flatMap((fg) => bgs.map((bg) => [fg, bg] as [string, string]));

// Text (≥ 4.5:1, SC 1.4.3) and indicators/interactive borders (≥ 3:1, SC 1.4.11).
const TEXT = [
  ...on(["text", "muted", "accent-ink", "verified", "reject", "src-llm", "src-fallback", "home", "away"], SURFACES),
  ["accent-fg", "accent"] as [string, string],
];
const GRAPHIC = on(["control-border", "focus"], SURFACES);
// Not checked against a background: --border (decorative), --accent (a fill; text on it is accent-fg).
const UNPAIRED = ["border", "accent"];

const STAGE_TEXT = [
  ...on(["stage-text", "stage-muted", "stage-accent", "stage-verified", "stage-reject", "stage-home", "stage-away"],
    ["stage-bg", "stage-surface", "stage-surface-2"]),
  ["stage-accent-fg", "stage-accent"] as [string, string],
];

describe.each([
  ["light", light],
  ["dark", dark],
])("%s theme", (_, t) => {
  it.each(TEXT)("text %s on %s ≥ 4.5", (fg, bg) => {
    expect(contrast(t[fg]!, t[bg]!)).toBeGreaterThanOrEqual(4.5);
  });
  it.each(GRAPHIC)("mark %s on %s ≥ 3", (fg, bg) => {
    expect(contrast(t[fg]!, t[bg]!)).toBeGreaterThanOrEqual(3);
  });
  it("checks every colour token in a pair (or lists it as unpaired)", () => {
    const paired = new Set([...TEXT, ...GRAPHIC].flat());
    expect(Object.keys(t).filter((k) => !paired.has(k) && !UNPAIRED.includes(k))).toEqual([]);
  });
});

describe("stage (dark in both themes)", () => {
  it.each(STAGE_TEXT)("text %s on %s ≥ 4.5", (fg, bg) => {
    expect(contrast(stage[fg]!, stage[bg]!)).toBeGreaterThanOrEqual(4.5);
  });
  it("is defined once and never overridden by a theme", () => {
    expect(Object.keys(stage).length).toBeGreaterThan(0);
    expect(Object.keys(darkMedia).filter((k) => k.startsWith("stage-"))).toEqual([]);
    expect(Object.keys(darkExplicit).filter((k) => k.startsWith("stage-"))).toEqual([]);
    expect(luminance(stage["stage-bg"]!)).toBeLessThan(luminance(stage["stage-text"]!));
  });
  it("checks every stage token in a pair", () => {
    const paired = new Set(STAGE_TEXT.flat());
    expect(Object.keys(stage).filter((k) => !paired.has(k))).toEqual([]);
  });
});

it("system dark and explicit dark use the same tokens", () => {
  expect(darkMedia).toEqual(darkExplicit);
});

it("dark overrides every light token", () => {
  expect(Object.keys(dark).sort()).toEqual(Object.keys(light).sort());
});

it("computes WCAG ratios (black on white is 21:1)", () => {
  expect(contrast("#000000", "#ffffff")).toBeCloseTo(21, 5);
});
