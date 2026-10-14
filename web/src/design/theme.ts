// Theme choice for UI v2 (docs/DESIGN.md D4): the system setting by default, a manual switch on top.
// The choice is stored in localStorage when it is reachable; otherwise it lasts for the page only.
export type Theme = "light" | "dark";
export const THEME_KEY = "whyball.theme";

/** The viewer's explicit choice; null follows the system setting. */
export function storedTheme(): Theme | null {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

export function systemTheme(): Theme {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** The theme on screen: the explicit choice, else the system setting. */
export function activeTheme(): Theme {
  const set = document.documentElement.dataset.theme;
  return set === "light" || set === "dark" ? set : systemTheme();
}

/** Applies a choice (null: no data-theme, the CSS media query decides) and remembers it. */
export function applyTheme(theme: Theme | null): void {
  if (theme) document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
  try {
    if (theme) localStorage.setItem(THEME_KEY, theme);
    else localStorage.removeItem(THEME_KEY);
  } catch {
    // private window or blocked storage: the choice lasts for this page only
  }
}

/** The manual switch: flips whatever is on screen. */
export function toggleTheme(): Theme {
  const next: Theme = activeTheme() === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}

/** On start-up: re-apply a stored choice. */
export function initTheme(): void {
  const theme = storedTheme();
  if (theme) document.documentElement.dataset.theme = theme;
}
