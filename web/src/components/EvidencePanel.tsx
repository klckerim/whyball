import { eventLabel, typeLabel } from "../timeline";
import type { Claim, Moment, Teams } from "../types";
import { Crest } from "./Scoreboard";
import { Pitch } from "./Pitch";

interface Props {
  moment: Moment;
  claim: Claim | null;
  eventId: string | null;
  teams: Teams;
  onSelectClaim: (claimId: string) => void;
  onSelectEvent: (eventId: string) => void;
}

/** Evidence of the selected claim: the claims of the card as chips, the events behind the chosen one
 * (minute, type, player) and where they happened. */
export function EvidencePanel({ moment, claim, eventId, teams, onSelectClaim, onSelectEvent }: Props) {
  return (
    <div className="evidence-panel">
      <p className="ev-moment">
        <span className="minute">{moment.minute_label}</span> {typeLabel(moment.type)}
        {moment.team && <span className="muted"> · {teams[moment.team]}</span>}
      </p>
      <div className="chips" role="group" aria-label="Claims in this card">
        {moment.claims.map((c) => (
          <button
            key={c.id}
            type="button"
            className="chip"
            aria-pressed={c.id === claim?.id}
            onClick={() => onSelectClaim(c.id)}
            title={c.label}
          >
            <strong>{c.display}</strong> <span className="chip-label">{c.label}</span>
          </button>
        ))}
      </div>

      {claim && (
        <section className="claim-detail" aria-label={`Evidence for ${claim.label}`}>
          <h3 className="claim-title">
            <strong className="claim-value">{claim.display}</strong> {claim.label}
            {claim.team && <span className="muted"> · {teams[claim.team]}</span>}
            {claim.player && <span className="muted"> · {claim.player}</span>}
          </h3>
          <p className="muted small">
            {claim.kind === "count" ? "Counted events" : "Measured as of"} ·{" "}
            {claim.start === claim.end ? `at ${claim.end}` : `${claim.start} → ${claim.end}`}
          </p>
          {claim.evidence.length === 0 ? (
            <p className="muted small">
              No events: the value counts none in this window.
            </p>
          ) : (
            <>
              {claim.evidence.some((e) => e.x != null && e.y != null) ? (
                <Pitch events={claim.evidence} teams={teams} selectedId={eventId} onSelect={onSelectEvent} />
              ) : (
                <p className="muted small">These events have no pitch position.</p>
              )}
              <ol className="ev-list" aria-label={`Events for ${claim.label}`}>
                {claim.evidence.map((e) => (
                  <li key={e.id}>
                    <button type="button" className="ev-row" aria-pressed={e.id === eventId} onClick={() => onSelectEvent(e.id)}>
                      {e.team ? <Crest side={e.team} name={teams[e.team]} size="sm" /> : <span className="crest crest-sm" />}
                      <span className="ev-minute">{e.minute_label}</span>
                      <span className="ev-type">{eventLabel(e.type)}</span>
                      <span className="ev-player">{e.player ?? (e.team ? teams[e.team] : "")}</span>
                      {(e.x == null || e.y == null) && <span className="ev-noloc">no location</span>}
                    </button>
                  </li>
                ))}
              </ol>
            </>
          )}
        </section>
      )}
    </div>
  );
}
