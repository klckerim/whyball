import { eventLabel, typeLabel } from "../timeline";
import type { Moment, Teams } from "../types";
import { SourceBadge } from "./SourceBadge";

interface Props {
  moment: Moment;
  teams: Teams;
  selected: boolean;
  fresh: boolean;
  onSelect: (id: string) => void;
  onTrace: (id: string) => void;
}

export function MomentCard({ moment, teams, selected, fresh, onSelect, onTrace }: Props) {
  const team = moment.team ? teams[moment.team] : null;
  return (
    <article
      className={`card${selected ? " selected" : ""}${fresh ? " fresh" : ""}`}
      aria-labelledby={`${moment.id}-title`}
      onClick={() => onSelect(moment.id)}
    >
      <header className="card-head">
        <span className="minute">{moment.minute_label}</span>
        <span className={`badge type type-${moment.type}`}>{typeLabel(moment.type)}</span>
        {team && <span className="team">{team}</span>}
        <button
          type="button"
          className="link"
          id={`${moment.id}-title`}
          aria-pressed={selected}
          onClick={(e) => {
            e.stopPropagation();
            onTrace(moment.id);
          }}
        >
          Trace
        </button>
      </header>
      <p className="text">{moment.text}</p>
      <footer className="card-foot">
        <SourceBadge source={moment.source} />
        <span className="muted small">{moment.prompt_version}</span>
      </footer>
      <details className="claims" onClick={(e) => e.stopPropagation()}>
        <summary>Verified claims ({moment.claims.length})</summary>
        <ul>
          {moment.claims.map((c) => (
            <li key={c.id}>
              <div className="claim">
                <span className="claim-label">
                  {c.label}
                  {c.team && <span className="muted"> · {teams[c.team]}</span>}
                  {c.player && <span className="muted"> · {c.player}</span>}
                </span>
                <strong className="claim-value">{c.display}</strong>
                <span className="muted small">
                  {c.start === c.end ? `at ${c.end}` : `${c.start} → ${c.end}`}
                </span>
              </div>
              {c.evidence.length > 0 && (
                <ul className="evidence" aria-label={`Evidence for ${c.label}`}>
                  <li className="ev-kind">{c.kind === "count" ? "Counted events" : "Measured as of"}</li>
                  {c.evidence.map((e) => (
                    <li key={e.id}>
                      <span className="ev-minute">{e.minute_label}</span> {eventLabel(e.type)}
                      {e.player && <> · {e.player}</>}
                      {e.team && <span className="muted"> ({teams[e.team]})</span>}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </details>
    </article>
  );
}
