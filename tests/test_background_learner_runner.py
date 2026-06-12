"""Tests for LEARN-1 live background-learner handlers.

Every handler is read-mostly or proposal-only; code/skill changes become pending
owner-approval Proposals, never applied. Disallowed kinds are still rejected at
enqueue (covered in test_background_learner.py).
"""

from muse_cli.background_learner import (
    BackgroundLearnerRunner,
    JobQueue,
    make_live_queue,
    run_idle_cycle,
)
from muse_cli.jarvis_prime.self_update import ProposalBook, ProposalStatus


def _runner():
    return BackgroundLearnerRunner(book=ProposalBook())


def _job(kind, **payload):
    from muse_cli.background_learner.queue import Job

    return Job(kind=kind, payload=payload, id=1)


def test_scan_outdated_deps_is_read_only():
    out = _runner().handle(_job("scan_outdated_deps"))
    assert out.status == "ran"
    assert "read-only" in out.detail


def test_summarize_session_local_only():
    out = _runner().handle(_job("summarize_session", text="line one\nline two\nline three"))
    assert out.status == "ran"
    assert "line one" in out.detail


def test_evaluate_model_routing_uses_eval_harness():
    out = _runner().handle(_job("evaluate_model_routing", worker_id="w1"))
    assert out.status == "ran"
    assert "worker=w1" in out.detail


def test_propose_code_patch_creates_pending_owner_proposal():
    r = _runner()
    out = r.handle(_job("propose_code_patch", target_path="muse_cli/x.py", rationale="why", diff_intent="what"))
    assert out.status == "proposed"
    assert out.proposal is not None
    # RC3 ⇒ needs owner approval; it is NOT applied.
    assert out.proposal.status == ProposalStatus.NEEDS_OWNER_APPROVAL
    assert out.proposal.requires_owner_approval is True
    assert r.book.pending(), "proposal should be in the pending owner queue"


def test_propose_skill_creates_pending_proposal():
    r = _runner()
    out = r.handle(_job("propose_skill", target_path="skills/foo/SKILL.md"))
    assert out.status == "proposed"
    assert out.proposal.status == ProposalStatus.NEEDS_OWNER_APPROVAL


def test_unhandled_allowed_kind_is_safe_noop():
    out = _runner().handle(_job("update_embeddings"))
    assert out.status == "skipped"


def test_handler_exception_is_contained():
    r = _runner()
    # summarize with a non-string payload that triggers the str() path safely;
    # force an error by monkeypatching the handler target.
    import muse_cli.background_learner.runner as rn

    orig = rn.BackgroundLearnerRunner._h_scan_outdated_deps

    def boom(self, job):
        raise RuntimeError("kaboom")

    rn.BackgroundLearnerRunner._h_scan_outdated_deps = boom  # ty: ignore[invalid-assignment]  # mock/duck-typed test fixture
    try:
        out = r.handle(_job("scan_outdated_deps"))
        assert out.status == "error"
    finally:
        rn.BackgroundLearnerRunner._h_scan_outdated_deps = orig


def test_live_queue_drains_and_emits_proposal():
    book = ProposalBook()
    queue, runner = make_live_queue(idle_check=lambda: True, book=book)
    queue.enqueue("scan_outdated_deps", priority=10)
    queue.enqueue("propose_code_patch", priority=20, payload={"target_path": "x.py"})
    ran = run_idle_cycle(queue, runner)
    assert ran == 2
    assert queue.pending() == []
    assert book.pending(), "a code-patch proposal should be pending owner approval"


def test_idle_gate_blocks_live_drain():
    queue, runner = make_live_queue(idle_check=lambda: False)
    queue.enqueue("scan_outdated_deps")
    assert run_idle_cycle(queue, runner) == 0
    assert len(queue.pending()) == 1
