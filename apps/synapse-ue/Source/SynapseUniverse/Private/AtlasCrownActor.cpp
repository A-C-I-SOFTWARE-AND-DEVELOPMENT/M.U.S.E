#include "AtlasCrownActor.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

AAtlasCrownActor::AAtlasCrownActor()
{
	PrimaryActorTick.bCanEverTick = true;
	StationRoot = CreateDefaultSubobject<USceneComponent>(TEXT("StationRoot"));
	SetRootComponent(StationRoot);

	NeuralCore = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("NeuralCore"));
	NeuralCore->SetupAttachment(StationRoot);
	AxialSpine = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("AxialSpine"));
	AxialSpine->SetupAttachment(StationRoot);
	StationaryDockingSpine = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("StationaryDockingSpine"));
	StationaryDockingSpine->SetupAttachment(StationRoot);

	CrownRingA = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("CrownRingA"));
	CrownRingA->SetupAttachment(StationRoot);
	CrownRingB = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("CrownRingB"));
	CrownRingB->SetupAttachment(StationRoot);
	SectorCues = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("FiveSectorCues"));
	SectorCues->SetupAttachment(StationRoot);

	CommandSectorAnchor = CreateDefaultSubobject<USceneComponent>(TEXT("CommandSectorAnchor"));
	CommandSectorAnchor->SetupAttachment(StationRoot);
	ProductionSectorAnchor = CreateDefaultSubobject<USceneComponent>(TEXT("ProductionSectorAnchor"));
	ProductionSectorAnchor->SetupAttachment(StationRoot);
	IntelligenceSectorAnchor = CreateDefaultSubobject<USceneComponent>(TEXT("IntelligenceSectorAnchor"));
	IntelligenceSectorAnchor->SetupAttachment(StationRoot);
	GovernanceSectorAnchor = CreateDefaultSubobject<USceneComponent>(TEXT("GovernanceSectorAnchor"));
	GovernanceSectorAnchor->SetupAttachment(StationRoot);
	SystemsSectorAnchor = CreateDefaultSubobject<USceneComponent>(TEXT("SystemsSectorAnchor"));
	SystemsSectorAnchor->SetupAttachment(StationRoot);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(
		TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(
		TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (SphereMesh.Succeeded())
	{
		NeuralCore->SetStaticMesh(SphereMesh.Object);
	}
	if (CylinderMesh.Succeeded())
	{
		AxialSpine->SetStaticMesh(CylinderMesh.Object);
		StationaryDockingSpine->SetStaticMesh(CylinderMesh.Object);
	}
	if (CubeMesh.Succeeded())
	{
		CrownRingA->SetStaticMesh(CubeMesh.Object);
		CrownRingB->SetStaticMesh(CubeMesh.Object);
		SectorCues->SetStaticMesh(CubeMesh.Object);
	}
	CrownRingA->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	CrownRingB->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SectorCues->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void AAtlasCrownActor::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	BuildMetricGeometry();
}

void AAtlasCrownActor::BuildMetricGeometry()
{
	const double CoreScale =
		MuseUniverseMath::MetersToCentimeters(MuseUniverseMath::AtlasSphereDiameterMeters) / 100.0;
	NeuralCore->SetRelativeScale3D(FVector(CoreScale));

	const double SpineLengthScale =
		MuseUniverseMath::MetersToCentimeters(MuseUniverseMath::AxialSpineLengthMeters) / 100.0;
	// Engine/BasicShapes/Cylinder has a 0.5 m radius and 1 m height.
	AxialSpine->SetRelativeScale3D(FVector(36.0, 36.0, SpineLengthScale));
	StationaryDockingSpine->SetRelativeScale3D(FVector(52.0, 52.0, SpineLengthScale));
	StationaryDockingSpine->ComponentTags.AddUnique(TEXT("stationary-dock"));

	BuildRing(CrownRingA, 0.0);
	BuildRing(CrownRingB, 36.0);
	BuildSectorCues();
}

void AAtlasCrownActor::BuildRing(
	UInstancedStaticMeshComponent* Ring,
	const double PhaseDegrees)
{
	if (!Ring)
	{
		return;
	}
	Ring->ClearInstances();
	const int32 Segments = FMath::Clamp(InteractiveRingSegments, 24, 384);
	const double RadiusCm = MuseUniverseMath::MetersToCentimeters(
		MuseUniverseMath::CrownRingDiameterMeters * 0.5);
	const double SegmentLengthCm = 2.0 * PI * RadiusCm / Segments;
	const double TubeCm = MuseUniverseMath::MetersToCentimeters(64.0);
	for (int32 Index = 0; Index < Segments; ++Index)
	{
		const double AngleDegrees = PhaseDegrees + 360.0 * Index / Segments;
		const double AngleRadians = FMath::DegreesToRadians(AngleDegrees);
		const FVector Location(
			RadiusCm * FMath::Cos(AngleRadians),
			RadiusCm * FMath::Sin(AngleRadians),
			0.0);
		const FRotator Rotation(0.0, AngleDegrees + 90.0, 0.0);
		const FVector Scale(
			SegmentLengthCm / 100.0,
			TubeCm / 100.0,
			TubeCm / 100.0);
		Ring->AddInstance(FTransform(Rotation, Location, Scale));
	}
}

void AAtlasCrownActor::BuildSectorCues()
{
	SectorCues->ClearInstances();
	USceneComponent* Anchors[] = {
		CommandSectorAnchor,
		ProductionSectorAnchor,
		IntelligenceSectorAnchor,
		GovernanceSectorAnchor,
		SystemsSectorAnchor,
	};
	const double RadiusCm = MuseUniverseMath::MetersToCentimeters(581.0);
	for (int32 Index = 0; Index < 5; ++Index)
	{
		const double AngleDegrees = 18.0 + Index * 72.0;
		const double AngleRadians = FMath::DegreesToRadians(AngleDegrees);
		const FVector Location(
			RadiusCm * FMath::Cos(AngleRadians),
			RadiusCm * FMath::Sin(AngleRadians),
			0.0);
		const FRotator Rotation(0.0, AngleDegrees + 90.0, 0.0);
		SectorCues->AddInstance(FTransform(Rotation, Location, FVector(90.0, 24.0, 18.0)));
		Anchors[Index]->SetRelativeLocationAndRotation(Location, Rotation);
	}
}

void AAtlasCrownActor::Tick(const float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bAnimateCrown)
	{
		return;
	}
	const std::pair<double, double> AngularVelocities =
		MuseUniverseMath::CounterRotationPair(RingDegreesPerSecond);
	RingAAngleDegrees = FMath::Fmod(
		RingAAngleDegrees + AngularVelocities.first * DeltaSeconds,
		360.0);
	RingBAngleDegrees = FMath::Fmod(
		RingBAngleDegrees + AngularVelocities.second * DeltaSeconds,
		360.0);
	CrownRingA->SetRelativeRotation(FRotator(0.0, RingAAngleDegrees, 0.0));
	CrownRingB->SetRelativeRotation(FRotator(0.0, RingBAngleDegrees, 0.0));
}

void AAtlasCrownActor::ApplyStationProjection(
	const FMuseStationProjection& Projection)
{
	Tags.AddUnique(FName(*Projection.Base.Id));
	SetActorHiddenInGame(Projection.Base.Id.IsEmpty());
}
