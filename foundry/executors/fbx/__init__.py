"""FBX executor — narrow deterministic operations with full provenance (§36/§38).

Every operation: works on a staging copy, records source/result hashes, runs
validation, never overwrites sources. No unrestricted filesystem access:
paths must live under an allowed staging root.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class OperationContract:
    """§36 executor operation contract."""
    name: str
    input_schema: dict[str, Any]
    capabilities_required: tuple[str, ...]
    side_effects: str
    allowed_root: str
    timeout_s: int = 300


CONTRACTS = {
    "import_fbx": OperationContract(
        name="import_fbx",
        input_schema={"path": "string"},
        capabilities_required=("fbx.read",),
        side_effects="reads source; writes staging copy",
        allowed_root="staging",
    ),
    "export_fbx": OperationContract(
        name="export_fbx",
        input_schema={"path": "string", "scale": "number?"},
        capabilities_required=("fbx.write",),
        side_effects="writes new file in staging; never overwrites source",
        allowed_root="staging",
    ),
    "validate_fbx": OperationContract(
        name="validate_fbx",
        input_schema={"path": "string"},
        capabilities_required=("fbx.read",),
        side_effects="none (read-only)",
        allowed_root="staging",
    ),
}


@dataclass
class FbxEvidence:
    operation: str
    source_path: str
    source_hash: str
    parameters: dict[str, Any]
    result_path: str = ""
    result_hash: str = ""
    validation: dict[str, Any] = field(default_factory=dict)
    tool: str = "foundry.executors.fbx/1.0"
    at: float = field(default_factory=time.time)


class FbxExecutor:
    """Staging-only FBX operations. The heavy lifting (real format conversion)
    is delegated to a backend callable — Blender headless or an FBX SDK bridge —
    injected at construction. This class owns path safety + provenance."""

    def __init__(self, staging_root: os.PathLike | str, backend=None):
        self.staging_root = Path(staging_root).resolve()
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self.backend = backend  # callable(op, params, src, dst) -> dict validation

    def _check_path(self, path: os.PathLike | str) -> Path:
        p = Path(path).resolve()
        if not str(p).startswith(str(self.staging_root)):
            raise PermissionError(f"path {p} outside staging root {self.staging_root}")
        return p

    def stage_source(self, source: os.PathLike | str) -> Path:
        """Copy a source asset into staging (§37: never work on the original)."""
        src = Path(source)
        if not src.exists():
            raise FileNotFoundError(src)
        dst = self.staging_root / f"{src.stem}.staged{src.suffix}"
        shutil.copy2(src, dst)
        return dst

    def execute(self, operation: str, parameters: dict[str, Any],
                capabilities: set[str]) -> FbxEvidence:
        if operation not in CONTRACTS:
            raise ValueError(f"unknown operation {operation!r}")
        contract = CONTRACTS[operation]
        missing = set(contract.capabilities_required) - capabilities
        if missing:
            raise PermissionError(f"missing capabilities {missing}")

        src = self._check_path(parameters["path"])
        ev = FbxEvidence(operation=operation, source_path=str(src),
                         source_hash=_sha256(src), parameters=dict(parameters))

        if operation == "validate_fbx":
            ev.validation = self._validate(src)
        elif self.backend is not None:
            dst = src.with_suffix(".out" + src.suffix)
            ev.validation = self.backend(operation, parameters, src, dst)
            if dst.exists():
                ev.result_path = str(dst)
                ev.result_hash = _sha256(dst)
        else:
            ev.validation = {"skipped": "no backend configured"}
        return ev

    @staticmethod
    def _validate(path: Path) -> dict[str, Any]:
        """Minimal structural validation: exists, non-empty, FBX magic/version sniff."""
        size = path.stat().st_size
        head = path.read_bytes()[:32]
        is_binary_fbx = head.startswith(b"Kaydara FBX Binary")
        looks_ascii_fbx = b"FBX" in head[:16] or b"; FBX" in head
        return {
            "exists": True,
            "size_bytes": size,
            "binary_fbx_magic": bool(is_binary_fbx),
            "ascii_fbx_hint": bool(looks_ascii_fbx),
            "nonempty": size > 0,
            "passed": size > 0 and (is_binary_fbx or looks_ascii_fbx),
        }
