"""AAA Game Foundry source packages with evidence-backed build claims."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .engine_discovery import UnrealInstallation, discover_unreal
from .game_verification import (
    discover_engine,
    evidence_as_dict,
    run_declared_commands,
    sha256_inventory,
)
from .types import GameBuildManifest, GameProductionSpec


PRODUCTION_LANES = (
    "concept", "gdd", "narrative", "characters", "systems", "economy",
    "accessibility", "concept_art", "mesh", "retopology", "uv", "pbr",
    "rigging", "animation", "lod", "gameplay", "ai", "physics", "audio",
    "ui", "save", "multiplayer", "analytics", "world_streaming",
    "procedural_generation", "tests", "packaging", "release",
)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "game"


class GameFoundry:
    """Materialize game-production lanes and run only declared real gates."""

    def __init__(
        self,
        root: str | Path,
        *,
        engine_discovery: Callable[..., UnrealInstallation | None] = discover_unreal,
        command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.root = Path(root)
        self.engine_discovery = engine_discovery
        self.command_runner = command_runner

    def create(self, spec: GameProductionSpec) -> GameBuildManifest:
        project_id = spec.project_id or _slug(spec.title)
        project_root = self.root / project_id
        project_root.mkdir(parents=True, exist_ok=True)
        self._write_spec(project_root, spec)
        self._write_lane_plan(project_root)
        self._write_engine_source(project_root, spec)
        status = discover_engine(
            spec.engine,
            spec.engine_version,
            unreal_discovery=self.engine_discovery,
        )
        manifest = GameBuildManifest(
            project_id=project_id,
            title=spec.title,
            root=project_root,
            lanes=PRODUCTION_LANES,
            engine=spec.engine,
            engine_version=status.version,
            engine_validation=status.validation,
            unavailable_reason=status.reason,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return self._persist_manifest(manifest)

    def build(self, spec: GameProductionSpec) -> GameBuildManifest:
        manifest = self.create(spec)
        status = discover_engine(
            spec.engine,
            spec.engine_version,
            unreal_discovery=self.engine_discovery,
        )
        if not status.available:
            return manifest

        commands = dict(spec.build_commands)
        commands.update(spec.test_commands)
        if not commands:
            return self._persist_manifest(
                replace(
                    manifest,
                    engine_validation="available_unbuilt",
                    unavailable_reason="no build or verification commands were declared",
                )
            )
        evidence = run_declared_commands(
            commands,
            cwd=manifest.root,
            evidence_dir=manifest.root / "Evidence" / "commands",
            runner=self.command_runner,
        )
        by_lane = {record.lane: record for record in evidence}
        build_records = [record for record in evidence if record.lane.startswith("build")]
        package_records = [record for record in evidence if record.lane.startswith("package")]
        smoke_records = [record for record in evidence if record.lane.startswith("smoke")]
        compiled = bool(build_records) and all(record.passed for record in build_records)
        package_verified = compiled and bool(package_records) and all(
            record.passed for record in package_records
        )
        smoke_verified = package_verified and bool(smoke_records) and all(
            record.passed for record in smoke_records
        )
        all_required_passed = all(record.passed for record in by_lane.values())
        inventory = sha256_inventory(manifest.root.rglob("*"), root=manifest.root)
        updated = replace(
            manifest,
            engine_validation=(
                "verified" if all_required_passed and compiled
                else "available_unbuilt" if all_required_passed
                else "verification_failed"
            ),
            compiled=compiled,
            package_verified=package_verified,
            smoke_verified=smoke_verified,
            playable=smoke_verified and all_required_passed,
            command_evidence=evidence_as_dict(evidence),
            artifact_hashes=inventory,
            unavailable_reason="" if all_required_passed else "one or more declared gates failed",
        )
        return self._persist_manifest(updated)

    @staticmethod
    def _write_spec(project_root: Path, spec: GameProductionSpec) -> None:
        path = project_root / "game-production-spec.json"
        path.write_text(json.dumps(asdict(spec), indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _write_lane_plan(project_root: Path) -> None:
        lanes = {
            lane: {
                "status": "planned",
                "claim": "No completion claim is made without attached evidence.",
            }
            for lane in PRODUCTION_LANES
        }
        (project_root / "production-lanes.json").write_text(
            json.dumps(lanes, indent=2, sort_keys=True), encoding="utf-8"
        )
        from .blueprints import load_open_world_rpg_blueprint

        domain_seed = {
            "claim": "Blueprint domains are planned work, not completion evidence.",
            "domains": load_open_world_rpg_blueprint().as_plan()["domains"],
        }
        (project_root / "open-world-domain-seed.json").write_text(
            json.dumps(domain_seed, indent=2, sort_keys=True), encoding="utf-8"
        )

    @staticmethod
    def _write_engine_source(project_root: Path, spec: GameProductionSpec) -> None:
        if spec.engine == "godot":
            (project_root / "project.godot").write_text(
                '[application]\nconfig/name="MUSE Foundry Game"\n'
                'run/main_scene="res://main.tscn"\n\n[display]\n'
                'window/size/viewport_width=1280\nwindow/size/viewport_height=720\n',
                encoding="utf-8",
            )
            (project_root / "main.tscn").write_text(
                '[gd_scene load_steps=2 format=3]\n\n'
                '[ext_resource path="res://main.gd" type="Script" id="1"]\n\n'
                '[node name="Main" type="Node2D"]\nscript = ExtResource("1")\n',
                encoding="utf-8",
            )
            (project_root / "main.gd").write_text(
                'extends Node2D\n\nfunc _draw() -> void:\n'
                '    draw_circle(Vector2(640, 360), 48, Color("6be4ff"))\n\n'
                'func _ready() -> void:\n    queue_redraw()\n',
                encoding="utf-8",
            )
            return
        if spec.engine == "unity":
            assets = project_root / "Assets" / "Scripts"
            assets.mkdir(parents=True, exist_ok=True)
            (assets / "FoundryBootstrap.cs").write_text(
                "using UnityEngine;\npublic sealed class FoundryBootstrap : MonoBehaviour {}\n",
                encoding="utf-8",
            )
            return

        source = project_root / "Source" / "Game"
        source.mkdir(parents=True, exist_ok=True)
        (project_root / "Config").mkdir(exist_ok=True)
        (project_root / "Content").mkdir(exist_ok=True)
        (project_root / "Game.uproject").write_text(
            json.dumps(
                {
                    "FileVersion": 3,
                    "EngineAssociation": spec.engine_version,
                    "Category": "Games",
                    "Description": spec.title,
                    "Modules": [
                        {"Name": "Game", "Type": "Runtime", "LoadingPhase": "Default"}
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (source / "Game.Build.cs").write_text(
            "using UnrealBuildTool;\npublic class Game : ModuleRules {\n"
            "    public Game(ReadOnlyTargetRules Target) : base(Target) {\n"
            '        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });\n'
            "    }\n}\n",
            encoding="utf-8",
        )
        (source / "Game.cpp").write_text(
            '#include "Modules/ModuleManager.h"\nIMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, Game, "Game");\n',
            encoding="utf-8",
        )

    @staticmethod
    def _persist_manifest(manifest: GameBuildManifest) -> GameBuildManifest:
        data = asdict(manifest)
        data["root"] = str(manifest.root)
        (manifest.root / "game-build-manifest.json").write_text(
            json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
        )
        return manifest


__all__ = ["GameFoundry", "PRODUCTION_LANES"]
