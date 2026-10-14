// Names for the generated API schema types (src/api/schema.gen.ts); new UI code imports from here.
import type { components } from "./schema.gen";

type Schemas = components["schemas"];

export type MatchSummary = Schemas["MatchSummary"];
export type MatchDetail = Schemas["MatchDetail"];
export type TimelineEvent = Schemas["TimelineEvent"];
export type Squads = Schemas["Squads"];
export type Moment = Schemas["MomentOut"];
export type Claim = Schemas["ClaimOut"];
export type Evidence = Schemas["EvidenceOut"];
export type Metrics = Schemas["MetricsOut"];
export type MetricInfo = Schemas["MetricInfo"];
export type Health = Schemas["Health"];
