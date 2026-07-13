"""Truthful engine, command, package, and smoke-test evidence for games."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from .engine_discovery import UnrealInstallation, discover_unreal


@dataclass(frozen=True)
class EngineAdapterStatus:
    engine: str
    version: str
    available: bool
    validation: str
    build_tool: str = ""
    editor_command: str = ""
    reason: str = ""


@dataclass(frozen=True)
class CommandEvidence:
    lane: str
    argv: tuple[str, ...]
    exit_code: int
    stdout_path: str
    stderr_path: str
    passed: bool


Runner = Callable[..., subprocess.CompletedProcess[str]]


def discover_engine(
    engine: str,
    version: str,
    *,
    unreal_discovery: Callable[..., UnrealInstallation | None] = discover_unreal,
) -> EngineAdapterStatus:
    """Return installed-engine evidence without inventing availability."""

    if engine == "unreal":
        try:
            found = unreal_discovery(preferred=version)
        except TypeError:
            found = unreal_discovery()
        if found is None:
            return EngineAdapterStatus(
                engine, version, False, "not_installed", reason="Unreal Engine was not discovered"
            )
        return EngineAdapterStatus(
            engine,
            found.version,
            True,
            "available_unbuilt",
            str(found.build_tool),
            str(found.editor_command),
        )
    executable = shutil.which("godot4") or shutil.which("godot") if engine == "godot" else None
    if engine == "unity":
        executable = shutil.which("Unity") or shutil.which("unity-editor")
    if executable is None:
        return EngineAdapterStatus(
            engine,
            version,
            False,
            "not_installed",
            reason=f"{engine.title()} executable was not discovered",
        )
    return EngineAdapterStatus(
        engine, version, True, "available_unbuilt", executable, executable
    )


def run_declared_commands(
    commands: Mapping[str, Sequence[str]],
    *,
    cwd: Path,
    evidence_dir: Path,
    runner: Runner = subprocess.run,
    timeout_seconds: int = 3600,
) -> tuple[CommandEvidence, ...]:
    """Run argv-only commands and persist complete stdout/stderr evidence."""

    evidence_dir.mkdir(parents=True, exist_ok=True)
    records: list[CommandEvidence] = []
    for lane, command in commands.items():
        argv = tuple(str(part) for part in command)
        if not argv:
            raise ValueError(f"{lane} command cannot be empty")
        completed = runner(
            list(argv),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout_path = evidence_dir / f"{lane}.stdout.log"
        stderr_path = evidence_dir / f"{lane}.stderr.log"
        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")
        records.append(
            CommandEvidence(
                lane=lane,
                argv=argv,
                exit_code=int(completed.returncode),
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                passed=completed.returncode == 0,
            )
        )
    return tuple(records)


def sha256_inventory(paths: Iterable[Path], *, root: Path) -> dict[str, str]:
    inventory: dict[str, str] = {}
    for path in sorted((item for item in paths if item.is_file()), key=lambda item: str(item)):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        key = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
        inventory[key] = "sha256:" + digest.hexdigest()
    return inventory


def evidence_as_dict(records: Iterable[CommandEvidence]) -> tuple[dict[str, object], ...]:
    return tuple(asdict(record) for record in records)


__all__ = [
    "CommandEvidence",
    "EngineAdapterStatus",
    "discover_engine",
    "evidence_as_dict",
    "run_declared_commands",
    "sha256_inventory",
]
