#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "MuseUniverseRuntimeSettings.generated.h"

UENUM(BlueprintType)
enum class EMuseDeliveryMode : uint8
{
	LocalNative,
	OpenXR,
	PixelStreaming,
	Accessible2D,
};

UENUM(BlueprintType)
enum class EMuseFidelityTier : uint8
{
	Auto,
	Cinema,
	Ultra,
	High,
	Balanced,
	Accessible2D,
};

USTRUCT(BlueprintType)
struct FMuseRuntimeSelection
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) EMuseDeliveryMode DeliveryMode = EMuseDeliveryMode::LocalNative;
	UPROPERTY(BlueprintReadOnly) EMuseFidelityTier FidelityTier = EMuseFidelityTier::Balanced;
	UPROPERTY(BlueprintReadOnly) FString SelectedTierReason;
	UPROPERTY(BlueprintReadOnly) FString ExternalEndpoint;
	UPROPERTY(BlueprintReadOnly) bool bValid = true;
	UPROPERTY(BlueprintReadOnly) bool bFallbackTo2D = false;
};

/** Non-secret runtime selection. Endpoint values come from the environment. */
UCLASS(Config = Game, DefaultConfig, meta = (DisplayName = "M.U.S.E. Atlas Runtime"))
class SYNAPSEUNIVERSE_API UMuseUniverseRuntimeSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	UMuseUniverseRuntimeSettings();

	UFUNCTION(BlueprintPure, Category = "M.U.S.E.|Runtime")
	FMuseRuntimeSelection ResolveRuntimeSelection() const;

	UPROPERTY(Config, EditAnywhere, Category = "Delivery")
	EMuseDeliveryMode PreferredDeliveryMode = EMuseDeliveryMode::LocalNative;

	UPROPERTY(Config, EditAnywhere, Category = "Fidelity")
	EMuseFidelityTier PreferredFidelityTier = EMuseFidelityTier::Auto;

	UPROPERTY(Config, EditAnywhere, Category = "Pixel Streaming")
	bool bAutoStartPixelStreaming = false;

	UPROPERTY(Config, EditAnywhere, Category = "Pixel Streaming")
	FString PixelStreamingUrlEnvironment = TEXT("MUSE_PIXEL_STREAMING_URL");

	UPROPERTY(Config, EditAnywhere, Category = "Pixel Streaming")
	bool bRequireTlsForExternal = true;

	UPROPERTY(Config, EditAnywhere, Category = "OpenXR")
	bool bOpenXREnabledByUser = false;

	UPROPERTY(Config, EditAnywhere, Category = "OpenXR", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	double ComfortVignetteStrength = 0.35;

	UPROPERTY(Config, EditAnywhere, Category = "OpenXR")
	double SnapTurnDegrees = 30.0;

	UPROPERTY(Config, EditAnywhere, Category = "Fallback")
	bool bFallbackToAccessible2D = true;
};

