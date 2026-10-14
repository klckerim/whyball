// The card sentence from its stored segments. Plain pieces are text; a piece that states a claim's value
// is drawn by <Fact> (data-claim-id), and in the Receipt it is a button that selects that claim. A segment
// that names a claim the card does not hold is drawn as plain text, never as a fact.
import type { Claim, Segment } from "../api/types";
import { Fact } from "./Fact";
import styles from "./primitives.module.css";

interface Props {
  segments: readonly Segment[];
  claims: readonly Claim[];
  /** Claim values become buttons (aria-pressed) that call `onSelect`. */
  interactive?: boolean;
  selectedId?: string | null;
  onSelect?: (claimId: string) => void;
}

export function SentenceText({ segments, claims, interactive = false, selectedId = null, onSelect }: Props) {
  return (
    <>
      {segments.map((seg, i) => {
        const claim = seg.claim_id ? claims.find((c) => c.id === seg.claim_id) : undefined;
        if (!claim) return <span key={i}>{seg.text}</span>;
        if (!interactive) return <Fact key={i} claim={claim} />;
        return (
          <button
            key={i}
            type="button"
            className={styles.valueButton}
            aria-pressed={claim.id === selectedId}
            aria-label={`${claim.label}: ${claim.display}`}
            onClick={() => onSelect?.(claim.id)}
          >
            <Fact claim={claim} />
          </button>
        );
      })}
    </>
  );
}
