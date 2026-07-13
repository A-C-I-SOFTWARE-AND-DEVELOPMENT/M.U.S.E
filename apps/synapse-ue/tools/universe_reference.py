from __future__ import annotations

import argparse
import hashlib
import json
import math
from typing import Any


ATLAS_SPHERE_DIAMETER_M = 210.0
AXIAL_SPINE_LENGTH_M = 1800.0
CROWN_RING_DIAMETER_M = 1200.0
NAVIGATION_CLEARANCE_M = 12.0
DEFAULT_RING_DEGREES_PER_SECOND = 0.25
DEFAULT_INTERAXIAL_MILLIMETERS = 65.0


def meters_to_centimeters(meters: float) -> float:
    return meters * 100.0


def station_dimensions() -> dict[str, float]:
    return {
        "atlas_sphere_diameter_m": ATLAS_SPHERE_DIAMETER_M,
        "axial_spine_length_m": AXIAL_SPINE_LENGTH_M,
        "crown_ring_diameter_m": CROWN_RING_DIAMETER_M,
        "navigation_clearance_m": NAVIGATION_CLEARANCE_M,
    }


def counter_rotation_pair(degrees_per_second: float) -> tuple[float, float]:
    return degrees_per_second, -degrees_per_second


def stationary_dock_transform(elapsed_seconds: float) -> tuple[float, float, float]:
    del elapsed_seconds
    return 0.0, 0.0, 0.0


def stable_vessel_id(realm_id: str, agent_id: str) -> str:
    material = realm_id.encode("utf-8") + b"\0" + agent_id.encode("utf-8")
    return "vsl_" + hashlib.sha256(material).hexdigest()[:20]


def stereo_offsets_m(interaxial_millimeters: float) -> tuple[float, float]:
    half_meters = interaxial_millimeters / 2000.0
    return -half_meters, half_meters


def convergence_vectors(
    interaxial_millimeters: float,
    convergence_distance_meters: float,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    half_meters = interaxial_millimeters / 2000.0
    distance = max(convergence_distance_meters, 1e-9)
    length = math.hypot(half_meters, distance)
    return (
        (half_meters / length, distance / length, 0.0),
        (-half_meters / length, distance / length, 0.0),
    )


def deterministic_shot_hash(shot_record: dict[str, Any]) -> str:
    canonical = json.dumps(
        shot_record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sample_shot_record() -> dict[str, Any]:
    return {
        "color_pipeline": "ACES 2.0",
        "convergence_distance_m": 10.0,
        "depth_budget_percent": 2.0,
        "deterministic_seed": 7,
        "display_geometry_m": [20.0, 10.526315789],
        "eye": "pair",
        "interaxial_mm": DEFAULT_INTERAXIAL_MILLIMETERS,
        "output": "OpenEXR 16-bit half",
        "safe_guides": [1.90, 1.43],
        "scene_revision": "scene_reference_v1",
        "shot_id": "shot_reference_001",
        "zero_parallax_distance_m": 10.0,
    }


def reference_payload() -> dict[str, Any]:
    shot = sample_shot_record()
    return {
        "counter_rotation_degrees_per_second": counter_rotation_pair(
            DEFAULT_RING_DEGREES_PER_SECOND
        ),
        "dimensions": station_dimensions(),
        "meter_to_centimeter": meters_to_centimeters(1.0),
        "sample_convergence_vectors": convergence_vectors(
            DEFAULT_INTERAXIAL_MILLIMETERS, 10.0
        ),
        "sample_shot_hash": deterministic_shot_hash(shot),
        "sample_stereo_offsets_m": stereo_offsets_m(
            DEFAULT_INTERAXIAL_MILLIMETERS
        ),
        "sample_vessel_id": stable_vessel_id("rlm_local", "research"),
        "stationary_dock_at_900s": stationary_dock_transform(900.0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print deterministic SYNAPSE universe reference values"
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = reference_payload()
    if args.check:
        assert payload["dimensions"]["atlas_sphere_diameter_m"] == 210.0
        assert payload["counter_rotation_degrees_per_second"] == (0.25, -0.25)
        assert payload["meter_to_centimeter"] == 100.0
        assert str(payload["sample_vessel_id"]).startswith("vsl_")
        assert len(str(payload["sample_shot_hash"])) == 64
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

