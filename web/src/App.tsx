import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchMatch, fetchMatches, fetchMoments } from "./api";
import { defaultClaim } from "./claimText";
import { EvidencePanel } from "./components/EvidencePanel";
import { MomentCard } from "./components/MomentCard";
import { Scoreboard } from "./components/Scoreboard";
import { SidePanel, type Tab } from "./components/SidePanel";
import { TimelineBar } from "./components/TimelineBar";
import { TracePanel } from "./components/TracePanel";
import { applyTheme, storedTheme, systemTheme, type Theme } from "./theme";
import { isFeatured, runMeta, scoreAt, scoreboardClock, typeLabel, visibleMoments } from "./timeline";
import type { MatchDetail, MatchSummary, Moment } from "./types";
import { useReplay } from "./useReplay";

// K toggles playback anywhere but text fields; Space too, unless a focused control uses it.
const TYPING = 'input:not([type="checkbox"]):not([type="radio"]):not([type="range"]), select, textarea, [contenteditable]';
const OWN_SPACE = 'input, select, textarea, button, a, summary, [role="tab"], [tabindex], [contenteditable]';

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

export function App() {
  const [matches, setMatches] = useState<MatchSummary[]>([]);
  const [matchId, setMatchId] = useState<string | null>(null);
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [moments, setMoments] = useState<Moment[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [claimId, setClaimId] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ moment: string; claim: string } | null>(null);
  const [eventId, setEventId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("evidence");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);
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
  const listed = useMemo(() => (showAll ? moments : moments.filter(isFeatured)), [moments, showAll]);
  const shown = useMemo(() => visibleMoments(listed, replay.t), [listed, replay.t]);

  const select = useCallback(
    (id: string, claim?: string) => {
      const m = moments.find((x) => x.id === id);
      setSelected(id);
      setClaimId(claim ?? (m ? defaultClaim(m)?.id ?? null : null));
      setEventId(null);
    },
    [moments],
  );

  // A shown card is always selected: the first one when the current one is not on screen (none
  // before the first card of a replay).
  useEffect(() => {
    if (shown.some((m) => m.id === selected)) return;
    if (shown[0]) select(shown[0].id);
    else if (selected) setSelected(null);
  }, [shown, selected, select]);

  // A card that arrives from the stream becomes the selected one.
  useEffect(() => {
    if (replay.arrived && listed.some((m) => m.id === replay.arrived)) select(replay.arrived);
  }, [replay.arrived, listed, select]);

  const { playing, play, pause } = replay;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const space = e.key === " ";
      if (!space && e.key.toLowerCase() !== "k") return;
      const target = e.target instanceof Element ? e.target : null;
      if (e.ctrlKey || e.metaKey || e.altKey || target?.closest(space ? OWN_SPACE : TYPING)) return;
      e.preventDefault();
      if (playing) pause();
      else play();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [playing, play, pause]);

  const selectClaim = (momentId: string, claim: string) => {
    if (momentId !== selected) select(momentId, claim);
    else {
      setClaimId(claim);
      setEventId(null);
    }
    setTab("evidence");
    setSheetOpen(true);
  };

  const onMarker = (m: Moment) => {
    if (m.t > replay.t) replay.seek(m.t);
    select(m.id);
    requestAnimationFrame(() =>
      document.getElementById(`card-${m.id}`)?.scrollIntoView({ block: "nearest", behavior: reducedMotion() ? "auto" : "smooth" }),
    );
  };

  // What the panel shows: a hovered value previews its claim; otherwise the selection.
  const panelMoment = moments.find((m) => m.id === (preview?.moment ?? selected)) ?? null;
  const panelClaim =
    panelMoment?.claims.find((c) => c.id === (preview ? preview.claim : claimId)) ?? (panelMoment ? defaultClaim(panelMoment) : null);
  const panelEvent =
    panelClaim?.evidence.find((e) => e.id === eventId)?.id ??
    panelClaim?.evidence.find((e) => e.x != null && e.y != null)?.id ??
    panelClaim?.evidence[0]?.id ??
    null;

  const run = detail ? runMeta(detail.prompt_version, detail.run_id) : null;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand-block">
          <h1 className="brand">
            WhyBall <span className="note">Synthetic data</span>
          </h1>
          <p className="tagline">Every sentence verified against the match data</p>
        </div>
        <div className="top-actions">
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
            className="btn icon"
            onClick={() => setChosen(theme === "dark" ? "light" : "dark")}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          >
            <span aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>
          </button>
        </div>
      </header>

      {error && (
        <p className="error" role="alert">
          Could not load data: {error}
        </p>
      )}

      {detail && (
        <>
          <Scoreboard
            teams={detail.teams}
            score={scoreAt(replay.t, detail.timeline)}
            minute={scoreboardClock(replay.t, duration, detail.periods)}
          />
          <TimelineBar
            t={replay.t}
            duration={duration}
            periods={detail.periods}
            moments={listed}
            playing={replay.playing}
            speed={speed}
            selectedId={selected}
            onPlay={replay.play}
            onPause={replay.pause}
            onRestart={() => {
              setSheetOpen(false); // the open sheet would cover the timeline on a phone
              replay.restart();
            }}
            onSeek={replay.seek}
            onSpeed={setSpeed}
            onMarker={onMarker}
          />
          <main className="layout">
            <section className="feed" aria-labelledby="feed-title">
              <div className="feed-head">
                <h2 id="feed-title" className="feed-title">
                  {showAll ? "All moments" : "Key moments"}{" "}
                  <span className="count">
                    {shown.length} of {listed.length}
                  </span>
                </h2>
                <label className="switch">
                  <input type="checkbox" role="switch" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
                  <span className="track-ui" aria-hidden="true" />
                  All moments
                </label>
              </div>
              {shown.length === 0 && <p className="muted small hint">Cards appear here as the match unfolds.</p>}
              {shown.map((m) => (
                <MomentCard
                  key={m.id}
                  moment={m}
                  teams={detail.teams}
                  selected={m.id === selected}
                  activeClaim={m.id === selected ? claimId : null}
                  fresh={m.id === replay.arrived}
                  onSelect={(id) => select(id)}
                  onSelectClaim={selectClaim}
                  onPreviewClaim={(moment, claim) => setPreview(claim ? { moment, claim } : null)}
                />
              ))}
            </section>
            <SidePanel
              tab={tab}
              onTab={setTab}
              open={sheetOpen}
              onOpen={setSheetOpen}
              peek={
                panelMoment ? (
                  <>
                    <strong>{panelMoment.minute_label}</strong> {typeLabel(panelMoment.type)}
                    {panelClaim && <span className="muted"> · {panelClaim.display} {panelClaim.label}</span>}
                  </>
                ) : (
                  "Evidence"
                )
              }
              evidence={
                panelMoment ? (
                  <EvidencePanel
                    moment={panelMoment}
                    claim={panelClaim}
                    eventId={panelEvent}
                    teams={detail.teams}
                    onSelectClaim={(c) => selectClaim(panelMoment.id, c)}
                    onSelectEvent={setEventId}
                  />
                ) : (
                  <p className="muted small">Select a card to see the events behind its numbers.</p>
                )
              }
              trace={<TracePanel moment={panelMoment} />}
            />
          </main>
          <footer className="foot">
            <span>Synthetic, seeded matches · no real clubs or players</span>
            {run && (
              <span title={run.full}>
                {" · "}
                {run.short}
              </span>
            )}
          </footer>
        </>
      )}
    </div>
  );
}
