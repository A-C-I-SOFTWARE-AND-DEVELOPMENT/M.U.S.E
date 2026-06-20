// ObservatoryFlowComponent — spline + Niagara data-flow particles.
// Copyright A-C-I Software & Development. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "ObservatoryTypes.h"
#include "ObservatoryFlowComponent.generated.h"

class UNiagaraComponent;
class UNiagaraSystem;
class USplineComponent;
class UObservatorySubsystem;

/** Relays a pipeline `job.stage` event to Blueprint so the station-spine packet
 *  can be driven (stage name + latency that maps to packet speed). */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(
	FOnPipelinePacket, const FString&, Stage, const FString&, TaskClass, float, StageLatencyMs);

/**
 * Drives the "data flowing along connections" effect. Given an edge spline it
 * spawns the assigned Niagara system and sets standard user parameters
 * (throughput -> spawn rate, latency -> speed, type -> color). The Niagara
 * *asset* is owner-authored (binary; not in this repo): when FlowSystem is
 * unset every call is a logged no-op, never a fabricated effect.
 *
 * It also relays `job.stage` stream events (OnPipelinePacket) so the station
 * spine animates packets moving job -> navigator -> worker -> gate -> ledger.
 */
UCLASS(ClassGroup = (MUSE), meta = (BlueprintSpawnableComponent))
class SYNAPSEOBSERVATORYRENDER_API UObservatoryFlowComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	UObservatoryFlowComponent();

	//~ Begin UActorComponent
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	//~ End UActorComponent

	/** Spawn a flow along Spline. Throughput sets the spawn-rate param, Speed
	 *  the speed param, Color the color param. Returns the spawned component
	 *  (null when no FlowSystem is assigned). The owner's Niagara system reads
	 *  the spline via its own exposed spline data interface (see docs). */
	UFUNCTION(BlueprintCallable, Category = "MUSE|Observatory")
	UNiagaraComponent* SpawnFlow(USplineComponent* Spline, float Throughput, float Speed, FLinearColor Color);

	/** The owner-authored Niagara system used for connection particles. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory")
	TSoftObjectPtr<UNiagaraSystem> FlowSystem;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory|Params")
	FName ThroughputParam = TEXT("User.Throughput");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory|Params")
	FName SpeedParam = TEXT("User.Speed");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory|Params")
	FName ColorParam = TEXT("User.Color");

	/** Bound to UObservatorySubsystem::OnJobStage — drive the station packet. */
	UPROPERTY(BlueprintAssignable, Category = "MUSE|Observatory")
	FOnPipelinePacket OnPipelinePacket;

private:
	UFUNCTION()
	void HandleJobStage(const FObsJobStage& Event);

	UObservatorySubsystem* ResolveSubsystem() const;
};
