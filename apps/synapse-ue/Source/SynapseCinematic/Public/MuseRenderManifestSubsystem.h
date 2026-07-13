#pragma once

#include "CoreMinimal.h"
#include "Subsystems/EngineSubsystem.h"
#include "MuseStereoTypes.h"
#include "MuseRenderManifestSubsystem.generated.h"

class ULevelSequence;
class UMoviePipelineExecutorJob;

/** Builds paired MRQ jobs and immutable evidence records for native stereo. */
UCLASS()
class SYNAPSECINEMATIC_API UMuseRenderManifestSubsystem : public UEngineSubsystem
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "M.U.S.E.|Stereo Render")
	TArray<FMuseEyeRenderJob> BuildNativeStereoJobs(
		const FMuseStereoShotMetadata& Shot,
		const FMuseStereoRenderSettings& Settings) const;

	UFUNCTION(BlueprintCallable, Category = "M.U.S.E.|Stereo Render")
	bool QueueNativeStereoRender(
		ULevelSequence* LeftEyeSequence,
		ULevelSequence* RightEyeSequence,
		const FSoftObjectPath& Map,
		const FMuseStereoShotMetadata& Shot,
		const FMuseStereoRenderSettings& Settings,
		FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "M.U.S.E.|Stereo Render")
	bool RecordFrame(
		const FString& ShotId,
		EMuseStereoEye Eye,
		int32 FrameNumber,
		int32 Attempt,
		double PresentationTimeSeconds,
		double VerticalAlignmentPixels,
		const FString& OutputPath,
		FMuseFrameRecord& OutRecord,
		FString& OutError);

	UFUNCTION(BlueprintPure, Category = "M.U.S.E.|Stereo Render")
	FMuseStereoQcResult ValidateEyePair(
		const FMuseStereoShotMetadata& Shot,
		const TArray<FMuseFrameRecord>& LeftFrames,
		const TArray<FMuseFrameRecord>& RightFrames) const;

	UFUNCTION(BlueprintPure, Category = "M.U.S.E.|Stereo Render")
	FString BuildQcSubmissionJson(
		const FMuseStereoShotMetadata& Shot,
		const FMuseStereoQcResult& Result) const;

	UFUNCTION(BlueprintPure, Category = "M.U.S.E.|Stereo Render")
	TArray<FMuseFrameRecord> GetFrameRecords() const { return FrameRecords; }

	static bool RejectPostConvertedDepthCard(
		const FMuseStereoShotMetadata& Shot,
		FString& OutError);

private:
	static FString BuildCanonicalMetadataJson(
		const FMuseStereoShotMetadata& Shot,
		const FMuseStereoRenderSettings& Settings,
		EMuseStereoEye Eye);
	static FString EyeCode(EMuseStereoEye Eye);
	static void ConfigureMoviePipelineJob(
		UMoviePipelineExecutorJob* Job,
		const FMuseEyeRenderJob& Descriptor,
		const FMuseStereoRenderSettings& Settings,
		const FSoftObjectPath& Sequence,
		const FSoftObjectPath& Map);

	UPROPERTY(Transient) TArray<FMuseFrameRecord> FrameRecords;
};
