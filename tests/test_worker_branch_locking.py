"""Tests for worker branch leases (muse_cli.jarvis_prime.worker_locks)
and the single-editor-per-branch policy enforced via worker_registry.

The core invariant: Claude Code and Codex must never edit the same branch
at the same time. ``locks_dir`` and ``now`` are injected so the tests are
hermetic and deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from muse_cli.jarvis_prime import worker_locks as wl
from muse_cli.jarvis_prime import worker_registry as wr


@pytest.fixture()
def locks(tmp_path: Path) -> Path:
    return tmp_path / "locks"


# ---------------------------------------------------------------------------
# basic acquire / release
# ---------------------------------------------------------------------------


def test_acquire_creates_lease(locks: Path) -> None:
    lease = wl.acquire_branch_lease("feature/x", "claude", locks_dir=locks)
    assert lease.worker == "claude"
    assert lease.branch == "feature/x"
    assert wl.is_branch_locked("feature/x", locks_dir=locks) is True


def test_release_frees_branch(locks: Path) -> None:
    wl.acquire_branch_lease("feature/x", "claude", locks_dir=locks)
    assert wl.release_branch_lease("feature/x", "claude", locks_dir=locks) is True
    assert wl.is_branch_locked("feature/x", locks_dir=locks) is False


# ---------------------------------------------------------------------------
# the load-bearing rule: two workers can't hold the same branch
# ---------------------------------------------------------------------------


def test_second_worker_blocked_on_same_branch(locks: Path) -> None:
    wl.acquire_branch_lease("feature/x", "claude", locks_dir=locks)
    with pytest.raises(wl.BranchLockedError):
        wl.acquire_branch_lease("feature/x", "codex", locks_dir=locks)


def test_same_worker_reacquire_refreshes(locks: Path) -> None:
    t = [1000.0]
    first = wl.acquire_branch_lease("feature/x", "claude", locks_dir=locks, now=lambda: t[0])
    t[0] = 1500.0
    second = wl.acquire_branch_lease("feature/x", "claude", locks_dir=locks, now=lambda: t[0])
    assert second.expires_at > first.expires_at


def test_different_branches_do_not_conflict(locks: Path) -> None:
    wl.acquire_branch_lease("feature/a", "claude", locks_dir=locks)
    # codex on a different branch is fine.
    lease = wl.acquire_branch_lease("feature/b", "codex", locks_dir=locks)
    assert lease.worker == "codex"


# ---------------------------------------------------------------------------
# expired leases are stealable (crashed worker self-heals)
# ---------------------------------------------------------------------------


def test_expired_lease_can_be_stolen(locks: Path) -> None:
    t = [1000.0]
    wl.acquire_branch_lease(
        "feature/x", "claude", locks_dir=locks, ttl_seconds=10, now=lambda: t[0]
    )
    t[0] = 2000.0  # well past the 10s TTL
    assert wl.is_branch_locked("feature/x", locks_dir=locks, now=t[0]) is False
    lease = wl.acquire_branch_lease(
        "feature/x", "codex", locks_dir=locks, now=lambda: t[0]
    )
    assert lease.worker == "codex"


def test_own_lease_does_not_block_self(locks: Path) -> None:
    wl.acquire_branch_lease("feature/x", "claude", locks_dir=locks)
    assert wl.is_branch_locked("feature/x", worker="claude", locks_dir=locks) is False
    assert wl.is_branch_locked("feature/x", worker="codex", locks_dir=locks) is True


# ---------------------------------------------------------------------------
# lease file hygiene
# ---------------------------------------------------------------------------


def test_lease_file_has_owner_only_perms(locks: Path) -> None:
    import os
    import stat

    wl.acquire_branch_lease("feature/x", "claude", locks_dir=locks)
    path = next(locks.glob("*.lock"))
    mode = stat.S_IMODE(os.stat(path).st_mode)
    # Best-effort 0o600 (skipped on platforms that can't chmod).
    if os.name == "posix":
        assert mode == 0o600


def test_branch_name_sanitized_to_single_file(locks: Path) -> None:
    wl.acquire_branch_lease("feature/with/slashes", "claude", locks_dir=locks)
    files = list(locks.glob("*.lock"))
    assert len(files) == 1
    assert "/" not in files[0].name


def test_clear_all_leases(locks: Path) -> None:
    wl.acquire_branch_lease("a", "claude", locks_dir=locks)
    wl.acquire_branch_lease("b", "codex", locks_dir=locks)
    assert wl.clear_all_leases(locks_dir=locks) == 2
    assert wl.list_leases(locks_dir=locks) == []


# ---------------------------------------------------------------------------
# registry-level brokering
# ---------------------------------------------------------------------------


def test_reviewer_lane_takes_no_edit_lease(locks: Path) -> None:
    # Reviewer reads the builder's output; it must not take an edit lease.
    result = wr.acquire_branch_for_lane("codex_reviewer", "feature/x", locks_dir=locks)
    assert result is None
    assert wl.is_branch_locked("feature/x", locks_dir=locks) is False


def test_builder_then_codex_fix_conflict_on_same_branch(locks: Path) -> None:
    # Builder (claude) holds the branch; a Codex bounded-fix on the SAME
    # branch must be refused — no concurrent editing.
    wr.acquire_branch_for_lane("claude_code_builder", "feature/x", locks_dir=locks)
    with pytest.raises(wl.BranchLockedError):
        wr.acquire_branch_for_lane("codex_bounded_fix", "feature/x", locks_dir=locks)


def test_release_for_lane_then_other_lane_can_acquire(locks: Path) -> None:
    wr.acquire_branch_for_lane("claude_code_builder", "feature/x", locks_dir=locks)
    assert wr.release_branch_for_lane("claude_code_builder", "feature/x", locks_dir=locks) is True
    # Now the codex fix lane can take the branch.
    lease = wr.acquire_branch_for_lane("codex_bounded_fix", "feature/x", locks_dir=locks)
    assert lease is not None and lease.worker == "codex"
