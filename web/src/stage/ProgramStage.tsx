// The 16:9 program frame: 1920×1080 logical units that scale with the width (container query units),
// always dark (--stage-* tokens), content inside the graphics-safe area.
import type { ReactNode } from "react";

import { safeInset } from "../design/safeArea";
import styles from "./stage.module.css";

export function ProgramStage({ children, guides = false }: { children: ReactNode; guides?: boolean }) {
  return (
    <div className={styles.frame} data-testid="program">
      <div className={styles.safe} style={{ inset: safeInset("graphics") }} data-testid="graphics-safe">
        {children}
      </div>
      {guides ? (
        <div className={styles.guides} aria-hidden="true" data-testid="guides">
          <div className={styles.guide} data-kind="action" style={{ inset: safeInset("action") }}>
            <span>action-safe</span>
          </div>
          <div className={styles.guide} data-kind="graphics" style={{ inset: safeInset("graphics") }}>
            <span>graphics-safe</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
