import { useCallback, useEffect, useRef, useState } from "react";

import { replayUrl } from "./api";
import type { MatchEvent, Moment } from "./types";

/** Playback over the SSE replay: the stream moves the clock and announces cards; pausing or
 * scrubbing closes it, playing again resumes from the current position. */
export function useReplay(matchId: string | null, speed: number, duration: number) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [arrived, setArrived] = useState<string | null>(null); // last card the stream delivered
  const source = useRef<EventSource | null>(null);
  const position = useRef(0);

  const close = useCallback(() => {
    source.current?.close();
    source.current = null;
  }, []);

  const pause = useCallback(() => {
    close();
    setPlaying(false);
  }, [close]);

  const seek = useCallback(
    (next: number) => {
      pause();
      position.current = next;
      setT(next);
    },
    [pause],
  );

  const play = useCallback(() => {
    if (!matchId) return;
    close();
    const from = position.current >= duration ? 0 : position.current;
    const es = new EventSource(replayUrl(matchId, speed, from));
    es.addEventListener("match_event", (ev) => {
      const e = JSON.parse((ev as MessageEvent).data) as MatchEvent;
      position.current = e.t;
      setT(e.t);
    });
    es.addEventListener("moment", (ev) => {
      setArrived((JSON.parse((ev as MessageEvent).data) as Moment).id);
    });
    es.addEventListener("end", () => {
      es.close();
      setPlaying(false);
    });
    es.onerror = () => {
      es.close(); // no automatic reconnect: the user presses play again
      setPlaying(false);
    };
    source.current = es;
    setPlaying(true);
  }, [matchId, speed, duration, close]);

  // A new match starts at kickoff.
  useEffect(() => {
    seek(0);
    setArrived(null);
  }, [matchId, seek]);

  // A speed change while playing restarts the stream from the current position.
  const playingRef = useRef(playing);
  playingRef.current = playing;
  useEffect(() => {
    if (playingRef.current) play();
  }, [speed]);

  useEffect(() => close, [close]);

  return { t, playing, arrived, play, pause, seek };
}
