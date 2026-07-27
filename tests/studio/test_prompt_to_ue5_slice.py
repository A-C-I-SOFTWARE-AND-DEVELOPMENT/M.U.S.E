from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import pytest

from agent.studio.engine_discovery import UnrealInstallation
from agent.studio.game_foundry import GameFoundry
from agent.studio.lingbot_previs import (
    CameraKeyframe,
    PrevisRequest,
    run_previs,
    write_camera_conditioning,
)
from agent.studio.prompt_spec import (
    parse_vertical_slice_prompt,
    to_game_production_spec,
)
from agent.studio.ue5_vertical_slice import generate_ue5_vertical_slice


PROMPT = (
    '"Ashfall Beacon": build a dark fantasy third-person action RPG set in '
    "a drowned volcanic kingdom where a warden recovers three sun relics."
)


def test_one_prompt_produces_stable_valid_spec() -> None:
    first = parse_vertical_slice_prompt(PROMPT)
    second = parse_vertical_slice_prompt(PROMPT)
    assert first == second
    assert first.title == "Ashfall Beacon"
    assert first.engine_version == "5.8"
    assert len(first.zones) == 3
    assert {"move", "attack", "interact"}.issubset(set(first.player_verbs))
    assert 15 <= first.target_minutes <= 30


def test_short_prompt_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 20"):
        parse_vertical_slice_prompt("make game")


def test_generator_materializes_source_complete_ue58_project(tmp_path: Path) -> None:
    spec = parse_vertical_slice_prompt(PROMPT)
    root = generate_ue5_vertical_slice(tmp_path / spec.project_id, spec)
    project = json.loads((root / f"{spec.project_id}.uproject").read_text())
    assert project["EngineAssociation"] == "5.8"
    source = root / "Source" / spec.project_id
    required = {
        f"{spec.project_id}Character.cpp",
        f"{spec.project_id}Actors.cpp",
        f"{spec.project_id}GameMode.cpp",
        f"{spec.project_id}HUD.cpp",
        f"{spec.project_id}Automation.cpp",
    }
    assert required.issubset({path.name for path in source.iterdir()})
    assert (root / "Content/Python/build_slice.py").is_file()
    assert (root / "Content/Python/audit_slice.py").is_file()
    for name in ("Ambience.wav", "Pickup.wav", "Defeat.wav"):
        path = root / "Generated" / "Audio" / name
        with wave.open(str(path), "rb") as audio:
            assert audio.getnframes() > 0
            assert audio.getnchannels() == 2


def test_lingbot_conditioning_preserves_authoritative_ue_trajectory(
    tmp_path: Path,
) -> None:
    np = pytest.importorskip("numpy")
    image = tmp_path / "source.png"
    image.write_bytes(b"image")
    request = PrevisRequest(
        prompt="A cinematic tracking shot through the drowned kingdom",
        source_image=image,
        camera_keyframes=(
            CameraKeyframe((0, 0, 180), (-5, 0, 0)),
            CameraKeyframe((500, 100, 200), (-3, 15, 0)),
        ),
        output_dir=tmp_path / "previs",
        trajectory_id="ashfall-intro",
    )
    conditioning = write_camera_conditioning(request)
    assert np.load(conditioning / "poses.npy").shape == (2, 4, 4)
    assert np.load(conditioning / "intrinsics.npy").shape == (2, 4)
    trajectory = json.loads(
        (conditioning / "ue-camera-trajectory.json").read_text(encoding="utf-8")
    )
    assert trajectory["authoritative"] is True
    assert trajectory["trajectory_id"] == "ashfall-intro"


def test_previs_requires_decodable_verified_video(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = tmp_path / "source.png"
    image.write_bytes(b"image")
    router = tmp_path / "router.py"
    router.write_text("# router", encoding="utf-8")
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not-empty")
    request = PrevisRequest(
        prompt="A cinematic tracking shot through the drowned kingdom",
        source_image=image,
        camera_keyframes=(
            CameraKeyframe((0, 0, 180), (0, 0, 0)),
            CameraKeyframe((500, 0, 180), (0, 0, 0)),
        ),
        output_dir=tmp_path / "previs",
        trajectory_id="ashfall-intro",
    )

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        payload = {
            "ok": True,
            "backend": "lingbot-local",
            "video_path": str(video),
            "license": {"spdx": "CC-BY-NC-SA-4.0", "commercial_use": False},
        }
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(
        "agent.studio.lingbot_previs.inspect_video",
        lambda _: {"ok": True, "width": 832, "height": 480, "actual_frames": 17},
    )
    result = run_previs(request, router=router, runner=runner)
    assert result.ok is True
    assert result.backend == "lingbot-local"
    assert result.license["commercial_use"] is False


def test_vertical_build_is_blocked_without_owner_spawn_gate(tmp_path: Path) -> None:
    vertical = parse_vertical_slice_prompt(PROMPT)
    production = to_game_production_spec(vertical)
    engine = tmp_path / "UE_5.8"
    found = UnrealInstallation(
        "5.8",
        engine,
        engine / "Build.bat",
        engine / "UnrealEditor-Cmd.exe",
        engine / "RunUAT.bat",
    )
    manifest = GameFoundry(
        tmp_path / "foundry", engine_discovery=lambda: found
    ).build_vertical_slice(production, allow_spawn=False)
    assert manifest.playable is False
    assert manifest.unavailable_reason == "engine_spawn_not_authorized"
    assert manifest.gate_results
    assert all(gate["status"] == "blocked" for gate in manifest.gate_results)


def test_playable_requires_all_real_vertical_slice_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    vertical = parse_vertical_slice_prompt(PROMPT)
    production = to_game_production_spec(vertical)
    engine = tmp_path / "UE_5.8"
    found = UnrealInstallation(
        "5.8",
        engine,
        engine / "Build.bat",
        engine / "UnrealEditor-Cmd.exe",
        engine / "RunUAT.bat",
    )
    foundry_root = tmp_path / "foundry"
    project = foundry_root / production.project_id
    calls: list[tuple[str, ...]] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(tuple(argv))
        command = " ".join(argv)
        if "Editor Win64 Development" in command:
            artifact = project / "Binaries/Win64" / f"UnrealEditor-{production.project_id}.dll"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(b"dll")
        if "build_slice.py" in command:
            artifact = project / "Content/Maps/MuseSlice.umap"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(b"map")
        if "BuildCookRun" in command:
            output = project / "Build/Win64"
            output.mkdir(parents=True, exist_ok=True)
            (output / f"{production.project_id}.exe").write_bytes(b"exe")
            paks = output / production.project_id / "Content/Paks"
            paks.mkdir(parents=True, exist_ok=True)
            for suffix in ("pak", "ucas", "utoc"):
                (paks / f"{production.project_id}.{suffix}").write_bytes(suffix.encode())
        return subprocess.CompletedProcess(argv, 0, stdout="passed", stderr="")

    monkeypatch.setenv("MUSE_GAME_ALLOW_SPAWN", "1")
    foundry = GameFoundry(
        foundry_root, engine_discovery=lambda: found, command_runner=runner
    )
    manifest = foundry.build_vertical_slice(production, allow_spawn=True)
    assert manifest.compiled is True
    assert manifest.package_verified is True
    assert manifest.smoke_verified is True
    assert manifest.playable is True
    assert len(manifest.gate_results) == 6
    assert all(gate["status"] == "passed" for gate in manifest.gate_results)

    calls.clear()
    resumed = foundry.build_vertical_slice(production, allow_spawn=True, resume=True)
    assert resumed.playable is True
    assert calls == []
    assert all(gate["reason"] == "resumed_from_verified_gate" for gate in resumed.gate_results)
