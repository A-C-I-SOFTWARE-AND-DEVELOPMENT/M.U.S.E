"""Deterministic QA validators — NEEDLE-QA routes here; the model never decides
quality by opinion (directive §39). Each validator is pure-python over an
asset-manifest dict so it is testable without Blender. Blender/FBX adapters
translate real assets into this manifest shape upstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    check: str
    passed: bool
    measured: Any = None
    limit: Any = None
    detail: str = ""


def check_polycount(manifest: dict, max_tris: int) -> CheckResult:
    tris = int(manifest.get("triangle_count", 0))
    return CheckResult("polycount", tris <= max_tris, tris, max_tris,
                       f"{tris} tris vs budget {max_tris}")


def check_ngons(manifest: dict, allow: bool = False) -> CheckResult:
    ngons = int(manifest.get("ngon_count", 0))
    ok = allow or ngons == 0
    return CheckResult("ngons", ok, ngons, 0 if not allow else None,
                       f"{ngons} n-gon faces")


def check_manifold(manifest: dict) -> CheckResult:
    nm = int(manifest.get("non_manifold_edges", 0))
    return CheckResult("manifold", nm == 0, nm, 0, f"{nm} non-manifold edges")


def check_degenerate(manifest: dict) -> CheckResult:
    deg = int(manifest.get("degenerate_faces", 0))
    return CheckResult("degenerate", deg == 0, deg, 0, f"{deg} degenerate faces")


def check_material_count(manifest: dict, max_materials: int) -> CheckResult:
    n = len(manifest.get("materials", []))
    return CheckResult("materials", n <= max_materials, n, max_materials,
                       f"{n} material slots vs budget {max_materials}")


def check_uv_overlap(manifest: dict) -> CheckResult:
    ov = float(manifest.get("uv_overlap_fraction", 0.0))
    return CheckResult("uv_overlap", ov <= 0.0, ov, 0.0, f"overlap fraction {ov}")


def check_transforms(manifest: dict) -> CheckResult:
    unapplied = [o for o in manifest.get("objects", [])
                 if o.get("scale") not in (None, [1.0, 1.0, 1.0], (1.0, 1.0, 1.0))]
    return CheckResult("transforms", not unapplied, len(unapplied), 0,
                       f"{len(unapplied)} objects with unapplied scale")


def check_naming(manifest: dict, pattern: str | None = None) -> CheckResult:
    import re
    rx = re.compile(pattern) if pattern else None
    bad = [o.get("name", "") for o in manifest.get("objects", [])
           if rx and not rx.match(o.get("name", ""))]
    return CheckResult("naming", not bad, len(bad), 0,
                       f"violations: {bad[:5]}" if bad else "all names conform")


VALIDATORS = {
    "polycount": check_polycount,
    "ngons": check_ngons,
    "manifold": check_manifold,
    "degenerate": check_degenerate,
    "materials": check_material_count,
    "uv_overlap": check_uv_overlap,
    "transforms": check_transforms,
    "naming": check_naming,
}


def run_asset_gate(manifest: dict, profile: str = "game-ready") -> dict:
    """Full deterministic gate. Profiles encode project budgets (§39)."""
    profiles = {
        "game-ready": {"max_tris": 20000, "max_materials": 4, "allow_ngons": False},
        "mobile": {"max_tris": 5000, "max_materials": 2, "allow_ngons": False},
        "cinematic": {"max_tris": 500000, "max_materials": 16, "allow_ngons": True},
    }
    p = profiles.get(profile, profiles["game-ready"])
    results = [
        check_polycount(manifest, p["max_tris"]),
        check_ngons(manifest, p["allow_ngons"]),
        check_manifold(manifest),
        check_degenerate(manifest),
        check_material_count(manifest, p["max_materials"]),
        check_uv_overlap(manifest),
        check_transforms(manifest),
    ]
    passed = all(r.passed for r in results)
    return {
        "profile": profile,
        "passed": passed,
        "checks": [vars(r) for r in results],
    }
