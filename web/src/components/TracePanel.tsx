import type { Moment } from "../types";

/** Agent trace of the selected card: narrate → lint → verify → accept / fallback steps. The replayed
 * store carries no trace yet, so the panel shows its empty state. */
export function TracePanel({ moment }: { moment: Moment | null }) {
  return (
    <aside className="panel trace" aria-labelledby="trace-title">
      <h2 id="trace-title">Agent trace</h2>
      {moment && <p className="muted small mono">{moment.id}</p>}
      {!moment || moment.trace.length === 0 ? (
        <div className="empty">
          <p>No trace yet</p>
          <p className="muted small">
            {moment
              ? "This card was replayed from the publication store; live runs will record each pipeline step here."
              : "Select a card to see how it was narrated and verified."}
          </p>
        </div>
      ) : (
        <ol className="steps">
          {moment.trace.map((s, i) => (
            <li key={i} className={s.ok ? "ok" : "fail"}>
              <span className="mono">#{s.attempt}</span> <strong>{s.step}</strong>{" "}
              <span className="muted">{s.ok ? "ok" : "failed"}</span>
              {s.codes && s.codes.length > 0 && <span className="muted small"> · {s.codes.join(", ")}</span>}
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}
