"""Job-folder contract and lifecycle controller.

A "job" is a unit of work the orchestrator runs across multiple workers.
Each job is a folder under ``<jobs_root>/<job_id>/`` with this contract:

```
<jobs_root>/<job_id>/
  job.json           # core metadata + status
  prompt.md          # the handoff prompt sent to every worker
  workers/<name>/
    output.diff      # unified diff produced by the worker
    log.txt          # captured stdout+stderr
    status.json      # {worker, status, exit_code, started_at, finished_at, ...}
    result.json      # {worker, success, message, files_changed, exit_code}
  selected.json      # {worker, score} — written after scoring
  validation.json    # {gates: {name: {passed, message}}, overall} — after gates
  publish.json       # {dry_run, branch, base, pr_url, pr_number, commands}
```

Only fields documented above are part of the public contract. Worker
adapters and orchestrator phases may write additional sidecar files, but
tests assert *at least* the documented fields exist.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hermes_cli.workers.base import JobContext, WorkerResult, WorkerStatus

JOB_FOLDER_VERSION = 1
_JOB_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class JobNotFoundError(LookupError):
    pass


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(text: str, *, max_len: int = 32) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_len] or "job"


def _new_job_id(title: str) -> str:
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = secrets.token_hex(2)
    slug = _slugify(title)
    return f"{stamp}-{slug}-{suffix}"


@dataclass
class JobController:
    """Owns the on-disk job folder contract."""

    jobs_root: Path

    def __post_init__(self) -> None:
        self.jobs_root = Path(self.jobs_root)
        self.jobs_root.mkdir(parents=True, exist_ok=True)

    # ── creation ──────────────────────────────────────────────────────

    def create(
        self,
        prompt: str,
        *,
        title: str = "",
        repo_dir: Path | str | None = None,
        base_branch: str = "main",
        job_id: str | None = None,
    ) -> JobContext:
        if not prompt or not prompt.strip():
            raise ValueError("prompt must not be empty")
        title = title or prompt.strip().splitlines()[0][:80]
        job_id = job_id or _new_job_id(title)
        if not _JOB_ID_RE.match(job_id):
            raise ValueError(f"invalid job_id: {job_id!r}")
        job_dir = self.jobs_root / job_id
        if job_dir.exists():
            raise FileExistsError(f"job already exists: {job_id}")
        job_dir.mkdir(parents=True)
        (job_dir / "workers").mkdir()
        created_at = _utcnow_iso()
        repo_path = Path(repo_dir) if repo_dir else job_dir / "repo"
        meta = {
            "version": JOB_FOLDER_VERSION,
            "id": job_id,
            "title": title,
            "status": WorkerStatus.PENDING,
            "created_at": created_at,
            "base_branch": base_branch,
            "repo_dir": str(repo_path),
        }
        (job_dir / "job.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8"
        )
        (job_dir / "prompt.md").write_text(prompt, encoding="utf-8")
        return JobContext(
            job_id=job_id,
            job_dir=job_dir,
            prompt=prompt,
            repo_dir=repo_path,
            base_branch=base_branch,
            title=title,
            created_at=created_at,
        )

    # ── lookup ────────────────────────────────────────────────────────

    def load(self, job_id: str) -> JobContext:
        job_dir = self.jobs_root / job_id
        if not job_dir.is_dir():
            raise JobNotFoundError(job_id)
        meta_path = job_dir / "job.json"
        if not meta_path.exists():
            raise JobNotFoundError(f"missing job.json in {job_id}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        prompt = (job_dir / "prompt.md").read_text(encoding="utf-8")
        return JobContext(
            job_id=meta["id"],
            job_dir=job_dir,
            prompt=prompt,
            repo_dir=Path(meta.get("repo_dir") or (job_dir / "repo")),
            base_branch=meta.get("base_branch", "main"),
            title=meta.get("title", ""),
            created_at=meta.get("created_at", ""),
        )

    def list(self) -> list[str]:
        """Return job IDs sorted oldest→newest."""
        if not self.jobs_root.is_dir():
            return []
        return sorted(
            d.name for d in self.jobs_root.iterdir()
            if d.is_dir() and (d / "job.json").exists()
        )

    # ── mutators ──────────────────────────────────────────────────────

    def _read_meta(self, ctx: JobContext) -> dict[str, Any]:
        return json.loads((ctx.job_dir / "job.json").read_text(encoding="utf-8"))

    def _write_meta(self, ctx: JobContext, meta: dict[str, Any]) -> None:
        (ctx.job_dir / "job.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8"
        )

    def set_status(self, ctx: JobContext, status: str) -> None:
        if status not in WorkerStatus.ALL:
            raise ValueError(f"invalid status: {status!r}")
        meta = self._read_meta(ctx)
        meta["status"] = status
        meta["updated_at"] = _utcnow_iso()
        self._write_meta(ctx, meta)

    def write_worker_result(self, ctx: JobContext, worker_adapter, result: WorkerResult) -> Path:
        """Persist a worker result under ``<job>/workers/<name>/``."""
        return worker_adapter.write_outputs(ctx, result)

    def mark_selected(self, ctx: JobContext, worker_name: str, score: float) -> Path:
        payload = {
            "worker": worker_name,
            "score": round(float(score), 6),
            "selected_at": _utcnow_iso(),
        }
        path = ctx.job_dir / "selected.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def write_validation(self, ctx: JobContext, payload: dict[str, Any]) -> Path:
        path = ctx.job_dir / "validation.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def write_publish(self, ctx: JobContext, payload: dict[str, Any]) -> Path:
        path = ctx.job_dir / "publish.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    # ── inspection ────────────────────────────────────────────────────

    def status(self, job_id: str) -> dict[str, Any]:
        ctx = self.load(job_id)
        meta = self._read_meta(ctx)
        meta["workers"] = self._collect_worker_statuses(ctx)
        meta["has_selected"] = (ctx.job_dir / "selected.json").exists()
        meta["has_validation"] = (ctx.job_dir / "validation.json").exists()
        meta["has_publish"] = (ctx.job_dir / "publish.json").exists()
        return meta

    @staticmethod
    def _collect_worker_statuses(ctx: JobContext) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        wdir = ctx.workers_dir
        if not wdir.is_dir():
            return out
        for child in sorted(wdir.iterdir()):
            status_file = child / "status.json"
            if status_file.exists():
                out[child.name] = json.loads(status_file.read_text(encoding="utf-8"))
        return out


__all__ = ["JOB_FOLDER_VERSION", "JobController", "JobNotFoundError"]
