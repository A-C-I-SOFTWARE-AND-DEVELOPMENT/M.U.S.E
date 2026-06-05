"""Unified release gate for Hermes — one verdict over every ship signal.

Backs ``hermes doctor --release-gate``. It aggregates the existing 10/10
release-readiness checks (:func:`hermes_cli.release_readiness_doctor.run_10_10_doctor`)
with the two *runtime* gates the smoke script (``scripts/hermes-10-10-smoke.sh``)
also runs — ``ruff check .`` and a fast, launch-critical pytest slice — into a
single :class:`~hermes_cli.release_readiness_doctor.ReadinessReport`.

Design notes:

* It **reuses** the doctor's dataclasses (``ReadinessReport`` / ``ReadinessCheck``)
  rather than defining a parallel report type, so every consumer (CLI text/JSON
  render, ``.ok`` aggregation) keeps working unchanged.
* ruff / pytest are run as subprocesses, mirroring the smoke script — this keeps
  CI parity (same commands, same flags) and avoids importing pytest into the
  doctor's import-free probe model.
* A subprocess failure (missing tool, timeout, crash) surfaces as a ``FAIL``
  check, never an exception: like the doctor, this function never raises.

The ruff gate is **hard** (lint is the repo's enforced gate, so a dirty tree
must block ship). The test slice is **hard** too — a red fast slice is not
safe to ship. Soft 10/10 punch-list warnings from the doctor stay soft and
never block.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from hermes_cli.release_readiness_doctor import (
    FAIL,
    PASS,
    ReadinessCheck,
    ReadinessReport,
    run_10_10_doctor,
)

# Fast, launch-critical pytest slice — kept in lockstep with
# scripts/hermes-10-10-smoke.sh (readiness + action executors + a couple of
# plugin suites + orchestration commands).
_FAST_TEST_SLICE: tuple[str, ...] = (
    "tests/test_release_readiness_doctor.py",
    "tests/test_action_executors.py",
    "tests/plugins/test_vercel_plugin.py",
    "tests/plugins/test_supabase_plugin.py",
    "tests/plugins/memory/test_supabase_memory.py",
    "tests/test_orchestrator_commands.py",
)

# Generous ceilings so a slow-but-healthy run is not misreported as a failure.
_RUFF_TIMEOUT_S = 300
_PYTEST_TIMEOUT_S = 900


def _repo_root() -> Path:
    # hermes_cli/release_gate.py -> repo root is one level up.
    return Path(__file__).resolve().parents[1]


def _ruff_argv() -> list[str]:
    """Prefer ``uv run ruff`` (matches CI); fall back to a bare ``ruff``."""
    if shutil.which("uv"):
        return ["uv", "run", "ruff", "check", "."]
    return ["ruff", "check", "."]


def _pytest_argv() -> list[str]:
    """Run the fast slice the same way the smoke script does.

    ``-o addopts=""`` drops the xdist/timeout plugins the slice does not need;
    ``-q`` keeps output compact. Prefer ``uv run`` for environment parity.
    """
    base = ["python", "-m", "pytest", "-q", "-o", "addopts="]
    args = [*base, *_FAST_TEST_SLICE]
    if shutil.which("uv"):
        return ["uv", "run", *args]
    return args


def _run_subprocess(argv: list[str], *, timeout: int) -> tuple[int, str]:
    """Run ``argv`` from the repo root; return ``(returncode, tail)``.

    Never raises: a missing executable, timeout, or any OS error is turned into
    a non-zero return code plus a short diagnostic string.
    """
    try:
        proc = subprocess.run(
            argv,
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return 127, f"executable not found: {argv[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except OSError as exc:  # pragma: no cover - defensive
        return 1, f"failed to run {argv[0]}: {exc}"
    output = (proc.stdout or "") + (proc.stderr or "")
    # Keep only the tail so a FAIL detail stays readable in CLI/JSON output.
    tail = output.strip().splitlines()[-1:] if output.strip() else []
    return proc.returncode, (tail[0] if tail else "")


def _ruff_check() -> ReadinessCheck:
    code, tail = _run_subprocess(_ruff_argv(), timeout=_RUFF_TIMEOUT_S)
    ok = code == 0
    detail = (
        "ruff check . — clean"
        if ok
        else f"ruff check . failed (exit {code}): {tail}".rstrip(": ")
    )
    return ReadinessCheck("ruff lint", PASS if ok else FAIL, detail, hard=True)


def _fast_test_slice_check() -> ReadinessCheck:
    code, tail = _run_subprocess(_pytest_argv(), timeout=_PYTEST_TIMEOUT_S)
    ok = code == 0
    detail = (
        f"fast pytest slice passed ({len(_FAST_TEST_SLICE)} suites)"
        if ok
        else f"fast pytest slice failed (exit {code}): {tail}".rstrip(": ")
    )
    return ReadinessCheck("fast test slice", PASS if ok else FAIL, detail, hard=True)


def run_release_gate(*, run_tests: bool = True) -> ReadinessReport:
    """Aggregate the 10/10 doctor + ruff (+ fast test slice) into one verdict.

    Starts from every :func:`run_10_10_doctor` check, then appends a ruff gate
    and — when ``run_tests`` — the fast pytest slice, all in the same
    ``ReadinessCheck`` shape. ``ok`` is recomputed over the combined set so a
    hard FAIL anywhere (a doctor hard gate, ruff, or the slice) blocks ship,
    while soft punch-list warnings never do.

    Never raises: subprocess failures become FAIL checks.
    """
    report = run_10_10_doctor()
    checks = list(report.checks)
    checks.append(_ruff_check())
    if run_tests:
        checks.append(_fast_test_slice_check())
    ok = not any(c.status == FAIL and c.hard for c in checks)
    return ReadinessReport(ok=ok, checks=checks)
