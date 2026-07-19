"""Built-in, CLI-free worker: turn a job into a scored, actionable plan.

The first concrete :class:`~hermes_cli.workers.base.WorkerAdapter` in the
execution engine, and the one that makes the engine verifiable end-to-end
without any external tool installed.

It is **non-destructive by construction** — it never edits files and never
runs shell commands. It uses the deterministic HyperAgent navigator to
localize the objective to candidate edit sites + the tests that would verify
a change, and returns that as a worker plan + score. Repo-mutating, external
workers (Codex / Claude Code / Aider) implement the same five-step contract
and plug into the same dispatch path, but behind the orchestrator's
owner-approval gate; this one is safe to run ungated.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from hermes_cli.workers.base import (
    WorkerAdapter,
    WorkerArtifacts,
    WorkerDetection,
    WorkerPrompt,
    WorkerRunResult,
    WorkerScore,
)
from hermes_cli.workers.registry import register


class LocalPlannerWorker(WorkerAdapter):
    """A safe, deterministic, repo-read-only planning worker."""

    id = "hermes-local-planner"
    display_name = "muse local planner"
    # Non-destructive (read-only navigation; no edits, no shell) → runs ungated.
    requires_approval = False

    def __init__(self, repo_root: Optional[str] = None) -> None:
        self._repo_root = repo_root
        self._cache: dict[str, Any] = {}

    # -- helpers --------------------------------------------------------
    def _root(self) -> Path:
        return Path(self._repo_root) if self._repo_root else Path.cwd()

    @staticmethod
    def _objective(job: Any) -> str:
        return str(
            getattr(job, "prompt", "") or getattr(job, "objective", "") or ""
        ).strip()

    def _navigate(self, objective: str):
        if objective in self._cache:
            return self._cache[objective]
        from hermes_cli.jarvis_prime.navigation import Navigator

        result = Navigator.for_repo(self._root()).navigate(objective, limit=5)
        self._cache[objective] = result
        return result

    # -- WorkerAdapter five-step contract -------------------------------
    def detect(self) -> WorkerDetection:
        return WorkerDetection(
            available=True,
            version="builtin",
            reason="built-in planner — no external tool required",
        )

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        return WorkerPrompt(text=self._objective(job), role="planner")

    def run(self, job: Any) -> WorkerRunResult:
        objective = self._objective(job)
        if not objective:
            return WorkerRunResult(ok=False, error="empty objective")
        t0 = time.monotonic()
        try:
            result = self._navigate(objective)
        except Exception as exc:  # navigation is best-effort
            return WorkerRunResult(
                ok=False, error=str(exc), duration_seconds=time.monotonic() - t0
            )
        packet = result.worker_packet()
        files = list(packet.get("candidate_files") or [])
        verify = list(packet.get("verify_with") or [])
        summary = (
            f"Plan for: {objective}\n"
            f"Candidate files ({len(files)}): {', '.join(files) or '—'}\n"
            f"Verify with: {', '.join(verify) or '—'}\n"
            f"(plan only — no edits made, no commands run)"
        )
        return WorkerRunResult(
            ok=bool(files),
            stdout=summary,
            duration_seconds=time.monotonic() - t0,
            details={"packet": packet},
        )

    def collect(self, job: Any) -> WorkerArtifacts:
        objective = self._objective(job)
        files: tuple[str, ...] = ()
        try:
            packet = self._navigate(objective).worker_packet()
            files = tuple(packet.get("candidate_files") or [])
        except Exception:
            files = ()
        return WorkerArtifacts(
            files=files,
            notes="plan only — no edits made, no commands run",
            workspace_path=str(self._root()),
        )

    def score(self, artifacts: WorkerArtifacts) -> WorkerScore:
        n = len(artifacts.files)
        value = 0.8 if n else 0.2
        return WorkerScore(
            value=value,
            confidence=0.5 if n else 0.2,
            rationale=f"{n} candidate file(s) localized",
            components={"localization": value},
        )


# Self-register on import so the engine can dispatch to it. ``replace`` keeps
# re-imports (tests, reloads) idempotent.
register(LocalPlannerWorker(), replace=True)
