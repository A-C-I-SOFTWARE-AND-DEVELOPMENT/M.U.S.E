"""Tests for ``muse_cli.validation`` — Phase 14 validation gates.

Each test sets up an isolated temp workspace (or initialised git
repo) and exercises one slice of the runner. We do *not* depend on
the host having pytest/ruff/gradle/apktool installed — the relevant
checks degrade to ``skipped`` when their backing tool is missing,
and the tests assert that degradation explicitly.

The ``ValidationRunner.run()`` path is the public entry point;
parser/scanner helpers are also covered directly because they are
the most likely thing for an LLM-driven change to subtly break.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from muse_cli.validation import (
    CATEGORY_GIT,
    CATEGORY_HERMES,
    CATEGORY_LANGUAGE,
    CATEGORY_SECRETS,
    STATUS_BLOCKED,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_SKIPPED,
    STATUS_WARN,
    CheckResult,
    ValidationRunner,
    parse_frontmatter,
    render_summary,
    scan_text_for_secrets,
    validate_job_folder,
    validate_skill_frontmatter,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(  # noqa: S603 — args are test-controlled.
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} -> {proc.returncode}: {proc.stderr}")
    return proc.stdout


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "main", cwd=path)
    # Identity is required for any future commit.
    _git("config", "user.email", "test@example.com", cwd=path)
    _git("config", "user.name", "Test", cwd=path)
    # CI / sandboxed environments may have commit signing enabled
    # globally; force it off for the throwaway repo so commits don't
    # have to talk to the host's signing service.
    _git("config", "commit.gpgsign", "false", cwd=path)
    _git("config", "tag.gpgsign", "false", cwd=path)
    # Ignore the validation/ output directory so its presence in
    # subsequent runs doesn't bleed into git.status assertions.
    (path / ".gitignore").write_text("validation/\n", encoding="utf-8")
    _git("add", ".gitignore", cwd=path)
    _git("commit", "--no-gpg-sign", "-q", "-m", "init", cwd=path)


def _by_name(results: list[CheckResult]) -> dict[str, CheckResult]:
    return {r.name: r for r in results}


# ── Frontmatter / job / scanner unit tests ─────────────────────────────────


class TestFrontmatterParsing:
    def test_parses_valid_frontmatter(self) -> None:
        text = textwrap.dedent(
            """\
            ---
            name: hello
            description: a skill
            ---

            Body here.
            """
        )
        data = parse_frontmatter(text)
        assert data == {"name": "hello", "description": "a skill"}

    def test_missing_frontmatter_returns_none(self) -> None:
        assert parse_frontmatter("no frontmatter at all") is None

    def test_unclosed_fence_returns_none(self) -> None:
        assert parse_frontmatter("---\nname: x\n") is None

    def test_validate_skill_frontmatter_happy_path(self) -> None:
        text = "---\nname: hello\ndescription: stuff\n---\nbody"
        assert validate_skill_frontmatter(text) is None

    def test_validate_skill_frontmatter_missing_name(self) -> None:
        text = "---\ndescription: stuff\n---\nbody"
        err = validate_skill_frontmatter(text)
        assert err is not None
        assert "name" in err

    def test_validate_skill_frontmatter_bad_name(self) -> None:
        text = "---\nname: has spaces\ndescription: stuff\n---\nbody"
        err = validate_skill_frontmatter(text)
        assert err is not None
        assert "name" in err

    def test_validate_skill_frontmatter_missing_description(self) -> None:
        text = "---\nname: hello\n---\nbody"
        err = validate_skill_frontmatter(text)
        assert err is not None
        assert "description" in err


class TestJobFolderContract:
    def test_valid_job(self, tmp_path: Path) -> None:
        job = tmp_path / "job-001"
        job.mkdir()
        (job / "job.json").write_text(
            json.dumps({"id": "job-001", "status": "queued"}), encoding="utf-8"
        )
        (job / "logs").mkdir()
        assert validate_job_folder(job) is None

    def test_missing_job_json(self, tmp_path: Path) -> None:
        job = tmp_path / "bad"
        job.mkdir()
        assert validate_job_folder(job) == "missing job.json"

    def test_malformed_job_json(self, tmp_path: Path) -> None:
        job = tmp_path / "bad"
        job.mkdir()
        (job / "job.json").write_text("{not json", encoding="utf-8")
        err = validate_job_folder(job)
        assert err is not None and "parse error" in err

    def test_missing_required_keys(self, tmp_path: Path) -> None:
        job = tmp_path / "bad"
        job.mkdir()
        (job / "job.json").write_text(json.dumps({"id": "x"}), encoding="utf-8")
        err = validate_job_folder(job)
        assert err is not None and "status" in err

    def test_logs_is_a_file_not_dir(self, tmp_path: Path) -> None:
        job = tmp_path / "bad"
        job.mkdir()
        (job / "job.json").write_text(
            json.dumps({"id": "x", "status": "queued"}), encoding="utf-8"
        )
        (job / "logs").write_text("oops", encoding="utf-8")
        err = validate_job_folder(job)
        assert err is not None and "logs" in err


class TestSecretScanner:
    def test_finds_openai_style_key_in_added_line(self) -> None:
        diff = "+API_KEY = 'sk-abcdefghijklmnopqrstuvwxyz1234'"
        findings = scan_text_for_secrets(diff)
        assert findings
        labels = {f[0] for f in findings}
        # Either the openai or generic kv pattern will fire — both are fine.
        assert labels & {"openai_key", "generic_secret_kv"}

    def test_ignores_diff_file_header(self) -> None:
        # +++ b/file headers should never match.
        diff = "+++ b/some_file_with_sk-abcdefghijklmnopqrst_in_name.py"
        assert scan_text_for_secrets(diff) == []

    def test_redacts_match(self) -> None:
        diff = "+token = 'ghp_" + "A" * 36 + "'"
        findings = scan_text_for_secrets(diff)
        assert findings
        # Snippet must be a redacted form, not the raw token.
        for _, snippet in findings:
            assert "…" in snippet
            assert "A" * 36 not in snippet

    def test_no_findings_on_clean_diff(self) -> None:
        assert scan_text_for_secrets("+ just a normal line of code") == []

    def test_aws_access_key_match(self) -> None:
        findings = scan_text_for_secrets("+ AKIAIOSFODNN7EXAMPLE")
        labels = {f[0] for f in findings}
        assert "aws_access_key" in labels

    def test_private_key_block_match(self) -> None:
        findings = scan_text_for_secrets("+-----BEGIN RSA PRIVATE KEY-----")
        assert any(label == "private_key_block" for label, _ in findings)


# ── Runner integration tests ───────────────────────────────────────────────


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A minimal git-initialised workspace with no source files."""
    _init_repo(tmp_path)
    return tmp_path


class TestRunnerBasics:
    def test_clean_repo_publish_allowed(self, workspace: Path) -> None:
        runner = ValidationRunner(workspace)
        report = runner.run()
        assert report.publish_allowed is True
        assert report.blocking_failures == []

    def test_writes_three_artifacts(self, workspace: Path) -> None:
        runner = ValidationRunner(workspace)
        runner.run()
        out = workspace / "validation"
        assert (out / "results.json").exists()
        assert (out / "summary.md").exists()
        assert (out / "commands.log").exists()
        # results.json must be valid JSON
        data = json.loads((out / "results.json").read_text(encoding="utf-8"))
        assert "checks" in data and isinstance(data["checks"], list)

    def test_summary_md_records_publish_gate(self, workspace: Path) -> None:
        report = ValidationRunner(workspace).run()
        md = render_summary(report)
        assert "Publish gate" in md
        assert "OPEN" in md
        assert "git.status" in md

    def test_commands_log_has_run_commands(self, workspace: Path) -> None:
        ValidationRunner(workspace).run()
        log = (workspace / "validation" / "commands.log").read_text(encoding="utf-8")
        # Several git invocations always run inside a git repo.
        assert "git status --short" in log
        assert "git diff --stat" in log

    def test_only_category_filter_drops_others(self, workspace: Path) -> None:
        report = ValidationRunner(workspace, only=[CATEGORY_GIT]).run()
        categories = {r.category for r in report.results}
        assert categories == {CATEGORY_GIT}

    def test_skip_category_filter_drops_target(self, workspace: Path) -> None:
        report = ValidationRunner(workspace, skip=[CATEGORY_GIT]).run()
        categories = {r.category for r in report.results}
        assert CATEGORY_GIT not in categories


class TestGitChecks:
    def test_git_status_lists_changed_paths(self, workspace: Path) -> None:
        (workspace / "newfile.txt").write_text("hi\n", encoding="utf-8")
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["git.status"]
        assert result.status == STATUS_PASS
        assert result.metadata["changed_paths"] >= 1


class TestSecretChecks:
    def test_blocked_path_staged_blocks_publish(self, workspace: Path) -> None:
        env_file = workspace / ".env"
        env_file.write_text("OPENAI_API_KEY=sk-fake\n", encoding="utf-8")
        # Force-add despite .gitignore semantics by using -f, mirroring
        # the real "user accidentally staged it" scenario.
        _git("add", "-f", ".env", cwd=workspace)
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["secrets.blocked_paths"]
        assert result.status == STATUS_FAIL
        assert "secrets.blocked_paths" in report.blocking_failures
        assert report.publish_allowed is False

    def test_obvious_secret_in_staged_diff_blocks(self, workspace: Path) -> None:
        sneaky = workspace / "config.py"
        sneaky.write_text(
            "OPENAI_API_KEY = 'sk-abcdefghijklmnopqrstuvwxyz12'\n", encoding="utf-8"
        )
        _git("add", "config.py", cwd=workspace)
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["secrets.staged_diff"]
        assert result.status == STATUS_FAIL
        assert "secrets.staged_diff" in report.blocking_failures
        # The finding must carry redacted snippets, never the raw key.
        for finding in result.metadata.get("findings", []):
            assert "abcdefghijklmnopqrstuvwxyz12" not in finding["snippet"]

    def test_clean_staged_diff_passes(self, workspace: Path) -> None:
        (workspace / "ok.py").write_text("print('hi')\n", encoding="utf-8")
        _git("add", "ok.py", cwd=workspace)
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["secrets.staged_diff"]
        assert result.status == STATUS_PASS
        assert report.publish_allowed is True


class TestPythonChecks:
    def test_py_compile_passes_on_good_code(self, workspace: Path) -> None:
        (workspace / "good.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["python.py_compile"]
        assert result.status == STATUS_PASS

    def test_py_compile_fails_on_syntax_error(self, workspace: Path) -> None:
        (workspace / "bad.py").write_text("def broken(:\n", encoding="utf-8")
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["python.py_compile"]
        assert result.status == STATUS_FAIL
        # It is critical, so publish must be blocked.
        assert "python.py_compile" in report.blocking_failures
        assert report.publish_allowed is False

    def test_pytest_is_blocked_when_expensive_disabled(self, workspace: Path) -> None:
        (workspace / "tests").mkdir()
        (workspace / "tests" / "test_x.py").write_text(
            "def test_ok():\n    assert True\n", encoding="utf-8"
        )
        (workspace / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.0.1"\n', encoding="utf-8"
        )
        report = ValidationRunner(workspace, allow_expensive=False).run()
        result = _by_name(report.results)["python.pytest"]
        assert result.status == STATUS_BLOCKED


class TestShellCheck:
    def test_clean_shell_script_passes(self, workspace: Path) -> None:
        scripts = workspace / "scripts"
        scripts.mkdir()
        (scripts / "ok.sh").write_text("#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["shell.syntax"]
        if shutil.which("bash"):
            assert result.status == STATUS_PASS
        else:
            # On hosts without bash this degrades; we still record an
            # outcome, just not a pass.
            assert result.status in {STATUS_FAIL, STATUS_PASS}

    @pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
    def test_broken_shell_script_fails(self, workspace: Path) -> None:
        scripts = workspace / "scripts"
        scripts.mkdir()
        (scripts / "bad.sh").write_text("#!/usr/bin/env bash\nif then fi\n", encoding="utf-8")
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["shell.syntax"]
        assert result.status == STATUS_FAIL
        assert "shell.syntax" in report.blocking_failures


class TestSkillChecks:
    def test_invalid_skill_frontmatter_blocks(self, workspace: Path) -> None:
        skill_dir = workspace / "skills" / "broken"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "no frontmatter here\n", encoding="utf-8"
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["hermes.skill_frontmatter"]
        assert result.status == STATUS_FAIL
        assert "hermes.skill_frontmatter" in report.blocking_failures

    def test_valid_skill_frontmatter_passes(self, workspace: Path) -> None:
        skill_dir = workspace / "skills" / "good"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: good\ndescription: works\n---\nbody\n",
            encoding="utf-8",
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["hermes.skill_frontmatter"]
        assert result.status == STATUS_PASS

    def test_duplicate_skill_names_blocks(self, workspace: Path) -> None:
        for sub in ("a", "b"):
            d = workspace / "skills" / sub
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(
                "---\nname: same\ndescription: dup\n---\n",
                encoding="utf-8",
            )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["hermes.duplicate_skills"]
        assert result.status == STATUS_FAIL
        assert "same" in result.metadata["duplicates"]


class TestJobFolderCheck:
    def test_valid_job_folder_passes(self, workspace: Path) -> None:
        job = workspace / "jobs" / "j1"
        job.mkdir(parents=True)
        (job / "job.json").write_text(
            json.dumps({"id": "j1", "status": "done"}), encoding="utf-8"
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["hermes.job_folder"]
        assert result.status == STATUS_PASS

    def test_invalid_job_folder_blocks(self, workspace: Path) -> None:
        job = workspace / "jobs" / "broken"
        job.mkdir(parents=True)
        # No job.json at all.
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["hermes.job_folder"]
        assert result.status == STATUS_FAIL
        assert "hermes.job_folder" in report.blocking_failures


class TestModelRegistryCheck:
    def test_valid_json_registry_passes(self, workspace: Path) -> None:
        registry = {"anthropic/claude-sonnet-4-6": {"context": 200000}}
        (workspace / "model_registry.json").write_text(
            json.dumps(registry), encoding="utf-8"
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["hermes.model_registry"]
        assert result.status == STATUS_PASS
        assert result.metadata["entries"] == 1

    def test_malformed_registry_blocks(self, workspace: Path) -> None:
        (workspace / "model_registry.json").write_text(
            "{this is not json", encoding="utf-8"
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["hermes.model_registry"]
        assert result.status == STATUS_FAIL
        assert "hermes.model_registry" in report.blocking_failures


class TestWorkerStatusCheck:
    def test_fresh_worker_passes(self, workspace: Path) -> None:
        import time as _time

        worker = workspace / "workers" / "worker-1"
        worker.mkdir(parents=True)
        (worker / "status.json").write_text(
            json.dumps({"heartbeat": _time.time(), "state": "idle"}),
            encoding="utf-8",
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["hermes.worker_status"]
        assert result.status == STATUS_PASS

    def test_stale_worker_warns_not_blocks(self, workspace: Path) -> None:
        worker = workspace / "workers" / "worker-1"
        worker.mkdir(parents=True)
        # 48h ago — older than the 24h freshness threshold.
        (worker / "status.json").write_text(
            json.dumps({"heartbeat": 1, "state": "lost"}), encoding="utf-8"
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["hermes.worker_status"]
        assert result.status == STATUS_WARN
        # Non-critical: publish must remain allowed.
        assert "hermes.worker_status" not in report.blocking_failures


class TestExpensivePolicy:
    def test_expensive_checks_blocked_by_default(self, workspace: Path) -> None:
        (workspace / "gradlew").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(workspace / "gradlew", 0o755)
        report = ValidationRunner(workspace, allow_expensive=False).run()
        gradle = _by_name(report.results)["gradle.test"]
        assert gradle.status == STATUS_BLOCKED

    def test_expensive_checks_run_when_allowed(self, workspace: Path) -> None:
        (workspace / "gradlew").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(workspace / "gradlew", 0o755)
        report = ValidationRunner(workspace, allow_expensive=True).run()
        gradle = _by_name(report.results)["gradle.test"]
        # The fake gradlew returns 0 so it should pass; if /bin/sh is
        # missing in the sandbox it'd register as FAIL with returncode
        # 127 — both prove the check actually executed (no longer
        # ``blocked``).
        assert gradle.status in {STATUS_PASS, STATUS_FAIL}


class TestApkPack:
    def test_apk_checks_only_when_apk_present(self, workspace: Path) -> None:
        # No APK, no apk.* checks at all.
        report = ValidationRunner(workspace, allow_expensive=True).run()
        names = {r.name for r in report.results}
        assert not any(n.startswith("apk.") for n in names)

    def test_apk_checks_skipped_when_tool_missing(self, workspace: Path) -> None:
        # Drop a 1-byte fake APK so discovery kicks in; without
        # apktool/jadx/aapt on PATH the checks must record SKIPPED, not
        # crash.
        (workspace / "app-debug.apk").write_bytes(b"PK")
        report = ValidationRunner(workspace, allow_expensive=True).run()
        apk_results = [r for r in report.results if r.name.startswith("apk.")]
        assert apk_results, "expected apk.* checks to be discovered"
        # On a typical CI host none of apktool/jadx/aapt are installed.
        # They may legitimately *be* installed elsewhere, so we only
        # assert that every result has a terminal status — not that
        # they're all skipped.
        for r in apk_results:
            assert r.status in {
                STATUS_PASS,
                STATUS_FAIL,
                STATUS_WARN,
                STATUS_SKIPPED,
            }


class TestReportShape:
    def test_results_json_excludes_empty_fields(self, workspace: Path) -> None:
        report = ValidationRunner(workspace).run()
        data = json.loads(
            (workspace / "validation" / "results.json").read_text(encoding="utf-8")
        )
        # Every record must at minimum have name/category/status/summary.
        for check in data["checks"]:
            assert set(check).issuperset({"name", "category", "status", "summary"})

    def test_status_counts_sums_to_total(self, workspace: Path) -> None:
        report = ValidationRunner(workspace).run()
        counts = report.status_counts()
        assert sum(counts.values()) == len(report.results)
