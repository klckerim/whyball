// Routes: "/" (first match), "/match/:id" (?mode, ?moment, ?t), anything else: not found.
import * as Tabs from "@radix-ui/react-tabs";
import { BrowserRouter, Outlet, Route, Routes, useOutletContext, useParams, useSearchParams } from "react-router";

import { api } from "../api/client";
import type { MatchSummary } from "../api/types";
import styles from "./app.module.css";
import { MatchView } from "./MatchView";
import { Empty, Failed, Loading, NotFound } from "./states";
import { TopBar } from "./TopBar";
import { type Async, useAsync } from "./useAsync";

type MatchesState = Async<MatchSummary[]> & { retry: () => void };

function Shell() {
  const matches = useAsync(api.matches, "matches");
  const [params, setParams] = useSearchParams();
  const mode = params.get("mode") === "proof" ? "proof" : "air";
  return (
    <Tabs.Root
      className={styles.shell}
      value={mode}
      onValueChange={(v) => {
        const next = new URLSearchParams(params);
        next.set("mode", v);
        setParams(next, { replace: true });
      }}
    >
      <TopBar matches={matches.status === "ok" ? matches.data : null} />
      <main className={styles.main}>
        <Outlet context={matches} />
      </main>
    </Tabs.Root>
  );
}

function DefaultMatch() {
  const matches = useOutletContext<MatchesState>();
  if (matches.status === "loading") return <Loading what="the match list" />;
  if (matches.status === "error") return <Failed what="the match list" error={matches.error} retry={matches.retry} />;
  const first = matches.data[0];
  return first ? <MatchView id={first.id} /> : <Empty>No matches in the publication store.</Empty>;
}

function MatchRoute() {
  const { id = "" } = useParams();
  return <MatchView id={id} />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<DefaultMatch />} />
        <Route path="match/:id" element={<MatchRoute />} />
        <Route path="*" element={<NotFound what="There is no page at this address." />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
