// Observatory wire types — USTRUCT mirrors of the /v1/observatory/* JSON.
// Copyright A-C-I Software & Development. All rights reserved.
//
// Field names mirror gateway/cockpit/handlers_observatory.py +
// observatory_metrics.py (the actual v1 response shapes) exactly; each
// UPROPERTY comment cites its JSON field. Parsing is tolerant of ADDITIVE
// unknown fields (spec §3 versioning rule: additive only under v=1).
//
// Optional/nullable JSON handling (binding): USTRUCT members cannot be
// TOptional (UHT rejects it), so every field the gateway may send as null
// or omit (heat, pos, task_class, percentiles, …) gets an explicit bHas*
// boolean. bHas* == false means "the gateway did not measure/compute this"
// — render the documented cool-gray/dormant dressing, NEVER a guessed value
// (spec §5 confidence gate, §6 honesty rule).

#pragma once

#include "CoreMinimal.h"
#include "ObservatoryTypes.generated.h"

/** One graph super-node (snapshot `graph.clusters[]`, spec §3.1). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsCluster
{
	GENERATED_BODY()

	/** JSON `id` — super-node id ("c-…"), the key for /layout expansion. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Id;

	/** JSON `label` — display label (top-degree member's title). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Label;

	/** JSON `type_mix` — member-type fractions, e.g. {"code": 0.8, "docs": 0.2}. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TMap<FString, float> TypeMix;

	/** JSON `members` — member node count. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 Members = 0;

	/** True when JSON `pos` was a 3-number array (it is null until the
	 *  gateway layout engine has solved this graph version). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasPos = false;

	/** JSON `pos` — gateway-computed layout position, arbitrary units.
	 *  Only meaningful when bHasPos. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FVector Pos = FVector::ZeroVector;

	/** JSON `radius` — render radius hint, same units as Pos. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float Radius = 0.0f;

	/** True when JSON `heat` was a number. null = below the n>=5 confidence
	 *  gate or no activations measured (spec §5) — render cool-gray. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasHeat = false;

	/** JSON `heat` — normalized measured heat in [0,1]. Only when bHasHeat. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float Heat = 0.0f;
};

/** One edge between super-nodes — and, with bHasHeat=false and Heat unused,
 *  also the expanded-member edge shape of /layout (snapshot
 *  `graph.cluster_edges[]` / layout `edges[]`: `a`, `b`, `weight`[, `heat`]). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsClusterEdge
{
	GENERATED_BODY()

	/** JSON `a` — first endpoint id (cluster or node id by context). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString A;

	/** JSON `b` — second endpoint id. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString B;

	/** JSON `weight` — summed edge weight. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float Weight = 0.0f;

	/** True when JSON `heat` was a number (layout edges never carry heat). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasHeat = false;

	/** JSON `heat` — measured edge heat in [0,1]. Only when bHasHeat. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float Heat = 0.0f;
};

/** One in-flight job at a pipeline station (snapshot `stations.active_jobs[]`).
 *  The static station list itself is `stations.nodes` (FObsSnapshot::StationNodes). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsStation
{
	GENERATED_BODY()

	/** JSON `job_id` — click-through key for GET /v1/cockpit/jobs/{id}. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString JobId;

	/** True when JSON `task_class` was a string (not tracked for every job). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasTaskClass = false;

	/** JSON `task_class` — packet color key. Only when bHasTaskClass. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString TaskClass;

	/** JSON `stage` — current station (job|navigator|worker|gate|ledger|…). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Stage;

	/** JSON `stage_entered_at` — ISO-8601 timestamp. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString StageEnteredAt;

	/** True when JSON `queue_pos` was a number (null = not queued). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasQueuePos = false;

	/** JSON `queue_pos`. Only when bHasQueuePos. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 QueuePos = 0;
};

/** One Brain Ladder stratum (snapshot `ladder.tiers[]`, spec §2.3). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsLadderTier
{
	GENERATED_BODY()

	/** JSON `tier` — enum string: local | hosted | paired. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Tier;

	/** True when JSON `model` was a string (null = no decisions in window). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasModel = false;

	/** JSON `model` — most-routed model id on this tier. Only when bHasModel. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Model;

	/** True when JSON `share_1h` was a number. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasShare = false;

	/** JSON `share_1h` — fraction of routed turns ∈ [0,1] (ambient brightness). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float Share = 0.0f;

	/** JSON `n` — measured decision count behind these numbers. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 N = 0;

	/** True when JSON `p50_latency_ms` was a number. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasP50LatencyMs = false;

	/** JSON `p50_latency_ms`. Only when bHasP50LatencyMs. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float P50LatencyMs = 0.0f;

	/** True when JSON `p95_latency_ms` was a number. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasP95LatencyMs = false;

	/** JSON `p95_latency_ms`. Only when bHasP95LatencyMs. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float P95LatencyMs = 0.0f;
};

/** One per-stage rollup row (metrics `stages[]`, spec §3.3). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsStageStat
{
	GENERATED_BODY()

	/** JSON `stage`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Stage;

	/** True when JSON `task_class` was a string (null = class untracked). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasTaskClass = false;

	/** JSON `task_class`. Only when bHasTaskClass. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString TaskClass;

	/** JSON `count` — measured transitions in window. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 Count = 0;

	/** True when JSON `p50_ms` was a number. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasP50Ms = false;

	/** JSON `p50_ms`. Only when bHasP50Ms. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float P50Ms = 0.0f;

	/** True when JSON `p95_ms` was a number. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasP95Ms = false;

	/** JSON `p95_ms`. Only when bHasP95Ms. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float P95Ms = 0.0f;

	/** True when JSON `queue_wait_p95_ms` was a number. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasQueueWaitP95Ms = false;

	/** JSON `queue_wait_p95_ms`. Only when bHasQueueWaitP95Ms. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float QueueWaitP95Ms = 0.0f;

	/** JSON `retries`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 Retries = 0;
};

/** One per-gate rollup row (metrics `gates[]`, spec §3.3). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsGateStat
{
	GENERATED_BODY()

	/** JSON `gate` — planning|build|review|test|security|release|owner|rollback. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Gate;

	/** True when JSON `task_class` was a string. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasTaskClass = false;

	/** JSON `task_class`. Only when bHasTaskClass. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString TaskClass;

	/** JSON `passes`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 Passes = 0;

	/** JSON `fails`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 Fails = 0;

	/** JSON `overrides`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 Overrides = 0;

	/** True when JSON `fail_rate` was a number (null when n == 0). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasFailRate = false;

	/** JSON `fail_rate` ∈ [0,1]. Only when bHasFailRate. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float FailRate = 0.0f;
};

/** One per-model rollup row (metrics `models[]`, spec §3.3). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsModelStat
{
	GENERATED_BODY()

	/** JSON `tier` — local | hosted | paired. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Tier;

	/** JSON `model`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Model;

	/** JSON `calls`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 Calls = 0;

	/** True when JSON `p95_latency_ms` was a number. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasP95LatencyMs = false;

	/** JSON `p95_latency_ms`. Only when bHasP95LatencyMs. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float P95LatencyMs = 0.0f;

	/** JSON `tokens_in`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 TokensIn = 0;

	/** JSON `tokens_out`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 TokensOut = 0;

	/** JSON `est_cost_usd`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float EstCostUsd = 0.0f;
};

/** One per-task-class cost row (metrics `cost_per_task_class[]`, spec §3.3). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsCostEntry
{
	GENERATED_BODY()

	/** JSON `task_class`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString TaskClass;

	/** JSON `usd` — measured spend in window. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float Usd = 0.0f;

	/** JSON `n` — tasks behind the number. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 N = 0;
};

/** One bottleneck-heat entry (metrics `heat[]`, spec §5 math). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsHeatEntry
{
	GENERATED_BODY()

	/** JSON `key` — "stage:<stage>:<class>" / "gate:<gate>:<class>". */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Key;

	/** True when JSON `score` was a number. null = n < min_n confidence
	 *  gate — render cool-gray with "insufficient data (n=X)" tooltip. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasScore = false;

	/** JSON `score` ∈ [0,1]. Only when bHasScore. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float Score = 0.0f;

	/** JSON `n` — real observation count (shown even when score is null). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 N = 0;

	/** JSON `evidence_ref` — a filtered existing /v1/cockpit/ledger query;
	 *  the click-through proof for this glow (spec §5: no vibes). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString EvidenceRef;
};

/** GET /v1/observatory/metrics response (and snapshot `metrics_rollup`). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsMetricsRollup
{
	GENERATED_BODY()

	/** JSON `v` — contract version (1). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 V = 0;

	/** JSON `window` — 15m | 1h | 24h | 7d. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Window;

	/** JSON `from` — window start, ISO-8601. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString FromIso;

	/** JSON `to` — window end, ISO-8601. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString ToIso;

	/** JSON `stages[]`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FObsStageStat> Stages;

	/** JSON `gates[]`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FObsGateStat> Gates;

	/** JSON `models[]`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FObsModelStat> Models;

	/** JSON `cost_per_task_class[]`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FObsCostEntry> CostPerTaskClass;

	/** JSON `heat[]`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FObsHeatEntry> Heat;

	/** JSON `heat_weights` — the formula's current weights, returned so the
	 *  UI can show its work (spec §5). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TMap<FString, float> HeatWeights;

	/** JSON `min_n` — confidence-gate threshold below which heat is null. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 MinN = 0;
};

/** One expanded member node (GET /v1/observatory/layout `nodes[]`, spec §3.4). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsLayoutNode
{
	GENERATED_BODY()

	/** JSON `id` — graph node id ("n-…"). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Id;

	/** JSON `type` — code | docs | memory | ledger | … (ISM archetype key). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Type;

	/** JSON `label`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Label;

	/** True when JSON `pos` was a 3-number array (null until layout solved). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasPos = false;

	/** JSON `pos` — LOCAL space, relative to the cluster center (spec §3.4).
	 *  Only meaningful when bHasPos. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FVector Pos = FVector::ZeroVector;

	/** JSON `degree`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 Degree = 0;

	/** True when JSON `heat` was a number. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasHeat = false;

	/** JSON `heat` ∈ [0,1]. Only when bHasHeat. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float Heat = 0.0f;

	/** JSON `source_ref` — the real file/source behind this node. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString SourceRef;
};

/** GET /v1/observatory/layout response — one cluster's expansion. */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsClusterLayout
{
	GENERATED_BODY()

	/** JSON `v`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 V = 0;

	/** JSON `cluster` — the super-node id that was expanded. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Cluster;

	/** False when the gateway answered the documented
	 *  {"status":"unavailable"} shape (graph cache not built) — show the
	 *  dormant dressing, no fake galaxy. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bGraphAvailable = false;

	/** JSON `reason` of the unavailable shape (empty when available). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString UnavailableReason;

	/** JSON `graph_version` — mismatch vs the snapshot's is the stale-id
	 *  tell: refetch the snapshot (spec §3.4). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString GraphVersion;

	/** JSON `layout_status` — gateway's own statement of whether positions
	 *  were computed ("unavailable" => every node has bHasPos == false). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString LayoutStatus;

	/** JSON `layout_algo` — which algorithm actually ran (show-your-work
	 *  doctrine; absent on older gateways => empty). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString LayoutAlgo;

	/** JSON `truncated` — true when the cluster exceeded the limit and only
	 *  top-degree members were returned. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bTruncated = false;

	/** JSON `nodes[]`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FObsLayoutNode> Nodes;

	/** JSON `edges[]` (a/b/weight; never carries heat — bHasHeat false). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FObsClusterEdge> Edges;
};

/** GET /v1/observatory/snapshot response — the one-call map boot (spec §3.1). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsSnapshot
{
	GENERATED_BODY()

	/** JSON `v`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 V = 0;

	/** JSON `generated_at` — ISO-8601. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString GeneratedAt;

	/** False when `graph` answered the documented {"status":"unavailable"}
	 *  shape (GraphRAG cache not built) — dormant dressing, no fake data. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bGraphAvailable = false;

	/** JSON `graph.reason` of the unavailable shape (empty when available). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString GraphUnavailableReason;

	/** JSON `graph.graph_version` — changes when GraphRAG rebuilds. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString GraphVersion;

	/** JSON `graph.node_count` — full-graph scale (UE never loads it all). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 NodeCount = 0;

	/** JSON `graph.edge_count`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 EdgeCount = 0;

	/** JSON `graph.clusters[]` — the ~200 default-LOD super-nodes (§8). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FObsCluster> Clusters;

	/** JSON `graph.cluster_edges[]`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FObsClusterEdge> ClusterEdges;

	/** JSON `graph.clusters_total` — communities before the 200 cap. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 ClustersTotal = 0;

	/** JSON `graph.clusters_truncated`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bClustersTruncated = false;

	/** JSON `graph.layout_status` — gateway statement on cluster `pos`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString LayoutStatus;

	/** JSON `graph.layout_algo` (absent on older gateways => empty). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString LayoutAlgo;

	/** JSON `stations.nodes` — the static station graph:
	 *  job → navigator → worker → gate → ledger (spec §2.2). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FString> StationNodes;

	/** JSON `stations.active_jobs[]` — in-flight packets. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FObsStation> ActiveJobs;

	/** JSON `stations.queue_depth`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 QueueDepth = 0;

	/** JSON `ladder.tiers[]` — Brain Ladder strata (spec §2.3). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FObsLadderTier> LadderTiers;

	/** JSON `metrics_rollup` — same shape as GET /v1/observatory/metrics. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FObsMetricsRollup MetricsRollup;
};

/** Recommendation card `validation` block (spec §6: measured-only numbers). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsValidation
{
	GENERATED_BODY()

	/** JSON `method` — e.g. "replay" | "shadow". */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Method;

	/** JSON `n_baseline` — baseline sample size. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 NBaseline = 0;

	/** JSON `n_candidate` — candidate-policy sample size. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 NCandidate = 0;

	/** True when JSON `median_delta_pct` was a number (null while the card
	 *  is below the n>=50 evidence threshold — render "collecting"). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasMedianDeltaPct = false;

	/** JSON `median_delta_pct`. Only when bHasMedianDeltaPct. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float MedianDeltaPct = 0.0f;

	/** True when JSON `ci95` was a 2-number array (null while collecting). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasCi95 = false;

	/** JSON `ci95` — [low, high] 95% confidence interval. Only when bHasCi95. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<float> Ci95;

	/** JSON `metric` — what the delta measures (e.g. "latency_ms"). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Metric;
};

/** One verdict card (GET /v1/observatory/recommendations `cards[]`, spec §6). */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsRecommendationCard
{
	GENERATED_BODY()

	/** JSON `id` — card id, also the staged-proposal key for the owner-gated
	 *  apply path (POST /v1/cockpit/approvals/{id}, spec §7). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Id;

	/** JSON `title`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Title;

	/** JSON `state` — e.g. "validated" | "collecting". The card text for a
	 *  collecting state never shows projected numbers (spec §6 hard rule). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString State;

	/** True when JSON `delta` was non-null. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasDelta = false;

	/** JSON `delta` — human-readable measured delta (string verbatim; a bare
	 *  number is stringified). Only when bHasDelta. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Delta;

	/** JSON `validation` — the measurements behind every stated number. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FObsValidation Validation;

	/** JSON `evidence_refs[]` — existing cockpit routes proving the claim. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FString> EvidenceRefs;

	/** JSON `created_at` — ISO-8601. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString CreatedAt;
};

/** GET /v1/observatory/recommendations response. */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsRecommendations
{
	GENERATED_BODY()

	/** JSON `v`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 V = 0;

	/** JSON `generated_at` — ISO-8601. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString GeneratedAt;

	/** JSON `cards[]`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	TArray<FObsRecommendationCard> Cards;
};

/** SSE `job.stage` payload (spec §3.2) — a packet moved stations. */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsJobStage
{
	GENERATED_BODY()

	/** JSON `job_id`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString JobId;

	/** JSON `task_class` — packet color key. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString TaskClass;

	/** JSON `stage` — queued|navigator|worker|gate|ledger|done|failed. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Stage;

	/** JSON `queue_depth`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 QueueDepth = 0;

	/** True when JSON `stage_latency_ms` was a number (null on entry). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasStageLatencyMs = false;

	/** JSON `stage_latency_ms` — drives packet speed. Only when bHas…. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float StageLatencyMs = 0.0f;

	/** JSON `ts` — ISO-8601. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Ts;
};

/** SSE `gate.verdict` payload (spec §3.2) — a gate fired. FAIL flares red. */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsGateVerdict
{
	GENERATED_BODY()

	/** JSON `job_id`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString JobId;

	/** JSON `gate` — planning|build|review|test|security|release|owner|rollback. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Gate;

	/** JSON `verdict` — pass | fail | override. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Verdict;

	/** JSON `attempt`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 Attempt = 0;

	/** JSON `detail_ref` — existing cockpit route with the full record. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString DetailRef;

	/** JSON `ts` — ISO-8601. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Ts;
};

/** SSE `node.activate` payload (spec §3.2) — a GraphRAG touch; drives the
 *  pulse Niagara effect. Batched <= 10/s gateway-side with coalescing. */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsNodeActivate
{
	GENERATED_BODY()

	/** JSON `cluster_id` — which super-node pulses at default LOD. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString ClusterId;

	/** True when JSON `node_id` was a string (null = cluster-level event). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	bool bHasNodeId = false;

	/** JSON `node_id`. Only when bHasNodeId. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString NodeId;

	/** JSON `kind` — query | write | promote. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Kind;

	/** JSON `weight`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float Weight = 0.0f;

	/** JSON `ts` — ISO-8601. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Ts;
};

/** SSE `route.decision` payload (spec §3.2) — one turn's Brain Ladder path. */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsRouteDecision
{
	GENERATED_BODY()

	/** JSON `turn_id`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString TurnId;

	/** JSON `tier` — local | hosted | paired. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Tier;

	/** JSON `model`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Model;

	/** JSON `reason` — the router's stated reason string. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Reason;

	/** JSON `latency_ms`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float LatencyMs = 0.0f;

	/** JSON `tokens_in`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 TokensIn = 0;

	/** JSON `tokens_out`. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	int32 TokensOut = 0;

	/** JSON `ts` — ISO-8601. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Ts;
};

/** One raw stream frame: the `event:` type plus the verbatim `data:` JSON.
 *  Broadcast for EVERY frame (known types additionally get their typed
 *  delegate) so unknown additive event types are observable, never lost. */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsStreamEvent
{
	GENERATED_BODY()

	/** SSE `event:` field — job.stage | gate.verdict | node.activate |
	 *  route.decision | resync | <future additive types>. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Type;

	/** The verbatim `data:` payload (JSON text). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString PayloadJson;

	/** JSON `ts` extracted from the payload when present (every spec §3.2
	 *  payload carries one); empty otherwise. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Ts;
};

/** One fused action from GET /v1/observatory/actions — the live "neural network
 *  wallpaper" feed (gateway `action_fusion.py`). Every field comes verbatim from
 *  a really-recorded source event; nothing is invented. The `kind` vocabulary is
 *  closed (see gateway action_fusion.KINDS) so renderers can pin a finite switch. */
USTRUCT(BlueprintType)
struct SYNAPSEOBSERVATORY_API FObsActionEvent
{
	GENERATED_BODY()

	/** JSON `kind` — cluster.spark | pipeline.packet | gate.flare | ladder.streak
	 *  | owner.pulse | agent.pulse | skill.pulse | system.pulse | audit.flare. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Kind;

	/** JSON `source` — collector | flywheel | cockpit | axiom (provenance). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Source;

	/** JSON `target.cluster_id` — present for cluster-targeted actions; else empty. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString ClusterId;

	/** JSON `target.job_id` — present for job-targeted actions; else empty. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString JobId;

	/** JSON `label` — short human/visual label (from real fields only). */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Label;

	/** JSON `weight` — real numeric when the source carries one, else 1.0. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	float Weight = 1.0f;

	/** JSON `severity` — info | warn | error | critical. */
	UPROPERTY(BlueprintReadOnly, Category = "Observatory")
	FString Severity;
};
