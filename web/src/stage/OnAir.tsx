// The On Air face: the program stage with score bug, SYNTHETIC mark, pitch and lower third. Narrow
// screens (< 768 px) move the lower third under the stage; the stage keeps the seal (DESIGN D18).
import { useMemo } from "react";

import type { MatchDetail, Moment, TimelineEvent } from "../api/types";
import { REDUCED_MOTION, useMediaQuery, WIDE } from "../design/useMediaQuery";
import { ballAt, eventAt, positioned, trail } from "../state/match";
import { LowerThird } from "./LowerThird";
import { Pitch } from "./Pitch";
import { ProofSeal } from "./ProofSeal";
import { ProgramStage } from "./ProgramStage";
import { ScoreBug } from "./ScoreBug";
import styles from "./stage.module.css";
import { SyntheticMark } from "./SyntheticMark";

interface Props {
  detail: MatchDetail;
  events: TimelineEvent[];
  moments: Moment[];
  t: number;
  shownId: string | null;
  guides: boolean;
  onProof?: () => void;
}

export function OnAir({ detail, events, moments, t, shownId, guides, onProof }: Props) {
  const wide = useMediaQuery(WIDE);
  const reduced = useMediaQuery(REDUCED_MOTION);
  const points = useMemo(() => positioned(events), [events]);
  const meta = useMemo(() => events.find((e) => e.type === "match_meta") ?? null, [events]);
  const shown = moments.find((m) => m.id === shownId) ?? null;
  const ball = ballAt(points, t, !reduced);

  return (
    <div className={styles.onAir}>
      <ProgramStage guides={guides}>
        <div className={styles.top}>
          {meta ? <ScoreBug detail={detail} meta={meta} current={eventAt(events, t)} ended={t >= detail.duration_t} t={t} /> : null}
          <SyntheticMark />
        </div>
        <Pitch ball={ball} trail={trail(points, t)} />
        {shown && wide ? <LowerThird moment={shown} eventMatchId={detail.event_match_id} placement="stage" onProof={onProof} /> : null}
        {shown && !wide ? (
          <div className={styles.stageSeal}>
            <ProofSeal checks={shown.checks} onProof={onProof} />
          </div>
        ) : null}
      </ProgramStage>
      {!wide ? (
        shown ? (
          <LowerThird moment={shown} eventMatchId={detail.event_match_id} placement="panel" onProof={onProof} />
        ) : (
          <p className={styles.panelEmpty}>No card on air</p>
        )
      ) : null}
    </div>
  );
}
