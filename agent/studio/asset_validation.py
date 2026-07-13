"""Fail-closed format, topology, rights and publication validation."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .provenance import AssetProvenance, verify_provenance


@dataclass(frozen=True)
class AssetBudgets:
    max_triangles: int = 2_000_000
    max_vertices: int = 2_000_000
    max_texture_dimension: int = 8192
    max_material_slots: int = 32
    require_uv: bool = True
    require_lods: bool = True
    require_collision: bool = True
    require_navigation: bool = False


@dataclass(frozen=True)
class AssetValidation:
    passed: bool
    failures: tuple[str, ...]
    warnings: tuple[str, ...]
    metrics: Mapping[str, Any]
    parser: str
    asset_id: str = ""
    path: str = ""


def _sidecar(path: Path) -> tuple[dict[str, Any] | None, str]:
    candidates = (
        path.with_suffix(path.suffix + ".asset.json"),
        path.with_name(path.stem + ".asset.json"),
    )
    for candidate in candidates:
        if candidate.is_file():
            try:
                value = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None, "invalid_sidecar"
            return (value if isinstance(value, dict) else None), "muse_asset_sidecar_v1"
    if path.suffix.lower() == ".gltf" and path.is_file():
        try:
            gltf = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, "invalid_gltf"
        extras = gltf.get("extras") if isinstance(gltf, dict) else None
        muse = extras.get("muse_validation") if isinstance(extras, dict) else None
        if isinstance(muse, dict):
            return muse, "gltf_extras_muse_validation_v1"
    return None, "unverified_parser_missing"


def _finite_vector(value: object, length: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == length
        and all(
            not isinstance(item, bool)
            and isinstance(item, (int, float))
            and math.isfinite(float(item))
            for item in value
        )
    )


def validate_asset(
    path: str | Path,
    provenance: AssetProvenance,
    budgets: AssetBudgets | None = None,
) -> AssetValidation:
    asset = Path(path)
    limits = budgets or AssetBudgets()
    failures: list[str] = []
    warnings: list[str] = []
    evidence, parser = _sidecar(asset)
    provenance_result = verify_provenance(asset, provenance, required_use="public")
    failures.extend(provenance_result.failures)
    asset_format = asset.suffix.lower().lstrip(".")
    if provenance.formats and asset_format not in {
        item.lower().lstrip(".") for item in provenance.formats
    }:
        failures.append("format")
    if evidence is None:
        failures.append(parser)
        return AssetValidation(
            False,
            tuple(dict.fromkeys(failures)),
            (),
            {},
            parser,
            provenance.asset_id,
            str(asset),
        )

    def integer(name: str, *, minimum: int = 0) -> int | None:
        value = evidence.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            failures.append(name)
            return None
        return value

    triangles = integer("triangles")
    vertices = integer("vertices")
    texture_dimension = integer("texture_dimension", minimum=1)
    material_slots = integer("material_slots", minimum=1)
    if triangles is not None and triangles > limits.max_triangles:
        failures.append("triangle_budget")
    if vertices is not None and vertices > limits.max_vertices:
        failures.append("vertex_budget")
    if texture_dimension is not None and texture_dimension > limits.max_texture_dimension:
        failures.append("texture_budget")
    if material_slots is not None and material_slots > limits.max_material_slots:
        failures.append("material_slot_budget")

    units = evidence.get("units")
    if units not in {"meter", "centimeter"}:
        failures.append("units")
    scale = evidence.get("scale")
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(float(scale)) or scale <= 0:
        failures.append("scale")
    bounds_min = evidence.get("bounds_min")
    bounds_max = evidence.get("bounds_max")
    if not _finite_vector(bounds_min, 3) or not _finite_vector(bounds_max, 3):
        failures.append("finite_bounds")
    elif any(float(low) > float(high) for low, high in zip(bounds_min, bounds_max)):
        failures.append("finite_bounds")
    transforms = evidence.get("transforms")
    if not isinstance(transforms, dict) or transforms.get("frozen") is not True:
        failures.append("transforms")
    if limits.require_uv and evidence.get("uv") is not True:
        failures.append("uv")
    lod_levels = evidence.get("lod_levels")
    if limits.require_lods and (
        not isinstance(lod_levels, list)
        or not lod_levels
        or any(type(level) is not int or level < 0 for level in lod_levels)
    ):
        failures.append("lod")
    if limits.require_collision and evidence.get("collision") is not True:
        failures.append("collision")
    if limits.require_navigation and evidence.get("navigation") is not True:
        failures.append("navigation")
    if evidence.get("skinned") is True:
        if evidence.get("skeleton_compatible") is not True:
            failures.append("skeleton_compatibility")
        if evidence.get("animation_compatible") is not True:
            failures.append("animation_compatibility")
    if evidence.get("malware_scan") != "passed":
        failures.append("malware_scan")

    metrics = {
        "triangles": triangles,
        "vertices": vertices,
        "texture_dimension": texture_dimension,
        "material_slots": material_slots,
        "units": units,
        "scale": scale,
    }
    return AssetValidation(
        not failures,
        tuple(dict.fromkeys(failures)),
        tuple(dict.fromkeys(warnings)),
        metrics,
        parser,
        provenance.asset_id,
        str(asset),
    )


def verify_publishable_asset(
    path: str | Path,
    provenance: AssetProvenance,
    budgets: AssetBudgets | None = None,
) -> AssetValidation:
    return validate_asset(path, provenance, budgets)


__all__ = [
    "AssetBudgets",
    "AssetValidation",
    "validate_asset",
    "verify_publishable_asset",
]
