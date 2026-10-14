// Moment type glyphs: our own SVG shapes, so meaning never rests on colour (UI_SPEC §6).
// Every type of app/analytics/moments.py MOMENT_TYPES has an entry (tests/test_web_contract.py).
import styles from "./primitives.module.css";

type Shape = "dot" | "card" | "diamond" | "triangle" | "square" | "neutral";

export const MOMENT_TYPES: Record<string, { label: string; shape: Shape }> = {
  goal: { label: "Goal", shape: "dot" },
  red_card: { label: "Red card", shape: "card" },
  penalty: { label: "Penalty", shape: "diamond" },
  pressure_shift: { label: "Pressure shift", shape: "triangle" },
  dominance_without_reward: { label: "Dominance without reward", shape: "square" },
};

/** Readable name of a moment type; an unknown type keeps its own words. */
export function typeLabel(type: string): string {
  return MOMENT_TYPES[type]?.label ?? type.replace(/_/g, " ");
}

const SHAPES: Record<Shape, React.ReactNode> = {
  dot: <circle cx="8" cy="8" r="6" />,
  card: <rect x="4" y="1.5" width="8" height="13" rx="1" />,
  diamond: <path d="M8 1 15 8 8 15 1 8Z" />,
  triangle: <path d="M8 1.5 15 14.5H1Z" />,
  square: <rect x="2" y="2" width="12" height="12" />,
  neutral: <circle cx="8" cy="8" r="5" fill="none" stroke="currentColor" strokeWidth="2" />,
};

export function TypeGlyph({ type, className }: { type: string; className?: string }) {
  const shape = MOMENT_TYPES[type]?.shape ?? "neutral";
  return (
    <svg
      className={[styles.glyph, className].filter(Boolean).join(" ")}
      viewBox="0 0 16 16"
      role="img"
      aria-label={typeLabel(type)}
      data-shape={shape}
      fill="currentColor"
    >
      {SHAPES[shape]}
    </svg>
  );
}
