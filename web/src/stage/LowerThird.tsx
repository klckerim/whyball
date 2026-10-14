// Lower third: type glyph and label, minute, seal and source badge, and the narration. The sentence is
// drawn from the card's segments: claim values are <Fact>s, everything else is plain text.
import type { Moment } from "../api/types";
import { eventId, Fact } from "../design/Fact";
import { SentenceText } from "../design/SentenceText";
import { SourceBadge } from "../design/SourceBadge";
import { TypeGlyph, typeLabel } from "../design/TypeGlyph";
import { ProofSeal } from "./ProofSeal";
import styles from "./stage.module.css";

interface Props {
  moment: Moment;
  eventMatchId: string;
  placement: "stage" | "panel";
  onProof?: () => void;
}

export function LowerThird({ moment, eventMatchId, placement, onProof }: Props) {
  return (
    <section className={styles.lowerThird} data-placement={placement} aria-label="Narration" aria-live="polite">
      <header className={styles.ltHead}>
        <span className={styles.ltType}>
          <TypeGlyph type={moment.type} />
          <span>{typeLabel(moment.type)}</span>
          <Fact
            className={styles.ltMinute}
            event={{ id: eventId(eventMatchId, moment.at_seq), minute_label: moment.minute_label }}
            field="minute_label"
          />
        </span>
        <span className={styles.ltMeta}>
          <ProofSeal checks={moment.checks} onProof={onProof} />
          <SourceBadge source={moment.source} />
        </span>
      </header>
      <p className={styles.ltText} data-card-id={moment.id}>
        <SentenceText segments={moment.segments} claims={moment.claims} />
      </p>
    </section>
  );
}
