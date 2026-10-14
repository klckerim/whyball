import { describe, expect, it } from "vitest";

import { fixtureFiles, manifest, matchFixtures } from "./fixtures";

async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

describe("test fixtures", () => {
  it("are exactly the files the manifest lists", () => {
    expect(Object.keys(fixtureFiles).sort()).toEqual([...Object.keys(manifest.files), "manifest.json"].sort());
  });

  it.each(Object.entries(manifest.files))("%s matches its manifest hash", async (name, digest) => {
    expect(await sha256(fixtureFiles[name]!)).toBe(digest);
  });

  it("cover every store file the manifest names", () => {
    const ids = matchFixtures.map((m) => m.summary.id).sort();
    expect(Object.keys(manifest.sources).map((p) => p.replace(/^.*\/|\.json$/g, "")).sort()).toEqual(ids);
    expect(matchFixtures.every((m) => m.moments.length === m.summary.moments)).toBe(true);
  });
});
