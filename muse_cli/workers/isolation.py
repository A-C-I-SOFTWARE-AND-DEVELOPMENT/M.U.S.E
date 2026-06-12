"""Isolated multi-agent spawning for Hermes workers.

This module turns a single Hermes job into a fleet of *isolated agent
instances*. Each instance gets its own on-disk envelope — folder,
prompt, logs, state, sidecar metadata, and (optionally) a dedicated
git worktree — so two agents working on the same job can never trip
over each other's files.

The module is deliberately narrow:

* It only writes under ``<repo>/.hermes-orchestrator/agents/``. Nothing
  outside that subtree is touched.
* It never executes an external command on its own. ``prepare`` builds
  the envelope; ``run`` (on a :class:`WorkerAdapter`) is what the
  orchestrator chooses to call inside the envelope. This module's job
  is to give that call a safe place to land.
* It never deletes a workspace, worktree, or branch without an
  explicit ``confirm=True`` flag.

Layout::

    <repo>/.hermes-orchestrator/agents/
    └── <job-id>/
        └── <worker-id>/
            └── <instance-id>/
                ├── prompt.md       # whatever ``write_prompt`` was given
                ├── state.json      # arbitrary per-instance state
                ├── stdout.log      # append-only run logs
                ├── stderr.log
                └── instance.json   # sidecar metadata

When ``use_worktree=True`` the workspace is also paired with a
``worktrees.WorktreeInfo`` whose branch is
``hermes/<job-id>/<worker-id>-<instance-id>`` — distinct per instance
so multiple parallel runs of the same worker don't collide on a
branch name. The worktree itself lives under the existing
``.hermes-orchestrator/worktrees/`` tree so all orchestrator state
stays in one auditable location.

The :class:`IsolatedSpawner` convenience class wraps these primitives
for the common case: a single job that wants to spawn several
:class:`WorkerAdapter` runs side-by-side and collect their results.
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Iterable, Iterator, Literal, Mapping, Optional

from muse_cli import worktrees as wt
from muse_cli.workers.base import (
    WorkerAdapter,
    WorkerArtifacts,
    WorkerPrompt,
    WorkerRunResult,
    WorkerScore,
)

# ── public constants ──────────────────────────────────────────────────

AGENTS_SUBDIR = "agents"
"""Subdirectory of ``.hermes-orchestrator/`` we own."""

PROMPT_FILENAME = "prompt.md"
STATE_FILENAME = "state.json"
STDOUT_LOG_FILENAME = "stdout.log"
STDERR_LOG_FILENAME = "stderr.log"
METADATA_FILENAME = "instance.json"

LogKind = Literal["stdout", "stderr"]


class IsolationError(RuntimeError):
    """Raised for any isolation precondition or filesystem failure."""


# ── id + path helpers ────────────────────────────────────────────────


def new_instance_id(prefix: str = "i") -> str:
    """Return a fresh per-instance identifier.

    Format: ``<prefix>-<UTC timestamp>-<4 hex chars>`` — sortable by
    creation time and unique enough for the spawn rate we expect
    (a handful per job). The random suffix avoids collisions when
    two spawners on the same machine pick the same millisecond.
    """

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    rand = secrets.token_hex(2)
    cleaned_prefix = wt.sanitize_segment(prefix or "i", field_name="instance prefix")
    return f"{cleaned_prefix}-{stamp}-{rand}"


def agents_root(repo: Path) -> Path:
    """Root directory we write under for all isolated agent instances."""

    return wt.orchestrator_root(Path(repo)) / AGENTS_SUBDIR


def workspace_path(
    repo: Path, job_id: str, worker_id: str, instance_id: str
) -> Path:
    """Return the canonical on-disk path for an instance's workspace.

    Does not touch the filesystem. All three identifier segments are
    sanitized to the safe charset enforced by :mod:`muse_cli.worktrees`
    so callers can't escape the agents directory via ``../``.
    """

    job = wt.sanitize_segment(job_id, field_name="job_id")
    worker = wt.sanitize_segment(worker_id, field_name="worker_id")
    instance = wt.sanitize_segment(instance_id, field_name="instance_id")
    return agents_root(Path(repo)) / job / worker / instance


# ── workspace record ─────────────────────────────────────────────────


@dataclass(frozen=True)
class IsolatedWorkspace:
    """One on-disk isolated agent envelope.

    The dataclass is immutable so callers can pass it around without
    worrying about a downstream mutation moving the prompt or state
    paths out from under them. To "update" a workspace, write through
    one of the module-level helpers (``write_prompt``, ``write_state``,
    ``append_log``) — they operate on the paths recorded here.
    """

    job_id: str
    worker_id: str
    instance_id: str
    root: Path
    prompt_path: Path
    state_path: Path
    stdout_log: Path
    stderr_log: Path
    metadata_path: Path
    created_at: str
    worktree: Optional[wt.WorktreeInfo] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data = {
            "job_id": self.job_id,
            "worker_id": self.worker_id,
            "instance_id": self.instance_id,
            "root": str(self.root),
            "prompt_path": str(self.prompt_path),
            "state_path": str(self.state_path),
            "stdout_log": str(self.stdout_log),
            "stderr_log": str(self.stderr_log),
            "metadata_path": str(self.metadata_path),
            "created_at": self.created_at,
            "worktree": self.worktree.as_dict() if self.worktree else None,
            "metadata": dict(self.metadata),
        }
        return data

    def worktree_branch(self) -> Optional[str]:
        return self.worktree.branch if self.worktree else None

    def working_dir(self) -> Path:
        """``cwd`` an orchestrator should hand to the worker.

        When a worktree is attached, the worker runs inside it; otherwise
        the envelope folder itself is used so logs and state stay
        close to whatever the agent produces.
        """

        if self.worktree is not None:
            return self.worktree.path
        return self.root


# ── workspace lifecycle ──────────────────────────────────────────────


def _worker_branch_id(worker_id: str, instance_id: str) -> str:
    """Build the per-instance ``worker_id`` segment used for worktrees.

    ``worktrees.create_worktree`` keys its branch + path layout off
    ``(job_id, worker_id)``. Multiple instances of the same worker
    inside one job need distinct branches, so we splice the instance
    id into the worker segment before handing it down.
    """

    base = wt.sanitize_segment(worker_id, field_name="worker_id")
    suffix = wt.sanitize_segment(instance_id, field_name="instance_id")
    return f"{base}-{suffix}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def prepare_workspace(
    repo: Path,
    *,
    job_id: str,
    worker_id: str,
    instance_id: Optional[str] = None,
    prompt: Optional[str] = None,
    state: Optional[Mapping[str, Any]] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    use_worktree: bool = False,
    base_ref: Optional[str] = None,
    allow_dirty: bool = False,
) -> IsolatedWorkspace:
    """Materialise an isolated envelope for one agent instance.

    Creates ``<repo>/.hermes-orchestrator/agents/<job>/<worker>/<instance>/``
    plus empty ``prompt.md``, ``state.json``, ``stdout.log``,
    ``stderr.log`` and a populated ``instance.json`` sidecar. When
    ``prompt`` or ``state`` are passed they're written immediately.

    When ``use_worktree=True`` a fresh ``git worktree`` is also
    created via :func:`muse_cli.worktrees.create_worktree`. The
    branch is ``hermes/<job_id>/<worker_id>-<instance_id>`` so two
    instances of the same worker on the same job never collide.

    Raises :class:`IsolationError` when the target path already exists,
    when ``use_worktree`` is requested outside a git repo, or when the
    worktree subsystem refuses (dirty repo, branch collision, unknown
    base ref, ...). The latter is re-raised as :class:`IsolationError`
    so callers only need to catch one exception type.
    """

    repo_path = Path(repo).resolve()
    if not repo_path.exists():
        raise IsolationError(f"repo path does not exist: {repo_path}")

    iid = instance_id or new_instance_id()
    target = workspace_path(repo_path, job_id, worker_id, iid)
    if target.exists():
        raise IsolationError(f"workspace already exists: {target}")

    info: Optional[wt.WorktreeInfo] = None
    if use_worktree:
        try:
            info = wt.create_worktree(
                repo_path,
                job_id=job_id,
                worker_id=_worker_branch_id(worker_id, iid),
                base_ref=base_ref,
                allow_dirty=allow_dirty,
                extra_metadata={
                    "instance_id": iid,
                    "worker_id": worker_id,
                    "purpose": "isolated-agent-spawn",
                },
            )
        except wt.WorktreeError as exc:
            raise IsolationError(f"worktree setup failed: {exc}") from exc

    target.mkdir(parents=True, exist_ok=False)

    prompt_path = target / PROMPT_FILENAME
    state_path = target / STATE_FILENAME
    stdout_log = target / STDOUT_LOG_FILENAME
    stderr_log = target / STDERR_LOG_FILENAME
    meta_path = target / METADATA_FILENAME

    prompt_path.write_text(prompt or "", encoding="utf-8")
    state_path.write_text(
        json.dumps(dict(state or {}), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    stdout_log.touch()
    stderr_log.touch()

    workspace = IsolatedWorkspace(
        job_id=str(job_id),
        worker_id=str(worker_id),
        instance_id=iid,
        root=target,
        prompt_path=prompt_path,
        state_path=state_path,
        stdout_log=stdout_log,
        stderr_log=stderr_log,
        metadata_path=meta_path,
        created_at=_now_iso(),
        worktree=info,
        metadata=dict(metadata or {}),
    )
    _write_metadata(workspace)
    return workspace


def _write_metadata(workspace: IsolatedWorkspace) -> None:
    payload = json.dumps(workspace.as_dict(), indent=2, sort_keys=True) + "\n"
    workspace.metadata_path.write_text(payload, encoding="utf-8")


def read_metadata(
    repo: Path, job_id: str, worker_id: str, instance_id: str
) -> IsolatedWorkspace:
    """Hydrate an :class:`IsolatedWorkspace` from its sidecar metadata."""

    meta_path = (
        workspace_path(repo, job_id, worker_id, instance_id) / METADATA_FILENAME
    )
    if not meta_path.exists():
        raise IsolationError(f"no instance metadata at {meta_path}")
    return _workspace_from_metadata_path(meta_path)


def _workspace_from_metadata_path(meta_path: Path) -> IsolatedWorkspace:
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    wt_data = data.get("worktree")
    info: Optional[wt.WorktreeInfo] = None
    if wt_data:
        info = wt.WorktreeInfo(
            job_id=str(wt_data["job_id"]),
            worker_id=str(wt_data["worker_id"]),
            path=Path(str(wt_data["path"])),
            branch=str(wt_data["branch"]),
            base_ref=str(wt_data["base_ref"]),
            created_at=str(wt_data["created_at"]),
            metadata=dict(wt_data.get("metadata") or {}),
        )
    return IsolatedWorkspace(
        job_id=str(data["job_id"]),
        worker_id=str(data["worker_id"]),
        instance_id=str(data["instance_id"]),
        root=Path(str(data["root"])),
        prompt_path=Path(str(data["prompt_path"])),
        state_path=Path(str(data["state_path"])),
        stdout_log=Path(str(data["stdout_log"])),
        stderr_log=Path(str(data["stderr_log"])),
        metadata_path=Path(str(data["metadata_path"])),
        created_at=str(data["created_at"]),
        worktree=info,
        metadata=dict(data.get("metadata") or {}),
    )


# ── per-workspace IO ─────────────────────────────────────────────────


def write_prompt(workspace: IsolatedWorkspace, prompt: str) -> Path:
    """Replace ``prompt.md`` for an instance and return its path."""

    workspace.prompt_path.write_text(prompt, encoding="utf-8")
    return workspace.prompt_path


def read_prompt(workspace: IsolatedWorkspace) -> str:
    return workspace.prompt_path.read_text(encoding="utf-8")


def write_state(workspace: IsolatedWorkspace, state: Mapping[str, Any]) -> Path:
    """Atomically replace ``state.json`` for an instance.

    Uses a sibling ``.tmp`` file + ``os.replace`` so a concurrent reader
    never observes a half-written file.
    """

    target = workspace.state_path
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(dict(state), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, target)
    return target


def read_state(workspace: IsolatedWorkspace) -> dict[str, Any]:
    raw = workspace.state_path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    return dict(json.loads(raw))


def append_log(
    workspace: IsolatedWorkspace, kind: LogKind, text: str
) -> Path:
    """Append ``text`` to the instance's ``stdout`` / ``stderr`` log.

    Ensures the line terminator is present so consumers parsing the log
    line-by-line never observe a half-line trailing entry.
    """

    if kind == "stdout":
        target = workspace.stdout_log
    elif kind == "stderr":
        target = workspace.stderr_log
    else:
        raise IsolationError(
            f"unknown log kind {kind!r}; expected 'stdout' or 'stderr'"
        )
    payload = text if text.endswith("\n") else text + "\n"
    with target.open("a", encoding="utf-8") as fh:
        fh.write(payload)
    return target


# ── enumeration ──────────────────────────────────────────────────────


def list_workspaces(
    repo: Path,
    *,
    job_id: Optional[str] = None,
    worker_id: Optional[str] = None,
) -> list[IsolatedWorkspace]:
    """Enumerate every isolated workspace under ``repo``.

    ``job_id`` and ``worker_id`` are optional filters; both are
    sanitized the same way ``prepare_workspace`` does so callers can
    pass user input directly. Workspaces whose sidecar is missing or
    malformed are silently skipped — this is a best-effort discovery
    function, not a consistency check.
    """

    root = agents_root(Path(repo))
    if not root.exists():
        return []
    found: list[IsolatedWorkspace] = []

    def _iter_dirs(parent: Path) -> Iterator[Path]:
        try:
            yield from sorted(p for p in parent.iterdir() if p.is_dir())
        except OSError:
            return

    job_filter = (
        wt.sanitize_segment(job_id, field_name="job_id") if job_id else None
    )
    worker_filter = (
        wt.sanitize_segment(worker_id, field_name="worker_id")
        if worker_id
        else None
    )

    for job_dir in _iter_dirs(root):
        if job_filter and job_dir.name != job_filter:
            continue
        for worker_dir in _iter_dirs(job_dir):
            if worker_filter and worker_dir.name != worker_filter:
                continue
            for instance_dir in _iter_dirs(worker_dir):
                meta = instance_dir / METADATA_FILENAME
                if not meta.is_file():
                    continue
                try:
                    found.append(_workspace_from_metadata_path(meta))
                except (OSError, ValueError, KeyError):
                    continue
    return found


# ── cleanup (destructive — opt-in only) ──────────────────────────────


def cleanup_workspace(
    workspace: IsolatedWorkspace,
    *,
    confirm: bool = False,
    cleanup_worktree: bool = False,
    delete_branch: bool = False,
    repo: Optional[Path] = None,
) -> bool:
    """Remove an isolated workspace from disk.

    This is the only function in the module that deletes filesystem
    state. ``confirm=True`` is mandatory — otherwise the call is a
    no-op that returns ``False`` so a forgotten flag never silently
    discards work.

    Cleanup is layered:

    * Workspace folder + sidecar: always cleared when ``confirm=True``.
    * Attached worktree: only removed when ``cleanup_worktree=True``,
      and only via :func:`muse_cli.worktrees.cleanup_worktree` so the
      same safety checks (dirty worktree refuses to remove) apply.
    * The branch that backed the worktree: only removed when
      ``delete_branch=True`` AND ``cleanup_worktree=True``. Uses the
      non-force ``git branch -d`` form by way of the worktrees module.
    """

    if not confirm:
        return False

    removed = False

    if workspace.root.exists():
        # Walk the tree bottom-up so we drop files before their parents.
        for path in sorted(workspace.root.rglob("*"), reverse=True):
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            except OSError:
                continue
        try:
            workspace.root.rmdir()
        except OSError:
            pass
        removed = True

    # Clean up empty parent dirs so an inspector doesn't see hollow
    # job/worker shells lying around after the last instance is gone.
    for parent in (workspace.root.parent, workspace.root.parent.parent):
        if parent.exists() and not any(parent.iterdir()):
            try:
                parent.rmdir()
            except OSError:
                pass

    if cleanup_worktree and workspace.worktree is not None:
        target_repo = Path(repo).resolve() if repo else None
        if target_repo is None:
            # Fall back to the worktree's recorded path; its parent
            # chain ends at <repo>/.hermes-orchestrator/worktrees/<job>/...
            # so we can recover the repo root from it.
            try:
                target_repo = workspace.worktree.path.parents[3]
            except IndexError as exc:
                raise IsolationError(
                    "cannot infer repo path for worktree cleanup; pass repo="
                ) from exc
        try:
            wt.cleanup_worktree(
                target_repo,
                job_id=workspace.worktree.job_id,
                worker_id=workspace.worktree.worker_id,
                confirm=True,
                delete_branch=delete_branch,
            )
        except wt.WorktreeError as exc:
            raise IsolationError(f"worktree cleanup failed: {exc}") from exc

    return removed


# ── adapter-driven spawner ───────────────────────────────────────────


@dataclass(frozen=True)
class SpawnResult:
    """Pairing of an :class:`IsolatedWorkspace` with the adapter that owns it.

    Carries the prompt that was rendered into the workspace so callers
    don't have to re-read it from disk to know which payload was used.
    """

    adapter: WorkerAdapter
    workspace: IsolatedWorkspace
    prompt: WorkerPrompt


@dataclass(frozen=True)
class CollectedRun:
    """What :meth:`IsolatedSpawner.collect` produces per instance."""

    spawn: SpawnResult
    run: WorkerRunResult
    artifacts: WorkerArtifacts
    score: WorkerScore


class IsolatedSpawner:
    """Spawn and drive isolated :class:`WorkerAdapter` instances for a job.

    Typical use::

        spawner = IsolatedSpawner(repo, job_id="job-42", use_worktrees=True)
        s1 = spawner.spawn(adapter_a, job)
        s2 = spawner.spawn(adapter_b, job)
        results = spawner.collect_all([s1, s2], job)

    The spawner is intentionally thin: it composes :func:`prepare_workspace`,
    the adapter ABC, and ``read_*`` / ``write_*`` helpers. It owns no
    threads, no subprocesses, and no global state — concurrency is the
    caller's call.
    """

    def __init__(
        self,
        repo: Path,
        *,
        job_id: str,
        use_worktrees: bool = False,
        base_ref: Optional[str] = None,
        allow_dirty: bool = False,
    ) -> None:
        self._repo = Path(repo).resolve()
        self._job_id = str(job_id)
        self._use_worktrees = bool(use_worktrees)
        self._base_ref = base_ref
        self._allow_dirty = bool(allow_dirty)
        self._lock = Lock()
        self._spawned: list[SpawnResult] = []

    @property
    def repo(self) -> Path:
        return self._repo

    @property
    def job_id(self) -> str:
        return self._job_id

    def spawned(self) -> list[SpawnResult]:
        """Return a snapshot of every workspace this spawner has created."""

        with self._lock:
            return list(self._spawned)

    def spawn(
        self,
        adapter: WorkerAdapter,
        job: Any,
        *,
        instance_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        prompt_override: Optional[str] = None,
        use_worktree: Optional[bool] = None,
    ) -> SpawnResult:
        """Materialise one isolated instance for ``adapter`` on ``job``.

        Calls ``adapter.prepare_prompt(job)`` and writes the resulting
        text into the workspace. ``prompt_override`` skips that call
        when the caller already has a rendered prompt in hand (useful
        for replays / tests).

        ``use_worktree`` per-spawn overrides the spawner-wide default so
        a single job can mix worktree-isolated and folder-only
        instances when one worker needs a clean tree and another
        doesn't.
        """

        if not isinstance(adapter, WorkerAdapter):
            raise IsolationError(
                f"spawn() expected a WorkerAdapter, got {type(adapter).__name__}"
            )

        if prompt_override is None:
            prompt = adapter.prepare_prompt(job)
            if not isinstance(prompt, WorkerPrompt):
                raise IsolationError(
                    f"{type(adapter).__name__}.prepare_prompt must return a WorkerPrompt,"
                    f" got {type(prompt).__name__}"
                )
        else:
            prompt = WorkerPrompt(text=prompt_override)

        worker_id = adapter.id
        if not worker_id:
            raise IsolationError(
                f"{type(adapter).__name__} has no `id`; cannot spawn isolated instance"
            )

        wants_worktree = (
            self._use_worktrees if use_worktree is None else bool(use_worktree)
        )

        extra_metadata = {
            "adapter": type(adapter).__name__,
            "display_name": adapter.display_name,
            "prompt_role": prompt.role,
            **dict(metadata or {}),
        }

        workspace = prepare_workspace(
            self._repo,
            job_id=self._job_id,
            worker_id=worker_id,
            instance_id=instance_id,
            prompt=prompt.text,
            metadata=extra_metadata,
            use_worktree=wants_worktree,
            base_ref=self._base_ref,
            allow_dirty=self._allow_dirty,
        )

        result = SpawnResult(adapter=adapter, workspace=workspace, prompt=prompt)
        with self._lock:
            self._spawned.append(result)
        return result

    def collect(self, spawn: SpawnResult, job: Any) -> CollectedRun:
        """Run a spawned adapter end-to-end and gather its artifacts.

        The orchestrator usually wants ``run → collect → score`` in a
        single call, so this convenience does all three and records
        stdout/stderr into the workspace logs. Any string fields on
        :class:`WorkerRunResult` are persisted so they survive a
        restart.
        """

        run_result = spawn.adapter.run(job)
        if not isinstance(run_result, WorkerRunResult):
            raise IsolationError(
                f"{type(spawn.adapter).__name__}.run must return a WorkerRunResult"
            )
        if run_result.stdout:
            append_log(spawn.workspace, "stdout", run_result.stdout)
        if run_result.stderr:
            append_log(spawn.workspace, "stderr", run_result.stderr)

        artifacts = spawn.adapter.collect(job)
        if not isinstance(artifacts, WorkerArtifacts):
            raise IsolationError(
                f"{type(spawn.adapter).__name__}.collect must return WorkerArtifacts"
            )

        score = spawn.adapter.score(artifacts)
        if not isinstance(score, WorkerScore):
            raise IsolationError(
                f"{type(spawn.adapter).__name__}.score must return a WorkerScore"
            )

        write_state(
            spawn.workspace,
            {
                "ok": run_result.ok,
                "exit_code": run_result.exit_code,
                "duration_seconds": run_result.duration_seconds,
                "error": run_result.error,
                "score": score.value,
                "confidence": score.confidence,
                "files": list(artifacts.files),
                "patches": list(artifacts.patches),
                "links": list(artifacts.links),
            },
        )

        return CollectedRun(
            spawn=spawn, run=run_result, artifacts=artifacts, score=score
        )

    def collect_all(
        self, spawns: Iterable[SpawnResult], job: Any
    ) -> list[CollectedRun]:
        """Drive :meth:`collect` over a batch in submission order."""

        return [self.collect(s, job) for s in spawns]

    def cleanup(
        self,
        spawn: SpawnResult,
        *,
        confirm: bool = False,
        cleanup_worktree: bool = False,
        delete_branch: bool = False,
    ) -> bool:
        """Tear down one spawned instance — destructive, opt-in only."""

        removed = cleanup_workspace(
            spawn.workspace,
            confirm=confirm,
            cleanup_worktree=cleanup_worktree,
            delete_branch=delete_branch,
            repo=self._repo,
        )
        if removed:
            with self._lock:
                self._spawned = [s for s in self._spawned if s is not spawn]
        return removed


__all__ = [
    "AGENTS_SUBDIR",
    "CollectedRun",
    "IsolatedSpawner",
    "IsolatedWorkspace",
    "IsolationError",
    "METADATA_FILENAME",
    "PROMPT_FILENAME",
    "STATE_FILENAME",
    "STDERR_LOG_FILENAME",
    "STDOUT_LOG_FILENAME",
    "SpawnResult",
    "agents_root",
    "append_log",
    "cleanup_workspace",
    "list_workspaces",
    "new_instance_id",
    "prepare_workspace",
    "read_metadata",
    "read_prompt",
    "read_state",
    "workspace_path",
    "write_prompt",
    "write_state",
]
