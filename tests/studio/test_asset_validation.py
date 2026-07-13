from __future__ import annotations

import json
from pathlib import Path

from agent.studio.asset_validation import AssetBudgets, validate_asset
from agent.studio.provenance import AssetProvenance, sha256_file


def _provenance(asset: Path) -> AssetProvenance:
    return AssetProvenance(
        asset_id="ast_valid",
        content_hash=sha256_file(asset),
        formats=(asset.suffix,),
        creator="owner",
        license="Proprietary",
        allowed_uses=("public",),
        safety_status="passed",
    )


def _sidecar(asset: Path, **overrides: object) -> None:
    evidence = {
        "triangles": 1000,
        "vertices": 800,
        "texture_dimension": 2048,
        "material_slots": 2,
        "units": "meter",
        "scale": 1.0,
        "bounds_min": [-1.0, -1.0, -1.0],
        "bounds_max": [1.0, 1.0, 1.0],
        "transforms": {"frozen": True},
        "uv": True,
        "lod_levels": [0, 1, 2],
        "collision": True,
        "navigation": True,
        "malware_scan": "passed",
    }
    evidence.update(overrides)
    asset.with_suffix(asset.suffix + ".asset.json").write_text(
        json.dumps(evidence), encoding="utf-8"
    )


def test_complete_asset_evidence_passes(tmp_path: Path) -> None:
    asset = tmp_path / "hull.glb"
    asset.write_bytes(b"glTF")
    _sidecar(asset)
    assert validate_asset(asset, _provenance(asset)).passed is True


def test_missing_parser_and_budget_overrun_fail_closed(tmp_path: Path) -> None:
    asset = tmp_path / "hull.glb"
    asset.write_bytes(b"glTF")
    missing = validate_asset(asset, _provenance(asset))
    assert "unverified_parser_missing" in missing.failures

    _sidecar(asset, triangles=10_000)
    over = validate_asset(asset, _provenance(asset), AssetBudgets(max_triangles=100))
    assert "triangle_budget" in over.failures


def test_skinned_asset_requires_skeleton_and_animation_compatibility(tmp_path: Path) -> None:
    asset = tmp_path / "character.glb"
    asset.write_bytes(b"glTF")
    _sidecar(asset, skinned=True)
    result = validate_asset(asset, _provenance(asset))
    assert "skeleton_compatibility" in result.failures
    assert "animation_compatibility" in result.failures
