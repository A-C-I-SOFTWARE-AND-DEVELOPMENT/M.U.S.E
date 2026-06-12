"""Tests for the Phase 07 user-profile builder.

These are intentionally hermetic: they construct synthetic snapshots,
patch out subprocess/HTTP calls, and never reach the real GitHub.

Validation surface:
    - the six-month default constant + cutoff math
    - the secret redactor
    - every renderer (must contain required headings from the spec)
    - the approval gate (write_profile refuses without approved=True)
    - the .gitignore mutator (idempotent)
    - the CLI preview mode (no disk writes without --approve)
    - the `gh` fallback path when neither gh nor a token is available
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from muse_cli import github_history as gh_history
from muse_cli import user_profile_builder as upb


# ── fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 5, 23, tzinfo=timezone.utc)


@pytest.fixture
def synthetic_snapshot(fixed_now) -> gh_history.HistorySnapshot:
    """A small, deterministic snapshot exercising every code path."""

    commits = [
        gh_history.Commit(
            sha="aaa111",
            author="Jeremiah",
            email="echerd27@gmail.com",
            timestamp="2026-05-10T12:00:00Z",
            subject="fix: off-by-one in batch_runner pagination",
            body="Found via flaky test, root cause was an off-by-one bug.",
            files=["batch_runner.py", "tests/test_batch_runner.py"],
            additions=12,
            deletions=4,
        ),
        gh_history.Commit(
            sha="bbb222",
            author="Jeremiah",
            email="echerd27@gmail.com",
            timestamp="2026-05-05T10:00:00Z",
            subject="add: hermes orchestration ledger reader",
            body="",
            files=[
                "muse_cli/orchestrator.py",
                "docs/orchestration/README.md",
            ],
            additions=80,
            deletions=2,
        ),
        gh_history.Commit(
            sha="ccc333",
            author="Jeremiah",
            email="echerd27@gmail.com",
            timestamp="2026-04-28T08:00:00Z",
            subject="refactor: clean up gateway termux entry point",
            body="Cleanup pass; Claude agent suggested the rename.",
            files=["gateway/run.py", "apps/android/README.md"],
            additions=20,
            deletions=30,
        ),
    ]
    prs = [
        gh_history.PullRequest(
            number=42,
            title="Add orchestration ledger reader",
            body="Resolves #41. Adds reader + tests.",
            state="closed",
            created_at="2026-05-06T00:00:00Z",
            merged_at="2026-05-07T00:00:00Z",
            author="Jeremiah",
            repo="acme/hermes-agent",
            labels=["enhancement", "orchestration"],
            additions=80,
            deletions=2,
            changed_files=5,
        ),
    ]
    issues = [
        gh_history.Issue(
            number=41,
            title="Need ledger reader",
            body="The ledger needs a reader API.",
            state="closed",
            created_at="2026-05-01T00:00:00Z",
            closed_at="2026-05-07T00:00:00Z",
            author="Jeremiah",
            repo="acme/hermes-agent",
            labels=["enhancement"],
        ),
    ]
    return gh_history.HistorySnapshot(
        user="Jeremiah",
        since=gh_history.iso_since(now=fixed_now),
        window_days=gh_history.DEFAULT_WINDOW_DAYS,
        commits=commits,
        pull_requests=prs,
        issues=issues,
        sources_used=["local-git"],
        notes=["test snapshot"],
    )


# ── constants ──────────────────────────────────────────────────────────────


class TestWindow:
    def test_default_is_roughly_six_months(self):
        assert 175 <= gh_history.DEFAULT_WINDOW_DAYS <= 200

    def test_iso_since_uses_default_window(self, fixed_now):
        iso = gh_history.iso_since(now=fixed_now)
        cutoff = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        assert (fixed_now - cutoff) >= timedelta(days=gh_history.DEFAULT_WINDOW_DAYS - 1)
        assert (fixed_now - cutoff) <= timedelta(days=gh_history.DEFAULT_WINDOW_DAYS + 1)

    def test_custom_window(self, fixed_now):
        iso = gh_history.iso_since(window_days=30, now=fixed_now)
        cutoff = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        assert (fixed_now - cutoff).days == 30

    def test_compute_since_clamps_to_at_least_one_day(self, fixed_now):
        cutoff = gh_history.compute_since(0, now=fixed_now)
        assert (fixed_now - cutoff) >= timedelta(days=1)


# ── redactor ───────────────────────────────────────────────────────────────


class TestRedactSecrets:
    def test_redacts_github_pat(self):
        out = upb.redact_secrets("token=ghp_" + "A" * 36 + " end")
        assert "ghp_" not in out
        assert "[REDACTED]" in out

    def test_redacts_aws_key(self):
        out = upb.redact_secrets("AWS=AKIAABCDEFGHIJKLMNOP")
        assert "AKIAABCDEFGHIJKLMNOP" not in out
        assert "[REDACTED]" in out

    def test_redacts_pem_block_header(self):
        out = upb.redact_secrets("-----BEGIN RSA PRIVATE KEY-----")
        assert "PRIVATE KEY" not in out

    def test_passthrough_when_clean(self):
        text = "ordinary commit message about widgets"
        assert upb.redact_secrets(text) == text

    def test_handles_empty(self):
        assert upb.redact_secrets("") == ""


# ── renderers ──────────────────────────────────────────────────────────────


REQUIRED_HEADINGS = [
    "Preferred languages and frameworks",
    "Repeated project types",
    "Commit message style",
    "PR style",
    "Common bug categories",
    "Testing habits",
    "Documentation habits",
    "Mobile / Termux preferences",
    "AI-agent workflow preferences",
    "Mistakes Hermes should watch for",
    "Plain-English notes for future assistants",
]


class TestRenderers:
    def test_user_profile_contains_every_required_heading(self, synthetic_snapshot):
        commit_summary = gh_history.summarize_commits(synthetic_snapshot.commits)
        pr_summary = gh_history.summarize_pull_requests(synthetic_snapshot.pull_requests)
        issue_summary = gh_history.summarize_issues(synthetic_snapshot.issues)
        md = upb.render_user_profile(
            snapshot=synthetic_snapshot,
            commit_summary=commit_summary,
            pr_summary=pr_summary,
            issue_summary=issue_summary,
            user_label="Jeremiah",
        )
        for heading in REQUIRED_HEADINGS:
            assert heading in md, f"missing required heading: {heading!r}"

    def test_user_profile_mentions_six_months_window(self, synthetic_snapshot):
        commit_summary = gh_history.summarize_commits(synthetic_snapshot.commits)
        md = upb.render_user_profile(
            snapshot=synthetic_snapshot,
            commit_summary=commit_summary,
            pr_summary=gh_history.summarize_pull_requests([]),
            issue_summary=gh_history.summarize_issues([]),
            user_label="Jeremiah",
        )
        assert str(gh_history.DEFAULT_WINDOW_DAYS) in md

    def test_coding_style_lists_top_languages(self, synthetic_snapshot):
        commit_summary = gh_history.summarize_commits(synthetic_snapshot.commits)
        pr_summary = gh_history.summarize_pull_requests(synthetic_snapshot.pull_requests)
        md = upb.render_coding_style(commit_summary, pr_summary)
        assert "Languages by commit count" in md
        assert "Python" in md  # we have .py files in the synthetic data

    def test_common_mistakes_picks_up_off_by_one(self, synthetic_snapshot):
        commit_summary = gh_history.summarize_commits(synthetic_snapshot.commits)
        issue_summary = gh_history.summarize_issues(synthetic_snapshot.issues)
        md = upb.render_common_mistakes(commit_summary, issue_summary)
        assert "off-by-one" in md

    def test_preferred_stack_includes_repo(self, synthetic_snapshot):
        commit_summary = gh_history.summarize_commits(synthetic_snapshot.commits)
        pr_summary = gh_history.summarize_pull_requests(synthetic_snapshot.pull_requests)
        md = upb.render_preferred_stack(commit_summary, pr_summary)
        assert "acme/hermes-agent" in md

    def test_validation_preferences_includes_test_ratio(self, synthetic_snapshot):
        commit_summary = gh_history.summarize_commits(synthetic_snapshot.commits)
        md = upb.render_validation_preferences(commit_summary)
        assert "% of commits in window touched test files" in md
        assert "PR body" in md or "PR" in md  # checklist present

    def test_history_summary_json_is_valid(self, synthetic_snapshot):
        commit_summary = gh_history.summarize_commits(synthetic_snapshot.commits)
        pr_summary = gh_history.summarize_pull_requests(synthetic_snapshot.pull_requests)
        issue_summary = gh_history.summarize_issues(synthetic_snapshot.issues)
        blob = upb.render_history_summary_json(
            synthetic_snapshot, commit_summary, pr_summary, issue_summary
        )
        data = json.loads(blob)
        assert data["user"] == "Jeremiah"
        assert data["window_days"] == gh_history.DEFAULT_WINDOW_DAYS
        assert data["commits"]["total_commits"] == 3

    def test_redaction_runs_on_user_profile(self, synthetic_snapshot, monkeypatch):
        # Inject a fake token into a commit subject; the renderer must redact it.
        bad_commit = gh_history.Commit(
            sha="zzz",
            author="x",
            email="x@x",
            timestamp="2026-05-01T00:00:00Z",
            subject="oops ghp_" + "A" * 36 + " leaked",
            body="",
            files=["a.py"],
            additions=1,
            deletions=0,
        )
        snap = gh_history.HistorySnapshot(
            user="Jeremiah",
            since=synthetic_snapshot.since,
            window_days=synthetic_snapshot.window_days,
            commits=[bad_commit],
            pull_requests=[],
            issues=[],
            sources_used=["local-git"],
            notes=[],
        )
        commit_summary = gh_history.summarize_commits(snap.commits)
        md = upb.render_user_profile(
            snapshot=snap,
            commit_summary=commit_summary,
            pr_summary=gh_history.summarize_pull_requests([]),
            issue_summary=gh_history.summarize_issues([]),
            user_label="Jeremiah",
        )
        assert "ghp_" not in md


# ── build + write ──────────────────────────────────────────────────────────


class TestBuildAndWrite:
    def test_build_profile_returns_every_required_file(
        self, synthetic_snapshot, tmp_path
    ):
        rendered = upb.build_profile(
            tmp_path,
            user="Jeremiah",
            snapshot=synthetic_snapshot,
        )
        expected = {
            "user-profile.md",
            "coding-style.md",
            "common-mistakes.md",
            "preferred-stack.md",
            "validation-preferences.md",
            "github-history-summary.json",
        }
        assert expected.issubset(rendered.keys())

    def test_write_profile_refuses_without_approval(
        self, synthetic_snapshot, tmp_path
    ):
        rendered = upb.build_profile(
            tmp_path, user="Jeremiah", snapshot=synthetic_snapshot
        )
        with pytest.raises(upb.ApprovalRequired):
            upb.write_profile(tmp_path, rendered, approved=False)
        # No files written
        assert not (tmp_path / upb.PROFILE_DIR_NAME).exists()

    def test_write_profile_writes_when_approved(
        self, synthetic_snapshot, tmp_path
    ):
        rendered = upb.build_profile(
            tmp_path, user="Jeremiah", snapshot=synthetic_snapshot
        )
        artifacts = upb.write_profile(tmp_path, rendered, approved=True)
        assert artifacts.output_dir == tmp_path / upb.PROFILE_DIR_NAME
        for name in rendered:
            assert (artifacts.output_dir / name).exists()
        # And .gitignore got the new entry.
        ignore_text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert f"{upb.PROFILE_DIR_NAME}/" in ignore_text

    def test_snapshot_is_only_written_when_requested(
        self, synthetic_snapshot, tmp_path
    ):
        rendered = upb.build_profile(
            tmp_path, user="Jeremiah", snapshot=synthetic_snapshot
        )
        artifacts = upb.write_profile(
            tmp_path, rendered, approved=True, snapshot=None
        )
        assert artifacts.snapshot_path is None
        assert not (artifacts.output_dir / "snapshot.json").exists()

        artifacts2 = upb.write_profile(
            tmp_path, rendered, approved=True, snapshot=synthetic_snapshot
        )
        assert artifacts2.snapshot_path is not None
        assert artifacts2.snapshot_path.exists()


# ── .gitignore mutator ─────────────────────────────────────────────────────


class TestEnsureGitignore:
    def test_creates_file_when_missing(self, tmp_path):
        added = upb.ensure_gitignore(tmp_path)
        assert added is True
        body = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert f"{upb.PROFILE_DIR_NAME}/" in body

    def test_appends_when_missing(self, tmp_path):
        (tmp_path / ".gitignore").write_text("# existing\nfoo/\n", encoding="utf-8")
        added = upb.ensure_gitignore(tmp_path)
        assert added is True
        body = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert "foo/" in body
        assert f"{upb.PROFILE_DIR_NAME}/" in body

    def test_idempotent(self, tmp_path):
        (tmp_path / ".gitignore").write_text(
            f"{upb.PROFILE_DIR_NAME}/\n", encoding="utf-8"
        )
        added = upb.ensure_gitignore(tmp_path)
        assert added is False
        # No duplicate line.
        body = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert body.count(f"{upb.PROFILE_DIR_NAME}/") == 1


# ── CLI ────────────────────────────────────────────────────────────────────


class TestCli:
    def test_preview_mode_writes_nothing(
        self, synthetic_snapshot, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setattr(
            gh_history, "collect_history", lambda *a, **k: synthetic_snapshot
        )
        code = upb.main([
            "--repo", str(tmp_path),
            "--user", "Jeremiah",
        ])
        assert code == 0
        # No profile dir created in preview mode.
        assert not (tmp_path / upb.PROFILE_DIR_NAME).exists()
        captured = capsys.readouterr()
        assert "approval required" in captured.err.lower()

    def test_approve_mode_writes_files(
        self, synthetic_snapshot, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            gh_history, "collect_history", lambda *a, **k: synthetic_snapshot
        )
        code = upb.main([
            "--repo", str(tmp_path),
            "--user", "Jeremiah",
            "--approve",
        ])
        assert code == 0
        assert (tmp_path / upb.PROFILE_DIR_NAME / "user-profile.md").exists()
        assert (tmp_path / ".gitignore").exists()


# ── data-source fallback behaviour ─────────────────────────────────────────


class TestCollectHistoryFallbacks:
    def test_no_git_no_gh_no_token_returns_empty_snapshot_with_notes(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(gh_history, "have_git", lambda: False)
        monkeypatch.setattr(gh_history, "have_gh_auth", lambda: False)
        monkeypatch.setattr(gh_history, "get_github_token", lambda env=None: None)
        snap = gh_history.collect_history(tmp_path, user="someone")
        assert snap.commits == []
        assert snap.pull_requests == []
        assert any("git not on PATH" in n for n in snap.notes)
        # Even without sources, the window/since fields are set.
        assert snap.window_days == gh_history.DEFAULT_WINDOW_DAYS
        assert snap.since

    def test_token_path_uses_api_when_gh_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gh_history, "have_git", lambda: False)
        monkeypatch.setattr(gh_history, "have_gh_auth", lambda: False)
        monkeypatch.setattr(gh_history, "get_github_token", lambda env=None: "xx")

        calls: dict[str, int] = {"prs": 0, "issues": 0}

        def fake_prs(user, token, **kw):
            calls["prs"] += 1
            return [
                gh_history.PullRequest(
                    number=1,
                    title="t",
                    body="b",
                    state="open",
                    created_at="2026-05-01",
                    merged_at=None,
                    author=user,
                    repo="o/r",
                )
            ]

        def fake_issues(user, token, **kw):
            calls["issues"] += 1
            return []

        monkeypatch.setattr(gh_history, "collect_api_pull_requests", fake_prs)
        monkeypatch.setattr(gh_history, "collect_api_issues", fake_issues)

        snap = gh_history.collect_history(tmp_path, user="someone")
        assert "github-api" in snap.sources_used
        assert calls["prs"] == 1
        assert calls["issues"] == 1
        assert len(snap.pull_requests) == 1


# ── local git parser ───────────────────────────────────────────────────────


class TestLocalGitParser:
    def test_parses_synthetic_git_log_output(self, tmp_path, monkeypatch):
        # Build a fake git log output and feed it through _run_git.
        record1 = "\x1faaa111\x1eJ\x1ej@x\x1e2026-05-10T00:00:00Z\x1efix: bug\x1ebody one\n10\t2\tfile.py\n"
        record2 = "\x1fbbb222\x1eJ\x1ej@x\x1e2026-05-01T00:00:00Z\x1eadd: thing\x1e\n3\t0\ttest_thing.py\n"
        fake_stdout = record1 + record2

        def fake_run_git(args, *, cwd):
            return fake_stdout

        monkeypatch.setattr(gh_history, "_run_git", fake_run_git)

        commits = gh_history.collect_local_commits(tmp_path)
        assert len(commits) == 2
        assert commits[0].sha == "aaa111"
        assert commits[0].subject == "fix: bug"
        assert commits[0].files == ["file.py"]
        assert commits[0].additions == 10
        assert commits[0].deletions == 2
        assert commits[1].sha == "bbb222"

    def test_returns_empty_when_git_fails(self, tmp_path, monkeypatch):
        def boom(args, *, cwd):
            raise RuntimeError("git missing")

        monkeypatch.setattr(gh_history, "_run_git", boom)
        assert gh_history.collect_local_commits(tmp_path) == []


# ── summarisers ────────────────────────────────────────────────────────────


class TestSummarisers:
    def test_commit_summary_counts_languages_and_intent(self, synthetic_snapshot):
        s = gh_history.summarize_commits(synthetic_snapshot.commits)
        assert s["total_commits"] == 3
        # 2 .py + 2 .md + 1 .py in tests/ => Python should appear.
        langs = dict(s["languages"])
        assert "Python" in langs
        assert s["fix_intent"] >= 1
        assert s["feature_intent"] >= 1
        assert "off-by-one" in s["bug_categories"]

    def test_pr_summary_handles_empty(self):
        s = gh_history.summarize_pull_requests([])
        assert s["total"] == 0
        assert s["top_repos"] == []

    def test_issue_summary_handles_empty(self):
        s = gh_history.summarize_issues([])
        assert s["total"] == 0
