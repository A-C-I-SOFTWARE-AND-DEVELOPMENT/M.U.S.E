#include "AgentVesselActor.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

AAgentVesselActor::AAgentVesselActor()
{
	PrimaryActorTick.bCanEverTick = false;
	VesselRoot = CreateDefaultSubobject<USceneComponent>(TEXT("VesselRoot"));
	SetRootComponent(VesselRoot);
	PressureHull = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PressureHull"));
	PressureHull->SetupAttachment(VesselRoot);
	DockingCollar = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("DockingCollar"));
	DockingCollar->SetupAttachment(VesselRoot);
	SensorMast = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("SensorMast"));
	SensorMast->SetupAttachment(VesselRoot);
	RadiatorPort = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("RadiatorPort"));
	RadiatorPort->SetupAttachment(VesselRoot);
	RadiatorStarboard = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("RadiatorStarboard"));
	RadiatorStarboard->SetupAttachment(VesselRoot);
	StatusLabel = CreateDefaultSubobject<UTextRenderComponent>(TEXT("ProjectionStatus"));
	StatusLabel->SetupAttachment(VesselRoot);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(
		TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CylinderMesh.Succeeded())
	{
		PressureHull->SetStaticMesh(CylinderMesh.Object);
		DockingCollar->SetStaticMesh(CylinderMesh.Object);
		SensorMast->SetStaticMesh(CylinderMesh.Object);
	}
	if (CubeMesh.Succeeded())
	{
		RadiatorPort->SetStaticMesh(CubeMesh.Object);
		RadiatorStarboard->SetStaticMesh(CubeMesh.Object);
	}

	PressureHull->SetRelativeRotation(FRotator(90.0, 0.0, 0.0));
	PressureHull->SetRelativeScale3D(FVector(36.0, 36.0, 112.0));
	DockingCollar->SetRelativeLocation(FVector(0.0, -2100.0, 0.0));
	DockingCollar->SetRelativeRotation(FRotator(90.0, 0.0, 0.0));
	DockingCollar->SetRelativeScale3D(FVector(14.0, 14.0, 8.0));
	SensorMast->SetRelativeLocation(FVector(3400.0, 0.0, 1800.0));
	SensorMast->SetRelativeScale3D(FVector(2.4, 2.4, 9.0));
	RadiatorPort->SetRelativeLocation(FVector(-1800.0, -2900.0, -200.0));
	RadiatorPort->SetRelativeScale3D(FVector(20.0, 0.6, 8.0));
	RadiatorStarboard->SetRelativeLocation(FVector(-1800.0, 2900.0, -200.0));
	RadiatorStarboard->SetRelativeScale3D(FVector(20.0, 0.6, 8.0));
	StatusLabel->SetRelativeLocation(FVector(0.0, 0.0, 3000.0));
	StatusLabel->SetHorizontalAlignment(EHorizTextAligment::EHTA_Center);

	CommandBridgeAnchor = CreateRoomAnchor(TEXT("CommandBridgeAnchor"), FVector(46, 0, 5));
	NeuralChamberAnchor = CreateRoomAnchor(TEXT("NeuralChamberAnchor"), FVector(23, 0, 1));
	SensorLaboratoryAnchor = CreateRoomAnchor(TEXT("SensorLaboratoryAnchor"), FVector(32, 0, 9));
	FabricationBayAnchor = CreateRoomAnchor(TEXT("FabricationBayAnchor"), FVector(-9, 0, -2));
	MemoryVaultAnchor = CreateRoomAnchor(TEXT("MemoryVaultAnchor"), FVector(7, 0, -5));
	DroneHangarAnchor = CreateRoomAnchor(TEXT("DroneHangarAnchor"), FVector(-39, 0, -3));
	EngineeringAnchor = CreateRoomAnchor(TEXT("EngineeringAnchor"), FVector(-51, 0, 1));
	AirlockSecurityAnchor = CreateRoomAnchor(TEXT("AirlockSecurityAnchor"), FVector(0, -21, 0));
}

USceneComponent* AAgentVesselActor::CreateRoomAnchor(
	const TCHAR* Name,
	const FVector& LocationMeters)
{
	USceneComponent* Anchor = CreateDefaultSubobject<USceneComponent>(Name);
	Anchor->SetupAttachment(VesselRoot);
	Anchor->SetRelativeLocation(LocationMeters * 100.0);
	return Anchor;
}

void AAgentVesselActor::ApplyProjection(const FMuseVesselProjection& Projection)
{
	CurrentProjection = Projection;
	bSimulationDamage = Projection.Base.bSimulation &&
		!Projection.Health.Equals(TEXT("healthy"), ESearchCase::IgnoreCase);
	if (bSimulationDamage)
	{
		StatusLabel->SetText(FText::FromString(TEXT("SIMULATION DAMAGE")));
		StatusLabel->SetTextRenderColor(FColor(255, 190, 64));
	}
	else if (!Projection.Health.Equals(TEXT("healthy"), ESearchCase::IgnoreCase))
	{
		StatusLabel->SetText(FText::FromString(
			FString::Printf(TEXT("DEGRADED: %s"), *Projection.Health)));
		StatusLabel->SetTextRenderColor(FColor(255, 92, 92));
	}
	else
	{
		StatusLabel->SetText(FText::FromString(
			Projection.AgentBinding.AgentId.IsEmpty()
				? Projection.Base.Id
				: Projection.AgentBinding.AgentId));
		StatusLabel->SetTextRenderColor(FColor(120, 220, 255));
	}
	Tags.AddUnique(FName(*Projection.Base.Id));
	Tags.AddUnique(FName(*Projection.AgentBinding.AgentId));
	SetActorHiddenInGame(!Projection.bActive || Projection.bQuarantined);
}
