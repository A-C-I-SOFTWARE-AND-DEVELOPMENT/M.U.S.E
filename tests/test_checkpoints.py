"""Tests for muse_cli.checkpoints — the orchestration checkpoint store.

The CLI half of the module (``register_cli`` and friends) is exercised
elsewhere; these tests focus on the :class:`CheckpointStore` and the
:class:`Checkpoint`/:class:`GitSnapshot` data classes added in Phase 08.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from muse_cli.checkpoints import (
    ApprovalState,
    Checkpoint,
    CHECKPOINT_SCHEMA_VERSION,
    CheckpointError,
    CheckpointNotFoundError,
    CheckpointPhase,
    CheckpointStore,
    GitSnapshot,
    WorkerCheckpointStatus,
    capture_git_snapshot,
)


@pytest.fixture
def store(tmp_path: Path) -> CheckpointStore:
    return CheckpointStore(root=tmp_path / ".hermes-orchestrator")


# ──────────────────────────────────────────────────────────────────────
# create_checkpoint
# ──────────────────────────────────────────────────────────────────────


class TestCreateCheckpoint:
    def test_writes_json_file(self, store: CheckpointStore):
        cp = store.create_checkpoint(
            "job-1",
            CheckpointPhase.PRE_IMPLEMENTATION,
            job_state="planning",
            workers=[WorkerCheckpointStatus(
                worker_id="w1", role="builder", status="pending",
            )],
        )
        path = store.job_dir("job-1") / f"{cp.checkpoint_id}.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["version"] == CHECKPOINT_SCHEMA_VERSION
        assert data["job_id"] == "job-1"
        assert data["phase"] == CheckpointPhase.PRE_IMPLEMENTATION
        assert data["job_state"] == "planning"
        assert data["workers"][0]["worker_id"] == "w1"

    def test_checkpoint_id_includes_phase(self, store: CheckpointStore):
        cp = store.create_checkpoint("j", CheckpointPhase.PRE_VALIDATION)
        assert CheckpointPhase.PRE_VALIDATION in cp.checkpoint_id

    def test_rejects_unknown_phase(self, store: CheckpointStore):
        with pytest.raises(CheckpointError, match="phase must be one of"):
            store.create_checkpoint("j", "post_publish")

    def test_rejects_unknown_approval_state(self, store: CheckpointStore):
        with pytest.raises(CheckpointError, match="approval_state must be"):
            store.create_checkpoint(
                "j", CheckpointPhase.PRE_PUBLISH, approval_state="maybe",
            )

    def test_phase_helpers(self, store: CheckpointStore):
        a = store.checkpoint_pre_implementation("j")
        b = store.checkpoint_pre_validation("j")
        c = store.checkpoint_pre_publish("j")
        assert a.phase == CheckpointPhase.PRE_IMPLEMENTATION
        assert b.phase == CheckpointPhase.PRE_VALIDATION
        assert c.phase == CheckpointPhase.PRE_PUBLISH

    def test_workers_accept_dicts(self, store: CheckpointStore):
        cp = store.create_checkpoint(
            "j", CheckpointPhase.PRE_IMPLEMENTATION,
            workers=[
                {"worker_id": "w1", "status": "running"},
                WorkerCheckpointStatus(worker_id="w2", status="pending"),
            ],
        )
        assert [w.worker_id for w in cp.workers] == ["w1", "w2"]

    def test_approval_state_preserved(self, store: CheckpointStore):
        cp = store.create_checkpoint(
            "j", CheckpointPhase.PRE_PUBLISH,
            approval_state=ApprovalState.PENDING,
            approval_note="waiting for user",
        )
        assert cp.approval_state == ApprovalState.PENDING
        assert cp.approval_note == "waiting for user"

    def test_git_snapshot_optional(self, store: CheckpointStore):
        # Without repo_root and no explicit git=, snapshot is empty.
        cp = store.create_checkpoint("j", CheckpointPhase.PRE_IMPLEMENTATION)
        assert cp.git.branch == ""
        assert cp.git.dirty is False


# ──────────────────────────────────────────────────────────────────────
# list / load / latest
# ──────────────────────────────────────────────────────────────────────


class TestListAndLoad:
    def test_list_empty_for_unknown_job(self, store: CheckpointStore):
        assert store.list_checkpoints("nope") == []

    def test_list_sorted_by_time(self, store: CheckpointStore):
        a = store.create_checkpoint("j", CheckpointPhase.PRE_IMPLEMENTATION)
        b = store.create_checkpoint("j", CheckpointPhase.PRE_VALIDATION)
        c = store.create_checkpoint("j", CheckpointPhase.PRE_PUBLISH)
        ids = [cp.checkpoint_id for cp in store.list_checkpoints("j")]
        assert ids == [a.checkpoint_id, b.checkpoint_id, c.checkpoint_id]

    def test_load_round_trip(self, store: CheckpointStore):
        cp = store.create_checkpoint(
            "j", CheckpointPhase.PRE_VALIDATION,
            job_state="workers_complete",
            note="all green",
        )
        loaded = store.load_checkpoint("j", cp.checkpoint_id)
        assert loaded.checkpoint_id == cp.checkpoint_id
        assert loaded.job_state == "workers_complete"
        assert loaded.note == "all green"

    def test_load_missing_raises(self, store: CheckpointStore):
        with pytest.raises(CheckpointNotFoundError):
            store.load_checkpoint("j", "nope")

    def test_corrupt_file_is_skipped_in_list(self, store: CheckpointStore):
        store.create_checkpoint("j", CheckpointPhase.PRE_IMPLEMENTATION)
        bad = store.job_dir("j") / "bad.json"
        bad.write_text("{not json")
        # Should not raise; bad file is skipped.
        out = store.list_checkpoints("j")
        assert len(out) == 1

    def test_corrupt_file_load_raises(self, store: CheckpointStore):
        store.job_dir("j").mkdir(parents=True)
        (store.job_dir("j") / "bad.json").write_text("{not json")
        with pytest.raises(CheckpointError, match="corrupt"):
            store.load_checkpoint("j", "bad")

    def test_latest_returns_most_recent(self, store: CheckpointStore):
        store.create_checkpoint("j", CheckpointPhase.PRE_IMPLEMENTATION)
        b = store.create_checkpoint("j", CheckpointPhase.PRE_VALIDATION)
        assert store.latest("j").checkpoint_id == b.checkpoint_id  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture

    def test_latest_none_for_unknown(self, store: CheckpointStore):
        assert store.latest("nope") is None

    def test_latest_for_phase(self, store: CheckpointStore):
        a = store.create_checkpoint("j", CheckpointPhase.PRE_VALIDATION)
        store.create_checkpoint("j", CheckpointPhase.PRE_PUBLISH)
        b = store.create_checkpoint("j", CheckpointPhase.PRE_VALIDATION)
        out = store.latest_for_phase("j", CheckpointPhase.PRE_VALIDATION)
        assert out.checkpoint_id == b.checkpoint_id  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        # 'a' was older — confirm we picked the newer.
        assert out.created_at >= a.created_at  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture


# ──────────────────────────────────────────────────────────────────────
# latest_safe_phase
# ──────────────────────────────────────────────────────────────────────


class TestSafePhase:
    def test_none_when_no_checkpoints(self, store: CheckpointStore):
        assert store.latest_safe_phase("nope") is None

    def test_pre_impl_only(self, store: CheckpointStore):
        store.create_checkpoint("j", CheckpointPhase.PRE_IMPLEMENTATION)
        assert store.latest_safe_phase("j") == CheckpointPhase.PRE_IMPLEMENTATION

    def test_advances_through_phases(self, store: CheckpointStore):
        store.create_checkpoint("j", CheckpointPhase.PRE_IMPLEMENTATION)
        assert store.latest_safe_phase("j") == CheckpointPhase.PRE_IMPLEMENTATION
        store.create_checkpoint("j", CheckpointPhase.PRE_VALIDATION)
        assert store.latest_safe_phase("j") == CheckpointPhase.PRE_VALIDATION
        store.create_checkpoint("j", CheckpointPhase.PRE_PUBLISH)
        assert store.latest_safe_phase("j") == CheckpointPhase.PRE_PUBLISH

    def test_picks_highest_phase_regardless_of_timing(
        self, store: CheckpointStore
    ):
        # Even if pre_validation is taken *after* pre_publish (weird but
        # not impossible if recovery retries the validation gate), the
        # "safe phase" is the highest phase observed.
        store.create_checkpoint("j", CheckpointPhase.PRE_PUBLISH)
        store.create_checkpoint("j", CheckpointPhase.PRE_VALIDATION)
        assert store.latest_safe_phase("j") == CheckpointPhase.PRE_PUBLISH


# ──────────────────────────────────────────────────────────────────────
# clear / list_jobs
# ──────────────────────────────────────────────────────────────────────


class TestClearAndListJobs:
    def test_clear_job(self, store: CheckpointStore):
        store.create_checkpoint("j", CheckpointPhase.PRE_IMPLEMENTATION)
        store.create_checkpoint("j", CheckpointPhase.PRE_VALIDATION)
        n = store.clear_job("j")
        assert n == 2
        assert store.list_checkpoints("j") == []

    def test_clear_unknown_job_returns_zero(self, store: CheckpointStore):
        assert store.clear_job("nope") == 0

    def test_list_jobs(self, store: CheckpointStore):
        store.create_checkpoint("a", CheckpointPhase.PRE_IMPLEMENTATION)
        store.create_checkpoint("b", CheckpointPhase.PRE_VALIDATION)
        assert store.list_jobs() == ["a", "b"]

    def test_list_jobs_empty_when_no_base(self, store: CheckpointStore):
        assert store.list_jobs() == []


# ──────────────────────────────────────────────────────────────────────
# capture_git_snapshot
# ──────────────────────────────────────────────────────────────────────


def _has_git() -> bool:
    try:
        return subprocess.run(
            ["git", "--version"], capture_output=True, check=False
        ).returncode == 0
    except OSError:
        return False


class TestGitSnapshot:
    def test_non_repo_returns_empty(self, tmp_path: Path):
        snap = capture_git_snapshot(tmp_path)
        assert isinstance(snap, GitSnapshot)
        assert snap.branch == ""
        assert snap.dirty is False

    def test_missing_path_returns_empty(self, tmp_path: Path):
        snap = capture_git_snapshot(tmp_path / "ghost")
        assert snap.branch == ""

    @pytest.mark.skipif(not _has_git(), reason="git not available")
    def test_real_repo(self, tmp_path: Path):
        repo = tmp_path / "repo"
        repo.mkdir()
        # Minimal init with a deterministic identity. We disable GPG /
        # commit signing inline because some CI environments globally
        # enable it via gitconfig.
        common = [
            "-c", "init.defaultBranch=main",
            "-c", "commit.gpgsign=false",
            "-c", "tag.gpgsign=false",
            "-c", "user.email=test@example.com",
            "-c", "user.name=Test",
        ]
        subprocess.run(
            ["git", *common, "init", "-q"],
            cwd=str(repo), check=True,
        )
        (repo / "README.md").write_text("hi\n")
        subprocess.run(
            ["git", *common, "add", "."], cwd=str(repo), check=True,
        )
        commit = subprocess.run(
            ["git", *common, "commit", "-q", "-m", "initial"],
            cwd=str(repo), capture_output=True, text=True,
        )
        if commit.returncode != 0:
            # Hostile environment (e.g. mandatory signing): skip rather
            # than fail the test — the snapshot helper itself is still
            # exercised by the non-repo tests.
            pytest.skip(f"git commit unavailable in this env: {commit.stderr.strip()}")
        # Modify so the working tree is dirty.
        (repo / "README.md").write_text("hi\nchanged\n")

        snap = capture_git_snapshot(repo)
        assert snap.branch in ("main", "master")
        assert len(snap.head) == 40
        assert snap.dirty is True
        assert "README.md" in snap.status
        assert "README.md" in snap.diff_stat
