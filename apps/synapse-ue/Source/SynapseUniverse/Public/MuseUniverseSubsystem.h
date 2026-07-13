#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "TimerManager.h"
#include "MuseUniverseTypes.h"
#include "MuseUniverseSubsystem.generated.h"

class FJsonObject;
class UmuseGatewayClient;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(
	FOnMuseUniverseEvent, FMuseUniverseEvent, Event);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(
	FOnMuseUniverseConnectionChanged,
	EMuseUniverseConnectionState, State,
	const FString&, Reason);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(
	FOnMuseUniverseConflict, FMuseUniverseConflict, Conflict);

/**
 * Read-only projection/reconnect client for the authoritative muse-universe
 * plugin routes. Movement and presentation may be predicted locally; entity
 * versions, capabilities, permissions, inventory, and command outcomes are
 * never authored by this subsystem.
 */
UCLASS()
class SYNAPSEUNIVERSE_API UMuseUniverseSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	UFUNCTION(BlueprintCallable, Category = "M.U.S.E.|Universe")
	void Connect(const FString& RealmId, const FString& ActorId);

	UFUNCTION(BlueprintCallable, Category = "M.U.S.E.|Universe")
	void Disconnect();

	UFUNCTION(BlueprintCallable, Category = "M.U.S.E.|Universe")
	void RequestResync(const FString& Reason);

	UFUNCTION(BlueprintCallable, Category = "M.U.S.E.|Universe")
	bool SubmitCommand(const FMuseUniverseCommandRequest& Command);

	UFUNCTION(BlueprintPure, Category = "M.U.S.E.|Universe")
	int64 GetLastAcknowledgedCursor() const { return LastAcknowledgedCursor; }

	UFUNCTION(BlueprintPure, Category = "M.U.S.E.|Universe")
	EMuseUniverseConnectionState GetConnectionState() const { return ConnectionState; }

	UFUNCTION(BlueprintPure, Category = "M.U.S.E.|Universe")
	TArray<FMuseUniverseConflict> GetConflicts() const { return Conflicts; }

	UPROPERTY(BlueprintAssignable, Category = "M.U.S.E.|Universe")
	FOnMuseUniverseEvent OnUniverseEvent;

	UPROPERTY(BlueprintAssignable, Category = "M.U.S.E.|Universe")
	FOnMuseUniverseConnectionChanged OnConnectionChanged;

	UPROPERTY(BlueprintAssignable, Category = "M.U.S.E.|Universe")
	FOnMuseUniverseConflict OnConflict;

private:
	void FetchSnapshot();
	void FetchEvents();
	void ScheduleSnapshotRetry();
	void ScheduleEventPoll(bool bPreviousRequestSucceeded);
	bool ParseSnapshotJson(const FString& Body, FString& OutError);
	bool ParseEventPageJson(const FString& Body, FString& OutError);
	bool ParseEventObject(
		const TSharedPtr<FJsonObject>& Object,
		FMuseUniverseEvent& OutEvent,
		FString& OutError) const;
	bool ApplyOnlyIncreasingVersion(
		const FString& ProjectionKey,
		int64 Version,
		const FString& RawJson);
	void SetConnectionState(
		EMuseUniverseConnectionState NewState,
		const FString& Reason);
	static bool IsSensitivePayload(const FString& PayloadJson);

	TWeakObjectPtr<UmuseGatewayClient> GatewayClient;
	FString ActiveRealmId;
	FString ActiveActorId;
	int64 LastAcknowledgedCursor = 0;
	int64 LastRealmVersion = 0;
	double PollBackoffSeconds = 1.0;
	uint64 ConnectionGeneration = 0;
	bool bRequestInFlight = false;
	bool bResyncInFlight = false;
	bool bReplayingSnapshotHistory = false;
	EMuseUniverseConnectionState ConnectionState =
		EMuseUniverseConnectionState::Disconnected;
	FTimerHandle PollTimer;
	TMap<FString, int64> ProjectionVersions;
	TMap<FString, FString> ProjectionJsonByKey;
	TArray<FMuseUniverseConflict> Conflicts;
};
