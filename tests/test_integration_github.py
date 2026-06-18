"""Tests for the GitHub integration adapter.

The adapter is a thin façade over `hermes_cli.github_publisher`, so
these tests focus on the *adapter contract* — detect → plan → explain
→ execute — rather than re-testing publisher internals (those are
covered by ``tests/test_github_publisher.py``).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from hermes_cli.integrations import github as gh_int


_HAS_GIT = shutil.which("git") is not None
requires_git = pytest.mark.skipif(not _HAS_GIT, reason="git not on PATH")


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        text=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    if not _HAS_GIT:
        pytest.skip("git not on PATH")
    root = tmp_path / "repo"
    root.mkdir()
    _git("init", "-q", "-b", "main", cwd=root)
    _git("config", "user.email", "tester@example.com", cwd=root)
    _git("config", "user.name", "Tester", cwd=root)
    _git("config", "commit.gpgsign", "false", cwd=root)
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    _git("add", "README.md", cwd=root)
    _git("commit", "-q", "-m", "initial", cwd=root)
    return root


class TestDetect:
    def test_detect_returns_detection_dataclass(self) -> None:
        det = gh_int.detect()
        assert isinstance(det, gh_int.Detection)
        # Booleans, never None
        assert isinstance(det.cli_present, bool)
        assert isinstance(det.git_present, bool)
        assert isinstance(det.notes, list)

    def test_detect_notes_when_gh_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gh_int.shutil, "which", lambda name: None)
        det = gh_int.detect()
        assert det.cli_present is False
        assert det.cli_path is None
        assert det.git_present is False
        assert any("gh" in n for n in det.notes)
        assert any("git" in n for n in det.notes)

    def test_detect_makes_no_network_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Sanity: detect must not import anything that hits a socket.
        # Verified by replacing socket.socket and confirming detect()
        # doesn't trigger it.
        import socket

        def _no(*a, **kw):  # noqa: ANN001, ANN002, ANN003
            raise AssertionError("detect() must not open sockets")

        monkeypatch.setattr(socket, "socket", _no)
        gh_int.detect()


@requires_git
class TestPlan:
    def test_plan_returns_frozen_dataclass(self, repo: Path) -> None:
        plan = gh_int.plan(
            job_id="abc-123",
            files=["README.md"],
            commit_message="docs: tweak README",
            repo_root=repo,
        )
        assert isinstance(plan, gh_int.GitHubPlan)
        # Frozen — confirmed via dataclass params so the static checker
        # doesn't flag the deliberately-invalid assignment style.
        import dataclasses

        assert dataclasses.is_dataclass(plan)
        assert plan.__dataclass_params__.frozen is True

    def test_plan_has_branch_namespaced_under_hermes_job(self, repo: Path) -> None:
        plan = gh_int.plan(
            job_id="my-job",
            files=["README.md"],
            commit_message="x",
            repo_root=repo,
        )
        assert plan.branch.startswith("hermes/job-")
        assert "my-job" in plan.branch

    def test_plan_defaults_to_dry_run_and_requires_approval(self, repo: Path) -> None:
        plan = gh_int.plan(
            job_id="j",
            files=["README.md"],
            commit_message="x",
            repo_root=repo,
        )
        assert plan.dry_run is True
        assert plan.approval_required is True

    def test_plan_push_command_is_argv_list(self, repo: Path) -> None:
        plan = gh_int.plan(
            job_id="j", files=["README.md"], commit_message="x", repo_root=repo
        )
        assert isinstance(plan.push_command, list)
        assert plan.push_command[0:3] == ["git", "push", "-u"]
        assert plan.push_command[3] == "origin"

    def test_plan_includes_rollback_and_validation(self, repo: Path) -> None:
        plan = gh_int.plan(
            job_id="j", files=["README.md"], commit_message="x", repo_root=repo
        )
        assert plan.rollback_notes
        assert plan.validation_steps
        # Rollback must mention `--delete` (the canonical rollback)
        assert any("--delete" in n for n in plan.rollback_notes)

    def test_plan_uses_first_line_of_message_as_pr_title(self, repo: Path) -> None:
        plan = gh_int.plan(
            job_id="j",
            files=["README.md"],
            commit_message="add feature X\n\nlong body here",
            repo_root=repo,
        )
        assert plan.pr_title == "add feature X"

    def test_plan_pr_title_override(self, repo: Path) -> None:
        plan = gh_int.plan(
            job_id="j",
            files=["README.md"],
            commit_message="commit msg",
            pr_title="Different PR title",
            repo_root=repo,
        )
        assert plan.pr_title == "Different PR title"

    def test_plan_pr_body_contains_provenance(self, repo: Path) -> None:
        plan = gh_int.plan(
            job_id="prov-job",
            files=["README.md"],
            commit_message="x",
            repo_root=repo,
        )
        assert "prov-job" in plan.pr_body
        assert "Provenance" in plan.pr_body


@requires_git
class TestExplain:
    def test_explain_is_pure_markdown_string(self, repo: Path) -> None:
        plan = gh_int.plan(
            job_id="j", files=["README.md"], commit_message="x", repo_root=repo
        )
        rendered = gh_int.explain(plan)
        assert isinstance(rendered, str)
        assert rendered.startswith("### GitHub publish plan")
        assert plan.branch in rendered
        assert "Rollback" in rendered
        assert "Validation" in rendered.replace("validate", "Validation")  # case-insensitive-ish

    def test_explain_mentions_approval_requirement(self, repo: Path) -> None:
        plan = gh_int.plan(
            job_id="j", files=["README.md"], commit_message="x", repo_root=repo
        )
        rendered = gh_int.explain(plan)
        assert "Approval required" in rendered

    def test_explain_warns_when_gh_missing(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Force gh_available to return False even if gh is installed.
        from hermes_cli import github_publisher

        monkeypatch.setattr(github_publisher, "gh_available", lambda: False)
        plan = gh_int.plan(
            job_id="j", files=["README.md"], commit_message="x", repo_root=repo
        )
        assert plan.cli_present is False
        assert plan.pr_create_command is None
        rendered = gh_int.explain(plan)
        assert "gh not present" in rendered or "manually" in rendered


@requires_git
class TestExecute:
    def test_execute_refuses_without_approval(self, repo: Path) -> None:
        plan = gh_int.plan(
            job_id="j", files=["README.md"], commit_message="x", repo_root=repo
        )
        result = gh_int.execute(plan)
        assert result.executed is False
        assert result.pushed is False
        assert result.errors == ["approve=False — refused to execute"]
        assert result.artifact_dir is None

    def test_execute_with_approval_runs_but_push_fails_without_remote(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # HERMES_PUBLISH_LIVE is the network gate; set it so the push is actually
        # attempted (and then fails because there's no origin).
        monkeypatch.setenv("HERMES_PUBLISH_LIVE", "1")
        # Add a new file to commit
        (repo / "new.txt").write_text("hi\n", encoding="utf-8")
        plan = gh_int.plan(
            job_id="exec-job",
            files=["new.txt"],
            commit_message="add new.txt",
            repo_root=repo,
        )
        result = gh_int.execute(plan, approve=True, repo_root=repo)
        # Branch + commit succeed; push fails because there's no origin
        assert result.executed is True
        assert result.pushed is False
        assert any("push" in e for e in result.errors)
        # Artifacts were still written
        assert result.artifact_dir is not None
        assert (result.artifact_dir / "publish-plan.md").is_file()


class TestSecretBlocking:
    def test_secret_filename_blocks_at_plan_time_or_execute_time(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # We don't need a real repo for this — we test that scan_for_secrets
        # (imported via the integration) catches a .env filename.
        from hermes_cli import github_publisher

        findings = github_publisher.scan_for_secrets(
            [".env"], repo_root=tmp_path, scan_contents=False
        )
        assert ".env" in findings
        assert "blocked filename" in findings[".env"]


class TestIntegrationsRegistry:
    def test_available_integrations_lists_github(self) -> None:
        from hermes_cli.integrations import available_integrations

        avail = available_integrations()
        assert "github" in avail
        assert isinstance(avail["github"], bool)
