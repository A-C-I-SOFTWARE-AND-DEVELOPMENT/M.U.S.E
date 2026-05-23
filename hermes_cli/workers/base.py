"""Worker adapter base contract for the Hermes Job Controller.

This module defines the dataclasses and abstract base class that every
worker adapter under ``hermes_cli/workers/`` must satisfy. It is part of
the Phase 7 roadmap (see ``docs/orchestration/worker-adapter-interface.md``)
and is intentionally inert: importing this module has no side effects,
makes no external calls, and touches no filesystem state.

All concrete adapter methods that would actually drive an external tool
raise :class:`NotImplementedError` in this skeleton. They will be filled
in PRs that follow the roadmap.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Mapping

RunStatus = Literal["succeeded", "failed", "cancelled", "skipped"]


@dataclass(frozen=True)
class Job:
    """One user intent submitted via ``/orchestrate <prompt>``.

    The controller owns the canonical copy on disk. Adapters receive a
    read-only snapshot when they are asked to prepare a run.
    """

    job_id: str
    prompt: str
    cwd: Path
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AvailabilityReport:
    """Result of :meth:`WorkerAdapter.available`.

    ``ok=False`` means the model router should skip this adapter without
    recording a failed run. ``reason`` is shown verbatim in
    ``/ai-radar update`` output.
    """

    ok: bool
    reason: str | None = None
    version: str | None = None
    missing: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreparedRun:
    """Concrete handoff produced by :meth:`WorkerAdapter.prepare`.

    Inspectable by ``/orchestrator open <job-id>`` before the controller
    actually executes anything. ``env`` is a *diff* against the user's
    current environment, not a full replacement.
    """

    job_id: str
    worker: str
    argv: tuple[str, ...]
    env: Mapping[str, str]
    cwd: Path
    stdin_payload: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkerRun:
    """Outcome of a single :meth:`WorkerAdapter.run` invocation.

    Failures are returned as data (``status="failed"``) — adapters must
    not raise to signal a normal failure. See
    ``docs/orchestration/worker-adapter-interface.md`` §4.
    """

    run_id: str
    job_id: str
    worker: str
    status: RunStatus
    exit_code: int | None
    started_at: datetime
    ended_at: datetime
    stdout_path: Path
    stderr_path: Path
    error_summary: str | None = None


@dataclass(frozen=True)
class ArtifactBundle:
    """Anything worth surfacing after a successful run.

    Consumed by ``/orchestrator publish <job-id>``. Empty bundles are
    legal — some adapters (notably ``chatgpt_handoff``) finish their
    work by handing the user a prompt rather than producing a diff.
    """

    diff_path: Path | None = None
    patch_path: Path | None = None
    branch: str | None = None
    extra: Mapping[str, str] = field(default_factory=dict)


class WorkerAdapter(ABC):
    """Abstract base class for every worker adapter.

    Subclasses live under ``hermes_cli/workers/`` and are registered in
    ``hermes_cli/workers/__init__.py``. The Job Controller is the only
    code that should instantiate them; user-facing entry points go
    through ``hermes_cli/orchestrator.py``.
    """

    # Adapter identity. Subclasses MUST override these three attributes.
    name: str = ""
    description: str = ""
    capabilities: frozenset[str] = frozenset()

    @abstractmethod
    def available(self) -> AvailabilityReport:
        """Probe whether this adapter can run at all.

        Lightweight: may call ``shutil.which`` or read environment
        variables, but MUST NOT make a network call, log in, or mutate
        state. Used by ``/ai-radar update`` to refresh the cache.
        """

    @abstractmethod
    def prepare(self, job: Job) -> PreparedRun:
        """Translate a :class:`Job` into a concrete handoff.

        Pure function on its inputs. Does not start the worker. The
        result is what ``/orchestrator open <job-id>`` shows the user.
        """

    @abstractmethod
    def run(self, prepared: PreparedRun) -> WorkerRun:
        """Execute a prepared handoff and return the outcome.

        Blocking. Streams stdout/stderr to the per-run log paths the
        controller assigned. Returns ``WorkerRun(status="failed")`` on
        a normal failure; only programmer errors should propagate.
        """

    def cancel(self, run: WorkerRun) -> None:  # noqa: ARG002
        """Best-effort cancel of an in-flight run.

        Default implementation is a no-op. Adapters that wrap an
        interactive CLI should override this to send the CLI's own
        quit signal so it can flush state cleanly.
        """
        return None

    @abstractmethod
    def collect_artifacts(self, run: WorkerRun) -> ArtifactBundle:
        """Gather everything worth surfacing after a successful run.

        Returns an empty :class:`ArtifactBundle` when the adapter has
        nothing tangible to publish (e.g. a chat-only worker).
        """


__all__ = [
    "ArtifactBundle",
    "AvailabilityReport",
    "Job",
    "PreparedRun",
    "RunStatus",
    "WorkerAdapter",
    "WorkerRun",
]
