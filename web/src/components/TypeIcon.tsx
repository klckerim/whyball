import type { ReactElement } from "react";

import { typeLabel } from "../timeline";

/** One shape per moment type, so the type reads without colour: the badge, the timeline marker and
 * the legend all use it. Colour comes from `currentColor` (the `--type` token of the parent). */
const SHAPES: Record<string, ReactElement> = {
  goal: <circle cx="6" cy="6" r="5" />,
  red_card: <rect x="2.5" y="0.75" width="7" height="10.5" rx="1.2" />,
  penalty: <path d="M6 0.5 11.5 6 6 11.5 0.5 6Z" />,
  pressure_shift: <path d="M6 0.75 11.5 11 0.5 11Z" />,
  dominance_without_reward: <path d="M3.25 1 8.75 1 11.5 6 8.75 11 3.25 11 0.5 6Z" />,
};

export function TypeIcon({ type, size = 12 }: { type: string; size?: number }) {
  return (
    <svg className="type-icon" width={size} height={size} viewBox="0 0 12 12" aria-hidden="true" focusable="false">
      <g fill="currentColor">{SHAPES[type] ?? <circle cx="6" cy="6" r="4.5" fillOpacity="0" stroke="currentColor" strokeWidth="1.5" />}</g>
    </svg>
  );
}

export function TypeBadge({ type }: { type: string }) {
  return (
    <span className={`badge type type-${type}`}>
      <TypeIcon type={type} size={10} />
      {typeLabel(type)}
    </span>
  );
}
