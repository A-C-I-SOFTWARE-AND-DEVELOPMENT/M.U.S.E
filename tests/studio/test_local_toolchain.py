from pathlib import Path

from agent.studio.aaa_pipeline import AAAPipeline, AAAPipelineBrief
from agent.studio.engine_discovery import UnrealInstallation
from agent.studio.lingbot_previs import PrevisResult
from agent.studio.local_toolchain import discover_blender, unreal_commands


def test_discover_blender_honors_explicit_executable(tmp_path, monkeypatch):
    executable = tmp_path / "blender.exe"
    executable.write_bytes(b"proof")
    monkeypatch.setenv("BLENDER_EXECUTABLE", str(executable))

    assert discover_blender() == executable.resolve()


def test_unreal_commands_use_absolute_project_paths(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    uproject = project / "Proof.uproject"
    uproject.write_text("{}", encoding="utf-8")
    installation = UnrealInstallation(
        version="5.8",
        root=tmp_path / "UE_5.8",
        build_tool=tmp_path / "Build.bat",
        editor_command=tmp_path / "UnrealEditor-Cmd.exe",
        package_tool=tmp_path / "RunUAT.bat",
    )

    commands = unreal_commands(project, installation, package=True)

    assert str(uproject.resolve()) in commands["build_editor"]
    assert any(str(uproject.resolve()) in arg for arg in commands["package_win64"])
    assert "audit_world" in commands


def test_pipeline_records_successful_world_previs(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    source.write_bytes(b"png")
    video = tmp_path / "world.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "agent.studio.local_toolchain.generate_previs_source",
        lambda project_root: source,
    )
    monkeypatch.setattr(
        "agent.studio.lingbot_previs.run_previs",
        lambda request: PrevisResult(
            ok=True,
            status="passed",
            backend="reactor",
            video_path=str(video),
            metadata={"ok": True, "actual_frames": 10},
            license={"spdx": "LicenseRef-Test"},
            conditioning_dir=str(tmp_path / "conditioning"),
        ),
    )
    brief = AAAPipelineBrief(
        title="Previs Proof",
        genre="action-RPG",
        setting="original frontier",
        core_loop="track, hunt, craft",
        offline=True,
        generate_previs=True,
    )

    result = AAAPipeline(tmp_path / "output", resume=False).run(brief)

    assert "previs" in result.pipeline_manifest.stages_completed
    assert not result.stages_failed
