#include "MuseStereoRigActor.h"

#include "CineCameraComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Kismet/KismetMathLibrary.h"
#include "MuseUniverseMath.h"
#include "UObject/ConstructorHelpers.h"

AMuseStereoRigActor::AMuseStereoRigActor()
{
	PrimaryActorTick.bCanEverTick = false;
	RigRoot = CreateDefaultSubobject<USceneComponent>(TEXT("MetricStereoRigRoot"));
	SetRootComponent(RigRoot);
	LeftEyeCamera = CreateDefaultSubobject<UCineCameraComponent>(TEXT("LeftEyeCamera"));
	LeftEyeCamera->SetupAttachment(RigRoot);
	RightEyeCamera = CreateDefaultSubobject<UCineCameraComponent>(TEXT("RightEyeCamera"));
	RightEyeCamera->SetupAttachment(RigRoot);
	ConvergencePlane = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ConvergencePlane"));
	ConvergencePlane->SetupAttachment(RigRoot);
	SafeGuide190 = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("SafeGuide190"));
	SafeGuide190->SetupAttachment(RigRoot);
	SafeGuide143 = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("SafeGuide143"));
	SafeGuide143->SetupAttachment(RigRoot);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> PlaneMesh(
		TEXT("/Engine/BasicShapes/Plane.Plane"));
	if (PlaneMesh.Succeeded())
	{
		ConvergencePlane->SetStaticMesh(PlaneMesh.Object);
		SafeGuide190->SetStaticMesh(PlaneMesh.Object);
		SafeGuide143->SetStaticMesh(PlaneMesh.Object);
	}
	UStaticMeshComponent* Guides[] = {
		ConvergencePlane,
		SafeGuide190,
		SafeGuide143,
	};
	for (UStaticMeshComponent* Guide : Guides)
	{
		Guide->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Guide->SetHiddenInGame(true);
	}

	FString Diagnostic;
	ApplyShotMetadata(ShotMetadata, Diagnostic);
}

bool AMuseStereoRigActor::ApplyShotMetadata(
	const FMuseStereoShotMetadata& Metadata,
	FString& OutDiagnostic)
{
	if (Metadata.bPostConvertedDepthCard)
	{
		OutDiagnostic = TEXT("Post-converted depth cards are not native stereo masters");
		return false;
	}
	if (Metadata.InteraxialMillimeters <= 0.0 ||
		Metadata.ConvergenceDistanceMeters <= 0.0 ||
		Metadata.ZeroParallaxDistanceMeters <= 0.0 ||
		Metadata.DisplayWidthMeters <= 0.0 ||
		Metadata.DisplayHeightMeters <= 0.0 ||
		Metadata.DepthBudgetPercent <= 0.0)
	{
		OutDiagnostic = TEXT("stereo geometry and display metadata must be positive");
		return false;
	}
	if (Metadata.StereoPolicy == EMuseStereoPolicy::SymmetricOffAxis)
	{
		OutDiagnostic = TEXT(
			"off-axis stereo requires a verified projection-matrix extension; use symmetric toe-in until that environment gate closes");
		return false;
	}

	ShotMetadata = Metadata;
	const double HalfInteraxialCm = Metadata.InteraxialMillimeters / 20.0;
	LeftEyeCamera->SetRelativeLocation(FVector(0.0, -HalfInteraxialCm, 0.0));
	RightEyeCamera->SetRelativeLocation(FVector(0.0, +HalfInteraxialCm, 0.0));
	LeftEyeCamera->SetCurrentFocalLength(Metadata.LensMillimeters);
	RightEyeCamera->SetCurrentFocalLength(Metadata.LensMillimeters);
	LeftEyeCamera->SetCurrentAperture(static_cast<float>(Metadata.Aperture));
	RightEyeCamera->SetCurrentAperture(static_cast<float>(Metadata.Aperture));
	LeftEyeCamera->bOverride_CustomNearClippingPlane = true;
	RightEyeCamera->bOverride_CustomNearClippingPlane = true;
	LeftEyeCamera->SetCustomNearClippingPlane(static_cast<float>(
		MuseUniverseMath::MetersToCentimeters(Metadata.NearClipMeters)));
	RightEyeCamera->SetCustomNearClippingPlane(static_cast<float>(
		MuseUniverseMath::MetersToCentimeters(Metadata.NearClipMeters)));
	LeftEyeCamera->FocusSettings.ManualFocusDistance =
		MuseUniverseMath::MetersToCentimeters(Metadata.FocalDistanceMeters);
	RightEyeCamera->FocusSettings.ManualFocusDistance =
		MuseUniverseMath::MetersToCentimeters(Metadata.FocalDistanceMeters);

	const FVector ConvergenceTarget(
		MuseUniverseMath::MetersToCentimeters(Metadata.ConvergenceDistanceMeters),
		0.0,
		0.0);
	LeftEyeCamera->SetRelativeRotation(UKismetMathLibrary::FindLookAtRotation(
		LeftEyeCamera->GetRelativeLocation(), ConvergenceTarget));
	RightEyeCamera->SetRelativeRotation(UKismetMathLibrary::FindLookAtRotation(
		RightEyeCamera->GetRelativeLocation(), ConvergenceTarget));
	bRequiresPostProjectionShift = false;

	ConvergencePlane->SetRelativeLocation(ConvergenceTarget);
	ConvergencePlane->SetRelativeRotation(FRotator(0.0, 90.0, 0.0));
	ConvergencePlane->SetRelativeScale3D(FVector(
		Metadata.DisplayHeightMeters,
		Metadata.DisplayWidthMeters,
		1.0));
	SafeGuide190->SetRelativeTransform(ConvergencePlane->GetRelativeTransform());
	SafeGuide190->SetRelativeScale3D(FVector(
		Metadata.DisplayHeightMeters,
		Metadata.DisplayHeightMeters * 1.90,
		1.0));
	SafeGuide143->SetRelativeTransform(ConvergencePlane->GetRelativeTransform());
	SafeGuide143->SetRelativeScale3D(FVector(
		Metadata.DisplayHeightMeters,
		Metadata.DisplayHeightMeters * 1.43,
		1.0));
	OutDiagnostic = TEXT("symmetric toe-in physical cameras configured");
	return true;
}

FMuseStereoQcResult AMuseStereoRigActor::EvaluateComfort() const
{
	FMuseStereoQcResult Result;
	if (ShotMetadata.bPostConvertedDepthCard)
	{
		Result.Diagnostics.Add(TEXT("post-converted depth card rejected"));
	}
	if (ShotMetadata.InteraxialMillimeters > 75.0)
	{
		Result.Diagnostics.Add(TEXT("interaxial exceeds the default comfort review threshold"));
	}
	if (ShotMetadata.DepthBudgetPercent > 3.0)
	{
		Result.Diagnostics.Add(TEXT("depth budget exceeds the default theatrical review threshold"));
	}
	if (ShotMetadata.ConvergenceDistanceMeters < ShotMetadata.NearClipMeters)
	{
		Result.Diagnostics.Add(TEXT("convergence plane is behind the near clip"));
	}
	Result.bPassed = Result.Diagnostics.IsEmpty();
	return Result;
}

FTransform AMuseStereoRigActor::GetConvergencePlaneTransform() const
{
	return ConvergencePlane->GetComponentTransform();
}
