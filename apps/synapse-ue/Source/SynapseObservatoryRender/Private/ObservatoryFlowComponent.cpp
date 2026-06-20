// ObservatoryFlowComponent implementation — see ObservatoryFlowComponent.h.
// Copyright A-C-I Software & Development. All rights reserved.

#include "ObservatoryFlowComponent.h"

#include "Components/SplineComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "ObservatorySubsystem.h"
#include "ObservatoryTypes.h"
#include "SynapseObservatoryRender.h"

UObservatoryFlowComponent::UObservatoryFlowComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

void UObservatoryFlowComponent::BeginPlay()
{
	Super::BeginPlay();
	if (UObservatorySubsystem* Sub = ResolveSubsystem())
	{
		Sub->OnJobStage.AddDynamic(this, &UObservatoryFlowComponent::HandleJobStage);
	}
}

void UObservatoryFlowComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UObservatorySubsystem* Sub = ResolveSubsystem())
	{
		Sub->OnJobStage.RemoveDynamic(this, &UObservatoryFlowComponent::HandleJobStage);
	}
	Super::EndPlay(EndPlayReason);
}

UObservatorySubsystem* UObservatoryFlowComponent::ResolveSubsystem() const
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

UNiagaraComponent* UObservatoryFlowComponent::SpawnFlow(
	USplineComponent* Spline, float Throughput, float Speed, FLinearColor Color)
{
	if (FlowSystem.IsNull())
	{
		UE_LOG(LogSynapseObservatoryRender, Verbose,
			TEXT("SpawnFlow: no FlowSystem assigned; skipping (no fabricated effect)."));
		return nullptr;
	}
	UNiagaraSystem* System = FlowSystem.LoadSynchronous();
	if (!System || !Spline)
	{
		return nullptr;
	}

	UNiagaraComponent* Comp = UNiagaraFunctionLibrary::SpawnSystemAttached(
		System, Spline, NAME_None, FVector::ZeroVector, FRotator::ZeroRotator,
		EAttachLocation::KeepRelativeOffset, /*bAutoDestroy=*/true);
	if (!Comp)
	{
		return nullptr;
	}

	Comp->SetVariableFloat(ThroughputParam, Throughput);
	Comp->SetVariableFloat(SpeedParam, Speed);
	Comp->SetVariableLinearColor(ColorParam, Color);
	return Comp;
}

void UObservatoryFlowComponent::HandleJobStage(const FObsJobStage& Event)
{
	const float Latency = Event.bHasStageLatencyMs ? Event.StageLatencyMs : 0.0f;
	OnPipelinePacket.Broadcast(Event.Stage, Event.TaskClass, Latency);
}
