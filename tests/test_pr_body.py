"""Tests for the GitHub PR-body builder (Sprint 5)."""

from __future__ import annotations

import pytest

from muse_cli.pr_body import PrBodyInputs, render_pr_body

_FAKE_PAT = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _full() -> PrBodyInputs:
    return PrBodyInputs(
        job_id="job_42",
        session_id="sess_7",
        verdict_id="dv_abc",
        validation_summary="8/8 gates passed",
        worker_selected="claude-code",
        diffstat="4 files changed, +120 -8",
        acceptance_criteria=["adds replay", "no behavior change"],
        tests_run=["pytest tests/test_job_replay.py", "11 passed"],
        rollback="revert the PR",
    )


def test_renders_all_sections_and_ids():
    body = render_pr_body(_full())
    assert "## Hermes Job" in body
    assert "- Job: `job_42`" in body
    assert "- Source session: `sess_7`" in body
    assert "- Decision verdict: `dv_abc`" in body
    assert "- Validation: 8/8 gates passed" in body
    assert "- Worker selected: `claude-code`" in body
    assert "- Diffstat: 4 files changed, +120 -8" in body
    assert "## Acceptance criteria" in body
    assert "- [ ] adds replay" in body
    assert "## Tests run" in body
    assert "```text" in body
    assert "11 passed" in body
    assert "## Rollback" in body
    assert "revert the PR" in body


def test_missing_optionals_render_na():
    body = render_pr_body(PrBodyInputs(job_id="job_1"))
    assert "- Source session: `n/a`" in body
    assert "- Decision verdict: `n/a`" in body
    assert "- Validation: n/a" in body
    assert "- Worker selected: `n/a`" in body
    assert "- [ ] (none specified)" in body
    assert "(none recorded)" in body
    assert "## Rollback" in body


def test_empty_job_id_raises():
    with pytest.raises(ValueError):
        render_pr_body(PrBodyInputs(job_id=""))


def test_secrets_redacted_in_free_text():
    body = render_pr_body(
        PrBodyInputs(
            job_id="job_1",
            validation_summary=f"leaked {_FAKE_PAT}",
            rollback=f"token was {_FAKE_PAT}",
            tests_run=[f"echo {_FAKE_PAT}"],
            acceptance_criteria=[f"uses {_FAKE_PAT}"],
        )
    )
    assert _FAKE_PAT not in body


def test_ids_are_not_redacted():
    # ids are interpolated as-is (they are not secrets)
    body = render_pr_body(PrBodyInputs(job_id="job_42", verdict_id="dv_abc"))
    assert "`job_42`" in body
    assert "`dv_abc`" in body


def test_deterministic():
    assert render_pr_body(_full()) == render_pr_body(_full())
