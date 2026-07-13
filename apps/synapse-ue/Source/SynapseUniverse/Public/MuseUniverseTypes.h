#pragma once

#include "CoreMinimal.h"
#include "MuseUniverseMath.h"
#include "MuseUniverseTypes.generated.h"

// These records freeze schema-major 1 fields used by the client.
// Unknown fields are intentionally ignored for forward compatibility; a
// higher schema major is rejected before any projection is applied.

UENUM(BlueprintType)
enum class EMuseUniverseConnectionState : uint8
{
	Disconnected,
	LoadingSnapshot,
	Polling,
	Degraded,
	SchemaRejected,
};

USTRUCT(BlueprintType)
struct FMuseAuthorizationDecision
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) bool bAllowed = false;
	UPROPERTY(BlueprintReadOnly) FString Reason;
	UPROPERTY(BlueprintReadOnly) TArray<FString> Scopes;
	UPROPERTY(BlueprintReadOnly) FString OwnerGate = TEXT("not_required");
};

USTRUCT(BlueprintType)
struct FMuseProvenanceRecord
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) FString Source;
	UPROPERTY(BlueprintReadOnly) TArray<FString> Evidence;
	UPROPERTY(BlueprintReadOnly) double Confidence = 0.0;
	UPROPERTY(BlueprintReadOnly) FString Signature;
};

USTRUCT(BlueprintType)
struct FMuseProjectionBase
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) FString Id;
	UPROPERTY(BlueprintReadOnly) FString EntityType;
	UPROPERTY(BlueprintReadOnly) FString RealmId;
	UPROPERTY(BlueprintReadOnly) int64 Version = 0;
	UPROPERTY(BlueprintReadOnly) FString UpdatedAt;
	UPROPERTY(BlueprintReadOnly) bool bSimulation = false;
};

USTRUCT(BlueprintType)
struct FMuseAgentBindingProjection
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) FString AgentId;
	UPROPERTY(BlueprintReadOnly) FString DisplayName;
	UPROPERTY(BlueprintReadOnly) FString VesselClass;
	UPROPERTY(BlueprintReadOnly) TArray<FString> Capabilities;
	UPROPERTY(BlueprintReadOnly) TArray<FString> PermissionScopes;
	UPROPERTY(BlueprintReadOnly) FString ModelRouting;
	UPROPERTY(BlueprintReadOnly) FString Health = TEXT("unknown");
	UPROPERTY(BlueprintReadOnly) FString AuditRef;
	UPROPERTY(BlueprintReadOnly) FString LastReconciledAt;
	UPROPERTY(BlueprintReadOnly) bool bActive = false;
};

USTRUCT(BlueprintType)
struct FMuseUniverseEvent
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) int64 Sequence = 0;
	UPROPERTY(BlueprintReadOnly) FString EventId;
	UPROPERTY(BlueprintReadOnly) int32 SchemaVersion = 1;
	UPROPERTY(BlueprintReadOnly) FString EventType;
	UPROPERTY(BlueprintReadOnly) FString RealmId;
	UPROPERTY(BlueprintReadOnly) FString ActorId;
	UPROPERTY(BlueprintReadOnly) FString StreamType;
	UPROPERTY(BlueprintReadOnly) FString StreamId;
	UPROPERTY(BlueprintReadOnly) int64 StreamVersion = 0;
	UPROPERTY(BlueprintReadOnly) FMuseAuthorizationDecision Authorization;
	UPROPERTY(BlueprintReadOnly) FString CausationId;
	UPROPERTY(BlueprintReadOnly) FString CorrelationId;
	UPROPERTY(BlueprintReadOnly) FString OccurredAt;
	UPROPERTY(BlueprintReadOnly) FString PayloadJson;
	UPROPERTY(BlueprintReadOnly) FMuseProvenanceRecord Provenance;
	UPROPERTY(BlueprintReadOnly) bool bSimulation = false;
	UPROPERTY(BlueprintReadOnly) FString RollbackJson;
};

USTRUCT(BlueprintType)
struct FMuseRealmProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString Name;
	UPROPERTY(BlueprintReadOnly) FString Mode;
	UPROPERTY(BlueprintReadOnly) FString Visibility;
	UPROPERTY(BlueprintReadOnly) FString Ruleset;
};

USTRUCT(BlueprintType)
struct FMuseStationProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString StationType;
	UPROPERTY(BlueprintReadOnly) FString OwnerId;
	UPROPERTY(BlueprintReadOnly) TArray<FString> Rooms;
	UPROPERTY(BlueprintReadOnly) TArray<FString> Services;
};

USTRUCT(BlueprintType)
struct FMuseVesselModuleProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString ModuleId;
	UPROPERTY(BlueprintReadOnly) FString ModuleType;
	UPROPERTY(BlueprintReadOnly) TArray<FString> Capabilities;
	UPROPERTY(BlueprintReadOnly) TArray<FString> Scopes;
	UPROPERTY(BlueprintReadOnly) double Power = 0.0;
	UPROPERTY(BlueprintReadOnly) double Heat = 0.0;
};

USTRUCT(BlueprintType)
struct FMuseVesselProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString VesselClass;
	UPROPERTY(BlueprintReadOnly) FString OwnerId;
	UPROPERTY(BlueprintReadOnly) FString Health = TEXT("unknown");
	UPROPERTY(BlueprintReadOnly) FMuseAgentBindingProjection AgentBinding;
	UPROPERTY(BlueprintReadOnly) TArray<FString> Modules;
	UPROPERTY(BlueprintReadOnly) bool bQuarantined = false;
	UPROPERTY(BlueprintReadOnly) bool bActive = false;
};

USTRUCT(BlueprintType)
struct FMusePlayerProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString DisplayName;
	UPROPERTY(BlueprintReadOnly) FString Privacy;
	UPROPERTY(BlueprintReadOnly) FString AccessibilityJson;
};

USTRUCT(BlueprintType)
struct FMuseCivilizationProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString Name;
	UPROPERTY(BlueprintReadOnly) FString Charter;
	UPROPERTY(BlueprintReadOnly) FString GovernancePolicy;
};

USTRUCT(BlueprintType)
struct FMuseMembershipProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString PlayerId;
	UPROPERTY(BlueprintReadOnly) FString CivilizationId;
	UPROPERTY(BlueprintReadOnly) TArray<FString> Roles;
	UPROPERTY(BlueprintReadOnly) TArray<FString> Scopes;
	UPROPERTY(BlueprintReadOnly) FString Status;
};

USTRUCT(BlueprintType)
struct FMuseFleetProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString OwnerId;
	UPROPERTY(BlueprintReadOnly) FString MissionId;
	UPROPERTY(BlueprintReadOnly) TArray<FString> VesselIds;
	UPROPERTY(BlueprintReadOnly) FString Formation;
};

USTRUCT(BlueprintType)
struct FMuseMissionProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString SourceType;
	UPROPERTY(BlueprintReadOnly) FString SourceId;
	UPROPERTY(BlueprintReadOnly) FString State;
	UPROPERTY(BlueprintReadOnly) FString EvidenceJson;
};

USTRUCT(BlueprintType)
struct FMuseBlueprintProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString PackageVersion;
	UPROPERTY(BlueprintReadOnly) FString License;
	UPROPERTY(BlueprintReadOnly) FString ContentHash;
	UPROPERTY(BlueprintReadOnly) FString VerificationStatus;
};

USTRUCT(BlueprintType)
struct FMuseOperationalLedgerProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString Provider;
	UPROPERTY(BlueprintReadOnly) double ComputeSeconds = 0.0;
	UPROPERTY(BlueprintReadOnly) double CostUsd = 0.0;
};

USTRUCT(BlueprintType)
struct FMuseCreatorLedgerProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString AssetId;
	UPROPERTY(BlueprintReadOnly) double Quantity = 0.0;
	UPROPERTY(BlueprintReadOnly) FString TransferRef;
};

USTRUCT(BlueprintType)
struct FMuseWorkspaceLeaseProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString Provider;
	UPROPERTY(BlueprintReadOnly) FString ProjectId;
	UPROPERTY(BlueprintReadOnly) FString Status;
	UPROPERTY(BlueprintReadOnly) FString PreviewRef;
	UPROPERTY(BlueprintReadOnly) FString CheckpointRef;
};

USTRUCT(BlueprintType)
struct FMuseReleaseProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString ArtifactId;
	UPROPERTY(BlueprintReadOnly) FString Target;
	UPROPERTY(BlueprintReadOnly) FString Status;
	UPROPERTY(BlueprintReadOnly) FString RollbackRef;
};

USTRUCT(BlueprintType)
struct FMuseCinematicShotProjection
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FMuseProjectionBase Base;
	UPROPERTY(BlueprintReadOnly) FString SceneRevision;
	UPROPERTY(BlueprintReadOnly) FString StereoMetadataJson;
	UPROPERTY(BlueprintReadOnly) FString RenderConfigJson;
	UPROPERTY(BlueprintReadOnly) FString QcStatus;
};

USTRUCT(BlueprintType)
struct FMuseUniverseCommandRequest
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite) FString CommandId;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FString CommandType;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FString RealmId;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FString ActorId;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) int64 ExpectedVersion = 0;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FString PayloadJson = TEXT("{}");
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FString ApprovalId;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bSimulation = false;
};

USTRUCT(BlueprintType)
struct FMuseUniverseConflict
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) FString ProjectionKey;
	UPROPERTY(BlueprintReadOnly) int64 Version = 0;
	UPROPERTY(BlueprintReadOnly) FString CurrentJson;
	UPROPERTY(BlueprintReadOnly) FString IncomingJson;
};

