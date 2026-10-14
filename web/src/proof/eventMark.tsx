// Shapes for event types on the evidence pitch, in the legend and in the list. The shape (and the type
// label next to it) carries the meaning; colour only dims or highlights. Own drawings, unit coordinates.
import type { ReactNode } from "react";

import styles from "./proof.module.css";

type Shape = "dot" | "triangle" | "ring" | "cross" | "card" | "diamond" | "square" | "x";

export const EVENT_SHAPES: Record<string, Shape> = {
  goal: "dot",
  shot: "triangle",
  pass: "ring",
  dribble: "cross",
  red_card: "card",
  yellow_card: "card",
  penalty: "diamond",
  corner: "square",
  save: "ring",
  foul: "x",
  offside: "x",
  substitution: "x",
  kickoff: "x",
  half_time: "x",
  full_time: "x",
};

/** Readable name of an event type ("red_card" → "Red card"). */
export function eventLabel(type: string): string {
  const words = type.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function shapeOf(type: string): Shape {
  return EVENT_SHAPES[type] ?? "x";
}

function Shape({ shape }: { shape: Shape }): ReactNode {
  switch (shape) {
    case "dot":
      return <circle r="1" />;
    case "triangle":
      return <path d="M0 -1.15 1.05 0.85H-1.05Z" />;
    case "ring":
      return <circle r="0.8" fill="none" strokeWidth="0.4" />;
    case "cross":
      return <path d="M-1 0H1M0 -1V1" fill="none" strokeWidth="0.45" />;
    case "card":
      return <rect x="-0.6" y="-1" width="1.2" height="2" />;
    case "diamond":
      return <path d="M0 -1.2 1.2 0 0 1.2 -1.2 0Z" />;
    case "square":
      return <rect x="-0.9" y="-0.9" width="1.8" height="1.8" />;
    default:
      return <path d="M-0.9 -0.9 0.9 0.9M-0.9 0.9 0.9 -0.9" fill="none" strokeWidth="0.45" />;
  }
}

/** A mark inside the pitch SVG (pitch units), centred on (cx, cy). */
export function EventMark(props: {
  type: string;
  cx: number;
  cy: number;
  scale: number;
  state: "selected" | "marked" | "dim";
  onSelect?: () => void;
}) {
  const { type, cx, cy, scale, state, onSelect } = props;
  return (
    <g
      className={styles.mark}
      data-state={state}
      data-shape={shapeOf(type)}
      data-type={type}
      transform={`translate(${cx} ${cy}) scale(${scale})`}
      onClick={onSelect}
    >
      {state === "selected" ? <circle r="1.9" className={styles.markHalo} fill="none" /> : null}
      <Shape shape={shapeOf(type)} />
    </g>
  );
}

/** The same shape as an inline glyph (list rows, legend). */
export function EventGlyph({ type }: { type: string }) {
  return (
    <svg className={styles.eventGlyph} viewBox="-1.6 -1.6 3.2 3.2" aria-hidden="true" data-shape={shapeOf(type)}>
      <Shape shape={shapeOf(type)} />
    </svg>
  );
}
