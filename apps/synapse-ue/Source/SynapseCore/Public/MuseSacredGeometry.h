// MuseSacredGeometry — closed-form sacred-geometry coordinate generators.
// Copyright A-C-I Software & Development. All rights reserved.
//
// Pure, engine-light math (CoreMinimal only — FVector / FVector4 / FVector2D
// and FMath). NO Engine subsystem, HTTP, or UObject-instance state: this is the
// deterministic geometry kernel the SynapseObservatoryRender galaxy renderer and
// its automation tests call. Every generator is a closed-form function of its
// arguments, so the same inputs always yield byte-identical outputs.
//
// Numeric ground truth + the validation checklist live in
// `apps/synapse-ue/tools/sacred_geometry_reference.py` (runnable in the
// authoring container, where UE/UBT are not installed). The constants and exact
// vertex counts here MUST match that reference: golden angle 137.50776405 deg,
// 600-cell = 120 vertices, 120-cell = 600 vertices, etc. The automation tests in
// SynapseObservatoryRender assert exactly that on the owner's machine.

#pragma once

#include "CoreMinimal.h"
#include "MuseSacredGeometry.generated.h"

/** The five Platonic solids (3D structural-anchor frameworks). */
UENUM(BlueprintType)
enum class EMusePlatonic : uint8
{
	Tetrahedron,
	Cube,
	Octahedron,
	Icosahedron,
	Dodecahedron,
};

/** The six regular convex 4-polytopes (4D frameworks; projected each tick). */
UENUM(BlueprintType)
enum class EMusePolytope : uint8
{
	Cell5     UMETA(DisplayName = "5-cell"),
	Cell16    UMETA(DisplayName = "16-cell"),
	Tesseract UMETA(DisplayName = "8-cell (tesseract)"),
	Cell24    UMETA(DisplayName = "24-cell"),
	Cell600   UMETA(DisplayName = "600-cell"),
	Cell120   UMETA(DisplayName = "120-cell"),
};

/** The six coordinate planes a 4D rotation can occur in. XW/YW/ZW have no 3D
 *  analogue — they produce the "impossible" morphing nesting on projection. */
UENUM(BlueprintType)
enum class EMuseRotationPlane : uint8
{
	XY,
	XZ,
	XW,
	YZ,
	YW,
	ZW,
};

/** How a 4-vector collapses to 3-space for rendering. */
UENUM(BlueprintType)
enum class EMuseProjection : uint8
{
	/** Schlegel-style: scale by d/(d-w) — the classic nested-cube look. */
	Perspective,
	/** Inflate onto the unit 3-sphere, then project from the +w pole —
	 *  edges render as graceful curved arcs. */
	Stereographic,
};

/**
 * Closed-form sacred-geometry generators. Free functions in a namespace (not a
 * UObject) so they are trivially callable from the render module and from
 * headless automation tests, with no instance/lifecycle concerns.
 */
namespace MuseGeometry
{
	/** The golden ratio phi = (1 + sqrt 5) / 2. */
	SYNAPSECORE_API double Phi();

	/** The golden angle in radians: pi * (3 - sqrt 5) = 2*pi / phi^2. */
	SYNAPSECORE_API double GoldenAngleRadians();

	/** The golden angle in degrees (137.50776405...). */
	SYNAPSECORE_API double GoldenAngleDegrees();

	/** Vogel's sunflower phyllotaxis: point i at r = sqrt(i),
	 *  theta = i * golden angle. Returns N planar points (the "Flower"). */
	SYNAPSECORE_API TArray<FVector2D> VogelPhyllotaxis(int32 N);

	/** N near-uniform points on the unit sphere via the golden-angle spiral
	 *  (z = 1 - 2(i+0.5)/N, theta = golden angle * i). */
	SYNAPSECORE_API TArray<FVector> FibonacciSphere(int32 N);

	/** Exact vertices of a Platonic solid. When bNormalize, every vertex is
	 *  scaled to unit distance from the origin (uniform shell). */
	SYNAPSECORE_API TArray<FVector> PlatonicVertices(EMusePlatonic Solid, bool bNormalize = false);

	/** Exact 4D vertices of a regular 4-polytope. Counts (validated against the
	 *  Python reference): 5 / 8 / 16 / 24 / 120 / 600. */
	SYNAPSECORE_API TArray<FVector4> PolytopeVertices(EMusePolytope Polytope);

	/** Rotate a 4-vector by Angle (radians) in one coordinate plane. */
	SYNAPSECORE_API FVector4 Rotate4D(const FVector4& P, EMuseRotationPlane Plane, double Angle);

	/** Project a 4-vector to 3-space. Distance is the 4D camera distance for
	 *  the perspective mode (ignored by stereographic). */
	SYNAPSECORE_API FVector Project4DTo3D(const FVector4& P, EMuseProjection Mode, double Distance = 2.5);
}
