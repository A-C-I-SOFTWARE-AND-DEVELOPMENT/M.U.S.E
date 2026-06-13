"""Tests for :class:`SSHRuntimeAdapter` — subprocess fully mocked, no network.

The adapter shells out to the system ``ssh`` binary over a ``ControlMaster``
socket. Here ``shutil.which`` is faked present, ``subprocess.run`` (used by
``prepare``/``cleanup``) returns canned ``CompletedProcess`` results, and
``subprocess.Popen`` (used by the shared ``_spawn_to_files`` capture in ``run``)
is replaced with a fake that writes deterministic bytes into the stdout file
handle. No SSH server is contacted.
"""

from __future__ import annotations

import subprocess

import pytest

from hermes_cli import runtime_adapter
from hermes_cli.runtime_adapter import RuntimeResult, SSHRuntimeAdapter


class _FakeCompleted:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _present_binaries(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_adapter.shutil, "which", lambda name: f"/usr/bin/{name}"
    )


def _install_fake_popen(
    monkeypatch, *, out: str = "remote-out\n", returncode: int = 0, timeout: bool = False
) -> dict:
    captured: dict = {"killed": False}
    should_timeout = timeout

    class _FakePopen:
        def __init__(self, argv, **kwargs):
            captured["argv"] = argv
            captured["shell"] = kwargs.get("shell")
            self._waited = 0
            stdout = kwargs.get("stdout")
            if stdout is not None and hasattr(stdout, "write"):
                stdout.write(out)

        def wait(self, timeout=None):
            self._waited += 1
            if should_timeout and self._waited == 1:
                raise subprocess.TimeoutExpired(cmd="ssh", timeout=timeout)
            return returncode

        def kill(self):
            captured["killed"] = True

    monkeypatch.setattr(runtime_adapter.subprocess, "Popen", _FakePopen)
    return captured


def test_ssh_run_builds_argv_and_captures_output(tmp_path, monkeypatch):
    _present_binaries(monkeypatch)
    runs: list[list[str]] = []
    monkeypatch.setattr(
        runtime_adapter.subprocess,
        "run",
        lambda argv, **kw: (runs.append(argv), _FakeCompleted(0))[1],
    )
    captured = _install_fake_popen(monkeypatch, out="hello-remote\n")

    ssh = SSHRuntimeAdapter(
        host_id="box",
        host="h.example",
        user="me",
        port=2222,
        workdir="/srv/app",
        local_logdir=tmp_path,
    )
    ssh.prepare()
    # prepare opened a ControlMaster (-M) and verified the remote workdir.
    assert any("-M" in a for a in runs)
    assert any("test -d" in a[-1] for a in runs)

    result = ssh.run(["echo", "hi"], timeout=30)
    assert isinstance(result, RuntimeResult)
    assert result.returncode == 0
    assert result.timed_out is False

    argv = captured["argv"]
    assert argv[0] == "ssh"
    assert "me@h.example" in argv
    assert "-p" in argv and "2222" in argv
    assert captured["shell"] is False  # remote string is one ssh arg, no local shell
    remote = argv[-1]
    assert remote.startswith("cd /srv/app && ")
    assert "echo hi" in remote
    # "paths, not bytes": output landed in the local file.
    assert result.stdout_path.read_text(encoding="utf-8") == "hello-remote\n"


def test_ssh_run_applies_env_prefix(tmp_path, monkeypatch):
    _present_binaries(monkeypatch)
    monkeypatch.setattr(
        runtime_adapter.subprocess, "run", lambda argv, **kw: _FakeCompleted(0)
    )
    captured = _install_fake_popen(monkeypatch)

    ssh = SSHRuntimeAdapter(
        host_id="box", host="h", env={"FOO": "bar baz"}, local_logdir=tmp_path
    )
    ssh.prepare()
    ssh.run(["echo", "x"], timeout=10)
    remote = captured["argv"][-1]
    assert "export FOO='bar baz'; " in remote


def test_ssh_run_timeout_returns_124(tmp_path, monkeypatch):
    _present_binaries(monkeypatch)
    monkeypatch.setattr(
        runtime_adapter.subprocess, "run", lambda argv, **kw: _FakeCompleted(0)
    )
    captured = _install_fake_popen(monkeypatch, timeout=True)

    ssh = SSHRuntimeAdapter(host_id="box", host="h", local_logdir=tmp_path)
    ssh.prepare()
    result = ssh.run(["sleep", "100"], timeout=1)
    assert result.timed_out is True
    assert result.returncode == 124
    assert captured["killed"] is True


def test_ssh_prepare_connection_failure_raises(monkeypatch):
    _present_binaries(monkeypatch)
    monkeypatch.setattr(
        runtime_adapter.subprocess,
        "run",
        lambda argv, **kw: _FakeCompleted(255, stderr="connection refused"),
    )
    ssh = SSHRuntimeAdapter(host_id="box", host="bad")
    with pytest.raises(RuntimeError, match="control connection"):
        ssh.prepare()
    assert ssh._prepared is False


def test_ssh_prepare_missing_workdir_raises(monkeypatch):
    _present_binaries(monkeypatch)

    def fake_run(argv, **kw):
        if "test -d" in argv[-1]:
            return _FakeCompleted(1)  # workdir absent
        return _FakeCompleted(0)  # master opens fine

    monkeypatch.setattr(runtime_adapter.subprocess, "run", fake_run)
    ssh = SSHRuntimeAdapter(host_id="box", host="h", workdir="/nope")
    with pytest.raises(RuntimeError, match="workdir"):
        ssh.prepare()
    assert ssh._prepared is False


def test_ssh_cleanup_closes_control_socket(tmp_path, monkeypatch):
    _present_binaries(monkeypatch)
    runs: list[list[str]] = []
    monkeypatch.setattr(
        runtime_adapter.subprocess,
        "run",
        lambda argv, **kw: (runs.append(argv), _FakeCompleted(0))[1],
    )
    _install_fake_popen(monkeypatch)

    ssh = SSHRuntimeAdapter(host_id="box", host="h", local_logdir=tmp_path)
    ssh.prepare()
    ssh.cleanup()
    assert any("-O" in a and "exit" in a for a in runs)
    assert ssh._prepared is False
