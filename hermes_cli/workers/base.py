"""Base classes shared by every worker adapter."""

from __future__ import annotations

import abc
import datetime as _dt
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ClassVar


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class WorkerStatus:
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"

    ALL = {PENDING, RUNNING, DONE, FAILED, SKIPPED}


@dataclass
class JobContext:
    """In-memory view of a job folder.

    The on-disk contract is defined in
    :mod:`hermes_cli.orchestrator.job_controller`.
    """

    job_id: str
    job_dir: Path
    prompt: str
    repo_dir: Path
    base_branch: str = "main"
    title: str = ""
    created_at: str = ""

    @property
    def workers_dir(self) -> Path:
        return self.job_dir / "workers"


@dataclass
class WorkerResult:
    worker: str
    success: bool
    exit_code: int
    diff: str = ""
    log: str = ""
    files_changed: int = 0
    message: str = ""
    started_at: str = ""
    finished_at: str = ""

    def to_status_dict(self) -> dict[str, Any]:
        status = WorkerStatus.DONE if self.success else WorkerStatus.FAILED
        return {
            "worker": self.worker,
            "status": status,
            "exit_code": self.exit_code,
            "files_changed": self.files_changed,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    def to_result_dict(self) -> dict[str, Any]:
        return {
            "worker": self.worker,
            "success": self.success,
            "message": self.message,
            "files_changed": self.files_changed,
            "exit_code": self.exit_code,
        }


# Runner signature: (cmd, cwd, env) -> (exit_code, log_text)
RunnerFn = Callable[[list[str], Path, dict[str, str] | None], tuple[int, str]]


def _files_changed_in_diff(diff: str) -> int:
    """Count distinct ``+++ b/<path>`` entries in a unified diff."""
    count = 0
    for line in diff.splitlines():
        if line.startswith("+++ ") and not line.startswith("+++ /dev/null"):
            count += 1
    return count


class WorkerAdapter(abc.ABC):
    """Abstract base for all worker adapters.

    Subclasses must set ``name`` and ``binary`` and implement
    :meth:`build_command`. The default :meth:`run` shells out via an
    injectable runner so tests never touch real subprocesses.
    """

    name: ClassVar[str] = ""
    binary: ClassVar[str] = ""
    description: ClassVar[str] = ""
    # If True, ``detect`` always returns True (used by HermesLocalWorker).
    bundled: ClassVar[bool] = False

    @classmethod
    def detect(cls) -> bool:
        if cls.bundled:
            return True
        if not cls.binary:
            return False
        return shutil.which(cls.binary) is not None

    @abc.abstractmethod
    def build_command(self, job: JobContext) -> list[str]:
        """Return the argv to invoke this worker for the given job."""

    def env(self, job: JobContext) -> dict[str, str]:
        """Optional per-worker env overrides; merged onto ``os.environ``."""
        return {}

    def parse_log(self, log: str) -> dict[str, Any]:
        """Default no-op log parser; subclasses can extract metadata."""
        return {}

    def collect_diff(self, job: JobContext, *, runner: RunnerFn | None = None) -> str:
        """Capture a unified diff of the worker's changes in the repo.

        Default implementation runs ``git diff`` via the runner. Subclasses
        with non-git outputs can override this.
        """
        runner = runner or _real_runner
        rc, out = runner(["git", "diff", "--no-color"], job.repo_dir, None)
        return out if rc == 0 else ""

    def run(
        self,
        job: JobContext,
        *,
        runner: RunnerFn | None = None,
        dry_run: bool = False,
    ) -> WorkerResult:
        """Execute the worker against the job.

        Tests inject ``runner`` to avoid real subprocess calls. ``dry_run``
        records the command but does not execute it.
        """

        started = _utcnow_iso()
        if dry_run:
            cmd = self.build_command(job)
            log = "DRY-RUN: " + " ".join(cmd)
            return WorkerResult(
                worker=self.name,
                success=True,
                exit_code=0,
                diff="",
                log=log,
                files_changed=0,
                message="dry run",
                started_at=started,
                finished_at=_utcnow_iso(),
            )

        cmd = self.build_command(job)
        runner = runner or _real_runner
        env = {**os.environ, **self.env(job)} if self.env(job) else None
        rc, log = runner(cmd, job.repo_dir, env)
        diff = self.collect_diff(job, runner=runner)
        meta = self.parse_log(log) or {}
        return WorkerResult(
            worker=self.name,
            success=rc == 0,
            exit_code=rc,
            diff=diff,
            log=log,
            files_changed=meta.get("files_changed", _files_changed_in_diff(diff)),
            message=meta.get("message", ""),
            started_at=started,
            finished_at=_utcnow_iso(),
        )

    def write_outputs(self, job: JobContext, result: WorkerResult) -> Path:
        """Materialize ``result`` under ``<job>/workers/<name>/``."""
        wdir = job.workers_dir / self.name
        wdir.mkdir(parents=True, exist_ok=True)
        (wdir / "output.diff").write_text(result.diff, encoding="utf-8")
        (wdir / "log.txt").write_text(result.log, encoding="utf-8")
        (wdir / "status.json").write_text(
            json.dumps(result.to_status_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (wdir / "result.json").write_text(
            json.dumps(result.to_result_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return wdir


def _real_runner(
    cmd: list[str], cwd: Path, env: dict[str, str] | None
) -> tuple[int, str]:
    """Default real-subprocess runner. Never used in tests."""
    import subprocess  # local import: keep test imports cheap

    try:
        proc = subprocess.run(  # noqa: S603 — caller controls argv
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError as exc:
        return 127, f"binary not found: {exc}\n"
    except subprocess.TimeoutExpired:
        return 124, "timeout\n"


__all__ = [
    "JobContext",
    "RunnerFn",
    "WorkerAdapter",
    "WorkerResult",
    "WorkerStatus",
]
