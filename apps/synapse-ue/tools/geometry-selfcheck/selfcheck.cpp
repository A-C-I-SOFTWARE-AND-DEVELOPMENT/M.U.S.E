// Standalone, UE-free self-check for MuseSacredGeometry.
//
// Compiles the REAL apps/synapse-ue/Source/SynapseCore/Private/MuseSacredGeometry.cpp
// against a minimal non-UE shim (ueshim/) and asserts the same invariants the
// UE automation suite (Synapse.Geometry.*) and the Python reference check, so
// the geometry C++ is proven to compile + be numerically correct with a plain
// C++17 compiler — no Unreal Engine required. See README.md.
//
// Build (from repo root):
//   clang++ -std=c++17 -Wall -Wextra \
//     -I apps/synapse-ue/tools/geometry-selfcheck/ueshim \
//     -I apps/synapse-ue/Source/SynapseCore/Public \
//     apps/synapse-ue/tools/geometry-selfcheck/selfcheck.cpp \
//     apps/synapse-ue/Source/SynapseCore/Private/MuseSacredGeometry.cpp \
//     -o /tmp/geometry-selfcheck && /tmp/geometry-selfcheck

#include "MuseSacredGeometry.h"

#include <cmath>
#include <cstdio>

static int g_failures = 0;

static void check(bool cond, const char* msg)
{
	if (!cond)
	{
		std::printf("FAIL: %s\n", msg);
		++g_failures;
	}
}

static void check_count(int actual, int expected, const char* msg)
{
	if (actual != expected)
	{
		std::printf("FAIL: %s — got %d, want %d\n", msg, actual, expected);
		++g_failures;
	}
}

static double norm4(const FVector4& p)
{
	return std::sqrt(p.X * p.X + p.Y * p.Y + p.Z * p.Z + p.W * p.W);
}

int main()
{
	using namespace MuseGeometry;

	check(std::fabs(GoldenAngleDegrees() - 137.50776405) < 1e-6, "golden angle degrees");
	check(std::fabs(Phi() - 1.6180339887498949) < 1e-9, "phi");

	check_count(PlatonicVertices(EMusePlatonic::Tetrahedron).Num(), 4, "tetrahedron");
	check_count(PlatonicVertices(EMusePlatonic::Cube).Num(), 8, "cube");
	check_count(PlatonicVertices(EMusePlatonic::Octahedron).Num(), 6, "octahedron");
	check_count(PlatonicVertices(EMusePlatonic::Icosahedron).Num(), 12, "icosahedron");
	check_count(PlatonicVertices(EMusePlatonic::Dodecahedron).Num(), 20, "dodecahedron");

	check_count(PolytopeVertices(EMusePolytope::Cell5).Num(), 5, "5-cell");
	check_count(PolytopeVertices(EMusePolytope::Cell16).Num(), 8, "16-cell");
	check_count(PolytopeVertices(EMusePolytope::Tesseract).Num(), 16, "tesseract");
	check_count(PolytopeVertices(EMusePolytope::Cell24).Num(), 24, "24-cell");
	check_count(PolytopeVertices(EMusePolytope::Cell600).Num(), 120, "600-cell");
	check_count(PolytopeVertices(EMusePolytope::Cell120).Num(), 600, "120-cell");

	const FVector4 p(0.3, -0.7, 1.1, 0.5);
	const FVector4 r = Rotate4D(p, EMuseRotationPlane::ZW, 1.234);
	check(std::fabs(norm4(p) - norm4(r)) < 1e-9, "4D rotation preserves the norm");

	for (const FVector& v : PlatonicVertices(EMusePlatonic::Icosahedron, /*bNormalize=*/true))
	{
		check(std::fabs(v.Length() - 1.0) < 1e-6, "normalized icosahedron vertex on the unit shell");
	}

	for (const FVector4& v : PolytopeVertices(EMusePolytope::Tesseract))
	{
		const FVector pr = Project4DTo3D(v, EMuseProjection::Perspective, 2.5);
		check(std::isfinite(pr.X) && std::isfinite(pr.Y) && std::isfinite(pr.Z),
			"perspective projection is finite");
	}

	if (g_failures == 0)
	{
		std::printf("OK: MuseSacredGeometry C++ self-check passed (clang, no UE)\n");
		return 0;
	}
	std::printf("%d check(s) failed\n", g_failures);
	return 1;
}
