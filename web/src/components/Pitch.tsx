import { PITCH, spreadOverlaps, toPitch, VIEWBOX } from "../pitch";
import { eventLabel } from "../timeline";
import type { EvidenceEvent, Teams } from "../types";

const { w, h, pad } = PITCH;
const BOX = { depth: 16.5, width: 40.32 };
const SIX = { depth: 5.5, width: 18.32 };
const GOAL = 7.32;

function Ends() {
  const end = (x0: number, dir: 1 | -1) => {
    const x = (d: number) => (dir === 1 ? x0 : x0 - d);
    return (
      <>
        <rect x={x(BOX.depth)} y={pad + (h - BOX.width) / 2} width={BOX.depth} height={BOX.width} />
        <rect x={x(SIX.depth)} y={pad + (h - SIX.width) / 2} width={SIX.depth} height={SIX.width} />
        <rect x={dir === 1 ? x0 - 1.5 : x0} y={pad + (h - GOAL) / 2} width={1.5} height={GOAL} />
        <circle cx={x0 + dir * 11} cy={pad + h / 2} r={0.35} className="spot" />
      </>
    );
  };
  return (
    <>
      {end(pad, 1)}
      {end(pad + w, -1)}
    </>
  );
}

interface Props {
  events: EvidenceEvent[];
  teams: Teams;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/** The evidence events of one claim on a 105×68 pitch; the selected event is ringed. */
export function Pitch({ events, teams, selectedId, onSelect }: Props) {
  const points = spreadOverlaps(
    events.flatMap((e) => {
      const p = toPitch(e.x, e.y);
      return p ? [{ id: e.id, ...p, e }] : [];
    }),
  );
  const selected = points.find((p) => p.id === selectedId);
  return (
    <figure className="pitch">
      <svg viewBox={VIEWBOX} role="img" aria-label={`${points.length} of ${events.length} evidence events on the pitch`}>
        <g className="lines">
          <rect x={pad} y={pad} width={w} height={h} />
          <line x1={pad + w / 2} y1={pad} x2={pad + w / 2} y2={pad + h} />
          <circle cx={pad + w / 2} cy={pad + h / 2} r={9.15} />
          <circle cx={pad + w / 2} cy={pad + h / 2} r={0.35} className="spot" />
          <Ends />
        </g>
        {points.map((p) => (
          <circle
            key={p.id}
            className={`dot dot-${p.e.team ?? "none"}${p.id === selectedId ? " selected" : ""}`}
            cx={p.cx}
            cy={p.cy}
            r={p.id === selectedId ? 2.1 : 1.5}
            onClick={() => onSelect(p.id)}
          >
            <title>
              {`${p.e.minute_label} ${eventLabel(p.e.type)}${p.e.player ? ` · ${p.e.player}` : ""}`}
            </title>
          </circle>
        ))}
        {selected && <circle className="ring" cx={selected.cx} cy={selected.cy} r={3.6} />}
      </svg>
      <figcaption>
        <span className="attack">
          {teams.home} attack <span aria-hidden="true">→</span>
          <span className="visually-hidden">towards the right</span>
        </span>
        <span className="attack">
          <span aria-hidden="true">←</span>
          <span className="visually-hidden">towards the left:</span> {teams.away}
        </span>
      </figcaption>
    </figure>
  );
}
