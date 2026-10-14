// Top bar: wordmark, match picker, On Air | Proof, theme switch, SYNTHETIC DATA. No left menu (UI_SPEC §2).
import * as Tabs from "@radix-ui/react-tabs";
import { useState } from "react";
import { useMatch, useNavigate } from "react-router";

import type { MatchSummary } from "../api/types";
import { activeTheme, toggleTheme } from "../design/theme";
import styles from "./app.module.css";

export function TopBar({ matches }: { matches: MatchSummary[] | null }) {
  const route = useMatch("/match/:id");
  const navigate = useNavigate();
  const [theme, setTheme] = useState(activeTheme);
  const currentId = route?.params.id ?? matches?.[0]?.id ?? "";
  const known = matches?.some((m) => m.id === currentId);
  const hasMatches = !!matches?.length;
  return (
    <header className={styles.topBar}>
      <span className={styles.wordmark}>WhyBall</span>
      {matches && hasMatches ? (
        <label className={styles.picker}>
          <span className={styles.visuallyHidden}>Match</span>
          <select value={known ? currentId : ""} onChange={(e) => navigate(`/match/${encodeURIComponent(e.target.value)}`)}>
            {known ? null : <option value="">Choose a match</option>}
            {matches.map((m) => (
              <option key={m.id} value={m.id}>
                {m.teams.home} – {m.teams.away}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <Tabs.List className={styles.modes} aria-label="View">
        <Tabs.Trigger value="air" className={styles.mode}>
          On Air
        </Tabs.Trigger>
        <Tabs.Trigger value="proof" className={styles.mode}>
          Proof
        </Tabs.Trigger>
      </Tabs.List>
      <span className={styles.barEnd}>
        <span className={styles.synthetic}>SYNTHETIC DATA</span>
        <button
          type="button"
          className={styles.button}
          onClick={() => setTheme(toggleTheme())}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
        >
          {theme === "dark" ? (
            <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="3.2" fill="currentColor" /><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6 13 13M3 13l1.4-1.4M11.6 4.4 13 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>
          ) : (
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M13.5 10A6 6 0 0 1 6 2.5a6 6 0 1 0 7.5 7.5Z" fill="currentColor" /></svg>
          )}
        </button>
      </span>
    </header>
  );
}
