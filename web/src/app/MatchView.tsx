// One match: loads detail, moments, events and the pressure series, then plays them on the stage.
// Opens paused on the deep-linked moment, else at `?t=`, else on the first model-written card (DESIGN D23).
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import { api, NotFoundError } from "../api/client";
import type { MatchDetail, Moment, Series, TimelineEvent } from "../api/types";
import { REDUCED_MOTION, useMediaQuery } from "../design/useMediaQuery";
import { SPEEDS } from "../state/clock";
import { eventAt, stepMoment } from "../state/match";
import { type Card, initialPlayback, usePlayback } from "../state/playback";
import { ProofView } from "../proof/ProofView";
import { OnAir } from "../stage/OnAir";
import styles from "./app.module.css";
import { HelpDialog } from "./HelpDialog";
import { shortcutFor } from "./keys";
import { type Mode, useFlip } from "./useFlip";
import { Empty, Failed, Loading, NotFound } from "./states";
import { Transport } from "./Transport";
import { useAsync } from "./useAsync";

export const SERIES_STEP = 60;

export interface MatchData {
  detail: MatchDetail;
  moments: Moment[];
  events: TimelineEvent[];
  series: Series;
}

export async function loadMatch(id: string): Promise<MatchData> {
  const [detail, moments, events, series] = await Promise.all([
    api.detail(id),
    api.moments(id),
    api.events(id),
    api.series(id, "pressure_balance", SERIES_STEP),
  ]);
  return { detail, moments, events, series };
}

export function MatchView({ id }: { id: string }) {
  const data = useAsync(() => loadMatch(id), id);
  if (data.status === "loading") return <Loading what="the match" />;
  if (data.status === "error") {
    return data.error instanceof NotFoundError ? (
      <NotFound what={`No match with the id "${id}" in the publication store.`} />
    ) : (
      <Failed what="the match" error={data.error} retry={data.retry} />
    );
  }
  return <MatchPlayer key={id} data={data.data} />;
}

/** Where to open: a valid `moment` param, else a valid `t`, else the first llm card. */
export function openAt(params: URLSearchParams, moments: Moment[], duration: number): { showId: string | null; t: number } {
  const moment = params.get("moment");
  if (moment && moments.some((m) => m.id === moment)) return { showId: moment, t: 0 };
  const t = Number(params.get("t"));
  if (params.has("t") && Number.isFinite(t) && t >= 0) return { showId: null, t: Math.min(t, duration) };
  return { showId: moments.find((m) => m.source === "llm")?.id ?? null, t: 0 };
}

function MatchPlayer({ data }: { data: MatchData }) {
  const { detail, moments, events, series } = data;
  const [params, setParams] = useSearchParams();
  const metrics = useAsync(api.metrics, "metrics");
  const cards: Card[] = useMemo(() => moments.map((m) => ({ id: m.id, t: m.t, text: m.text })), [moments]);
  const [state, dispatch] = usePlayback(cards, () => {
    const at = openAt(params, moments, detail.duration_t);
    return initialPlayback(detail.duration_t, SPEEDS[0].speed, at.t, at.showId, cards);
  });
  const [proofId, setProofId] = useState<string | null>(
    () => moments.find((m) => m.id === params.get("moment"))?.id ?? moments.find((m) => m.source === "llm")?.id ?? moments[0]?.id ?? null,
  );
  const selectProof = (id: string) => {
    setProofId(id);
    const next = new URLSearchParams(params);
    next.set("moment", id);
    setParams(next, { replace: true });
  };
  const [guides, setGuides] = useState(false);
  const [help, setHelp] = useState(false);
  const { t, playing, speed } = state.clock;
  const shownId = state.dwell.current?.id ?? null;
  const mode: Mode = params.get("mode") === "proof" ? "proof" : "air";
  const reduced = useMediaQuery(REDUCED_MOTION);
  const { shown: face, phase } = useFlip(mode, reduced);
  const noMoments = moments.length === 0;
  const prev = stepMoment(moments, t, shownId, -1);
  const next = stepMoment(moments, t, shownId, 1);

  // Flip (from the seal, P or the tabs): On Air's card opens in Proof; Proof's moment comes back on air.
  const lastMode = useRef(mode);
  useEffect(() => {
    if (lastMode.current === mode) return;
    lastMode.current = mode;
    if (mode === "proof") {
      dispatch({ type: "pause" });
      const at = shownId ?? [...moments].reverse().find((m) => m.t <= t)?.id ?? moments[0]?.id ?? null;
      if (at) selectProof(at);
    } else if (proofId) {
      dispatch({ type: "showMoment", id: proofId });
    }
  }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps -- runs on a mode change only

  const flip = () => {
    const next = new URLSearchParams(params);
    next.set("mode", mode === "proof" ? "air" : "proof");
    setParams(next, { replace: true });
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const s = shortcutFor(e.key, e.target, { ctrl: e.ctrlKey, meta: e.metaKey, alt: e.altKey });
      if (!s || help) return;
      e.preventDefault();
      if (s === "flip") flip();
      else if (mode === "proof") {
        if (s === "help") setHelp(true);
      } else if (s === "toggle") dispatch({ type: "toggle" });
      else if (s === "prev" && prev) dispatch({ type: "showMoment", id: prev.id });
      else if (s === "next" && next) dispatch({ type: "showMoment", id: next.id });
      else if (s === "guides") setGuides((g) => !g);
      else if (s === "help") setHelp(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dispatch, prev, next, help, mode, params]);

  return (
    <>
      <div className={styles.flip} data-phase={phase} role="tabpanel" aria-label={face === "air" ? "On Air" : "Proof"} data-face={face}>
        {face === "air" ? (
          <div className={styles.air}>
            <div className={styles.stageWrap}>
              <OnAir detail={detail} events={events} moments={moments} t={t} shownId={shownId} guides={guides} onProof={flip} />
            </div>
            {noMoments ? <Empty>No narrated moments in this match.</Empty> : null}
            <Transport
              t={t}
              duration={detail.duration_t}
              playing={playing}
              speed={speed}
              periods={detail.periods}
              moments={moments}
              series={series}
              minuteLabel={eventAt(events, t)?.minute_label ?? "no data"}
              shownId={shownId}
              canPrev={!!prev}
              canNext={!!next}
              onToggle={() => dispatch({ type: "toggle" })}
              onSpeed={(s) => dispatch({ type: "setSpeed", speed: s })}
              onPrev={() => prev && dispatch({ type: "showMoment", id: prev.id })}
              onNext={() => next && dispatch({ type: "showMoment", id: next.id })}
              onSeek={(to) => dispatch({ type: "seek", t: to })}
              onMoment={(mid) => dispatch({ type: "showMoment", id: mid })}
            />
          </div>
        ) : (
          <div className={styles.proof}>
            <ProofView detail={detail} moments={moments} events={events} metrics={metrics} momentId={proofId} onMoment={selectProof} />
          </div>
        )}
      </div>
      <HelpDialog open={help} onOpenChange={setHelp} />
    </>
  );
}
