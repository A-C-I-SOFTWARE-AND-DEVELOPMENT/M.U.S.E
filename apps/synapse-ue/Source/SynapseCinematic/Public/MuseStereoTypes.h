#pragma once

#include "CoreMinimal.h"
#include "MuseStereoTypes.generated.h"

UENUM(BlueprintType)
enum class EMuseStereoPolicy : uint8
{
	SymmetricOffAxis,
	SymmetricToeIn,
};

UENUM(BlueprintType)
enum class EMuseStereoEye : uint8
{
	Left,
	Right,
};

USTRUCT(BlueprintType)
struct FMuseStereoShotMetadata
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite) FString ShotId;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FString SceneRevision;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 DeterministicSeed = 1;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) EMuseStereoPolicy StereoPolicy = EMuseStereoPolicy::SymmetricToeIn;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, meta = (ClampMin = "1.0", ClampMax = "1000.0"))
	double InteraxialMillimeters = 65.0;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, meta = (ClampMin = "0.1"))
	double ConvergenceDistanceMeters = 10.0;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, meta = (ClampMin = "0.1"))
	double ZeroParallaxDistanceMeters = 10.0;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, meta = (ClampMin = "0.1"))
	double FocalDistanceMeters = 10.0;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, meta = (ClampMin = "1.0"))
	double LensMillimeters = 35.0;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, meta = (ClampMin = "0.1"))
	double Aperture = 5.6;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, meta = (ClampMin = "0.001"))
	double NearClipMeters = 0.05;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, meta = (ClampMin = "1.0"))
	double FarClipMeters = 100000.0;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, meta = (ClampMin = "0.1"))
	double DisplayWidthMeters = 20.0;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, meta = (ClampMin = "0.1"))
	double DisplayHeightMeters = 10.526315789;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, meta = (ClampMin = "0.0", ClampMax = "10.0"))
	double DepthBudgetPercent = 2.0;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bProtectSafeGuide190 = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bProtectSafeGuide143 = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bPostConvertedDepthCard = false;
};

USTRUCT(BlueprintType)
struct FMuseStereoRenderSettings
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite) FIntPoint OutputResolution = FIntPoint(4096, 2160);
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FFrameRate OutputFrameRate = FFrameRate(24, 1);
	UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 SpatialSamples = 8;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 TemporalSamples = 8;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) double ExposureCompensation = 0.0;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) double MotionBlurAmount = 0.5;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bDepthOfField = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bVolumetrics = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bReflections = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bRefraction = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FString ColorPipeline = TEXT("ACES 2.0");
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FString OutputFormat = TEXT("OpenEXR 16-bit half");
};

USTRUCT(BlueprintType)
struct FMuseEyeRenderJob
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) EMuseStereoEye Eye = EMuseStereoEye::Left;
	UPROPERTY(BlueprintReadOnly) FString EyeCode;
	UPROPERTY(BlueprintReadOnly) FString CameraBinding;
	UPROPERTY(BlueprintReadOnly) FString ShotId;
	UPROPERTY(BlueprintReadOnly) FString SceneRevision;
	UPROPERTY(BlueprintReadOnly) int32 DeterministicSeed = 0;
	UPROPERTY(BlueprintReadOnly) FString FileNameFormat;
	UPROPERTY(BlueprintReadOnly) FString MetadataHash;
	UPROPERTY(BlueprintReadOnly) FString CanonicalMetadataJson;
};

USTRUCT(BlueprintType)
struct FMuseFrameRecord
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) FString ShotId;
	UPROPERTY(BlueprintReadOnly) EMuseStereoEye Eye = EMuseStereoEye::Left;
	UPROPERTY(BlueprintReadOnly) int32 FrameNumber = 0;
	UPROPERTY(BlueprintReadOnly) int32 Attempt = 1;
	UPROPERTY(BlueprintReadOnly) FString FrameHash;
	UPROPERTY(BlueprintReadOnly) FString OutputPath;
	UPROPERTY(BlueprintReadOnly) double PresentationTimeSeconds = 0.0;
	UPROPERTY(BlueprintReadOnly) double VerticalAlignmentPixels = 0.0;
};

USTRUCT(BlueprintType)
struct FMuseStereoQcResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) bool bPassed = false;
	UPROPERTY(BlueprintReadOnly) TArray<FString> Diagnostics;
	UPROPERTY(BlueprintReadOnly) FString MetadataHash;
};
