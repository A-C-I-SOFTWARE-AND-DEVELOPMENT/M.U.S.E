// ObservatoryRenderSettings — project settings + console vars for the galaxy.
// Copyright A-C-I Software & Development. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "MuseSacredGeometry.h"
#include "ObservatoryRenderTypes.h"
#include "ObservatoryRenderSettings.generated.h"

/**
 * Project-wide defaults for the sacred-geometry galaxy renderer
 * (Project Settings -> Plugins -> "MUSE Observatory Render"). Mirrored by the
 * `muse.Observatory.*` console variables (see ObservatoryRenderSettings.cpp) so
 * the layout can be switched live in PIE without rebuilding. A spawned
 * AObservatoryGalaxyActor reads these as its initial values; per-actor
 * overrides remain editable on the instance.
 */
UCLASS(Config = Game, DefaultConfig, meta = (DisplayName = "MUSE Observatory Render"))
class SYNAPSEOBSERVATORYRENDER_API UObservatoryRenderSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	UObservatoryRenderSettings();

	virtual FName GetCategoryName() const override;

	/** Initial node-placement mode for spawned galaxies. */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Layout")
	EMuseLayoutMode LayoutMode = EMuseLayoutMode::Gateway;

	/** Morph 0 = pure gateway position, 1 = pure sacred-geometry anchor. */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Layout",
		meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float GeometryBlend = 1.0f;

	/** Which Platonic solid is used when LayoutMode == Platonic. */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Layout")
	EMusePlatonic Platonic = EMusePlatonic::Icosahedron;

	/** Which 4-polytope is used when LayoutMode == Polytope4D. */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Layout")
	EMusePolytope Polytope = EMusePolytope::Cell600;

	/** The 4D rotation plane animated when LayoutMode == Polytope4D. */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Layout|4D")
	EMuseRotationPlane RotationPlane = EMuseRotationPlane::ZW;

	/** Optional second plane for a Clifford / double rotation (set equal to
	 *  RotationPlane to disable the second axis). */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Layout|4D")
	EMuseRotationPlane SecondRotationPlane = EMuseRotationPlane::XY;

	/** Whether the second plane contributes (true => isoclinic/double spin). */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Layout|4D")
	bool bDoubleRotation = false;

	/** 4D rotation speed, radians per second. */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Layout|4D")
	float RotationSpeed = 0.25f;

	/** How a 4-vector collapses to 3-space. */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Layout|4D")
	EMuseProjection Projection = EMuseProjection::Perspective;

	/** World-space radius the unit-scale geometry frameworks are scaled to
	 *  (matches the gateway's [-100,100] box by default). */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Layout",
		meta = (ClampMin = "1.0"))
	float WorldScale = 100.0f;
};
