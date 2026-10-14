import { describe, expect, it } from "vitest";

import tokens from "./tokens.css?raw";

const sources = import.meta.glob<string>(["./**/*.{ts,tsx,css}", "!./**/*.test.*", "!./tokens.css", "!./design/tokens.css"], {
  query: "?raw",
  import: "default",
  eager: true,
});

function block(selector: string): Record<string, string> {
  const start = tokens.indexOf(selector);
  const body = tokens.slice(tokens.indexOf("{", start) + 1, tokens.indexOf("}", start));
  return Object.fromEntries([...body.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})\s*;/gi)].map((m) => [m[1], m[2]]));
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const TYPES = ["goal", "red", "penalty", "pressure", "dominance"];
// Text and badges: 4.5:1 (WCAG AA). Marks, focus rings, control borders: 3:1 (non-text contrast).
const TEXT: [string, string][] = [
  ...["bg", "surface", "surface-2", "accent-soft"].flatMap((bg) => [["text", bg], ["muted", bg]] as [string, string][]),
  ["accent", "surface"],
  ["accent", "bg"],
  ["accent-fg", "accent"],
  ["llm-fg", "llm-bg"],
  ["tpl-fg", "tpl-bg"],
  ["fb-fg", "fb-bg"],
  ["ok", "surface"],
  ["ok", "surface-2"],
  ["fail", "surface"],
  ["home-fg", "home"],
  ["away-fg", "away"],
  ...TYPES.map((t) => [t, "surface"] as [string, string]),
];
const GRAPHIC: [string, string][] = [
  ["focus", "bg"],
  ["focus", "surface"],
  ["control-border", "surface"],
  ["accent", "surface-2"],
  ["home", "pitch"],
  ["away", "pitch"],
  ["accent", "pitch"],
  ...TYPES.map((t) => [t, "surface-2"] as [string, string]),
];

describe.each([
  ["light", ":root {"],
  ["dark", ':root[data-theme="dark"]'],
])("%s theme", (_, selector) => {
  const t = block(selector);
  it.each(TEXT)("text %s on %s ≥ 4.5", (fg, bg) => {
    expect(contrast(t[fg]!, t[bg]!)).toBeGreaterThanOrEqual(4.5);
  });
  it.each(GRAPHIC)("mark %s on %s ≥ 3", (fg, bg) => {
    expect(contrast(t[fg]!, t[bg]!)).toBeGreaterThanOrEqual(3);
  });
});

it("system dark and explicit dark use the same tokens", () => {
  expect(block(':root:not([data-theme="light"])')).toEqual(block(':root[data-theme="dark"]'));
});

it("has no colour literals outside tokens.css", () => {
  expect(Object.keys(sources).length).toBeGreaterThan(5);
  for (const [path, text] of Object.entries(sources)) {
    expect([path, text.match(/#[0-9a-f]{3,8}\b(?![-\w])|\b(?:rgb|hsl)a?\(/gi)]).toEqual([path, null]);
  }
});
