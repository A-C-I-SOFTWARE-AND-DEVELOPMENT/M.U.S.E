// UE-free C++17 self-check for the REAL production MuseUniverseMath.h.
// This validates deterministic math only. It does not emulate Unreal gameplay,
// rendering, HTTP, UObject lifecycles, MRQ, OpenXR, or Pixel Streaming.

#include "MuseUniverseMath.h"

#include <cmath>
#include <cstdio>
#include <string>

namespace
{
	int Failures = 0;

	void Check(const bool Condition, const char* Message)
	{
		if (!Condition)
		{
			std::printf("FAIL: %s\n", Message);
			++Failures;
		}
	}
}

int main()
{
	using namespace MuseUniverseMath;

	Check(std::fabs(MetersToCentimeters(1.0) - 100.0) < 1e-12,
		"meter to centimeter conversion");
	Check(std::fabs(AtlasSphereDiameterMeters - 210.0) < 1e-12,
		"Atlas sphere diameter");
	Check(std::fabs(AxialSpineLengthMeters - 1800.0) < 1e-12,
		"axial spine length");
	Check(std::fabs(CrownRingDiameterMeters - 1200.0) < 1e-12,
		"crown ring diameter");

	const auto Rotation = CounterRotationPair(0.25);
	Check(std::fabs(Rotation.first + Rotation.second) < 1e-12,
		"equal opposite ring rotation");
	const Vector3d DockAtStart = StationaryDockTransform(0.0);
	const Vector3d DockLater = StationaryDockTransform(900.0);
	Check(DockAtStart.X == DockLater.X && DockAtStart.Y == DockLater.Y &&
		DockAtStart.Z == DockLater.Z,
		"docking transform remains stationary");

	Check(Sha256Hex("abc") ==
		"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
		"SHA-256 standard vector");
	const std::string Vessel = StableVesselId("rlm_local", "research");
	Check(Vessel.rfind("vsl_", 0) == 0 && Vessel.size() == 24,
		"stable vessel id shape");
	Check(Vessel == StableVesselId("rlm_local", "research"),
		"stable vessel id determinism");

	const auto Offsets = StereoOffsetsMeters(65.0);
	Check(std::fabs(Offsets.first + 0.0325) < 1e-12,
		"left camera offset");
	Check(std::fabs(Offsets.second - 0.0325) < 1e-12,
		"right camera offset");
	const auto Convergence = ConvergenceVectors(65.0, 10.0);
	Check(std::fabs(Convergence.first.X + Convergence.second.X) < 1e-12,
		"symmetric convergence x");
	Check(std::fabs(Convergence.first.Y - Convergence.second.Y) < 1e-12,
		"symmetric convergence y");

	const std::string CanonicalShot =
		"{\"color_pipeline\":\"ACES 2.0\",\"convergence_distance_m\":10.0,"
		"\"depth_budget_percent\":2.0,\"deterministic_seed\":7,"
		"\"display_geometry_m\":[20.0,10.526315789],\"eye\":\"pair\","
		"\"interaxial_mm\":65.0,\"output\":\"OpenEXR 16-bit half\","
		"\"safe_guides\":[1.9,1.43],\"scene_revision\":\"scene_reference_v1\","
		"\"shot_id\":\"shot_reference_001\",\"zero_parallax_distance_m\":10.0}";
	const std::string ShotHash = DeterministicShotHash(CanonicalShot);
	Check(ShotHash.size() == 64 && ShotHash == DeterministicShotHash(CanonicalShot),
		"deterministic shot hash");

	if (Failures == 0)
	{
		std::printf("OK: Synapse universe C++ self-check passed\n");
		std::printf(
			"{\"counter_rotation_degrees_per_second\":[%.17g,%.17g],"
			"\"dimensions\":{\"atlas_sphere_diameter_m\":%.17g,"
			"\"axial_spine_length_m\":%.17g,\"crown_ring_diameter_m\":%.17g,"
			"\"navigation_clearance_m\":%.17g},\"meter_to_centimeter\":%.17g,"
			"\"sample_convergence_vectors\":[[%.17g,%.17g,%.17g],[%.17g,%.17g,%.17g]],"
			"\"sample_shot_hash\":\"%s\",\"sample_stereo_offsets_m\":[%.17g,%.17g],"
			"\"sample_vessel_id\":\"%s\",\"stationary_dock_at_900s\":[%.17g,%.17g,%.17g]}\n",
			Rotation.first,
			Rotation.second,
			AtlasSphereDiameterMeters,
			AxialSpineLengthMeters,
			CrownRingDiameterMeters,
			NavigationClearanceMeters,
			MetersToCentimeters(1.0),
			Convergence.first.X,
			Convergence.first.Y,
			Convergence.first.Z,
			Convergence.second.X,
			Convergence.second.Y,
			Convergence.second.Z,
			ShotHash.c_str(),
			Offsets.first,
			Offsets.second,
			Vessel.c_str(),
			DockLater.X,
			DockLater.Y,
			DockLater.Z);
		return 0;
	}
	std::printf("%d universe self-check(s) failed\n", Failures);
	return 1;
}
