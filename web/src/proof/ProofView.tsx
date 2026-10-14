// The Proof face (desktop ≥ 1024 px: rail | Receipt | evidence; below: one column). State here is the
// selected claim and event; the selected moment lives in the match view so the Flip can carry it.
import { useMemo, useState } from "react";

import type { MatchDetail, Moment, TimelineEvent } from "../api/types";
import { Empty } from "../app/states";
import { DESKTOP, useMediaQuery } from "../design/useMediaQuery";
import { bySeq, rowsOf } from "./evidence";
import { EvidenceList } from "./EvidenceList";
import { EvidencePitch } from "./EvidencePitch";
import { MomentRail } from "./MomentRail";
import styles from "./proof.module.css";
import { defaultClaim, Receipt, type MetricsState } from "./Receipt";

interface Props {
  detail: MatchDetail;
  moments: readonly Moment[];
  events: readonly TimelineEvent[];
  metrics: MetricsState;
  momentId: string | null;
  onMoment: (id: string) => void;
}

export function ProofView({ detail, moments, events, metrics, momentId, onMoment }: Props) {
  const desktop = useMediaQuery(DESKTOP);
  if (moments.length === 0) return <Empty>No narrated moments in this match.</Empty>;
  const moment = moments.find((m) => m.id === momentId) ?? moments[0]!;
  return (
    <div className={styles.proof} data-layout={desktop ? "desktop" : "narrow"}>
      <div className={styles.railCol}>
        <MomentRail moments={moments} eventMatchId={detail.event_match_id} selectedId={moment.id} horizontal={!desktop} onSelect={onMoment} />
      </div>
      <MomentProof key={moment.id} moment={moment} detail={detail} events={events} metrics={metrics} />
    </div>
  );
}

/** Everything that belongs to one moment; remounted per moment so claim and event selection reset. */
function MomentProof({ moment, detail, events, metrics }: { moment: Moment; detail: MatchDetail; events: readonly TimelineEvent[]; metrics: MetricsState }) {
  const [claimId, setClaimId] = useState(() => defaultClaim(moment));
  const [eventSel, setEventSel] = useState<string | null>(null);
  const index = useMemo(() => bySeq(events), [events]);
  const claim = moment.claims.find((c) => c.id === claimId) ?? null;
  const rows = useMemo(() => rowsOf(claim?.evidence ?? [], index), [claim, index]);
  const others = useMemo(
    () => rowsOf(moment.claims.filter((c) => c.id !== claimId).flatMap((c) => c.evidence), index),
    [moment, claimId, index],
  );
  return (
    <>
      <Receipt
        moment={moment}
        detail={detail}
        metrics={metrics}
        claimId={claimId}
        onSelectClaim={(id) => {
          setClaimId(id);
          setEventSel(null);
        }}
      />
      <aside className={styles.evidence} aria-label="Evidence">
        <EvidencePitch marked={rows} dimmed={others} selectedEventId={eventSel} onSelect={setEventSel} />
        <EvidenceList rows={rows} teams={detail.teams} selectedEventId={eventSel} onSelect={setEventSel} />
      </aside>
    </>
  );
}
