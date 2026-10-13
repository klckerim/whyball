import type { MouseEvent } from "react";

import { markClaims } from "../claimText";
import { runMeta } from "../timeline";
import type { Moment, Teams } from "../types";
import { SourceBadge } from "./SourceBadge";
import { TypeBadge } from "./TypeIcon";

interface Props {
  moment: Moment;
  teams: Teams;
  selected: boolean;
  activeClaim: string | null;
  fresh: boolean;
  onSelect: (id: string) => void;
  onSelectClaim: (momentId: string, claimId: string) => void;
  onPreviewClaim: (momentId: string, claimId: string | null) => void;
}

export function CheckIcon() {
  return (
    <svg className="check" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" focusable="false">
      <circle cx="7" cy="7" r="7" fill="currentColor" />
      <path d="M3.8 7.2 6 9.3l4.3-4.6" fill="none" stroke="var(--surface)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function MomentCard({ moment, teams, selected, activeClaim, fresh, onSelect, onSelectClaim, onPreviewClaim }: Props) {
  const team = moment.team ? teams[moment.team] : null;
  const meta = runMeta(moment.prompt_version, moment.run_id);
  const n = moment.claims.length;
  const claimProps = (claimId: string) => ({
    "aria-pressed": selected && activeClaim === claimId,
    onClick: (e: MouseEvent) => {
      e.stopPropagation();
      onSelectClaim(moment.id, claimId);
    },
    onMouseEnter: () => onPreviewClaim(moment.id, claimId),
    onMouseLeave: () => onPreviewClaim(moment.id, null),
    onFocus: () => onPreviewClaim(moment.id, claimId),
    onBlur: () => onPreviewClaim(moment.id, null),
  });

  return (
    <article
      id={`card-${moment.id}`}
      className={`card type-${moment.type}${selected ? " selected" : ""}${fresh ? " fresh" : ""}`}
      aria-labelledby={`${moment.id}-title`}
      aria-current={selected ? "true" : undefined}
      tabIndex={0}
      onClick={() => onSelect(moment.id)}
      onKeyDown={(e) => {
        if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          onSelect(moment.id);
        }
      }}
    >
      <header className="card-head" id={`${moment.id}-title`}>
        <span className="minute">{moment.minute_label}</span>
        <TypeBadge type={moment.type} />
        {team && <span className="team">{team}</span>}
      </header>
      <p className="text">
        {markClaims(moment.text, moment.claims).map((s, i) =>
          s.claimId ? (
            <button key={i} type="button" className="val" title="Verified value: show its evidence" {...claimProps(s.claimId)}>
              {s.text}
            </button>
          ) : (
            <span key={i}>{s.text}</span>
          ),
        )}
      </p>
      <details className="claims" onClick={(e) => e.stopPropagation()}>
        <summary>
          <CheckIcon />
          <span className="claims-title">Verified claims ({n})</span>
          <span className="checks">
            {n} {n === 1 ? "check" : "checks"} passed
          </span>
        </summary>
        <ul>
          {moment.claims.map((c) => (
            <li key={c.id}>
              <button type="button" className="claim-row" {...claimProps(c.id)}>
                <span className="claim-label">
                  {c.label}
                  {c.team && <span className="muted"> · {teams[c.team]}</span>}
                  {c.player && <span className="muted"> · {c.player}</span>}
                </span>
                <strong className="claim-value">{c.display}</strong>
              </button>
            </li>
          ))}
        </ul>
      </details>
      <footer className="card-foot">
        <SourceBadge source={moment.source} />
        <span className="run-meta" title={meta.full}>
          {meta.short}
        </span>
      </footer>
    </article>
  );
}
