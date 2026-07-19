#include "MuseRenderManifestSubsystem.h"

#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "LevelSequence.h"
#include "Misc/FileHelper.h"
#include "MoviePipelineAntiAliasingSetting.h"
#include "MoviePipelineOutputSetting.h"
#include "MoviePipelinePrimaryConfig.h"
#include "MoviePipelineQueue.h"
#include "MoviePipelineQueueEngineSubsystem.h"
#include "MuseUniverseMath.h"
#include "Serialization/JsonSerializer.h"
#include "SynapseCinematic.h"

FString UMuseRenderManifestSubsystem::EyeCode(const EMuseStereoEye Eye)
{
	return Eye == EMuseStereoEye::Left ? TEXT("L") : TEXT("R");
}

bool UMuseRenderManifestSubsystem::RejectPostConvertedDepthCard(
	const FMuseStereoShotMetadata& Shot,
	FString& OutError)
{
	if (!Shot.bPostConvertedDepthCard)
	{
		return false;
	}
	OutError = TEXT(
		"PostConverted input rejected: a depth-card conversion cannot be labeled or queued as native stereo");
	return true;
}

FString UMuseRenderManifestSubsystem::BuildCanonicalMetadataJson(
	const FMuseStereoShotMetadata& Shot,
	const FMuseStereoRenderSettings& Settings,
	const EMuseStereoEye Eye)
{
	// Field insertion order is fixed and becomes the version-1 canonical form.
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("color_pipeline"), Settings.ColorPipeline);
	Root->SetNumberField(TEXT("convergence_distance_m"), Shot.ConvergenceDistanceMeters);
	Root->SetNumberField(TEXT("depth_budget_percent"), Shot.DepthBudgetPercent);
	Root->SetNumberField(TEXT("deterministic_seed"), Shot.DeterministicSeed);
	Root->SetNumberField(TEXT("display_height_m"), Shot.DisplayHeightMeters);
	Root->SetNumberField(TEXT("display_width_m"), Shot.DisplayWidthMeters);
	Root->SetBoolField(TEXT("dof"), Settings.bDepthOfField);
	Root->SetStringField(TEXT("eye"), EyeCode(Eye));
	Root->SetStringField(
		TEXT("eye_camera_binding"),
		Eye == EMuseStereoEye::Left ? TEXT("LeftEyeCamera") : TEXT("RightEyeCamera"));
	Root->SetNumberField(TEXT("exposure_compensation"), Settings.ExposureCompensation);
	Root->SetNumberField(TEXT("frame_rate_denominator"), Settings.OutputFrameRate.Denominator);
	Root->SetNumberField(TEXT("frame_rate_numerator"), Settings.OutputFrameRate.Numerator);
	Root->SetNumberField(TEXT("interaxial_mm"), Shot.InteraxialMillimeters);
	Root->SetNumberField(TEXT("lens_mm"), Shot.LensMillimeters);
	Root->SetNumberField(TEXT("motion_blur"), Settings.MotionBlurAmount);
	Root->SetStringField(TEXT("output_format"), Settings.OutputFormat);
	Root->SetNumberField(TEXT("resolution_x"), Settings.OutputResolution.X);
	Root->SetNumberField(TEXT("resolution_y"), Settings.OutputResolution.Y);
	Root->SetBoolField(TEXT("reflections"), Settings.bReflections);
	Root->SetBoolField(TEXT("refraction"), Settings.bRefraction);
	Root->SetStringField(TEXT("scene_revision"), Shot.SceneRevision);
	Root->SetStringField(TEXT("shot_id"), Shot.ShotId);
	Root->SetNumberField(TEXT("spatial_samples"), Settings.SpatialSamples);
	Root->SetNumberField(TEXT("temporal_samples"), Settings.TemporalSamples);
	Root->SetBoolField(TEXT("volumetrics"), Settings.bVolumetrics);
	Root->SetNumberField(TEXT("zero_parallax_distance_m"), Shot.ZeroParallaxDistanceMeters);
	FString Json;
	const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Json);
	FJsonSerializer::Serialize(Root, Writer);
	return Json;
}

TArray<FMuseEyeRenderJob> UMuseRenderManifestSubsystem::BuildNativeStereoJobs(
	const FMuseStereoShotMetadata& Shot,
	const FMuseStereoRenderSettings& Settings) const
{
	TArray<FMuseEyeRenderJob> Jobs;
	for (const EMuseStereoEye Eye : {EMuseStereoEye::Left, EMuseStereoEye::Right})
	{
		FMuseEyeRenderJob Descriptor;
		Descriptor.Eye = Eye;
		Descriptor.EyeCode = EyeCode(Eye);
		Descriptor.CameraBinding = Eye == EMuseStereoEye::Left
			? TEXT("LeftEyeCamera") : TEXT("RightEyeCamera");
		Descriptor.ShotId = Shot.ShotId;
		Descriptor.SceneRevision = Shot.SceneRevision;
		Descriptor.DeterministicSeed = Shot.DeterministicSeed;
		Descriptor.FileNameFormat = Eye == EMuseStereoEye::Left
			? TEXT("{shot_name}/eye_L/{frame_number}")
			: TEXT("{shot_name}/eye_R/{frame_number}");
		Descriptor.CanonicalMetadataJson =
			BuildCanonicalMetadataJson(Shot, Settings, Eye);
		const std::string Utf8(TCHAR_TO_UTF8(*Descriptor.CanonicalMetadataJson));
		Descriptor.MetadataHash = UTF8_TO_TCHAR(
			MuseUniverseMath::DeterministicShotHash(Utf8).c_str());
		Jobs.Add(Descriptor);
	}
	return Jobs;
}

void UMuseRenderManifestSubsystem::ConfigureMoviePipelineJob(
	UMoviePipelineExecutorJob* Job,
	const FMuseEyeRenderJob& Descriptor,
	const FMuseStereoRenderSettings& Settings,
	const FSoftObjectPath& Sequence,
	const FSoftObjectPath& Map)
{
	check(Job);
	Job->JobName = FString::Printf(
		TEXT("%s_eye_%s"), *Descriptor.ShotId, *Descriptor.EyeCode);
	Job->Author = TEXT("M.U.S.E. SynapseCinematic");
	Job->Comment = FString::Printf(
		TEXT("Native physical eye %s (%s); SceneRevision=%s; DeterministicSeed=%d; ACES=%s"),
		*Descriptor.EyeCode,
		*Descriptor.CameraBinding,
		*Descriptor.SceneRevision,
		Descriptor.DeterministicSeed,
		*Settings.ColorPipeline);
	Job->UserData = Descriptor.CanonicalMetadataJson;
	Job->SetSequence(Sequence);
	Job->Map = Map;

	UMoviePipelinePrimaryConfig* Config = Job->GetConfiguration();
	check(Config);
	auto* Output = CastChecked<UMoviePipelineOutputSetting>(
		Config->FindOrAddSettingByClass(
			UMoviePipelineOutputSetting::StaticClass(), true, false));
	Output->FileNameFormat = Descriptor.FileNameFormat;
	Output->OutputResolution = Settings.OutputResolution;
	Output->bUseCustomFrameRate = true;
	Output->OutputFrameRate = Settings.OutputFrameRate;
	Output->bOverrideExistingOutput = false;
	Output->ZeroPadFrameNumbers = 6;

	auto* AntiAliasing = CastChecked<UMoviePipelineAntiAliasingSetting>(
		Config->FindOrAddSettingByClass(
			UMoviePipelineAntiAliasingSetting::StaticClass(), true, false));
	AntiAliasing->SpatialSampleCount = FMath::Max(1, Settings.SpatialSamples);
	AntiAliasing->TemporalSampleCount = FMath::Max(1, Settings.TemporalSamples);

	// Path tracer deferred pass disabled — requires MovieRenderPipelineRenderPasses
	// which has an unresolvable OpenEXR/Imath dependency in this UE 5.7 install.
}

bool UMuseRenderManifestSubsystem::QueueNativeStereoRender(
	ULevelSequence* LeftEyeSequence,
	ULevelSequence* RightEyeSequence,
	const FSoftObjectPath& Map,
	const FMuseStereoShotMetadata& Shot,
	const FMuseStereoRenderSettings& Settings,
	FString& OutError)
{
	if (!LeftEyeSequence || !RightEyeSequence ||
		Shot.ShotId.IsEmpty() || Shot.SceneRevision.IsEmpty())
	{
		OutError = TEXT(
			"left/right physical-eye sequences, shot id, and scene revision are required");
		return false;
	}
	if (RejectPostConvertedDepthCard(Shot, OutError))
	{
		return false;
	}
	if (Shot.StereoPolicy == EMuseStereoPolicy::SymmetricOffAxis)
	{
		OutError = TEXT(
			"off-axis jobs are blocked until a UE 5.6 projection-matrix extension is verified; queue symmetric toe-in physical cameras instead");
		return false;
	}
	UMoviePipelineQueueEngineSubsystem* QueueSubsystem =
		GEngine ? GEngine->GetEngineSubsystem<UMoviePipelineQueueEngineSubsystem>() : nullptr;
	if (!QueueSubsystem || QueueSubsystem->IsRendering())
	{
		OutError = TEXT("Movie Render Queue runtime subsystem is unavailable or busy");
		return false;
	}
	UMoviePipelineQueue* Queue = QueueSubsystem->GetQueue();
	if (!Queue)
	{
		OutError = TEXT("Movie Render Queue did not provide a queue");
		return false;
	}

	const TArray<FMuseEyeRenderJob> Descriptors = BuildNativeStereoJobs(Shot, Settings);
	for (const FMuseEyeRenderJob& Descriptor : Descriptors)
	{
		ULevelSequence* EyeSequence = Descriptor.Eye == EMuseStereoEye::Left
			? LeftEyeSequence : RightEyeSequence;
		UMoviePipelineExecutorJob* Job = Queue->AllocateNewJob(
			UMoviePipelineExecutorJob::StaticClass());
		ConfigureMoviePipelineJob(
			Job,
			Descriptor,
			Settings,
			FSoftObjectPath(EyeSequence->GetPathName()),
			Map);
	}
	OutError.Reset();
	return true;
}

bool UMuseRenderManifestSubsystem::RecordFrame(
	const FString& ShotId,
	const EMuseStereoEye Eye,
	const int32 FrameNumber,
	const int32 Attempt,
	const double PresentationTimeSeconds,
	const double VerticalAlignmentPixels,
	const FString& OutputPath,
	FMuseFrameRecord& OutRecord,
	FString& OutError)
{
	TArray<uint8> Bytes;
	if (ShotId.IsEmpty() || Attempt < 1 ||
		!FFileHelper::LoadFileToArray(Bytes, *OutputPath) || Bytes.IsEmpty())
	{
		OutError = TEXT("frame output is missing, empty, or has invalid metadata");
		return false;
	}
	const std::string Binary(
		reinterpret_cast<const char*>(Bytes.GetData()),
		static_cast<std::size_t>(Bytes.Num()));
	OutRecord.ShotId = ShotId;
	OutRecord.Eye = Eye;
	OutRecord.FrameNumber = FrameNumber;
	OutRecord.Attempt = Attempt;
	OutRecord.FrameHash = UTF8_TO_TCHAR(MuseUniverseMath::Sha256Hex(Binary).c_str());
	OutRecord.OutputPath = OutputPath;
	OutRecord.PresentationTimeSeconds = PresentationTimeSeconds;
	OutRecord.VerticalAlignmentPixels = VerticalAlignmentPixels;
	FrameRecords.Add(OutRecord);
	OutError.Reset();
	return true;
}

FMuseStereoQcResult UMuseRenderManifestSubsystem::ValidateEyePair(
	const FMuseStereoShotMetadata& Shot,
	const TArray<FMuseFrameRecord>& LeftFrames,
	const TArray<FMuseFrameRecord>& RightFrames) const
{
	FMuseStereoQcResult Result;
	FString PostConversionError;
	if (RejectPostConvertedDepthCard(Shot, PostConversionError))
	{
		Result.Diagnostics.Add(PostConversionError);
	}
	if (LeftFrames.Num() != RightFrames.Num() || LeftFrames.IsEmpty())
	{
		Result.Diagnostics.Add(TEXT("left/right frame counts are missing or unequal"));
	}
	const int32 PairCount = FMath::Min(LeftFrames.Num(), RightFrames.Num());
	for (int32 Index = 0; Index < PairCount; ++Index)
	{
		const FMuseFrameRecord& Left = LeftFrames[Index];
		const FMuseFrameRecord& Right = RightFrames[Index];
		if (Left.Eye != EMuseStereoEye::Left || Right.Eye != EMuseStereoEye::Right)
		{
			Result.Diagnostics.Add(TEXT("eye labels are not L/R ordered"));
		}
		if (Left.FrameNumber != Right.FrameNumber)
		{
			Result.Diagnostics.Add(FString::Printf(
				TEXT("frame parity mismatch at pair %d"), Index));
		}
		if (!FMath::IsNearlyEqual(
			Left.PresentationTimeSeconds,
			Right.PresentationTimeSeconds,
			1e-6))
		{
			Result.Diagnostics.Add(FString::Printf(
				TEXT("temporal sync mismatch at frame %d"), Left.FrameNumber));
		}
		if (Left.FrameHash.IsEmpty() || Right.FrameHash.IsEmpty())
		{
			Result.Diagnostics.Add(FString::Printf(
				TEXT("checksum missing at frame %d"), Left.FrameNumber));
		}
		if (FMath::Abs(Left.VerticalAlignmentPixels - Right.VerticalAlignmentPixels) > 0.5)
		{
			Result.Diagnostics.Add(FString::Printf(
				TEXT("vertical alignment exceeds 0.5 px at frame %d"), Left.FrameNumber));
		}
	}
	const FString Canonical = FString::Printf(
		TEXT("{\"depth_budget_percent\":%.9g,\"interaxial_mm\":%.9g,\"pairs\":%d,\"scene_revision\":\"%s\",\"shot_id\":\"%s\"}"),
		Shot.DepthBudgetPercent,
		Shot.InteraxialMillimeters,
		PairCount,
		*Shot.SceneRevision.ReplaceCharWithEscapedChar(),
		*Shot.ShotId.ReplaceCharWithEscapedChar());
	const std::string Utf8(TCHAR_TO_UTF8(*Canonical));
	Result.MetadataHash = UTF8_TO_TCHAR(
		MuseUniverseMath::DeterministicShotHash(Utf8).c_str());
	Result.bPassed = Result.Diagnostics.IsEmpty();
	return Result;
}

FString UMuseRenderManifestSubsystem::BuildQcSubmissionJson(
	const FMuseStereoShotMetadata& Shot,
	const FMuseStereoQcResult& Result) const
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("shot_id"), Shot.ShotId);
	Root->SetStringField(TEXT("scene_revision"), Shot.SceneRevision);
	Root->SetStringField(TEXT("metadata_hash"), Result.MetadataHash);
	Root->SetBoolField(TEXT("passed"), Result.bPassed);
	TArray<TSharedPtr<FJsonValue>> Diagnostics;
	for (const FString& Diagnostic : Result.Diagnostics)
	{
		Diagnostics.Add(MakeShared<FJsonValueString>(Diagnostic));
	}
	Root->SetArrayField(TEXT("diagnostics"), Diagnostics);
	FString Json;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
	FJsonSerializer::Serialize(Root, Writer);
	return Json;
}
