// The only way a number, name or match time reaches the screen (UI_SPEC §7, T1/T2): every value is
// tied to the claim or event it comes from, through data-claim-id / data-event-id.
import type { Claim, Evidence } from "../api/types";

/** Shown instead of a missing value; never 0 or an empty mark (UI_SPEC T4). */
export const NO_DATA = "no data";

export type EventField = "minute_label" | "player" | "team" | "score_home" | "score_away";

/** A match event as Fact needs it: evidence events carry `id`; build one for timeline events with `eventId`. */
export type FactEvent = Pick<Evidence, "id"> &
  Partial<Pick<Evidence, "minute_label" | "player" | "team">> & { score?: { home: number; away: number } };

function fieldValue(event: FactEvent, field: EventField): string | null {
  if (field === "score_home" || field === "score_away") {
    const n = event.score?.[field === "score_home" ? "home" : "away"];
    return n === undefined ? null : String(n);
  }
  return event[field] ?? null;
}

type Props = { className?: string } & (
  | { claim: Pick<Claim, "id" | "display">; event?: never }
  | {
      event: FactEvent;
      field: EventField;
      /** Team names by side, for field="team" (the event holds "home" / "away"). */
      teams?: { home: string; away: string };
      missing?: string;
      claim?: never;
    }
);

/** Event id in the store's format ("<event_match_id>#<seq>"), for timeline events that carry only `seq`. */
export function eventId(eventMatchId: string, seq: number): string {
  return `${eventMatchId}#${seq}`;
}

export function Fact(props: Props) {
  if (props.claim) {
    return (
      <span className={props.className} data-claim-id={props.claim.id}>
        {props.claim.display}
      </span>
    );
  }
  const { event, field, teams, missing = NO_DATA, className } = props;
  const raw = fieldValue(event, field);
  const value = field === "team" && raw !== null ? (teams?.[raw as "home" | "away"] ?? null) : raw;
  return (
    <span className={className} data-event-id={event.id} data-missing={value === null ? "" : undefined}>
      {value ?? missing}
    </span>
  );
}
