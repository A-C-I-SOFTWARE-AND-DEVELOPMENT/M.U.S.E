"""Runtime adapters: *where* a worker command runs (Sprint 13, multi-host).

The worker-lease kernel (:mod:`muse_cli.worker_lease`) decides *whether* a
worker may run and the lease store (:mod:`muse_cli.worker_lease_store`)
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
* :class:`SSHRuntimeAdapter` / :class:`DockerRuntimeAdapter` — documented stubs
  that raise :class:`NotImplementedError`. Their docstrings describe the
  intended contract so the follow-up that wires real remote execution has a
  precise target.

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
import subprocess
import time
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
        out_path.parent.mkdir(parents=True, exist_ok=True)
        err_path.parent.mkdir(parents=True, exist_ok=True)

        use_shell, argv = _normalize_command(command)

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
                cwd=str(workdir),
                env=self._child_env(),
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


@dataclass
class SSHRuntimeAdapter:
    """Run commands on a remote host over SSH — **stub** (not yet implemented).

    Intended contract for the follow-up that adds real multi-host execution:

    * :meth:`prepare` opens (or validates) an SSH connection to
      ``host``/``user`` — most likely a multiplexed OpenSSH ``ControlMaster``
      socket or a Paramiko channel — and verifies the remote ``workdir`` exists.
    * :meth:`run` executes the command on the remote host, streaming the remote
      stdout/stderr back into local files (so :class:`RuntimeResult` keeps the
      same "paths, not bytes" shape as the local adapter), and maps the remote
      exit status onto ``returncode`` / ``timed_out``.
    * :meth:`cleanup` tears the connection / control socket down.

    Until implemented, every method raises :class:`NotImplementedError` so a
    scheduler can register an ``ssh`` host without anything silently running
    locally by mistake.
    """

    host_id: str
    host: str
    user: str | None = None
    port: int = 22
    workdir: str | None = None
    kind: str = "ssh"

    _UNIMPLEMENTED = (
        "SSHRuntimeAdapter is a Sprint 13 stub; remote SSH execution is a "
        "documented follow-up. Use LocalRuntimeAdapter for the local host."
    )

    def prepare(self) -> None:
        raise NotImplementedError(self._UNIMPLEMENTED)

    def run(self, command: Command, *, timeout: float) -> RuntimeResult:
        raise NotImplementedError(self._UNIMPLEMENTED)

    def cleanup(self) -> None:
        # Safe to call on a never-prepared stub; there is nothing to release.
        return None


@dataclass
class DockerRuntimeAdapter:
    """Run commands inside a Docker container — **stub** (not yet implemented).

    Intended contract for the follow-up:

    * :meth:`prepare` ensures the ``image`` is present (pull if missing) and
      starts (or attaches to) a container, bind-mounting the job workspace so
      the command sees the repo — mirroring how the existing Docker execution
      environment bind-mounts the host workspace.
    * :meth:`run` executes the command inside the container
      (``docker exec``-style), streaming container stdout/stderr to local files
      and surfacing the container exit code as ``returncode`` / ``timed_out``.
    * :meth:`cleanup` stops and removes the container it created.

    Until implemented, every method raises :class:`NotImplementedError`.
    """

    host_id: str
    image: str
    workdir: str = "/workspace"
    container_name: str | None = None
    kind: str = "docker"

    _UNIMPLEMENTED = (
        "DockerRuntimeAdapter is a Sprint 13 stub; container execution is a "
        "documented follow-up. Use LocalRuntimeAdapter for the local host."
    )

    def prepare(self) -> None:
        raise NotImplementedError(self._UNIMPLEMENTED)

    def run(self, command: Command, *, timeout: float) -> RuntimeResult:
        raise NotImplementedError(self._UNIMPLEMENTED)

    def cleanup(self) -> None:
        # Safe to call on a never-prepared stub; there is nothing to release.
        return None


def _shell_join(argv: Sequence[str]) -> str:
    """Best-effort shell quoting for argv → string (used by remote stubs' docs).

    Kept here so the ssh/docker follow-up has a ready helper; ``shlex.join`` on
    3.8+ is equivalent but this is explicit about quoting each token.
    """

    return " ".join(shlex.quote(token) for token in argv)
