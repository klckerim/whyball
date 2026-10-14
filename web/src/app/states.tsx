// Screen states (UI_SPEC §5): loading, error with retry, not found, empty. Each says what is true.
import { Link } from "react-router";

import styles from "./app.module.css";

export function Loading({ what }: { what: string }) {
  return (
    <div className={styles.state} aria-busy="true" role="status">
      <div className={styles.skeleton} aria-hidden="true" />
      <p>Loading {what}…</p>
    </div>
  );
}

export function Failed({ what, error, retry }: { what: string; error: Error; retry: () => void }) {
  return (
    <div className={styles.state} role="alert">
      <p>Could not load {what}.</p>
      <p className={styles.detail}>{error.message}</p>
      <button type="button" className={styles.textButton} onClick={retry}>
        Retry
      </button>
    </div>
  );
}

export function NotFound({ what }: { what: string }) {
  return (
    <div className={styles.state} role="status">
      <p>{what}</p>
      <Link to="/">Open the default match</Link>
    </div>
  );
}

export function Empty({ children }: { children: string }) {
  return <p className={styles.empty}>{children}</p>;
}
