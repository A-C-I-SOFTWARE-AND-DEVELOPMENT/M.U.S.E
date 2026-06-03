"""Eval harness (EVAL-1) — deterministic, fast, model-optional.

Produces `eval_passed` / `eval_results` for `WorkerEntry` (ROUTE-2). See
`docs/audits/one-sprint-build-plan.md` and `docs/self-improvement/eval-gates.md`.
"""

from __future__ import annotations

from .harness import BUILTIN_CASES, EvalCase, EvalReport, run_suite

__all__ = ["EvalCase", "EvalReport", "run_suite", "BUILTIN_CASES"]
