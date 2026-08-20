"""Immutable benchmark run directories (Work Packet §12.2, §14.3, Phase 0).

A `latest` pointer may move. A finished run directory is never overwritten.
Every finalize() writes hashes.sha256 over the artifacts that already exist.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

__all__ = ["ImmutableRun", "RunCollision", "default_runs_root"]


class RunCollision(FileExistsError):
    """Raised when a caller tries to mutate a finished or existing run."""


def default_runs_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[2] / "runs"


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write(path: Path, data: str | bytes, *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise RunCollision(f"refusing to overwrite {path}")
    tmp = path.with_suffix(path.suffix + ".tmp")
    if isinstance(data, str):
        tmp.write_text(data, encoding="utf-8")
    else:
        tmp.write_bytes(data)
    os.replace(tmp, path)


def _git_sha(repo: Path) -> Optional[str]:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or None
    except Exception:
        return None


@dataclass
class ImmutableRun:
    """One frozen benchmark execution.

    Layout (Work Packet §14.3)::

        runs/<benchmark>/<UTC-run-id>/
          manifest.json config.json environment.json
          tasks.jsonl results.jsonl
          trajectories/ validator_outputs/ logs/
          git_diff.patch summary.json hashes.sha256
    """

    benchmark: str
    root: Path = field(default_factory=default_runs_root)
    run_id: str = field(default_factory=_utc_run_id)
    _finalized: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.benchmark or "/" in self.benchmark or "\\" in self.benchmark:
            raise ValueError("benchmark name must be a single path segment")
        self.dir.mkdir(parents=True, exist_ok=True)
        for sub in ("trajectories", "validator_outputs", "logs"):
            (self.dir / sub).mkdir(exist_ok=True)

    @property
    def dir(self) -> Path:
        return Path(self.root) / self.benchmark / self.run_id

    @property
    def finalized(self) -> bool:
        return self._finalized or (self.dir / "hashes.sha256").exists()

    def write_json(self, name: str, payload: Any, *, overwrite: bool = False) -> Path:
        if self.finalized and not overwrite:
            raise RunCollision(f"run {self.run_id} is finalized")
        path = self.dir / name
        _atomic_write(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n", overwrite=overwrite)
        return path

    def write_manifest(self, **fields: Any) -> Path:
        repo = Path(__file__).resolve().parents[2]
        body = {
            "benchmark": self.benchmark,
            "run_id": self.run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "repo_sha": _git_sha(repo),
            **fields,
        }
        return self.write_json("manifest.json", body)

    def write_config(self, config: dict[str, Any]) -> Path:
        return self.write_json("config.json", config)

    def write_environment(self, extra: Optional[dict[str, Any]] = None) -> Path:
        env = {
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
            "cwd": os.getcwd(),
        }
        if extra:
            env.update(extra)
        return self.write_json("environment.json", env)

    def append_jsonl(self, name: str, record: dict[str, Any]) -> None:
        if self.finalized:
            raise RunCollision(f"run {self.run_id} is finalized")
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def append_task(self, record: dict[str, Any]) -> None:
        self.append_jsonl("tasks.jsonl", record)

    def append_result(self, record: dict[str, Any]) -> None:
        self.append_jsonl("results.jsonl", record)

    def write_summary(self, summary: dict[str, Any]) -> Path:
        return self.write_json("summary.json", summary)

    def write_git_diff(self, repo: Optional[Path] = None) -> Path:
        repo = repo or Path(__file__).resolve().parents[2]
        try:
            diff = subprocess.check_output(
                ["git", "diff", "HEAD"],
                cwd=repo,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            diff = b""
        path = self.dir / "git_diff.patch"
        _atomic_write(path, diff)
        return path

    def finalize(self, *, latest: bool = True) -> Path:
        if self.finalized and (self.dir / "hashes.sha256").exists():
            raise RunCollision(f"run {self.run_id} already finalized")
        lines: list[str] = []
        for path in sorted(p for p in self.dir.rglob("*") if p.is_file()):
            if path.name in {"hashes.sha256", "hashes.sha256.tmp"}:
                continue
            rel = path.relative_to(self.dir).as_posix()
            lines.append(f"{_sha256_file(path)}  {rel}")
        digest = "\n".join(lines) + ("\n" if lines else "")
        hash_path = self.dir / "hashes.sha256"
        _atomic_write(hash_path, digest)
        self._finalized = True
        if latest:
            self.point_latest()
        return hash_path

    def point_latest(self) -> Path:
        """Move the mutable latest pointer. Never touches run artifacts."""
        pointer = Path(self.root) / self.benchmark / "latest"
        _atomic_write(pointer, self.run_id + "\n", overwrite=True)
        return pointer

    def verify(self) -> list[str]:
        """Return mismatch descriptions. Empty list means the run is intact."""
        hash_path = self.dir / "hashes.sha256"
        if not hash_path.exists():
            return ["missing hashes.sha256"]
        problems: list[str] = []
        recorded: dict[str, str] = {}
        for line in hash_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, _, rel = line.partition("  ")
            recorded[rel] = digest
            path = self.dir / rel
            if not path.is_file():
                problems.append(f"missing {rel}")
            elif _sha256_file(path) != digest:
                problems.append(f"changed {rel}")
        for path in self.dir.rglob("*"):
            if not path.is_file() or path.name == "hashes.sha256":
                continue
            rel = path.relative_to(self.dir).as_posix()
            if rel not in recorded:
                problems.append(f"unhashed {rel}")
        return problems

    @classmethod
    def open_latest(cls, benchmark: str, root: Optional[Path] = None) -> "ImmutableRun":
        root = root or default_runs_root()
        pointer = root / benchmark / "latest"
        run_id = pointer.read_text(encoding="utf-8").strip()
        run = cls(benchmark=benchmark, root=root, run_id=run_id)
        run._finalized = (run.dir / "hashes.sha256").exists()
        return run
