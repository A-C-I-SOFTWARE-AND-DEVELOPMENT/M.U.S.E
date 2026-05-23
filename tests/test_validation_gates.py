"""Tests for validation gates and the gate runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.orchestrator.validation_gates import (
    GateResult,
    NoSecretsGate,
    PatchAppliesGate,
    PyCompileGate,
    PytestGate,
    ShellSyntaxGate,
    ValidationGate,
    all_passed,
    run_gates,
)


# ── PyCompileGate ────────────────────────────────────────────────────


def test_py_compile_passes_with_no_files(tmp_path: Path) -> None:
    res = PyCompileGate().check(tmp_path, runner=lambda *a, **kw: (0, ""))
    assert res.passed
    assert "no .py" in res.message


def test_py_compile_invokes_runner_with_target_files(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 2\n")
    captured: list[list[str]] = []

    def runner(cmd, cwd, env):
        captured.append(cmd)
        return 0, ""

    res = PyCompileGate().check(tmp_path, runner=runner)
    assert res.passed
    assert captured[0][:3] == ["python", "-m", "py_compile"]
    assert any(p.endswith("a.py") for p in captured[0])
    assert any(p.endswith("b.py") for p in captured[0])


def test_py_compile_records_failure(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("bad syntax !!\n")

    def runner(cmd, cwd, env):
        return 1, "  File 'a.py', line 1\n    bad syntax\n   SyntaxError: invalid\n"

    res = PyCompileGate().check(tmp_path, runner=runner)
    assert not res.passed
    assert "SyntaxError" in res.message


def test_py_compile_with_include(tmp_path: Path) -> None:
    (tmp_path / "keep").mkdir()
    (tmp_path / "keep" / "a.py").write_text("ok\n")
    (tmp_path / "skip").mkdir()
    (tmp_path / "skip" / "b.py").write_text("ok\n")
    captured: list[list[str]] = []

    def runner(cmd, cwd, env):
        captured.append(cmd)
        return 0, ""

    PyCompileGate(include=["keep"]).check(tmp_path, runner=runner)
    flat = " ".join(captured[0])
    assert "keep/a.py" in flat
    assert "skip/b.py" not in flat


# ── ShellSyntaxGate ──────────────────────────────────────────────────


def test_shell_syntax_passes_with_no_files(tmp_path: Path) -> None:
    res = ShellSyntaxGate().check(tmp_path, runner=lambda *a, **kw: (0, ""))
    assert res.passed


def test_shell_syntax_calls_bash_n_per_file(tmp_path: Path) -> None:
    (tmp_path / "a.sh").write_text("echo hi\n")
    (tmp_path / "b.sh").write_text("echo bye\n")
    cmds: list[list[str]] = []

    def runner(cmd, cwd, env):
        cmds.append(cmd)
        return 0, ""

    res = ShellSyntaxGate().check(tmp_path, runner=runner)
    assert res.passed
    assert len(cmds) == 2
    for c in cmds:
        assert c[:2] == ["bash", "-n"]


def test_shell_syntax_reports_each_failure(tmp_path: Path) -> None:
    (tmp_path / "a.sh").write_text("echo hi\n")
    (tmp_path / "b.sh").write_text("if then; fi\n")

    def runner(cmd, cwd, env):
        if cmd[-1].endswith("b.sh"):
            return 2, "b.sh: line 1: syntax error\n"
        return 0, ""

    res = ShellSyntaxGate().check(tmp_path, runner=runner)
    assert not res.passed
    assert "b.sh" in res.message


# ── NoSecretsGate ────────────────────────────────────────────────────


def test_no_secrets_passes_on_clean_diff() -> None:
    diff = (
        "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-foo\n+bar\n"
    )
    res = NoSecretsGate(diff=diff).check(Path("/tmp"))
    assert res.passed


def test_no_secrets_blocks_aws_key() -> None:
    diff = "+++ b/.env\n+AWS_KEY=AKIA1234567890ABCDEF\n"
    res = NoSecretsGate(diff=diff).check(Path("/tmp"))
    assert not res.passed
    assert "AKIA" in res.details["hits"][0] or "secret" in res.message.lower()


def test_no_secrets_blocks_github_token() -> None:
    diff = "+++ b/.env\n+TOKEN=ghp_" + "a" * 40 + "\n"
    res = NoSecretsGate(diff=diff).check(Path("/tmp"))
    assert not res.passed


def test_no_secrets_blocks_openai_key() -> None:
    diff = "+++ b/.env\n+OPENAI_API_KEY=sk-" + "b" * 40 + "\n"
    res = NoSecretsGate(diff=diff).check(Path("/tmp"))
    assert not res.passed


def test_no_secrets_blocks_private_key_block() -> None:
    diff = (
        "+++ b/secret.pem\n"
        "+-----BEGIN RSA PRIVATE KEY-----\n"
        "+MIIBOgIBAAJBA...\n"
    )
    res = NoSecretsGate(diff=diff).check(Path("/tmp"))
    assert not res.passed


def test_no_secrets_ignores_context_lines() -> None:
    """Secrets that appear only in unchanged context lines do not block."""
    diff = (
        " context line with AKIA1234567890ABCDEF\n"
        "-old\n"
        "+new\n"
    )
    res = NoSecretsGate(diff=diff).check(Path("/tmp"))
    assert res.passed


# ── PatchAppliesGate ─────────────────────────────────────────────────


def test_patch_applies_empty_diff_passes(tmp_path: Path) -> None:
    res = PatchAppliesGate("").check(tmp_path, runner=lambda *a, **kw: (0, ""))
    assert res.passed


def test_patch_applies_invokes_git_apply_check(tmp_path: Path) -> None:
    captured: list[list[str]] = []

    def runner(cmd, cwd, env):
        captured.append(cmd)
        return 0, ""

    diff = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
    res = PatchAppliesGate(diff).check(tmp_path, runner=runner)
    assert res.passed
    assert captured[0][:3] == ["git", "apply", "--check"]


def test_patch_applies_fails_when_check_fails(tmp_path: Path) -> None:
    def runner(cmd, cwd, env):
        return 1, "patch does not apply\n"

    res = PatchAppliesGate("--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n").check(
        tmp_path, runner=runner
    )
    assert not res.passed


# ── PytestGate ───────────────────────────────────────────────────────


def test_pytest_gate_passes_on_zero_exit(tmp_path: Path) -> None:
    captured: list[list[str]] = []

    def runner(cmd, cwd, env):
        captured.append(cmd)
        return 0, "5 passed\n"

    res = PytestGate(args=["tests/test_x.py"]).check(tmp_path, runner=runner)
    assert res.passed
    assert captured[0][0] == "pytest"
    assert "tests/test_x.py" in captured[0]


def test_pytest_gate_fails_on_nonzero(tmp_path: Path) -> None:
    def runner(cmd, cwd, env):
        return 1, "1 failed, 4 passed\n"

    res = PytestGate().check(tmp_path, runner=runner)
    assert not res.passed
    assert "failed" in res.message


# ── run_gates / all_passed ──────────────────────────────────────────


def test_run_gates_collects_every_result(tmp_path: Path) -> None:
    class A(ValidationGate):
        name = "a"
        def check(self, w, *, runner=None):
            return GateResult("a", True, "ok")

    class B(ValidationGate):
        name = "b"
        def check(self, w, *, runner=None):
            return GateResult("b", False, "no")

    results = run_gates(tmp_path, [A(), B()])
    assert set(results.keys()) == {"a", "b"}
    assert results["a"].passed and not results["b"].passed
    assert all_passed(results) is False


def test_run_gates_catches_exceptions(tmp_path: Path) -> None:
    class Boom(ValidationGate):
        name = "boom"
        def check(self, w, *, runner=None):
            raise RuntimeError("kaboom")

    results = run_gates(tmp_path, [Boom()])
    assert "boom" in results
    assert not results["boom"].passed
    assert "kaboom" in results["boom"].message


def test_all_passed_empty_is_true() -> None:
    assert all_passed({}) is True
