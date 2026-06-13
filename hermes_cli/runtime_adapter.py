"""Runtime adapters: *where* a worker command runs (Sprint 13, multi-host).

The worker-lease kernel (:mod:`hermes_cli.worker_lease`) decides *whether* a
worker may run and the lease store (:mod:`hermes_cli.worker_lease_store`)
records the fact + a host registry. Neither says *how* a command is actually
spawned on a given host. This module fills exactly that gap with a small,
runtime-checkable contract:

* :class:`RuntimeAdapter` — a ``@runtime_checkable`` Protocol every host
  backend satisfies: ``host_id`` / ``kind`` identify the host, ``prepare`` does
  any one-time setup, ``run`` spawns one command and returns a
  :class:`RuntimeResult`, and ``cleanup`` releases resources.
* :class:`LocalRuntimeAdapter` — a concrete, stdlib-only adapter that runs the
  command on the machine hosting Hermes via :mod:`subprocess`, streaming
  stdout/stderr to caller-chosen files. It deliberately does **not** import or
  touch the orchestrator runner (``orchestrator_parallel.py``); it is a
  standalone building block so the runner can adopt it later without a circular
  import or a behavior change to the existing local path.
* :class:`SSHRuntimeAdapter` / :class:`DockerRuntimeAdapter` — concrete,
  stdlib-only adapters that run a command on a remote host over OpenSSH or
  inside a Docker container via the ``docker`` CLI. Both shell out through
  :mod:`subprocess` (no third-party SDK), stream the remote/container
  stdout/stderr into local files (same "paths, not bytes" shape as
  :class:`LocalRuntimeAdapter`), and degrade with a clear :class:`RuntimeError`
  when the required ``ssh`` / ``docker`` binary is absent.

Design constraints (same spirit as the lease modules and
``tools/environments/base.py``):

* Stdlib-only at import time (Termux / slim-CI friendly), no network.
* Pure data carriers are frozen dataclasses; the Protocol is structural so a
  backend never has to inherit from anything.
* ``run`` writes streams to files (not in-memory) so a long, chatty worker
  can't blow up RSS — mirroring how the orchestrator already captures worker
  logs to disk. The returned :class:`RuntimeResult` carries the *paths*, never
  the bytes.

Wiring this into the runner (have ``orchestrator_parallel.ParallelRunner``
spawn LOCAL_RUN workers through a :class:`RuntimeAdapter`, and select the
adapter per ``host_id`` from the lease store's host registry) is the documented
next step — see ``docs`` / the module that owns the runner. This file is the
adapter layer + its tests only.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence, Union, runtime_checkable

__all__ = [
    "RuntimeResult",
    "RuntimeAdapter",
    "LocalRuntimeAdapter",
    "SSHRuntimeAdapter",
    "DockerRuntimeAdapter",
]

#: A command is either an argv list (preferred — no shell parsing) or a single
#: shell string. :class:`LocalRuntimeAdapter` accepts both; a list is run
#: without a shell, a string is run via the platform shell.
Command = Union[Sequence[str], str]


@dataclass(frozen=True)
class RuntimeResult:
    """Outcome of running one command on a host.

    Streams are captured to files rather than memory so a noisy worker can't
    grow the parent's RSS; the result carries the *paths* (and the realized
    duration), not the bytes. ``stdout_path`` / ``stderr_path`` may be the same
    path when the adapter merged the streams.
    """

    returncode: int
    stdout_path: Path
    stderr_path: Path
    duration: float
    #: True when the command was killed for exceeding its ``timeout``. The
    #: ``returncode`` is then adapter-defined (``LocalRuntimeAdapter`` uses
    #: ``124``, matching ``coreutils timeout`` and the existing terminal path).
    timed_out: bool = False


@runtime_checkable
class RuntimeAdapter(Protocol):
    """How a worker command is executed on one host.

    Structural (``@runtime_checkable``) so any object exposing the four members
    below satisfies it without inheriting — ``isinstance(obj, RuntimeAdapter)``
    checks that ``host_id``/``kind``/``prepare``/``run``/``cleanup`` all exist.
    (Like every ``runtime_checkable`` Protocol, the check inspects member
    *presence*, not signatures.)

    Lifecycle: ``prepare()`` once → ``run(...)`` one or more times →
    ``cleanup()`` once. Implementations must be safe to ``cleanup()`` even if
    ``prepare()`` failed or was never called.
    """

    #: Stable identifier for the host this adapter targets. Matches a
    #: ``HostRecord.host_id`` in the lease store's registry.
    host_id: str
    #: One of ``"local"`` / ``"ssh"`` / ``"docker"`` — matches
    #: ``HostRecord.kind`` so a scheduler can pick an adapter by host kind.
    kind: str

    def prepare(self) -> None:
        """Perform one-time setup (open the connection, pull the image, …).

        Idempotent: calling it twice is a no-op for adapters that are already
        prepared. May raise if the host is unreachable.
        """
        ...

    def run(self, command: Command, *, timeout: float) -> RuntimeResult:
        """Run ``command`` to completion (or ``timeout``) and return its result.

        ``timeout`` is in seconds and must be ``> 0``; a command still running
        at the deadline is killed and the result has ``timed_out=True``.
        """
        ...

    def cleanup(self) -> None:
        """Release any resources held by :meth:`prepare` (best-effort)."""
        ...


def _resolve_stream_paths(
    workdir: Path, stdout_path: Path | None, stderr_path: Path | None
) -> tuple[Path, Path]:
    """Pick concrete stdout/stderr paths, defaulting under ``workdir``."""

    out = Path(stdout_path) if stdout_path is not None else workdir / "stdout.log"
    err = Path(stderr_path) if stderr_path is not None else workdir / "stderr.log"
    return out, err


def _spawn_to_files(
    argv: Union[list[str], str],
    *,
    use_shell: bool,
    cwd: str | None,
    env: dict[str, str] | None,
    timeout: float,
    out_path: Path,
    err_path: Path,
) -> RuntimeResult:
    """Spawn a child process, stream its streams to files, honor ``timeout``.

    Shared by every adapter so the "paths, not bytes" capture, the shared-handle
    merge when stdout/stderr resolve to one path, and the timeout→``124`` /
    ``timed_out`` convention live in exactly one place. The local adapter runs
    the worker command directly; the SSH/Docker adapters pass an ``ssh`` /
    ``docker`` argv whose child *is* the local transport process — the remote
    bytes stream over the wire into these same local file handles.
    """

    out_path.parent.mkdir(parents=True, exist_ok=True)
    err_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    timed_out = False
    # Open both stream files for the lifetime of the child. When stdout and
    # stderr resolve to the same path, share one handle so interleaving is
    # preserved rather than two writers clobbering each other.
    same_target = out_path == err_path
    out_fh = open(out_path, "w", encoding="utf-8")
    err_fh = out_fh if same_target else open(err_path, "w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdout=out_fh,
            stderr=subprocess.STDOUT if same_target else err_fh,
            stdin=subprocess.DEVNULL,
            shell=use_shell,
            text=True,
        )
        try:
            returncode = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            # Reap so we don't leak a zombie; output already on disk.
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - kill stuck
                pass
            returncode = 124
    finally:
        out_fh.close()
        if not same_target:
            err_fh.close()

    duration = time.monotonic() - start
    return RuntimeResult(
        returncode=returncode,
        stdout_path=out_path,
        stderr_path=err_path,
        duration=duration,
        timed_out=timed_out,
    )


@dataclass
class LocalRuntimeAdapter:
    """Run commands on the machine hosting Hermes, via :mod:`subprocess`.

    This is the concrete ``"local"`` :class:`RuntimeAdapter`. It mirrors the
    spirit of the existing local execution path (spawn a child process, capture
    output) but is deliberately **standalone**: it does not import or modify
    ``orchestrator_parallel.py`` / ``tools/environments`` so it can be adopted
    by the runner later without a circular dependency or any change to the
    current behavior.

    Output handling: stdout and stderr are streamed to files. By default they
    land under ``workdir`` (``stdout.log`` / ``stderr.log``); pass explicit
    ``stdout_path`` / ``stderr_path`` to override. Files are opened per
    :meth:`run` call and truncated, so re-running reuses the paths cleanly.

    Timeout: a command that outlives ``timeout`` seconds is terminated and the
    result carries ``timed_out=True`` with ``returncode=124`` (matching
    ``coreutils timeout`` and Hermes' existing terminal-timeout convention).
    """

    host_id: str = "local"
    kind: str = "local"
    workdir: Path | None = None
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    #: Extra environment overlaid on the parent's ``os.environ`` for the child.
    env: dict[str, str] | None = None
    _prepared: bool = False

    def prepare(self) -> None:
        """Ensure the working directory exists. Idempotent and cheap."""

        target = self._workdir()
        target.mkdir(parents=True, exist_ok=True)
        self._prepared = True

    def _workdir(self) -> Path:
        return Path(self.workdir) if self.workdir is not None else Path.cwd()

    def _child_env(self) -> dict[str, str] | None:
        if not self.env:
            return None
        return {**os.environ, **self.env}

    def run(self, command: Command, *, timeout: float) -> RuntimeResult:
        """Spawn ``command`` locally, capturing streams to files.

        ``command`` may be an argv sequence (run without a shell — the safe
        default) or a single string (run through the platform shell). Raises
        ``ValueError`` for a non-positive ``timeout`` or an empty command.
        """

        if timeout <= 0:
            raise ValueError("timeout must be > 0")

        if not self._prepared:
            # Tolerate callers that skip prepare(); set-up is cheap and keeps
            # the adapter usable as a one-shot.
            self.prepare()

        workdir = self._workdir()
        out_path, err_path = _resolve_stream_paths(
            workdir, self.stdout_path, self.stderr_path
        )
        use_shell, argv = _normalize_command(command)

        return _spawn_to_files(
            argv,
            use_shell=use_shell,
            cwd=str(workdir),
            env=self._child_env(),
            timeout=timeout,
            out_path=out_path,
            err_path=err_path,
        )

    def cleanup(self) -> None:
        """No persistent resources to release for local execution."""

        self._prepared = False


def _normalize_command(command: Command) -> tuple[bool, Union[list[str], str]]:
    """Return ``(use_shell, argv)`` for :class:`subprocess.Popen`.

    A string is run through the shell; a non-empty sequence is run directly
    (no shell parsing). Raises ``ValueError`` on an empty command.
    """

    if isinstance(command, str):
        if not command.strip():
            raise ValueError("command string must be non-empty")
        return True, command
    argv = list(command)
    if not argv:
        raise ValueError("command sequence must be non-empty")
    return False, argv


def _command_to_str(command: Command) -> str:
    """Flatten a command into a single shell string for a remote/container run.

    An argv list is shell-quoted with :func:`_shell_join`; a string is passed
    through (it is already a shell command). Raises ``ValueError`` on empty
    input — same contract as :func:`_normalize_command`.
    """

    if isinstance(command, str):
        if not command.strip():
            raise ValueError("command string must be non-empty")
        return command
    argv = list(command)
    if not argv:
        raise ValueError("command sequence must be non-empty")
    return _shell_join(argv)


@dataclass
class SSHRuntimeAdapter:
    """Run commands on a remote host over OpenSSH, via :mod:`subprocess`.

    Concrete ``"ssh"`` :class:`RuntimeAdapter`. It shells out to the system
    ``ssh`` binary (no third-party SDK) over a multiplexed ``ControlMaster``
    socket, so the per-command handshake cost is paid once in :meth:`prepare`:

    * :meth:`prepare` checks that ``ssh`` is on ``PATH``, opens a backgrounded
      ``ControlMaster`` socket to ``[user@]host:port`` (``BatchMode=yes`` — no
      interactive prompts), and verifies the remote ``workdir`` exists. It
      raises :class:`RuntimeError` (not :class:`NotImplementedError`) if the
      binary is absent or the connection/workdir check fails, so a scheduler
      never silently falls back to local execution.
    * :meth:`run` runs the command over the shared control socket, redirecting
      the remote stdout/stderr into local files — keeping the same
      "paths, not bytes" :class:`RuntimeResult` shape as the local adapter, with
      the same timeout→``124`` / ``timed_out`` convention (via
      :func:`_spawn_to_files`). ``workdir``/``env`` are applied as a
      ``cd``/``export`` prefix on the remote command.
    * :meth:`cleanup` closes the control socket (``ssh -O exit``) and removes
      the temp socket dir. Safe to call even if :meth:`prepare` never ran.
    """

    host_id: str
    host: str
    user: str | None = None
    port: int = 22
    workdir: str | None = None
    kind: str = "ssh"
    #: Local directory for the captured stdout/stderr files (defaults to cwd).
    local_logdir: Path | None = None
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    #: Environment exported on the remote host for the command.
    env: dict[str, str] | None = None
    ssh_bin: str = "ssh"
    connect_timeout: float = 30.0
    _control_dir: str | None = None
    _control_path: str | None = None
    _prepared: bool = False

    def _target(self) -> str:
        return f"{self.user}@{self.host}" if self.user else self.host

    def prepare(self) -> None:
        if self._prepared:
            return
        if shutil.which(self.ssh_bin) is None:
            raise RuntimeError(
                f"SSHRuntimeAdapter requires the {self.ssh_bin!r} binary; "
                "it was not found on PATH."
            )
        self._control_dir = tempfile.mkdtemp(prefix="hermes-ssh-")
        self._control_path = os.path.join(self._control_dir, "cm.sock")
        master = [
            self.ssh_bin,
            "-M",
            "-S",
            self._control_path,
            "-o",
            "ControlPersist=60",
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={int(self.connect_timeout)}",
            "-p",
            str(self.port),
            "-fN",
            self._target(),
        ]
        opened = subprocess.run(
            master,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=self.connect_timeout + 10,
        )
        if opened.returncode != 0:
            self._teardown_control()
            raise RuntimeError(
                f"failed to open SSH control connection to {self._target()}: "
                f"{opened.stderr.strip() or opened.returncode}"
            )
        if self.workdir:
            check = subprocess.run(
                [
                    self.ssh_bin,
                    "-S",
                    self._control_path,
                    "-p",
                    str(self.port),
                    self._target(),
                    f"test -d {shlex.quote(self.workdir)}",
                ],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=self.connect_timeout,
            )
            if check.returncode != 0:
                self._teardown_control()
                raise RuntimeError(
                    f"remote workdir {self.workdir!r} not found on {self._target()}"
                )
        self._prepared = True

    def run(self, command: Command, *, timeout: float) -> RuntimeResult:
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        if not self._prepared:
            self.prepare()
        assert self._control_path is not None  # set by prepare()

        logdir = (
            Path(self.local_logdir) if self.local_logdir is not None else Path.cwd()
        )
        out_path, err_path = _resolve_stream_paths(
            logdir, self.stdout_path, self.stderr_path
        )

        remote = _command_to_str(command)
        if self.env:
            prefix = "".join(
                f"export {key}={shlex.quote(value)}; "
                for key, value in self.env.items()
            )
            remote = prefix + remote
        if self.workdir:
            remote = f"cd {shlex.quote(self.workdir)} && {remote}"

        argv = [
            self.ssh_bin,
            "-S",
            self._control_path,
            "-o",
            "BatchMode=yes",
            "-p",
            str(self.port),
            self._target(),
            remote,
        ]
        return _spawn_to_files(
            argv,
            use_shell=False,
            cwd=None,
            env=None,
            timeout=timeout,
            out_path=out_path,
            err_path=err_path,
        )

    def _teardown_control(self) -> None:
        if self._control_path and shutil.which(self.ssh_bin):
            try:
                subprocess.run(
                    [
                        self.ssh_bin,
                        "-S",
                        self._control_path,
                        "-O",
                        "exit",
                        "-p",
                        str(self.port),
                        self._target(),
                    ],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except (OSError, subprocess.SubprocessError):  # pragma: no cover
                pass
        if self._control_dir:
            shutil.rmtree(self._control_dir, ignore_errors=True)
        self._control_path = None
        self._control_dir = None

    def cleanup(self) -> None:
        # Safe to call even if prepare() never ran or failed mid-way.
        self._teardown_control()
        self._prepared = False


@dataclass
class DockerRuntimeAdapter:
    """Run commands inside a Docker container, via the ``docker`` CLI.

    Concrete ``"docker"`` :class:`RuntimeAdapter`. It shells out to the system
    ``docker`` binary (no SDK):

    * :meth:`prepare` checks that ``docker`` is on ``PATH``, pulls ``image`` if
      it is not already present (``docker image inspect`` → ``docker pull``),
      and starts a detached container (``sleep infinity``) optionally
      bind-mounting ``host_workspace`` at ``workdir`` so the command sees the
      repo. Raises :class:`RuntimeError` if the binary is absent or the
      pull/start fails.
    * :meth:`run` executes the command inside the container
      (``docker exec -w <workdir> ... sh -c <cmd>``), streaming container
      stdout/stderr to local files with the same :class:`RuntimeResult` shape
      and timeout convention as the local adapter (via :func:`_spawn_to_files`).
    * :meth:`cleanup` force-removes the container it created. Safe to call even
      if :meth:`prepare` never ran.
    """

    host_id: str
    image: str
    workdir: str = "/workspace"
    container_name: str | None = None
    kind: str = "docker"
    #: Host directory bind-mounted at ``workdir`` inside the container.
    host_workspace: Path | None = None
    #: Local directory for the captured stdout/stderr files (defaults to cwd).
    local_logdir: Path | None = None
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    #: Environment passed into the container for the command (``docker -e``).
    env: dict[str, str] | None = None
    docker_bin: str = "docker"
    pull_timeout: float = 300.0
    _container: str | None = None
    _prepared: bool = False

    def prepare(self) -> None:
        if self._prepared:
            return
        if shutil.which(self.docker_bin) is None:
            raise RuntimeError(
                f"DockerRuntimeAdapter requires the {self.docker_bin!r} binary; "
                "it was not found on PATH."
            )
        inspect = subprocess.run(
            [self.docker_bin, "image", "inspect", self.image],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if inspect.returncode != 0:
            pull = subprocess.run(
                [self.docker_bin, "pull", self.image],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=self.pull_timeout,
            )
            if pull.returncode != 0:
                raise RuntimeError(
                    f"failed to pull image {self.image!r}: "
                    f"{pull.stderr.strip() or pull.returncode}"
                )
        name = self.container_name or f"hermes-{self.host_id}-{uuid.uuid4().hex[:8]}"
        run_argv = [self.docker_bin, "run", "-d", "--name", name]
        if self.host_workspace is not None:
            mount = f"{Path(self.host_workspace).resolve()}:{self.workdir}"
            run_argv += ["-v", mount]
        run_argv += ["-w", self.workdir, self.image, "sleep", "infinity"]
        started = subprocess.run(
            run_argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if started.returncode != 0:
            raise RuntimeError(
                f"failed to start container from {self.image!r}: "
                f"{started.stderr.strip() or started.returncode}"
            )
        self._container = name
        self._prepared = True

    def run(self, command: Command, *, timeout: float) -> RuntimeResult:
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        if not self._prepared:
            self.prepare()
        assert self._container is not None  # set by prepare()

        logdir = (
            Path(self.local_logdir) if self.local_logdir is not None else Path.cwd()
        )
        out_path, err_path = _resolve_stream_paths(
            logdir, self.stdout_path, self.stderr_path
        )

        inner = _command_to_str(command)
        argv = [self.docker_bin, "exec"]
        if self.env:
            for key, value in self.env.items():
                argv += ["-e", f"{key}={value}"]
        argv += ["-w", self.workdir, self._container, "sh", "-c", inner]
        return _spawn_to_files(
            argv,
            use_shell=False,
            cwd=None,
            env=None,
            timeout=timeout,
            out_path=out_path,
            err_path=err_path,
        )

    def cleanup(self) -> None:
        # Safe to call even if prepare() never ran or failed mid-way.
        if self._container and shutil.which(self.docker_bin):
            try:
                subprocess.run(
                    [self.docker_bin, "rm", "-f", self._container],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except (OSError, subprocess.SubprocessError):  # pragma: no cover
                pass
        self._container = None
        self._prepared = False


def _shell_join(argv: Sequence[str]) -> str:
    """Best-effort shell quoting for argv → string.

    Used by the SSH/Docker adapters to flatten an argv command into a single
    remote/container shell string; ``shlex.join`` on 3.8+ is equivalent but this
    is explicit about quoting each token.
    """

    return " ".join(shlex.quote(token) for token in argv)
