import { afterEach, describe, expect, it, vi } from "vitest";

import { activeTheme, applyTheme, initTheme, storedTheme, THEME_KEY, toggleTheme } from "./theme";

function systemPrefersDark(dark: boolean) {
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: dark && q === "(prefers-color-scheme: dark)" }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("theme", () => {
  it("follows the system setting when nothing is chosen", () => {
    systemPrefersDark(true);
    expect(storedTheme()).toBeNull();
    expect(activeTheme()).toBe("dark");
    systemPrefersDark(false);
    expect(activeTheme()).toBe("light");
  });

  it("stores a manual choice and re-applies it on start-up", () => {
    systemPrefersDark(true);
    expect(toggleTheme()).toBe("light");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
    delete document.documentElement.dataset.theme;
    initTheme();
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(toggleTheme()).toBe("dark");
  });

  it("clears the choice with null", () => {
    applyTheme("dark");
    applyTheme(null);
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
  });

  it("ignores an unknown stored value", () => {
    localStorage.setItem(THEME_KEY, "sepia");
    expect(storedTheme()).toBeNull();
  });

  it("still switches when storage is blocked", () => {
    systemPrefersDark(false);
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(storedTheme()).toBeNull();
    expect(toggleTheme()).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
