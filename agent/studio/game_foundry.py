"""AAA Game Foundry source packages with evidence-backed build claims."""
from __future__ import annotations

import json
import hashlib
import os
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
from .types import (
    BuildGateResult,
    GameBuildManifest,
    GameProductionSpec,
    VerticalSliceSpec,
)
from .ue5_vertical_slice import generate_ue5_vertical_slice


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
        vertical_data = spec.metadata.get("vertical_slice") if spec.metadata else None
        if isinstance(vertical_data, dict):
            data = dict(vertical_data)
            data["player_verbs"] = tuple(data.get("player_verbs") or ())
            data["zones"] = tuple(data.get("zones") or ())
            generate_ue5_vertical_slice(project_root, VerticalSliceSpec(**data))
        else:
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

    def build_vertical_slice(
        self,
        spec: GameProductionSpec,
        *,
        allow_spawn: bool = False,
        resume: bool = True,
    ) -> GameBuildManifest:
        """Generate and gate a UE5 slice; engine execution is owner-gated."""

        manifest = self.create(spec)
        try:
            found = self.engine_discovery(preferred=spec.engine_version)
        except TypeError:
            found = self.engine_discovery()
        if found is None:
            return self._persist_manifest(
                replace(
                    manifest,
                    engine_validation="not_installed",
                    unavailable_reason="Unreal Engine 5.8 was not discovered",
                )
            )
        commands = self._vertical_slice_commands(manifest.root, spec, found)
        plan_path = manifest.root / "Evidence" / "build-plan.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(
            json.dumps({name: list(argv) for name, argv in commands.items()}, indent=2),
            encoding="utf-8",
        )
        if not allow_spawn or os.environ.get("MUSE_GAME_ALLOW_SPAWN") != "1":
            blocked = tuple(
                asdict(
                    BuildGateResult(
                        name=name,
                        status="blocked",
                        command=argv,
                        reason=(
                            "engine spawn requires explicit owner authorization and "
                            "MUSE_GAME_ALLOW_SPAWN=1"
                        ),
                    )
                )
                for name, argv in commands.items()
            )
            return self._persist_manifest(
                replace(
                    manifest,
                    engine_version=found.version,
                    engine_validation="available_unbuilt",
                    gate_results=blocked,
                    unavailable_reason="engine_spawn_not_authorized",
                )
            )
        return self._run_vertical_slice_gates(
            manifest, spec, found, commands, resume=resume
        )

    def build(self, spec: GameProductionSpec) -> GameBuildManifest:
        if isinstance((spec.metadata or {}).get("vertical_slice"), dict):
            return self.build_vertical_slice(
                spec,
                allow_spawn=os.environ.get("MUSE_GAME_ALLOW_SPAWN") == "1",
            )
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
    def _vertical_slice_commands(
        project_root: Path,
        spec: GameProductionSpec,
        found: UnrealInstallation,
    ) -> dict[str, tuple[str, ...]]:
        module = spec.project_id
        uproject = project_root / f"{module}.uproject"
        editor = found.editor_command
        package_tool = found.package_tool or (
            found.root / "Engine/Build/BatchFiles/RunUAT.bat"
        )
        archive = project_root / "Build" / "Win64"
        packaged_exe = archive / f"{module}.exe"
        return {
            "build_editor": (
                str(found.build_tool),
                f"{module}Editor",
                "Win64",
                "Development",
                str(uproject),
                "-WaitMutex",
                "-NoHotReload",
            ),
            "author_map": (
                str(editor),
                str(uproject),
                f"-ExecutePythonScript={project_root / 'Content/Python/build_slice.py'}",
                "-unattended",
                "-nop4",
                "-nosplash",
            ),
            "audit_map": (
                str(editor),
                str(uproject),
                f"-ExecutePythonScript={project_root / 'Content/Python/audit_slice.py'}",
                "-unattended",
                "-nop4",
                "-nullrhi",
            ),
            "test_automation": (
                str(editor),
                str(uproject),
                f"-ExecCmds=Automation RunTests {module}.VerticalSlice;Quit",
                "-TestExit=Automation Test Queue Empty",
                "-unattended",
                "-nop4",
                "-nullrhi",
                "-nosplash",
            ),
            "package_win64": (
                str(package_tool),
                "BuildCookRun",
                f"-project={uproject}",
                "-noP4",
                "-platform=Win64",
                "-clientconfig=Development",
                "-build",
                "-cook",
                "-stage",
                "-pak",
                "-package",
                "-archive",
                f"-archivedirectory={archive}",
                "-utf8output",
            ),
            "smoke_win64": (
                str(packaged_exe),
                "-unattended",
                "-nullrhi",
                "-nosound",
                "-ExecCmds=quit",
            ),
        }

    @staticmethod
    def _source_fingerprint(project_root: Path) -> str:
        digest = hashlib.sha256()
        roots = [
            project_root / "Source",
            project_root / "Config",
            project_root / "Generated",
        ]
        files = [project_root / "game-spec.json"]
        files.extend(project_root.glob("*.uproject"))
        for root in roots:
            if root.is_dir():
                files.extend(path for path in root.rglob("*") if path.is_file())
        for path in sorted(files, key=lambda value: str(value)):
            digest.update(path.relative_to(project_root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
        return "sha256:" + digest.hexdigest()

    @staticmethod
    def _gate_artifacts(project_root: Path, gate: str, module: str) -> tuple[str, ...]:
        if gate == "build_editor":
            matches = list((project_root / "Binaries" / "Win64").glob(f"*{module}*"))
        elif gate == "author_map":
            matches = [project_root / "Content" / "Maps" / "MuseSlice.umap"]
        elif gate == "package_win64":
            build = project_root / "Build" / "Win64"
            matches = [
                path
                for suffix in ("*.exe", "*.pak", "*.ucas", "*.utoc")
                for path in build.rglob(suffix)
            ]
        elif gate == "smoke_win64":
            matches = list((project_root / "Build" / "Win64").rglob(f"{module}.exe"))
        else:
            matches = []
        return tuple(str(path) for path in matches if path.is_file() and path.stat().st_size > 0)

    def _run_vertical_slice_gates(
        self,
        manifest: GameBuildManifest,
        spec: GameProductionSpec,
        found: UnrealInstallation,
        commands: dict[str, tuple[str, ...]],
        *,
        resume: bool,
    ) -> GameBuildManifest:
        evidence_dir = manifest.root / "Evidence" / "commands"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        state_path = manifest.root / "Evidence" / "gate-state.json"
        previous: dict[str, dict[str, object]] = {}
        if resume and state_path.is_file():
            try:
                loaded = json.loads(state_path.read_text(encoding="utf-8"))
                previous = loaded if isinstance(loaded, dict) else {}
            except (OSError, json.JSONDecodeError):
                previous = {}
        source_fingerprint = self._source_fingerprint(manifest.root)
        results: list[BuildGateResult] = []
        state: dict[str, dict[str, object]] = dict(previous)
        module = spec.project_id

        for name, argv in commands.items():
            command_fingerprint = "sha256:" + hashlib.sha256(
                ("\0".join(argv) + "\0" + source_fingerprint).encode("utf-8")
            ).hexdigest()
            old = previous.get(name) or {}
            old_artifacts = tuple(str(item) for item in old.get("artifacts") or ())
            can_resume = (
                resume
                and old.get("status") == "passed"
                and old.get("fingerprint") == command_fingerprint
                and all(Path(path).is_file() for path in old_artifacts)
            )
            # Audit/automation produce logs rather than additional build artifacts.
            if name in {"audit_map", "test_automation"}:
                can_resume = (
                    resume
                    and old.get("status") == "passed"
                    and old.get("fingerprint") == command_fingerprint
                    and bool(old.get("log_path"))
                    and Path(str(old["log_path"])).is_file()
                )
            if can_resume:
                result = BuildGateResult(
                    name=name,
                    status="passed",
                    command=argv,
                    exit_code=0,
                    log_path=str(old.get("log_path") or ""),
                    artifacts=old_artifacts,
                    fingerprint=command_fingerprint,
                    reason="resumed_from_verified_gate",
                )
                results.append(result)
                continue

            try:
                completed = self.command_runner(
                    list(argv),
                    cwd=str(manifest.root),
                    capture_output=True,
                    text=True,
                    timeout=7200,
                    check=False,
                )
            except OSError as exc:
                completed = subprocess.CompletedProcess(
                    list(argv), 127, stdout="", stderr=str(exc)
                )
            log_path = evidence_dir / f"{name}.log"
            log_path.write_text(
                (completed.stdout or "") + "\n--- STDERR ---\n" + (completed.stderr or ""),
                encoding="utf-8",
            )
            artifacts = self._gate_artifacts(manifest.root, name, module)
            artifact_required = name in {
                "build_editor", "author_map", "package_win64", "smoke_win64"
            }
            package_complete = True
            if name == "package_win64":
                suffixes = {Path(path).suffix.lower() for path in artifacts}
                package_complete = {".exe", ".pak", ".ucas", ".utoc"}.issubset(suffixes)
            passed = (
                completed.returncode == 0
                and (not artifact_required or bool(artifacts))
                and package_complete
            )
            reason = "" if passed else (
                "command_failed" if completed.returncode != 0 else "required_artifact_missing"
            )
            result = BuildGateResult(
                name=name,
                status="passed" if passed else "failed",
                command=argv,
                exit_code=int(completed.returncode),
                log_path=str(log_path),
                artifacts=artifacts,
                fingerprint=command_fingerprint,
                reason=reason,
            )
            results.append(result)
            state[name] = asdict(result)
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
            if not passed:
                break

        by_name = {result.name: result for result in results}
        compiled = by_name.get("build_editor", BuildGateResult("x", "pending")).status == "passed"
        package_verified = (
            by_name.get("package_win64", BuildGateResult("x", "pending")).status == "passed"
        )
        smoke_verified = (
            by_name.get("smoke_win64", BuildGateResult("x", "pending")).status == "passed"
        )
        all_required = len(results) == len(commands) and all(
            result.status == "passed" for result in results
        )
        inventory = sha256_inventory(manifest.root.rglob("*"), root=manifest.root)
        return self._persist_manifest(
            replace(
                manifest,
                engine_version=found.version,
                engine_validation="verified" if all_required else "verification_failed",
                compiled=compiled,
                package_verified=package_verified,
                smoke_verified=smoke_verified,
                playable=all_required and compiled and package_verified and smoke_verified,
                gate_results=tuple(asdict(result) for result in results),
                artifact_hashes=inventory,
                unavailable_reason="" if all_required else "one or more required gates failed",
            )
        )

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

        from agent.studio.quality_profiles import load_quality_profile
        from agent.studio.ue5_generator import generate_ue5_project

        profile_name = str(spec.metadata.get("quality_profile", "high_fidelity"))
        try:
            profile = load_quality_profile(profile_name)
        except ValueError:
            profile = load_quality_profile("high_fidelity")
        generate_ue5_project(
            project_root,
            title=spec.title,
            engine_version=spec.engine_version,
            profile=profile,
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
