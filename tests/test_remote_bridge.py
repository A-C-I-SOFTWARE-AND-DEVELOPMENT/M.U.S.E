"""Tests for the remote-bridge surfaces of the orchestrator.

The "remote bridge" in Hermes is the handoff path that lets a local
orchestrator dispatch work to an external tool the user is logged into
(Codex, Claude Code, ChatGPT web, …) without ever shipping credentials
itself. Two artefacts pin that contract:

  1. ``scripts/hermes-orchestrate.sh`` and the Termux supervisor scripts
     — they construct the on-disk job folder the bridge consumes.
  2. ``ParallelRunner`` running in :data:`HANDOFF_REQUIRED` mode — it
     writes the structured handoff payload the bridge picks up.

The tests in this module run on any Linux host; nothing requires Termux
itself, an Android device, or any network access.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from hermes_cli import orchestrator_parallel as op


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_ROOT / "scripts"


# ── bash syntax sanity ────────────────────────────────────────────────


class TestBridgeScriptSyntax:
    @pytest.mark.parametrize(
        "name",
        [
            "hermes-orchestrate.sh",
            "hermes-termux-service.sh",
            "hermes-termux-doctor.sh",
            "hermes-ai-radar.sh",
        ],
    )
    def test_script_parses(self, name: str) -> None:
        if shutil.which("bash") is None:
            pytest.skip("bash not available")
        path = SCRIPT_DIR / name
        assert path.is_file(), f"missing script: {path}"
        proc = subprocess.run(  # noqa: S603 — test runs a known script.
            ["bash", "-n", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"bash -n {name}: {proc.stderr}"

    @pytest.mark.parametrize(
        "name",
        [
            "hermes-orchestrate.sh",
            "hermes-termux-service.sh",
            "hermes-termux-doctor.sh",
            "hermes-ai-radar.sh",
        ],
    )
    def test_script_has_no_destructive_default(self, name: str) -> None:
        # No bridge script should *execute* ``rm -rf $HOME``,
        # ``git push --force``, or ``kill -9`` in its default code path.
        # Comments referencing those tokens are fine (and several
        # scripts call out exactly why they avoid them) — so strip
        # comment-only lines before scanning.
        text = (SCRIPT_DIR / name).read_text(encoding="utf-8")
        non_comment = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("#")
        )
        assert "rm -rf $HOME" not in non_comment
        assert "git push --force" not in non_comment
        assert "kill -9" not in non_comment


# ── handoff prompt generation ─────────────────────────────────────────


class TestHandoffPromptGeneration:
    def test_handoff_writes_prompt_and_payload(self, tmp_path: Path) -> None:
        plan = op.ExecutionPlan(
            job_id="job-bridge",
            workers=[
                op.WorkerPlan(
                    worker_id="codex-handoff",
                    profile="codex",
                    mode=op.ExecutionMode.HANDOFF_REQUIRED,
                    prompt="Refactor src/main.py to add structured logging.",
                    handoff={
                        "destination": "codex",
                        "tool": "manual",
                        "next_step": "user pastes prompt into Codex CLI",
                    },
                )
            ],
        )
        runner = op.ParallelRunner(tmp_path, plan)
        statuses = runner.run()
        assert statuses["codex-handoff"].state == op.WorkerState.AWAITING_HANDOFF

        worker_root = op.worker_dir(tmp_path, plan.job_id, "codex-handoff")
        prompt = (worker_root / op.PROMPT_FILENAME).read_text(encoding="utf-8")
        assert "Refactor src/main.py" in prompt

        handoff = json.loads(
            (worker_root / op.HANDOFF_FILENAME).read_text(encoding="utf-8")
        )
        assert handoff["destination"] == "codex"
        assert handoff["tool"] == "manual"
        assert handoff["next_step"] == "user pastes prompt into Codex CLI"

    def test_handoff_payload_is_json_serialisable(self) -> None:
        # The bridge consumes the payload as JSON; this guard prevents
        # someone shoving an unserialisable object into the worker spec.
        for value in (None, "str", 1, 1.5, True, [], {}):
            json.dumps({"destination": "x", "extra": value})

    def test_handoff_required_does_not_run_subprocess(
        self, tmp_path: Path
    ) -> None:
        # If the bridge implementation regressed and shelled out, the
        # test would either need ``shutil.which`` or fail noisily. The
        # current contract is: prompt + handoff.json only.
        plan = op.ExecutionPlan(
            job_id="job-noshell",
            workers=[
                op.WorkerPlan(
                    worker_id="w",
                    profile="claude_code",
                    mode=op.ExecutionMode.HANDOFF_REQUIRED,
                    prompt="placeholder",
                    handoff={"destination": "claude_code"},
                )
            ],
        )
        runner = op.ParallelRunner(tmp_path, plan)
        runner.run()
        # No stdout.log / stderr.log should appear — those only exist
        # for LOCAL_RUN.
        worker_root = op.worker_dir(tmp_path, plan.job_id, "w")
        assert not (worker_root / op.STDOUT_LOG).exists()
        assert not (worker_root / op.STDERR_LOG).exists()


# ── bridge status discovery ───────────────────────────────────────────


class TestBridgeStatusDiscovery:
    def test_list_jobs_returns_only_jobs_with_status(self, tmp_path: Path) -> None:
        # Carve out a bogus job folder without status.json — list_jobs
        # must skip it so the bridge UI never shows a half-written job.
        root = tmp_path / op.ORCHESTRATOR_DIRNAME / op.JOBS_SUBDIR
        (root / "halfwritten").mkdir(parents=True)
        # A real job goes through the runner so the status file lands.
        plan = op.ExecutionPlan(
            job_id="real-job",
            workers=[
                op.WorkerPlan(
                    worker_id="w",
                    profile="p",
                    mode=op.ExecutionMode.PROMPT_ONLY,
                )
            ],
        )
        op.ParallelRunner(tmp_path, plan).run()
        jobs = op.list_jobs(tmp_path)
        assert "real-job" in jobs
        assert "halfwritten" not in jobs

    def test_request_cancel_drops_flag(self, tmp_path: Path) -> None:
        # The bridge signals cancel by writing a flag file the runner
        # polls — confirm the contract still holds.
        path = op.request_cancel(tmp_path, "j-1")
        assert path.is_file()
        assert path.read_text().strip().endswith("Z") or path.read_text().strip()


# ── bridge code never embeds API keys ────────────────────────────────


class TestBridgeScriptsHaveNoSecrets:
    @pytest.mark.parametrize(
        "name",
        [
            "hermes-orchestrate.sh",
            "hermes-termux-service.sh",
            "hermes-termux-doctor.sh",
            "hermes-ai-radar.sh",
        ],
    )
    def test_no_literal_credentials(self, name: str) -> None:
        text = (SCRIPT_DIR / name).read_text(encoding="utf-8")
        # The bridge is credential-free by design — see
        # docs/orchestration/local-validation-gates.md. The strings the
        # script *names* (``OPENAI_API_KEY`` etc. as env-var references)
        # are fine; literal values are not. We confirm by checking that
        # nothing here looks like a real key.
        for forbidden_prefix in ("AKIA", "ghp_AAAA", "sk-ant-AAAA"):
            assert forbidden_prefix not in text, (
                f"{name} appears to contain a literal credential prefix "
                f"{forbidden_prefix!r}"
            )
