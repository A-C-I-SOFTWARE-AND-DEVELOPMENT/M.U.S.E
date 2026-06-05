"""Tests for hermes_cli.github_publisher.

The publisher runtime has three classes of behaviour we care about:

1. **Pure helpers** (slugify, branch_name_for_job, prepare_pr_body,
   build_gh_pr_create_command, scan_for_secrets) — exercised in
   isolation. No git, no filesystem mutations beyond a tempdir.
2. **Git plumbing** (get_repo_info, get_current_branch, get_status,
   stage_files, commit, create_branch) — exercised against a real
   ephemeral git repo created in the test's tempdir. We skip these if
   ``git`` isn't on PATH instead of mocking, because the value of the
   test is precisely that we're driving real git.
3. **End-to-end ``run()``** — runs in plan-only mode (``approve=False``)
   against a tempdir repo, and verifies the six artifact files.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hermes_cli import github_publisher as gp


# ── helpers ──────────────────────────────────────────────────────────────────


def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        text=True,
        capture_output=True,
    )
    return proc.stdout


_HAS_GIT = shutil.which("git") is not None
requires_git = pytest.mark.skipif(not _HAS_GIT, reason="git not on PATH")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A fresh git repo with one initial commit on ``main``."""
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


# ── branch-name generation ───────────────────────────────────────────────────


class TestBranchName:
    def test_basic_slugify(self) -> None:
        assert gp.slugify("Hello World") == "hello-world"

    def test_slugify_strips_punctuation_and_consecutive_dashes(self) -> None:
        assert gp.slugify("kanban/2026-05-23 #001!!") == "kanban-2026-05-23-001"

    def test_slugify_empty_becomes_job(self) -> None:
        assert gp.slugify("") == "job"
        assert gp.slugify("!!!") == "job"

    def test_slugify_truncates(self) -> None:
        s = gp.slugify("a" * 200, max_len=20)
        assert len(s) <= 20
        # All "a"s — no trailing dash to strip
        assert s == "a" * 20

    def test_branch_name_for_job_uses_prefix(self) -> None:
        name = gp.branch_name_for_job("kanban-2026-05-23-001")
        assert name == "hermes/job-kanban-2026-05-23-001"

    def test_branch_name_for_job_sanitizes(self) -> None:
        name = gp.branch_name_for_job("Some Job / With Spaces!")
        # exactly one slash (the prefix) and only [a-z0-9-] after it
        prefix, _, slug = name.partition("/")
        assert prefix == "hermes"
        assert "/" not in slug
        assert all(c.islower() or c.isdigit() or c in "-_" for c in slug)

    def test_branch_name_deterministic(self) -> None:
        assert gp.branch_name_for_job("abc") == gp.branch_name_for_job("abc")


# ── PR body rendering ────────────────────────────────────────────────────────


class TestPrepareBody:
    def test_minimal_body_includes_provenance_and_job_id(self) -> None:
        body = gp.prepare_pr_body("job-42")
        assert "## Summary" in body
        assert "## Test plan" in body
        assert "## Provenance" in body
        assert "`job-42`" in body
        # Default summary used when none provided
        assert "Hermes job `job-42`" in body

    def test_body_with_all_sections(self) -> None:
        body = gp.prepare_pr_body(
            "job-99",
            summary="Adds widgets.",
            changes=["add widget", "wire widget into UI"],
            test_plan=["pytest", "manual smoke"],
            notes="Rolls back cleanly with the documented commands.",
        )
        assert "Adds widgets." in body
        assert "- add widget" in body
        assert "- wire widget into UI" in body
        assert "- [ ] pytest" in body
        assert "- [ ] manual smoke" in body
        assert "## Notes" in body
        assert "Rolls back cleanly" in body
        # Sections are in expected order
        assert body.index("## Summary") < body.index("## Changes")
        assert body.index("## Changes") < body.index("## Test plan")
        assert body.index("## Test plan") < body.index("## Notes")
        assert body.index("## Notes") < body.index("## Provenance")

    def test_body_omits_changes_when_empty(self) -> None:
        body = gp.prepare_pr_body("job-1", changes=[" ", ""])
        assert "## Changes" not in body

    def test_body_default_test_plan_when_empty(self) -> None:
        body = gp.prepare_pr_body("job-1")
        assert "- [ ] Reviewer confirms automated changes." in body

    def test_decision_block_present_with_verdict_id(self) -> None:
        body = gp.prepare_pr_body("job-7", verdict_id="dv_abc123", decision_tier="ask")
        assert "## Decision" in body
        assert "`dv_abc123`" in body
        assert "tier: ask" in body
        assert body.index("## Decision") < body.index("## Provenance")

    def test_decision_block_absent_by_default(self) -> None:
        # additive: callers that don't pass a verdict get the prior output
        assert "## Decision" not in gp.prepare_pr_body("job-7")


# ── secret blocking ──────────────────────────────────────────────────────────


class TestSecretBlocking:
    def test_blocks_dotenv_filename(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("X=1\n", encoding="utf-8")
        findings = gp.scan_for_secrets([".env"], repo_root=tmp_path)
        assert ".env" in findings
        assert "filename" in findings[".env"]

    def test_blocks_dotenv_variants(self, tmp_path: Path) -> None:
        for name in (".env.production", ".env.local", ".env.staging"):
            (tmp_path / name).write_text("X=1\n", encoding="utf-8")
        findings = gp.scan_for_secrets(
            [".env.production", ".env.local", ".env.staging"],
            repo_root=tmp_path,
        )
        assert set(findings.keys()) == {
            ".env.production",
            ".env.local",
            ".env.staging",
        }

    def test_blocks_pem_extension(self, tmp_path: Path) -> None:
        (tmp_path / "deploy.pem").write_text("nothing here", encoding="utf-8")
        findings = gp.scan_for_secrets(["deploy.pem"], repo_root=tmp_path)
        assert "deploy.pem" in findings
        assert "extension" in findings["deploy.pem"]

    def test_blocks_secrets_directory_fragment(self, tmp_path: Path) -> None:
        d = tmp_path / "secrets"
        d.mkdir()
        (d / "config.yaml").write_text("a: 1\n", encoding="utf-8")
        findings = gp.scan_for_secrets(["secrets/config.yaml"], repo_root=tmp_path)
        assert "secrets/config.yaml" in findings

    def test_blocks_github_pat_in_content(self, tmp_path: Path) -> None:
        bad = tmp_path / "src.py"
        bad.write_text("TOKEN = 'ghp_" + "A" * 30 + "'\n", encoding="utf-8")
        findings = gp.scan_for_secrets(["src.py"], repo_root=tmp_path)
        assert "src.py" in findings
        assert "GitHub PAT" in findings["src.py"]

    def test_blocks_aws_access_key_in_content(self, tmp_path: Path) -> None:
        bad = tmp_path / "deploy.sh"
        bad.write_text("export AWS_KEY=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")
        findings = gp.scan_for_secrets(["deploy.sh"], repo_root=tmp_path)
        assert "deploy.sh" in findings

    def test_blocks_private_key_pem_block_in_content(self, tmp_path: Path) -> None:
        bad = tmp_path / "key.txt"
        bad.write_text(
            "-----BEGIN RSA PRIVATE KEY-----\nMIIB...\n-----END RSA PRIVATE KEY-----\n",
            encoding="utf-8",
        )
        findings = gp.scan_for_secrets(["key.txt"], repo_root=tmp_path)
        assert "key.txt" in findings

    def test_clean_file_is_not_blocked(self, tmp_path: Path) -> None:
        (tmp_path / "ok.py").write_text("print('hello')\n", encoding="utf-8")
        assert gp.scan_for_secrets(["ok.py"], repo_root=tmp_path) == {}

    def test_content_scan_can_be_disabled(self, tmp_path: Path) -> None:
        bad = tmp_path / "src.py"
        bad.write_text("TOKEN='ghp_" + "A" * 40 + "'\n", encoding="utf-8")
        findings = gp.scan_for_secrets(
            ["src.py"], repo_root=tmp_path, scan_contents=False
        )
        assert findings == {}

    @requires_git
    def test_stage_files_raises_secret_blocked(self, repo: Path) -> None:
        (repo / ".env").write_text("SECRET=1\n", encoding="utf-8")
        with pytest.raises(gp.SecretBlocked) as excinfo:
            gp.stage_files([".env"], repo_root=repo, dry_run=True)
        assert ".env" in str(excinfo.value)


# ── gh detection / fallback ──────────────────────────────────────────────────


class TestGhFallback:
    def test_build_gh_pr_create_command_defaults_to_draft(self) -> None:
        cmd = gp.build_gh_pr_create_command(
            title="t", body="b", base="main", head="branch"
        )
        assert cmd[0] == "gh"
        assert "--draft" in cmd
        # all CLI args have a value after them
        assert "--title" in cmd and cmd[cmd.index("--title") + 1] == "t"
        assert "--body" in cmd and cmd[cmd.index("--body") + 1] == "b"
        assert "--base" in cmd and cmd[cmd.index("--base") + 1] == "main"
        assert "--head" in cmd and cmd[cmd.index("--head") + 1] == "branch"

    def test_build_gh_pr_create_command_non_draft(self) -> None:
        cmd = gp.build_gh_pr_create_command(
            title="t", body="b", base="main", head="branch", draft=False
        )
        assert "--draft" not in cmd

    def test_gh_available_matches_shutil(self, monkeypatch) -> None:
        monkeypatch.setattr(gp.shutil, "which", lambda _: None)
        assert gp.gh_available() is False
        monkeypatch.setattr(gp.shutil, "which", lambda _: "/usr/bin/gh")
        assert gp.gh_available() is True

    @requires_git
    def test_run_without_gh_omits_pr_command(self, repo: Path, monkeypatch) -> None:
        monkeypatch.setattr(gp.shutil, "which", lambda _: None)
        # File to "stage" so files list isn't empty
        (repo / "foo.py").write_text("x = 1\n", encoding="utf-8")
        result = gp.run(
            job_id="job-x",
            files=["foo.py"],
            commit_message="feat: add foo",
            repo_root=repo,
            approve=False,
        )
        assert result.plan.gh_present is False
        assert result.plan.pr_create_command is None
        plan_md = (result.plan.output_dir / "publish-plan.md").read_text(
            encoding="utf-8"
        )
        assert "gh not present" in plan_md

    @requires_git
    def test_run_with_gh_emits_pr_command_when_remote_is_github(
        self, repo: Path, monkeypatch
    ) -> None:
        # Fake a github remote and a present gh binary
        _git(
            "remote",
            "add",
            "origin",
            "https://github.com/some-owner/some-repo.git",
            cwd=repo,
        )
        monkeypatch.setattr(gp.shutil, "which", lambda _: "/usr/bin/gh")
        (repo / "foo.py").write_text("x = 1\n", encoding="utf-8")
        result = gp.run(
            job_id="job-y",
            files=["foo.py"],
            commit_message="feat: add foo",
            repo_root=repo,
            approve=False,
        )
        assert result.plan.gh_present is True
        assert result.plan.pr_create_command is not None
        assert result.plan.pr_create_command[:3] == ["gh", "pr", "create"]
        assert "--draft" in result.plan.pr_create_command

    @requires_git
    def test_run_with_gh_but_non_github_remote_omits_pr_command(
        self, repo: Path, monkeypatch
    ) -> None:
        _git(
            "remote",
            "add",
            "origin",
            "https://gitlab.com/foo/bar.git",
            cwd=repo,
        )
        monkeypatch.setattr(gp.shutil, "which", lambda _: "/usr/bin/gh")
        (repo / "foo.py").write_text("x = 1\n", encoding="utf-8")
        result = gp.run(
            job_id="job-z",
            files=["foo.py"],
            commit_message="feat: add foo",
            repo_root=repo,
            approve=False,
        )
        assert result.plan.gh_present is True
        # repo.slug is None when remote isn't github → no PR command
        assert result.plan.repo.slug is None
        assert result.plan.pr_create_command is None


# ── dry-run end-to-end ───────────────────────────────────────────────────────


class TestDryRun:
    @requires_git
    def test_run_writes_six_artifact_files(self, repo: Path) -> None:
        (repo / "foo.py").write_text("x = 1\n", encoding="utf-8")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_foo.py").write_text(
            "def test_x(): assert True\n", encoding="utf-8"
        )
        result = gp.run(
            job_id="kanban-2026-05-23-001",
            files=["foo.py", "tests/test_foo.py"],
            commit_message="feat(foo): introduce foo\n\nDetails.",
            pr_summary="Adds foo.",
            pr_changes=["add foo", "add test"],
            pr_test_plan=["pytest tests/test_foo.py"],
            repo_root=repo,
            approve=False,
        )

        artifact_dir = repo / "github"
        for name in (
            "branch.txt",
            "commit-message.txt",
            "pr-title.txt",
            "pr-body.md",
            "publish-plan.md",
            "publish-status.json",
        ):
            assert (artifact_dir / name).is_file(), f"missing {name}"

        # Branch contents
        assert (artifact_dir / "branch.txt").read_text(
            encoding="utf-8"
        ).strip() == "hermes/job-kanban-2026-05-23-001"

        # PR title comes from first line of commit message when not overridden
        assert (artifact_dir / "pr-title.txt").read_text(
            encoding="utf-8"
        ).strip() == "feat(foo): introduce foo"

        # Body contains our summary
        body = (artifact_dir / "pr-body.md").read_text(encoding="utf-8")
        assert "Adds foo." in body
        assert "- [ ] pytest tests/test_foo.py" in body
        # run() now surfaces the decision verdict id in the body (Sprint 5 wiring)
        assert "## Decision" in body
        assert "- Verdict: `dv_" in body

        # Status JSON is well-formed and dry-run
        status = json.loads(
            (artifact_dir / "publish-status.json").read_text(encoding="utf-8")
        )
        assert status["dry_run"] is True
        assert status["executed"] is False
        assert status["pushed"] is False
        assert status["branch"] == "hermes/job-kanban-2026-05-23-001"
        assert set(status["files"]) == {"foo.py", "tests/test_foo.py"}
        # Plan dataclass result mirrors the artifact
        assert result.plan.branch == status["branch"]
        assert result.executed is False
        assert result.pushed is False

    @requires_git
    def test_dry_run_does_not_modify_git_state(self, repo: Path) -> None:
        (repo / "foo.py").write_text("x = 1\n", encoding="utf-8")
        before_branch = gp.get_current_branch(repo)
        before_status = gp.get_status(repo)

        gp.run(
            job_id="job-1",
            files=["foo.py"],
            commit_message="feat: foo",
            repo_root=repo,
            approve=False,
        )

        # Branch unchanged, working tree state unchanged
        assert gp.get_current_branch(repo) == before_branch
        after_status = gp.get_status(repo)
        # The artifact dir is new untracked content, but foo.py status is unchanged
        assert "foo.py" in after_status.untracked
        assert before_status.staged == after_status.staged

    @requires_git
    def test_publish_plan_md_contains_preview_commands_and_rollback(
        self, repo: Path
    ) -> None:
        (repo / "foo.py").write_text("x = 1\n", encoding="utf-8")
        result = gp.run(
            job_id="job-1",
            files=["foo.py"],
            commit_message="feat: foo",
            repo_root=repo,
            approve=False,
        )
        plan_md = (result.plan.output_dir / "publish-plan.md").read_text(
            encoding="utf-8"
        )
        assert "git checkout -b hermes/job-job-1" in plan_md
        assert "git add -- foo.py" in plan_md
        assert "git push -u origin hermes/job-job-1" in plan_md
        # Rollback section is present and references --delete only on the new branch
        assert "## Rollback" in plan_md
        assert "git push origin --delete hermes/job-job-1" in plan_md
        # No force-push or merge instructions leak in
        assert "--force" not in plan_md
        assert "git merge" not in plan_md

    @requires_git
    def test_run_blocks_when_env_file_is_listed(self, repo: Path) -> None:
        (repo / ".env").write_text("X=1\n", encoding="utf-8")
        result = gp.run(
            job_id="job-1",
            files=[".env"],
            commit_message="oops",
            repo_root=repo,
            approve=True,  # even with approval, secret blocking wins
        )
        assert any(".env" in e for e in result.errors)
        assert result.executed is False
        assert result.pushed is False
        # Plan artifact still written so the operator can see what happened
        status = json.loads(
            (result.plan.output_dir / "publish-status.json").read_text(encoding="utf-8")
        )
        assert status["executed"] is False
        assert any(".env" in e for e in status["errors"])


# ── git plumbing ─────────────────────────────────────────────────────────────


class TestGitPlumbing:
    @requires_git
    def test_get_repo_info_parses_https_remote(self, repo: Path) -> None:
        _git(
            "remote",
            "add",
            "origin",
            "https://github.com/owner/some-repo.git",
            cwd=repo,
        )
        info = gp.get_repo_info(repo)
        assert info.owner == "owner"
        assert info.repo == "some-repo"
        assert info.slug == "owner/some-repo"

    @requires_git
    def test_get_repo_info_parses_ssh_remote(self, repo: Path) -> None:
        _git(
            "remote",
            "add",
            "origin",
            "git@github.com:owner/some-repo.git",
            cwd=repo,
        )
        info = gp.get_repo_info(repo)
        assert info.slug == "owner/some-repo"

    @requires_git
    def test_get_repo_info_handles_no_remote(self, repo: Path) -> None:
        info = gp.get_repo_info(repo)
        assert info.owner is None
        assert info.repo is None
        assert info.remote_url is None

    def test_get_repo_info_outside_git_raises(self, tmp_path: Path) -> None:
        with pytest.raises(gp.PublisherError):
            gp.get_repo_info(tmp_path)

    @requires_git
    def test_get_current_branch(self, repo: Path) -> None:
        assert gp.get_current_branch(repo) == "main"

    @requires_git
    def test_get_status_clean_then_dirty(self, repo: Path) -> None:
        clean = gp.get_status(repo)
        assert clean.clean is True
        (repo / "new.py").write_text("y = 2\n", encoding="utf-8")
        dirty = gp.get_status(repo)
        assert dirty.clean is False
        assert "new.py" in dirty.untracked


# ── decision verdict at the publish boundary (Sprint 2 wiring) ───────────────


@requires_git
def test_publish_status_includes_auto_verdict_for_clean_dry_run(repo: Path) -> None:
    (repo / "foo.py").write_text("x = 1\n", encoding="utf-8")
    result = gp.run(
        job_id="verdict-clean",
        files=["foo.py"],
        commit_message="feat: foo",
        repo_root=repo,
        approve=False,
    )
    verdict = result.plan.decision_verdict
    assert verdict is not None
    assert verdict["tier"] == "auto"
    # and it is surfaced in the written status artifact
    status = json.loads(
        (repo / "github" / "publish-status.json").read_text(encoding="utf-8")
    )
    assert status["decision_verdict"]["tier"] == "auto"


@requires_git
def test_publish_status_refuses_on_secret(repo: Path) -> None:
    (repo / ".env").write_text("API_KEY=supersecretvalue\n", encoding="utf-8")
    result = gp.run(
        job_id="verdict-secret",
        files=[".env"],
        commit_message="chore: env",
        repo_root=repo,
        approve=False,
    )
    verdict = result.plan.decision_verdict
    assert verdict is not None
    assert verdict["tier"] == "refuse"
    assert "secret_detected" in verdict["reason_codes"]


# ── live-publish repo allowlist ──────────────────────────────────────────────


def test_load_allowed_repos_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_PUBLISH_ALLOWED_REPOS", "a/b, c/d  e/f")
    assert gp._load_allowed_repos() == ["a/b", "c/d", "e/f"]


@requires_git
def test_live_publish_refused_when_repo_not_allowlisted(
    repo: Path, monkeypatch
) -> None:
    # An allowlist that does NOT include the target repo refuses the live
    # publish: the verdict is refuse and the push block is never entered.
    _git(
        "remote",
        "add",
        "origin",
        "https://github.com/some-owner/some-repo.git",
        cwd=repo,
    )
    monkeypatch.setattr(gp.shutil, "which", lambda _: None)
    monkeypatch.setenv("HERMES_PUBLISH_ALLOWED_REPOS", "other-owner/other-repo")
    (repo / "foo.py").write_text("x = 1\n", encoding="utf-8")
    result = gp.run(
        job_id="allow-block",
        files=["foo.py"],
        commit_message="feat: foo",
        repo_root=repo,
        approve=True,
    )
    assert result.executed is False
    assert result.pushed is False
    assert any("not in the publish allowlist" in e for e in result.errors)
    verdict = result.plan.decision_verdict
    assert verdict is not None
    assert verdict["tier"] == "refuse"
    assert "live_publish" in verdict["reason_codes"]
