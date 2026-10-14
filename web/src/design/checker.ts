// Who ran the checks, in one place. Today lint and claim verification are run by code; when a Verifier
// agent exists (P2) this is the only line to change. Every label, aria text and test reads it.
export const CHECKED_BY = "checked by code";

/** Sentence-case form for the seal ("Checked by code"). */
export const CHECKED_BY_CAPITAL = CHECKED_BY.charAt(0).toUpperCase() + CHECKED_BY.slice(1);
