// ObservatoryValidationViz implementation — see ObservatoryValidationViz.h.
// Copyright A-C-I Software & Development. All rights reserved.

#include "ObservatoryValidationViz.h"

#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialParameterCollection.h"
#include "ObservatorySubsystem.h"
#include "ObservatoryTypes.h"
#include "SynapseObservatoryRender.h"

UObservatoryValidationViz::UObservatoryValidationViz()
{
	PrimaryComponentTick.bCanEverTick = false;
}

const TArray<FString>& UObservatoryValidationViz::GateOrder()
{
	// Mirrors axiom/axiom/orchestrator/gates.py GATES (lowercased; the gateway
	// emits `owner` for OwnerApproval).
	static const TArray<FString> Gates = {
		TEXT("planning"), TEXT("build"), TEXT("review"), TEXT("test"),
		TEXT("security"), TEXT("release"), TEXT("owner"), TEXT("rollback"),
	};
	return Gates;
}

int32 UObservatoryValidationViz::GateIndexOf(const FString& Gate)
{
	const FString Key = Gate.ToLower();
	const int32 Index = GateOrder().IndexOfByKey(Key);
	if (Index != INDEX_NONE)
	{
		return Index;
	}
	// Accept a few spellings the gateway/ledger may use.
	if (Key == TEXT("ownerapproval") || Key == TEXT("owner_approval"))
	{
		return GateOrder().IndexOfByKey(TEXT("owner"));
	}
	return INDEX_NONE;
}

void UObservatoryValidationViz::BeginPlay()
{
	Super::BeginPlay();
	if (UObservatorySubsystem* Sub = ResolveSubsystem())
	{
		Sub->OnGateVerdict.AddDynamic(this, &UObservatoryValidationViz::HandleGateVerdict);
		Sub->OnNodeActivate.AddDynamic(this, &UObservatoryValidationViz::HandleNodeActivate);
	}
}

void UObservatoryValidationViz::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UObservatorySubsystem* Sub = ResolveSubsystem())
	{
		Sub->OnGateVerdict.RemoveDynamic(this, &UObservatoryValidationViz::HandleGateVerdict);
		Sub->OnNodeActivate.RemoveDynamic(this, &UObservatoryValidationViz::HandleNodeActivate);
	}
	Super::EndPlay(EndPlayReason);
}

UObservatorySubsystem* UObservatoryValidationViz::ResolveSubsystem() const
{
	if (const UWorld* W = GetWorld())
	{
		if (UGameInstance* GI = W->GetGameInstance())
		{
			return GI->GetSubsystem<UObservatorySubsystem>();
		}
	}
	return nullptr;
}

void UObservatoryValidationViz::SetGateScalar(const FString& Gate, float Value)
{
	if (!GateCollection)
	{
		return;
	}
	const FName Param(*FString::Printf(TEXT("Gate_%s"), *Gate));
	UKismetMaterialLibrary::SetScalarParameterValue(this, GateCollection, Param, Value);
}

void UObservatoryValidationViz::HandleGateVerdict(const FObsGateVerdict& Event)
{
	const int32 Index = GateIndexOf(Event.Gate);
	const FString Verdict = Event.Verdict.ToLower();

	if (Verdict == TEXT("pass"))
	{
		SetGateScalar(Event.Gate.ToLower(), 1.0f);
		OnGatePass.Broadcast(Event.Gate, Index);
	}
	else if (Verdict == TEXT("fail"))
	{
		SetGateScalar(Event.Gate.ToLower(), -1.0f);
		OnGateFail.Broadcast(Event.Gate, Index);
	}
	else  // override / unknown -> amber pending
	{
		SetGateScalar(Event.Gate.ToLower(), 0.5f);
		OnGatePending.Broadcast(Event.Gate, Index);
	}

	UE_LOG(LogSynapseObservatoryRender, Verbose,
		TEXT("gate.verdict %s -> %s (index=%d)"), *Event.Gate, *Event.Verdict, Index);
}

void UObservatoryValidationViz::HandleNodeActivate(const FObsNodeActivate& Event)
{
	OnPulse.Broadcast(Event.ClusterId, Event.Weight);
}
