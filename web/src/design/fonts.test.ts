import { describe, expect, it } from "vitest";

import fonts from "./fonts.css?raw";

const licences = import.meta.glob<string>("/licenses/*.txt", { query: "?raw", import: "default", eager: true });
const imports = [...fonts.matchAll(/@import\s+"([^"]+)"/g)].map((m) => m[1]!);

describe("self-hosted fonts", () => {
  it("imports only local @fontsource packages, no remote URL", () => {
    expect(imports.length).toBeGreaterThan(0);
    expect(imports.every((p) => p.startsWith("@fontsource/"))).toBe(true);
    expect(fonts).not.toMatch(/https?:/);
  });

  it.each(imports)("%s resolves to local woff2 files of a family the tokens name", async (path) => {
    const css: string = (await import(/* @vite-ignore */ `${path}?raw`)).default;
    const family = css.match(/font-family:\s*'([^']+)'/)![1]!;
    expect(fonts).toContain(`"${family}"`);
    expect(css).toMatch(/url\(\.\/files\/[\w-]+\.woff2\)/);
  });

  it.each([
    ["Inter-OFL-1.1.txt", "The Inter Project Authors"],
    ["BarlowCondensed-OFL-1.1.txt", "The Barlow Project Authors"],
  ])("ships the licence text %s", (file, copyright) => {
    const text = licences[`/licenses/${file}`]!;
    expect(text).toContain("SIL OPEN FONT LICENSE Version 1.1");
    expect(text).toContain(copyright);
  });
});
