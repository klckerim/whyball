// Who wrote the published text, from the card's own `source` field. Text + border style carry the
// meaning (solid fill / outline / dashed outline); colour only repeats it.
import type { Source } from "../api/types";
import styles from "./primitives.module.css";

export const SOURCES: Record<Source, { label: string; title: string; style: "solid" | "outline" | "dashed" }> = {
  llm: { label: "LLM", title: "Model draft that passed lint and claim verification", style: "solid" },
  template: { label: "Template", title: "Template narration (moment not selected for the model)", style: "outline" },
  template_fallback: {
    label: "Template fallback",
    title: "The model draft failed the checks; the template narration was published instead",
    style: "dashed",
  },
};

export function SourceBadge({ source }: { source: Source }) {
  const s = SOURCES[source];
  return (
    <span className={styles.badge} data-source={source} data-style={s.style} title={s.title}>
      {s.label}
    </span>
  );
}
