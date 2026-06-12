"""Data models for the local Hermes orchestrator job controller.

These are deliberately small dataclasses with explicit JSON
serialization so the on-disk format is human-inspectable and version-
controllable. We intentionally avoid pydantic here because the
controller has no untrusted input boundary — every call is in-process
from another Hermes module — and dataclasses keep the import surface
small.

The on-disk layout under ``.hermes-orchestrator/`` is::

    .hermes-orchestrator/
        jobs/
            <job-id>/
                job.json              # serialized Job (this module)
                decision_ledger.md    # optional, controller-written
                scorecard.md          # optional, controller-written
                workers/
                    <worker-id>/
                        prompt.md
                        artifacts/    # outputs collected back from worker
                github/               # github-ready artifact bundle
                    pr_body.md
                    decision_ledger.md
                    scorecard.md
                    manifest.json
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Iterable


# ──────────────────────────────────────────────────────────────────────
# State machine
# ──────────────────────────────────────────────────────────────────────

class JobState:
    """Canonical job states. Strings (not Enum) so they round-trip JSON cleanly."""

    CREATED = "created"
    PLANNING = "planning"
    WORKERS_ASSIGNED = "workers_assigned"
    WORKERS_RUNNING = "workers_running"
    WORKERS_COMPLETE = "workers_complete"
    SCORED = "scored"
    GITHUB_READY = "github_ready"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

    ALL = frozenset({
        CREATED,
        PLANNING,
        WORKERS_ASSIGNED,
        WORKERS_RUNNING,
        WORKERS_COMPLETE,
        SCORED,
        GITHUB_READY,
        DONE,
        FAILED,
        CANCELLED,
    })


class JobMode:
    """Recognized job modes (mirror Android TaskType, lowercased)."""

    BUILD = "build"
    REVIEW = "review"
    AUDIT = "audit"
    DEBUG = "debug"
    REFACTOR = "refactor"
    RESEARCH = "research"
    PLANNING = "planning"

    ALL = frozenset({BUILD, REVIEW, AUDIT, DEBUG, REFACTOR, RESEARCH, PLANNING})


class WorkerRole:
    """Roles map onto the Android PromptBuilder roles."""

    BUILDER = "builder"
    REVIEWER = "reviewer"
    PLANNER = "planner"
    ARCHITECT = "architect"

    ALL = frozenset({BUILDER, REVIEWER, PLANNER, ARCHITECT})


# Default worker fan-out for each job mode. Used when ``create_job`` is
# called without an explicit ``workers=`` list.
DEFAULT_WORKERS_BY_MODE: dict[str, tuple[str, ...]] = {
    JobMode.BUILD: (WorkerRole.BUILDER,),
    JobMode.REVIEW: (WorkerRole.REVIEWER,),
    JobMode.AUDIT: (WorkerRole.REVIEWER,),
    JobMode.DEBUG: (WorkerRole.BUILDER,),
    JobMode.REFACTOR: (WorkerRole.BUILDER, WorkerRole.REVIEWER),
    JobMode.RESEARCH: (WorkerRole.PLANNER,),
    JobMode.PLANNING: (WorkerRole.PLANNER, WorkerRole.ARCHITECT),
}


# ──────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────

@dataclass
class WorkerSpec:
    """One worker assignment within a job."""

    worker_id: str
    role: str
    target_tool: str = "manual"
    prompt_written: bool = False
    artifact_count: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkerSpec":
        return cls(
            worker_id=str(data.get("worker_id", "")),
            role=str(data.get("role", "")),
            target_tool=str(data.get("target_tool", "manual")),
            prompt_written=bool(data.get("prompt_written", False)),
            artifact_count=int(data.get("artifact_count", 0) or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HistoryEntry:
    """One state-transition record on a job."""

    timestamp: float
    from_state: str | None
    to_state: str
    note: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoryEntry":
        return cls(
            timestamp=float(data.get("timestamp", 0.0) or 0.0),
            from_state=data.get("from_state"),
            to_state=str(data.get("to_state", "")),
            note=data.get("note"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Job:
    """One orchestrator job. Serialized to ``job.json`` per-job."""

    job_id: str
    prompt: str
    mode: str
    repo_root: str
    trusted_local: bool
    state: str = JobState.CREATED
    created_at: float = 0.0
    updated_at: float = 0.0
    workers: list[WorkerSpec] = field(default_factory=list)
    history: list[HistoryEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── serialization ─────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "prompt": self.prompt,
            "mode": self.mode,
            "repo_root": self.repo_root,
            "trusted_local": self.trusted_local,
            "state": self.state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "workers": [w.to_dict() for w in self.workers],
            "history": [h.to_dict() for h in self.history],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        workers_raw: Iterable[Any] = data.get("workers") or []
        history_raw: Iterable[Any] = data.get("history") or []
        return cls(
            job_id=str(data.get("job_id", "")),
            prompt=str(data.get("prompt", "")),
            mode=str(data.get("mode", "")),
            repo_root=str(data.get("repo_root", "")),
            trusted_local=bool(data.get("trusted_local", False)),
            state=str(data.get("state", JobState.CREATED)),
            created_at=float(data.get("created_at", 0.0) or 0.0),
            updated_at=float(data.get("updated_at", 0.0) or 0.0),
            workers=[
                WorkerSpec.from_dict(w) for w in workers_raw if isinstance(w, dict)
            ],
            history=[
                HistoryEntry.from_dict(h) for h in history_raw if isinstance(h, dict)
            ],
            metadata=dict(data.get("metadata") or {}),
        )

    # ── lookups ───────────────────────────────────────────────────────

    def worker(self, worker_id: str) -> WorkerSpec | None:
        for w in self.workers:
            if w.worker_id == worker_id:
                return w
        return None
