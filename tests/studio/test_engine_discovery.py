from __future__ import annotations

from pathlib import Path

from agent.studio.engine_discovery import discover_unreal


def _fake_unreal(root: Path, version: str) -> tuple[Path, Path]:
    engine = root / f"UE_{version}"
    build = engine / "Engine" / "Build" / "BatchFiles" / "Build.bat"
    editor = engine / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"
    build.parent.mkdir(parents=True)
    editor.parent.mkdir(parents=True)
    build.write_text("@echo off", encoding="utf-8")
    editor.write_bytes(b"MZ")
    return build, editor


def test_discovers_supported_engine_from_explicit_roots(tmp_path: Path) -> None:
    build, editor = _fake_unreal(tmp_path, "5.6")
    found = discover_unreal(search_roots=[tmp_path])
    assert found is not None
    assert found.version == "5.6"
    assert found.build_tool == build.resolve()
    assert found.editor_command == editor.resolve()


def test_preferred_engine_wins_over_newer_install(tmp_path: Path) -> None:
    _fake_unreal(tmp_path, "5.6")
    _fake_unreal(tmp_path, "5.7")
    found = discover_unreal(preferred="5.6", search_roots=[tmp_path])
    assert found is not None and found.version == "5.6"


def test_partial_install_and_absent_engine_are_not_faked(tmp_path: Path) -> None:
    build = tmp_path / "UE_5.6" / "Engine" / "Build" / "BatchFiles" / "Build.bat"
    build.parent.mkdir(parents=True)
    build.write_text("@echo off", encoding="utf-8")
    assert discover_unreal(search_roots=[tmp_path]) is None
    assert discover_unreal(search_roots=[]) is None


def test_rejects_non_ue5_installations(tmp_path: Path) -> None:
    _fake_unreal(tmp_path, "4.27")
    assert discover_unreal(search_roots=[tmp_path]) is None
