// Explicit exceptions to the T1 scan (no hand-written numbers in JSX, UI_SPEC §7). Each entry names
// the file (path under src/), the exact snippet the scan reports, and why it is not a fact.
// provenance.test.tsx fails on an entry that no longer matches anything.
export interface Allowed {
  file: string;
  snippet: string;
  reason: string;
}

export const ALLOWED: Allowed[] = [];
