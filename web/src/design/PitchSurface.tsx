// The pitch drawing shared by the stage and the evidence view: our own abstract markings in the event
// coordinate system (105×68; approximate, not a regulation plan). Children are drawn in those units.
import type { ReactNode } from "react";

export const PITCH = { w: 105, h: 68 } as const;

/** Event coordinates → SVG: y flipped so y=0 is the bottom touchline. */
export function toSvg(p: { x: number; y: number }): { cx: number; cy: number } {
  return { cx: p.x, cy: PITCH.h - p.y };
}

interface Props {
  label: string;
  svgClassName?: string;
  linesClassName?: string;
  children?: ReactNode;
}

export function PitchSurface({ label, svgClassName, linesClassName, children }: Props) {
  return (
    <svg
      className={svgClassName}
      viewBox={`0 0 ${PITCH.w} ${PITCH.h}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={label}
    >
      <g className={linesClassName}>
        <rect x="0" y="0" width={PITCH.w} height={PITCH.h} />
        <line x1={PITCH.w / 2} y1="0" x2={PITCH.w / 2} y2={PITCH.h} />
        <circle cx={PITCH.w / 2} cy={PITCH.h / 2} r="9" />
        <rect x="0" y="14" width="16" height="40" />
        <rect x={PITCH.w - 16} y="14" width="16" height="40" />
        <rect x="0" y="25" width="5" height="18" />
        <rect x={PITCH.w - 5} y="25" width="5" height="18" />
      </g>
      {children}
    </svg>
  );
}
