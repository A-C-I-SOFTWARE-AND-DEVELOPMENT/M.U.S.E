"""Background-learner autoresearch_train job kind — plan-only by default."""

from __future__ import annotations

from typing import Any

import pytest

from hermes_cli.background_learner.queue import ALLOWED_KINDS, JobQueue, JobRejected
from hermes_cli.background_learner.runner import BackgroundLearnerRunner
from hermes_cli.jarvis_prime.self_update import ProposalBook, ProposalStatus

SPAWN_ENV = "MUSE_AUTORESEARCH_ALLOW_SPAWN"
PAYLOAD = {"tag": "nightly", "lanes": 2, "max_experiments": 4, "max_cost_usd": 1.0}


def test_kind_is_allowed_and_unknown_kinds_still_rejected() -> None:
    assert "autoresearch_train" in ALLOWED_KINDS
    queue = JobQueue()
    queue.enqueue("autoresearch_train", payload=dict(PAYLOAD))
    with pytest.raises(JobRejected):
        queue.enqueue("autoresearch_overclock_gpu")


def test_live_enqueue_without_token_downgrades_to_dry_run() -> None:
    queue = JobQueue()
    job = queue.enqueue("autoresearch_train", dry_run=False, payload=dict(PAYLOAD))
    assert job.dry_run is True  # fail-closed downgrade
    assert any(e["event"] == "downgraded" for e in queue.audit_log())


def test_dry_run_is_plan_only_and_never_calls_the_runner(monkeypatch) -> None:
    monkeypatch.setenv(SPAWN_ENV, "1")  # even with the env open, dry_run plans only
    calls: list[Any] = []
    runner = BackgroundLearnerRunner(autoresearch_fn=lambda *a, **k: calls.append(1))
    queue = JobQueue(executor=runner.handle)
    job = queue.enqueue("autoresearch_train", payload=dict(PAYLOAD))
    out = runner.handle(job)
    assert out.status == "ran"
    assert "plan-only (dry_run)" in out.detail
    assert "autoresearch/nightly-gpu0" in out.detail  # the plan names branches
    assert "autoresearch/nightly-gpu1" in out.detail
    assert calls == []


def test_live_without_spawn_env_degrades_to_plan_only(monkeypatch) -> None:
    monkeypatch.delenv(SPAWN_ENV, raising=False)
    calls: list[Any] = []
    runner = BackgroundLearnerRunner(autoresearch_fn=lambda *a, **k: calls.append(1))
    queue = JobQueue()
    job = queue.enqueue(
        "autoresearch_train",
        dry_run=False,
        payload=dict(PAYLOAD),
        approval_token="owner-token",
    )
    assert job.dry_run is False  # token accepted at enqueue
    out = runner.handle(job)
    assert out.status == "ran"
    assert SPAWN_ENV in out.detail  # the missing gate is named
    assert calls == []


def test_fully_gated_live_run_proposes(monkeypatch) -> None:
    monkeypatch.setenv(SPAWN_ENV, "1")
    book = ProposalBook()

    class _FakeSwarmOutcome:
        def __init__(self, proposal: Any) -> None:
            self.proposal_outcome = type("PO", (), {"proposal": proposal})()

    def fake_swarm(plan, *, book: ProposalBook, baseline_bpb, min_bpb_delta):
        assert [a.branch for a in plan.assignments] == [
            "autoresearch/nightly-gpu0",
            "autoresearch/nightly-gpu1",
        ]
        from hermes_cli.jarvis_prime.self_update import ProposalKind

        proposal = book.propose(
            kind=ProposalKind.SELF_RUNTIME_UPDATE,
            target_path="vendor/train.py",
            rationale="fake swarm winner",
            diff_intent="adopt champion",
            risk_class="RC4",
        )
        return _FakeSwarmOutcome(proposal)

    runner = BackgroundLearnerRunner(book=book, autoresearch_fn=fake_swarm)
    queue = JobQueue()
    job = queue.enqueue(
        "autoresearch_train",
        dry_run=False,
        payload=dict(PAYLOAD),
        approval_token="owner-token",
    )
    out = runner.handle(job)
    assert out.status == "proposed"
    assert out.proposal is not None
    assert out.proposal.status is ProposalStatus.NEEDS_OWNER_APPROVAL


def test_live_without_wired_runner_is_plan_only(monkeypatch) -> None:
    monkeypatch.setenv(SPAWN_ENV, "1")
    runner = BackgroundLearnerRunner()  # no autoresearch_fn wired
    queue = JobQueue()
    job = queue.enqueue(
        "autoresearch_train", dry_run=False, payload=dict(PAYLOAD), approval_token="t"
    )
    out = runner.handle(job)
    assert out.status == "ran"
    assert "no live autoresearch runner" in out.detail


def test_missing_tag_is_an_error() -> None:
    runner = BackgroundLearnerRunner()
    queue = JobQueue()
    job = queue.enqueue("autoresearch_train", payload={})
    out = runner.handle(job)
    assert out.status == "error"
    assert "tag" in out.detail
