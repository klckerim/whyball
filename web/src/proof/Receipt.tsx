// The Receipt: the card's sentence with each claim value underlined, the selected claim's detail
// (value beside its definition, subject, window) and the card's recorded checks. Definitions and
// windows come from /api/metrics (UI_SPEC T5); the UI writes none of its own.
import type { Claim, MatchDetail, MetricInfo, Metrics, Moment } from "../api/types";
import { Failed } from "../app/states";
import type { Async } from "../app/useAsync";
import { eventId, Fact } from "../design/Fact";
import { SentenceText } from "../design/SentenceText";
import { SourceBadge } from "../design/SourceBadge";
import { TypeGlyph, typeLabel } from "../design/TypeGlyph";
import styles from "./proof.module.css";
import { windowKind } from "./window";

export type MetricsState = Async<Metrics> & { retry: () => void };

interface Props {
  moment: Moment;
  detail: Pick<MatchDetail, "event_match_id" | "teams">;
  metrics: MetricsState;
  claimId: string | null;
  onSelectClaim: (id: string) => void;
}

/** Claims whose value is written in the sentence, then the others (the sentence states them in words). */
export function splitClaims(moment: Moment): { inText: Claim[]; inWords: Claim[] } {
  const shown = new Set(moment.segments.map((s) => s.claim_id).filter(Boolean));
  return {
    inText: moment.claims.filter((c) => shown.has(c.id)),
    inWords: moment.claims.filter((c) => !shown.has(c.id)),
  };
}

/** The claim to open with: the first value in the sentence, else the first claim. */
export function defaultClaim(moment: Moment): string | null {
  const first = moment.segments.find((s) => s.claim_id && moment.claims.some((c) => c.id === s.claim_id));
  return first?.claim_id ?? moment.claims[0]?.id ?? null;
}

export function Receipt({ moment, detail, metrics, claimId, onSelectClaim }: Props) {
  const { inWords } = splitClaims(moment);
  const claim = moment.claims.find((c) => c.id === claimId) ?? null;
  const hasWords = inWords.length > 0;
  return (
    <section className={styles.receipt} aria-label="Receipt" data-card-id={moment.id}>
      <header className={styles.receiptHead}>
        <span className={styles.receiptType}>
          <TypeGlyph type={moment.type} />
          <span>{typeLabel(moment.type)}</span>
          <Fact
            className={styles.receiptMinute}
            event={{ id: eventId(detail.event_match_id, moment.at_seq), minute_label: moment.minute_label }}
            field="minute_label"
          />
        </span>
        <SourceBadge source={moment.source} />
      </header>
      <p className={styles.sentence}>
        <SentenceText segments={moment.segments} claims={moment.claims} interactive selectedId={claimId} onSelect={onSelectClaim} />
      </p>
      {hasWords ? (
        <div className={styles.inWords}>
          <h3 className={styles.h3}>Claims the sentence states in words</h3>
          <ul className={styles.wordList}>
            {inWords.map((c) => (
              <li key={c.id}>
                <button type="button" className={styles.wordClaim} aria-pressed={c.id === claimId} onClick={() => onSelectClaim(c.id)}>
                  <Fact claim={c} field="label" /> <Fact claim={c} />
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {claim ? <ClaimDetail claim={claim} detail={detail} metrics={metrics} /> : <p className={styles.note}>This card holds no claims.</p>}
      <VerificationRecord moment={moment} />
    </section>
  );
}

function ClaimDetail({ claim, detail, metrics }: { claim: Claim; detail: Pick<MatchDetail, "teams">; metrics: MetricsState }) {
  const info: MetricInfo | undefined = metrics.status === "ok" ? metrics.data.metrics.find((m) => m.id === claim.metric) : undefined;
  return (
    <section className={styles.claim} aria-label="Selected claim" data-claim-id={claim.id}>
      <h3 className={styles.h3}>{info?.label ?? claim.label}</h3>
      <p className={styles.valueLine}>
        <Fact className={styles.bigValue} claim={claim} />
        <span className={styles.definition} data-testid="definition">
          {metrics.status === "ok" ? (info ? info.definition : "No definition is published for this metric.") : null}
          {metrics.status === "loading" ? <span className={styles.skeletonLine} aria-busy="true" role="status">Loading the definition…</span> : null}
        </span>
      </p>
      {metrics.status === "error" ? <Failed what="the metric definitions" error={metrics.error} retry={metrics.retry} /> : null}
      <dl className={styles.facts}>
        <div>
          <dt>Subject</dt>
          <dd>
            {claim.team || claim.player ? (
              <>
                {claim.team ? <Fact claim={claim} field="team" teams={detail.teams} /> : null}
                {claim.team && claim.player ? " · " : null}
                {claim.player ? <Fact claim={claim} field="player" /> : null}
              </>
            ) : (
              "no subject"
            )}
          </dd>
        </div>
        <div>
          <dt>Window</dt>
          <dd>
            <WindowText claim={claim} info={info} loading={metrics.status !== "ok"} />
          </dd>
        </div>
      </dl>
    </section>
  );
}

function WindowText({ claim, info, loading }: { claim: Claim; info: MetricInfo | undefined; loading: boolean }) {
  const w = windowKind(claim, info);
  if (w.kind === "at") {
    return (
      <>
        at <Fact claim={claim} field="end" />
      </>
    );
  }
  if (w.kind === "range") {
    return (
      <>
        from <Fact claim={claim} field="start" /> to <Fact claim={claim} field="end" />
      </>
    );
  }
  if (w.kind === "rolling" && info) {
    return (
      <>
        the last <Fact claim={claim} window={info.window} /> minutes played, closing at the claim's end (<Fact claim={claim} field="end" />)
      </>
    );
  }
  return <>{loading ? "not loaded yet" : "no window published"}</>;
}

function VerificationRecord({ moment }: { moment: Moment }) {
  const rows = [
    ["Lint issues", "lint_issues"],
    ["Claims checked", "claims_total"],
    ["Claims passed", "claims_verified"],
  ] as const;
  return (
    <section className={styles.record} aria-label="Verification record">
      <h3 className={styles.h3}>
        Verification record <span className={styles.codeTag}>checked by code</span>
      </h3>
      <dl className={styles.facts}>
        {rows.map(([label, field]) => (
          <div key={field}>
            <dt>{label}</dt>
            <dd>
              <Fact checks={moment.checks} cardId={moment.id} field={field} />
            </dd>
          </div>
        ))}
      </dl>
      <p className={styles.note}>Recorded when this card was published: text lint and claim verification, both run by code.</p>
    </section>
  );
}
