"""Unified release gate for M.U.S.E. — one verdict over every ship signal.

Backs ``muse doctor --release-gate``. It aggregates the existing 10/10
release-readiness checks (:func:`muse_cli.release_readiness_doctor.run_10_10_doctor`)
with the two *runtime* gates the smoke script (``scripts/muse-10-10-smoke.sh``)
also runs — ``ruff check .`` and a fast, launch-critical pytest slice — into a
single :class:`~muse_cli.release_readiness_doctor.ReadinessReport`.

Design notes:

* It **reuses** the doctor's dataclasses (``ReadinessReport`` / ``ReadinessCheck``)
  rather than defining a parallel report type, so every consumer (CLI text/JSON
  render, ``.ok`` aggregation) keeps working unchanged.
* ruff / pytest are run as subprocesses, mirroring the smoke script — this keeps
  CI parity (same commands, same flags) and avoids importing pytest into the
  doctor's import-free probe model.
* A subprocess failure surfaces as a check, never an exception: like the
  doctor, this function never raises. A *real* red result (lint dirty / suite
  failing) is a hard ``FAIL``; a *missing tool* (no reachable ruff/pytest) is a
  soft ``WARN`` so it never false-REDs ship — see the FU-10 note below.

The ruff gate is **hard** (lint is the repo's enforced gate, so a dirty tree
must block ship). The test slice is **hard** too — a red fast slice is not
safe to ship. Soft 10/10 punch-list warnings from the doctor stay soft and
never block.

False-RED hardening (FU-10): the gate prefers ``uv run`` for CI parity, but
a host can have ``uv`` on PATH while its *project venv* lacks the dev tools
(e.g. an un-synced checkout with no ``pytest``). In that case
``uv run python -m pytest`` exits non-zero with ``No module named pytest`` —
which is *tooling absent*, not a red suite, and must never masquerade as a
hard FAIL. So before committing to an interpreter the gate **probes** whether
it can import the tool: if ``uv``'s interpreter can't, it falls back to the
system interpreter (``sys.executable``) / a bare ``ruff``. If *no* reachable
interpreter has the tool at all, the check reports a clearly-labeled,
non-blocking ``WARN`` (tooling absent) — distinct from a genuine ``FAIL``
(the tool ran and the suite/lint was red).

Strict tooling (WC-2): the FU-10 anti-false-RED behavior above protects dev
checkouts but inverts the gate on a release host (a stripped Termux release
lane or CI runner with no ``ruff``/``pytest`` reports GREEN ship having
validated nothing). When ``HERMES_RELEASE_GATE_STRICT=1`` (set on release
hosts and CI), missing tools become a *hard FAIL* with a clear "tooling
absent on release host" message. Default stays soft for dev convenience —
this is strictly opt-in. Equivalently, callers can pass
``strict_tooling=True`` to :func:`run_release_gate` to force the strict
verdict regardless of env.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from muse_cli.release_readiness_doctor import (
    FAIL,
    PASS,
    WARN,
    ReadinessCheck,
    ReadinessReport,
    run_10_10_doctor,
)

# WC-2: the env var that flips the gate from "anti-false-RED" (dev default)
# to "fail-closed on missing tools" (release host / CI). Truthy values are
# the canonical set: 1 / true / yes / on (case-insensitive).
_STRICT_TOOLING_ENV = "HERMES_RELEASE_GATE_STRICT"
_STRICT_TRUTHY = {"1", "true", "yes", "on"}


def _strict_tooling_enabled() -> bool:
    """True iff ``HERMES_RELEASE_GATE_STRICT`` is set to a truthy value.

    Read at every check (not cached) so tests / CI can flip it via
    monkeypatch without restarting the process. Default OFF preserves the
    FU-10 anti-false-RED behavior on dev hosts; release lanes opt in.
    """
    return os.environ.get(_STRICT_TOOLING_ENV, "").strip().lower() in _STRICT_TRUTHY

# Fast, launch-critical pytest slice — kept in lockstep with
# scripts/muse-10-10-smoke.sh (readiness + action executors + a couple of
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
# A capability probe ("can this interpreter import the tool?") is a couple of
# import statements — short, never the long-pole.
_PROBE_TIMEOUT_S = 60


def _repo_root() -> Path:
    # muse_cli/release_gate.py -> repo root is one level up.
    return Path(__file__).resolve().parents[1]


def _probe_ok(argv: list[str]) -> bool:
    """True iff ``argv`` runs to a zero exit (a capability probe).

    Used to ask "can this interpreter actually import the tool?" *before* the
    gate commits to it. Never raises (delegates to :func:`_run_subprocess`),
    and a missing executable / crash / timeout reads as ``False``.
    """
    code, _ = _run_subprocess(argv, timeout=_PROBE_TIMEOUT_S)
    return code == 0


def _uv_can_import(module: str) -> bool:
    """True iff ``uv``'s project interpreter can ``import <module>``.

    Guards the ``uv run`` fast-path: ``uv`` may be on PATH while its venv is
    un-synced and lacks the dev tool (the FU-10 false-RED). Probing import
    here lets the gate fall back to the system interpreter instead of turning
    "tooling absent under uv" into a red suite/lint.
    """
    if not shutil.which("uv"):
        return False
    return _probe_ok(["uv", "run", "python", "-c", f"import {module}"])


def _ruff_argv() -> tuple[list[str], bool]:
    """Pick the ruff invocation, preferring ``uv run ruff`` for CI parity.

    Returns ``(argv, available)``. Probes (in order) ``uv run ruff`` then a
    bare ``ruff``; the first that responds to ``--version`` wins. ``available``
    is ``False`` only when *no* reachable ruff exists — the caller turns that
    into an honest non-blocking WARN ("tooling absent"), never a red-lint FAIL.
    """
    if shutil.which("uv") and _probe_ok(["uv", "run", "ruff", "--version"]):
        return ["uv", "run", "ruff", "check", "."], True
    if shutil.which("ruff") and _probe_ok(["ruff", "--version"]):
        return ["ruff", "check", "."], True
    # Last resort: still return a runnable argv so the caller's distinction
    # logic (missing-tool vs failed-lint) drives the verdict, not a guess here.
    return (["uv", "run", "ruff", "check", "."] if shutil.which("uv") else ["ruff", "check", "."]), False


def _pytest_argv() -> tuple[list[str], bool]:
    """Pick the pytest invocation for the fast slice, preferring ``uv run``.

    Returns ``(argv, available)``. ``-o addopts=""`` drops the xdist/timeout
    plugins the slice does not need; ``-q`` keeps output compact. The gate
    prefers ``uv run`` for environment parity, but only after confirming
    ``uv``'s interpreter can ``import pytest`` — otherwise it falls back to the
    system interpreter (``sys.executable -m pytest``). ``available`` is
    ``False`` only when *no* reachable interpreter has pytest, which the caller
    renders as a non-blocking "tooling absent" WARN rather than a red suite.
    """
    flags = ["-m", "pytest", "-q", "-o", "addopts="]
    slice_args = [*flags, *_FAST_TEST_SLICE]
    # Preferred: uv's interpreter, but only if it can actually import pytest.
    if _uv_can_import("pytest"):
        return ["uv", "run", "python", *slice_args], True
    # Fallback: the system interpreter running the gate, if it has pytest.
    if _probe_ok([sys.executable, "-c", "import pytest"]):
        return [sys.executable, *slice_args], True
    # Neither has pytest: hand back the system-interpreter argv (most honest
    # error text) and flag it unavailable so the caller emits a WARN, not FAIL.
    return [sys.executable, *slice_args], False


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


# Substrings that mean "the tool was absent from the chosen interpreter",
# i.e. the runner never ran the suite/lint — not a red result. Matching these
# downgrades a non-zero exit from a hard FAIL to an honest, non-blocking WARN.
_PYTEST_ABSENT_MARKERS: tuple[str, ...] = (
    "no module named pytest",
    "no module named 'pytest'",
)
_RUFF_ABSENT_MARKERS: tuple[str, ...] = (
    "executable not found",
    "no such file or directory",
    "command not found",
)


def _looks_tool_absent(tail: str, markers: tuple[str, ...]) -> bool:
    low = tail.lower()
    return any(m in low for m in markers)


def _tool_absent_check(name: str, dev_msg: str, strict_msg: str, *, strict: bool) -> ReadinessCheck:
    """Render a "tool absent" verdict.

    WC-2: in strict mode (release host / CI), tool absence is a hard FAIL —
    the gate refuses to ship without having actually run the check. In dev
    mode (the default) it is a soft WARN, preserving FU-10's anti-false-RED
    behavior on an un-synced checkout. The message names the strict mode
    explicitly so an operator who sees a FAIL knows exactly which env var
    inverted the verdict.
    """
    if strict:
        return ReadinessCheck(
            name,
            FAIL,
            f"{strict_msg} [release-host strict mode: {_STRICT_TOOLING_ENV}=1]",
            hard=True,
        )
    return ReadinessCheck(name, WARN, dev_msg, hard=False)


def _ruff_check(*, strict_tooling: bool = False) -> ReadinessCheck:
    argv, available = _ruff_argv()
    if not available:
        # No reachable ruff (neither ``uv run ruff`` nor a bare ``ruff``).
        # In dev mode that's tooling absent (soft WARN, FU-10 behavior). In
        # strict mode it's a hard FAIL — a release host with no ruff cannot
        # claim a clean lint.
        return _tool_absent_check(
            "ruff lint",
            dev_msg=(
                "ruff unavailable (no uv/ruff on this host) — lint not run; "
                "install ruff or sync the uv venv to enforce this gate"
            ),
            strict_msg=(
                "ruff unavailable on a release host — refusing to ship without "
                "the lint check actually running; install ruff or sync the uv venv"
            ),
            strict=strict_tooling,
        )
    code, tail = _run_subprocess(argv, timeout=_RUFF_TIMEOUT_S)
    if code == 0:
        return ReadinessCheck("ruff lint", PASS, "ruff check . — clean", hard=True)
    # Defensive: a probe-passed interpreter that still reports the tool missing
    # (e.g. PATH raced) is tooling-absent, not a lint failure.
    if _looks_tool_absent(tail, _RUFF_ABSENT_MARKERS):
        return _tool_absent_check(
            "ruff lint",
            dev_msg=f"ruff unavailable in chosen env (exit {code}): {tail}".rstrip(": "),
            strict_msg=f"ruff unavailable on a release host (exit {code}): {tail}".rstrip(": "),
            strict=strict_tooling,
        )
    detail = f"ruff check . failed (exit {code}): {tail}".rstrip(": ")
    return ReadinessCheck("ruff lint", FAIL, detail, hard=True)


def _fast_test_slice_check(*, strict_tooling: bool = False) -> ReadinessCheck:
    argv, available = _pytest_argv()
    if not available:
        # No reachable interpreter has pytest. In dev mode that's a soft WARN
        # (FU-10 behavior). In strict mode the gate refuses to ship: a release
        # host cannot pass on a test slice that never ran.
        return _tool_absent_check(
            "fast test slice",
            dev_msg=(
                "pytest unavailable (no uv/system interpreter with pytest) — "
                "fast slice not run; sync the uv venv or install pytest to "
                "enforce this gate"
            ),
            strict_msg=(
                "pytest unavailable on a release host — refusing to ship without "
                "the fast slice actually running; install pytest or sync the uv venv"
            ),
            strict=strict_tooling,
        )
    code, tail = _run_subprocess(argv, timeout=_PYTEST_TIMEOUT_S)
    if code == 0:
        return ReadinessCheck(
            "fast test slice",
            PASS,
            f"fast pytest slice passed ({len(_FAST_TEST_SLICE)} suites)",
            hard=True,
        )
    # Defensive: if the chosen interpreter still reports pytest missing (the
    # FU-10 false-RED), treat it as tooling absent — never a red suite.
    if _looks_tool_absent(tail, _PYTEST_ABSENT_MARKERS):
        return _tool_absent_check(
            "fast test slice",
            dev_msg=f"pytest unavailable in chosen env (exit {code}): {tail}".rstrip(": "),
            strict_msg=f"pytest unavailable on a release host (exit {code}): {tail}".rstrip(": "),
            strict=strict_tooling,
        )
    detail = f"fast pytest slice failed (exit {code}): {tail}".rstrip(": ")
    return ReadinessCheck("fast test slice", FAIL, detail, hard=True)


def run_release_gate(
    *, run_tests: bool = True, strict_tooling: bool | None = None
) -> ReadinessReport:
    """Aggregate the 10/10 doctor + ruff (+ fast test slice) into one verdict.

    Starts from every :func:`run_10_10_doctor` check, then appends a ruff gate
    and — when ``run_tests`` — the fast pytest slice, all in the same
    ``ReadinessCheck`` shape. ``ok`` is recomputed over the combined set so a
    hard FAIL anywhere (a doctor hard gate, ruff, or the slice) blocks ship,
    while soft punch-list warnings never do.

    WC-2 ``strict_tooling``:

    * ``None`` (default) → consult the ``HERMES_RELEASE_GATE_STRICT`` env var;
      truthy values flip the gate to fail-closed on missing tools.
    * ``True`` → force strict mode regardless of env (used by tests and by the
      release-host launch lane).
    * ``False`` → force dev-friendly mode regardless of env (escape hatch for
      manual local runs on an un-synced checkout).

    Never raises: subprocess failures become FAIL checks.
    """
    if strict_tooling is None:
        strict_tooling = _strict_tooling_enabled()
    report = run_10_10_doctor()
    checks = list(report.checks)
    checks.append(_ruff_check(strict_tooling=strict_tooling))
    if run_tests:
        checks.append(_fast_test_slice_check(strict_tooling=strict_tooling))
    ok = not any(c.status == FAIL and c.hard for c in checks)
    return ReadinessReport(ok=ok, checks=checks)
