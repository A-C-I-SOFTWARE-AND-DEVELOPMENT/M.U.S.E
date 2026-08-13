"""Blender executor — headless deterministic builds (§36/§37).

Policy: production work happens on staging copies only; source hashes recorded
before and after; output hashed; QA gate runs on the result; promotion only on
pass. The `bpy` surface is never exposed to any model — only the bounded
macro-operations below, each backed by a deterministic bpy script.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class BlenderOp:
    name: str
    capabilities_required: tuple[str, ...]
    side_effects: str
    timeout_s: int = 600


OPS = {
    "create_base_geometry": BlenderOp("create_base_geometry", ("blender.write",),
                                      "writes new .blend in staging"),
    "apply_geometry_operation": BlenderOp("apply_geometry_operation", ("blender.write",),
                                          "modifies staged .blend"),
    "surface_asset": BlenderOp("surface_asset", ("blender.write",),
                               "assigns materials/UVs on staged asset"),
    "optimize_asset": BlenderOp("optimize_asset", ("blender.write",),
                                "decimate/cleanup on staged asset"),
    "export_asset": BlenderOp("export_asset", ("blender.write", "fbx.write"),
                              "writes export artifact in staging"),
}


class BlenderExecutor:
    """Runs `blender --background --python <script>` under a timeout with
    staging-only paths. If Blender is absent, preflight fails closed."""

    def __init__(self, staging_root: os.PathLike | str, blender_path: Optional[str] = None):
        self.staging_root = Path(staging_root).resolve()
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self.blender = blender_path or self._find_blender()

    @staticmethod
    def _find_blender() -> Optional[str]:
        for cand in (r"C:\Program Files\Blender Foundation",
                     r"C:\Program Files (x86)\Blender Foundation"):
            root = Path(cand)
            if root.is_dir():
                for exe in sorted(root.glob("Blender*\\blender.exe"), reverse=True):
                    return str(exe)
        return None

    def preflight(self) -> tuple[bool, str]:
        if not self.blender or not Path(self.blender).exists():
            return False, "blender_not_found"
        return True, ""

    def run_headless(self, script: Path, params: dict[str, Any],
                     timeout_s: int = 600) -> dict[str, Any]:
        ok, why = self.preflight()
        if not ok:
            return {"passed": False, "error": why}
        script_hash = hashlib.sha256(script.read_bytes()).hexdigest()
        t0 = time.time()
        proc = subprocess.run(
            [self.blender, "--background", "--factory-startup",
             "--python", str(script), "--", json.dumps(params)],
            capture_output=True, text=True, timeout=timeout_s,
            cwd=str(self.staging_root),
        )
        return {
            "script_hash": script_hash,
            "params": params,
            "exit_code": proc.returncode,
            "wall_clock_s": round(time.time() - t0, 2),
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
            "passed": proc.returncode == 0,
        }
