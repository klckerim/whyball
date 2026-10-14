// The seal as the way into Proof: a visible button "Proof · P" that carries the seal. P does the same.
import type { Checks } from "../api/types";
import { Seal } from "../design/Seal";
import styles from "./stage.module.css";

export function ProofSeal({ checks, onProof }: { checks: Checks; onProof?: () => void }) {
  if (!onProof) return <Seal checks={checks} />;
  return (
    <button type="button" className={styles.proofSeal} onClick={onProof} aria-keyshortcuts="P" title="Open the proof for this card">
      <Seal checks={checks} />
      <span className={styles.proofLabel}>Proof · P</span>
    </button>
  );
}
