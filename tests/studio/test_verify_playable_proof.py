import json
from pathlib import Path

from scripts.verify_playable_proof import verify


GATES = (
    "build_editor",
    "author_map",
    "audit_map",
    "test_automation",
    "package_win64",
    "smoke_win64",
)
SOURCE_ASSETS = (
    "FrontierTerrain.fbx",
    "FrontierTree.fbx",
    "FrontierRock.fbx",
    "FrontierCreature.fbx",
)
TEXTURE_MATERIALS = (
    "ForestGround",
    "Bark",
    "Canopy",
    "Stone",
    "CreatureHide",
    "CreatureLimb",
    "CreatureHorn",
)
SOURCE_TEXTURES = tuple(
    f"{material}_{map_name}.png"
    for material in TEXTURE_MATERIALS
    for map_name in ("BaseColor", "Normal", "ORM")
)
IMPORTED_ASSETS = (
    "FrontierTerrain.uasset",
    "FrontierTree.uasset",
    "FrontierRock.uasset",
    "FrontierCreature.uasset",
) + tuple(
    f"Materials/M_{material}.uasset" for material in TEXTURE_MATERIALS
) + tuple(
    f"Textures/{Path(name).stem}.uasset" for name in SOURCE_TEXTURES
)


def _write(path: Path, content: bytes = b"proof") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _proof_tree(root: Path) -> None:
    manifest = {
        "playable": True,
        "gate_results": [
            {"name": name, "status": "passed", "exit_code": 0} for name in GATES
        ],
    }
    (root / "game-build-manifest.json").parent.mkdir(parents=True, exist_ok=True)
    (root / "game-build-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    logs = root / "Evidence/commands"
    logs.mkdir(parents=True)
    (logs / "author_map.log").write_text("MUSE_MAP_BUILT", encoding="utf-8")
    (logs / "audit_map.log").write_text("MUSE_AUDIT_PASS", encoding="utf-8")
    (logs / "package_win64.log").write_text("BUILD SUCCESSFUL", encoding="utf-8")
    (root / "Evidence/author-map-complete.json").write_text(
        json.dumps(
            {"passed": True, "actor_count": 21, "generated_actor_count": 17}
        ),
        encoding="utf-8",
    )
    for suffix in ("exe", "pak", "ucas", "utoc"):
        _write(root / f"Build/Win64/FrontierHunt.{suffix}")
    _write(root / "Content/Maps/MuseSlice.umap")
    for name in SOURCE_ASSETS:
        _write(root / "Generated/Assets" / name)
    for name in SOURCE_TEXTURES:
        _write(root / "Generated/Textures" / name)
    for name in IMPORTED_ASSETS:
        _write(root / "Content/Generated" / name)
    audit = {
        "passed": True,
        "generated_actor_count": 17,
        "required_assets": ["/Game/Generated/FrontierTerrain"],
    }
    (root / "Evidence/full-world-audit.json").write_text(
        json.dumps(audit), encoding="utf-8"
    )


def test_verify_playable_proof_requires_complete_generated_world(tmp_path: Path) -> None:
    _proof_tree(tmp_path)

    result = verify(tmp_path)

    assert result["ok"] is True
    assert result["playable"] is True


def test_verify_playable_proof_rejects_missing_material_and_sentinel(
    tmp_path: Path,
) -> None:
    _proof_tree(tmp_path)
    (tmp_path / "Content/Generated/Materials/M_Canopy.uasset").unlink()
    (tmp_path / "Evidence/author-map-complete.json").unlink()
    (tmp_path / "Evidence/commands/author_map.log").write_text(
        "LogPython: Error: map already exists", encoding="utf-8"
    )
    (tmp_path / "Evidence/commands/package_win64.log").write_text(
        "Failed to compile Material; doesn't have a valid ShaderMap", encoding="utf-8"
    )

    result = verify(tmp_path)

    assert result["ok"] is False
    assert "missing_imported_unreal_asset:Materials/M_Canopy.uasset" in result["failures"]
    assert "missing_author_map_completion_evidence" in result["failures"]
    assert "python_error_in_gate_log:author_map" in result["failures"]
    assert "generated_material_compile_failure" in result["failures"]
    assert "manifest_overclaims_playable" in result["failures"]
