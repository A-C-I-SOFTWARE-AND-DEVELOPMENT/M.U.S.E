"""Tests for :class:`DockerRuntimeAdapter` — subprocess fully mocked, no daemon.

The adapter shells out to the ``docker`` CLI. ``shutil.which`` is faked present,
``subprocess.run`` (``prepare``/``cleanup``: image inspect/pull, container
run/rm) returns canned results keyed on the docker subcommand, and
``subprocess.Popen`` (``run``'s capture via ``_spawn_to_files``) writes
deterministic bytes into the stdout file handle. No Docker daemon is contacted.
"""

from __future__ import annotations

import subprocess

import pytest

from hermes_cli import runtime_adapter
from hermes_cli.runtime_adapter import DockerRuntimeAdapter, RuntimeResult


class _FakeCompleted:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _present_binaries(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_adapter.shutil, "which", lambda name: f"/usr/bin/{name}"
    )


def _install_docker_run(
    monkeypatch,
    *,
    image_present: bool = True,
    pull_ok: bool = True,
    start_ok: bool = True,
) -> list[list[str]]:
    records: list[list[str]] = []

    def fake_run(argv, **kw):
        records.append(argv)
        sub = argv[1] if len(argv) > 1 else ""
        if argv[1:3] == ["image", "inspect"]:
            return _FakeCompleted(0 if image_present else 1)
        if sub == "pull":
            return _FakeCompleted(0 if pull_ok else 1, stderr="pull boom")
        if sub == "run":
            return _FakeCompleted(
                0 if start_ok else 1, stdout="cid123\n", stderr="run boom"
            )
        return _FakeCompleted(0)

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)
    return records


def _install_fake_popen(
    monkeypatch, *, out: str = "ctr-out\n", returncode: int = 0, timeout: bool = False
) -> dict:
    captured: dict = {"killed": False}
    should_timeout = timeout

    class _FakePopen:
        def __init__(self, argv, **kwargs):
            captured["argv"] = argv
            self._waited = 0
            stdout = kwargs.get("stdout")
            if stdout is not None and hasattr(stdout, "write"):
                stdout.write(out)

        def wait(self, timeout=None):
            self._waited += 1
            if should_timeout and self._waited == 1:
                raise subprocess.TimeoutExpired(cmd="docker", timeout=timeout)
            return returncode

        def kill(self):
            captured["killed"] = True

    monkeypatch.setattr(runtime_adapter.subprocess, "Popen", _FakePopen)
    return captured


def test_docker_run_builds_exec_argv_and_captures(tmp_path, monkeypatch):
    _present_binaries(monkeypatch)
    _install_docker_run(monkeypatch, image_present=True)
    captured = _install_fake_popen(monkeypatch, out="container-said-hi\n")

    docker = DockerRuntimeAdapter(
        host_id="ctr",
        image="python:3.12",
        container_name="ctr1",
        local_logdir=tmp_path,
    )
    docker.prepare()
    result = docker.run(["echo", "hi"], timeout=30)

    assert isinstance(result, RuntimeResult)
    assert result.returncode == 0
    argv = captured["argv"]
    assert argv[:2] == ["docker", "exec"]
    assert "-w" in argv and "/workspace" in argv
    assert argv[-4:-1] == ["ctr1", "sh", "-c"]
    assert "echo hi" in argv[-1]
    assert result.stdout_path.read_text(encoding="utf-8") == "container-said-hi\n"


def test_docker_prepare_pulls_when_image_absent(tmp_path, monkeypatch):
    _present_binaries(monkeypatch)
    records = _install_docker_run(monkeypatch, image_present=False, pull_ok=True)
    _install_fake_popen(monkeypatch)

    docker = DockerRuntimeAdapter(
        host_id="ctr", image="busybox:latest", container_name="c", local_logdir=tmp_path
    )
    docker.prepare()
    assert any(a[1] == "pull" and "busybox:latest" in a for a in records)


def test_docker_prepare_pull_failure_raises(monkeypatch):
    _present_binaries(monkeypatch)
    _install_docker_run(monkeypatch, image_present=False, pull_ok=False)
    docker = DockerRuntimeAdapter(host_id="ctr", image="nope:404")
    with pytest.raises(RuntimeError, match="pull"):
        docker.prepare()
    assert docker._prepared is False


def test_docker_prepare_start_failure_raises(monkeypatch):
    _present_binaries(monkeypatch)
    _install_docker_run(monkeypatch, image_present=True, start_ok=False)
    docker = DockerRuntimeAdapter(host_id="ctr", image="python:3.12")
    with pytest.raises(RuntimeError, match="start container"):
        docker.prepare()
    assert docker._prepared is False


def test_docker_run_env_and_mount(tmp_path, monkeypatch):
    _present_binaries(monkeypatch)
    records = _install_docker_run(monkeypatch, image_present=True)
    captured = _install_fake_popen(monkeypatch)

    docker = DockerRuntimeAdapter(
        host_id="ctr",
        image="python:3.12",
        container_name="c2",
        host_workspace=tmp_path,
        env={"TOKEN": "abc"},
        local_logdir=tmp_path,
    )
    docker.prepare()
    docker.run(["echo", "x"], timeout=10)

    # bind-mount was passed to `docker run`.
    run_argv = next(a for a in records if len(a) > 1 and a[1] == "run")
    assert "-v" in run_argv
    assert any(str(tmp_path.resolve()) in tok for tok in run_argv)
    # env reached `docker exec`.
    exec_argv = captured["argv"]
    assert "-e" in exec_argv and "TOKEN=abc" in exec_argv


def test_docker_run_timeout_returns_124(tmp_path, monkeypatch):
    _present_binaries(monkeypatch)
    _install_docker_run(monkeypatch, image_present=True)
    captured = _install_fake_popen(monkeypatch, timeout=True)

    docker = DockerRuntimeAdapter(
        host_id="ctr", image="python:3.12", container_name="c3", local_logdir=tmp_path
    )
    docker.prepare()
    result = docker.run(["sleep", "100"], timeout=1)
    assert result.timed_out is True
    assert result.returncode == 124
    assert captured["killed"] is True


def test_docker_cleanup_removes_container(tmp_path, monkeypatch):
    _present_binaries(monkeypatch)
    records = _install_docker_run(monkeypatch, image_present=True)
    _install_fake_popen(monkeypatch)

    docker = DockerRuntimeAdapter(
        host_id="ctr", image="python:3.12", container_name="c4", local_logdir=tmp_path
    )
    docker.prepare()
    docker.cleanup()
    assert any(a[1:3] == ["rm", "-f"] and "c4" in a for a in records)
    assert docker._prepared is False
