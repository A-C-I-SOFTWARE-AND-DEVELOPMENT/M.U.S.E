"""Live, read-only collectors that assemble a monitor context.

These feed :mod:`hermes_cli.jarvis_prime.monitors` / ``owner_brief`` with
real local state so the daily brief reflects the actual repo instead of
reporting every source as a blind spot.

Everything here is **read-only**: the git collector runs only
``git status`` / ``rev-parse`` (no mutation), and the rest read local
JSONL stores. No network calls, no owner-gated actions. Command execution
is injectable so tests never need a real git repo or subprocess.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from hermes_cli.jarvis_prime.model_scorecard import ScorecardBook
from hermes_cli.jarvis_prime.memory_tree import MemoryTreeStore

# A runner takes a git argv (without the leading "git") and returns stdout,
# or raises/returns "" on failure. Injectable for tests.
GitRunner = Callable[[list[str]], str]


def _default_git_runner(repo_root: str) -> GitRunner:
    def run(args: list[str]) -> str:
        if not shutil.which("git"):
            raise FileNotFoundError("git not found")
        proc = subprocess.run(
            ["git", "-C", repo_root, *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "git failed")
        return proc.stdout

    return run


def collect_repo_state(
    repo_root: str = ".", *, runner: Optional[GitRunner] = None
) -> Optional[dict]:
    """Read-only git state: branch + dirty flag + changed files.

    Returns ``None`` if git state cannot be observed (→ a blind spot, which
    is the honest signal rather than a fabricated "clean").
    """

    run = runner or _default_git_runner(repo_root)
    try:
        branch = run(["rev-parse", "--abbrev-ref", "HEAD"]).strip() or "?"
        porcelain = run(["status", "--porcelain"])
    except Exception:
        return None
    changed = [line[3:].strip() for line in porcelain.splitlines() if line.strip()]
    return {
        "branch": branch,
        "dirty": bool(changed),
        "changed_files": changed,
    }


def collect_memory_contradictions(
    store_path: Optional[Path] = None, *, store: Optional[MemoryTreeStore] = None
) -> Optional[list]:
    """Open (unresolved) Memory Tree contradictions, by subject."""

    try:
        store = store or MemoryTreeStore.load(store_path)
    except Exception:
        return None
    return [r.subject for r in store.open_contradictions()]


def collect_model_failures(
    scorecard_path: Optional[Path] = None, *, book: Optional[ScorecardBook] = None
) -> Optional[list]:
    """Models with recorded test failures or repeated errors."""

    try:
        book = book or ScorecardBook.load(scorecard_path)
    except Exception:
        return None
    fails: list[str] = []
    for c in book.scorecards:
        if c.tests_failed or c.repeated_error_count:
            fails.append(
                f"{c.model}: {c.tests_failed} failed, {c.repeated_error_count} repeated"
            )
    return fails


def collect_pending_proposals(path: Optional[Path] = None) -> Optional[list]:
    """Pending self-update proposals from a JSONL book, if present.

    Returns ``None`` when no proposal store exists (blind), an empty list
    when the store exists but nothing is pending.
    """

    if path is None or not Path(path).exists():
        return None
    pending: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if rec.get("status") in ("proposed", "needs_owner_approval"):
                    pending.append(rec)
    except OSError:
        return None
    return pending


def collect_context(
    repo_root: str = ".",
    *,
    memory_store_path: Optional[Path] = None,
    scorecard_path: Optional[Path] = None,
    proposals_path: Optional[Path] = None,
    test_results: Optional[dict] = None,
    git_runner: Optional[GitRunner] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Assemble a monitor context from locally observable sources.

    Only observable sources are included; everything else is omitted on
    purpose so the corresponding monitor reports BLIND (an honest coverage
    gap) rather than a fabricated OK. ``open_prs``, ``docs``, and
    ``android`` are intentionally left to the caller / future collectors.
    """

    context: dict = {}

    repo = collect_repo_state(repo_root, runner=git_runner)
    if repo is not None:
        context["repo"] = repo

    contradictions = collect_memory_contradictions(memory_store_path)
    if contradictions is not None:
        context["open_contradictions"] = contradictions

    failures = collect_model_failures(scorecard_path)
    if failures is not None:
        context["model_failures"] = failures

    proposals = collect_pending_proposals(proposals_path)
    if proposals is not None:
        context["pending_proposals"] = proposals

    if test_results is not None:
        context["tests"] = test_results

    if extra:
        context.update(extra)

    return context
