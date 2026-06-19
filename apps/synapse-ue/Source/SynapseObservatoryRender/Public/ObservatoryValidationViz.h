// ObservatoryValidationViz — AXIOM gate verdicts -> visual state.
// Copyright A-C-I Software & Development. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ObservatoryTypes.h"
#include "ObservatoryValidationViz.generated.h"

class UMaterialParameterCollection;
class UObservatorySubsystem;

/** Broadcast when a gate verdict arrives — designers bind these to drive the
 *  gate-ring flares (pass = green pulse, fail = red flare, pending = amber). */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(
	FOnGateVisual, const FString&, Gate, int32, GateIndex);

/** Broadcast on a GraphRAG node.activate touch (drives the pulse effect). */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(
	FOnActivatePulse, const FString&, ClusterId, float, Weight);

/**
 * Binds UObservatorySubsystem's gate/activation stream to renderable state:
 * the eight AXIOM gates (Planning..Rollback) drive a Material Parameter
 * Collection (one scalar per gate: +1 pass, -1 fail, +0.5 pending/override) and
 * Blueprint events for bespoke flares. Material-parameter writes only — no
 * per-tick work. Every value comes verbatim from a real `gate.verdict`
 * event; nothing is invented (a gate with no event stays at its neutral 0).
 */
UCLASS(ClassGroup = (MUSE), meta = (BlueprintSpawnableComponent))
class SYNAPSEOBSERVATORYRENDER_API UObservatoryValidationViz : public UActorComponent
{
	GENERATED_BODY()

public:
	UObservatoryValidationViz();

	//~ Begin UActorComponent
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	//~ End UActorComponent

	/** The canonical eight AXIOM gates, lowercase, in pipeline order. */
	static const TArray<FString>& GateOrder();

	/** Canonical index 0..7 for a gate string (-1 if unknown). Accepts the
	 *  gateway's `owner` shorthand for "OwnerApproval". */
	UFUNCTION(BlueprintPure, Category = "MUSE|Observatory")
	static int32 GateIndexOf(const FString& Gate);

	/** Optional MPC; each gate maps to scalar param `Gate_<Name>`. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MUSE|Observatory")
	TObjectPtr<UMaterialParameterCollection> GateCollection;

	UPROPERTY(BlueprintAssignable, Category = "MUSE|Observatory")
	FOnGateVisual OnGatePass;

	UPROPERTY(BlueprintAssignable, Category = "MUSE|Observatory")
	FOnGateVisual OnGateFail;

	UPROPERTY(BlueprintAssignable, Category = "MUSE|Observatory")
	FOnGateVisual OnGatePending;

	UPROPERTY(BlueprintAssignable, Category = "MUSE|Observatory")
	FOnActivatePulse OnPulse;

private:
	UFUNCTION()
	void HandleGateVerdict(const FObsGateVerdict& Event);

	UFUNCTION()
	void HandleNodeActivate(const FObsNodeActivate& Event);

	UObservatorySubsystem* ResolveSubsystem() const;

	void SetGateScalar(const FString& Gate, float Value);
};
