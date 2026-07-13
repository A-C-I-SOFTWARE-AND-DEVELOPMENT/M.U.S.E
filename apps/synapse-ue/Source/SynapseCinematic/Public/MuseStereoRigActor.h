#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MuseStereoTypes.h"
#include "MuseStereoRigActor.generated.h"

class UCineCameraComponent;
class USceneComponent;
class UStaticMeshComponent;

/** Two physical cameras derived symmetrically from one metric rig transform. */
UCLASS(BlueprintType)
class SYNAPSECINEMATIC_API AMuseStereoRigActor : public AActor
{
	GENERATED_BODY()

public:
	AMuseStereoRigActor();

	UFUNCTION(BlueprintCallable, Category = "M.U.S.E.|Stereo")
	bool ApplyShotMetadata(const FMuseStereoShotMetadata& Metadata, FString& OutDiagnostic);

	UFUNCTION(BlueprintPure, Category = "M.U.S.E.|Stereo")
	FMuseStereoQcResult EvaluateComfort() const;

	UFUNCTION(BlueprintPure, Category = "M.U.S.E.|Stereo")
	FTransform GetConvergencePlaneTransform() const;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Stereo")
	TObjectPtr<USceneComponent> RigRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Stereo")
	TObjectPtr<UCineCameraComponent> LeftEyeCamera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Stereo")
	TObjectPtr<UCineCameraComponent> RightEyeCamera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Stereo")
	TObjectPtr<UStaticMeshComponent> ConvergencePlane;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Stereo")
	TObjectPtr<UStaticMeshComponent> SafeGuide190;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "M.U.S.E.|Stereo")
	TObjectPtr<UStaticMeshComponent> SafeGuide143;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "M.U.S.E.|Stereo")
	FMuseStereoShotMetadata ShotMetadata;

	UPROPERTY(BlueprintReadOnly, Category = "M.U.S.E.|Stereo")
	bool bRequiresPostProjectionShift = false;
};

