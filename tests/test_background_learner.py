"""Tests for the safe-by-default background-learner queue scaffold."""

import pytest

from muse_cli.background_learner import Job, JobQueue, JobRejected
from muse_cli.background_learner.queue import ALLOWED_KINDS, DISALLOWED_KINDS


def test_allowed_kind_enqueues():
    q = JobQueue()
    job = q.enqueue("summarize_session", priority=10)
    assert isinstance(job, Job)
    assert job.dry_run is True
    assert q.pending() == [job]


@pytest.mark.parametrize("kind", sorted(DISALLOWED_KINDS))
def test_disallowed_kind_rejected_at_enqueue(kind):
    q = JobQueue()
    with pytest.raises(JobRejected):
        q.enqueue(kind)
    assert q.pending() == []


def test_unknown_kind_rejected():
    q = JobQueue()
    with pytest.raises(JobRejected):
        q.enqueue("do_something_weird")


def test_live_run_downgraded_to_dry_run_without_approval():
    q = JobQueue()
    job = q.enqueue("propose_code_patch", dry_run=False)
    assert job.dry_run is True  # forced back to dry-run
    assert any(e["event"] == "downgraded" for e in q.audit_log())


def test_priority_ordering():
    q = JobQueue()
    q.enqueue("summarize_session", priority=50)
    q.enqueue("index_local_files", priority=10)
    q.enqueue("update_embeddings", priority=30)
    order = [j.kind for j in q.pending()]
    assert order == ["index_local_files", "update_embeddings", "summarize_session"]


def test_cancel():
    q = JobQueue()
    job = q.enqueue("index_local_files")
    assert q.cancel(job.id) is True
    assert q.pending() == []
    assert q.cancel(9999) is False


def test_idle_gate_blocks_run():
    q = JobQueue(idle_check=lambda: False)
    q.enqueue("index_local_files")
    assert q.run_once() is None  # not idle → nothing runs
    assert len(q.pending()) == 1


def test_run_once_is_dry_run_only():
    q = JobQueue(idle_check=lambda: True)
    q.enqueue("run_local_benchmark", priority=5)
    job = q.run_once()
    assert job is not None and job.kind == "run_local_benchmark"
    assert job.dry_run is True
    assert any(e["event"] == "ran_dry" for e in q.audit_log())
    assert q.pending() == []


def test_allowed_and_disallowed_are_disjoint():
    assert ALLOWED_KINDS.isdisjoint(DISALLOWED_KINDS)
