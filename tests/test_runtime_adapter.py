"""Tests for the runtime adapters (Sprint 13, multi-host substrate).

Pure + local: the only adapter exercised end-to-end is
:class:`LocalRuntimeAdapter`, which spawns trivial child processes via
``subprocess``. No network, no orchestrator import. The Protocol's
``@runtime_checkable`` behavior is verified structurally.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hermes_cli.runtime_adapter import (
    DockerRuntimeAdapter,
    LocalRuntimeAdapter,
    RuntimeAdapter,
    RuntimeResult,
    SSHRuntimeAdapter,
)


def _py(*code: str) -> list[str]:
    """An argv that runs the given python lines in this interpreter."""

    return [sys.executable, "-c", "\n".join(code)]


# ─── Protocol runtime-check ───────────────────────────────────────────


def test_local_adapter_is_runtime_adapter_instance():
    adapter = LocalRuntimeAdapter()
    assert isinstance(adapter, RuntimeAdapter)
    # host metadata matches the registry's "local" kind.
    assert adapter.host_id == "local"
    assert adapter.kind == "local"


def test_stub_adapters_are_runtime_adapter_instances():
    # The remote adapters satisfy the structural Protocol (they expose all
    # members). End-to-end behavior is covered in the dedicated ssh/docker
    # test modules; here we only assert the structural contract + host kind.
    ssh = SSHRuntimeAdapter(host_id="box", host="example.invalid")
    docker = DockerRuntimeAdapter(host_id="ctr", image="python:3.12")
    assert isinstance(ssh, RuntimeAdapter)
    assert isinstance(docker, RuntimeAdapter)
    assert (ssh.kind, docker.kind) == ("ssh", "docker")


def test_incomplete_object_is_not_a_runtime_adapter():
    class _Partial:
        host_id = "x"
        kind = "local"

        def prepare(self) -> None:  # missing run() and cleanup()
            ...

    assert not isinstance(_Partial(), RuntimeAdapter)

    # A bare object with none of the members certainly isn't one either.
    assert not isinstance(object(), RuntimeAdapter)


# ─── LocalRuntimeAdapter: running commands ────────────────────────────


def test_local_adapter_runs_trivial_command(tmp_path: Path):
    adapter = LocalRuntimeAdapter(workdir=tmp_path)
    adapter.prepare()
    result = adapter.run(_py("print('hello-runtime')"), timeout=30)

    assert isinstance(result, RuntimeResult)
    assert result.returncode == 0
    assert result.timed_out is False
    assert result.duration >= 0.0
    assert result.stdout_path.exists()
    assert "hello-runtime" in result.stdout_path.read_text(encoding="utf-8")


def test_local_adapter_captures_nonzero_exit(tmp_path: Path):
    adapter = LocalRuntimeAdapter(workdir=tmp_path)
    result = adapter.run(_py("import sys", "sys.exit(7)"), timeout=30)
    assert result.returncode == 7
    assert result.timed_out is False


def test_local_adapter_separate_stream_paths(tmp_path: Path):
    out = tmp_path / "out.log"
    err = tmp_path / "err.log"
    adapter = LocalRuntimeAdapter(workdir=tmp_path, stdout_path=out, stderr_path=err)
    result = adapter.run(
        _py(
            "import sys",
            "sys.stdout.write('to-out')",
            "sys.stderr.write('to-err')",
        ),
        timeout=30,
    )
    assert result.stdout_path == out
    assert result.stderr_path == err
    assert out.read_text(encoding="utf-8") == "to-out"
    assert err.read_text(encoding="utf-8") == "to-err"


def test_local_adapter_string_command_uses_shell(tmp_path: Path):
    adapter = LocalRuntimeAdapter(workdir=tmp_path)
    # A shell string exercises the shell=True path (echo is a shell builtin /
    # ubiquitous on POSIX + Windows).
    result = adapter.run("echo shellpath", timeout=30)
    assert result.returncode == 0
    assert "shellpath" in result.stdout_path.read_text(encoding="utf-8")


def test_local_adapter_runs_in_workdir(tmp_path: Path):
    sub = tmp_path / "nested"
    sub.mkdir()
    adapter = LocalRuntimeAdapter(workdir=sub)
    result = adapter.run(_py("import os", "print(os.getcwd())"), timeout=30)
    printed = result.stdout_path.read_text(encoding="utf-8").strip()
    # Resolve both sides: macOS /tmp symlinks to /private/tmp etc.
    assert Path(printed).resolve() == sub.resolve()


# Genuinely needs real signal delivery: the adapter SIGKILLs its own child on
# timeout. The autouse live-system guard blocks os.kill for PIDs it can't prove
# are in the test subtree (e.g. when psutil is absent in a slim env), so this
# test opts out — same precedent as the subprocess-killing tests in
# tests/test_parallel_runner.py.
@pytest.mark.live_system_guard_bypass
def test_local_adapter_times_out(tmp_path: Path):
    adapter = LocalRuntimeAdapter(workdir=tmp_path)
    # Sleep far longer than the timeout; the adapter must kill it and flag it.
    result = adapter.run(_py("import time", "time.sleep(30)"), timeout=0.5)
    assert result.timed_out is True
    assert result.returncode == 124


def test_local_adapter_run_without_prepare(tmp_path: Path):
    # run() tolerates a missing prepare() — it sets up the workdir itself.
    adapter = LocalRuntimeAdapter(workdir=tmp_path / "auto")
    result = adapter.run(_py("print('ok')"), timeout=30)
    assert result.returncode == 0
    assert (tmp_path / "auto").is_dir()


def test_local_adapter_env_overlay(tmp_path: Path):
    adapter = LocalRuntimeAdapter(workdir=tmp_path, env={"HERMES_RT_TEST": "42"})
    result = adapter.run(
        _py("import os", "print(os.environ.get('HERMES_RT_TEST', 'MISSING'))"),
        timeout=30,
    )
    assert result.stdout_path.read_text(encoding="utf-8").strip() == "42"


def test_local_adapter_rejects_bad_timeout(tmp_path: Path):
    adapter = LocalRuntimeAdapter(workdir=tmp_path)
    with pytest.raises(ValueError):
        adapter.run(_py("print('x')"), timeout=0)


def test_local_adapter_rejects_empty_command(tmp_path: Path):
    adapter = LocalRuntimeAdapter(workdir=tmp_path)
    with pytest.raises(ValueError):
        adapter.run([], timeout=30)
    with pytest.raises(ValueError):
        adapter.run("   ", timeout=30)


def test_local_adapter_default_stream_paths_under_workdir(tmp_path: Path):
    adapter = LocalRuntimeAdapter(workdir=tmp_path)
    result = adapter.run(_py("print('x')"), timeout=30)
    assert result.stdout_path == tmp_path / "stdout.log"
    assert result.stderr_path == tmp_path / "stderr.log"


def test_local_adapter_cleanup_is_safe(tmp_path: Path):
    adapter = LocalRuntimeAdapter(workdir=tmp_path)
    adapter.prepare()
    adapter.cleanup()
    # cleanup() on an already-cleaned adapter must not raise.
    adapter.cleanup()


# ─── remote adapters degrade clearly when their binary is absent ──────


def test_ssh_adapter_missing_binary_raises_runtimeerror(monkeypatch):
    # No `ssh` on PATH → a clear RuntimeError (never NotImplementedError, and
    # never a silent local fallback). cleanup() stays a safe no-op.
    monkeypatch.setattr("hermes_cli.runtime_adapter.shutil.which", lambda _: None)
    ssh = SSHRuntimeAdapter(host_id="box", host="example.invalid", user="me")
    with pytest.raises(RuntimeError, match="ssh"):
        ssh.prepare()
    assert ssh.cleanup() is None


def test_docker_adapter_missing_binary_raises_runtimeerror(monkeypatch):
    monkeypatch.setattr("hermes_cli.runtime_adapter.shutil.which", lambda _: None)
    docker = DockerRuntimeAdapter(host_id="ctr", image="python:3.12")
    with pytest.raises(RuntimeError, match="docker"):
        docker.prepare()
    assert docker.cleanup() is None
