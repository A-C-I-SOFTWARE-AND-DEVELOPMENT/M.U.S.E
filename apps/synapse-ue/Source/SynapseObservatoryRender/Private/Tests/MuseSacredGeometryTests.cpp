// MuseSacredGeometry automation tests.
// Copyright A-C-I Software & Development. All rights reserved.
//
// Headless (`-nullrhi`) automation suites that prove the closed-form geometry
// the galaxy renderer depends on. Run on the owner's machine via:
//   Automation RunTests Synapse.Geometry
// These assert exactly what apps/synapse-ue/tools/sacred_geometry_reference.py
// proves in the authoring container (golden angle, exact vertex counts, 4D
// rotation invariants) — the two MUST agree.

#include "Misc/AutomationTest.h"
#include "MuseSacredGeometry.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr double MuseTestPi = 3.14159265358979323846;

	double Norm4(const FVector4& P)
	{
		return FMath::Sqrt(P.X * P.X + P.Y * P.Y + P.Z * P.Z + P.W * P.W);
	}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseGeometryConstantsTest, "Synapse.Geometry.Constants",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseGeometryConstantsTest::RunTest(const FString& /*Parameters*/)
{
	TestTrue(TEXT("phi"), FMath::IsNearlyEqual(MuseGeometry::Phi(), 1.6180339887498949, 1e-9));
	TestTrue(TEXT("golden angle degrees"),
		FMath::IsNearlyEqual(MuseGeometry::GoldenAngleDegrees(), 137.50776405003785, 1e-6));
	const double P = MuseGeometry::Phi();
	TestTrue(TEXT("golden angle = 2*pi/phi^2"),
		FMath::IsNearlyEqual(MuseGeometry::GoldenAngleRadians(), 2.0 * MuseTestPi / (P * P), 1e-9));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseGeometryVertexCountsTest, "Synapse.Geometry.VertexCounts",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseGeometryVertexCountsTest::RunTest(const FString& /*Parameters*/)
{
	TestEqual(TEXT("tetrahedron"), MuseGeometry::PlatonicVertices(EMusePlatonic::Tetrahedron).Num(), 4);
	TestEqual(TEXT("cube"), MuseGeometry::PlatonicVertices(EMusePlatonic::Cube).Num(), 8);
	TestEqual(TEXT("octahedron"), MuseGeometry::PlatonicVertices(EMusePlatonic::Octahedron).Num(), 6);
	TestEqual(TEXT("icosahedron"), MuseGeometry::PlatonicVertices(EMusePlatonic::Icosahedron).Num(), 12);
	TestEqual(TEXT("dodecahedron"), MuseGeometry::PlatonicVertices(EMusePlatonic::Dodecahedron).Num(), 20);

	TestEqual(TEXT("5-cell"), MuseGeometry::PolytopeVertices(EMusePolytope::Cell5).Num(), 5);
	TestEqual(TEXT("16-cell"), MuseGeometry::PolytopeVertices(EMusePolytope::Cell16).Num(), 8);
	TestEqual(TEXT("tesseract"), MuseGeometry::PolytopeVertices(EMusePolytope::Tesseract).Num(), 16);
	TestEqual(TEXT("24-cell"), MuseGeometry::PolytopeVertices(EMusePolytope::Cell24).Num(), 24);
	TestEqual(TEXT("600-cell"), MuseGeometry::PolytopeVertices(EMusePolytope::Cell600).Num(), 120);
	TestEqual(TEXT("120-cell"), MuseGeometry::PolytopeVertices(EMusePolytope::Cell120).Num(), 600);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseGeometryRotationTest, "Synapse.Geometry.Rotation4D",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseGeometryRotationTest::RunTest(const FString& /*Parameters*/)
{
	const FVector4 P(0.3, -0.7, 1.1, 0.5);
	const FVector4 R = MuseGeometry::Rotate4D(P, EMuseRotationPlane::ZW, 1.234);
	TestTrue(TEXT("rotation preserves the 4D norm"),
		FMath::IsNearlyEqual(Norm4(P), Norm4(R), 1e-9));

	const FVector4 Spun = MuseGeometry::Rotate4D(P, EMuseRotationPlane::XY, 2.0 * MuseTestPi);
	TestTrue(TEXT("full 2*pi rotation is the identity"), Spun.Equals(P, 1e-6));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseGeometryShellTest, "Synapse.Geometry.NormalizedShell",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseGeometryShellTest::RunTest(const FString& /*Parameters*/)
{
	for (const EMusePlatonic Solid :
		 {EMusePlatonic::Cube, EMusePlatonic::Icosahedron, EMusePlatonic::Dodecahedron})
	{
		for (const FVector& V : MuseGeometry::PlatonicVertices(Solid, /*bNormalize=*/true))
		{
			TestTrue(TEXT("normalized Platonic vertex on the unit shell"),
				FMath::IsNearlyEqual(V.Length(), 1.0, 1e-6));
		}
	}

	for (const FVector& V : MuseGeometry::FibonacciSphere(50))
	{
		TestTrue(TEXT("Fibonacci-sphere point on the unit sphere"),
			FMath::IsNearlyEqual(V.Length(), 1.0, 1e-6));
	}

	for (const FVector4& V : MuseGeometry::PolytopeVertices(EMusePolytope::Tesseract))
	{
		const FVector Projected = MuseGeometry::Project4DTo3D(V, EMuseProjection::Perspective, 2.5);
		TestTrue(TEXT("perspective projection is finite"), Projected.ContainsNaN() == false);
	}
	return true;
}

#endif  // WITH_DEV_AUTOMATION_TESTS
