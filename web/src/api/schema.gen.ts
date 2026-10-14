// Generated from web/openapi.json by web/tools/openapi-gen (openapi-typescript). Do not edit:
// run `.venv/bin/python -m app.api.openapi` then `cd web && npm run gen:api`.

export interface paths {
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/matches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Matches */
        get: operations["matches_api_matches_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/matches/{match_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Match Detail */
        get: operations["match_detail_api_matches__match_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/matches/{match_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Match Events
         * @description Every event of the stream in order, match_meta (seq 0) included; the stage reads ball positions here.
         */
        get: operations["match_events_api_matches__match_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/matches/{match_id}/moments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Moments */
        get: operations["moments_api_matches__match_id__moments_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/matches/{match_id}/replay": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Match Replay */
        get: operations["match_replay_api_matches__match_id__replay_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/matches/{match_id}/series": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Match Series */
        get: operations["match_series_api_matches__match_id__series_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/metrics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Metrics */
        get: operations["metrics_api_metrics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/healthz": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Healthz */
        get: operations["healthz_healthz_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ClaimOut */
        ClaimOut: {
            /** Comparison */
            comparison: string;
            /** Display */
            display: string;
            /** End */
            end: string;
            /** Evidence */
            evidence: components["schemas"]["EvidenceOut"][];
            /** Id */
            id: string;
            /** Kind */
            kind: string;
            /** Label */
            label: string;
            /** Metric */
            metric: string;
            /** Player */
            player: string | null;
            /** Start */
            start: string;
            /** Team */
            team: string | null;
            /** Value */
            value: number;
        };
        /** EvidenceOut */
        EvidenceOut: {
            /** Id */
            id: string;
            /** Minute */
            minute: number;
            /** Minute Label */
            minute_label: string;
            /** Period */
            period: number;
            /** Player */
            player: string | null;
            /** Second */
            second: number;
            /** Seq */
            seq: number;
            /** Team */
            team: string | null;
            /** Type */
            type: string;
            /** X */
            x?: number | null;
            /** Y */
            y?: number | null;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** Health */
        Health: {
            /** Matches */
            matches: number;
            /** Ok */
            ok: boolean;
        };
        /** MatchDetail */
        MatchDetail: {
            /** Duration T */
            duration_t: number;
            /** Event Match Id */
            event_match_id: string;
            final_score: components["schemas"]["Score"];
            /** Id */
            id: string;
            /** Periods */
            periods: components["schemas"]["Period"][];
            /** Prompt Version */
            prompt_version: string;
            /** Run Id */
            run_id: string;
            squads: components["schemas"]["Squads"];
            teams: components["schemas"]["Teams"];
            /** Timeline */
            timeline: components["schemas"]["TimelineEvent"][];
        };
        /** MatchSummary */
        MatchSummary: {
            final_score: components["schemas"]["Score"];
            /** Id */
            id: string;
            /** Moments */
            moments: number;
            /** Sources */
            sources: {
                [key: string]: number;
            };
            teams: components["schemas"]["Teams"];
        };
        /** MetricInfo */
        MetricInfo: {
            /** Definition */
            definition: string;
            /** Id */
            id: string;
            /** Kind */
            kind: string;
            /** Label */
            label: string;
            window: components["schemas"]["MetricWindow"];
        };
        /** MetricWindow */
        MetricWindow: {
            /** Minutes */
            minutes?: number | null;
            /**
             * Type
             * @enum {string}
             */
            type: "rolling" | "claim_range" | "cumulative";
        };
        /** MetricsOut */
        MetricsOut: {
            /** Comparisons */
            comparisons: string[];
            /** Kinds */
            kinds: string[];
            /** Metrics */
            metrics: components["schemas"]["MetricInfo"][];
        };
        /** MomentOut */
        MomentOut: {
            /** At Seq */
            at_seq: number;
            checks: components["schemas"]["StoredChecks"];
            /** Claims */
            claims: components["schemas"]["ClaimOut"][];
            /** Id */
            id: string;
            /** Importance */
            importance: number;
            /** Minute */
            minute: number;
            /** Minute Label */
            minute_label: string;
            /** Period */
            period: number;
            /** Prompt Version */
            prompt_version: string;
            /** Run Id */
            run_id: string | null;
            /** Second */
            second: number;
            /** Segments */
            segments: components["schemas"]["Segment"][];
            /**
             * Source
             * @enum {string}
             */
            source: "llm" | "template" | "template_fallback";
            /** T */
            t: number;
            /** Team */
            team: string | null;
            /** Text */
            text: string;
            /** Trace */
            trace: {
                [key: string]: unknown;
            }[];
            /** Type */
            type: string;
        };
        /** Period */
        Period: {
            /** End T */
            end_t: number;
            /** Period */
            period: number;
            /** Start T */
            start_t: number;
        };
        /** Score */
        Score: {
            /** Away */
            away: number;
            /** Home */
            home: number;
        };
        /**
         * Segment
         * @description A piece of the card text. `claim_id` is set only on a piece that states a claim's value.
         */
        Segment: {
            /** Claim Id */
            claim_id?: string | null;
            /** Text */
            text: string;
        };
        /** Series */
        Series: {
            /** Definition */
            definition: string;
            /** Label */
            label: string;
            /** Metric */
            metric: string;
            /**
             * Perspective
             * @constant
             */
            perspective: "home";
            /** Points */
            points: components["schemas"]["SeriesPoint"][];
            /** Step */
            step: number;
            window: components["schemas"]["MetricWindow"];
        };
        /** SeriesPoint */
        SeriesPoint: {
            /** T */
            t: number;
            /** Value */
            value: number | null;
        };
        /** Squad */
        Squad: {
            /** Bench */
            bench: string[];
            /** Lineup */
            lineup: string[];
            /** Name */
            name: string;
        };
        /** Squads */
        Squads: {
            away: components["schemas"]["Squad"];
            home: components["schemas"]["Squad"];
        };
        /**
         * StoredChecks
         * @description What the publish pipeline checked for this card (`run_moment` result at publish time).
         */
        StoredChecks: {
            /** Claims Total */
            claims_total: number;
            /** Claims Verified */
            claims_verified: number;
            /** Lint Issues */
            lint_issues: number;
        };
        /** Teams */
        Teams: {
            /** Away */
            away: string;
            /** Home */
            home: string;
        };
        /** TimelineEvent */
        TimelineEvent: {
            /** Minute */
            minute: number;
            /** Minute Label */
            minute_label: string;
            /** Outcome */
            outcome: string | null;
            /** Period */
            period: number;
            /** Player */
            player: string | null;
            score: components["schemas"]["Score"];
            /** Second */
            second: number;
            /** Seq */
            seq: number;
            /** T */
            t: number;
            /** Team */
            team: string | null;
            /** Type */
            type: string;
            /** X */
            x: number | null;
            /** Y */
            y: number | null;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: boolean;
                    };
                };
            };
        };
    };
    matches_api_matches_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MatchSummary"][];
                };
            };
        };
    };
    match_detail_api_matches__match_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                match_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MatchDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    match_events_api_matches__match_id__events_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                match_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TimelineEvent"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    moments_api_matches__match_id__moments_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                match_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MomentOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    match_replay_api_matches__match_id__replay_get: {
        parameters: {
            query?: {
                /** @description match seconds per second; 0 = no wait */
                speed?: number;
                /** @description start at this many seconds since kickoff */
                from_t?: number;
            };
            header?: never;
            path: {
                match_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    match_series_api_matches__match_id__series_get: {
        parameters: {
            query: {
                /** @description metric id with a series: pressure_balance, possession, field_tilt */
                metric: string;
                /** @description seconds between points on the match clock t */
                step?: number;
            };
            header?: never;
            path: {
                match_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Series"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    metrics_api_metrics_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MetricsOut"];
                };
            };
        };
    };
    healthz_healthz_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Health"];
                };
            };
        };
    };
}
