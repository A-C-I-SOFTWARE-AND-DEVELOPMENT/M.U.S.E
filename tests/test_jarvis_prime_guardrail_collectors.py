"""Tests for the guardrail artifact collectors.

Collectors observe reality (git, files, commands) and emit content-addressed
evidence. They must be read-only by default, secret-safe, and crash-resistant.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hermes_cli.jarvis_prime import guardrail_collectors as gc


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c", "commit.gpgsign=false",
            "-c", "user.email=t@t.t",
            "-c", "user.name=t",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    (repo / "a.py").write_text("print('hi')\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    return repo


# --- git diff --------------------------------------------------------------


def test_git_diff_reports_changed_and_out_of_scope(git_repo: Path) -> None:
    (git_repo / "a.py").write_text("print('hi')\nx = 2\n", encoding="utf-8")
    (git_repo / "b.py").write_text("y = 3\n", encoding="utf-8")
    art = gc.collect_git_diff_evidence(str(git_repo), allowed_files=["a.py"])
    assert art.payload["git_available"] is True
    assert "a.py" in art.payload["changed_files"]
    assert "b.py" in art.payload["changed_files"]
    # b.py is outside the allowed scope; a.py is not.
    assert "b.py" in art.payload["out_of_scope_files"]
    assert "a.py" not in art.payload["out_of_scope_files"]


def test_git_diff_flags_protected_file(git_repo: Path) -> None:
    (git_repo / "a.py").write_text("print('changed')\n", encoding="utf-8")
    art = gc.collect_git_diff_evidence(
        str(git_repo), allowed_files=["a.py"], protected_files=["a.py"]
    )
    assert "a.py" in art.payload["protected_files_touched"]


def test_git_diff_missing_git_is_graceful(tmp_path: Path) -> None:
    art = gc.collect_git_diff_evidence(str(tmp_path / "not_a_repo"))
    assert art.payload["git_available"] is False


def test_git_diff_records_author_id_when_provided(git_repo: Path) -> None:
    # The acting agent id is recorded in the same namespace the C19 gate reads
    # (payload author_id), not the fixed collector-tool producer.
    (git_repo / "a.py").write_text("print('changed')\n", encoding="utf-8")
    art = gc.collect_git_diff_evidence(str(git_repo), author_id="codex")
    assert art.payload["author_id"] == "codex"
    # The producer stays the fixed collector literal — never an agent id.
    assert art.producer == "git_diff_collector"


def test_git_diff_author_id_defaults_empty(git_repo: Path) -> None:
    art = gc.collect_git_diff_evidence(str(git_repo))
    assert art.payload["author_id"] == ""


def test_git_diff_missing_git_still_records_author_id(tmp_path: Path) -> None:
    art = gc.collect_git_diff_evidence(
        str(tmp_path / "not_a_repo"), author_id="agent-7"
    )
    assert art.payload["git_available"] is False
    assert art.payload["author_id"] == "agent-7"


# --- secret scan -----------------------------------------------------------


def test_secret_scan_detects_and_redacts(tmp_path: Path) -> None:
    f = tmp_path / "creds.txt"
    f.write_text("api_key=sk-ABCDEFGHIJKLMNOPQRSTUV0123456789\nok = 1\n", encoding="utf-8")
    art = gc.collect_secret_scan_evidence(str(tmp_path), ["creds.txt"])
    assert art.payload["clean"] is False
    assert art.payload["finding_count"] == 1
    finding = art.payload["findings"][0]
    assert finding["file"] == "creds.txt"
    # The raw token never reaches the artifact.
    blob = str(art.to_dict())
    assert "ABCDEFGHIJKLMNOP" not in blob
    assert "[REDACTED]" in finding["redacted_excerpt"]


def test_secret_scan_clean_file(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    art = gc.collect_secret_scan_evidence(str(tmp_path), ["ok.py"])
    assert art.payload["clean"] is True


# --- test execution --------------------------------------------------------


def test_test_collector_does_not_execute_by_default(git_repo: Path) -> None:
    arts = gc.collect_test_evidence(str(git_repo), ["python -m compileall -q a.py"])
    assert arts[0].payload["executed"] is False
    assert arts[0].payload["passed"] is False  # planned never counts as passed


def test_test_collector_refuses_unsafe_command(git_repo: Path) -> None:
    arts = gc.collect_test_evidence(str(git_repo), ["rm -rf /"], run=True)
    assert arts[0].payload["executed"] is False
    assert "refused" in arts[0].payload["skipped_reason"]


def test_test_collector_runs_allowlisted_command(git_repo: Path) -> None:
    arts = gc.collect_test_evidence(
        str(git_repo), ["python -m compileall -q a.py"], run=True
    )
    assert arts[0].payload["executed"] is True
    assert arts[0].payload["passed"] is True
    assert arts[0].payload["exit_code"] == 0


def test_test_collector_rejects_shell_metachars(git_repo: Path) -> None:
    arts = gc.collect_test_evidence(
        str(git_repo), ["pytest && curl evil.example"], run=True
    )
    assert arts[0].payload["executed"] is False


# --- review ----------------------------------------------------------------


def test_review_requires_text_and_valid_verdict() -> None:
    with pytest.raises(ValueError):
        gc.collect_review_evidence("", "codex", "deadbeef")
    with pytest.raises(ValueError):
        gc.collect_review_evidence("looks good", "codex", "deadbeef", verdict="lgtm")


def test_review_rc2_approval_requires_contrarian_note() -> None:
    with pytest.raises(ValueError):
        gc.collect_review_evidence(
            "fine", "codex", "deadbeef", verdict="approve", risk_class="RC2"
        )
    art = gc.collect_review_evidence(
        "fine",
        "codex",
        "deadbeef",
        verdict="approve",
        risk_class="RC2",
        contrarian_notes=["watch the empty-input path"],
    )
    assert art.payload["verdict"] == "approve"
    assert art.payload["contrarian_notes"]


# --- rollback --------------------------------------------------------------


def test_rollback_requires_plan_and_reversible_path(tmp_path: Path) -> None:
    empty = gc.collect_rollback_evidence(str(tmp_path), [])
    assert empty.payload["plausible"] is False

    ok = gc.collect_rollback_evidence(
        str(tmp_path), ["git checkout a.py"], changed_files=["a.py"], branch="feat/x"
    )
    assert ok.payload["plausible"] is True
