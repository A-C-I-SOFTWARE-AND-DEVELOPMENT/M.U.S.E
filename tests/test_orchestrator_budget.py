"""Budget hard-stop on the single-job ``orchestrator.dispatch_job`` path (FU-11).

The parallel runner already meters worker cost and stops on a hard budget; this
suite covers the matching guard on the *single-job* dispatch path plus the
tightened readiness-doctor check that previously false-PASSed off the parallel
file alone.

Three behaviours are pinned:

* a single-job run that exceeds a configured hard budget is blocked, with a
  ``budget_stop`` ledger entry whose reason is ``budget_exhausted``;
* the default (no budget configured) path is unchanged — a normal job completes
  exactly as before, with no budget ledger entry;
* :func:`release_readiness_doctor._check_budget_enforced` PASSes only when the
  *single-job* path actually consults the budget (not merely the parallel file).

Worker registration / dispatch / ledger access mirror
``tests/test_worker_dispatch.py``. Tests run against an isolated ``HERMES_HOME``
(see ``tests/conftest.py``) so job JSON never leaks between tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from hermes_cli import orchestrator as orch
from hermes_cli import release_readiness_doctor as rrd
from hermes_cli.workers import registry as wr
from hermes_cli.workers.base import (
    WorkerAdapter,
    WorkerArtifacts,
    WorkerDetection,
    WorkerPrompt,
    WorkerRunResult,
    WorkerScore,
)


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    yield tmp_path


class _CostingWorker(WorkerAdapter):
    """A non-destructive worker that reports a fixed ``cost_usd`` (so it runs
    ungated and moves the budget meter). The cost rides in
    ``WorkerRunResult.details`` exactly like a real worker's usage block."""

    id = "test-costing-worker"
    display_name = "Test costing worker"
    requires_approval = False  # non-destructive → ungated, no owner approval

    def __init__(self, cost_usd: float) -> None:
        self._cost = cost_usd

    def detect(self) -> WorkerDetection:
        return WorkerDetection(available=True)

    def prepare_prompt(self, job) -> WorkerPrompt:
        return WorkerPrompt(text="x")

    def run(self, job) -> WorkerRunResult:
        return WorkerRunResult(
            ok=True,
            stdout="did work",
            details={"cost_usd": self._cost},
        )

    def collect(self, job) -> WorkerArtifacts:
        return WorkerArtifacts()

    def score(self, artifacts) -> WorkerScore:
        return WorkerScore(value=1.0)


def _kinds(job_id: str) -> list[object]:
    return [e.get("kind") for e in orch.get_ledger(job_id)[job_id]]


# ── (a) over-budget single-job run is blocked with budget_exhausted ─────────


def test_single_job_blocks_when_hard_budget_exceeded(isolated_home: Path) -> None:
    wr.register(_CostingWorker(cost_usd=1.5), replace=True)
    job = orch.submit_job("spendy work")

    out = orch.dispatch_job(
        job.id, worker_id="test-costing-worker", budget_hard_limit=1.0
    )

    # The worker ran (its result + score are recorded), but the accrued cost
    # ($1.50) reached the hard cap ($1.00) so the job is blocked, not completed.
    assert out is not None
    assert out.status == "blocked"
    kinds = _kinds(job.id)
    assert {"worker_result", "worker_score", "budget_stop"} <= set(kinds)

    stop = next(
        e for e in orch.get_ledger(job.id)[job.id] if e.get("kind") == "budget_stop"
    )
    assert stop["reason"] == "budget_exhausted"
    assert stop["hard_limit"] == 1.0
    assert stop["spent"] == 1.5


def test_pre_dispatch_guard_blocks_next_worker_without_running_it(
    isolated_home: Path,
) -> None:
    # First dispatch exhausts the budget; a *second* dispatch must refuse to run
    # the next worker at all (mirrors the parallel "stop launching the rest").
    wr.register(_CostingWorker(cost_usd=2.0), replace=True)
    job = orch.submit_job("two-step spendy work")

    orch.dispatch_job(job.id, worker_id="test-costing-worker", budget_hard_limit=1.0)
    first = orch.get_job(job.id)
    assert first is not None and first.status == "blocked"

    class _MustNotRun(WorkerAdapter):
        id = "test-must-not-run"
        display_name = "Must not run"
        requires_approval = False

        def detect(self):  # pragma: no cover - reached only on a guard regression
            raise AssertionError("budget-exhausted job must not dispatch a new worker")

        def prepare_prompt(self, job):  # pragma: no cover
            return WorkerPrompt(text="x")

        def run(self, job):  # pragma: no cover
            return WorkerRunResult(ok=True)

        def collect(self, job):  # pragma: no cover
            return WorkerArtifacts()

        def score(self, artifacts):  # pragma: no cover
            return WorkerScore(value=1.0)

    wr.register(_MustNotRun(), replace=True)
    out = orch.dispatch_job(
        job.id, worker_id="test-must-not-run", budget_hard_limit=1.0
    )
    # The second worker was refused before launch: its ``detect()`` (which would
    # raise) was never reached, the job stays blocked, and the only
    # ``worker_dispatch`` recorded is the FIRST worker's — not a second one.
    assert out is not None and out.status == "blocked"
    assert _kinds(job.id).count("worker_dispatch") == 1


def test_under_budget_single_job_completes(isolated_home: Path) -> None:
    # Spend below the hard limit → the job completes normally; no budget stop.
    wr.register(_CostingWorker(cost_usd=0.25), replace=True)
    job = orch.submit_job("cheap work")

    out = orch.dispatch_job(
        job.id, worker_id="test-costing-worker", budget_hard_limit=1.0
    )

    assert out is not None and out.status == "completed"
    assert "budget_stop" not in _kinds(job.id)


# ── (b) default (no budget) path is unchanged ───────────────────────────────


def test_default_no_budget_path_completes_unchanged(isolated_home: Path) -> None:
    # With no budget configured the dispatch path is byte-identical to before:
    # the very same costing worker completes, and NO budget ledger entry appears.
    wr.register(_CostingWorker(cost_usd=999.0), replace=True)
    job = orch.submit_job("normal work")

    out = orch.dispatch_job(job.id, worker_id="test-costing-worker")

    assert out is not None and out.status == "completed"
    kinds = _kinds(job.id)
    assert {"worker_dispatch", "worker_result", "worker_score"} <= set(kinds)
    assert "budget_stop" not in kinds


def test_builtin_local_planner_default_path_still_completes(
    isolated_home: Path, tmp_path: Path
) -> None:
    # The built-in non-destructive planner on the default (no budget) path keeps
    # completing end-to-end — the regression guard for "default path unchanged".
    repo = tmp_path / "repo"
    (repo / "svc").mkdir(parents=True)
    (repo / "svc" / "uploader.py").write_text(
        "def upload_file(p):\n    return open(p).read()\n"
    )
    job = orch.submit_job("upload_file fails on large files")
    out = orch.dispatch_job(job.id, repo_root=str(repo))
    assert out is not None and out.status == "completed"
    assert "budget_stop" not in _kinds(job.id)


# ── budget subsystem never crashes the job (defensive) ──────────────────────


def test_budget_subsystem_error_does_not_crash_dispatch(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # If the budget *policy kernel* blows up, dispatch must not raise. The stop
    # is swallowed (no hard-stop can be proven), so the job keeps its honest
    # terminal status — here ``completed`` — rather than crashing the caller.
    import hermes_cli.budget_policy as bp

    def _boom(*_args, **_kwargs):
        raise RuntimeError("budget kernel exploded")

    monkeypatch.setattr(bp, "evaluate_budget", _boom)
    wr.register(_CostingWorker(cost_usd=5.0), replace=True)
    job = orch.submit_job("robust work")

    out = orch.dispatch_job(
        job.id, worker_id="test-costing-worker", budget_hard_limit=1.0
    )
    # Never raised; honest terminal status preserved; no spurious budget stop.
    assert out is not None and out.status == "completed"
    assert "budget_stop" not in _kinds(job.id)


def test_budget_helpers_never_raise_on_bad_input() -> None:
    # The policy-facing helper swallows subsystem errors and returns None, and
    # the cost extractor returns 0.0 for malformed inputs — both never raise.
    assert (
        orch._budget_stop_for_spend(-1.0, soft_limit=None, hard_limit=0.0) is None
    )  # negative spend would raise inside evaluate_budget; helper swallows it

    class _NoDetails:
        details = "not-a-dict"

    assert orch._worker_reported_cost(_NoDetails()) == 0.0
    assert orch._worker_reported_cost(object()) == 0.0

    class _BoolCost:
        details = {"cost_usd": True}  # bool must not count as a number

    assert orch._worker_reported_cost(_BoolCost()) == 0.0

    class _NestedUsage:
        details = {"usage": {"cost_usd": 0.5}}

    assert orch._worker_reported_cost(_NestedUsage()) == 0.5


# ── (c) doctor PASSes only when the single-job path enforces ────────────────


_PARALLEL_ENFORCING = "evaluate_budget(...)\nif decision.should_stop: ...\n"
_SINGLE_ENFORCING = "evaluate_budget(...)\nreason = 'budget_exhausted'\n"
_SINGLE_INERT = "def dispatch_job(...):\n    return job  # no budget consulted\n"


def _doctor_with_files(
    monkeypatch: pytest.MonkeyPatch, files: dict[str, str]
) -> rrd.ReadinessCheck:
    def _fake_read(rel: str):
        return files.get(rel)

    monkeypatch.setattr(rrd, "_read", _fake_read)
    return rrd._check_budget_enforced()


def test_doctor_warns_when_only_parallel_enforces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The exact false-PASS this task fixes: the parallel file enforces but the
    # single-job file does not → must WARN, not PASS.
    check = _doctor_with_files(
        monkeypatch,
        {
            "hermes_cli/orchestrator.py": _SINGLE_INERT,
            "hermes_cli/orchestrator_parallel.py": _PARALLEL_ENFORCING,
        },
    )
    assert check.status == rrd.WARN
    assert "single-job" in check.detail


def test_doctor_passes_only_when_single_job_path_enforces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check = _doctor_with_files(
        monkeypatch,
        {
            "hermes_cli/orchestrator.py": _SINGLE_ENFORCING,
            "hermes_cli/orchestrator_parallel.py": _PARALLEL_ENFORCING,
        },
    )
    assert check.status == rrd.PASS
    assert "single-job" in check.detail


def test_doctor_warns_when_neither_path_enforces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check = _doctor_with_files(
        monkeypatch,
        {
            "hermes_cli/orchestrator.py": _SINGLE_INERT,
            "hermes_cli/orchestrator_parallel.py": "no budget here\n",
        },
    )
    assert check.status == rrd.WARN


def test_live_repo_doctor_now_passes_budget_check() -> None:
    # On the real tree (with this PR applied) the single-job path enforces, so
    # the live check PASSes — the honest end-state for FU-11.
    by_name = {c.name: c for c in rrd.run_10_10_doctor().checks}
    assert by_name["per-job budget hard-stop"].status == rrd.PASS
