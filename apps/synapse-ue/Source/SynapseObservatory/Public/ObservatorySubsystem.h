// UObservatorySubsystem — typed client for the /v1/observatory/* family.
// Copyright A-C-I Software & Development. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "ObservatoryTypes.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "ObservatorySubsystem.generated.h"

class UmuseSseClient;

/** Fired after GET /v1/observatory/snapshot. bOk = HTTP 2xx AND the body
 *  parsed as the v1 shape; on failure Snapshot is default-initialized. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnObsSnapshot, bool, bOk, const FObsSnapshot&, Snapshot);

/** Fired after GET /v1/observatory/metrics?window=. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnObsMetrics, bool, bOk, const FObsMetricsRollup&, Rollup);

/** Fired after GET /v1/observatory/layout?cluster=. A 404 (stale cluster id
 *  after a graph rebuild) arrives as bOk=false — refetch the snapshot. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnObsLayout, bool, bOk, const FObsClusterLayout&, Layout);

/** Fired after GET /v1/observatory/recommendations. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnObsRecommendations, bool, bOk, const FObsRecommendations&, Recommendations);

/** SSE `job.stage` — a pipeline packet moved stations. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnObsJobStage, const FObsJobStage&, Event);

/** SSE `gate.verdict` — a verification gate fired. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnObsGateVerdict, const FObsGateVerdict&, Event);

/** SSE `node.activate` — a GraphRAG touch (pulse effect input). */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnObsNodeActivate, const FObsNodeActivate&, Event);

/** SSE `route.decision` — one turn's Brain Ladder routing. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnObsRouteDecision, const FObsRouteDecision&, Event);

/** The client must refetch the snapshot: the gateway sent SSE `resync`
 *  (Reason = "gap" | "graph_rebuilt" per spec §3.2). Listeners call
 *  FetchSnapshot() and rebuild from the fresh state. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnObsResyncRequired, const FString&, Reason);

/** Raw tap: fired for EVERY stream frame (including types unknown to this
 *  client build — additive event types are observable, never dropped). */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnObsStreamEvent, const FObsStreamEvent&, Event);

/**
 * Typed client for the additive, read-only /v1/observatory/* route family
 * (10-observatory-spec.md §3). Pure data plane: it fetches, parses, and
 * broadcasts — it renders nothing and holds no policy logic (TDD §2.4).
 *
 * Contract routes implemented (greppable per TDD §2.2):
 *   GET /v1/observatory/snapshot         — auth: bearer (spec §3.1)
 *   GET /v1/observatory/stream           — auth: bearer, SSE (spec §3.2)
 *   GET /v1/observatory/metrics?window=  — auth: bearer (spec §3.3)
 *   GET /v1/observatory/layout?cluster=  — auth: bearer (spec §3.4)
 *   GET /v1/observatory/recommendations  — auth: bearer (spec §6)
 *
 * Networking & auth: every fetch goes through
 * UmuseGatewayClient::CreateAuthorizedGetRequest — SynapseNet stays the
 * only module that owns base-URL/token handling (token read fresh from the
 * settings token file, never stored here, never logged). The stream rides
 * UmuseSseClient (bearer + reconnect/backoff live there).
 *
 * Threading (TDD §2.2 / spec §8): fetch completions arrive on HTTP worker
 * threads and the JSON parse runs THERE — never on the game thread; only
 * the finished USTRUCT is marshaled over via
 * AsyncTask(ENamedThreads::GameThread, …). Stream frames are delivered by
 * UmuseSseClient already on the game thread; their payloads are small
 * per-event deltas (<= 10/s coalesced gateway-side), parsed inline. ALL
 * delegate broadcasts happen on the game thread.
 *
 * Honesty rule: parse failures and non-2xx broadcast bOk=false with a
 * default struct — the map shows its dormant dressing, never fake data.
 */
UCLASS()
class SYNAPSEOBSERVATORY_API UObservatorySubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	//~ Begin USubsystem
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;
	//~ End USubsystem

	/** GET /v1/observatory/snapshot — the one-call map boot (spec §3.1).
	 *  Broadcasts OnSnapshot on the game thread. */
	UFUNCTION(BlueprintCallable, Category = "muse|Observatory")
	void FetchSnapshot();

	/** GET /v1/observatory/metrics?window=<Window>[&task_class=<TaskClass>]
	 *  (spec §3.3). Window ∈ {15m, 1h, 24h, 7d}; empty => the gateway
	 *  default (1h). TaskClass is an optional filter; empty => no filter.
	 *  Broadcasts OnMetrics on the game thread. */
	UFUNCTION(BlueprintCallable, Category = "muse|Observatory")
	void FetchMetrics(const FString& Window = TEXT("1h"), const FString& TaskClass = TEXT(""));

	/** GET /v1/observatory/layout?cluster=<ClusterId>[&limit=<Limit>] —
	 *  on-demand cluster expansion for the galaxy LOD (spec §3.4; the §8
	 *  budget allows <= 3 expanded clusters, <= 2000 instances total).
	 *  Limit <= 0 omits the param (gateway default 500, server cap 2000).
	 *  Broadcasts OnLayout on the game thread; a stale id 404s => bOk=false. */
	UFUNCTION(BlueprintCallable, Category = "muse|Observatory")
	void FetchLayout(const FString& ClusterId, int32 Limit = 0);

	/** GET /v1/observatory/recommendations — verdict cards (spec §6).
	 *  Broadcasts OnRecommendations on the game thread. */
	UFUNCTION(BlueprintCallable, Category = "muse|Observatory")
	void FetchRecommendations();

	/** Subscribe to GET /v1/observatory/stream via UmuseSseClient.
	 *  Idempotent: a second call restarts the stream. Reconnect/backoff is
	 *  the SSE client's policy (1s -> … -> 30s cap). NOTE: the Prompt 0 SSE
	 *  client does not yet resume via Last-Event-ID — after a reconnect,
	 *  treat state as suspect and refetch the snapshot (the gap is
	 *  documented in docs/observatory-module.md, not papered over). */
	UFUNCTION(BlueprintCallable, Category = "muse|Observatory")
	void StartStream();

	/** Stop the stream (cancels the request and pending reconnects). */
	UFUNCTION(BlueprintCallable, Category = "muse|Observatory")
	void StopStream();

	/** True between StartStream() and StopStream(). */
	UFUNCTION(BlueprintPure, Category = "muse|Observatory")
	bool IsStreaming() const;

	/** Snapshot results. Game thread. */
	UPROPERTY(BlueprintAssignable, Category = "muse|Observatory")
	FOnObsSnapshot OnSnapshot;

	/** Metrics results. Game thread. */
	UPROPERTY(BlueprintAssignable, Category = "muse|Observatory")
	FOnObsMetrics OnMetrics;

	/** Layout-expansion results. Game thread. */
	UPROPERTY(BlueprintAssignable, Category = "muse|Observatory")
	FOnObsLayout OnLayout;

	/** Recommendation cards. Game thread. */
	UPROPERTY(BlueprintAssignable, Category = "muse|Observatory")
	FOnObsRecommendations OnRecommendations;

	/** Stream: job.stage events. Game thread. */
	UPROPERTY(BlueprintAssignable, Category = "muse|Observatory")
	FOnObsJobStage OnJobStage;

	/** Stream: gate.verdict events. Game thread. */
	UPROPERTY(BlueprintAssignable, Category = "muse|Observatory")
	FOnObsGateVerdict OnGateVerdict;

	/** Stream: node.activate events. Game thread. */
	UPROPERTY(BlueprintAssignable, Category = "muse|Observatory")
	FOnObsNodeActivate OnNodeActivate;

	/** Stream: route.decision events. Game thread. */
	UPROPERTY(BlueprintAssignable, Category = "muse|Observatory")
	FOnObsRouteDecision OnRouteDecision;

	/** Stream: resync — refetch the snapshot now. Game thread. */
	UPROPERTY(BlueprintAssignable, Category = "muse|Observatory")
	FOnObsResyncRequired OnResyncRequired;

	/** Stream: every frame, raw (additive-unknown types included). Game thread. */
	UPROPERTY(BlueprintAssignable, Category = "muse|Observatory")
	FOnObsStreamEvent OnStreamEvent;

private:
	/** SSE frame sink — bound to UmuseSseClient::OnSseEvent, which always
	 *  broadcasts on the game thread. */
	UFUNCTION()
	void HandleSseEvent(const FString& EventType, const FString& Data);

	/** The gateway client subsystem (SynapseNet owns URL + token handling). */
	class UmuseGatewayClient* ResolveGatewayClient() const;

	/** Issue an authorized GET via UmuseGatewayClient and invoke OnComplete
	 *  with (WeakThis, HttpCode, Body) on the HTTP WORKER thread — callers
	 *  parse there and marshal only the finished struct to the game thread. */
	void IssueGet(
		const FString& Path,
		TFunction<void(TWeakObjectPtr<UObservatorySubsystem>, int32, const FString&)> OnCompleteWorkerThread);

	/** The /v1/observatory/stream consumer (created on first StartStream). */
	UPROPERTY()
	TObjectPtr<UmuseSseClient> SseClient;
};
