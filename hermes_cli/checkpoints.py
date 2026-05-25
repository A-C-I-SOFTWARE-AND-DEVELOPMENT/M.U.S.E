"""`hermes checkpoints` CLI subcommand and orchestration checkpoint store.

This module wears two hats:

1. **CLI** for the filesystem checkpoint store at
   ``~/.hermes/checkpoints/`` (the rollback-history store used by
   ``/rollback``). The user-facing surface is the ``hermes
   checkpoints …`` subcommand tree::

       hermes checkpoints               # same as `status`
       hermes checkpoints status        # total size, project count, breakdown
       hermes checkpoints list          # per-project checkpoint counts + workdir
       hermes checkpoints prune [opts]  # force a sweep (ignores the 24h marker)
       hermes checkpoints clear [-f]    # nuke the entire base (asks first)
       hermes checkpoints clear-legacy  # delete just the legacy-* archives

   Examples::

       hermes checkpoints
       hermes checkpoints prune --retention-days 3 --max-size-mb 200
       hermes checkpoints clear -f

2. **Orchestration checkpoint store** — small JSON snapshots taken at
   the three safe points in the orchestrator pipeline:

   - ``pre_implementation`` — workers about to write code
   - ``pre_validation``     — implementation done, validators about to run
   - ``pre_publish``        — validators passed, about to push/PR

   Each checkpoint captures the job's phase, the workers' statuses,
   the approval state, and a snapshot of git (branch / status / diff
   stat) so a later recovery can resume from the last safe phase
   without re-running already-completed work. The store lives
   alongside ``queue.json`` at ``<root>/checkpoints/<job-id>/``.

None of the CLI bits require the agent to be running. Safe to call
any time.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

logger = logging.getLogger(__name__)


def _fmt_bytes(n: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(n or 0)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _fmt_ts(ts: Any) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return "—"


def _fmt_age(ts: Any) -> str:
    try:
        age = time.time() - float(ts)
    except (TypeError, ValueError):
        return "—"
    if age < 0:
        return "now"
    if age < 60:
        return f"{int(age)}s ago"
    if age < 3600:
        return f"{int(age / 60)}m ago"
    if age < 86400:
        return f"{int(age / 3600)}h ago"
    return f"{int(age / 86400)}d ago"


def cmd_status(args: argparse.Namespace) -> int:
    from tools.checkpoint_manager import store_status

    info = store_status()
    base = info["base"]
    print(f"Checkpoint base: {base}")
    print(f"Total size:      {_fmt_bytes(info['total_size_bytes'])}")
    print(f"  store/         {_fmt_bytes(info['store_size_bytes'])}")
    print(f"  legacy-*       {_fmt_bytes(info['legacy_size_bytes'])}")
    print(f"Projects:        {info['project_count']}")

    projects = sorted(
        info["projects"],
        key=lambda p: (p.get("last_touch") or 0),
        reverse=True,
    )
    if projects:
        print()
        print(f"  {'WORKDIR':<60}  {'COMMITS':>7}  {'LAST TOUCH':>12}  STATE")
        for p in projects[: args.limit if hasattr(args, "limit") and args.limit else 20]:
            wd = p.get("workdir") or "(unknown)"
            if len(wd) > 60:
                wd = "…" + wd[-59:]
            exists = p.get("exists")
            state = "live" if exists else "orphan"
            commits = p.get("commits", 0)
            last = _fmt_age(p.get("last_touch"))
            print(f"  {wd:<60}  {commits:>7}  {last:>12}  {state}")

    legacy = info.get("legacy_archives", [])
    if legacy:
        print()
        print(f"Legacy archives ({len(legacy)}):")
        for arch in sorted(legacy, key=lambda a: a.get("mtime", 0), reverse=True):
            print(f"  {arch['name']:<40}  {_fmt_bytes(arch['size_bytes']):>10}")
        print()
        print("Clear with: hermes checkpoints clear-legacy")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    # `list` is just a terser status — already covered.
    return cmd_status(args)


def cmd_prune(args: argparse.Namespace) -> int:
    from tools.checkpoint_manager import prune_checkpoints

    retention_days = args.retention_days
    max_size_mb = args.max_size_mb

    print("Pruning checkpoint store…")
    print(f"  retention_days:    {retention_days}")
    print(f"  delete_orphans:    {not args.keep_orphans}")
    print(f"  max_total_size_mb: {max_size_mb}")
    print()

    result = prune_checkpoints(
        retention_days=retention_days,
        delete_orphans=not args.keep_orphans,
        max_total_size_mb=max_size_mb,
    )
    print(f"Scanned:         {result['scanned']}")
    print(f"Deleted orphan:  {result['deleted_orphan']}")
    print(f"Deleted stale:   {result['deleted_stale']}")
    print(f"Errors:          {result['errors']}")
    print(f"Bytes reclaimed: {_fmt_bytes(result['bytes_freed'])}")
    return 0


def _confirm(prompt: str) -> bool:
    try:
        resp = input(f"{prompt} [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return resp in {"y", "yes"}


def cmd_clear(args: argparse.Namespace) -> int:
    from tools.checkpoint_manager import CHECKPOINT_BASE, clear_all, store_status

    info = store_status()
    if info["total_size_bytes"] == 0 and not Path(CHECKPOINT_BASE).exists():
        print("Nothing to clear — checkpoint base does not exist.")
        return 0

    print(f"This will delete the ENTIRE checkpoint base at {info['base']}")
    print(f"  size:        {_fmt_bytes(info['total_size_bytes'])}")
    print(f"  projects:    {info['project_count']}")
    print(f"  legacy dirs: {len(info.get('legacy_archives', []))}")
    print()
    print("All /rollback history for every working directory will be lost.")
    if not args.force and not _confirm("Proceed?"):
        print("Aborted.")
        return 1

    result = clear_all()
    if result["deleted"]:
        print(f"Cleared. Reclaimed {_fmt_bytes(result['bytes_freed'])}.")
        return 0
    print("Could not clear checkpoint base (see logs).")
    return 2


def cmd_clear_legacy(args: argparse.Namespace) -> int:
    from tools.checkpoint_manager import clear_legacy, store_status

    info = store_status()
    legacy = info.get("legacy_archives", [])
    if not legacy:
        print("No legacy archives to clear.")
        return 0

    total = sum(a.get("size_bytes", 0) for a in legacy)
    print(f"Found {len(legacy)} legacy archive(s), total {_fmt_bytes(total)}:")
    for arch in legacy:
        print(f"  {arch['name']:<40}  {_fmt_bytes(arch['size_bytes']):>10}")
    print()
    print("Legacy archives hold pre-v2 per-project shadow repos, moved aside")
    print("during the single-store migration. Delete when you're confident")
    print("you don't need the old /rollback history.")
    if not args.force and not _confirm("Delete all legacy archives?"):
        print("Aborted.")
        return 1

    result = clear_legacy()
    print(f"Deleted {result['deleted']} archive(s), reclaimed {_fmt_bytes(result['bytes_freed'])}.")
    return 0


def register_cli(parser: argparse.ArgumentParser) -> None:
    """Wire subcommands onto the ``hermes checkpoints`` parser."""
    parser.set_defaults(func=cmd_status)  # bare `hermes checkpoints` → status
    subs = parser.add_subparsers(dest="checkpoints_command", metavar="COMMAND")

    p_status = subs.add_parser(
        "status",
        help="Show total size, project count, and per-project breakdown",
    )
    p_status.add_argument("--limit", type=int, default=20,
                          help="Max projects to list (default 20)")
    p_status.set_defaults(func=cmd_status)

    p_list = subs.add_parser(
        "list",
        help="Alias for 'status'",
    )
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=cmd_list)

    p_prune = subs.add_parser(
        "prune",
        help="Delete orphan/stale checkpoints and GC the store",
    )
    p_prune.add_argument("--retention-days", type=int, default=7,
                         help="Drop projects whose last_touch is older than N days (default 7)")
    p_prune.add_argument("--max-size-mb", type=int, default=500,
                         help="After orphan/stale prune, drop oldest commits "
                              "per project until total size <= this (default 500)")
    p_prune.add_argument("--keep-orphans", action="store_true",
                         help="Skip deleting projects whose workdir no longer exists")
    p_prune.set_defaults(func=cmd_prune)

    p_clear = subs.add_parser(
        "clear",
        help="Delete the entire checkpoint base (all /rollback history)",
    )
    p_clear.add_argument("-f", "--force", action="store_true",
                         help="Skip confirmation prompt")
    p_clear.set_defaults(func=cmd_clear)

    p_legacy = subs.add_parser(
        "clear-legacy",
        help="Delete only the legacy-<ts>/ archives from v1 migration",
    )
    p_legacy.add_argument("-f", "--force", action="store_true",
                          help="Skip confirmation prompt")
    p_legacy.set_defaults(func=cmd_clear_legacy)


# ══════════════════════════════════════════════════════════════════════
# Orchestration checkpoint store
# ══════════════════════════════════════════════════════════════════════
#
# Lives under ``<root>/checkpoints/<job-id>/<checkpoint-id>.json``. Each
# checkpoint is a self-contained snapshot — no inter-checkpoint diffing,
# no compression — because they're small (a few KB) and disk is cheap
# compared to the cost of getting recovery wrong.

CHECKPOINTS_DIRNAME = "checkpoints"
ORCHESTRATOR_ROOT_DIRNAME = ".hermes-orchestrator"

# Schema version for a single checkpoint file. Bumped on breaking
# changes only.
CHECKPOINT_SCHEMA_VERSION = 1


class CheckpointError(RuntimeError):
    """Base error for the orchestration checkpoint store."""


class CheckpointNotFoundError(CheckpointError):
    """Raised when a checkpoint or job-checkpoint folder is missing."""


class CheckpointPhase:
    """Phases at which the orchestrator takes a checkpoint.

    The order here is the order they're taken in. Recovery uses this
    order to pick "the last safe phase to resume from".
    """

    PRE_IMPLEMENTATION = "pre_implementation"
    PRE_VALIDATION = "pre_validation"
    PRE_PUBLISH = "pre_publish"

    ALL = (PRE_IMPLEMENTATION, PRE_VALIDATION, PRE_PUBLISH)


class ApprovalState:
    """Approval state stored on the checkpoint."""

    NONE = "none"            # no approval required
    PENDING = "pending"      # asked, waiting
    APPROVED = "approved"
    REJECTED = "rejected"

    ALL = frozenset({NONE, PENDING, APPROVED, REJECTED})


@dataclass
class WorkerCheckpointStatus:
    """Snapshot of one worker's status at checkpoint time."""

    worker_id: str
    role: str = ""
    target_tool: str = "manual"
    status: str = ""
    attempts: int = 0
    last_error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkerCheckpointStatus":
        return cls(
            worker_id=str(data.get("worker_id", "")),
            role=str(data.get("role", "")),
            target_tool=str(data.get("target_tool", "manual")),
            status=str(data.get("status", "")),
            attempts=int(data.get("attempts", 0) or 0),
            last_error=data.get("last_error"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GitSnapshot:
    """Minimal git state captured at checkpoint time.

    We do not bundle the full diff (potentially MB) — only the status
    output, branch, head SHA, and a numstat-style diff summary. That's
    enough for a human to confirm "yes, this matches what I had" before
    the orchestrator resumes.
    """

    branch: str = ""
    head: str = ""
    status: str = ""        # `git status --porcelain=v1` output
    diff_stat: str = ""     # `git diff --numstat` output (staged + unstaged)
    dirty: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GitSnapshot":
        return cls(
            branch=str(data.get("branch", "")),
            head=str(data.get("head", "")),
            status=str(data.get("status", "")),
            diff_stat=str(data.get("diff_stat", "")),
            dirty=bool(data.get("dirty", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Checkpoint:
    """One checkpoint snapshot."""

    checkpoint_id: str
    job_id: str
    phase: str
    created_at: float
    job_state: str = ""
    job_phase_label: str | None = None
    approval_state: str = ApprovalState.NONE
    approval_note: str | None = None
    workers: list[WorkerCheckpointStatus] = field(default_factory=list)
    git: GitSnapshot = field(default_factory=GitSnapshot)
    note: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        workers_raw: Iterable[Any] = data.get("workers") or []
        return cls(
            checkpoint_id=str(data.get("checkpoint_id", "")),
            job_id=str(data.get("job_id", "")),
            phase=str(data.get("phase", "")),
            created_at=float(data.get("created_at", 0.0) or 0.0),
            job_state=str(data.get("job_state", "")),
            job_phase_label=data.get("job_phase_label"),
            approval_state=str(data.get("approval_state", ApprovalState.NONE)),
            approval_note=data.get("approval_note"),
            workers=[
                WorkerCheckpointStatus.from_dict(w)
                for w in workers_raw
                if isinstance(w, dict)
            ],
            git=GitSnapshot.from_dict(data.get("git") or {}),
            note=data.get("note"),
            metadata=dict(data.get("metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CHECKPOINT_SCHEMA_VERSION,
            "checkpoint_id": self.checkpoint_id,
            "job_id": self.job_id,
            "phase": self.phase,
            "created_at": self.created_at,
            "job_state": self.job_state,
            "job_phase_label": self.job_phase_label,
            "approval_state": self.approval_state,
            "approval_note": self.approval_note,
            "workers": [w.to_dict() for w in self.workers],
            "git": self.git.to_dict(),
            "note": self.note,
            "metadata": dict(self.metadata),
        }


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(
        f".{path.name}.tmp.{os.getpid()}.{secrets.token_hex(3)}"
    )
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def capture_git_snapshot(repo_root: str | Path) -> GitSnapshot:
    """Capture git branch / head / status / diff-stat for ``repo_root``.

    Never raises. If the directory isn't a git repo, returns an empty
    snapshot — orchestration should still be allowed to checkpoint
    work even when git isn't involved (e.g. research jobs).
    """
    snap = GitSnapshot()
    root = Path(repo_root)
    if not root.exists() or shutil.which("git") is None:
        return snap

    def _run(args: list[str]) -> str:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return (out.stdout or "").strip()

    # `git rev-parse --is-inside-work-tree` is the canonical "is this a
    # git checkout?" probe.
    is_repo = _run(["rev-parse", "--is-inside-work-tree"])
    if is_repo != "true":
        return snap

    snap.branch = _run(["rev-parse", "--abbrev-ref", "HEAD"]) or ""
    snap.head = _run(["rev-parse", "HEAD"]) or ""
    snap.status = _run(["status", "--porcelain=v1"])
    snap.dirty = bool(snap.status.strip())
    # numstat is bounded (one line per touched file), unlike `git diff`.
    staged = _run(["diff", "--cached", "--numstat"])
    unstaged = _run(["diff", "--numstat"])
    parts = [p for p in (staged, unstaged) if p]
    snap.diff_stat = "\n".join(parts)
    return snap


class CheckpointStore:
    """Filesystem-backed orchestration checkpoint store.

    All writes are atomic. The store does not need an in-process lock
    because each checkpoint file has a unique id (timestamp + random
    suffix) — concurrent writes to the same job folder cannot collide
    on a filename.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            env_root = os.environ.get("HERMES_ORCHESTRATOR_HOME")
            root = (
                Path(env_root) if env_root
                else Path.cwd() / ORCHESTRATOR_ROOT_DIRNAME
            )
        self.root = Path(root)
        self.base = self.root / CHECKPOINTS_DIRNAME

    def job_dir(self, job_id: str) -> Path:
        if not job_id or not str(job_id).strip():
            raise CheckpointError("job_id is required")
        return self.base / str(job_id)

    @staticmethod
    def _new_checkpoint_id(phase: str) -> str:
        if phase not in CheckpointPhase.ALL:
            raise CheckpointError(
                f"phase must be one of {list(CheckpointPhase.ALL)}; "
                f"got {phase!r}"
            )
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dt%H%M%Sz")
        suffix = secrets.token_hex(3)
        return f"{stamp}-{phase}-{suffix}"

    def create_checkpoint(
        self,
        job_id: str,
        phase: str,
        *,
        repo_root: str | Path | None = None,
        job_state: str = "",
        job_phase_label: str | None = None,
        workers: Iterable[WorkerCheckpointStatus | dict[str, Any]] | None = None,
        approval_state: str = ApprovalState.NONE,
        approval_note: str | None = None,
        note: str | None = None,
        metadata: dict[str, Any] | None = None,
        git: GitSnapshot | None = None,
    ) -> Checkpoint:
        """Snapshot ``job_id`` at ``phase`` and write it to disk.

        Returns the new :class:`Checkpoint`. The ``checkpoint_id``
        embeds the phase so a stray ``ls`` in the job folder makes the
        timeline obvious.
        """
        if phase not in CheckpointPhase.ALL:
            raise CheckpointError(
                f"phase must be one of {list(CheckpointPhase.ALL)}; "
                f"got {phase!r}"
            )
        if approval_state not in ApprovalState.ALL:
            raise CheckpointError(
                f"approval_state must be one of {sorted(ApprovalState.ALL)}; "
                f"got {approval_state!r}"
            )

        worker_snaps: list[WorkerCheckpointStatus] = []
        for w in workers or []:
            if isinstance(w, WorkerCheckpointStatus):
                worker_snaps.append(w)
            elif isinstance(w, dict):
                worker_snaps.append(WorkerCheckpointStatus.from_dict(w))
            else:
                raise CheckpointError(
                    "workers must be WorkerCheckpointStatus or dict instances"
                )

        if git is None:
            git = capture_git_snapshot(repo_root) if repo_root else GitSnapshot()

        cid = self._new_checkpoint_id(phase)
        cp = Checkpoint(
            checkpoint_id=cid,
            job_id=str(job_id),
            phase=phase,
            created_at=time.time(),
            job_state=str(job_state or ""),
            job_phase_label=job_phase_label,
            approval_state=approval_state,
            approval_note=approval_note,
            workers=worker_snaps,
            git=git,
            note=note,
            metadata=dict(metadata or {}),
        )
        path = self.job_dir(job_id) / f"{cid}.json"
        _atomic_write_json(path, cp.to_dict())
        logger.info(
            "checkpoints: %s %s (phase=%s, workers=%d)",
            job_id, cid, phase, len(worker_snaps),
        )
        return cp

    # Phase-specific helpers — same as create_checkpoint, but the
    # callsite reads better when you can see *which* phase you're
    # asking for.
    def checkpoint_pre_implementation(self, job_id: str, **kw: Any) -> Checkpoint:
        return self.create_checkpoint(
            job_id, CheckpointPhase.PRE_IMPLEMENTATION, **kw
        )

    def checkpoint_pre_validation(self, job_id: str, **kw: Any) -> Checkpoint:
        return self.create_checkpoint(
            job_id, CheckpointPhase.PRE_VALIDATION, **kw
        )

    def checkpoint_pre_publish(self, job_id: str, **kw: Any) -> Checkpoint:
        return self.create_checkpoint(
            job_id, CheckpointPhase.PRE_PUBLISH, **kw
        )

    def list_checkpoints(self, job_id: str) -> list[Checkpoint]:
        """Return all checkpoints for ``job_id``, oldest-first."""
        jdir = self.job_dir(job_id)
        if not jdir.exists():
            return []
        out: list[Checkpoint] = []
        for path in sorted(jdir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning(
                    "checkpoints: skipping unreadable %s (%s)", path, exc
                )
                continue
            try:
                out.append(Checkpoint.from_dict(data))
            except Exception as exc:  # noqa: BLE001 — defensive on disk
                logger.warning(
                    "checkpoints: skipping malformed %s (%s)", path, exc
                )
        out.sort(key=lambda c: (c.created_at, c.checkpoint_id))
        return out

    def load_checkpoint(self, job_id: str, checkpoint_id: str) -> Checkpoint:
        path = self.job_dir(job_id) / f"{checkpoint_id}.json"
        if not path.exists():
            raise CheckpointNotFoundError(
                f"checkpoint not found: job={job_id} id={checkpoint_id}"
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CheckpointError(
                f"checkpoint {checkpoint_id} for {job_id} is corrupt: {exc}"
            ) from exc
        return Checkpoint.from_dict(data)

    def latest(self, job_id: str) -> Checkpoint | None:
        cps = self.list_checkpoints(job_id)
        return cps[-1] if cps else None

    def latest_for_phase(
        self, job_id: str, phase: str
    ) -> Checkpoint | None:
        if phase not in CheckpointPhase.ALL:
            raise CheckpointError(
                f"phase must be one of {list(CheckpointPhase.ALL)}; "
                f"got {phase!r}"
            )
        match: Checkpoint | None = None
        for cp in self.list_checkpoints(job_id):
            if cp.phase == phase:
                match = cp
        return match

    def latest_safe_phase(self, job_id: str) -> str | None:
        """Return the highest-progress phase we have a checkpoint for.

        Returns one of ``CheckpointPhase.ALL`` or ``None`` if no
        checkpoint has been taken yet for this job. "Safe" means the
        recovery is allowed to assume that everything *before* this
        phase already happened — but anything *after* must be re-run.
        """
        cps = self.list_checkpoints(job_id)
        if not cps:
            return None
        # Phase order is the declaration order in CheckpointPhase.ALL.
        order = {p: i for i, p in enumerate(CheckpointPhase.ALL)}
        best = -1
        for cp in cps:
            idx = order.get(cp.phase, -1)
            if idx > best:
                best = idx
        return CheckpointPhase.ALL[best] if best >= 0 else None

    def clear_job(self, job_id: str) -> int:
        """Delete every checkpoint for ``job_id``. Returns count removed."""
        jdir = self.job_dir(job_id)
        if not jdir.exists():
            return 0
        count = 0
        for path in jdir.glob("*.json"):
            try:
                path.unlink()
                count += 1
            except OSError as exc:
                logger.warning(
                    "checkpoints: could not delete %s (%s)", path, exc
                )
        try:
            jdir.rmdir()
        except OSError:
            pass  # not empty (legitimate artefacts) or already gone
        return count

    def list_jobs(self) -> list[str]:
        """Return every job_id that has at least one checkpoint."""
        if not self.base.exists():
            return []
        return sorted(
            p.name for p in self.base.iterdir()
            if p.is_dir() and any(p.glob("*.json"))
        )
