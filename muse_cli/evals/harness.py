"""Lightweight, deterministic eval harness (EVAL-1).

Feeds ROUTE-2: produces `eval_passed` + `eval_results` consumable by
`muse_cli/model_registry.py::WorkerEntry`. Designed to run **without network
or model downloads** — model-independent cases (e.g. compaction quality) run
always; model-dependent cases run only when a `runner` callable is supplied.

Heavy, real-model evaluation can later delegate to
`mini_swe_runner.MiniSWERunner` (documented hook in `run_suite`); this module
stays self-contained and fast so it can gate routing and self-update proposals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# A runner executes a prompt against a worker and returns a response object.
# Shape is intentionally loose: model-dependent cases interpret it. When None,
# only model-independent cases run.
Runner = Callable[[str], Any]


@dataclass(frozen=True)
class EvalCase:
    name: str
    fn: Callable[[Optional[Runner]], float]  # returns score in [0.0, 1.0]
    requires_runner: bool = False
    weight: float = 1.0


@dataclass
class EvalReport:
    worker_id: str
    scores: dict[str, float] = field(default_factory=dict)
    threshold: float = 0.7
    skipped: list[str] = field(default_factory=list)

    @property
    def aggregate(self) -> float:
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)

    @property
    def passed(self) -> bool:
        # A worker passes only if at least one case ran AND the weighted mean
        # meets the threshold. No scores (everything skipped) → not passed.
        return bool(self.scores) and self.aggregate >= self.threshold

    def to_registry_fields(self) -> dict[str, Any]:
        """Return fields consumable by WorkerEntry (ROUTE-2)."""
        return {
            "eval_passed": self.passed,
            "eval_results": tuple(sorted(self.scores.items())),
        }


# ── Built-in, model-independent cases ───────────────────────────────────────

def _case_compaction_quality(_runner: Optional[Runner]) -> float:
    """Score TokenJuice's reduction on a known-verbose payload (no model)."""
    from tools.tokenjuice import compact_tool_output

    payload = (
        "On branch main\nYour branch is up to date.\n\n"
        + "\n".join(f"\tmodified:   src/file_{i}.py" for i in range(150))
        + "\n"
    )
    out, stats = compact_tool_output("exec", {"command": "git status"}, payload, 0)
    if not stats.applied or stats.original_chars == 0:
        return 0.0
    # Reward reduction; 1.0 at >=80% reduction, linear below.
    reduction = 1.0 - (stats.compacted_chars / stats.original_chars)
    return max(0.0, min(1.0, reduction / 0.8))


def _case_scrub_no_leak(_runner: Optional[Runner]) -> float:
    """Score credential scrubbing: 1.0 iff the secret does not survive."""
    from tools.tokenjuice import scrub_credentials

    out = scrub_credentials("api_key=supersecretvalue12345")
    return 1.0 if "supersecretvalue12345" not in out and "[REDACTED]" in out else 0.0


def _case_tool_call_correctness(runner: Optional[Runner]) -> float:
    """Model-dependent: the runner must return a well-formed tool call."""
    if runner is None:
        return 0.0
    resp = runner("call the echo tool with text=hi")
    if isinstance(resp, dict) and resp.get("name") and isinstance(resp.get("arguments"), dict):
        return 1.0
    return 0.0


BUILTIN_CASES: tuple[EvalCase, ...] = (
    EvalCase("compaction_quality", _case_compaction_quality),
    EvalCase("scrub_no_leak", _case_scrub_no_leak),
    EvalCase("tool_call_correctness", _case_tool_call_correctness, requires_runner=True),
)


def run_suite(
    worker_id: str,
    *,
    runner: Optional[Runner] = None,
    cases: Optional[tuple[EvalCase, ...]] = None,
    threshold: float = 0.7,
) -> EvalReport:
    """Run the eval suite for ``worker_id``.

    Model-independent cases always run. Cases with ``requires_runner=True`` run
    only when ``runner`` is provided, else they are recorded as skipped. To run
    heavy real-model SWE evals, pass a ``runner`` that delegates to
    ``mini_swe_runner.MiniSWERunner`` (kept out of this module to stay fast).
    """
    report = EvalReport(worker_id=worker_id, threshold=threshold)
    for case in (cases or BUILTIN_CASES):
        if case.requires_runner and runner is None:
            report.skipped.append(case.name)
            continue
        try:
            score = float(case.fn(runner))
        except Exception:
            score = 0.0
        report.scores[case.name] = max(0.0, min(1.0, score))
    return report
