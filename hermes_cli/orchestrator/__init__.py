"""Hermes orchestration system.

Phases of a job:

1. **Create** — ``JobController.create`` writes a job folder with the
   contract documented in :mod:`hermes_cli.orchestrator.job_controller`.
2. **Run workers** — each worker adapter (see :mod:`hermes_cli.workers`)
   produces a diff + log + status under ``<job>/workers/<name>/``.
3. **Score** — :mod:`hermes_cli.orchestrator.scoring` picks the best
   worker by a simple, deterministic rubric.
4. **Merge** — optional: :mod:`hermes_cli.orchestrator.merge_engine`
   combines compatible diffs into one.
5. **Validate** — :mod:`hermes_cli.orchestrator.validation_gates` runs
   safety / correctness gates over the materialized output. Any failing
   gate blocks publish.
6. **Publish** — :mod:`hermes_cli.orchestrator.github_publisher` opens
   a PR (or prints the would-be commands in ``--dry-run`` mode).
"""

from hermes_cli.orchestrator.job_controller import (
    JOB_FOLDER_VERSION,
    JobController,
    JobNotFoundError,
)
from hermes_cli.orchestrator.scoring import ScoreBreakdown, score_worker, select_best
from hermes_cli.orchestrator.merge_engine import (
    MergeResult,
    apply_diff,
    has_conflicts,
    merge_diffs,
    parse_diff,
)
from hermes_cli.orchestrator.validation_gates import (
    GateResult,
    NoSecretsGate,
    PatchAppliesGate,
    PyCompileGate,
    PytestGate,
    ShellSyntaxGate,
    ValidationGate,
    run_gates,
)
from hermes_cli.orchestrator.github_publisher import PublishResult, publish

__all__ = [
    "GateResult",
    "JOB_FOLDER_VERSION",
    "JobController",
    "JobNotFoundError",
    "MergeResult",
    "NoSecretsGate",
    "PatchAppliesGate",
    "PublishResult",
    "PyCompileGate",
    "PytestGate",
    "ScoreBreakdown",
    "ShellSyntaxGate",
    "ValidationGate",
    "apply_diff",
    "has_conflicts",
    "merge_diffs",
    "parse_diff",
    "publish",
    "run_gates",
    "score_worker",
    "select_best",
]
