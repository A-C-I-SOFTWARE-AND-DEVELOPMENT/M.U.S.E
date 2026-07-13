#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MuseUniverseTypes.h"
#include "AtlasCrownActor.generated.h"

class UInstancedStaticMeshComponent;
class USceneComponent;
class UStaticMeshComponent;

/** Procedural metric fallback for the original Atlas Crown USDA source. */
UCLASS(BlueprintType)
class SYNAPSEUNIVERSE_API AAtlasCrownActor : public AActor
{
	GENERATED_BODY()

public:
	AAtlasCrownActor();
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnConstruction(const FTransform& Transform) override;

	UFUNCTION(BlueprintCallable, Category = "M.U.S.E.|Atlas Crown")
	void ApplyStationProjection(const FMuseStationProjection& Projection);

	UFUNCTION(BlueprintPure, Category = "M.U.S.E.|Atlas Crown")
	double GetRingAAngleDegrees() const { return RingAAngleDegrees; }

	UFUNCTION(BlueprintPure, Category = "M.U.S.E.|Atlas Crown")
	double GetRingBAngleDegrees() const { return RingBAngleDegrees; }

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "M.U.S.E.|Atlas Crown")
	bool bAnimateCrown = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "M.U.S.E.|Atlas Crown", meta = (ClampMin = "24", ClampMax = "384"))
	int32 InteractiveRingSegments = 96;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "M.U.S.E.|Atlas Crown")
	double RingDegreesPerSecond = 0.25;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Atlas Crown")
	TObjectPtr<USceneComponent> StationRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Atlas Crown")
	TObjectPtr<UStaticMeshComponent> NeuralCore;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Atlas Crown")
	TObjectPtr<UStaticMeshComponent> AxialSpine;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Atlas Crown")
	TObjectPtr<UStaticMeshComponent> StationaryDockingSpine;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Atlas Crown")
	TObjectPtr<UInstancedStaticMeshComponent> CrownRingA;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Atlas Crown")
	TObjectPtr<UInstancedStaticMeshComponent> CrownRingB;

private:
	void BuildMetricGeometry();
	void BuildRing(UInstancedStaticMeshComponent* Ring, double PhaseDegrees);
	void BuildSectorCues();

	UPROPERTY(VisibleAnywhere) TObjectPtr<UInstancedStaticMeshComponent> SectorCues;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> CommandSectorAnchor;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> ProductionSectorAnchor;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> IntelligenceSectorAnchor;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> GovernanceSectorAnchor;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> SystemsSectorAnchor;

	double RingAAngleDegrees = 0.0;
	double RingBAngleDegrees = 0.0;
};

