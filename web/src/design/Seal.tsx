// The verified seal reads only the card's own `checks` (recorded at publish by build_match). No checks
// record, or any failed check, shows "not verified": the seal is never a default.
import type { Checks } from "../api/types";
import styles from "./primitives.module.css";

export function isVerified(checks: Checks | null | undefined): boolean {
  return !!checks && checks.lint_issues === 0 && checks.claims_total > 0 && checks.claims_verified === checks.claims_total;
}

export function Seal({ checks }: { checks: Checks | null | undefined }) {
  const ok = isVerified(checks);
  return (
    <span
      className={styles.seal}
      data-verified={ok}
      role="img"
      aria-label={ok ? "Verified: the text passed lint and every claim passed verification" : "Not verified"}
    >
      {ok ? (
        <svg viewBox="0 0 16 16" aria-hidden="true">
          <path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : null}
      {ok ? "Verified" : "Not verified"}
    </span>
  );
}
