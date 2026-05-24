"""Tests for the pure helpers in ``hermes_cli.validation``.

The :class:`ValidationRunner` orchestration is covered in
``test_validation_gates.py``; this module pins the standalone helpers
the orchestrator depends on:

  * ``parse_frontmatter`` — YAML-frontmatter parser used by every skill
    validator.
  * ``validate_skill_frontmatter`` — required-key contract for
    ``skills/*/SKILL.md`` files.
  * ``validate_job_folder`` — orchestrator job-folder contract.
  * ``render_summary`` — markdown rendering of a ValidationReport.

These helpers are intentionally side-effect-free and have no external
deps so the tests run instantly with no fixtures.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from hermes_cli.validation import (
    CheckResult,
    ValidationReport,
    parse_frontmatter,
    render_summary,
    validate_job_folder,
    validate_skill_frontmatter,
)


# ── parse_frontmatter ─────────────────────────────────────────────────


class TestParseFrontmatter:
    def test_returns_none_without_leading_fence(self) -> None:
        assert parse_frontmatter("no fence here") is None

    def test_returns_none_when_fence_unterminated(self) -> None:
        assert parse_frontmatter("---\nname: x") is None

    def test_parses_simple_scalar_keys(self) -> None:
        text = "---\nname: alpha\ndescription: a thing\n---\nbody\n"
        data = parse_frontmatter(text)
        assert data == {"name": "alpha", "description": "a thing"}

    def test_strips_quotes(self) -> None:
        text = '---\nname: "alpha"\ndescription: \'a thing\'\n---\n'
        data = parse_frontmatter(text)
        assert data["name"] == "alpha"
        assert data["description"] == "a thing"

    def test_returns_none_for_non_mapping(self) -> None:
        # Top-level list — invalid frontmatter for our purposes.
        assert parse_frontmatter("---\n- a\n- b\n---\n") is None


# ── validate_skill_frontmatter ────────────────────────────────────────


class TestValidateSkillFrontmatter:
    def test_accepts_valid_frontmatter(self) -> None:
        text = "---\nname: skill-x\ndescription: does a thing\n---\n"
        assert validate_skill_frontmatter(text) is None

    def test_rejects_missing_name(self) -> None:
        text = "---\ndescription: x\n---\n"
        assert "name" in (validate_skill_frontmatter(text) or "")

    def test_rejects_missing_description(self) -> None:
        text = "---\nname: x\n---\n"
        assert "description" in (validate_skill_frontmatter(text) or "")

    def test_rejects_empty_name(self) -> None:
        text = '---\nname: ""\ndescription: x\n---\n'
        assert validate_skill_frontmatter(text) is not None

    def test_rejects_whitespace_in_name(self) -> None:
        text = "---\nname: bad name\ndescription: x\n---\n"
        assert "invalid `name`" in (validate_skill_frontmatter(text) or "")

    def test_rejects_path_separator_in_name(self) -> None:
        text = "---\nname: bad/name\ndescription: x\n---\n"
        assert "invalid `name`" in (validate_skill_frontmatter(text) or "")

    def test_rejects_when_no_frontmatter(self) -> None:
        assert validate_skill_frontmatter("no fence") is not None


# ── validate_job_folder ───────────────────────────────────────────────


class TestValidateJobFolder:
    def test_missing_job_json_is_rejected(self, tmp_path: Path) -> None:
        assert validate_job_folder(tmp_path) == "missing job.json"

    def test_bad_json_returns_parse_error(self, tmp_path: Path) -> None:
        (tmp_path / "job.json").write_text("not json", encoding="utf-8")
        result = validate_job_folder(tmp_path)
        assert result and result.startswith("job.json parse error")

    def test_non_object_top_level_is_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "job.json").write_text("[1, 2, 3]", encoding="utf-8")
        result = validate_job_folder(tmp_path)
        assert result == "job.json: top level must be an object"

    def test_missing_required_key_is_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "job.json").write_text(
            json.dumps({"id": "abc"}), encoding="utf-8"
        )
        result = validate_job_folder(tmp_path)
        assert "status" in (result or "")

    def test_logs_must_be_a_directory(self, tmp_path: Path) -> None:
        (tmp_path / "job.json").write_text(
            json.dumps({"id": "abc", "status": "queued"}), encoding="utf-8"
        )
        (tmp_path / "logs").write_text("oops", encoding="utf-8")
        result = validate_job_folder(tmp_path)
        assert result == "logs/ exists but is not a directory"

    def test_accepts_minimal_job_folder(self, tmp_path: Path) -> None:
        (tmp_path / "job.json").write_text(
            json.dumps({"id": "abc", "status": "queued"}), encoding="utf-8"
        )
        assert validate_job_folder(tmp_path) is None

    def test_accepts_job_folder_with_logs_dir(self, tmp_path: Path) -> None:
        (tmp_path / "job.json").write_text(
            json.dumps({"id": "abc", "status": "queued"}), encoding="utf-8"
        )
        (tmp_path / "logs").mkdir()
        assert validate_job_folder(tmp_path) is None


# ── render_summary ────────────────────────────────────────────────────


def _empty_report(allowed: bool = True) -> ValidationReport:
    now = time.time()
    return ValidationReport(
        workspace="/tmp/ws",
        results=[],
        publish_allowed=allowed,
        blocking_failures=[] if allowed else ["forced.fail"],
        started_at=now,
        finished_at=now + 0.5,
    )


class TestRenderSummary:
    def test_open_when_publish_allowed(self) -> None:
        out = render_summary(_empty_report(allowed=True))
        assert "Publish gate: **OPEN**" in out

    def test_blocked_when_publish_denied(self) -> None:
        out = render_summary(_empty_report(allowed=False))
        assert "Publish gate: **BLOCKED**" in out
        assert "forced.fail" in out

    def test_rows_render_per_check(self) -> None:
        report = _empty_report(allowed=True)
        report.results.append(
            CheckResult(
                name="git.status",
                category="git",
                status="pass",
                summary="clean tree",
            )
        )
        out = render_summary(report)
        assert "`git.status`" in out
        assert "clean tree" in out

    def test_pipe_in_summary_is_escaped(self) -> None:
        report = _empty_report(allowed=True)
        report.results.append(
            CheckResult(
                name="x", category="git", status="warn",
                summary="a | b",
            )
        )
        out = render_summary(report)
        # The pipe is escaped so it can't break the markdown table.
        assert "a \\| b" in out

    def test_trailing_newline(self) -> None:
        out = render_summary(_empty_report(allowed=True))
        assert out.endswith("\n")
