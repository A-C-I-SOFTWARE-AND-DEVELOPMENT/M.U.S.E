"""End-to-end integration test for the orchestrator slash commands.

Drives the full chat-flow a user (or a gateway) sees:

  /orchestrate <prompt>
  /orchestrator list
  /orchestrator status <id>
  /orchestrator resume <id>
  /orchestrator publish <id>
  /decision-ledger show <id>
  /model-router explain <prompt>
  /ai-radar update
  /best-coding-tool-mission status

Every call goes through the public ``run_*`` dispatchers — the same
entry points the CLI parser and the gateway use — so a regression in
either surface trips this test.
"""

from __future__ import annotations

import pytest

from muse_cli import orchestrator as orch


def test_full_chat_flow() -> None:
    # 1. submit
    msg = orch.run_orchestrate("ship the orchestrator")
    assert "Orchestration job queued" in msg
    # Pull the job id out of the controller — easier than parsing the
    # surface.
    jobs = orch.list_jobs()
    assert len(jobs) == 1
    job_id = jobs[0].id

    # 2. listing
    listed = orch.run_orchestrator("list")
    assert job_id in listed
    assert "Recent orchestrator jobs" in listed

    # 3. status with id
    status = orch.run_orchestrator(f"status {job_id}")
    assert job_id in status
    assert "queued" in status

    # 4. resume — move it to paused so resume actually flips status.
    all_jobs = orch._load_jobs()
    all_jobs[-1].status = "paused"
    orch._save_jobs(all_jobs)
    msg = orch.run_orchestrator(f"resume {job_id}")
    assert "re-queued" in msg

    # 5. publish
    msg = orch.run_orchestrator(f"publish {job_id}")
    assert "published" in msg

    # 6. decision ledger
    ledger = orch.run_decision_ledger(f"show {job_id}")
    assert "submit" in ledger
    assert "publish" in ledger
    # resume entry was recorded too.
    assert "resume" in ledger

    # 7. model router
    decision = orch.run_model_router("explain please review this PR")
    assert "reviewer-profile" in decision

    # 8. ai radar
    msg = orch.run_ai_radar("update")
    assert "ai-radar snapshot written" in msg

    # 9. mission status now reflects the live counters
    mission = orch.run_best_coding_tool_mission("status")
    assert "jobs_submitted: 1" in mission
    assert "jobs_published: 1" in mission


def test_help_text_returned_when_empty() -> None:
    assert "Usage:" in orch.run_orchestrate("")
    assert "Usage:" in orch.run_orchestrator("")
    assert "Usage:" in orch.run_model_router("")
    assert "Usage:" in orch.run_decision_ledger("")
    assert "Usage:" in orch.run_ai_radar("")
    assert "Usage:" in orch.run_best_coding_tool_mission("")


def test_unknown_subcommand_returns_error_not_crash() -> None:
    msg = orch.run_orchestrator("teleport")
    assert "unknown subcommand" in msg

    msg = orch.run_model_router("decide foo")
    assert "unknown subcommand" in msg


def test_open_resume_publish_require_id() -> None:
    for cmd in ("open", "resume", "publish"):
        msg = orch.run_orchestrator(cmd)
        assert "requires a job id" in msg


def test_lookup_supports_prefix() -> None:
    job = orch.submit_job("prefix lookup test")
    short = job.id[:6]
    msg = orch.run_orchestrator(f"open {short}")
    assert job.id in msg


def test_unknown_job_lookup_returns_clean_error() -> None:
    msg = orch.run_orchestrator("open orc-deadbeef")
    assert "unknown job id" in msg
