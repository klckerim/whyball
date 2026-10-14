import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { Source } from "../api/types";
import { matchFixtures } from "../test/fixtures";
import { CHECKED_BY_CAPITAL } from "./checker";
import { isVerified, Seal } from "./Seal";
import { SourceBadge, SOURCES } from "./SourceBadge";
import { MOMENT_TYPES, TypeGlyph, typeLabel } from "./TypeGlyph";

afterEach(cleanup);

const moments = matchFixtures.flatMap((m) => m.moments);

describe("TypeGlyph", () => {
  it.each([...new Set(moments.map((m) => m.type))])("maps fixture type %s to its own shape and name", (type) => {
    expect(MOMENT_TYPES[type]).toBeDefined();
    render(<TypeGlyph type={type} />);
    const img = screen.getByRole("img", { name: MOMENT_TYPES[type]!.label });
    expect(img.getAttribute("data-shape")).not.toBe("neutral");
  });

  it("gives every known type a different shape", () => {
    const shapes = Object.values(MOMENT_TYPES).map((t) => t.shape);
    expect(new Set(shapes).size).toBe(shapes.length);
  });

  it("an unknown type gets the neutral glyph and keeps its words", () => {
    render(<TypeGlyph type="corner_flurry" />);
    expect(screen.getByRole("img", { name: "corner flurry" }).getAttribute("data-shape")).toBe("neutral");
    expect(typeLabel("corner_flurry")).toBe("corner flurry");
  });
});

describe("SourceBadge", () => {
  // every value of the generated Source enum (the store has no template_fallback card today)
  const all: Source[] = ["llm", "template", "template_fallback"];

  it.each(all)("%s carries text and a border style, not only colour", (source) => {
    const { container } = render(<SourceBadge source={source} />);
    const el = container.querySelector("[data-source]")!;
    expect(el.textContent).toBe(SOURCES[source].label);
    expect(el.getAttribute("title")).toBe(SOURCES[source].title);
    expect(el.getAttribute("data-style")).toBe(SOURCES[source].style);
  });

  it("styles and labels are all different", () => {
    expect(new Set(all.map((s) => SOURCES[s].style)).size).toBe(all.length);
    expect(new Set(all.map((s) => SOURCES[s].label)).size).toBe(all.length);
  });

  it("covers every source in the fixtures", () => {
    for (const m of moments) expect(SOURCES[m.source]).toBeDefined();
  });
});

describe("Seal", () => {
  it.each(moments.map((m) => [m.id, m] as const))("%s: verified from its own checks", (_, m) => {
    expect(isVerified(m.checks)).toBe(true);
    render(<Seal checks={m.checks} />);
    expect(screen.getByRole("img").getAttribute("data-verified")).toBe("true");
    expect(screen.getByRole("img").textContent).toBe(CHECKED_BY_CAPITAL);
  });

  it.each([
    ["no record", null],
    ["a lint issue", { lint_issues: 1, claims_total: 2, claims_verified: 2 }],
    ["a failed claim", { lint_issues: 0, claims_total: 2, claims_verified: 1 }],
    ["no claims", { lint_issues: 0, claims_total: 0, claims_verified: 0 }],
  ])("is not verified with %s", (_, checks) => {
    expect(isVerified(checks)).toBe(false);
    render(<Seal checks={checks} />);
    expect(screen.getByRole("img", { name: "Checks not passed or not recorded" }).textContent).toBe("Checks not passed");
  });
});
