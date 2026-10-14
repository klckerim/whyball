import { useEffect, useState } from "react";

/** Live result of a media query; false where matchMedia is missing (tests, old browsers). */
export function useMediaQuery(query: string): boolean {
  const get = () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(query).matches : false);
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    if (!window.matchMedia) return;
    const mql = window.matchMedia(query);
    const on = () => setMatches(mql.matches);
    on();
    mql.addEventListener?.("change", on);
    return () => mql.removeEventListener?.("change", on);
  }, [query]);
  return matches;
}

/** Below this width the lower third leaves the stage and becomes a panel under it (DESIGN D18). */
export const WIDE = "(min-width: 768px)";
export const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";
