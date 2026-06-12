"""Tests for the ChatGPT manual-handoff worker adapter.

The adapter is intentionally execution-free: ChatGPT has no headless
CLI we can drive against a user's own subscription, so every run path
ends in ``WorkerStatus.HANDOFF_REQUIRED``. These tests pin that
contract plus the prompt shape, the artifact-collection helper, and
the score stub.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hermes_cli.workers import WorkerStatus, WorkerTask
from hermes_cli.workers import chatgpt_handoff as worker


def _task(**overrides: Any) -> WorkerTask:
    defaults: dict[str, Any] = {
        "title": "Pre-merge review of the auth refactor",
        "instructions": (
            "Skim the PR description below and give me a strategic "
            "go/no-go plus product/UX notes I would not get from a "
            "code-only review."
        ),
        "files": ["docs/auth-refactor.md", "app/auth.py"],
        "context": "PR #1234 — replaces session cookies with signed JWTs.",
        "acceptance_criteria": [
            "Recommendation in first paragraph",
            "Open questions section present",
        ],
    }
    defaults.update(overrides)
    return WorkerTask(**defaults)


# ── prompt rendering ──────────────────────────────────────────────────


class TestPromptRendering:
    def test_prompt_includes_all_required_sections(self):
        prompt = worker.render_prompt(_task())
        assert "# Pre-merge review of the auth refactor" in prompt
        assert "## Task" in prompt
        assert "## Files in scope" in prompt
        assert "docs/auth-refactor.md" in prompt
        assert "## Context" in prompt
        assert "## Acceptance criteria" in prompt
        assert "## What we want from you" in prompt
        assert "## Response format" in prompt
        assert "## Guardrails" in prompt
        # Roles framing the worker is intended for must be in the body.
        assert "product/UX/strategy/final review" in prompt
        # Manual-handoff framing must be explicit so ChatGPT does not
        # claim to have run anything.
        assert "manually" in prompt.lower()
        assert "do not claim to have run anything" in prompt.lower()
        # Destructive shortcuts MUST be explicitly forbidden.
        assert "git reset --hard" in prompt
        assert "git push --force" in prompt

    def test_prompt_handles_empty_optional_fields(self):
        prompt = worker.render_prompt(WorkerTask(title="t", instructions="i"))
        assert "# t" in prompt
        assert "## Files in scope" not in prompt
        assert "## Context" not in prompt
        assert "## Acceptance criteria" not in prompt

    def test_prompt_blank_title_does_not_crash(self):
        prompt = worker.render_prompt(WorkerTask(title="   ", instructions="   "))
        assert "Untitled task" in prompt
        assert "(no instructions provided)" in prompt

    def test_prompt_role_override_appears_in_body(self):
        cfg = worker.ChatGPTHandoffConfig(role="strategy")
        prompt = worker.render_prompt(_task(), config=cfg)
        assert "**strategy**" in prompt
        # Default role string should NOT also appear when overridden.
        assert "**product/UX/strategy/final review**" not in prompt

    def test_prompt_blank_role_falls_back_to_default(self):
        cfg = worker.ChatGPTHandoffConfig(role="   ")
        prompt = worker.render_prompt(_task(), config=cfg)
        assert "product/UX/strategy/final review" in prompt


# ── handoff path ──────────────────────────────────────────────────────


class TestHandoffPath:
    def test_run_returns_handoff_required(self, tmp_path: Path):
        result = worker.run(_task(), tmp_path / "ws")
        assert result.status is WorkerStatus.HANDOFF_REQUIRED
        assert result.worker == "chatgpt-handoff"
        # No CLI exists for ChatGPT; command_available must be False.
        assert result.command_available is False
        assert result.prompt_path.exists()
        assert result.status_path.exists()
        # No execution artifacts are ever produced by this worker.
        assert result.output_path is None
        assert result.patch_path is None
        assert result.changed_files_path is None
        assert result.exit_code is None
        assert result.error is None

    def test_handoff_command_describes_manual_paste(self, tmp_path: Path):
        result = worker.run(_task(), tmp_path / "ws")
        assert result.handoff_command is not None
        # The "command" is human-readable instructions, not a shell line.
        assert "prompt.md" in result.handoff_command
        assert "response.md" in result.handoff_command
        # We must NOT pretend there is a binary to run.
        assert "$ " not in result.handoff_command
        assert "chatgpt --" not in result.handoff_command

    def test_handoff_command_uses_deep_link_when_provided(self, tmp_path: Path):
        cfg = worker.ChatGPTHandoffConfig(deep_link="https://chat.openai.com/g/foo")
        result = worker.run(_task(), tmp_path / "ws", config=cfg)
        assert result.handoff_command is not None
        assert "https://chat.openai.com/g/foo" in result.handoff_command

    def test_prompt_written_matches_render_prompt(self, tmp_path: Path):
        result = worker.run(_task(), tmp_path / "ws")
        on_disk = result.prompt_path.read_text(encoding="utf-8")
        assert on_disk == worker.render_prompt(_task())

    def test_status_json_is_machine_readable(self, tmp_path: Path):
        result = worker.run(_task(), tmp_path / "ws")
        data = json.loads(result.status_path.read_text(encoding="utf-8"))
        assert data["worker"] == "chatgpt-handoff"
        assert data["status"] == "handoff_required"
        assert data["command_available"] is False
        assert data["role"] == worker.DEFAULT_ROLE
        assert data["response_filename"] == worker.RESPONSE_FILENAME
        assert data["deep_link"] is None
        assert "expected_artifacts" in data
        assert "prompt.md" in data["expected_artifacts"]
        assert "status.json" in data["expected_artifacts"]
        assert worker.RESPONSE_FILENAME in data["expected_artifacts"]
        assert data["handoff_instructions"]
        assert data["created_at"]
        assert "timestamp" in data

    def test_custom_response_filename_propagates(self, tmp_path: Path):
        cfg = worker.ChatGPTHandoffConfig(response_filename="reply.md")
        result = worker.run(_task(), tmp_path / "ws", config=cfg)
        data = json.loads(result.status_path.read_text(encoding="utf-8"))
        assert data["response_filename"] == "reply.md"
        assert "reply.md" in data["expected_artifacts"]
        assert result.handoff_command is not None
        assert "reply.md" in result.handoff_command

    def test_run_is_idempotent(self, tmp_path: Path):
        """Two runs into the same workspace should overwrite cleanly."""
        ws = tmp_path / "ws"
        worker.run(_task(), ws)
        result = worker.run(_task(title="Second pass"), ws)
        prompt = result.prompt_path.read_text(encoding="utf-8")
        assert "# Second pass" in prompt
        assert "# Pre-merge review of the auth refactor" not in prompt


# ── artifact collection ──────────────────────────────────────────────


class TestCollectArtifacts:
    def test_collect_before_handoff_returns_pending_note(self, tmp_path: Path):
        ws = tmp_path / "ws"
        worker.run(_task(), ws)
        artifacts = worker.collect_artifacts(ws)
        assert "prompt.md" in " ".join(artifacts.files)
        assert "status.json" in " ".join(artifacts.files)
        assert artifacts.details["response_present"] is False
        assert "pending" in artifacts.notes.lower()

    def test_collect_includes_response_when_present(self, tmp_path: Path):
        ws = tmp_path / "ws"
        worker.run(_task(), ws)
        (ws / worker.RESPONSE_FILENAME).write_text("**Recommendation**: ship it.\n")
        (ws / worker.NOTES_FILENAME).write_text("Reviewer was happy.\n")
        artifacts = worker.collect_artifacts(ws)
        joined = " ".join(artifacts.files)
        assert worker.RESPONSE_FILENAME in joined
        assert worker.NOTES_FILENAME in joined
        assert artifacts.details["response_present"] is True
        assert artifacts.notes == ""

    def test_collect_honours_custom_response_filename(self, tmp_path: Path):
        ws = tmp_path / "ws"
        cfg = worker.ChatGPTHandoffConfig(response_filename="reply.md")
        worker.run(_task(), ws, config=cfg)
        (ws / "reply.md").write_text("ok\n")
        artifacts = worker.collect_artifacts(ws, config=cfg)
        assert artifacts.details["response_filename"] == "reply.md"
        assert artifacts.details["response_present"] is True
        assert any(name.endswith("reply.md") for name in artifacts.files)

    def test_collect_does_not_duplicate_files(self, tmp_path: Path):
        ws = tmp_path / "ws"
        worker.run(_task(), ws)
        (ws / worker.RESPONSE_FILENAME).write_text("x\n")
        artifacts = worker.collect_artifacts(ws)
        # ``files`` should be deduped even though the default response
        # filename appears in both the static list and the config-driven
        # extras.
        assert len(artifacts.files) == len(set(artifacts.files))


# ── score stub ───────────────────────────────────────────────────────


class TestScoreStub:
    def test_score_pending_handoff_is_zero(self, tmp_path: Path):
        ws = tmp_path / "ws"
        worker.run(_task(), ws)
        artifacts = worker.collect_artifacts(ws)
        score = worker.score(artifacts)
        assert score.value == 0.0
        assert score.confidence == 0.0
        assert "pending" in score.rationale.lower()

    def test_score_with_response_is_placeholder(self, tmp_path: Path):
        ws = tmp_path / "ws"
        worker.run(_task(), ws)
        (ws / worker.RESPONSE_FILENAME).write_text("recommendation: ship\n")
        artifacts = worker.collect_artifacts(ws)
        score = worker.score(artifacts)
        # The placeholder value must be inside the documented [0, 1] range.
        assert 0.0 <= score.value <= 1.0
        assert score.value == 0.5
        assert score.confidence > 0.0
        assert "stub" in score.rationale.lower()

    def test_score_clamps_component_axes(self, tmp_path: Path):
        ws = tmp_path / "ws"
        worker.run(_task(), ws)
        (ws / worker.RESPONSE_FILENAME).write_text("x\n")
        artifacts = worker.collect_artifacts(ws)
        score = worker.score(artifacts, components={"strategy": 1.7, "ux": -0.4})
        assert score.components["strategy"] == 1.0
        assert score.components["ux"] == 0.0

    def test_score_ignores_non_numeric_components(self, tmp_path: Path):
        ws = tmp_path / "ws"
        worker.run(_task(), ws)
        (ws / worker.RESPONSE_FILENAME).write_text("x\n")
        artifacts = worker.collect_artifacts(ws)
        bad: dict[str, float] = {"strategy": "n/a"}  # type: ignore[dict-item]  # ty: ignore[invalid-assignment]  # mock/duck-typed test fixture
        score = worker.score(artifacts, components=bad)
        assert score.components["strategy"] == 0.0


# ── misc ─────────────────────────────────────────────────────────────


def test_no_execute_kwarg_exists():
    """The adapter must not accept an ``execute`` parameter — it would
    suggest there is an automation path, and there is not."""
    import inspect

    sig = inspect.signature(worker.run)
    assert "execute" not in sig.parameters


def test_module_is_importable():
    import hermes_cli.workers.chatgpt_handoff as _  # noqa: F401


@pytest.mark.parametrize(
    "role",
    ["product", "ux", "strategy", "final review", "product/UX/strategy/final review"],
)
def test_role_string_passes_through_to_prompt(role: str):
    cfg = worker.ChatGPTHandoffConfig(role=role)
    prompt = worker.render_prompt(_task(), config=cfg)
    assert role in prompt
