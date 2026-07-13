from __future__ import annotations

import subprocess
from pathlib import Path

from agent.studio.engine_discovery import UnrealInstallation
from agent.studio.game_foundry import GameFoundry, PRODUCTION_LANES
from agent.studio.types import GameProductionSpec


def _spec(**overrides: object) -> GameProductionSpec:
    values = {
        "title": "Atlas Crown",
        "project_id": "atlas-crown",
        "engine": "unreal",
        "engine_version": "5.6",
        "platforms": ("windows",),
        "performance_budgets": {"frame_ms": 16.67},
        "accessibility_requirements": ("subtitles", "remapping"),
        "rights_checklist": ("asset provenance",),
        "rating_checklist": ("rating questionnaire",),
        "store_checklist": ("capsules",),
        "migration_plan": "migrate saves by schema version",
        "crash_telemetry": "owner-approved opt-in",
    }
    values.update(overrides)
    return GameProductionSpec(**values)


def test_game_manifest_covers_complete_production_lanes(tmp_path: Path) -> None:
    manifest = GameFoundry(tmp_path, engine_discovery=lambda: None).create(_spec())
    assert set(manifest.lanes) == set(PRODUCTION_LANES)
    assert (manifest.root / "production-lanes.json").is_file()
    assert (manifest.root / "Game.uproject").is_file()


def test_uncompiled_engine_package_is_not_marked_playable(tmp_path: Path) -> None:
    manifest = GameFoundry(tmp_path, engine_discovery=lambda: None).build(_spec())
    assert manifest.playable is False
    assert manifest.compiled is False
    assert manifest.engine_validation == "not_installed"


def test_playable_requires_build_package_smoke_and_declared_gates(tmp_path: Path) -> None:
    engine = tmp_path / "UE_5.6"
    found = UnrealInstallation(
        "5.6", engine, engine / "Build.bat", engine / "UnrealEditor-Cmd.exe"
    )

    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, stdout="passed", stderr="")

    spec = _spec(
        build_commands={
            "build_win64": ("build",),
            "package_win64": ("package",),
            "smoke_win64": ("smoke",),
        },
        test_commands={"test_unit": ("test",)},
    )
    manifest = GameFoundry(
        tmp_path / "foundry", engine_discovery=lambda: found, command_runner=runner
    ).build(spec)
    assert manifest.compiled is True
    assert manifest.package_verified is True
    assert manifest.smoke_verified is True
    assert manifest.playable is True
