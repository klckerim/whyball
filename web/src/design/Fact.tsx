// The only way a number, name or match time reaches the screen (UI_SPEC §7, T1/T2): every value is
// tied to the claim or event it comes from, through data-claim-id / data-event-id.
import type { Checks, Claim, Evidence, MetricInfo } from "../api/types";

/** Shown instead of a missing value; never 0 or an empty mark (UI_SPEC T4). */
export const NO_DATA = "no data";

export type EventField = "minute_label" | "player" | "team" | "outcome" | "score_home" | "score_away";
/** Other values of a claim than the one the sentence states: its window, subject and label. */
export type ClaimField = "start" | "end" | "player" | "team" | "label";
export type CheckField = keyof Checks;

/** A match event as Fact needs it: evidence events carry `id`; build one for timeline events with `eventId`. */
export type FactEvent = Pick<Evidence, "id"> &
  Partial<Pick<Evidence, "minute_label" | "player" | "team">> & {
    outcome?: string | null;
    score?: { home: number; away: number };
  };

function fieldValue(event: FactEvent, field: EventField): string | null {
  if (field === "score_home" || field === "score_away") {
    const n = event.score?.[field === "score_home" ? "home" : "away"];
    return n === undefined ? null : String(n);
  }
  return event[field] ?? null;
}

type Props = { className?: string } & (
  | { claim: Pick<Claim, "id" | "display">; field?: never; window?: never; event?: never; checks?: never }
  | {
      /** A field of the claim other than its value (data-claim-id stays the claim's). */
      claim: Pick<Claim, "id" | "start" | "end" | "player" | "team" | "label">;
      field: ClaimField;
      teams?: { home: string; away: string };
      missing?: string;
      window?: never;
      event?: never;
      checks?: never;
    }
  | {
      /** The rolling window length the claim's metric has in /api/metrics (the claim's own id marks the source). */
      claim: Pick<Claim, "id">;
      window: MetricInfo["window"];
      field?: never;
      event?: never;
      checks?: never;
    }
  | {
      /** A number of the card's recorded checks (data-card-id). */
      checks: Checks;
      cardId: string;
      field: CheckField;
      claim?: never;
      event?: never;
    }
  | {
      event: FactEvent;
      field: EventField;
      /** Team names by side, for field="team" (the event holds "home" / "away"). */
      teams?: { home: string; away: string };
      missing?: string;
      claim?: never;
      checks?: never;
    }
);

/** Event id in the store's format ("<event_match_id>#<seq>"), for timeline events that carry only `seq`. */
export function eventId(eventMatchId: string, seq: number): string {
  return `${eventMatchId}#${seq}`;
}

export function Fact(props: Props) {
  if (props.checks) {
    return (
      <span className={props.className} data-card-id={props.cardId} data-field={props.field}>
        {String(props.checks[props.field])}
      </span>
    );
  }
  if (props.claim) {
    const { claim, className } = props;
    if (props.window) {
      const n = props.window.minutes;
      return (
        <span className={className} data-claim-id={claim.id} data-field="window_minutes" data-missing={n == null ? "" : undefined}>
          {n == null ? NO_DATA : String(n)}
        </span>
      );
    }
    if (props.field) {
      const full = claim as Pick<Claim, "start" | "end" | "player" | "team" | "label">;
      const raw = full[props.field];
      const value = props.field === "team" && raw ? (props.teams?.[raw as "home" | "away"] ?? null) : (raw ?? null);
      return (
        <span className={className} data-claim-id={claim.id} data-field={props.field} data-missing={value === null ? "" : undefined}>
          {value ?? props.missing ?? NO_DATA}
        </span>
      );
    }
    return (
      <span className={className} data-claim-id={claim.id}>
        {(claim as Pick<Claim, "display">).display}
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
