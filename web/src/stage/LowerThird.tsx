// Lower third: type glyph and label, minute, seal and source badge, and the narration. The stored card
// has no sentence or value spans, so the text is drawn as one plain block tied to its card id; values
// inside it are not wrapped in <Fact> (U2 open item).
import type { Moment } from "../api/types";
import { eventId, Fact } from "../design/Fact";
import { Seal } from "../design/Seal";
import { SourceBadge } from "../design/SourceBadge";
import { TypeGlyph, typeLabel } from "../design/TypeGlyph";
import styles from "./stage.module.css";

interface Props {
  moment: Moment;
  eventMatchId: string;
  placement: "stage" | "panel";
}

export function LowerThird({ moment, eventMatchId, placement }: Props) {
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
          <Seal checks={moment.checks} />
          <SourceBadge source={moment.source} />
        </span>
      </header>
      <p className={styles.ltText} data-card-id={moment.id}>
        {moment.text}
      </p>
    </section>
  );
}
