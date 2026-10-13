import type { Moment } from "../types";

/** Agent trace of the selected card: narrate → lint → verify → accept / fallback steps. The replayed
 * store carries no trace yet, so the tab shows its empty state. */
export function TracePanel({ moment }: { moment: Moment | null }) {
  if (!moment || moment.trace.length === 0) {
    return (
      <div className="empty">
        <p className="empty-title">No trace yet</p>
        <p className="muted small">
          {moment
            ? "This card was replayed from the publication store. Live runs record each step here: narrate, lint, verify, then accept or fall back to the template."
            : "Select a card to see how it was narrated and verified."}
        </p>
        {moment && <p className="muted small mono">{moment.id}</p>}
      </div>
    );
  }
  return (
    <ol className="steps">
      {moment.trace.map((s, i) => (
        <li key={i} className={s.ok ? "ok" : "fail"}>
          <span className="mono">#{s.attempt}</span> <strong>{s.step}</strong>{" "}
          <span className="status">{s.ok ? "ok" : "failed"}</span>
          {s.codes && s.codes.length > 0 && <span className="muted small"> · {s.codes.join(", ")}</span>}
        </li>
      ))}
    </ol>
  );
}
