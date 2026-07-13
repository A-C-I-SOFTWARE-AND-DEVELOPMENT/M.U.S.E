#include "MuseUniverseRuntimeSettings.h"

#include "GenericPlatform/GenericPlatformMisc.h"

namespace
{
	bool IsLoopbackWebSocket(const FString& Url)
	{
		const FString Lower = Url.ToLower();
		return Lower.StartsWith(TEXT("ws://127.0.0.1:")) ||
			Lower.StartsWith(TEXT("ws://localhost:")) ||
			Lower.StartsWith(TEXT("ws://[::1]:")) ||
			Lower.StartsWith(TEXT("wss://127.0.0.1:")) ||
			Lower.StartsWith(TEXT("wss://localhost:")) ||
			Lower.StartsWith(TEXT("wss://[::1]:"));
	}

	bool IsSafeEndpointShape(const FString& Url)
	{
		return !Url.Contains(TEXT("@")) &&
			!Url.Contains(TEXT("?")) &&
			!Url.Contains(TEXT("#")) &&
			(Url.StartsWith(TEXT("ws://"), ESearchCase::IgnoreCase) ||
			 Url.StartsWith(TEXT("wss://"), ESearchCase::IgnoreCase));
	}
}

UMuseUniverseRuntimeSettings::UMuseUniverseRuntimeSettings()
{
	CategoryName = TEXT("Project");
	SectionName = TEXT("M.U.S.E. Atlas Runtime");
}

FMuseRuntimeSelection UMuseUniverseRuntimeSettings::ResolveRuntimeSelection() const
{
	FMuseRuntimeSelection Selection;
	Selection.DeliveryMode = PreferredDeliveryMode;
	Selection.FidelityTier = PreferredFidelityTier == EMuseFidelityTier::Auto
		? EMuseFidelityTier::Balanced
		: PreferredFidelityTier;
	Selection.SelectedTierReason = PreferredFidelityTier == EMuseFidelityTier::Auto
		? TEXT("Auto selected Balanced until measured GPU capability promotes the tier")
		: TEXT("Explicit user fidelity preference");

	if (PreferredDeliveryMode == EMuseDeliveryMode::OpenXR && !bOpenXREnabledByUser)
	{
		Selection.bValid = false;
		Selection.SelectedTierReason = TEXT("OpenXR requested without explicit user enablement");
	}
	else if (PreferredDeliveryMode == EMuseDeliveryMode::PixelStreaming)
	{
		Selection.ExternalEndpoint = FGenericPlatformMisc::GetEnvironmentVariable(
			*PixelStreamingUrlEnvironment);
		if (bAutoStartPixelStreaming || Selection.ExternalEndpoint.IsEmpty() ||
			!IsSafeEndpointShape(Selection.ExternalEndpoint) ||
			(bRequireTlsForExternal && !IsLoopbackWebSocket(Selection.ExternalEndpoint) &&
			 !Selection.ExternalEndpoint.StartsWith(TEXT("wss://"), ESearchCase::IgnoreCase)))
		{
			Selection.bValid = false;
			Selection.SelectedTierReason = TEXT(
				"Pixel Streaming requires an explicit safe environment endpoint; external endpoints require TLS");
			Selection.ExternalEndpoint.Reset();
		}
	}

	if (!Selection.bValid && bFallbackToAccessible2D)
	{
		Selection.DeliveryMode = EMuseDeliveryMode::Accessible2D;
		Selection.FidelityTier = EMuseFidelityTier::Accessible2D;
		Selection.bFallbackTo2D = true;
	}
	return Selection;
}

