"""Background-learner scaffold — safe-by-default idle job queue.

Ships the gating + queueing layer only; the runner is **dry-run** and produces
no external effects. Live jobs + scheduler are a follow-up (ticket LEARN-1 in
``docs/audits/one-sprint-build-plan.md``). See
``docs/audits/autonomy-security-threat-model.md`` for the safety rationale.
"""

from __future__ import annotations

from .queue import (
    ALLOWED_KINDS,
    DISALLOWED_KINDS,
    Job,
    JobQueue,
    JobRejected,
)
from .runner import (
    BackgroundLearnerRunner,
    JobOutcome,
    make_live_queue,
    run_idle_cycle,
)

__all__ = [
    "Job",
    "JobQueue",
    "JobRejected",
    "ALLOWED_KINDS",
    "DISALLOWED_KINDS",
    "BackgroundLearnerRunner",
    "JobOutcome",
    "make_live_queue",
    "run_idle_cycle",
]
