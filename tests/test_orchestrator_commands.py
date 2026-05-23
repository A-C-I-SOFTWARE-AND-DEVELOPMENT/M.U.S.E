"""Tests for the Phase 16 native orchestrator slash commands.

Covers:

* The CommandDef entries in :mod:`hermes_cli.commands`.
* The controller in :mod:`hermes_cli.orchestrator` (job CRUD, ledger,
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

from hermes_cli import orchestrator as orch
from hermes_cli.commands import (
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
        ("orchestrator", ("status", "list", "open", "resume", "publish")),
        ("model-router", ("explain",)),
        ("decision-ledger", ("show",)),
        ("ai-radar", ("update",)),
        ("best-coding-tool-mission", ("status",)),
    ])
    def test_subcommand_registry(self, name: str, subs: tuple[str, ...]) -> None:
        cmd = resolve_command(name)
        assert cmd is not None, f"missing CommandDef for /{name}"
        assert cmd.subcommands == subs
        # Subcommand lookup must be wired so tab-completion sees them.
        assert SUBCOMMANDS.get(f"/{name}") == list(subs)

    def test_all_orchestrator_commands_are_cli_only(self) -> None:
        # Phase 16 leaves all six commands cli_only to avoid bumping
        # aliases like /q and /btw off Slack's 50-slash cap. They remain
        # discoverable via /help, the tab-completer, and prefix matching
        # in :func:`HermesCLI.process_command`.
        for name in (
            "orchestrate",
            "orchestrator",
            "model-router",
            "decision-ledger",
            "ai-radar",
            "best-coding-tool-mission",
        ):
            cmd = resolve_command(name)
            assert cmd is not None and cmd.cli_only, (
                f"/{name} should be cli_only in Phase 16"
            )

    def test_no_orchestrator_command_appears_in_gateway_set(self) -> None:
        # GATEWAY_KNOWN_COMMANDS excludes cli_only entries (unless
        # gateway_config_gate is set). Sanity-check that Phase 16's
        # orchestrator commands are not silently surfaced.
        for name in (
            "orchestrate",
            "orchestrator",
            "model-router",
            "decision-ledger",
            "ai-radar",
            "best-coding-tool-mission",
        ):
            assert name not in GATEWAY_KNOWN_COMMANDS, (
                f"/{name} unexpectedly appears in GATEWAY_KNOWN_COMMANDS"
            )

    def test_no_orchestrator_command_collides_with_existing_names(self) -> None:
        # Each canonical name appears exactly once.
        new_names = {
            "orchestrate", "orchestrator", "model-router",
            "decision-ledger", "ai-radar", "best-coding-tool-mission",
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
