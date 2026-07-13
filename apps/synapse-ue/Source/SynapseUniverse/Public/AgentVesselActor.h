#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MuseUniverseTypes.h"
#include "AgentVesselActor.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

/** Original aerospace vessel whose visuals are driven only by projections. */
UCLASS(BlueprintType)
class SYNAPSEUNIVERSE_API AAgentVesselActor : public AActor
{
	GENERATED_BODY()

public:
	AAgentVesselActor();

	UFUNCTION(BlueprintCallable, Category = "M.U.S.E.|Vessel")
	void ApplyProjection(const FMuseVesselProjection& Projection);

	UFUNCTION(BlueprintPure, Category = "M.U.S.E.|Vessel")
	const FMuseVesselProjection& GetProjection() const { return CurrentProjection; }

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Vessel")
	TObjectPtr<USceneComponent> VesselRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Vessel")
	TObjectPtr<UStaticMeshComponent> PressureHull;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Vessel")
	TObjectPtr<UStaticMeshComponent> DockingCollar;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Vessel")
	TObjectPtr<UStaticMeshComponent> SensorMast;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Vessel")
	TObjectPtr<UStaticMeshComponent> RadiatorPort;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Vessel")
	TObjectPtr<UStaticMeshComponent> RadiatorStarboard;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Vessel")
	TObjectPtr<UTextRenderComponent> StatusLabel;

private:
	USceneComponent* CreateRoomAnchor(const TCHAR* Name, const FVector& LocationMeters);

	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> CommandBridgeAnchor;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> NeuralChamberAnchor;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> SensorLaboratoryAnchor;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> FabricationBayAnchor;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> MemoryVaultAnchor;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> DroneHangarAnchor;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> EngineeringAnchor;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> AirlockSecurityAnchor;

	UPROPERTY(VisibleAnywhere) FMuseVesselProjection CurrentProjection;
	bool bSimulationDamage = false;
};

