// ObservatoryRenderTypes — render-side enums for the sacred-geometry galaxy.
// Copyright A-C-I Software & Development. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "ObservatoryRenderTypes.generated.h"

/**
 * How the galaxy places its nodes. ``Gateway`` keeps the deterministic
 * gateway-computed positions (force / solar — the existing behavior);
 * the others arrange nodes onto a closed-form sacred-geometry framework.
 * A per-actor GeometryBlend in [0,1] morphs between the gateway layout (0)
 * and the chosen geometry (1).
 */
UENUM(BlueprintType)
enum class EMuseLayoutMode : uint8
{
	/** Use the gateway's `pos` verbatim (force-directed or solar). Default. */
	Gateway,
	/** Vogel phyllotaxis disk — the flat "Flower" arrangement. */
	Phyllotaxis,
	/** Spherical Fibonacci lattice — one node per golden-angle shell point. */
	FibonacciSphere,
	/** Platonic-solid vertices as structural anchors (cycled if over-full). */
	Platonic,
	/** A regular 4-polytope, rotated in 4D each tick and projected to 3-space. */
	Polytope4D,
};
