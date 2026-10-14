import { useCallback, useEffect, useState } from "react";

export type Async<T> =
  | { status: "loading" }
  | { status: "error"; error: Error }
  | { status: "ok"; data: T };

/** Runs `load` when `key` changes; `retry` runs it again. Late results of an old key are dropped. */
export function useAsync<T>(load: () => Promise<T>, key: string): Async<T> & { retry: () => void } {
  const [state, setState] = useState<Async<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    setState({ status: "loading" });
    load().then(
      (data) => live && setState({ status: "ok", data }),
      (error: unknown) => live && setState({ status: "error", error: error instanceof Error ? error : new Error(String(error)) }),
    );
    return () => {
      live = false;
    };
  }, [key, attempt]); // `load` is re-created each render; `key` names what it loads
  const retry = useCallback(() => setAttempt((a) => a + 1), []);
  return { ...state, retry };
}
