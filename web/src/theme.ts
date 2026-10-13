export type Theme = "light" | "dark";
const KEY = "whyball.theme";

/** The viewer's explicit choice; null follows the system setting. */
export function storedTheme(): Theme | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

export function systemTheme(): Theme {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Applies an explicit choice (null: no data-theme, the CSS media query decides). */
export function applyTheme(theme: Theme | null): void {
  if (theme) document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
  try {
    if (theme) localStorage.setItem(KEY, theme);
  } catch {
    // private window or blocked storage: the choice lasts for this page only
  }
}
