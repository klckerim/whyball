import { SOURCE_META } from "../timeline";
import type { Source } from "../types";

export function SourceBadge({ source }: { source: Source }) {
  const meta = SOURCE_META[source];
  return (
    <span className={`badge source source-${source}`} title={meta.title} data-source={source}>
      <span aria-hidden="true">{meta.glyph}</span> {meta.label}
    </span>
  );
}
