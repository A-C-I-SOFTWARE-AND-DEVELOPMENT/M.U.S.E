// ObservatoryGalaxyActor — the ISM node field arranged on sacred geometry.
// Copyright A-C-I Software & Development. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MuseSacredGeometry.h"
#include "ObservatoryRenderTypes.h"
#include "ObservatoryTypes.h"
#include "ObservatoryGalaxyActor.generated.h"

class UInstancedStaticMeshComponent;
class UObservatorySubsystem;

/**
 * Renders the Neural Observatory galaxy: one ISM instance per gateway
 * super-node cluster (plus a second ISM for an expanded cluster's members),
 * positioned by blending the gateway-computed `pos` with a closed-form
 * sacred-geometry anchor (MuseSacredGeometry). When LayoutMode == Polytope4D
 * the assigned 4D vertices are rotated each tick and re-projected — the only
 * per-tick work, done as a single bulk ISM transform update (never per-frame
 * instance add/remove, per the UE5 instancing gotcha).
 *
 * Honesty: when the gateway graph is unavailable or a node's `pos` was never
 * solved, the renderer shows nothing fabricated — unavailable graphs clear the
 * field; unsolved positions fall back to the pure geometry anchor.
 *
 * This actor runs NO networking and NO force-directed physics; it only reads
 * UObservatorySubsystem's delegates and places instances.
 */
UCLASS()
class SYNAPSEOBSERVATORYRENDER_API AObservatoryGalaxyActor : public AActor
{
	GENERATED_BODY()

public:
	AObservatoryGalaxyActor();

	//~ Begin AActor
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;
	//~ End AActor

	/** Set the layout mode at runtime and rebuild the field. */
	UFUNCTION(BlueprintCallable, Category = "MUSE|Observatory")
	void SetLayoutMode(EMuseLayoutMode NewMode);

	/** Set the gateway<->geometry morph (0..1) and rebuild. */
	UFUNCTION(BlueprintCallable, Category = "MUSE|Observatory")
	void SetGeometryBlend(float NewBlend);

	/** Re-fetch the snapshot from the gateway and rebuild. */
	UFUNCTION(BlueprintCallable, Category = "MUSE|Observatory")
	void Refresh();

	/** The static mesh used for each node instance (a small sphere works well;
	 *  owner-assigned — a null mesh renders nothing, never a placeholder). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory")
	TObjectPtr<UStaticMesh> NodeMesh;

	/** Initial layout mode (seeded from UObservatoryRenderSettings). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory")
	EMuseLayoutMode LayoutMode = EMuseLayoutMode::Gateway;

	/** 0 = pure gateway position, 1 = pure sacred-geometry anchor. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory",
		meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float GeometryBlend = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory")
	EMusePlatonic Platonic = EMusePlatonic::Icosahedron;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory")
	EMusePolytope Polytope = EMusePolytope::Cell600;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory|4D")
	EMuseRotationPlane RotationPlane = EMuseRotationPlane::ZW;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory|4D")
	EMuseRotationPlane SecondRotationPlane = EMuseRotationPlane::XY;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory|4D")
	bool bDoubleRotation = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory|4D")
	float RotationSpeed = 0.25f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory|4D")
	EMuseProjection Projection = EMuseProjection::Perspective;

	/** World radius the unit-scale frameworks are scaled to. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory",
		meta = (ClampMin = "1.0"))
	float WorldScale = 100.0f;

	/** Uniform scale of each node instance. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory",
		meta = (ClampMin = "0.01"))
	float NodeScale = 2.0f;

	/** Fetch the snapshot automatically on BeginPlay. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory")
	bool bAutoFetchOnBeginPlay = true;

	/** Seed the layout fields from UObservatoryRenderSettings on BeginPlay
	 *  (uncheck to keep per-instance editor overrides). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory")
	bool bUseProjectSettings = true;

private:
	/** ISM for the ~200 super-node clusters. */
	UPROPERTY(VisibleAnywhere, Category = "MUSE|Observatory")
	TObjectPtr<UInstancedStaticMeshComponent> ClusterMesh;

	/** ISM for one expanded cluster's members (local-space layout). */
	UPROPERTY(VisibleAnywhere, Category = "MUSE|Observatory")
	TObjectPtr<UInstancedStaticMeshComponent> MemberMesh;

	UFUNCTION()
	void HandleSnapshot(bool bOk, const FObsSnapshot& Snapshot);

	UFUNCTION()
	void HandleLayout(bool bOk, const FObsClusterLayout& Layout);

	UObservatorySubsystem* ResolveSubsystem() const;

	/** Apply any active `muse.Observatory.*` console overrides onto the
	 *  effective fields used by the build/tick. */
	void ApplyConsoleOverrides();

	/** Closed-form anchors (unit framework scaled to WorldScale) for Count
	 *  nodes in the active non-polytope mode. */
	TArray<FVector> BuildAnchors(int32 Count) const;

	/** Per-instance unit 4D vertices for Polytope4D mode (cycled, normalized). */
	TArray<FVector4> BuildSource4D(int32 Count) const;

	/** Rebuild the cluster ISM from the last snapshot. */
	void RebuildClusters();

	/** Bulk-update cluster transforms for the current 4D rotation (Polytope4D). */
	void RefreshClusterTransforms();

	/** Project source 4D vertex Index for the current accumulated angle. */
	FVector ProjectedAnchor(int32 Index) const;

	// Cached state from the last good snapshot (no fabricated data is cached).
	TArray<FString> ClusterIds;         // cluster id per instance (member centering)
	TArray<FVector> GatewayPositions;   // gateway `pos` per cluster (world)
	TArray<bool> HasGatewayPosition;    // bHasPos per cluster
	TArray<FVector> StaticAnchors;      // non-polytope anchors per cluster
	TArray<FVector4> Source4D;          // polytope unit vertices per cluster
	TMap<FString, FVector> ClusterWorldById;  // for member expansion centering

	double RotationAngle = 0.0;
	bool bHaveSnapshot = false;
};
