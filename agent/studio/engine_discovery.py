"""Truthful, cross-platform Unreal Engine discovery for Studio outputs."""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_UE_DIR = re.compile(r"^UE_(\d+)\.(\d+)$")


@dataclass(frozen=True)
class UnrealInstallation:
    version: str
    root: Path
    build_tool: Path
    editor_command: Path


def _default_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    configured = os.environ.get("UNREAL_ENGINE_ROOT")
    if configured:
        path = Path(configured).expanduser()
        # A direct UE_5.x root is handled alongside parent install roots.
        roots.extend((path, path.parent))
    if sys.platform == "win32":
        for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
            base = os.environ.get(variable)
            if base:
                roots.append(Path(base) / "Epic Games")
        roots.append(Path("C:/Program Files/Epic Games"))
    elif sys.platform == "darwin":
        roots.extend((Path("/Users/Shared/Epic Games"), Path("/Applications")))
    else:
        roots.extend((Path("/opt"), Path.home() / "UnrealEngine"))
    return tuple(dict.fromkeys(roots))


def _installation(candidate: Path, version: str) -> UnrealInstallation | None:
    if sys.platform == "win32" or (candidate / "Engine/Build/BatchFiles/Build.bat").exists():
        build = candidate / "Engine/Build/BatchFiles/Build.bat"
        editor_candidates = (
            candidate / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe",
            candidate / "Engine/Binaries/Win64/UnrealEditor.exe",
        )
    elif sys.platform == "darwin":
        build = candidate / "Engine/Build/BatchFiles/Mac/Build.sh"
        editor_candidates = (
            candidate / "Engine/Binaries/Mac/UnrealEditor-Cmd",
            candidate / "Engine/Binaries/Mac/UnrealEditor",
        )
    else:
        build = candidate / "Engine/Build/BatchFiles/Linux/Build.sh"
        editor_candidates = (
            candidate / "Engine/Binaries/Linux/UnrealEditor-Cmd",
            candidate / "Engine/Binaries/Linux/UnrealEditor",
        )
    editor = next((path for path in editor_candidates if path.is_file()), None)
    if not build.is_file() or editor is None:
        return None
    return UnrealInstallation(version, candidate.resolve(), build.resolve(), editor.resolve())


def discover_unreal(
    preferred: str = "5.6",
    *,
    search_roots: Iterable[str | Path] | None = None,
) -> UnrealInstallation | None:
    """Return a complete UE install, never a guessed or partial installation."""

    roots_source = _default_roots() if search_roots is None else search_roots
    roots = tuple(Path(root).expanduser() for root in roots_source)
    discovered: dict[Path, UnrealInstallation] = {}
    for root in roots:
        candidates: list[Path] = []
        direct_match = _UE_DIR.match(root.name)
        if direct_match:
            candidates.append(root)
        if root.is_dir():
            try:
                candidates.extend(
                    child for child in root.iterdir() if child.is_dir() and _UE_DIR.match(child.name)
                )
            except OSError:
                continue
        for candidate in candidates:
            match = _UE_DIR.match(candidate.name)
            if match is None:
                continue
            version = f"{int(match.group(1))}.{int(match.group(2))}"
            if int(match.group(1)) != 5:
                continue
            found = _installation(candidate, version)
            if found is not None:
                discovered[found.root] = found
    if not discovered:
        return None

    def order(item: UnrealInstallation) -> tuple[int, int, int]:
        major, minor = (int(part) for part in item.version.split(".", 1))
        return (int(item.version == preferred), major, minor)

    return max(discovered.values(), key=order)


__all__ = ["UnrealInstallation", "discover_unreal"]
