"""Termux import-time discipline for the JARVIS Prime package.

JARVIS Prime must be importable on Termux and slim CI images where
``pydantic``, ``anthropic``, ``openai``, ``yaml``, gateway, and the
Hermes plugin layer may not be installed. The package docstring
(``hermes_cli/jarvis_prime/__init__.py:18-21``) promises stdlib-only
imports at module-import time; optional plugin backends are loaded
lazily inside ``runtime`` and ``awareness``.

These tests run each import inside a fresh subprocess so they aren't
fooled by other tests in the parent process having already pulled in
the forbidden deps via unrelated code paths.

The forbidden-deps list is intentionally narrow: only modules whose
presence at JARVIS-import time would defeat Termux compatibility.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_DEPS = (
    "pydantic",
    "requests",
    "httpx",
    "yaml",
    "anthropic",
    "openai",
    "supabase",
    "mem0",
    "honcho",
    "gateway",
    "plugins",
    "hermes_cli.kanban",
)


# Every public Python module under ``hermes_cli/jarvis_prime/``.
# Used to parametrize the per-module isolation test.
JARVIS_MODULES = (
    "hermes_cli.jarvis_prime",
    "hermes_cli.jarvis_prime.awareness",
    "hermes_cli.jarvis_prime.communication_style",
    "hermes_cli.jarvis_prime.epistemics",
    "hermes_cli.jarvis_prime.gates",
    "hermes_cli.jarvis_prime.memory",
    "hermes_cli.jarvis_prime.modes",
    "hermes_cli.jarvis_prime.onboarding",
    "hermes_cli.jarvis_prime.owner_auth",
    "hermes_cli.jarvis_prime.persona",
    "hermes_cli.jarvis_prime.reasoning",
    "hermes_cli.jarvis_prime.research",
    "hermes_cli.jarvis_prime.router",
    "hermes_cli.jarvis_prime.self_update",
    "hermes_cli.jarvis_prime.social_research",
    "hermes_cli.jarvis_prime.tick",
    "hermes_cli.jarvis_prime.work_packet",
)


def _run_in_subprocess(snippet: str) -> subprocess.CompletedProcess[str]:
    """Run a Python snippet in a fresh interpreter, project root on sys.path."""

    return subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _import_check_snippet(import_target: str, forbidden: tuple[str, ...]) -> str:
    forbidden_list = ", ".join(repr(f) for f in forbidden)
    return (
        "import sys\n"
        f"import {import_target}\n"
        f"forbidden = ({forbidden_list},)\n"
        "leaked = sorted(\n"
        "    m for m in sys.modules\n"
        "    if any(m == f or m.startswith(f + '.') for f in forbidden)\n"
        ")\n"
        "if leaked:\n"
        "    print('LEAKED:', ','.join(leaked), file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "print('ok')\n"
    )


def test_top_level_package_imports_no_heavy_deps() -> None:
    """``import hermes_cli.jarvis_prime`` must not pull in any heavy dep."""

    proc = _run_in_subprocess(
        _import_check_snippet("hermes_cli.jarvis_prime", FORBIDDEN_DEPS)
    )
    if proc.returncode != 0:
        pytest.fail(
            "Top-level JARVIS Prime import leaked forbidden deps.\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    assert "ok" in proc.stdout


@pytest.mark.parametrize("module", JARVIS_MODULES)
def test_each_jarvis_module_imports_in_isolation(module: str) -> None:
    """Each JARVIS module must import cleanly in a fresh subprocess.

    Catches accidental top-level imports of optional deps in modules
    that haven't yet been wired into ``__init__.py``.
    """

    proc = _run_in_subprocess(_import_check_snippet(module, FORBIDDEN_DEPS))
    if proc.returncode != 0:
        pytest.fail(
            f"Module {module} leaked forbidden deps at import time.\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )


def test_cli_help_runs_in_clean_subprocess() -> None:
    """``python -m hermes_cli.jarvis_prime --help`` must exit 0."""

    proc = subprocess.run(
        [sys.executable, "-m", "hermes_cli.jarvis_prime", "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        pytest.fail(
            f"CLI --help exited {proc.returncode}.\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )


def test_forbidden_deps_list_matches_package_docstring() -> None:
    """Documented promise: ``pydantic``, ``requests``, ``httpx`` are off the
    import-time hot path. Keep the test's forbidden list in sync with that
    promise so we don't quietly drop coverage of the documented invariant.
    """

    docstring = (REPO_ROOT / "hermes_cli" / "jarvis_prime" / "__init__.py").read_text(
        encoding="utf-8"
    )
    assert "stdlib-only at import time" in docstring
    for required in ("pydantic", "requests", "httpx"):
        assert required in FORBIDDEN_DEPS, (
            f"FORBIDDEN_DEPS must cover {required!r} to match the package "
            "docstring's promise."
        )
