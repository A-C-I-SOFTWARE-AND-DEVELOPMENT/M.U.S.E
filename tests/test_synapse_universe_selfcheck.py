from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest


REPO = Path(__file__).resolve().parents[1]
UE = REPO / "apps" / "synapse-ue"
REFERENCE_PATH = UE / "tools" / "universe_reference.py"
SELFCHECK = UE / "tools" / "universe-selfcheck" / "selfcheck.cpp"
MATH_HEADER = UE / "Source" / "SynapseUniverse" / "Public" / "MuseUniverseMath.h"


def _reference_module():
    spec = importlib.util.spec_from_file_location("universe_reference", REFERENCE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_python_reference_freezes_metric_station_and_counter_rotation() -> None:
    reference = _reference_module()
    assert reference.station_dimensions() == {
        "atlas_sphere_diameter_m": 210.0,
        "axial_spine_length_m": 1800.0,
        "crown_ring_diameter_m": 1200.0,
        "navigation_clearance_m": 12.0,
    }
    assert reference.counter_rotation_pair(0.25) == (0.25, -0.25)
    assert reference.meters_to_centimeters(1.0) == 100.0
    assert reference.stationary_dock_transform(17.0) == (0.0, 0.0, 0.0)


def test_stable_vessel_id_matches_sha256_contract() -> None:
    reference = _reference_module()
    realm_id = "rlm_local"
    agent_id = "research"
    expected = "vsl_" + hashlib.sha256(
        realm_id.encode() + b"\0" + agent_id.encode()
    ).hexdigest()[:20]
    assert reference.stable_vessel_id(realm_id, agent_id) == expected


def test_stereo_offsets_convergence_and_shot_hash_are_deterministic() -> None:
    reference = _reference_module()
    assert reference.stereo_offsets_m(65.0) == (-0.0325, 0.0325)
    left, right = reference.convergence_vectors(65.0, 10.0)
    assert left[1] == pytest.approx(right[1], abs=1e-12)
    assert left[0] == pytest.approx(-right[0], abs=1e-12)
    shot = reference.sample_shot_record()
    first = reference.deterministic_shot_hash(shot)
    second = reference.deterministic_shot_hash(json.loads(json.dumps(shot)))
    assert first == second
    assert len(first) == 64


def test_cpp_selfcheck_compiles_the_real_shared_math_header_when_available(
    tmp_path: Path,
) -> None:
    compiler = shutil.which("clang++") or shutil.which("g++")
    if compiler is None:
        pytest.skip("C++17 compiler unavailable; engine-independent compile gate is open")
    output = tmp_path / ("universe-selfcheck.exe" if Path(compiler).suffix == ".exe" else "universe-selfcheck")
    command = [
        compiler,
        "-std=c++17",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I",
        str(MATH_HEADER.parent),
        str(SELFCHECK),
        "-o",
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    result = subprocess.run(
        [str(output)], check=True, capture_output=True, text=True
    )
    assert "OK: Synapse universe C++ self-check passed" in result.stdout
    actual = json.loads(result.stdout.splitlines()[-1])
    reference = _reference_module().reference_payload()
    assert actual["dimensions"] == reference["dimensions"]
    assert actual["meter_to_centimeter"] == reference["meter_to_centimeter"]
    assert actual["sample_vessel_id"] == reference["sample_vessel_id"]
    assert actual["sample_shot_hash"] == reference["sample_shot_hash"]
    assert actual["counter_rotation_degrees_per_second"] == pytest.approx(
        reference["counter_rotation_degrees_per_second"], abs=1e-12
    )
    assert actual["sample_stereo_offsets_m"] == pytest.approx(
        reference["sample_stereo_offsets_m"], abs=1e-12
    )
    assert actual["sample_convergence_vectors"][0] == pytest.approx(
        reference["sample_convergence_vectors"][0], abs=1e-12
    )
    assert actual["sample_convergence_vectors"][1] == pytest.approx(
        reference["sample_convergence_vectors"][1], abs=1e-12
    )
    assert actual["stationary_dock_at_900s"] == pytest.approx(
        reference["stationary_dock_at_900s"], abs=1e-12
    )


def test_selfcheck_is_engine_independent_and_uses_no_gameplay_shim() -> None:
    source = SELFCHECK.read_text(encoding="utf-8")
    runner = (UE / "tools" / "run-universe-selfcheck.ps1").read_text(
        encoding="utf-8"
    )
    shim = (
        UE / "tools" / "universe-selfcheck" / "ueshim" / "CoreMinimal.h"
    ).read_text(encoding="utf-8")
    assert '#include "MuseUniverseMath.h"' in source
    assert "UnrealEditor" not in source
    assert "clang++" in runner and "cl.exe" in runner
    assert "NO GAMEPLAY TYPES" in shim
