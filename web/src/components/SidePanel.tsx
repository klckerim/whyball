import { useRef, type KeyboardEvent, type ReactNode } from "react";

export type Tab = "evidence" | "trace";

const TABS: { id: Tab; label: string }[] = [
  { id: "evidence", label: "Evidence" },
  { id: "trace", label: "Agent trace" },
];

interface Props {
  tab: Tab;
  onTab: (tab: Tab) => void;
  open: boolean; // bottom sheet state on narrow screens; the desktop panel is always open
  onOpen: (open: boolean) => void;
  peek: ReactNode;
  evidence: ReactNode;
  trace: ReactNode;
}

/** Right-hand panel with Evidence / Agent trace tabs; on a narrow screen a bottom sheet whose
 * collapsed row shows the selected claim. */
export function SidePanel({ tab, onTab, open, onOpen, peek, evidence, trace }: Props) {
  const refs = useRef<Record<Tab, HTMLButtonElement | null>>({ evidence: null, trace: null });
  const onKey = (e: KeyboardEvent) => {
    const i = TABS.findIndex((t) => t.id === tab);
    const next =
      e.key === "ArrowRight" ? TABS[(i + 1) % TABS.length] : e.key === "ArrowLeft" ? TABS[(i + TABS.length - 1) % TABS.length] : e.key === "Home" ? TABS[0] : e.key === "End" ? TABS[TABS.length - 1] : null;
    if (!next) return;
    e.preventDefault();
    onTab(next.id);
    refs.current[next.id]?.focus();
  };

  return (
    <aside className={`side${open ? " open" : ""}`} aria-label="Details">
      <button type="button" className="sheet-handle" aria-expanded={open} aria-controls="side-body" onClick={() => onOpen(!open)}>
        <span className="grip" aria-hidden="true" />
        <span className="peek">{peek}</span>
        <span className="chev" aria-hidden="true" />
        <span className="visually-hidden">{open ? "Hide details" : "Show details"}</span>
      </button>
      <div className="side-body" id="side-body">
        <div className="tabs" role="tablist" aria-label="Details" onKeyDown={onKey}>
          {TABS.map((t) => (
            <button
              key={t.id}
              ref={(el) => {
                refs.current[t.id] = el;
              }}
              type="button"
              role="tab"
              id={`tab-${t.id}`}
              aria-selected={tab === t.id}
              aria-controls={`panel-${t.id}`}
              tabIndex={tab === t.id ? 0 : -1}
              onClick={() => onTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div role="tabpanel" id="panel-evidence" aria-labelledby="tab-evidence" hidden={tab !== "evidence"} className="tabpanel">
          {evidence}
        </div>
        <div role="tabpanel" id="panel-trace" aria-labelledby="tab-trace" hidden={tab !== "trace"} className="tabpanel">
          {trace}
        </div>
      </div>
    </aside>
  );
}
