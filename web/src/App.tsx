import { useEffect, useMemo, useState } from "react";

import { fetchMatch, fetchMatches, fetchMoments } from "./api";
import { MomentCard } from "./components/MomentCard";
import { Scoreboard } from "./components/Scoreboard";
import { TimelineBar } from "./components/TimelineBar";
import { TracePanel } from "./components/TracePanel";
import { applyTheme, storedTheme, systemTheme, type Theme } from "./theme";
import { clockLabel, scoreAt, visibleMoments } from "./timeline";
import type { MatchDetail, MatchSummary, Moment } from "./types";
import { useReplay } from "./useReplay";

export function App() {
  const [matches, setMatches] = useState<MatchSummary[]>([]);
  const [matchId, setMatchId] = useState<string | null>(null);
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [moments, setMoments] = useState<Moment[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [speed, setSpeed] = useState(60);
  const [error, setError] = useState<string | null>(null);
  const [chosen, setChosen] = useState<Theme | null>(storedTheme);
  const theme = chosen ?? systemTheme();

  useEffect(() => applyTheme(chosen), [chosen]);

  useEffect(() => {
    fetchMatches()
      .then((list) => {
        setMatches(list);
        setMatchId((id) => id ?? list[0]?.id ?? null);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!matchId) return;
    let live = true;
    setDetail(null);
    setSelected(null);
    Promise.all([fetchMatch(matchId), fetchMoments(matchId)])
      .then(([d, m]) => {
        if (!live) return;
        setDetail(d);
        setMoments(m);
      })
      .catch((e: Error) => setError(e.message));
    return () => {
      live = false;
    };
  }, [matchId]);

  const duration = detail?.duration_t ?? 0;
  const replay = useReplay(matchId, speed, duration);
  const shown = useMemo(() => visibleMoments(moments, replay.t), [moments, replay.t]);
  const selectedMoment = moments.find((m) => m.id === selected) ?? null;

  // "Trace" selects the card; on a narrow screen the panel sits below the feed, so scroll to it.
  const showTrace = (id: string) => {
    setSelected(id);
    if (window.matchMedia?.("(max-width: 760px)").matches) {
      requestAnimationFrame(() => document.getElementById("trace-title")?.scrollIntoView({ behavior: "smooth" }));
    }
  };

  // A card that arrives from the stream becomes the selected one.
  useEffect(() => {
    if (replay.arrived) setSelected(replay.arrived);
  }, [replay.arrived]);

  return (
    <div className="app">
      <header className="topbar">
        <h1 className="brand">WhyBall</h1>
        <label className="picker">
          <span className="visually-hidden">Match</span>
          <select value={matchId ?? ""} onChange={(e) => setMatchId(e.target.value)} disabled={!matches.length}>
            {matches.map((m) => (
              <option key={m.id} value={m.id}>
                {m.teams.home} – {m.teams.away}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="theme-toggle"
          onClick={() => setChosen(theme === "dark" ? "light" : "dark")}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </header>

      {error && <p className="error" role="alert">Could not load data: {error}</p>}

      {detail && (
        <>
          <Scoreboard
            teams={detail.teams}
            score={scoreAt(replay.t, detail.timeline)}
            minute={clockLabel(replay.t, detail.periods)}
          />
          <TimelineBar
            t={replay.t}
            duration={duration}
            periods={detail.periods}
            moments={moments}
            playing={replay.playing}
            speed={speed}
            onPlay={replay.play}
            onPause={replay.pause}
            onSeek={replay.seek}
            onSpeed={setSpeed}
          />
          <main className="layout">
            <section className="feed" aria-label="Moments">
              {shown.length === 0 ? (
                <div className="panel empty">
                  <p>No moments yet</p>
                  <p className="muted small">Press play or drag the timeline.</p>
                </div>
              ) : (
                shown.map((m) => (
                  <MomentCard
                    key={m.id}
                    moment={m}
                    teams={detail.teams}
                    selected={m.id === selected}
                    fresh={m.id === replay.arrived}
                    onSelect={setSelected}
                    onTrace={showTrace}
                  />
                ))
              )}
            </section>
            <TracePanel moment={selectedMoment} />
          </main>
          <footer className="muted small foot">
            Every number in a card is checked against deterministic match metrics. Run{" "}
            <span className="mono">{detail.run_id}</span>.
          </footer>
        </>
      )}
    </div>
  );
}
