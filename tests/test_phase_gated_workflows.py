"""Tests for the phase-gated workflow engine.

The engine is storage-only, so every test runs against a tmp_path job
directory. Phase progress is driven through the public API (no direct
JSON edits) so the tests double as documentation of the supported call
sequences.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from muse_cli import workflows
from muse_cli.workflow_models import (
    ALWAYS_APPROVAL_GATED,
    ALWAYS_APPROVED_ACTIONS,
    APPROVAL,
    APPROVED,
    AUTO_STARTABLE,
    BLOCKED,
    COMPLETED,
    FAILED,
    IMPLEMENTATION,
    INTAKE,
    NEEDS_APPROVAL,
    PENDING,
    PHASE_ORDER,
    PHASE_STATUSES,
    PLANNING,
    PUBLISH,
    REJECTED,
    REPORT_PHASES,
    RESEARCH,
    RETROSPECTIVE,
    RUNNING,
    TERMINAL_STATUSES,
    VALIDATION,
    Phase,
    WorkflowState,
)
from muse_cli.workflows import (
    InvalidTransitionError,
    JobHandle,
    UnknownPhaseError,
    WorkflowError,
    approve_phase,
    complete_phase,
    fail_phase,
    get_current_phase,
    initialize_phases,
    list_phases,
    load_state,
    reject_phase,
    require_approval,
    transition_phase,
    write_phase_report,
)


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def job(tmp_path: Path) -> JobHandle:
    return JobHandle(
        job_id="job-test-001",
        job_dir=tmp_path / "jobs" / "job-test-001",
        trusted_local=False,
    )


@pytest.fixture
def trusted_job(tmp_path: Path) -> JobHandle:
    return JobHandle(
        job_id="job-test-trusted",
        job_dir=tmp_path / "jobs" / "job-test-trusted",
        trusted_local=True,
    )


def _good_report(phase: str) -> str:
    return (
        f"# {phase.title()} report\n\n"
        f"## Findings\n\nFound something.\n\n"
        f"## Plain English\n\nWe ran the {phase} phase and here is what "
        f"happened, in plain language.\n"
    )


# ──────────────────────────────────────────────────────────────────────
# Constants / shape
# ──────────────────────────────────────────────────────────────────────


class TestConstants:
    def test_phase_order_is_the_required_eight_in_order(self):
        assert PHASE_ORDER == (
            "intake",
            "research",
            "planning",
            "approval",
            "implementation",
            "validation",
            "publish",
            "retrospective",
        )

    def test_phase_statuses_cover_all_required(self):
        required = {
            "pending",
            "running",
            "blocked",
            "needs_approval",
            "approved",
            "rejected",
            "completed",
            "failed",
        }
        assert required.issubset(PHASE_STATUSES)

    def test_intake_is_not_a_report_phase(self):
        assert INTAKE not in REPORT_PHASES

    def test_publish_and_approval_are_always_approval_gated(self):
        assert APPROVAL in ALWAYS_APPROVAL_GATED
        assert PUBLISH in ALWAYS_APPROVAL_GATED

    def test_destructive_and_secrets_always_need_approval(self):
        assert "destructive" in ALWAYS_APPROVED_ACTIONS
        assert "secrets" in ALWAYS_APPROVED_ACTIONS


# ──────────────────────────────────────────────────────────────────────
# initialize_phases
# ──────────────────────────────────────────────────────────────────────


class TestInitializePhases:
    def test_creates_phases_dir_and_status_json(self, job: JobHandle):
        state = initialize_phases(job)
        assert (job.job_dir / "phases").is_dir()
        assert (job.job_dir / "status.json").is_file()
        assert state.job_id == job.job_id
        assert state.created_at > 0

    def test_initializes_all_eight_phases(self, job: JobHandle):
        state = initialize_phases(job)
        for name in PHASE_ORDER:
            assert name in state.phases
            assert state.phases[name].name == name

    def test_intake_starts_completed(self, job: JobHandle):
        state = initialize_phases(job)
        assert state.phases[INTAKE].status == COMPLETED
        assert state.phases[INTAKE].completed_at is not None

    def test_other_phases_start_pending(self, job: JobHandle):
        state = initialize_phases(job)
        for name in PHASE_ORDER:
            if name == INTAKE:
                continue
            assert state.phases[name].status == PENDING

    def test_current_phase_is_research(self, job: JobHandle):
        state = initialize_phases(job)
        assert state.current_phase == RESEARCH

    def test_approval_and_publish_marked_requires_approval(self, job: JobHandle):
        state = initialize_phases(job)
        assert state.phases[APPROVAL].requires_approval is True
        assert state.phases[PUBLISH].requires_approval is True

    def test_implementation_requires_approval_without_trusted_local(
        self, job: JobHandle
    ):
        state = initialize_phases(job)
        assert state.phases[IMPLEMENTATION].requires_approval is True

    def test_trusted_local_drops_implementation_approval(
        self, trusted_job: JobHandle
    ):
        state = initialize_phases(trusted_job)
        assert state.phases[IMPLEMENTATION].requires_approval is False
        # but approval and publish are still gated
        assert state.phases[APPROVAL].requires_approval is True
        assert state.phases[PUBLISH].requires_approval is True

    def test_idempotent(self, job: JobHandle):
        s1 = initialize_phases(job)
        s2 = initialize_phases(job)
        assert s1.created_at == s2.created_at
        assert s1.job_id == s2.job_id


# ──────────────────────────────────────────────────────────────────────
# get_current_phase
# ──────────────────────────────────────────────────────────────────────


class TestGetCurrentPhase:
    def test_returns_research_after_init(self, job: JobHandle):
        initialize_phases(job)
        phase = get_current_phase(job)
        assert phase.name == RESEARCH

    def test_returns_running_after_research_started(self, job: JobHandle):
        initialize_phases(job)
        transition_phase(job, RESEARCH, RESEARCH, "kickoff research")
        phase = get_current_phase(job)
        assert phase.name == RESEARCH
        assert phase.status == RUNNING


# ──────────────────────────────────────────────────────────────────────
# transition_phase — happy paths
# ──────────────────────────────────────────────────────────────────────


class TestTransitionPhase:
    def test_research_can_start_automatically(self, job: JobHandle):
        initialize_phases(job)
        state = transition_phase(job, RESEARCH, RESEARCH, "start research")
        assert state.phases[RESEARCH].status == RUNNING

    def test_advance_research_to_planning_requires_evidence(
        self, job: JobHandle
    ):
        initialize_phases(job)
        transition_phase(job, RESEARCH, RESEARCH, "start research")
        complete_phase(job, RESEARCH, reason="found things")
        # No report on disk yet → planning cannot start.
        with pytest.raises(InvalidTransitionError, match="research"):
            transition_phase(job, RESEARCH, PLANNING, "advance")

    def test_advance_research_to_planning_with_evidence(self, job: JobHandle):
        initialize_phases(job)
        transition_phase(job, RESEARCH, RESEARCH, "start research")
        write_phase_report(job, RESEARCH, _good_report(RESEARCH))
        complete_phase(job, RESEARCH, reason="found things")
        state = transition_phase(job, RESEARCH, PLANNING, "advance to planning")
        assert state.current_phase == PLANNING
        assert state.phases[PLANNING].status == RUNNING

    def test_planning_to_approval_lands_in_needs_approval(self, job: JobHandle):
        initialize_phases(job)
        transition_phase(job, RESEARCH, RESEARCH, "start")
        write_phase_report(job, RESEARCH, _good_report(RESEARCH))
        complete_phase(job, RESEARCH, reason="done")
        transition_phase(job, RESEARCH, PLANNING, "advance")
        write_phase_report(job, PLANNING, _good_report(PLANNING))
        complete_phase(job, PLANNING, reason="planned")
        state = transition_phase(
            job, PLANNING, APPROVAL, "submit plan for approval"
        )
        assert state.phases[APPROVAL].status == NEEDS_APPROVAL
        assert state.current_phase == APPROVAL

    def test_implementation_cannot_start_without_approval(self, job: JobHandle):
        initialize_phases(job)
        # Force-fill predecessors with the public API.
        _walk_to_approval(job)
        # Approval is needs_approval — implementation should be blocked.
        with pytest.raises(InvalidTransitionError, match="approval"):
            transition_phase(
                job, APPROVAL, IMPLEMENTATION, "skip approval", actor="bot"
            )

    def test_implementation_runs_after_approval(self, job: JobHandle):
        initialize_phases(job)
        _walk_to_approval(job)
        approve_phase(job, APPROVAL, approver="alice", note="LGTM")
        state = transition_phase(
            job, APPROVAL, IMPLEMENTATION, "approved → implement"
        )
        assert state.phases[IMPLEMENTATION].status == RUNNING

    def test_trusted_local_can_start_implementation_directly(
        self, trusted_job: JobHandle
    ):
        initialize_phases(trusted_job)
        _walk_to_approval(trusted_job)
        approve_phase(trusted_job, APPROVAL, approver="auto", note="trusted")
        state = transition_phase(
            trusted_job, APPROVAL, IMPLEMENTATION, "trusted-local"
        )
        assert state.phases[IMPLEMENTATION].status == RUNNING

    def test_validation_starts_after_implementation(self, job: JobHandle):
        initialize_phases(job)
        _walk_to_implementation(job)
        write_phase_report(
            job, IMPLEMENTATION, _good_report(IMPLEMENTATION)
        )
        complete_phase(job, IMPLEMENTATION, reason="patch applied")
        state = transition_phase(
            job, IMPLEMENTATION, VALIDATION, "run gates"
        )
        assert state.phases[VALIDATION].status == RUNNING

    def test_publish_lands_in_needs_approval(self, job: JobHandle):
        initialize_phases(job)
        _walk_to_implementation(job)
        write_phase_report(
            job, IMPLEMENTATION, _good_report(IMPLEMENTATION)
        )
        complete_phase(job, IMPLEMENTATION, reason="patch applied")
        transition_phase(job, IMPLEMENTATION, VALIDATION, "run gates")
        write_phase_report(job, VALIDATION, _good_report(VALIDATION))
        complete_phase(job, VALIDATION, reason="green")
        state = transition_phase(
            job, VALIDATION, PUBLISH, "promote artifact"
        )
        assert state.phases[PUBLISH].status == NEEDS_APPROVAL


# ──────────────────────────────────────────────────────────────────────
# transition_phase — invariants
# ──────────────────────────────────────────────────────────────────────


class TestTransitionInvariants:
    def test_cannot_skip_phases(self, job: JobHandle):
        initialize_phases(job)
        with pytest.raises(InvalidTransitionError, match="one step at a time"):
            transition_phase(
                job, RESEARCH, IMPLEMENTATION, "skip", actor="bot"
            )

    def test_cannot_go_backwards(self, job: JobHandle):
        initialize_phases(job)
        with pytest.raises(InvalidTransitionError):
            transition_phase(job, RESEARCH, INTAKE, "rewind")

    def test_unknown_phase_raises(self, job: JobHandle):
        initialize_phases(job)
        with pytest.raises(UnknownPhaseError):
            transition_phase(job, "no-such-phase", RESEARCH, "x")

    def test_reason_required(self, job: JobHandle):
        initialize_phases(job)
        with pytest.raises(WorkflowError, match="reason"):
            transition_phase(job, RESEARCH, RESEARCH, "")

    def test_publish_cannot_be_started_in_place(self, job: JobHandle):
        initialize_phases(job)
        with pytest.raises(InvalidTransitionError, match="approval"):
            transition_phase(job, PUBLISH, PUBLISH, "start publishing")

    def test_implementation_cannot_be_started_in_place_untrusted(
        self, job: JobHandle
    ):
        initialize_phases(job)
        with pytest.raises(InvalidTransitionError, match="trusted_local"):
            transition_phase(
                job, IMPLEMENTATION, IMPLEMENTATION, "start"
            )


# ──────────────────────────────────────────────────────────────────────
# approve_phase / reject_phase
# ──────────────────────────────────────────────────────────────────────


class TestApprovalAndRejection:
    def test_approve_records_approver_and_note(self, job: JobHandle):
        initialize_phases(job)
        _walk_to_approval(job)
        state = approve_phase(
            job, APPROVAL, approver="alice", note="ship it"
        )
        phase = state.phases[APPROVAL]
        assert phase.status == APPROVED
        assert phase.approver == "alice"
        assert phase.approval_note == "ship it"

    def test_approve_requires_non_empty_approver(self, job: JobHandle):
        initialize_phases(job)
        with pytest.raises(WorkflowError, match="approver"):
            approve_phase(job, APPROVAL, approver="", note="x")

    def test_reject_records_reason(self, job: JobHandle):
        initialize_phases(job)
        _walk_to_approval(job)
        state = reject_phase(job, APPROVAL, reason="design unclear")
        phase = state.phases[APPROVAL]
        assert phase.status == REJECTED
        assert phase.rejection_reason == "design unclear"

    def test_reject_requires_reason(self, job: JobHandle):
        initialize_phases(job)
        with pytest.raises(WorkflowError, match="reason"):
            reject_phase(job, APPROVAL, reason="")

    def test_approve_is_idempotent_after_terminal(self, job: JobHandle):
        initialize_phases(job)
        _walk_to_approval(job)
        approve_phase(job, APPROVAL, approver="alice")
        # second call should be a no-op, not raise.
        state = approve_phase(job, APPROVAL, approver="bob")
        # original approver preserved.
        assert state.phases[APPROVAL].approver == "alice"


# ──────────────────────────────────────────────────────────────────────
# require_approval
# ──────────────────────────────────────────────────────────────────────


class TestRequireApproval:
    def test_destructive_always_escalates(self, trusted_job: JobHandle):
        initialize_phases(trusted_job)
        state = require_approval(
            trusted_job,
            IMPLEMENTATION,
            "destructive",
            reason="rm -rf",
        )
        assert state.phases[IMPLEMENTATION].status == NEEDS_APPROVAL

    def test_secrets_always_escalates(self, trusted_job: JobHandle):
        initialize_phases(trusted_job)
        state = require_approval(
            trusted_job,
            IMPLEMENTATION,
            "secrets",
            reason="rotate API key",
        )
        assert state.phases[IMPLEMENTATION].status == NEEDS_APPROVAL

    def test_publish_always_escalates(self, trusted_job: JobHandle):
        initialize_phases(trusted_job)
        state = require_approval(
            trusted_job, PUBLISH, "publish PR", reason="cut release"
        )
        assert state.phases[PUBLISH].status == NEEDS_APPROVAL

    def test_trusted_local_skips_non_forced_approval(
        self, trusted_job: JobHandle
    ):
        initialize_phases(trusted_job)
        state = require_approval(
            trusted_job, IMPLEMENTATION, "ordinary patch", reason="edit"
        )
        # Status should not flip to needs_approval under trusted_local
        assert state.phases[IMPLEMENTATION].status != NEEDS_APPROVAL
        history = state.phases[IMPLEMENTATION].history
        assert any(
            entry.get("result") == "auto-approved by trusted_local"
            for entry in history
        )

    def test_require_approval_needs_action(self, job: JobHandle):
        initialize_phases(job)
        with pytest.raises(WorkflowError, match="action"):
            require_approval(job, IMPLEMENTATION, "", reason=None)


# ──────────────────────────────────────────────────────────────────────
# write_phase_report
# ──────────────────────────────────────────────────────────────────────


class TestWritePhaseReport:
    def test_writes_file_under_phases_dir(self, job: JobHandle):
        initialize_phases(job)
        path = write_phase_report(job, RESEARCH, _good_report(RESEARCH))
        assert path.is_file()
        assert path == job.job_dir / "phases" / "research.md"

    def test_requires_plain_english_section(self, job: JobHandle):
        initialize_phases(job)
        body = "# Research\n\nNo plain-language summary here.\n"
        with pytest.raises(WorkflowError, match="Plain English"):
            write_phase_report(job, RESEARCH, body)

    def test_accepts_case_insensitive_heading(self, job: JobHandle):
        initialize_phases(job)
        body = (
            "# Research\n\n"
            "## plain english\n\n"
            "Lowercase heading should still count.\n"
        )
        write_phase_report(job, RESEARCH, body)

    def test_rejects_intake_report(self, job: JobHandle):
        initialize_phases(job)
        with pytest.raises(WorkflowError, match="report"):
            write_phase_report(job, INTAKE, _good_report(INTAKE))

    def test_rejects_empty_body(self, job: JobHandle):
        initialize_phases(job)
        with pytest.raises(WorkflowError, match="empty"):
            write_phase_report(job, RESEARCH, "   \n")

    def test_records_report_path_in_state(self, job: JobHandle):
        initialize_phases(job)
        write_phase_report(job, RESEARCH, _good_report(RESEARCH))
        state = load_state(job)
        assert state.phases[RESEARCH].report_path == "phases/research.md"


# ──────────────────────────────────────────────────────────────────────
# End-to-end happy path
# ──────────────────────────────────────────────────────────────────────


class TestEndToEnd:
    def test_full_workflow_runs_to_retrospective(self, job: JobHandle):
        state = initialize_phases(job)
        assert state.current_phase == RESEARCH

        # Research
        transition_phase(job, RESEARCH, RESEARCH, "start")
        write_phase_report(job, RESEARCH, _good_report(RESEARCH))
        complete_phase(job, RESEARCH, reason="done")

        # Planning
        transition_phase(job, RESEARCH, PLANNING, "have evidence")
        write_phase_report(job, PLANNING, _good_report(PLANNING))
        complete_phase(job, PLANNING, reason="plan ready")

        # Approval
        transition_phase(job, PLANNING, APPROVAL, "review plan")
        write_phase_report(job, APPROVAL, _good_report(APPROVAL))
        approve_phase(job, APPROVAL, approver="alice", note="LGTM")

        # Implementation
        transition_phase(job, APPROVAL, IMPLEMENTATION, "go")
        write_phase_report(
            job, IMPLEMENTATION, _good_report(IMPLEMENTATION)
        )
        complete_phase(job, IMPLEMENTATION, reason="patch applied")

        # Validation
        transition_phase(job, IMPLEMENTATION, VALIDATION, "gates")
        write_phase_report(job, VALIDATION, _good_report(VALIDATION))
        complete_phase(job, VALIDATION, reason="green")

        # Publish (requires approval)
        transition_phase(job, VALIDATION, PUBLISH, "promote")
        assert get_current_phase(job).status == NEEDS_APPROVAL
        write_phase_report(job, PUBLISH, _good_report(PUBLISH))
        approve_phase(job, PUBLISH, approver="alice", note="ship")

        # Retrospective
        transition_phase(job, PUBLISH, RETROSPECTIVE, "wrap up")
        write_phase_report(
            job, RETROSPECTIVE, _good_report(RETROSPECTIVE)
        )
        complete_phase(job, RETROSPECTIVE, reason="captured lessons")

        state = load_state(job)
        terminal = TERMINAL_STATUSES
        for name in PHASE_ORDER:
            assert state.phases[name].status in terminal, name

    def test_history_records_each_transition(self, job: JobHandle):
        initialize_phases(job)
        transition_phase(job, RESEARCH, RESEARCH, "first start")
        complete_phase(job, RESEARCH, reason="done")
        history = load_state(job).phases[RESEARCH].history
        # at minimum: a "to RUNNING" and a "to COMPLETED" entry.
        assert any(h.get("to") == RUNNING for h in history)
        assert any(h.get("to") == COMPLETED for h in history)


# ──────────────────────────────────────────────────────────────────────
# fail_phase
# ──────────────────────────────────────────────────────────────────────


class TestFailPhase:
    def test_fails_phase_with_reason(self, job: JobHandle):
        initialize_phases(job)
        transition_phase(job, RESEARCH, RESEARCH, "start")
        state = fail_phase(job, RESEARCH, "model timed out")
        assert state.phases[RESEARCH].status == FAILED
        assert state.phases[RESEARCH].rejection_reason == "model timed out"

    def test_requires_reason(self, job: JobHandle):
        initialize_phases(job)
        with pytest.raises(WorkflowError, match="reason"):
            fail_phase(job, RESEARCH, "")


# ──────────────────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────────────────


class TestPersistence:
    def test_status_json_round_trips(self, job: JobHandle):
        initialize_phases(job)
        transition_phase(job, RESEARCH, RESEARCH, "start")
        raw = json.loads((job.job_dir / "status.json").read_text())
        state = WorkflowState.from_dict(raw)
        assert state.job_id == job.job_id
        assert state.phases[RESEARCH].status == RUNNING

    def test_list_phases_returns_canonical_order(self, job: JobHandle):
        initialize_phases(job)
        names = [p.name for p in list_phases(job)]
        assert names == list(PHASE_ORDER)


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _walk_to_approval(job: JobHandle) -> None:
    """Drive the workflow forward to the approval phase, leaving it in
    ``needs_approval``. Used by the gate-rule tests so each one can
    focus on the assertion instead of the setup."""

    transition_phase(job, RESEARCH, RESEARCH, "start")
    write_phase_report(job, RESEARCH, _good_report(RESEARCH))
    complete_phase(job, RESEARCH, reason="done")
    transition_phase(job, RESEARCH, PLANNING, "have evidence")
    write_phase_report(job, PLANNING, _good_report(PLANNING))
    complete_phase(job, PLANNING, reason="plan ready")
    transition_phase(job, PLANNING, APPROVAL, "submit for approval")


def _walk_to_implementation(job: JobHandle) -> None:
    """Drive the workflow to ``implementation`` in ``running`` status."""

    _walk_to_approval(job)
    approve_phase(job, APPROVAL, approver="alice", note="ok")
    transition_phase(job, APPROVAL, IMPLEMENTATION, "begin")
