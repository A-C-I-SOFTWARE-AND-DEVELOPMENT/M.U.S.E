// UObservatorySubsystem implementation.
// Copyright A-C-I Software & Development. All rights reserved.

#include "ObservatorySubsystem.h"

#include "Async/Async.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/GameInstance.h"
#include "GenericPlatform/GenericPlatformHttp.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "museGatewayClient.h"
#include "museSseClient.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SynapseObservatory.h"

namespace
{
	// -- small tolerant JSON helpers ------------------------------------------
	// All of these treat "missing", "null", and "wrong type" identically:
	// the bHas* flag stays false and the value stays at its default. Unknown
	// ADDITIVE fields are simply never read (spec §3 versioning rule).

	TSharedPtr<FJsonObject> ParseJsonObject(const FString& Body)
	{
		TSharedPtr<FJsonObject> Json;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Body);
		if (FJsonSerializer::Deserialize(Reader, Json) && Json.IsValid())
		{
			return Json;
		}
		return nullptr;
	}

	FString GetStringOr(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, const TCHAR* Default = TEXT(""))
	{
		FString Out;
		if (Obj.IsValid() && Obj->TryGetStringField(Field, Out))
		{
			return Out;
		}
		return Default;
	}

	void SetOptionalString(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, bool& bHas, FString& Value)
	{
		FString Out;
		bHas = Obj.IsValid() && Obj->TryGetStringField(Field, Out);
		Value = bHas ? Out : FString();
	}

	int32 GetIntOr(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, int32 Default = 0)
	{
		int32 Out = Default;
		if (Obj.IsValid() && Obj->TryGetNumberField(Field, Out))
		{
			return Out;
		}
		return Default;
	}

	float GetFloatOr(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, float Default = 0.0f)
	{
		double Out = 0.0;
		if (Obj.IsValid() && Obj->TryGetNumberField(Field, Out))
		{
			return static_cast<float>(Out);
		}
		return Default;
	}

	void SetOptionalFloat(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, bool& bHas, float& Value)
	{
		double Out = 0.0;
		bHas = Obj.IsValid() && Obj->TryGetNumberField(Field, Out);
		Value = bHas ? static_cast<float>(Out) : 0.0f;
	}

	void SetOptionalInt(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, bool& bHas, int32& Value)
	{
		int32 Out = 0;
		bHas = Obj.IsValid() && Obj->TryGetNumberField(Field, Out);
		Value = bHas ? Out : 0;
	}

	bool GetBoolOr(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, bool bDefault = false)
	{
		bool Out = bDefault;
		if (Obj.IsValid() && Obj->TryGetBoolField(Field, Out))
		{
			return Out;
		}
		return bDefault;
	}

	/** `pos` arrives as a 3-number array or null/absent (spec §3.1/§3.4). */
	void SetOptionalVec3(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, bool& bHas, FVector& Value)
	{
		bHas = false;
		Value = FVector::ZeroVector;
		const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
		if (Obj.IsValid() && Obj->TryGetArrayField(Field, Arr) && Arr != nullptr && Arr->Num() >= 3)
		{
			double X = 0.0, Y = 0.0, Z = 0.0;
			if ((*Arr)[0]->TryGetNumber(X) && (*Arr)[1]->TryGetNumber(Y) && (*Arr)[2]->TryGetNumber(Z))
			{
				Value = FVector(X, Y, Z);
				bHas = true;
			}
		}
	}

	void ParseFloatMap(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, TMap<FString, float>& Out)
	{
		Out.Reset();
		const TSharedPtr<FJsonObject>* MapObj = nullptr;
		if (!Obj.IsValid() || !Obj->TryGetObjectField(Field, MapObj) || MapObj == nullptr || !MapObj->IsValid())
		{
			return;
		}
		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*MapObj)->Values)
		{
			double Num = 0.0;
			if (Pair.Value.IsValid() && Pair.Value->TryGetNumber(Num))
			{
				Out.Add(Pair.Key, static_cast<float>(Num));
			}
		}
	}

	void ParseStringArray(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, TArray<FString>& Out)
	{
		Out.Reset();
		const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
		if (!Obj.IsValid() || !Obj->TryGetArrayField(Field, Arr) || Arr == nullptr)
		{
			return;
		}
		for (const TSharedPtr<FJsonValue>& Value : *Arr)
		{
			FString Item;
			if (Value.IsValid() && Value->TryGetString(Item))
			{
				Out.Add(MoveTemp(Item));
			}
		}
	}

	/** Iterate an array-of-objects field, invoking Fn per element object. */
	template <typename FnType>
	void ForEachObject(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, FnType Fn)
	{
		const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
		if (!Obj.IsValid() || !Obj->TryGetArrayField(Field, Arr) || Arr == nullptr)
		{
			return;
		}
		for (const TSharedPtr<FJsonValue>& Value : *Arr)
		{
			const TSharedPtr<FJsonObject>* Element = nullptr;
			if (Value.IsValid() && Value->TryGetObject(Element) && Element != nullptr && Element->IsValid())
			{
				Fn(*Element);
			}
		}
	}

	// -- /v1/observatory/* shape parsers (field names mirror
	// gateway/cockpit/handlers_observatory.py + observatory_metrics.py) ------

	FObsCluster ParseCluster(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsCluster Out;
		Out.Id = GetStringOr(Obj, TEXT("id"));
		Out.Label = GetStringOr(Obj, TEXT("label"));
		ParseFloatMap(Obj, TEXT("type_mix"), Out.TypeMix);
		Out.Members = GetIntOr(Obj, TEXT("members"));
		SetOptionalVec3(Obj, TEXT("pos"), Out.bHasPos, Out.Pos);
		Out.Radius = GetFloatOr(Obj, TEXT("radius"));
		SetOptionalFloat(Obj, TEXT("heat"), Out.bHasHeat, Out.Heat);
		return Out;
	}

	FObsClusterEdge ParseClusterEdge(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsClusterEdge Out;
		Out.A = GetStringOr(Obj, TEXT("a"));
		Out.B = GetStringOr(Obj, TEXT("b"));
		Out.Weight = GetFloatOr(Obj, TEXT("weight"));
		SetOptionalFloat(Obj, TEXT("heat"), Out.bHasHeat, Out.Heat);
		return Out;
	}

	FObsStation ParseStation(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsStation Out;
		Out.JobId = GetStringOr(Obj, TEXT("job_id"));
		SetOptionalString(Obj, TEXT("task_class"), Out.bHasTaskClass, Out.TaskClass);
		Out.Stage = GetStringOr(Obj, TEXT("stage"));
		Out.StageEnteredAt = GetStringOr(Obj, TEXT("stage_entered_at"));
		SetOptionalInt(Obj, TEXT("queue_pos"), Out.bHasQueuePos, Out.QueuePos);
		return Out;
	}

	FObsLadderTier ParseLadderTier(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsLadderTier Out;
		Out.Tier = GetStringOr(Obj, TEXT("tier"));
		SetOptionalString(Obj, TEXT("model"), Out.bHasModel, Out.Model);
		SetOptionalFloat(Obj, TEXT("share_1h"), Out.bHasShare, Out.Share);
		Out.N = GetIntOr(Obj, TEXT("n"));
		SetOptionalFloat(Obj, TEXT("p50_latency_ms"), Out.bHasP50LatencyMs, Out.P50LatencyMs);
		SetOptionalFloat(Obj, TEXT("p95_latency_ms"), Out.bHasP95LatencyMs, Out.P95LatencyMs);
		return Out;
	}

	FObsStageStat ParseStageStat(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsStageStat Out;
		Out.Stage = GetStringOr(Obj, TEXT("stage"));
		SetOptionalString(Obj, TEXT("task_class"), Out.bHasTaskClass, Out.TaskClass);
		Out.Count = GetIntOr(Obj, TEXT("count"));
		SetOptionalFloat(Obj, TEXT("p50_ms"), Out.bHasP50Ms, Out.P50Ms);
		SetOptionalFloat(Obj, TEXT("p95_ms"), Out.bHasP95Ms, Out.P95Ms);
		SetOptionalFloat(Obj, TEXT("queue_wait_p95_ms"), Out.bHasQueueWaitP95Ms, Out.QueueWaitP95Ms);
		Out.Retries = GetIntOr(Obj, TEXT("retries"));
		return Out;
	}

	FObsGateStat ParseGateStat(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsGateStat Out;
		Out.Gate = GetStringOr(Obj, TEXT("gate"));
		SetOptionalString(Obj, TEXT("task_class"), Out.bHasTaskClass, Out.TaskClass);
		Out.Passes = GetIntOr(Obj, TEXT("passes"));
		Out.Fails = GetIntOr(Obj, TEXT("fails"));
		Out.Overrides = GetIntOr(Obj, TEXT("overrides"));
		SetOptionalFloat(Obj, TEXT("fail_rate"), Out.bHasFailRate, Out.FailRate);
		return Out;
	}

	FObsModelStat ParseModelStat(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsModelStat Out;
		Out.Tier = GetStringOr(Obj, TEXT("tier"));
		Out.Model = GetStringOr(Obj, TEXT("model"));
		Out.Calls = GetIntOr(Obj, TEXT("calls"));
		SetOptionalFloat(Obj, TEXT("p95_latency_ms"), Out.bHasP95LatencyMs, Out.P95LatencyMs);
		Out.TokensIn = GetIntOr(Obj, TEXT("tokens_in"));
		Out.TokensOut = GetIntOr(Obj, TEXT("tokens_out"));
		Out.EstCostUsd = GetFloatOr(Obj, TEXT("est_cost_usd"));
		return Out;
	}

	FObsCostEntry ParseCostEntry(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsCostEntry Out;
		Out.TaskClass = GetStringOr(Obj, TEXT("task_class"));
		Out.Usd = GetFloatOr(Obj, TEXT("usd"));
		Out.N = GetIntOr(Obj, TEXT("n"));
		return Out;
	}

	FObsHeatEntry ParseHeatEntry(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsHeatEntry Out;
		Out.Key = GetStringOr(Obj, TEXT("key"));
		SetOptionalFloat(Obj, TEXT("score"), Out.bHasScore, Out.Score);
		Out.N = GetIntOr(Obj, TEXT("n"));
		Out.EvidenceRef = GetStringOr(Obj, TEXT("evidence_ref"));
		return Out;
	}

	void ParseRollupObject(const TSharedPtr<FJsonObject>& Obj, FObsMetricsRollup& Out)
	{
		Out.V = GetIntOr(Obj, TEXT("v"));
		Out.Window = GetStringOr(Obj, TEXT("window"));
		Out.FromIso = GetStringOr(Obj, TEXT("from"));
		Out.ToIso = GetStringOr(Obj, TEXT("to"));
		ForEachObject(Obj, TEXT("stages"), [&Out](const TSharedPtr<FJsonObject>& Row) { Out.Stages.Add(ParseStageStat(Row)); });
		ForEachObject(Obj, TEXT("gates"), [&Out](const TSharedPtr<FJsonObject>& Row) { Out.Gates.Add(ParseGateStat(Row)); });
		ForEachObject(Obj, TEXT("models"), [&Out](const TSharedPtr<FJsonObject>& Row) { Out.Models.Add(ParseModelStat(Row)); });
		ForEachObject(Obj, TEXT("cost_per_task_class"), [&Out](const TSharedPtr<FJsonObject>& Row) { Out.CostPerTaskClass.Add(ParseCostEntry(Row)); });
		ForEachObject(Obj, TEXT("heat"), [&Out](const TSharedPtr<FJsonObject>& Row) { Out.Heat.Add(ParseHeatEntry(Row)); });
		ParseFloatMap(Obj, TEXT("heat_weights"), Out.HeatWeights);
		Out.MinN = GetIntOr(Obj, TEXT("min_n"));
	}

	bool ParseSnapshot(const FString& Body, FObsSnapshot& Out)
	{
		const TSharedPtr<FJsonObject> Json = ParseJsonObject(Body);
		if (!Json.IsValid())
		{
			return false;
		}
		Out.V = GetIntOr(Json, TEXT("v"));
		Out.GeneratedAt = GetStringOr(Json, TEXT("generated_at"));

		const TSharedPtr<FJsonObject>* Graph = nullptr;
		if (Json->TryGetObjectField(TEXT("graph"), Graph) && Graph != nullptr && Graph->IsValid())
		{
			// The documented unavailable shape is {"status":"unavailable","reason":…}.
			Out.bGraphAvailable = GetStringOr(*Graph, TEXT("status")) != TEXT("unavailable");
			Out.GraphUnavailableReason = GetStringOr(*Graph, TEXT("reason"));
			Out.GraphVersion = GetStringOr(*Graph, TEXT("graph_version"));
			Out.NodeCount = GetIntOr(*Graph, TEXT("node_count"));
			Out.EdgeCount = GetIntOr(*Graph, TEXT("edge_count"));
			ForEachObject(*Graph, TEXT("clusters"), [&Out](const TSharedPtr<FJsonObject>& Row) { Out.Clusters.Add(ParseCluster(Row)); });
			ForEachObject(*Graph, TEXT("cluster_edges"), [&Out](const TSharedPtr<FJsonObject>& Row) { Out.ClusterEdges.Add(ParseClusterEdge(Row)); });
			Out.ClustersTotal = GetIntOr(*Graph, TEXT("clusters_total"));
			Out.bClustersTruncated = GetBoolOr(*Graph, TEXT("clusters_truncated"));
			Out.LayoutStatus = GetStringOr(*Graph, TEXT("layout_status"));
			Out.LayoutAlgo = GetStringOr(*Graph, TEXT("layout_algo"));
		}

		const TSharedPtr<FJsonObject>* Stations = nullptr;
		if (Json->TryGetObjectField(TEXT("stations"), Stations) && Stations != nullptr && Stations->IsValid())
		{
			ParseStringArray(*Stations, TEXT("nodes"), Out.StationNodes);
			ForEachObject(*Stations, TEXT("active_jobs"), [&Out](const TSharedPtr<FJsonObject>& Row) { Out.ActiveJobs.Add(ParseStation(Row)); });
			Out.QueueDepth = GetIntOr(*Stations, TEXT("queue_depth"));
		}

		const TSharedPtr<FJsonObject>* Ladder = nullptr;
		if (Json->TryGetObjectField(TEXT("ladder"), Ladder) && Ladder != nullptr && Ladder->IsValid())
		{
			ForEachObject(*Ladder, TEXT("tiers"), [&Out](const TSharedPtr<FJsonObject>& Row) { Out.LadderTiers.Add(ParseLadderTier(Row)); });
		}

		const TSharedPtr<FJsonObject>* Rollup = nullptr;
		if (Json->TryGetObjectField(TEXT("metrics_rollup"), Rollup) && Rollup != nullptr && Rollup->IsValid())
		{
			ParseRollupObject(*Rollup, Out.MetricsRollup);
		}
		return true;
	}

	bool ParseMetrics(const FString& Body, FObsMetricsRollup& Out)
	{
		const TSharedPtr<FJsonObject> Json = ParseJsonObject(Body);
		if (!Json.IsValid())
		{
			return false;
		}
		ParseRollupObject(Json, Out);
		return true;
	}

	bool ParseLayout(const FString& Body, FObsClusterLayout& Out)
	{
		const TSharedPtr<FJsonObject> Json = ParseJsonObject(Body);
		if (!Json.IsValid())
		{
			return false;
		}
		Out.V = GetIntOr(Json, TEXT("v"));
		Out.Cluster = GetStringOr(Json, TEXT("cluster"));
		Out.bGraphAvailable = GetStringOr(Json, TEXT("status")) != TEXT("unavailable");
		Out.UnavailableReason = GetStringOr(Json, TEXT("reason"));
		Out.GraphVersion = GetStringOr(Json, TEXT("graph_version"));
		Out.LayoutStatus = GetStringOr(Json, TEXT("layout_status"));
		Out.LayoutAlgo = GetStringOr(Json, TEXT("layout_algo"));
		Out.bTruncated = GetBoolOr(Json, TEXT("truncated"));
		ForEachObject(Json, TEXT("nodes"), [&Out](const TSharedPtr<FJsonObject>& Row)
		{
			FObsLayoutNode Node;
			Node.Id = GetStringOr(Row, TEXT("id"));
			Node.Type = GetStringOr(Row, TEXT("type"));
			Node.Label = GetStringOr(Row, TEXT("label"));
			SetOptionalVec3(Row, TEXT("pos"), Node.bHasPos, Node.Pos);
			Node.Degree = GetIntOr(Row, TEXT("degree"));
			SetOptionalFloat(Row, TEXT("heat"), Node.bHasHeat, Node.Heat);
			Node.SourceRef = GetStringOr(Row, TEXT("source_ref"));
			Out.Nodes.Add(MoveTemp(Node));
		});
		ForEachObject(Json, TEXT("edges"), [&Out](const TSharedPtr<FJsonObject>& Row) { Out.Edges.Add(ParseClusterEdge(Row)); });
		return true;
	}

	FObsValidation ParseValidation(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsValidation Out;
		Out.Method = GetStringOr(Obj, TEXT("method"));
		Out.NBaseline = GetIntOr(Obj, TEXT("n_baseline"));
		Out.NCandidate = GetIntOr(Obj, TEXT("n_candidate"));
		SetOptionalFloat(Obj, TEXT("median_delta_pct"), Out.bHasMedianDeltaPct, Out.MedianDeltaPct);
		const TArray<TSharedPtr<FJsonValue>>* Ci = nullptr;
		if (Obj.IsValid() && Obj->TryGetArrayField(TEXT("ci95"), Ci) && Ci != nullptr)
		{
			for (const TSharedPtr<FJsonValue>& Bound : *Ci)
			{
				double Num = 0.0;
				if (Bound.IsValid() && Bound->TryGetNumber(Num))
				{
					Out.Ci95.Add(static_cast<float>(Num));
				}
			}
			Out.bHasCi95 = Out.Ci95.Num() >= 2;
			if (!Out.bHasCi95)
			{
				Out.Ci95.Reset(); // Never expose a half-parsed interval.
			}
		}
		Out.Metric = GetStringOr(Obj, TEXT("metric"));
		return Out;
	}

	bool ParseRecommendations(const FString& Body, FObsRecommendations& Out)
	{
		const TSharedPtr<FJsonObject> Json = ParseJsonObject(Body);
		if (!Json.IsValid())
		{
			return false;
		}
		Out.V = GetIntOr(Json, TEXT("v"));
		Out.GeneratedAt = GetStringOr(Json, TEXT("generated_at"));
		ForEachObject(Json, TEXT("cards"), [&Out](const TSharedPtr<FJsonObject>& Row)
		{
			FObsRecommendationCard Card;
			Card.Id = GetStringOr(Row, TEXT("id"));
			Card.Title = GetStringOr(Row, TEXT("title"));
			Card.State = GetStringOr(Row, TEXT("state"));
			// `delta` is a measured human-readable string when validated,
			// null while collecting (spec §6); tolerate a bare number too.
			if (const TSharedPtr<FJsonValue> Delta = Row->TryGetField(TEXT("delta")))
			{
				FString AsString;
				double AsNumber = 0.0;
				if (Delta->TryGetString(AsString))
				{
					Card.bHasDelta = true;
					Card.Delta = AsString;
				}
				else if (Delta->TryGetNumber(AsNumber))
				{
					Card.bHasDelta = true;
					Card.Delta = FString::SanitizeFloat(AsNumber);
				}
			}
			const TSharedPtr<FJsonObject>* Validation = nullptr;
			if (Row->TryGetObjectField(TEXT("validation"), Validation) && Validation != nullptr && Validation->IsValid())
			{
				Card.Validation = ParseValidation(*Validation);
			}
			ParseStringArray(Row, TEXT("evidence_refs"), Card.EvidenceRefs);
			Card.CreatedAt = GetStringOr(Row, TEXT("created_at"));
			Out.Cards.Add(MoveTemp(Card));
		});
		return true;
	}

	// -- SSE payload parsers (spec §3.2 schemas) -------------------------------

	FObsJobStage ParseJobStagePayload(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsJobStage Out;
		Out.JobId = GetStringOr(Obj, TEXT("job_id"));
		Out.TaskClass = GetStringOr(Obj, TEXT("task_class"));
		Out.Stage = GetStringOr(Obj, TEXT("stage"));
		Out.QueueDepth = GetIntOr(Obj, TEXT("queue_depth"));
		SetOptionalFloat(Obj, TEXT("stage_latency_ms"), Out.bHasStageLatencyMs, Out.StageLatencyMs);
		Out.Ts = GetStringOr(Obj, TEXT("ts"));
		return Out;
	}

	FObsGateVerdict ParseGateVerdictPayload(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsGateVerdict Out;
		Out.JobId = GetStringOr(Obj, TEXT("job_id"));
		Out.Gate = GetStringOr(Obj, TEXT("gate"));
		Out.Verdict = GetStringOr(Obj, TEXT("verdict"));
		Out.Attempt = GetIntOr(Obj, TEXT("attempt"));
		Out.DetailRef = GetStringOr(Obj, TEXT("detail_ref"));
		Out.Ts = GetStringOr(Obj, TEXT("ts"));
		return Out;
	}

	FObsNodeActivate ParseNodeActivatePayload(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsNodeActivate Out;
		Out.ClusterId = GetStringOr(Obj, TEXT("cluster_id"));
		SetOptionalString(Obj, TEXT("node_id"), Out.bHasNodeId, Out.NodeId);
		Out.Kind = GetStringOr(Obj, TEXT("kind"));
		Out.Weight = GetFloatOr(Obj, TEXT("weight"));
		Out.Ts = GetStringOr(Obj, TEXT("ts"));
		return Out;
	}

	FObsRouteDecision ParseRouteDecisionPayload(const TSharedPtr<FJsonObject>& Obj)
	{
		FObsRouteDecision Out;
		Out.TurnId = GetStringOr(Obj, TEXT("turn_id"));
		Out.Tier = GetStringOr(Obj, TEXT("tier"));
		Out.Model = GetStringOr(Obj, TEXT("model"));
		Out.Reason = GetStringOr(Obj, TEXT("reason"));
		Out.LatencyMs = GetFloatOr(Obj, TEXT("latency_ms"));
		Out.TokensIn = GetIntOr(Obj, TEXT("tokens_in"));
		Out.TokensOut = GetIntOr(Obj, TEXT("tokens_out"));
		Out.Ts = GetStringOr(Obj, TEXT("ts"));
		return Out;
	}
}

void UObservatorySubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	// The gateway client is the network dependency — make sure it spins up
	// first so ResolveGatewayClient() never races subsystem creation.
	Collection.InitializeDependency(UmuseGatewayClient::StaticClass());

	UE_LOG(LogSynapseObservatory, Log, TEXT("ObservatorySubsystem ready (routes: /v1/observatory/{snapshot,metrics,layout,recommendations,stream})."));
}

void UObservatorySubsystem::Deinitialize()
{
	StopStream();
	OnSnapshot.Clear();
	OnMetrics.Clear();
	OnLayout.Clear();
	OnRecommendations.Clear();
	OnJobStage.Clear();
	OnGateVerdict.Clear();
	OnNodeActivate.Clear();
	OnRouteDecision.Clear();
	OnResyncRequired.Clear();
	OnStreamEvent.Clear();
	Super::Deinitialize();
}

UmuseGatewayClient* UObservatorySubsystem::ResolveGatewayClient() const
{
	UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UmuseGatewayClient>() : nullptr;
}

void UObservatorySubsystem::IssueGet(
	const FString& Path,
	TFunction<void(TWeakObjectPtr<UObservatorySubsystem>, int32, const FString&)> OnCompleteWorkerThread)
{
	UmuseGatewayClient* Gateway = ResolveGatewayClient();
	if (Gateway == nullptr)
	{
		UE_LOG(LogSynapseObservatory, Warning, TEXT("%s skipped — UmuseGatewayClient subsystem unavailable."), *Path);
		return;
	}

	// SynapseNet builds the request: base URL, timeout, and the bearer token
	// (read fresh from the token file, never duplicated or logged here).
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = Gateway->CreateAuthorizedGetRequest(Path);

	TWeakObjectPtr<UObservatorySubsystem> WeakThis(this);
	Request->OnProcessRequestComplete().BindLambda(
		[WeakThis, OnComplete = MoveTemp(OnCompleteWorkerThread)](FHttpRequestPtr /*Req*/, FHttpResponsePtr Response, bool bConnected)
		{
			// HTTP worker thread: hand the raw body to the route's parser —
			// the parse stays OFF the game thread (TDD §2.2, spec §8).
			const int32 Code = (bConnected && Response.IsValid()) ? Response->GetResponseCode() : 0;
			const FString Body = (bConnected && Response.IsValid()) ? Response->GetContentAsString() : FString();
			OnComplete(WeakThis, Code, Body);
		});

	Request->ProcessRequest();
}

void UObservatorySubsystem::FetchSnapshot()
{
	// Contract route: GET /v1/observatory/snapshot — bearer (spec §3.1).
	IssueGet(TEXT("/v1/observatory/snapshot"),
		[](TWeakObjectPtr<UObservatorySubsystem> WeakThis, int32 Code, const FString& Body)
		{
			FObsSnapshot Snapshot;
			const bool bOk = EHttpResponseCodes::IsOk(Code) && ParseSnapshot(Body, Snapshot);
			AsyncTask(ENamedThreads::GameThread, [WeakThis, bOk, Code, Snapshot = MoveTemp(Snapshot)]()
			{
				if (UObservatorySubsystem* Self = WeakThis.Get())
				{
					UE_LOG(LogSynapseObservatory, Log,
						TEXT("/v1/observatory/snapshot -> HTTP %d ok=%s (clusters=%d active_jobs=%d tiers=%d)"),
						Code, bOk ? TEXT("true") : TEXT("false"),
						Snapshot.Clusters.Num(), Snapshot.ActiveJobs.Num(), Snapshot.LadderTiers.Num());
					Self->OnSnapshot.Broadcast(bOk, Snapshot);
				}
			});
		});
}

void UObservatorySubsystem::FetchMetrics(const FString& Window, const FString& TaskClass)
{
	// Contract route: GET /v1/observatory/metrics?window= — bearer (spec §3.3).
	// Window validation is the gateway's job (400 bad_request); we pass through.
	FString Path = FString::Printf(TEXT("/v1/observatory/metrics?window=%s"),
		*FGenericPlatformHttp::UrlEncode(Window.IsEmpty() ? FString(TEXT("1h")) : Window));
	if (!TaskClass.IsEmpty())
	{
		Path += TEXT("&task_class=") + FGenericPlatformHttp::UrlEncode(TaskClass);
	}

	IssueGet(Path,
		[](TWeakObjectPtr<UObservatorySubsystem> WeakThis, int32 Code, const FString& Body)
		{
			FObsMetricsRollup Rollup;
			const bool bOk = EHttpResponseCodes::IsOk(Code) && ParseMetrics(Body, Rollup);
			AsyncTask(ENamedThreads::GameThread, [WeakThis, bOk, Code, Rollup = MoveTemp(Rollup)]()
			{
				if (UObservatorySubsystem* Self = WeakThis.Get())
				{
					UE_LOG(LogSynapseObservatory, Log,
						TEXT("/v1/observatory/metrics -> HTTP %d ok=%s (window=%s stages=%d heat_keys=%d)"),
						Code, bOk ? TEXT("true") : TEXT("false"),
						*Rollup.Window, Rollup.Stages.Num(), Rollup.Heat.Num());
					Self->OnMetrics.Broadcast(bOk, Rollup);
				}
			});
		});
}

void UObservatorySubsystem::FetchLayout(const FString& ClusterId, int32 Limit)
{
	if (ClusterId.IsEmpty())
	{
		// The gateway would 400 this anyway — fail fast, honestly, locally.
		UE_LOG(LogSynapseObservatory, Warning, TEXT("FetchLayout called with an empty cluster id — broadcasting failure."));
		OnLayout.Broadcast(false, FObsClusterLayout());
		return;
	}

	// Contract route: GET /v1/observatory/layout?cluster= — bearer (spec §3.4).
	FString Path = FString::Printf(TEXT("/v1/observatory/layout?cluster=%s"),
		*FGenericPlatformHttp::UrlEncode(ClusterId));
	if (Limit > 0)
	{
		Path += FString::Printf(TEXT("&limit=%d"), Limit);
	}

	IssueGet(Path,
		[](TWeakObjectPtr<UObservatorySubsystem> WeakThis, int32 Code, const FString& Body)
		{
			FObsClusterLayout Layout;
			const bool bOk = EHttpResponseCodes::IsOk(Code) && ParseLayout(Body, Layout);
			AsyncTask(ENamedThreads::GameThread, [WeakThis, bOk, Code, Layout = MoveTemp(Layout)]()
			{
				if (UObservatorySubsystem* Self = WeakThis.Get())
				{
					// 404 = stale cluster id after a graph rebuild — the
					// graph_version mismatch is the tell; refetch the snapshot.
					UE_LOG(LogSynapseObservatory, Log,
						TEXT("/v1/observatory/layout -> HTTP %d ok=%s (cluster=%s nodes=%d truncated=%s)"),
						Code, bOk ? TEXT("true") : TEXT("false"),
						*Layout.Cluster, Layout.Nodes.Num(), Layout.bTruncated ? TEXT("true") : TEXT("false"));
					Self->OnLayout.Broadcast(bOk, Layout);
				}
			});
		});
}

void UObservatorySubsystem::FetchRecommendations()
{
	// Contract route: GET /v1/observatory/recommendations — bearer (spec §6).
	IssueGet(TEXT("/v1/observatory/recommendations"),
		[](TWeakObjectPtr<UObservatorySubsystem> WeakThis, int32 Code, const FString& Body)
		{
			FObsRecommendations Recommendations;
			const bool bOk = EHttpResponseCodes::IsOk(Code) && ParseRecommendations(Body, Recommendations);
			AsyncTask(ENamedThreads::GameThread, [WeakThis, bOk, Code, Recommendations = MoveTemp(Recommendations)]()
			{
				if (UObservatorySubsystem* Self = WeakThis.Get())
				{
					UE_LOG(LogSynapseObservatory, Log,
						TEXT("/v1/observatory/recommendations -> HTTP %d ok=%s (cards=%d)"),
						Code, bOk ? TEXT("true") : TEXT("false"), Recommendations.Cards.Num());
					Self->OnRecommendations.Broadcast(bOk, Recommendations);
				}
			});
		});
}

void UObservatorySubsystem::StartStream()
{
	check(IsInGameThread());

	if (SseClient == nullptr)
	{
		SseClient = NewObject<UmuseSseClient>(this);
		SseClient->OnSseEvent.AddDynamic(this, &UObservatorySubsystem::HandleSseEvent);
	}

	// Contract route: GET /v1/observatory/stream — bearer, SSE (spec §3.2).
	// Reconnect/backoff is UmuseSseClient policy. Last-Event-ID resume is a
	// DOCUMENTED GAP of the Prompt 0 SSE client (docs/observatory-module.md):
	// after a reconnect, listeners should treat state as suspect and call
	// FetchSnapshot() — the gateway's `resync` event also forces this.
	SseClient->Start(TEXT("/v1/observatory/stream"));

	UE_LOG(LogSynapseObservatory, Log, TEXT("Observatory stream starting: /v1/observatory/stream"));
}

void UObservatorySubsystem::StopStream()
{
	if (SseClient != nullptr)
	{
		SseClient->Stop();
	}
}

bool UObservatorySubsystem::IsStreaming() const
{
	return SseClient != nullptr && SseClient->IsStreaming();
}

void UObservatorySubsystem::HandleSseEvent(const FString& EventType, const FString& Data)
{
	// UmuseSseClient broadcasts on the game thread only (its contract).
	check(IsInGameThread());

	// Stream payloads are small per-event deltas (gateway coalesces
	// node.activate to <= 10/s, spec §3.2) — parsed inline here; the heavy
	// documents (snapshot/metrics/layout) parse on worker threads instead.
	const TSharedPtr<FJsonObject> Payload = ParseJsonObject(Data);

	// Raw tap first: every frame is observable, including event types this
	// client build does not know yet (additive tolerance, spec §3 versioning).
	FObsStreamEvent Raw;
	Raw.Type = EventType;
	Raw.PayloadJson = Data;
	Raw.Ts = Payload.IsValid() ? GetStringOr(Payload, TEXT("ts")) : FString();
	OnStreamEvent.Broadcast(Raw);

	if (!Payload.IsValid())
	{
		UE_LOG(LogSynapseObservatory, Verbose, TEXT("Stream frame '%s' carried a non-JSON payload (%d chars) — raw broadcast only."), *EventType, Data.Len());
		return;
	}

	if (EventType == TEXT("job.stage"))
	{
		OnJobStage.Broadcast(ParseJobStagePayload(Payload));
	}
	else if (EventType == TEXT("gate.verdict"))
	{
		OnGateVerdict.Broadcast(ParseGateVerdictPayload(Payload));
	}
	else if (EventType == TEXT("node.activate"))
	{
		OnNodeActivate.Broadcast(ParseNodeActivatePayload(Payload));
	}
	else if (EventType == TEXT("route.decision"))
	{
		OnRouteDecision.Broadcast(ParseRouteDecisionPayload(Payload));
	}
	else if (EventType == TEXT("resync"))
	{
		// reason ∈ {gap, graph_rebuilt} (spec §3.2): our event view is stale.
		const FString Reason = GetStringOr(Payload, TEXT("reason"), TEXT("unspecified"));
		UE_LOG(LogSynapseObservatory, Log, TEXT("Observatory stream resync (reason=%s) — snapshot refetch required."), *Reason);
		OnResyncRequired.Broadcast(Reason);
	}
	// Unknown event types: the raw broadcast above is the whole contract.
}
