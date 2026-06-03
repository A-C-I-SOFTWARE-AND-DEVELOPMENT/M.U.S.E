"""Background-learner job queue (safe-by-default scaffold).

This sprint ships the **gating + queueing** layer only. No job produces an
external side effect: the runner executes **dry-run** logging exclusively. The
defining safety properties:

* **Allowlist at enqueue** — only known-safe, local, read-mostly job kinds are
  accepted. Disallowed kinds (send message/email, spend, install, mutate prod,
  auto-merge, destructive shell, …) are **rejected when enqueued**, not merely
  skipped at run time.
* **Dry-run by default** — ``Job.dry_run`` defaults to True; a live run requires
  an explicit approval token which is not issuable yet, so high-risk jobs are
  always deferred.
* **Idle-gated** — the runner only drains while the system reports idle.

Live job implementations + scheduler are a follow-up (ticket LEARN-1).
"""

from __future__ import annotations

import itertools
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Safe, local, read-mostly work the learner may queue.
ALLOWED_KINDS: frozenset[str] = frozenset(
    {
        "index_local_files",
        "summarize_session",
        "extract_candidate_memory",
        "update_embeddings",
        "refresh_integration_metadata",
        "run_local_benchmark",
        "evaluate_model_routing",
        "scan_outdated_deps",
        "propose_skill",
        "propose_code_patch",
        "build_research_digest",
    }
)

# External-effect / dangerous work that must never be enqueued without an
# explicit, human-issued approval (not issuable this sprint).
DISALLOWED_KINDS: frozenset[str] = frozenset(
    {
        "send_message",
        "send_email",
        "send_sms",
        "change_production_code",
        "install_package",
        "spend_money",
        "access_new_account",
        "exfiltrate_data",
        "create_external_schedule",
        "modify_secret",
        "auto_merge_self_update",
        "destructive_shell",
    }
)


class JobRejected(Exception):
    """Raised when a job is not allowed to be enqueued."""


@dataclass(order=False)
class Job:
    kind: str
    priority: int = 100  # lower = higher priority
    permission_scope: str = "read_local"
    dry_run: bool = True
    payload: dict = field(default_factory=dict)
    id: int = 0
    cancelled: bool = False


class JobQueue:
    """In-memory priority queue with enqueue-time gating. Not persisted."""

    def __init__(
        self,
        idle_check: Optional[Callable[[], bool]] = None,
        executor: Optional[Callable[["Job"], object]] = None,
    ):
        self._jobs: list[Job] = []
        self._ids = itertools.count(1)
        self._idle_check = idle_check or (lambda: True)
        # Optional real executor (e.g. BackgroundLearnerRunner.handle). When
        # absent, run_once falls back to dry-run logging (no side effects).
        self._executor = executor
        self._audit: list[dict] = []

    # ── enqueue / cancel ────────────────────────────────────────────────
    def enqueue(self, kind: str, *, priority: int = 100, permission_scope: str = "read_local",
                dry_run: bool = True, payload: Optional[dict] = None,
                approval_token: Optional[str] = None) -> Job:
        if kind in DISALLOWED_KINDS:
            self._audit.append({"event": "rejected", "kind": kind, "reason": "disallowed", "ts": time.time()})
            raise JobRejected(f"job kind '{kind}' is disallowed without explicit approval")
        if kind not in ALLOWED_KINDS:
            self._audit.append({"event": "rejected", "kind": kind, "reason": "unknown", "ts": time.time()})
            raise JobRejected(f"job kind '{kind}' is not in the allowlist")
        # A live (non-dry-run) job requires an approval token. None is issuable
        # this sprint, so any live request is forced back to dry-run + audited.
        if not dry_run and not _valid_approval(approval_token):
            self._audit.append({"event": "downgraded", "kind": kind, "reason": "no-approval", "ts": time.time()})
            dry_run = True

        job = Job(kind=kind, priority=priority, permission_scope=permission_scope,
                  dry_run=dry_run, payload=payload or {}, id=next(self._ids))
        self._jobs.append(job)
        self._jobs.sort(key=lambda j: (j.priority, j.id))
        self._audit.append({"event": "enqueued", "kind": kind, "id": job.id, "dry_run": job.dry_run, "ts": time.time()})
        return job

    def cancel(self, job_id: int) -> bool:
        for j in self._jobs:
            if j.id == job_id and not j.cancelled:
                j.cancelled = True
                self._audit.append({"event": "cancelled", "id": job_id, "ts": time.time()})
                return True
        return False

    def pending(self) -> list[Job]:
        return [j for j in self._jobs if not j.cancelled]

    def audit_log(self) -> list[dict]:
        return list(self._audit)

    # ── draining ────────────────────────────────────────────────────────
    def run_once(self) -> Optional[Job]:
        """Pop and execute the highest-priority job.

        Idle-gated: returns None when not idle or empty. If an ``executor`` was
        provided it runs the real handler (read-mostly / proposal-only — see
        ``runner.py``); otherwise it falls back to dry-run logging with no side
        effects. Returns the processed job.
        """
        if not self._idle_check():
            return None
        for idx, job in enumerate(self._jobs):
            if job.cancelled:
                continue
            self._jobs.pop(idx)
            if self._executor is not None:
                try:
                    self._executor(job)
                    self._audit.append({"event": "ran", "id": job.id, "kind": job.kind, "ts": time.time()})
                except Exception as err:  # an executor error must not wedge the queue
                    logger.warning("[background-learner] executor failed job=%s: %s", job.id, err)
                    self._audit.append({"event": "error", "id": job.id, "kind": job.kind, "ts": time.time()})
            else:
                self._execute_dry_run(job)
            return job
        return None

    def drain(self, max_jobs: int = 100) -> int:
        """Run queued jobs (idle-gated) until empty or ``max_jobs`` processed."""
        count = 0
        while count < max_jobs:
            job = self.run_once()
            if job is None:
                break
            count += 1
        return count

    def _execute_dry_run(self, job: Job) -> None:
        logger.info(
            "[background-learner] DRY-RUN job id=%s kind=%s scope=%s (no side effects)",
            job.id, job.kind, job.permission_scope,
        )
        self._audit.append({"event": "ran_dry", "id": job.id, "kind": job.kind, "ts": time.time()})


def _valid_approval(token: Optional[str]) -> bool:
    # No approval tokens are issuable this sprint — live jobs are always deferred.
    return False
