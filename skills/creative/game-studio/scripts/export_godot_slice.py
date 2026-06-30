#!/usr/bin/env python3
"""Headless Godot 4 export for the Game Studio vertical slice.

Owner-gated engine spawn — modeled on the `ue5-render` skill's
``MUSE_UE5_ALLOW_SPAWN`` pattern. Without ``MUSE_GAME_ALLOW_SPAWN=1`` this
**dry-runs**: it prints the exact command it would run and reports
``"spawned": false`` so the owner can review before any process is launched.

Usage::

    python export_godot_slice.py [--project DIR] [--preset linux] [--out PATH] [--godot BIN]

Emits a single JSON object to stdout:

    {"success": bool, "spawned": bool, "artifact": str|None,
     "command": [...], "exit_code": int|None, "log_tail": str, "engine": "godot"}
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Default slice location: the reference slice co-located with this skill
# (…/skills/creative/game-studio/scripts/ → …/game-studio/reference-slice/).
_DEFAULT_PROJECT = Path(__file__).resolve().parents[1] / "reference-slice"
_SPAWN_ENV = "MUSE_GAME_ALLOW_SPAWN"


def _emit(payload: dict) -> int:
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("success") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Headless Godot export (owner-gated).")
    parser.add_argument("--project", default=str(_DEFAULT_PROJECT),
                        help="Godot project directory (contains project.godot).")
    parser.add_argument("--preset", default="linux",
                        help="export_presets.cfg preset name (default: linux).")
    parser.add_argument("--out", default=None,
                        help="Output artifact path (default: <project>/build/slice.x86_64).")
    parser.add_argument("--godot", default=os.environ.get("GODOT_BIN", "godot"),
                        help="Godot 4 executable (default: $GODOT_BIN or 'godot').")
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    out = Path(args.out).resolve() if args.out else (project / "build" / "slice.x86_64")
    command = [
        args.godot, "--headless", "--path", str(project),
        "--export-release", args.preset, str(out),
    ]

    if not (project / "project.godot").is_file():
        return _emit({
            "success": False, "spawned": False, "artifact": None,
            "command": command, "exit_code": None, "engine": "godot",
            "log_tail": f"No project.godot found in {project}",
        })

    # Owner gate: do not spawn a process unless explicitly authorized.
    if os.environ.get(_SPAWN_ENV) != "1":
        return _emit({
            "success": False, "spawned": False, "artifact": None,
            "command": command, "exit_code": None, "engine": "godot",
            "log_tail": (
                f"Engine spawn is gated. Set {_SPAWN_ENV}=1 to allow this "
                f"export. Dry-run command shown above."
            ),
        })

    if shutil.which(args.godot) is None and not Path(args.godot).is_file():
        return _emit({
            "success": False, "spawned": False, "artifact": None,
            "command": command, "exit_code": None, "engine": "godot",
            "log_tail": f"Godot executable not found: {args.godot!r}",
        })

    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(  # noqa: S603 — command is constructed, not shell
            command, capture_output=True, text=True, timeout=900,
        )
    except subprocess.TimeoutExpired:
        return _emit({
            "success": False, "spawned": True, "artifact": None,
            "command": command, "exit_code": None, "engine": "godot",
            "log_tail": "Godot export timed out (900s).",
        })

    log = (proc.stdout or "") + (proc.stderr or "")
    artifact_ok = out.is_file() and out.stat().st_size > 0
    return _emit({
        "success": proc.returncode == 0 and artifact_ok,
        "spawned": True,
        "artifact": str(out) if artifact_ok else None,
        "command": command,
        "exit_code": proc.returncode,
        "engine": "godot",
        "log_tail": log[-2000:],
    })


if __name__ == "__main__":
    sys.exit(main())
