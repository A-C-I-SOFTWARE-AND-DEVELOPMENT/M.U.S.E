"""Validation gates that must pass before publishing.

A gate inspects a working directory (the materialized worker output)
and returns a :class:`GateResult`. ``run_gates`` runs each gate in
order; the overall result is the conjunction of every individual gate.

Tests inject a fake ``runner`` so gates that would normally shell out
(``pytest``, ``py_compile``, ``bash -n``) stay hermetic.
"""

from __future__ import annotations

import abc
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from hermes_cli.workers.base import _real_runner

RunnerFn = Callable[[list[str], Path, dict[str, str] | None], tuple[int, str]]


@dataclass
class GateResult:
    name: str
    passed: bool
    message: str = ""
    duration_s: float = 0.0
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d["details"] is None:
            d.pop("details")
        return d


class ValidationGate(abc.ABC):
    name: str = ""

    @abc.abstractmethod
    def check(
        self, workdir: Path, *, runner: RunnerFn | None = None
    ) -> GateResult: ...


# ── concrete gates ──────────────────────────────────────────────────


class PyCompileGate(ValidationGate):
    """Run ``python -m py_compile`` over targeted .py files.

    By default we compile every ``.py`` file under ``workdir``. Pass
    ``include`` to restrict (e.g. ``["hermes_cli", "tests"]``).
    """

    name = "py_compile"

    def __init__(self, include: list[str] | None = None) -> None:
        self.include = include

    def _targets(self, workdir: Path) -> list[Path]:
        if self.include:
            roots = [workdir / p for p in self.include]
        else:
            roots = [workdir]
        files: list[Path] = []
        for r in roots:
            if r.is_file() and r.suffix == ".py":
                files.append(r)
            elif r.is_dir():
                files.extend(sorted(r.rglob("*.py")))
        return files

    def check(self, workdir: Path, *, runner: RunnerFn | None = None) -> GateResult:
        runner = runner or _real_runner
        t0 = time.monotonic()
        files = self._targets(Path(workdir))
        if not files:
            return GateResult(self.name, True, "no .py files to compile",
                              time.monotonic() - t0)
        cmd = ["python", "-m", "py_compile", *[str(p) for p in files]]
        rc, out = runner(cmd, Path(workdir), None)
        return GateResult(
            self.name,
            rc == 0,
            (out.strip().splitlines()[-1] if rc != 0 and out.strip()
             else f"compiled {len(files)} files"),
            time.monotonic() - t0,
            details={"file_count": len(files), "exit_code": rc},
        )


class ShellSyntaxGate(ValidationGate):
    """Run ``bash -n`` over every ``.sh`` file under ``workdir``."""

    name = "shell_syntax"

    def __init__(self, include: list[str] | None = None) -> None:
        self.include = include

    def _targets(self, workdir: Path) -> list[Path]:
        roots = [workdir / p for p in self.include] if self.include else [workdir]
        out: list[Path] = []
        for r in roots:
            if r.is_file() and r.suffix == ".sh":
                out.append(r)
            elif r.is_dir():
                out.extend(sorted(r.rglob("*.sh")))
        return out

    def check(self, workdir: Path, *, runner: RunnerFn | None = None) -> GateResult:
        runner = runner or _real_runner
        t0 = time.monotonic()
        files = self._targets(Path(workdir))
        if not files:
            return GateResult(self.name, True, "no .sh files to check",
                              time.monotonic() - t0)
        failures: list[str] = []
        for path in files:
            rc, out = runner(["bash", "-n", str(path)], Path(workdir), None)
            if rc != 0:
                failures.append(f"{path.name}: {out.strip()}")
        return GateResult(
            self.name,
            not failures,
            "; ".join(failures) if failures else f"checked {len(files)} files",
            time.monotonic() - t0,
            details={"file_count": len(files), "failures": failures},
        )


class PytestGate(ValidationGate):
    """Run ``pytest`` over a targeted set of tests."""

    name = "pytest"

    def __init__(self, args: list[str] | None = None) -> None:
        # No defaults — the orchestrator picks the right test selection.
        self.args = list(args or [])

    def check(self, workdir: Path, *, runner: RunnerFn | None = None) -> GateResult:
        runner = runner or _real_runner
        t0 = time.monotonic()
        cmd = ["pytest", "-q", *self.args]
        rc, out = runner(cmd, Path(workdir), None)
        msg = "tests passed" if rc == 0 else (
            out.strip().splitlines()[-1] if out.strip() else f"pytest exit {rc}"
        )
        return GateResult(self.name, rc == 0, msg, time.monotonic() - t0,
                          details={"exit_code": rc})


class NoSecretsGate(ValidationGate):
    """Refuse a diff that contains obvious secret patterns."""

    name = "no_secrets"

    # Conservative patterns: AWS keys, GitHub tokens, generic high-entropy
    # API key strings, RSA blocks.
    PATTERNS = [
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"ghp_[A-Za-z0-9]{36,}"),
        re.compile(r"github_pat_[A-Za-z0-9_]{40,}"),
        re.compile(r"sk-[A-Za-z0-9]{32,}"),
        re.compile(r"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    ]

    def __init__(self, diff: str = "") -> None:
        self.diff = diff

    def check(self, workdir: Path, *, runner: RunnerFn | None = None) -> GateResult:
        t0 = time.monotonic()
        hits: list[str] = []
        added = "\n".join(
            line for line in self.diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        for pat in self.PATTERNS:
            m = pat.search(added)
            if m:
                hits.append(pat.pattern)
        return GateResult(
            self.name,
            not hits,
            f"secret-shaped strings: {hits}" if hits else "no secrets",
            time.monotonic() - t0,
            details={"hits": hits},
        )


class PatchAppliesGate(ValidationGate):
    """Verify a diff applies cleanly via ``git apply --check``."""

    name = "patch_applies"

    def __init__(self, diff: str) -> None:
        self.diff = diff

    def check(self, workdir: Path, *, runner: RunnerFn | None = None) -> GateResult:
        from hermes_cli.orchestrator.merge_engine import apply_diff
        # apply_diff calls git apply --check first and aborts on failure.
        # We pass a "dry run" runner-only check via the runner fixture.
        t0 = time.monotonic()
        if not self.diff.strip():
            return GateResult(self.name, True, "empty diff", time.monotonic() - t0)
        runner = runner or _real_runner

        import tempfile

        with tempfile.NamedTemporaryFile(
            "w", suffix=".diff", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(self.diff)
            path = tf.name
        try:
            rc, out = runner(["git", "apply", "--check", path],
                             Path(workdir), None)
        finally:
            try:
                Path(path).unlink()
            except OSError:
                pass
        return GateResult(
            self.name,
            rc == 0,
            "applies" if rc == 0 else out.strip() or f"exit {rc}",
            time.monotonic() - t0,
            details={"exit_code": rc},
        )


# ── runner ──────────────────────────────────────────────────────────


def run_gates(
    workdir: Path | str,
    gates: Iterable[ValidationGate],
    *,
    runner: RunnerFn | None = None,
) -> dict[str, GateResult]:
    """Run every gate and return ``{gate.name: GateResult}``.

    Each gate runs independently — one failure does not skip subsequent
    gates, so the operator sees the full picture.
    """

    workdir = Path(workdir)
    out: dict[str, GateResult] = {}
    for gate in gates:
        try:
            out[gate.name] = gate.check(workdir, runner=runner)
        except Exception as exc:  # noqa: BLE001 — gates must never raise
            out[gate.name] = GateResult(
                gate.name, False, f"gate raised: {exc!r}"
            )
    return out


def all_passed(results: dict[str, GateResult]) -> bool:
    return all(r.passed for r in results.values())


__all__ = [
    "GateResult",
    "NoSecretsGate",
    "PatchAppliesGate",
    "PyCompileGate",
    "PytestGate",
    "ShellSyntaxGate",
    "ValidationGate",
    "all_passed",
    "run_gates",
]
