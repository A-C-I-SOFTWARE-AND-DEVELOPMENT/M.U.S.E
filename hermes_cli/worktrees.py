"""Git worktree isolation for the Hermes parallel orchestrator.

The parallel runner can place each worker in its own ``git worktree`` so
concurrent workers do not stomp on each other's working tree. This module
is intentionally narrow:

* It never pushes, force-pushes, or rewrites history.
* It refuses to create a worktree when the repo is dirty unless the
  caller explicitly opts in.
* It never removes a worktree implicitly — ``cleanup_worktree`` must be
  called with ``confirm=True`` to actually delete state on disk.

Layout::

    <repo>/.hermes-orchestrator/worktrees/<job-id>/<worker-id>/
                                                  worktree.json     # metadata
                                                  ...working tree...

Branch naming::

    hermes/<job-id>/<worker-id>

Both segments are sanitized to a conservative ``[A-Za-z0-9_.-]`` charset
before being used in branch names or filesystem paths.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
import json
import re
import shutil
import subprocess

ORCHESTRATOR_DIRNAME = ".hermes-orchestrator"
WORKTREES_SUBDIR = "worktrees"
METADATA_SUFFIX = ".worktree.json"
BRANCH_PREFIX = "hermes"

_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class WorktreeError(RuntimeError):
    """Raised for any worktree precondition or git failure we surface."""


@dataclass(frozen=True)
class WorktreeInfo:
    """A single Hermes-managed worktree on disk."""

    job_id: str
    worker_id: str
    path: Path
    branch: str
    base_ref: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        return data


# ─── identifier helpers ───────────────────────────────────────────────


def sanitize_segment(value: str, *, field_name: str) -> str:
    """Return a filesystem/branch-safe identifier or raise.

    Allowed characters: ``[A-Za-z0-9_.-]``. Empty inputs and inputs that
    sanitize down to an empty string are rejected so callers can't pass
    e.g. ``../`` and end up writing outside the orchestrator dir.
    """

    text = (value or "").strip()
    if not text:
        raise WorktreeError(f"{field_name} is required")
    cleaned = _SAFE_RE.sub("-", text).strip("-.")
    if not cleaned:
        raise WorktreeError(f"{field_name} must contain at least one safe character")
    if len(cleaned) > 120:
        raise WorktreeError(f"{field_name} must be <= 120 characters after sanitization")
    return cleaned


def branch_name(job_id: str, worker_id: str) -> str:
    """``hermes/<job-id>/<worker-id>`` after sanitization."""

    return f"{BRANCH_PREFIX}/{sanitize_segment(job_id, field_name='job_id')}/{sanitize_segment(worker_id, field_name='worker_id')}"


def orchestrator_root(repo: Path) -> Path:
    return Path(repo) / ORCHESTRATOR_DIRNAME


def worktree_root(repo: Path) -> Path:
    return orchestrator_root(repo) / WORKTREES_SUBDIR


def worktree_path(repo: Path, job_id: str, worker_id: str) -> Path:
    """Return the on-disk path for a worker's worktree.

    Does not touch the filesystem.
    """

    job = sanitize_segment(job_id, field_name="job_id")
    worker = sanitize_segment(worker_id, field_name="worker_id")
    return worktree_root(repo) / job / worker


def metadata_path_for(repo: Path, job_id: str, worker_id: str) -> Path:
    """Sibling metadata file path for a worker's worktree.

    Lives next to the worktree dir (NOT inside it) so it doesn't show up
    as an untracked file inside the checked-out branch.
    """

    job = sanitize_segment(job_id, field_name="job_id")
    worker = sanitize_segment(worker_id, field_name="worker_id")
    return worktree_root(repo) / job / f"{worker}{METADATA_SUFFIX}"


# ─── git helpers ──────────────────────────────────────────────────────


def _run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run ``git`` inside ``repo``. Never invokes destructive commands."""

    forbidden = {"push", "reset", "clean", "rebase"}
    if args and args[0] in forbidden:
        raise WorktreeError(f"git {args[0]} is not allowed from this module")
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise WorktreeError(
            f"git {' '.join(args)} failed ({proc.returncode}): "
            f"{(proc.stderr or proc.stdout or '').strip()}"
        )
    return proc


def is_git_repo(repo: Path) -> bool:
    proc = _run_git(repo, "rev-parse", "--is-inside-work-tree", check=False)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def is_dirty(repo: Path) -> bool:
    """Return True if the worktree has uncommitted or untracked changes.

    Untracked files inside our orchestrator dir (``.hermes-orchestrator``)
    are ignored — they are orchestrator state, not user work in progress.
    """

    proc = _run_git(repo, "status", "--porcelain")
    out = proc.stdout
    if not out.strip():
        return False
    for line in out.splitlines():
        # porcelain line format: ``XY path``
        if len(line) < 3:
            continue
        path = line[3:]
        # untracked files for our own state directory don't count
        if path.startswith(ORCHESTRATOR_DIRNAME + "/") or path == ORCHESTRATOR_DIRNAME:
            continue
        return True
    return False


def _ensure_orchestrator_excluded(repo: Path) -> None:
    """Ensure ``.hermes-orchestrator/`` is in this repo's ``.git/info/exclude``.

    Writes to the repo-local exclude file (NOT ``.gitignore``) so we do
    not modify user-tracked content. Idempotent.
    """

    proc = _run_git(repo, "rev-parse", "--git-common-dir", check=False)
    if proc.returncode != 0:
        return
    git_dir = Path(proc.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = Path(repo) / git_dir
    info_dir = git_dir / "info"
    info_dir.mkdir(parents=True, exist_ok=True)
    exclude_path = info_dir / "exclude"
    line = ORCHESTRATOR_DIRNAME + "/"
    existing = ""
    if exclude_path.exists():
        existing = exclude_path.read_text(encoding="utf-8")
        for entry in existing.splitlines():
            if entry.strip() == line:
                return
    sep = "" if not existing or existing.endswith("\n") else "\n"
    exclude_path.write_text(
        existing + sep + line + "\n", encoding="utf-8"
    )


def _resolve_base_ref(repo: Path, base_ref: Optional[str]) -> str:
    """Resolve ``base_ref`` to a commit-ish that ``git`` recognizes.

    Defaults to ``HEAD`` when ``base_ref`` is not provided.
    """

    ref = (base_ref or "HEAD").strip() or "HEAD"
    proc = _run_git(repo, "rev-parse", "--verify", ref, check=False)
    if proc.returncode != 0:
        raise WorktreeError(f"base ref {ref!r} not found in repository")
    return ref


def _branch_exists(repo: Path, branch: str) -> bool:
    proc = _run_git(
        repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False
    )
    return proc.returncode == 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── metadata ─────────────────────────────────────────────────────────


def write_metadata(repo: Path, info: WorktreeInfo) -> Path:
    """Persist the worker's metadata file next to its worktree directory.

    Returns the metadata file path.
    """

    target = metadata_path_for(repo, info.job_id, info.worker_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(info.as_dict(), indent=2, sort_keys=True) + "\n"
    target.write_text(payload, encoding="utf-8")
    return target


def read_metadata(repo: Path, job_id: str, worker_id: str) -> WorktreeInfo:
    target = metadata_path_for(repo, job_id, worker_id)
    if not target.exists():
        raise WorktreeError(f"no worktree metadata at {target}")
    data = json.loads(target.read_text(encoding="utf-8"))
    return WorktreeInfo(
        job_id=str(data["job_id"]),
        worker_id=str(data["worker_id"]),
        path=Path(str(data["path"])),
        branch=str(data["branch"]),
        base_ref=str(data["base_ref"]),
        created_at=str(data["created_at"]),
        metadata=dict(data.get("metadata") or {}),
    )


# ─── lifecycle ────────────────────────────────────────────────────────


def create_worktree(
    repo: Path,
    *,
    job_id: str,
    worker_id: str,
    base_ref: Optional[str] = None,
    allow_dirty: bool = False,
    extra_metadata: Optional[dict[str, Any]] = None,
) -> WorktreeInfo:
    """Create an isolated worktree for ``worker_id`` on ``branch_name(...)``.

    * Validates that ``repo`` is a git repo.
    * Refuses to proceed if the parent worktree is dirty unless
      ``allow_dirty=True``.
    * Branches off ``base_ref`` (default ``HEAD``).
    * Writes ``worktree.json`` next to the new working tree.
    """

    repo_path = Path(repo).resolve()
    if not is_git_repo(repo_path):
        raise WorktreeError(f"{repo_path} is not a git repository")

    _ensure_orchestrator_excluded(repo_path)

    if not allow_dirty and is_dirty(repo_path):
        raise WorktreeError(
            f"repository {repo_path} has uncommitted changes; commit/stash or "
            "pass allow_dirty=True before creating a worktree"
        )

    target = worktree_path(repo_path, job_id, worker_id)
    if target.exists():
        raise WorktreeError(f"worktree path already exists: {target}")

    branch = branch_name(job_id, worker_id)
    if _branch_exists(repo_path, branch):
        raise WorktreeError(f"branch {branch!r} already exists; refusing to reuse")

    resolved_base = _resolve_base_ref(repo_path, base_ref)

    target.parent.mkdir(parents=True, exist_ok=True)

    # `git worktree add -b <branch> <path> <base>` creates the branch off
    # base_ref and checks it out in the new worktree. We avoid `-B` (force
    # reset) so an existing branch can never be silently rewound.
    _run_git(
        repo_path,
        "worktree",
        "add",
        "-b",
        branch,
        str(target),
        resolved_base,
    )

    info = WorktreeInfo(
        job_id=str(job_id),
        worker_id=str(worker_id),
        path=target,
        branch=branch,
        base_ref=resolved_base,
        created_at=_now_iso(),
        metadata=dict(extra_metadata or {}),
    )
    write_metadata(repo_path, info)
    return info


def list_worktrees(repo: Path) -> list[WorktreeInfo]:
    """Enumerate Hermes-managed worktrees by reading sidecar metadata files."""

    root = worktree_root(Path(repo))
    if not root.exists():
        return []
    found: list[WorktreeInfo] = []
    for job_dir_path in sorted(p for p in root.iterdir() if p.is_dir()):
        for meta in sorted(job_dir_path.glob(f"*{METADATA_SUFFIX}")):
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                found.append(
                    WorktreeInfo(
                        job_id=str(data["job_id"]),
                        worker_id=str(data["worker_id"]),
                        path=Path(str(data["path"])),
                        branch=str(data["branch"]),
                        base_ref=str(data["base_ref"]),
                        created_at=str(data["created_at"]),
                        metadata=dict(data.get("metadata") or {}),
                    )
                )
            except (OSError, ValueError, KeyError):
                continue
    return found


def cleanup_worktree(
    repo: Path,
    *,
    job_id: str,
    worker_id: str,
    confirm: bool = False,
    delete_branch: bool = False,
) -> bool:
    """Remove a Hermes-managed worktree.

    This is the ONLY function in this module that deletes filesystem
    state. ``confirm`` must be ``True`` — otherwise the call is a no-op
    that returns ``False``. ``delete_branch`` is also opt-in and uses
    ``git branch -d`` (the non-force form), so a branch with unmerged
    commits stays put.
    """

    if not confirm:
        return False

    repo_path = Path(repo).resolve()
    target = worktree_path(repo_path, job_id, worker_id)
    meta = metadata_path_for(repo_path, job_id, worker_id)
    if not target.exists() and not meta.exists():
        return False

    if target.exists():
        # ``git worktree remove`` refuses if the worktree is dirty; that
        # is the desired safety behavior here. Callers can pre-stash or
        # commit before retrying.
        _run_git(repo_path, "worktree", "remove", str(target))
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)

    if meta.exists():
        try:
            meta.unlink()
        except OSError:
            pass

    parent = target.parent
    if parent.exists() and not any(parent.iterdir()):
        try:
            parent.rmdir()
        except OSError:
            pass

    if delete_branch:
        branch = branch_name(job_id, worker_id)
        if _branch_exists(repo_path, branch):
            _run_git(repo_path, "branch", "-d", branch)

    return True


def iter_worktrees_for_job(repo: Path, job_id: str) -> Iterable[WorktreeInfo]:
    """Yield worktrees that belong to ``job_id``."""

    job = sanitize_segment(job_id, field_name="job_id")
    for info in list_worktrees(repo):
        if sanitize_segment(info.job_id, field_name="job_id") == job:
            yield info
