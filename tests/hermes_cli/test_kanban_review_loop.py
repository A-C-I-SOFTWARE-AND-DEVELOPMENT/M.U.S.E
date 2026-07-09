"""Tests for the opt-in kanban rejection loop (review_before_done)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    """Isolated HERMES_HOME with an empty kanban DB."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _make_running_task(conn, *, assignee="executor"):
    task_id = kb.create_task(conn, title="build the thing", assignee=assignee)
    claimed = kb.claim_task(conn, task_id)
    assert claimed is not None
    return claimed


def _event_kinds(conn, task_id):
    return [e.kind for e in kb.list_events(conn, task_id)]


class TestDefaultPathUnchanged:
    def test_complete_goes_straight_to_done_by_default(self, kanban_home):
        with kb.connect() as conn:
            task = _make_running_task(conn)
            ok = kb.complete_task(conn, task.id, result="did it", summary="done")
            assert ok is True
            assert kb.get_task(conn, task.id).status == "done"
            assert "review_requested" not in _event_kinds(conn, task.id)

    def test_explicit_false_overrides_config(self, kanban_home):
        with kb.connect() as conn:
            task = _make_running_task(conn)
            ok = kb.complete_task(
                conn, task.id, result="did it", review_before_done=False
            )
            assert ok is True
            assert kb.get_task(conn, task.id).status == "done"


class TestReviewDiversion:
    def test_builder_completion_diverts_to_review(self, kanban_home):
        with kb.connect() as conn:
            task = _make_running_task(conn)
            ok = kb.complete_task(
                conn, task.id,
                result="did it", summary="please review",
                review_before_done=True,
            )
            assert ok is True
            refreshed = kb.get_task(conn, task.id)
            assert refreshed.status == "review"
            assert refreshed.result == "did it"
            assert refreshed.claim_lock is None
            kinds = _event_kinds(conn, task.id)
            assert "review_requested" in kinds
            assert "completed" not in kinds

    def test_reviewer_recorded_without_reassigning_builder(self, kanban_home):
        """The task keeps its builder as assignee — the reviewer is spawn
        routing, not ownership. A crashed review run can then never corrupt
        builder attribution."""
        with kb.connect() as conn:
            task = _make_running_task(conn, assignee="executor")
            kb.complete_task(
                conn, task.id, result="did it",
                review_before_done=True, reviewer_profile="critic",
            )
            refreshed = kb.get_task(conn, task.id)
            assert refreshed.status == "review"
            assert refreshed.assignee == "executor"
            payload = kb._latest_event_payload(conn, task.id, "review_requested")
            assert payload["builder"] == "executor"
            assert payload["reviewer"] == "critic"

    def test_manual_completion_never_diverts(self, kanban_home):
        """A human 'mark done' on a never-claimed task is a human decision —
        straight to done even with the loop enabled."""
        with kb.connect() as conn:
            task_id = kb.create_task(conn, title="manual", assignee="executor")
            ok = kb.complete_task(
                conn, task_id, result="done by operator",
                review_before_done=True, reviewer_profile="critic",
            )
            assert ok is True
            assert kb.get_task(conn, task_id).status == "done"

    def test_blocked_task_completion_never_diverts(self, kanban_home):
        """Closing out a blocked task goes straight to done — diverting
        would let a later rejection defeat the sticky operator block."""
        with kb.connect() as conn:
            task = _make_running_task(conn)
            kb.block_task(conn, task.id, reason="needs human input")
            ok = kb.complete_task(
                conn, task.id, result="resolved offline",
                review_before_done=True,
            )
            assert ok is True
            assert kb.get_task(conn, task.id).status == "done"

    def test_operator_can_force_done_from_review(self, kanban_home):
        """A task parked in review must have an operator exit: a manual
        completion (no claim) closes it out."""
        with kb.connect() as conn:
            task = _make_running_task(conn)
            kb.complete_task(
                conn, task.id, result="attempt", review_before_done=True
            )
            assert kb.get_task(conn, task.id).status == "review"
            ok = kb.complete_task(
                conn, task.id, result="operator override",
                review_before_done=True,
            )
            assert ok is True
            assert kb.get_task(conn, task.id).status == "done"

    def test_review_run_records_reviewer_profile(self, kanban_home):
        with kb.connect() as conn:
            task = _make_running_task(conn, assignee="executor")
            kb.complete_task(
                conn, task.id, result="attempt",
                review_before_done=True, reviewer_profile="critic",
            )
            claimed = kb.claim_review_task(
                conn, task.id, run_profile="critic"
            )
            assert claimed is not None
            run = kb.latest_run(conn, task.id)
            assert run.profile == "critic"
            # Task assignee untouched by the review claim.
            assert kb.get_task(conn, task.id).assignee == "executor"

    def test_rejected_task_is_not_respawn_guarded(self, kanban_home):
        """A rejection is an explicit rework instruction — neither the
        'recent_success' window nor a PR URL in the critique may freeze
        the builder respawn."""
        with kb.connect() as conn:
            task = _make_running_task(conn, assignee="executor")
            kb.complete_task(
                conn, task.id, result="attempt",
                review_before_done=True, reviewer_profile="critic",
            )
            assert kb.claim_review_task(conn, task.id) is not None
            kb.reject_review(
                conn, task.id, reviewer="critic",
                critique=(
                    "tests missing — see "
                    "https://github.com/o/r/pull/42 for the diff"
                ),
            )
            assert kb.get_task(conn, task.id).status == "ready"
            assert kb.check_respawn_guard(conn, task.id) is None

    def test_children_are_not_promoted_until_real_completion(self, kanban_home):
        with kb.connect() as conn:
            parent = _make_running_task(conn)
            child_id = kb.create_task(conn, title="child", parents=[parent.id])
            assert kb.get_task(conn, child_id).status == "todo"
            kb.complete_task(
                conn, parent.id, result="done-ish", review_before_done=True
            )
            kb.recompute_ready(conn)
            assert kb.get_task(conn, child_id).status == "todo"

    def test_review_run_completion_goes_to_done_with_approval(self, kanban_home):
        with kb.connect() as conn:
            task = _make_running_task(conn, assignee="executor")
            kb.complete_task(
                conn, task.id, result="did it",
                review_before_done=True, reviewer_profile="critic",
            )
            claimed = kb.claim_review_task(conn, task.id)
            assert claimed is not None
            ok = kb.complete_task(
                conn, task.id, result="verified",
                review_before_done=True, reviewer_profile="critic",
            )
            assert ok is True
            refreshed = kb.get_task(conn, task.id)
            assert refreshed.status == "done"
            # Attribution restored to the builder on approval.
            assert refreshed.assignee == "executor"
            kinds = _event_kinds(conn, task.id)
            assert "review_approved" in kinds
            payload = kb._latest_event_payload(conn, task.id, "review_approved")
            assert payload["builder"] == "executor"


class TestRejectReview:
    def _diverted_and_claimed(self, conn):
        task = _make_running_task(conn, assignee="executor")
        kb.complete_task(
            conn, task.id, result="attempt 1",
            review_before_done=True, reviewer_profile="critic",
        )
        claimed = kb.claim_review_task(conn, task.id)
        assert claimed is not None
        return task

    def test_reject_returns_task_to_builder_with_critique(self, kanban_home):
        with kb.connect() as conn:
            task = self._diverted_and_claimed(conn)
            ok = kb.reject_review(
                conn, task.id,
                critique="tests missing for the error path",
                reviewer="critic",
            )
            assert ok is True
            refreshed = kb.get_task(conn, task.id)
            assert refreshed.status == "ready"
            assert refreshed.assignee == "executor"
            comments = kb.list_comments(conn, task.id)
            assert any(
                "tests missing" in c.body and c.author == "critic"
                for c in comments
            )
            payload = kb._latest_event_payload(conn, task.id, "review_rejected")
            assert payload["rejections"] == 1
            assert payload["builder"] == "executor"

    def test_reject_requires_critique(self, kanban_home):
        with kb.connect() as conn:
            task = self._diverted_and_claimed(conn)
            with pytest.raises(ValueError):
                kb.reject_review(conn, task.id, critique="  ")

    def test_reject_refused_on_plain_builder_run(self, kanban_home):
        with kb.connect() as conn:
            task = _make_running_task(conn)
            assert (
                kb.reject_review(conn, task.id, critique="nope") is False
            )

    def test_reject_on_unclaimed_review_task(self, kanban_home):
        with kb.connect() as conn:
            task = _make_running_task(conn, assignee="executor")
            kb.complete_task(
                conn, task.id, result="attempt 1", review_before_done=True
            )
            ok = kb.reject_review(
                conn, task.id, critique="manual rejection", reviewer="owner"
            )
            assert ok is True
            assert kb.get_task(conn, task.id).status == "ready"

    def test_reject_limit_parks_task_in_blocked(self, kanban_home):
        with kb.connect() as conn:
            task = _make_running_task(conn, assignee="executor")
            for i in range(2):
                kb.complete_task(
                    conn, task.id, result=f"attempt {i}",
                    review_before_done=True, reviewer_profile="critic",
                )
                assert kb.claim_review_task(conn, task.id) is not None
                kb.reject_review(
                    conn, task.id,
                    critique=f"still wrong ({i})", reviewer="critic",
                    reject_limit=2,
                )
                # Re-claim for the next attempt unless the breaker tripped.
                if kb.get_task(conn, task.id).status == "ready":
                    assert kb.claim_task(conn, task.id) is not None
            refreshed = kb.get_task(conn, task.id)
            assert refreshed.status == "blocked"
            kinds = _event_kinds(conn, task.id)
            assert kinds.count("review_rejected") == 2
            assert "blocked" in kinds

    def test_unblock_resets_rejection_budget(self, kanban_home):
        """An operator unblock grants a fresh rejection budget, not exactly
        one more review cycle."""
        with kb.connect() as conn:
            task = _make_running_task(conn, assignee="executor")
            for i in range(2):
                kb.complete_task(
                    conn, task.id, result=f"attempt {i}",
                    review_before_done=True, reviewer_profile="critic",
                )
                assert kb.claim_review_task(conn, task.id) is not None
                kb.reject_review(
                    conn, task.id, critique=f"wrong ({i})",
                    reviewer="critic", reject_limit=2,
                )
                if kb.get_task(conn, task.id).status == "ready":
                    assert kb.claim_task(conn, task.id) is not None
            assert kb.get_task(conn, task.id).status == "blocked"

            kb.unblock_task(conn, task.id)
            assert kb.claim_task(conn, task.id) is not None
            kb.complete_task(
                conn, task.id, result="fresh attempt",
                review_before_done=True, reviewer_profile="critic",
            )
            assert kb.claim_review_task(conn, task.id) is not None
            kb.reject_review(
                conn, task.id, critique="one more issue",
                reviewer="critic", reject_limit=2,
            )
            # First rejection after the unblock: budget was reset, so the
            # task returns to ready instead of instantly re-blocking.
            assert kb.get_task(conn, task.id).status == "ready"

    def test_full_loop_reject_then_fix_then_approve(self, kanban_home):
        with kb.connect() as conn:
            task = _make_running_task(conn, assignee="executor")
            kb.complete_task(
                conn, task.id, result="attempt 1",
                review_before_done=True, reviewer_profile="critic",
            )
            assert kb.claim_review_task(conn, task.id) is not None
            kb.reject_review(
                conn, task.id, critique="fix the tests", reviewer="critic"
            )
            # Builder picks the rework back up; critique is in its context.
            claimed = kb.claim_task(conn, task.id)
            assert claimed is not None
            ctx = kb.build_worker_context(conn, task.id)
            assert "fix the tests" in ctx
            kb.complete_task(
                conn, task.id, result="attempt 2",
                review_before_done=True, reviewer_profile="critic",
            )
            assert kb.claim_review_task(conn, task.id) is not None
            kb.complete_task(
                conn, task.id, result="approved",
                review_before_done=True, reviewer_profile="critic",
            )
            assert kb.get_task(conn, task.id).status == "done"


class TestStats:
    def test_review_stats_aggregates_by_builder(self, kanban_home):
        with kb.connect() as conn:
            task = _make_running_task(conn, assignee="executor")
            kb.complete_task(
                conn, task.id, result="attempt 1",
                review_before_done=True, reviewer_profile="critic",
            )
            assert kb.claim_review_task(conn, task.id) is not None
            kb.reject_review(conn, task.id, critique="redo", reviewer="critic")
            assert kb.claim_task(conn, task.id) is not None
            kb.complete_task(
                conn, task.id, result="attempt 2",
                review_before_done=True, reviewer_profile="critic",
            )
            assert kb.claim_review_task(conn, task.id) is not None
            kb.complete_task(
                conn, task.id, result="ok",
                review_before_done=True, reviewer_profile="critic",
            )
            stats = kb.review_stats(conn)
            assert stats["executor"] == {
                "submitted": 2, "approved": 1, "rejected": 1,
            }

    def test_profile_outcome_stats_groups_runs(self, kanban_home):
        with kb.connect() as conn:
            t1 = _make_running_task(conn, assignee="executor")
            kb.complete_task(conn, t1.id, result="ok")
            t2 = _make_running_task(conn, assignee="executor")
            kb.block_task(conn, t2.id, reason="need input")
            stats = kb.profile_outcome_stats(conn)
            assert stats["executor"]["completed"] == 1
            assert stats["executor"]["blocked"] == 1
