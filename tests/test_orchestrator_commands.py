"""Tests for the Phase 16 native orchestrator slash commands.

Covers:

* The CommandDef entries in :mod:`muse_cli.commands`.
* The controller in :mod:`muse_cli.orchestrator` (job CRUD, ledger,
  model router, AI radar, mission status).
* The ``run_*`` entry points used by both the CLI and the gateway.

Each test runs against an isolated ``HERMES_HOME`` (see
``tests/conftest.py``), so JSON files written by the orchestrator do
not leak between tests.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from muse_cli import orchestrator as orch
from muse_cli.commands import (
    COMMAND_REGISTRY,
    GATEWAY_KNOWN_COMMANDS,
    SUBCOMMANDS,
    resolve_command,
)


# ---------------------------------------------------------------------------
# CommandDef registry tests
# ---------------------------------------------------------------------------

class TestRegistryEntries:
    def test_orchestrate_is_registered(self) -> None:
        cmd = resolve_command("orchestrate")
        assert cmd is not None
        assert cmd.name == "orchestrate"
        assert cmd.args_hint == "<prompt>"
        # Phase 16 keeps orchestrator commands cli_only so they don't
        # crowd Slack's 50-slash app-manifest cap. The gateway dispatcher
        # is wired but dormant — a future phase can flip the gate.
        assert cmd.cli_only
        assert not cmd.gateway_only

    @pytest.mark.parametrize("name,subs", [
        ("orchestrator", (
            "status", "list", "open", "resume", "cancel",
            "approve", "validate", "publish", "publish-plan",
        )),
        ("model-router", ("explain",)),
        ("decision-ledger", ("show",)),
        ("ai-radar", ("update",)),
        ("best-coding-tool-mission", ("status",)),
        ("voice-capture", ("status", "mode")),
        ("remote-worker", ("status",)),
        ("self-improve", ("run",)),
        ("profile", ("build-github-history",)),
    ])
    def test_subcommand_registry(self, name: str, subs: tuple[str, ...]) -> None:
        cmd = resolve_command(name)
        assert cmd is not None, f"missing CommandDef for /{name}"
        assert cmd.subcommands == subs
        # Subcommand lookup must be wired so tab-completion sees them.
        assert SUBCOMMANDS.get(f"/{name}") == list(subs)

    def test_all_orchestrator_commands_are_cli_only(self) -> None:
        # Phase 24 keeps the orchestrator-family commands cli_only to avoid
        # bumping aliases like /q and /btw off Slack's 50-slash cap.  They
        # remain discoverable via /help, the tab-completer, and prefix
        # matching in :func:`HermesCLI.process_command`.  ``/profile`` is
        # excluded — it predates this surface and is gateway-visible.
        for name in (
            "orchestrate",
            "orchestrator",
            "model-router",
            "decision-ledger",
            "ai-radar",
            "best-coding-tool-mission",
            "voice-capture",
            "remote-worker",
            "self-improve",
        ):
            cmd = resolve_command(name)
            assert cmd is not None and cmd.cli_only, (
                f"/{name} should be cli_only"
            )

    def test_no_orchestrator_command_appears_in_gateway_set(self) -> None:
        # GATEWAY_KNOWN_COMMANDS excludes cli_only entries (unless
        # gateway_config_gate is set). Sanity-check that the orchestrator
        # commands are not silently surfaced.  ``/profile`` is excluded —
        # it predates this surface and is gateway-visible.
        for name in (
            "orchestrate",
            "orchestrator",
            "model-router",
            "decision-ledger",
            "ai-radar",
            "best-coding-tool-mission",
            "voice-capture",
            "remote-worker",
            "self-improve",
        ):
            assert name not in GATEWAY_KNOWN_COMMANDS, (
                f"/{name} unexpectedly appears in GATEWAY_KNOWN_COMMANDS"
            )

    def test_no_orchestrator_command_collides_with_existing_names(self) -> None:
        # Each canonical name appears exactly once.
        new_names = {
            "orchestrate", "orchestrator", "model-router",
            "decision-ledger", "ai-radar", "best-coding-tool-mission",
            "voice-capture", "remote-worker", "self-improve",
        }
        seen = [c.name for c in COMMAND_REGISTRY if c.name in new_names]
        assert sorted(seen) == sorted(new_names)


# ---------------------------------------------------------------------------
# Controller: job CRUD
# ---------------------------------------------------------------------------

class TestJobLifecycle:
    def test_submit_records_job(self, tmp_path: Path) -> None:
        job = orch.submit_job("ship the orchestrator")
        assert job.id.startswith("orc-")
        assert job.prompt == "ship the orchestrator"
        assert job.status == "queued"
        assert job.created_at > 0

        # File was persisted under HERMES_HOME/orchestrator/jobs.json.
        home = Path(os.environ["HERMES_HOME"]) / "orchestrator"
        jobs_file = home / "jobs.json"
        assert jobs_file.is_file()
        on_disk = json.loads(jobs_file.read_text(encoding="utf-8"))
        assert isinstance(on_disk, list) and len(on_disk) == 1
        assert on_disk[0]["id"] == job.id

    def test_submit_rejects_blank_prompt(self) -> None:
        with pytest.raises(ValueError):
            orch.submit_job("   ")

    def test_list_returns_newest_first(self) -> None:
        a = orch.submit_job("first")
        b = orch.submit_job("second")
        c = orch.submit_job("third")
        listing = orch.list_jobs()
        # Newest first: c, b, a.  All three live.
        assert [j.id for j in listing[:3]] == [c.id, b.id, a.id]

    def test_get_job_prefix_matches(self) -> None:
        job = orch.submit_job("prefix lookup")
        # First 5 chars of the id should resolve unambiguously.
        prefix = job.id[:5]
        found = orch.get_job(prefix)
        assert found is not None and found.id == job.id

    def test_resume_marks_paused_failed_back_to_queued(self) -> None:
        job = orch.submit_job("resume me")
        # Hand-flip status to paused before resuming.
        jobs = orch._load_jobs()
        jobs[0].status = "paused"
        orch._save_jobs(jobs)
        resumed = orch.resume_job(job.id)
        assert resumed is not None
        assert resumed.status == "queued"
        assert resumed.resumed_count == 1

    def test_resume_unknown_id_returns_none(self) -> None:
        assert orch.resume_job("does-not-exist") is None

    def test_publish_sets_status_and_timestamp(self) -> None:
        job = orch.submit_job("publish me")
        published = orch.publish_job(job.id)
        assert published is not None
        assert published.status == "published"
        assert published.published_at and published.published_at > 0

    def test_publish_unknown_id_returns_none(self) -> None:
        assert orch.publish_job("nope") is None


# ---------------------------------------------------------------------------
# Controller: decision ledger
# ---------------------------------------------------------------------------

class TestDecisionLedger:
    def test_submit_writes_ledger_entry(self) -> None:
        job = orch.submit_job("hello ledger")
        ledger = orch.get_ledger(job.id)
        assert job.id in ledger
        entries = ledger[job.id]
        assert len(entries) == 1
        assert entries[0]["kind"] == "submit"
        assert entries[0]["prompt"] == "hello ledger"

    def test_resume_and_publish_append_ledger_entries(self) -> None:
        job = orch.submit_job("multi-step")
        orch.resume_job(job.id)
        orch.publish_job(job.id)
        entries = orch.get_ledger(job.id)[job.id]
        kinds = [e.get("kind") for e in entries]
        assert kinds == ["submit", "resume", "publish"]

    def test_get_ledger_unknown_id_returns_empty(self) -> None:
        assert orch.get_ledger("does-not-exist") == {}


# ---------------------------------------------------------------------------
# Controller: unified decision verdict at the submit boundary (Sprint 2)
# ---------------------------------------------------------------------------

class TestSubmitDecisionVerdict:
    def test_submit_attaches_auto_verdict_to_submit_entry(self) -> None:
        """submit_job records the unified verdict on its `submit` ledger entry.

        Submitting is intent-only — no worker runs, no owner-gated action — so
        the verdict is `auto`.
        """
        job = orch.submit_job("verdict at submit")
        entries = orch.get_ledger(job.id)[job.id]
        submit = next(e for e in entries if e.get("kind") == "submit")
        verdict = submit.get("decision_verdict")
        assert verdict is not None
        assert verdict["tier"] == "auto"
        assert verdict["action_type"] == "orchestrator.submit_job"
        # auto verdicts carry no reason codes and never require an owner phrase.
        assert verdict["reason_codes"] == []
        assert verdict["required_owner_phrase"] is None

    def test_submit_verdict_is_recorded_only_not_gating(self) -> None:
        """Recording the verdict must not change the submit outcome.

        The job is still queued and the ledger still holds exactly one
        `submit` entry (the verdict rides on it, it is not a second entry).
        """
        job = orch.submit_job("recorded not gating")
        assert job.status == "queued"
        entries = orch.get_ledger(job.id)[job.id]
        submit_entries = [e for e in entries if e.get("kind") == "submit"]
        assert len(submit_entries) == 1
        # Behaviour preserved: the original submit fields are untouched.
        assert submit_entries[0]["prompt"] == "recorded not gating"


# ---------------------------------------------------------------------------
# Controller: model router / radar / mission
# ---------------------------------------------------------------------------

class TestModelRouter:
    @pytest.mark.parametrize("prompt,expected_route", [
        ("please review this PR carefully", "reviewer-profile"),
        ("debug the failing test", "debug-profile"),
        ("refactor the auth flow", "builder-profile"),
        ("design a sharding plan", "architect-profile"),
        ("write a test for the new helper", "tester-profile"),
        ("document the gateway hooks", "writer-profile"),
    ])
    def test_keyword_routes(self, prompt: str, expected_route: str) -> None:
        decision = orch.model_router_explain(prompt)
        assert decision["route"] == expected_route
        assert decision["rationale"]
        assert decision["matched_keywords"]

    def test_no_keyword_defaults_to_default_profile(self) -> None:
        decision = orch.model_router_explain("what's the weather like")
        assert decision["route"] == "default-profile"
        assert decision["matched_keywords"] == []


class TestAiRadar:
    def test_update_writes_snapshot(self) -> None:
        snap = orch.ai_radar_update()
        assert snap["updated_at"] > 0
        # File is on disk.
        home = Path(os.environ["HERMES_HOME"]) / "orchestrator"
        assert (home / "ai_radar.json").is_file()
        # Status reads the same file.
        loaded = orch.ai_radar_status()
        assert loaded["updated_at"] == snap["updated_at"]


class TestMissionStatus:
    def test_metrics_reflect_live_jobs(self) -> None:
        a = orch.submit_job("alpha")
        b = orch.submit_job("beta")
        orch.publish_job(a.id)
        orch.resume_job(b.id)
        snap = orch.best_coding_tool_mission_status()
        assert snap["metrics"]["jobs_submitted"] == 2
        assert snap["metrics"]["jobs_published"] == 1
        assert snap["metrics"]["jobs_resumed"] == 1


# ---------------------------------------------------------------------------
# Slash entry points (used by CLI and gateway)
# ---------------------------------------------------------------------------

class TestRunOrchestrate:
    def test_help_when_no_payload(self) -> None:
        out = orch.run_orchestrate("")
        assert "Usage: /orchestrate" in out

    def test_help_when_dash_h(self) -> None:
        assert "Usage: /orchestrate" in orch.run_orchestrate("--help")
        assert "Usage: /orchestrate" in orch.run_orchestrate("-h")

    def test_success_path_includes_job_id(self) -> None:
        out = orch.run_orchestrate("build the new dashboard")
        assert "Orchestration job queued" in out
        assert "orc-" in out
        assert "No worker has started" in out


class TestRunOrchestrator:
    def test_help_when_no_subcommand(self) -> None:
        assert "Usage: /orchestrator" in orch.run_orchestrator("")
        assert "Usage: /orchestrator" in orch.run_orchestrator("help")

    def test_status_with_no_jobs(self) -> None:
        out = orch.run_orchestrator("status")
        assert "no jobs yet" in out

    def test_list_with_jobs(self) -> None:
        job = orch.submit_job("listing test")
        out = orch.run_orchestrator("list")
        assert job.id in out
        assert "listing test" in out

    def test_status_with_unknown_id(self) -> None:
        out = orch.run_orchestrator("status nonexistent-job")
        assert "unknown job id" in out

    def test_open_returns_full_detail(self) -> None:
        job = orch.submit_job("open me")
        out = orch.run_orchestrator(f"open {job.id}")
        assert f"job:        {job.id}" in out
        assert "prompt:" in out
        assert "open me" in out

    def test_resume_then_publish(self) -> None:
        job = orch.submit_job("flow test")
        out_resume = orch.run_orchestrator(f"resume {job.id}")
        assert job.id in out_resume
        assert "re-queued" in out_resume
        out_publish = orch.run_orchestrator(f"publish {job.id}")
        assert "marked published" in out_publish

    def test_unknown_subcommand(self) -> None:
        out = orch.run_orchestrator("teleport")
        assert "unknown subcommand" in out

    def test_open_without_id(self) -> None:
        out = orch.run_orchestrator("open")
        assert "requires a job id" in out

    def test_resume_without_id(self) -> None:
        out = orch.run_orchestrator("resume")
        assert "requires a job id" in out

    def test_publish_without_id(self) -> None:
        out = orch.run_orchestrator("publish")
        assert "requires a job id" in out


class TestRunModelRouter:
    def test_help_when_no_subcommand(self) -> None:
        out = orch.run_model_router("")
        assert "Usage: /model-router" in out

    def test_help_when_explain_with_no_prompt(self) -> None:
        out = orch.run_model_router("explain")
        assert "Usage: /model-router" in out

    def test_explain_returns_route_block(self) -> None:
        out = orch.run_model_router("explain please review this diff")
        assert "route:" in out
        assert "reviewer-profile" in out
        assert "rationale:" in out
        assert "matched:" in out

    def test_unknown_subcommand(self) -> None:
        out = orch.run_model_router("forecast")
        assert "unknown subcommand" in out


class TestRunDecisionLedger:
    def test_help_when_no_payload(self) -> None:
        out = orch.run_decision_ledger("")
        assert "Usage: /decision-ledger" in out

    def test_show_empty_returns_empty_message(self) -> None:
        out = orch.run_decision_ledger("show")
        assert "no ledger entries" in out

    def test_show_after_submit_lists_entries(self) -> None:
        job = orch.submit_job("ledger test")
        out = orch.run_decision_ledger("show")
        assert job.id in out
        assert "submit" in out

    def test_show_with_job_id_filters(self) -> None:
        a = orch.submit_job("alpha")
        b = orch.submit_job("beta")
        out = orch.run_decision_ledger(f"show {a.id}")
        assert a.id in out
        assert b.id not in out

    def test_unknown_subcommand(self) -> None:
        out = orch.run_decision_ledger("delete")
        assert "unknown subcommand" in out


class TestRunAiRadar:
    def test_help_when_no_payload(self) -> None:
        out = orch.run_ai_radar("")
        assert "Usage: /ai-radar" in out

    def test_update_writes_and_reports(self) -> None:
        out = orch.run_ai_radar("update")
        assert "snapshot written" in out
        home = Path(os.environ["HERMES_HOME"]) / "orchestrator"
        assert (home / "ai_radar.json").is_file()

    def test_unknown_subcommand(self) -> None:
        out = orch.run_ai_radar("download")
        assert "unknown subcommand" in out


class TestRunMission:
    def test_help_when_no_payload(self) -> None:
        out = orch.run_best_coding_tool_mission("")
        assert "Usage: /best-coding-tool-mission" in out

    def test_status_returns_mission_summary(self) -> None:
        orch.submit_job("alpha")
        out = orch.run_best_coding_tool_mission("status")
        assert "mission:" in out
        assert "jobs_submitted: 1" in out

    def test_unknown_subcommand(self) -> None:
        out = orch.run_best_coding_tool_mission("reset")
        assert "unknown subcommand" in out


# ---------------------------------------------------------------------------
# Phase 24: cancel / approve / validate / publish-plan
# ---------------------------------------------------------------------------

class TestCancelJob:
    def test_cancel_marks_job_cancelled(self) -> None:
        job = orch.submit_job("cancel me")
        cancelled = orch.cancel_job(job.id)
        assert cancelled is not None
        assert cancelled.status == "cancelled"
        assert cancelled.cancelled_at and cancelled.cancelled_at > 0

    def test_cancel_unknown_id_returns_none(self) -> None:
        assert orch.cancel_job("nope") is None

    def test_cancel_refuses_to_retract_published_job(self) -> None:
        job = orch.submit_job("publish first")
        orch.publish_job(job.id)
        after = orch.cancel_job(job.id)
        assert after is not None
        # Already published — status must not flip to cancelled.
        assert after.status == "published"


class TestApprovePhase:
    def test_approval_records_timestamp(self) -> None:
        job = orch.submit_job("approve me")
        approved = orch.approve_phase(job.id, "plan")
        assert approved is not None
        assert approved.approvals.get("plan") and approved.approvals["plan"] > 0
        assert orch.has_approval(approved, "plan")

    def test_unknown_phase_raises(self) -> None:
        job = orch.submit_job("bad phase")
        with pytest.raises(ValueError):
            orch.approve_phase(job.id, "teleport")

    def test_unknown_job_id_returns_none(self) -> None:
        assert orch.approve_phase("does-not-exist", "plan") is None


class TestValidateJob:
    def test_validate_returns_summary_for_known_job(self) -> None:
        job = orch.submit_job("validate me")
        summary = orch.validate_job(job.id)
        assert summary is not None
        assert summary["job_id"] == job.id
        # Either the runner returned counts or surfaced a note.
        assert "status_counts" in summary
        # Validation summary persisted next to jobs.
        from pathlib import Path
        home = Path(os.environ["HERMES_HOME"]) / "orchestrator"
        assert (home / "validation.json").is_file()

    def test_validate_unknown_id_returns_none(self) -> None:
        assert orch.validate_job("nope") is None

    def test_validate_appends_ledger_entry(self) -> None:
        job = orch.submit_job("ledger validate")
        orch.validate_job(job.id)
        entries = orch.get_ledger(job.id)[job.id]
        kinds = [e.get("kind") for e in entries]
        assert "validate" in kinds


class TestPublishPlan:
    def test_publish_plan_blocked_without_approval(self) -> None:
        job = orch.submit_job("plan me")
        result = orch.publish_plan(job.id)
        assert result["ok"] is False
        assert "approval required" in result["reason"] or "approve" in result["reason"]

    def test_publish_plan_succeeds_after_approval(self) -> None:
        job = orch.submit_job("approved plan")
        orch.approve_phase(job.id, "plan")
        result = orch.publish_plan(job.id)
        assert result["ok"] is True
        plan = result["plan"]
        assert plan["job_id"] == job.id
        # Status should bump to "plan_ready".
        refreshed = orch.get_job(job.id)
        assert refreshed is not None and refreshed.status == "plan_ready"

    def test_publish_plan_persists_to_disk(self) -> None:
        job = orch.submit_job("persist plan")
        orch.approve_phase(job.id, "plan")
        orch.publish_plan(job.id)
        from pathlib import Path
        home = Path(os.environ["HERMES_HOME"]) / "orchestrator"
        assert (home / "publish_plans.json").is_file()

    def test_publish_plan_blocked_by_failing_validation(self, monkeypatch) -> None:
        job = orch.submit_job("blocked plan")
        orch.approve_phase(job.id, "plan")
        # Stub a validation summary with a critical failure.
        summary = {
            job.id: {
                "job_id": job.id,
                "checked_at": 1,
                "status_counts": {"fail": 1},
                "publish_blocked": True,
                "checks": [],
            }
        }
        from pathlib import Path
        path = Path(os.environ["HERMES_HOME"]) / "orchestrator" / "validation.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary), encoding="utf-8")
        result = orch.publish_plan(job.id)
        assert result["ok"] is False
        assert "blocked by failing validation" in result["reason"]


# ---------------------------------------------------------------------------
# Phase 24: voice-capture, remote-worker, self-improve, profile
# ---------------------------------------------------------------------------

class TestVoiceCapture:
    def test_default_status_is_disabled(self) -> None:
        state = orch.voice_capture_status()
        assert state["mode"] == "disabled"

    @pytest.mark.parametrize("mode", [
        "push_to_talk", "wake_word", "driving_capture", "disabled",
    ])
    def test_set_mode_persists_and_tracks_history(self, mode: str) -> None:
        state = orch.set_voice_capture_mode(mode)
        assert state["mode"] == mode
        assert state["history"]
        # Reload from disk to confirm persistence.
        reloaded = orch.voice_capture_status()
        assert reloaded["mode"] == mode

    def test_set_mode_rejects_unknown_mode(self) -> None:
        with pytest.raises(ValueError):
            orch.set_voice_capture_mode("siri")


class TestRemoteWorker:
    def test_status_returns_placeholder_when_empty(self) -> None:
        snap = orch.remote_worker_status()
        assert snap["workers"] == []
        assert "No remote workers" in snap.get("note", "")

    def test_status_reads_local_registry(self) -> None:
        from pathlib import Path
        path = Path(os.environ["HERMES_HOME"]) / "orchestrator" / "remote_workers.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "workers": [
                {"id": "lab-host", "kind": "ssh", "status": "ready", "url": "ssh://lab"},
            ]
        }), encoding="utf-8")
        snap = orch.remote_worker_status()
        assert len(snap["workers"]) == 1
        assert snap["workers"][0]["id"] == "lab-host"


class TestSelfImprove:
    def test_run_blocked_without_approval(self) -> None:
        job = orch.submit_job("self-improve me")
        result = orch.self_improve_run(job.id)
        assert result["ok"] is False
        assert "approve" in result["reason"]

    def test_run_succeeds_after_approval(self) -> None:
        job = orch.submit_job("approve self_improve")
        orch.approve_phase(job.id, "self_improve")
        result = orch.self_improve_run(job.id)
        assert result["ok"] is True
        assert result["record"]["job_id"] == job.id
        # Persisted under self_improve.json.
        from pathlib import Path
        path = Path(os.environ["HERMES_HOME"]) / "orchestrator" / "self_improve.json"
        assert path.is_file()

    def test_run_unknown_job_returns_failure(self) -> None:
        result = orch.self_improve_run("nope")
        assert result["ok"] is False
        assert "unknown job id" in result["reason"]


class TestProfileBuildGithubHistory:
    def test_build_writes_snapshot(self) -> None:
        payload = orch.profile_build_github_history()
        assert payload["built_at"] > 0
        from pathlib import Path
        path = Path(os.environ["HERMES_HOME"]) / "orchestrator" / "profile_github_history.json"
        assert path.is_file()
        # Status reads the same file.
        loaded = orch.profile_github_history_status()
        assert loaded["built_at"] == payload["built_at"]


# ---------------------------------------------------------------------------
# Phase 24: slash entry points for the new commands
# ---------------------------------------------------------------------------

class TestRunOrchestratorPhase24Subs:
    def test_cancel_requires_id(self) -> None:
        out = orch.run_orchestrator("cancel")
        assert "requires a job id" in out

    def test_cancel_marks_job(self) -> None:
        job = orch.submit_job("cancel via slash")
        out = orch.run_orchestrator(f"cancel {job.id}")
        assert "cancelled" in out

    def test_approve_requires_phase(self) -> None:
        job = orch.submit_job("approve via slash")
        out = orch.run_orchestrator(f"approve {job.id}")
        assert "<job-id> <phase>" in out

    def test_approve_unknown_phase(self) -> None:
        job = orch.submit_job("approve via slash 2")
        out = orch.run_orchestrator(f"approve {job.id} teleport")
        assert "unknown approval phase" in out

    def test_approve_success(self) -> None:
        job = orch.submit_job("approve via slash 3")
        out = orch.run_orchestrator(f"approve {job.id} plan")
        assert "approved" in out
        assert "plan" in out

    def test_validate_returns_summary(self) -> None:
        job = orch.submit_job("validate via slash")
        out = orch.run_orchestrator(f"validate {job.id}")
        assert job.id in out
        assert "publish_blocked" in out

    def test_publish_plan_requires_approval(self) -> None:
        job = orch.submit_job("plan via slash")
        out = orch.run_orchestrator(f"publish-plan {job.id}")
        assert "approval" in out or "approve" in out

    def test_publish_plan_after_approval(self) -> None:
        job = orch.submit_job("plan via slash success")
        orch.run_orchestrator(f"approve {job.id} plan")
        out = orch.run_orchestrator(f"publish-plan {job.id}")
        assert "Publish-plan emitted" in out


class TestRunVoiceCapture:
    def test_help_when_empty(self) -> None:
        out = orch.run_voice_capture("")
        assert "Usage: /voice-capture" in out

    def test_status_default(self) -> None:
        out = orch.run_voice_capture("status")
        assert "mode:" in out
        assert "disabled" in out

    def test_mode_without_arg_returns_help(self) -> None:
        out = orch.run_voice_capture("mode")
        assert "Usage" in out or "requires a mode" in out

    @pytest.mark.parametrize("mode", [
        "push_to_talk", "wake_word", "driving_capture", "disabled",
    ])
    def test_mode_set(self, mode: str) -> None:
        out = orch.run_voice_capture(f"mode {mode}")
        assert mode in out

    def test_unknown_mode(self) -> None:
        out = orch.run_voice_capture("mode siri")
        assert "unknown voice-capture mode" in out

    def test_unknown_subcommand(self) -> None:
        out = orch.run_voice_capture("teleport")
        assert "unknown subcommand" in out


class TestRunRemoteWorker:
    def test_help_when_empty(self) -> None:
        out = orch.run_remote_worker("")
        assert "Usage: /remote-worker" in out

    def test_status_no_workers(self) -> None:
        out = orch.run_remote_worker("status")
        assert "workers:" in out

    def test_unknown_subcommand(self) -> None:
        out = orch.run_remote_worker("connect")
        assert "unknown subcommand" in out


class TestRunSelfImprove:
    def test_help_when_empty(self) -> None:
        out = orch.run_self_improve("")
        assert "Usage: /self-improve" in out

    def test_run_requires_id(self) -> None:
        out = orch.run_self_improve("run")
        assert "requires a job id" in out

    def test_run_blocked_without_approval(self) -> None:
        job = orch.submit_job("self-improve slash")
        out = orch.run_self_improve(f"run {job.id}")
        assert "approve" in out

    def test_run_succeeds_after_approval(self) -> None:
        job = orch.submit_job("self-improve slash 2")
        orch.run_orchestrator(f"approve {job.id} self_improve")
        out = orch.run_self_improve(f"run {job.id}")
        assert "staged" in out

    def test_unknown_subcommand(self) -> None:
        out = orch.run_self_improve("teleport")
        assert "unknown subcommand" in out


class TestRunProfile:
    def test_help_when_empty(self) -> None:
        out = orch.run_profile("")
        assert "Usage: /profile" in out

    def test_build_github_history(self) -> None:
        out = orch.run_profile("build-github-history")
        assert "GitHub-history snapshot written" in out

    def test_unknown_subcommand(self) -> None:
        out = orch.run_profile("teleport")
        assert "unknown subcommand" in out
