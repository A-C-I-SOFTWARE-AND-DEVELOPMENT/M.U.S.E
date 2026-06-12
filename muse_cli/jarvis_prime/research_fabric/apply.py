"""Real, reversible git-backed apply / rollback for live auto-apply.

These make the controller's ``applier`` / ``rollback`` injection points concrete:
a candidate's change is written and committed (returning the commit sha as the
rollback handle), and rollback hard-resets the touched branch back to a prior
handle. Defense-in-depth: the applier refuses any path that escapes the repo or
matches the hard-wall protected markers, even though the controller already
blocks those (C34).

Autonomy must run on a dedicated branch/worktree (``WORKER_POLICY``); rollback
uses ``git reset --hard`` and is destructive to that branch's tip by design — it
is how "never worsens itself" is enforced after the fact.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .charter import PROTECTED_PATH_MARKERS
from .verifier import Candidate


class ApplyRefused(RuntimeError):
    """Raised when a candidate change is outside the permitted file envelope."""


def _git(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def current_head(repo_root: Path) -> str:
    return _git(Path(repo_root), "rev-parse", "HEAD")


def _safe_target(repo_root: Path, target_path: str) -> Path:
    norm = (target_path or "").replace("\\", "/")
    for marker in PROTECTED_PATH_MARKERS:
        if marker in norm:
            raise ApplyRefused(f"target matches protected marker {marker!r} (C34)")
    resolved = (repo_root / norm).resolve()
    if repo_root.resolve() not in resolved.parents and resolved != repo_root.resolve():
        raise ApplyRefused(f"target {target_path!r} escapes the repo root")
    return resolved


class GitApplier:
    """Apply a candidate's text change and commit it; return the commit sha."""

    def __init__(self, repo_root: Path, *, author: str = "jarvis-research-fabric") -> None:
        self.repo_root = Path(repo_root)
        self.author = author

    def __call__(self, candidate: Candidate) -> str:
        target = _safe_target(self.repo_root, candidate.target_path)
        if not candidate.diff_text:
            raise ApplyRefused("candidate has no diff_text to apply")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(candidate.diff_text, encoding="utf-8")
        rel = str(target.relative_to(self.repo_root.resolve()))
        _git(self.repo_root, "add", rel)
        _git(
            self.repo_root,
            "-c", f"user.name={self.author}",
            "-c", "user.email=research-fabric@local",
            "commit", "-m",
            f"auto-apply: {candidate.candidate_id} -> {rel}",
        )
        return current_head(self.repo_root)


class GitRollback:
    """Hard-reset the branch tip back to a prior handle (the prior champion)."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)

    def __call__(self, handle: str) -> None:
        if not handle:
            return
        _git(self.repo_root, "reset", "--hard", handle)


__all__ = ["ApplyRefused", "GitApplier", "GitRollback", "current_head"]
