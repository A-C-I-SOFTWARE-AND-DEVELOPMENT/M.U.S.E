#!/usr/bin/env python3
"""Verify a packaged GameFoundry proof without trusting manifest booleans alone."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def verify(root: Path) -> dict[str, object]:
    manifest_path = root / "game-build-manifest.json"
    if not manifest_path.is_file():
        return {"ok": False, "failures": ["missing_game_build_manifest"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    gates = {item.get("name"): item for item in manifest.get("gate_results", [])}
    required = (
        "build_editor",
        "author_map",
        "audit_map",
        "test_automation",
        "package_win64",
        "smoke_win64",
    )
    for name in required:
        gate = gates.get(name)
        if not gate or gate.get("status") != "passed" or gate.get("exit_code") != 0:
            failures.append(f"gate_not_passed:{name}")
    for gate_name in ("author_map", "audit_map"):
        log_path = root / "Evidence" / "commands" / f"{gate_name}.log"
        if not log_path.is_file():
            failures.append(f"missing_gate_log:{gate_name}")
            continue
        log = log_path.read_text(encoding="utf-8", errors="replace")
        if "Traceback (most recent call last)" in log or "LogPython: Error:" in log:
            failures.append(f"python_error_in_gate_log:{gate_name}")
    package_log_path = root / "Evidence" / "commands" / "package_win64.log"
    if not package_log_path.is_file():
        failures.append("missing_gate_log:package_win64")
    else:
        package_log = package_log_path.read_text(encoding="utf-8", errors="replace")
        if (
            "Failed to compile Material" in package_log
            or "doesn't have a valid ShaderMap" in package_log
        ):
            failures.append("generated_material_compile_failure")
    package_root = root / "Build" / "Win64"
    suffixes = {
        path.suffix.lower()
        for path in package_root.rglob("*")
        if path.is_file() and path.stat().st_size > 0
    }
    for suffix in (".exe", ".pak", ".ucas", ".utoc"):
        if suffix not in suffixes:
            failures.append(f"missing_package_artifact:{suffix}")
    map_path = root / "Content" / "Maps" / "MuseSlice.umap"
    if not map_path.is_file() or map_path.stat().st_size <= 0:
        failures.append("missing_authored_map")
    author_report_path = root / "Evidence" / "author-map-complete.json"
    if not author_report_path.is_file():
        failures.append("missing_author_map_completion_evidence")
    else:
        try:
            author_report = json.loads(author_report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            failures.append("invalid_author_map_completion_evidence")
        else:
            if author_report.get("passed") is not True:
                failures.append("author_map_completion_failed")
            if int(author_report.get("generated_actor_count", 0)) < 17:
                failures.append("authored_world_population_too_small")
    source_assets = root / "Generated" / "Assets"
    required_assets = (
        "FrontierTerrain.fbx",
        "FrontierTree.fbx",
        "FrontierRock.fbx",
        "FrontierCreature.fbx",
    )
    for name in required_assets:
        path = source_assets / name
        if not path.is_file() or path.stat().st_size <= 0:
            failures.append(f"missing_generated_source_asset:{name}")
    texture_materials = (
        "ForestGround",
        "Bark",
        "Canopy",
        "Stone",
        "CreatureHide",
        "CreatureLimb",
        "CreatureHorn",
    )
    required_texture_sources = tuple(
        f"{material}_{map_name}.png"
        for material in texture_materials
        for map_name in ("BaseColor", "Normal", "ORM")
    )
    for name in required_texture_sources:
        path = root / "Generated" / "Textures" / name
        if not path.is_file() or path.stat().st_size <= 0:
            failures.append(f"missing_generated_texture_source:{name}")
    required_imports = (
        "FrontierTerrain.uasset",
        "FrontierTree.uasset",
        "FrontierRock.uasset",
        "FrontierCreature.uasset",
    ) + tuple(
        f"Materials/M_{material}.uasset" for material in texture_materials
    ) + tuple(
        f"Textures/{Path(name).stem}.uasset" for name in required_texture_sources
    )
    imported_assets = root / "Content" / "Generated"
    for name in required_imports:
        path = imported_assets / name
        if not path.is_file() or path.stat().st_size <= 0:
            failures.append(f"missing_imported_unreal_asset:{name}")
    audit_path = root / "Evidence" / "full-world-audit.json"
    if not audit_path.is_file():
        failures.append("missing_full_world_audit")
    else:
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            failures.append("invalid_full_world_audit")
        else:
            if audit.get("passed") is not True:
                failures.append("full_world_audit_failed")
            if int(audit.get("generated_actor_count", 0)) < 17:
                failures.append("generated_world_population_too_small")
    if manifest.get("playable") is True and failures:
        failures.append("manifest_overclaims_playable")
    return {
        "ok": not failures,
        "root": str(root),
        "playable": manifest.get("playable") is True and not failures,
        "required_gates": list(required),
        "package_suffixes": sorted(suffixes),
        "generated_assets": list(required_assets),
        "generated_texture_sources": list(required_texture_sources),
        "imported_unreal_assets": list(required_imports),
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print(json.dumps({"ok": False, "error": "usage: verify_playable_proof.py ROOT"}))
        return 2
    result = verify(Path(args[0]))
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
