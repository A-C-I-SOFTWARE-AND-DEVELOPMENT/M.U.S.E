#include "MuseUniverseSubsystem.h"

#include "Async/Async.h"
#include "Dom/JsonObject.h"
#include "GenericPlatform/GenericPlatformHttp.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "MuseGatewayClient.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SynapseUniverse.h"

namespace
{
	constexpr int32 SupportedSchemaMajor = 1;
	constexpr double MaximumPollBackoffSeconds = 30.0;

	FString SerializeObject(const TSharedPtr<FJsonObject>& Object)
	{
		if (!Object.IsValid())
		{
			return TEXT("{}");
		}
		FString Encoded;
		const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Encoded);
		FJsonSerializer::Serialize(Object.ToSharedRef(), Writer);
		return Encoded;
	}

	FString StringField(const TSharedPtr<FJsonObject>& Object, const TCHAR* Name)
	{
		FString Value;
		if (Object.IsValid())
		{
			Object->TryGetStringField(Name, Value);
		}
		return Value;
	}

	int64 IntegerField(
		const TSharedPtr<FJsonObject>& Object,
		const TCHAR* Name,
		const int64 DefaultValue = 0)
	{
		double Number = static_cast<double>(DefaultValue);
		if (Object.IsValid() && Object->TryGetNumberField(Name, Number))
		{
			return static_cast<int64>(Number);
		}
		return DefaultValue;
	}

	bool BoolField(
		const TSharedPtr<FJsonObject>& Object,
		const TCHAR* Name,
		const bool DefaultValue = false)
	{
		bool Value = DefaultValue;
		if (Object.IsValid())
		{
			Object->TryGetBoolField(Name, Value);
		}
		return Value;
	}

	void ReadStringArray(
		const TSharedPtr<FJsonObject>& Object,
		const TCHAR* Name,
		TArray<FString>& Out)
	{
		Out.Reset();
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (!Object.IsValid() || !Object->TryGetArrayField(Name, Values) || Values == nullptr)
		{
			return;
		}
		for (const TSharedPtr<FJsonValue>& Value : *Values)
		{
			FString Text;
			if (Value.IsValid() && Value->TryGetString(Text))
			{
				Out.Add(Text);
			}
		}
	}
}

void UMuseUniverseSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	Collection.InitializeDependency<UmuseGatewayClient>();
	GatewayClient = GetGameInstance()->GetSubsystem<UmuseGatewayClient>();
	SetConnectionState(
		GatewayClient.IsValid()
			? EMuseUniverseConnectionState::Disconnected
			: EMuseUniverseConnectionState::Degraded,
		GatewayClient.IsValid() ? TEXT("ready") : TEXT("SynapseNet unavailable"));
}

void UMuseUniverseSubsystem::Deinitialize()
{
	Disconnect();
	OnUniverseEvent.Clear();
	OnConnectionChanged.Clear();
	OnConflict.Clear();
	GatewayClient.Reset();
	Super::Deinitialize();
}

void UMuseUniverseSubsystem::Connect(
	const FString& RealmId,
	const FString& ActorId)
{
	if (!GatewayClient.IsValid() || RealmId.TrimStartAndEnd().IsEmpty() ||
		ActorId.TrimStartAndEnd().IsEmpty())
	{
		SetConnectionState(
			EMuseUniverseConnectionState::Degraded,
			TEXT("gateway client, realm id, and authoritative actor id are required"));
		return;
	}
	Disconnect();
	ActiveRealmId = RealmId.TrimStartAndEnd();
	ActiveActorId = ActorId.TrimStartAndEnd();
	LastAcknowledgedCursor = 0;
	LastRealmVersion = 0;
	PollBackoffSeconds = 1.0;
	bReplayingSnapshotHistory = true;
	ProjectionVersions.Reset();
	ProjectionJsonByKey.Reset();
	Conflicts.Reset();
	SetConnectionState(
		EMuseUniverseConnectionState::LoadingSnapshot,
		TEXT("loading authoritative snapshot"));
	FetchSnapshot();
}

void UMuseUniverseSubsystem::Disconnect()
{
	++ConnectionGeneration;
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(PollTimer);
	}
	bRequestInFlight = false;
	bResyncInFlight = false;
	bReplayingSnapshotHistory = false;
	ActiveRealmId.Reset();
	ActiveActorId.Reset();
	LastRealmVersion = 0;
	SetConnectionState(
		EMuseUniverseConnectionState::Disconnected,
		TEXT("disconnected"));
}

void UMuseUniverseSubsystem::SetConnectionState(
	const EMuseUniverseConnectionState NewState,
	const FString& Reason)
{
	ConnectionState = NewState;
	OnConnectionChanged.Broadcast(ConnectionState, Reason);
}

void UMuseUniverseSubsystem::FetchSnapshot()
{
	if (bRequestInFlight || !GatewayClient.IsValid() ||
		ActiveRealmId.IsEmpty() || ActiveActorId.IsEmpty())
	{
		return;
	}
	bRequestInFlight = true;
	const uint64 RequestGeneration = ConnectionGeneration;
	const FString Path = FString::Printf(
		TEXT("/v1/plugins/muse-universe/snapshot?realm_id=%s&actor_id=%s"),
		*FGenericPlatformHttp::UrlEncode(ActiveRealmId),
		*FGenericPlatformHttp::UrlEncode(ActiveActorId));
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request =
		GatewayClient->CreateAuthorizedJsonRequest(Path, TEXT("GET"));
	// Authorization is added inside SynapseNet. This module never reads,
	// serializes, retains, or logs the bearer value.
	Request->OnProcessRequestComplete().BindLambda(
		[WeakThis = TWeakObjectPtr<UMuseUniverseSubsystem>(this), RequestGeneration](
			FHttpRequestPtr /*RequestPtr*/,
			FHttpResponsePtr Response,
			bool bConnected)
		{
			const int32 Code = bConnected && Response.IsValid()
				? Response->GetResponseCode() : 0;
			const FString Body = bConnected && Response.IsValid()
				? Response->GetContentAsString() : FString();
			AsyncTask(ENamedThreads::GameThread, [WeakThis, RequestGeneration, Code, Body]()
			{
				UMuseUniverseSubsystem* Self = WeakThis.Get();
				if (!Self || Self->ConnectionGeneration != RequestGeneration)
				{
					return;
				}
				Self->bRequestInFlight = false;
				Self->bResyncInFlight = false;
				FString Error;
				if (EHttpResponseCodes::IsOk(Code) && Self->ParseSnapshotJson(Body, Error))
				{
					Self->PollBackoffSeconds = 1.0;
					Self->SetConnectionState(
						EMuseUniverseConnectionState::Polling,
						TEXT("snapshot synchronized"));
					Self->ScheduleEventPoll(true);
				}
				else
				{
					if (Self->ConnectionState ==
						EMuseUniverseConnectionState::SchemaRejected)
					{
						return;
					}
					Self->SetConnectionState(
						EMuseUniverseConnectionState::Degraded,
						Error.IsEmpty()
							? FString::Printf(TEXT("snapshot HTTP %d"), Code)
							: Error);
					Self->ScheduleSnapshotRetry();
				}
			});
		});
	Request->ProcessRequest();
}

void UMuseUniverseSubsystem::FetchEvents()
{
	if (bRequestInFlight || !GatewayClient.IsValid() || ActiveRealmId.IsEmpty())
	{
		return;
	}
	bRequestInFlight = true;
	const uint64 RequestGeneration = ConnectionGeneration;
	const FString Path = FString::Printf(
		TEXT("/v1/plugins/muse-universe/events?realm_id=%s&since=%lld&limit=256"),
		*FGenericPlatformHttp::UrlEncode(ActiveRealmId),
		LastAcknowledgedCursor);
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request =
		GatewayClient->CreateAuthorizedJsonRequest(Path, TEXT("GET"));
	Request->OnProcessRequestComplete().BindLambda(
		[WeakThis = TWeakObjectPtr<UMuseUniverseSubsystem>(this), RequestGeneration](
			FHttpRequestPtr /*RequestPtr*/,
			FHttpResponsePtr Response,
			bool bConnected)
		{
			const int32 Code = bConnected && Response.IsValid()
				? Response->GetResponseCode() : 0;
			const FString Body = bConnected && Response.IsValid()
				? Response->GetContentAsString() : FString();
			AsyncTask(ENamedThreads::GameThread, [WeakThis, RequestGeneration, Code, Body]()
			{
				UMuseUniverseSubsystem* Self = WeakThis.Get();
				if (!Self || Self->ConnectionGeneration != RequestGeneration)
				{
					return;
				}
				Self->bRequestInFlight = false;
				FString Error;
				const bool bOk = EHttpResponseCodes::IsOk(Code) &&
					Self->ParseEventPageJson(Body, Error);
				if (!bOk && Error.Contains(TEXT("cursor gap")))
				{
					Self->LastAcknowledgedCursor = 0;
					Self->LastRealmVersion = 0;
					Self->bReplayingSnapshotHistory = true;
					Self->RequestResync(Error);
					return;
				}
				if (!bOk && Self->ConnectionState ==
					EMuseUniverseConnectionState::SchemaRejected)
				{
					return;
				}
				Self->SetConnectionState(
					bOk ? EMuseUniverseConnectionState::Polling
						: EMuseUniverseConnectionState::Degraded,
					bOk ? TEXT("event cursor acknowledged")
						: (Error.IsEmpty()
							? FString::Printf(TEXT("events HTTP %d"), Code)
							: Error));
				Self->ScheduleEventPoll(bOk);
			});
		});
	Request->ProcessRequest();
}

void UMuseUniverseSubsystem::ScheduleSnapshotRetry()
{
	UWorld* World = GetWorld();
	if (!World || ActiveRealmId.IsEmpty() || ActiveActorId.IsEmpty())
	{
		return;
	}
	PollBackoffSeconds = FMath::Min(
		MaximumPollBackoffSeconds,
		FMath::Max(1.0, PollBackoffSeconds * 2.0));
	const double Jitter = FMath::FRandRange(0.0, PollBackoffSeconds * 0.2);
	World->GetTimerManager().SetTimer(
		PollTimer,
		this,
		&UMuseUniverseSubsystem::FetchSnapshot,
		static_cast<float>(PollBackoffSeconds + Jitter),
		false);
}

void UMuseUniverseSubsystem::ScheduleEventPoll(
	const bool bPreviousRequestSucceeded)
{
	UWorld* World = GetWorld();
	if (!World || ActiveRealmId.IsEmpty())
	{
		return;
	}
	if (bPreviousRequestSucceeded)
	{
		PollBackoffSeconds = 1.0;
	}
	else
	{
		PollBackoffSeconds = FMath::Min(
			MaximumPollBackoffSeconds,
			FMath::Max(1.0, PollBackoffSeconds * 2.0));
	}
	const double Jitter = FMath::FRandRange(0.0, PollBackoffSeconds * 0.2);
	World->GetTimerManager().SetTimer(
		PollTimer,
		this,
		&UMuseUniverseSubsystem::FetchEvents,
		static_cast<float>(PollBackoffSeconds + Jitter),
		false);
}

bool UMuseUniverseSubsystem::ParseSnapshotJson(
	const FString& Body,
	FString& OutError)
{
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Body);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		OutError = TEXT("snapshot is not valid JSON");
		return false;
	}
	const int64 SchemaVersion = IntegerField(Root, TEXT("schema_version"), 1);
	if (SchemaVersion != SupportedSchemaMajor)
	{
		OutError = FString::Printf(
			TEXT("unsupported universe schema major %lld"), SchemaVersion);
		SetConnectionState(EMuseUniverseConnectionState::SchemaRejected, OutError);
		return false;
	}

	const TSharedPtr<FJsonObject>* SnapshotObject = nullptr;
	const TSharedPtr<FJsonObject> ProjectionRoot =
		Root->TryGetObjectField(TEXT("snapshot"), SnapshotObject) && SnapshotObject
			? *SnapshotObject : Root;
	if (!ProjectionRoot.IsValid())
	{
		OutError = TEXT("snapshot projection object is missing");
		return false;
	}

	ProjectionVersions.Reset();
	ProjectionJsonByKey.Reset();
	bReplayingSnapshotHistory = true;
	for (const TPair<FString, TSharedPtr<FJsonValue>>& Field : ProjectionRoot->Values)
	{
		const TArray<TSharedPtr<FJsonValue>>* Items = nullptr;
		if (!Field.Value.IsValid() || !Field.Value->TryGetArray(Items) || Items == nullptr)
		{
			continue;
		}
		FString FallbackType = Field.Key;
		if (FallbackType.EndsWith(TEXT("s")))
		{
			FallbackType.LeftChopInline(1);
		}
		for (const TSharedPtr<FJsonValue>& Item : *Items)
		{
			const TSharedPtr<FJsonObject>* ObjectPtr = nullptr;
			if (!Item.IsValid() || !Item->TryGetObject(ObjectPtr) || !ObjectPtr || !ObjectPtr->IsValid())
			{
				continue;
			}
			const TSharedPtr<FJsonObject> Object = *ObjectPtr;
			const FString Id = StringField(Object, TEXT("id"));
			FString EntityType = StringField(Object, TEXT("entity_type"));
			if (EntityType.IsEmpty())
			{
				EntityType = FallbackType;
			}
			const int64 Version = IntegerField(Object, TEXT("version"));
			if (!Id.IsEmpty() && Version >= 0)
			{
				ApplyOnlyIncreasingVersion(
					EntityType + TEXT(":") + Id,
					Version,
					SerializeObject(Object));
			}
		}
	}
	LastAcknowledgedCursor = IntegerField(
		Root, TEXT("cursor"), LastAcknowledgedCursor);
	return true;
}

bool UMuseUniverseSubsystem::ParseEventObject(
	const TSharedPtr<FJsonObject>& Object,
	FMuseUniverseEvent& OutEvent,
	FString& OutError) const
{
	if (!Object.IsValid())
	{
		OutError = TEXT("event is not an object");
		return false;
	}
	OutEvent.SchemaVersion = static_cast<int32>(
		IntegerField(Object, TEXT("schema_version"), 1));
	if (OutEvent.SchemaVersion != SupportedSchemaMajor)
	{
		OutError = FString::Printf(
			TEXT("unsupported event schema major %d"),
			OutEvent.SchemaVersion);
		return false;
	}
	OutEvent.Sequence = IntegerField(Object, TEXT("sequence"));
	OutEvent.EventId = StringField(Object, TEXT("event_id"));
	OutEvent.EventType = StringField(Object, TEXT("event_type"));
	OutEvent.RealmId = StringField(Object, TEXT("realm_id"));
	OutEvent.ActorId = StringField(Object, TEXT("actor_id"));
	OutEvent.StreamType = StringField(Object, TEXT("stream_type"));
	OutEvent.StreamId = StringField(Object, TEXT("stream_id"));
	OutEvent.StreamVersion = IntegerField(Object, TEXT("stream_version"));
	OutEvent.CausationId = StringField(Object, TEXT("causation_id"));
	OutEvent.CorrelationId = StringField(Object, TEXT("correlation_id"));
	OutEvent.OccurredAt = StringField(Object, TEXT("occurred_at"));
	OutEvent.bSimulation = BoolField(Object, TEXT("simulation"));

	const TSharedPtr<FJsonObject>* Authorization = nullptr;
	if (Object->TryGetObjectField(TEXT("authorization"), Authorization) && Authorization)
	{
		OutEvent.Authorization.bAllowed = BoolField(*Authorization, TEXT("allowed"));
		OutEvent.Authorization.Reason = StringField(*Authorization, TEXT("reason"));
		OutEvent.Authorization.OwnerGate = StringField(*Authorization, TEXT("owner_gate"));
		ReadStringArray(*Authorization, TEXT("scopes"), OutEvent.Authorization.Scopes);
	}

	const TSharedPtr<FJsonObject>* Provenance = nullptr;
	if (Object->TryGetObjectField(TEXT("provenance"), Provenance) && Provenance)
	{
		OutEvent.Provenance.Source = StringField(*Provenance, TEXT("source"));
		OutEvent.Provenance.Signature = StringField(*Provenance, TEXT("signature"));
		double Confidence = 0.0;
		(*Provenance)->TryGetNumberField(TEXT("confidence"), Confidence);
		OutEvent.Provenance.Confidence = Confidence;
		ReadStringArray(*Provenance, TEXT("evidence"), OutEvent.Provenance.Evidence);
	}

	const TSharedPtr<FJsonObject>* Payload = nullptr;
	if (Object->TryGetObjectField(TEXT("payload"), Payload) && Payload)
	{
		OutEvent.PayloadJson = SerializeObject(*Payload);
	}
	const TSharedPtr<FJsonObject>* Rollback = nullptr;
	if (Object->TryGetObjectField(TEXT("rollback"), Rollback) && Rollback)
	{
		OutEvent.RollbackJson = SerializeObject(*Rollback);
	}

	if (OutEvent.Sequence <= 0 || OutEvent.EventId.IsEmpty() ||
		OutEvent.StreamType.IsEmpty() || OutEvent.StreamId.IsEmpty() ||
		OutEvent.StreamVersion <= 0)
	{
		OutError = TEXT("event envelope is incomplete");
		return false;
	}
	return true;
}

bool UMuseUniverseSubsystem::ParseEventPageJson(
	const FString& Body,
	FString& OutError)
{
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Body);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		OutError = TEXT("event page is not valid JSON");
		return false;
	}
	const TArray<TSharedPtr<FJsonValue>>* Events = nullptr;
	if (!Root->TryGetArrayField(TEXT("events"), Events) || Events == nullptr)
	{
		OutError = TEXT("event page has no events array");
		return false;
	}

	int64 Cursor = LastAcknowledgedCursor;
	for (const TSharedPtr<FJsonValue>& Value : *Events)
	{
		const TSharedPtr<FJsonObject>* Object = nullptr;
		if (!Value.IsValid() || !Value->TryGetObject(Object) || !Object)
		{
			OutError = TEXT("event page contains a non-object event");
			return false;
		}
		FMuseUniverseEvent Event;
		if (!ParseEventObject(*Object, Event, OutError))
		{
			if (OutError.StartsWith(TEXT("unsupported event schema major")))
			{
				SetConnectionState(
					EMuseUniverseConnectionState::SchemaRejected,
					OutError);
			}
			return false;
		}
		if (Event.Sequence <= Cursor)
		{
			OutError = FString::Printf(
				TEXT("event cursor gap requires snapshot resync: sequence must exceed %lld, received %lld"),
				Cursor,
				Event.Sequence);
			return false;
		}
		const FString Key = Event.StreamType + TEXT(":") + Event.StreamId;
		const int64* SnapshotVersion = ProjectionVersions.Find(Key);
		const bool bCoveredBySnapshot = bReplayingSnapshotHistory &&
			SnapshotVersion && Event.StreamVersion <= *SnapshotVersion;
		if (!bCoveredBySnapshot)
		{
			ApplyOnlyIncreasingVersion(Key, Event.StreamVersion, Event.PayloadJson);
			OnUniverseEvent.Broadcast(Event);
		}
		Cursor = Event.Sequence;
	}

	const int64 ServerCursor = IntegerField(Root, TEXT("cursor"), Cursor);
	const int64 RealmVersion = IntegerField(Root, TEXT("realm_version"), -1);
	const int64 ExpectedEventCount = RealmVersion - LastRealmVersion;
	if (ServerCursor < Cursor || RealmVersion < LastRealmVersion ||
		ExpectedEventCount != Events->Num())
	{
		OutError = FString::Printf(
			TEXT("event cursor gap requires snapshot resync: expected %lld realm events, received %d"),
			ExpectedEventCount,
			Events->Num());
		return false;
	}
	LastAcknowledgedCursor = ServerCursor;
	LastRealmVersion = RealmVersion;
	bReplayingSnapshotHistory = false;
	return true;
}

bool UMuseUniverseSubsystem::ApplyOnlyIncreasingVersion(
	const FString& ProjectionKey,
	const int64 Version,
	const FString& RawJson)
{
	const int64* CurrentVersion = ProjectionVersions.Find(ProjectionKey);
	if (CurrentVersion && Version <= *CurrentVersion)
	{
		const FString CurrentJson = ProjectionJsonByKey.FindRef(ProjectionKey);
		if (Version == *CurrentVersion && CurrentJson != RawJson)
		{
			FMuseUniverseConflict Conflict;
			Conflict.ProjectionKey = ProjectionKey;
			Conflict.Version = Version;
			Conflict.CurrentJson = CurrentJson;
			Conflict.IncomingJson = RawJson;
			Conflicts.Add(Conflict);
			OnConflict.Broadcast(Conflict);
		}
		return false;
	}
	ProjectionVersions.Add(ProjectionKey, Version);
	ProjectionJsonByKey.Add(ProjectionKey, RawJson);
	return true;
}

void UMuseUniverseSubsystem::RequestResync(const FString& Reason)
{
	if (bResyncInFlight || ActiveRealmId.IsEmpty())
	{
		return;
	}
	bResyncInFlight = true;
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(PollTimer);
	}
	SetConnectionState(
		EMuseUniverseConnectionState::LoadingSnapshot,
		Reason.IsEmpty() ? TEXT("resync requested") : Reason);
	FetchSnapshot();
}

bool UMuseUniverseSubsystem::IsSensitivePayload(const FString& PayloadJson)
{
	const FString Lower = PayloadJson.ToLower();
	return Lower.Contains(TEXT("owner_authorization")) ||
		Lower.Contains(TEXT("authorization_phrase")) ||
		Lower.Contains(TEXT("api_key")) ||
		Lower.Contains(TEXT("access_token")) ||
		Lower.Contains(TEXT("credential_pool"));
}

bool UMuseUniverseSubsystem::SubmitCommand(
	const FMuseUniverseCommandRequest& Command)
{
	if (!GatewayClient.IsValid() || bRequestInFlight ||
		Command.CommandId.IsEmpty() || Command.CommandType.IsEmpty() ||
		Command.RealmId.IsEmpty() || Command.ActorId.IsEmpty() ||
		Command.RealmId != ActiveRealmId || Command.ActorId != ActiveActorId ||
		Command.ExpectedVersion < 0 || IsSensitivePayload(Command.PayloadJson))
	{
		SetConnectionState(
			EMuseUniverseConnectionState::Degraded,
			TEXT("command is incomplete, busy, or contains forbidden sensitive fields"));
		return false;
	}

	TSharedPtr<FJsonObject> Payload;
	const TSharedRef<TJsonReader<>> PayloadReader =
		TJsonReaderFactory<>::Create(Command.PayloadJson);
	if (!FJsonSerializer::Deserialize(PayloadReader, Payload) || !Payload.IsValid())
	{
		SetConnectionState(
			EMuseUniverseConnectionState::Degraded,
			TEXT("command payload must be a JSON object"));
		return false;
	}

	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("command_id"), Command.CommandId);
	Root->SetStringField(TEXT("command_type"), Command.CommandType);
	Root->SetStringField(TEXT("realm_id"), Command.RealmId);
	Root->SetStringField(TEXT("actor_id"), Command.ActorId);
	Root->SetNumberField(TEXT("expected_version"), Command.ExpectedVersion);
	Root->SetObjectField(TEXT("payload"), Payload);
	Root->SetBoolField(TEXT("simulation"), Command.bSimulation);
	if (!Command.ApprovalId.IsEmpty())
	{
		Root->SetStringField(TEXT("approval_id"), Command.ApprovalId);
	}

	FString Body;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
	FJsonSerializer::Serialize(Root, Writer);
	bRequestInFlight = true;
	const uint64 RequestGeneration = ConnectionGeneration;
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request =
		GatewayClient->CreateAuthorizedJsonRequest(
			TEXT("/v1/plugins/muse-universe/commands"),
			TEXT("POST"),
			Body);
	Request->OnProcessRequestComplete().BindLambda(
		[WeakThis = TWeakObjectPtr<UMuseUniverseSubsystem>(this), RequestGeneration](
			FHttpRequestPtr /*RequestPtr*/,
			FHttpResponsePtr Response,
			bool bConnected)
		{
			const int32 Code = bConnected && Response.IsValid()
				? Response->GetResponseCode() : 0;
			const FString ResponseBody = bConnected && Response.IsValid()
				? Response->GetContentAsString() : FString();
			AsyncTask(ENamedThreads::GameThread, [WeakThis, RequestGeneration, Code, ResponseBody]()
			{
				UMuseUniverseSubsystem* Self = WeakThis.Get();
				if (!Self || Self->ConnectionGeneration != RequestGeneration)
				{
					return;
				}
				Self->bRequestInFlight = false;
				if (EHttpResponseCodes::IsOk(Code))
				{
					Self->RequestResync(TEXT("command accepted; refreshing authoritative projection"));
				}
				else
				{
					Self->SetConnectionState(
						EMuseUniverseConnectionState::Degraded,
						FString::Printf(
							TEXT("command rejected with HTTP %d (%d response bytes)"),
							Code,
							ResponseBody.Len()));
					Self->ScheduleEventPoll(false);
				}
			});
		});
	Request->ProcessRequest();
	return true;
}
