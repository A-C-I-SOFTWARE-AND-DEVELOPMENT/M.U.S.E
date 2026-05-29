"""Tests for the edit-site ranker and the Navigator facade."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.navigation import Navigator


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "svc").mkdir()
    (tmp_path / "svc" / "__init__.py").write_text("")
    (tmp_path / "svc" / "uploader.py").write_text(
        "def upload_file(path):\n    return open(path).read()\n\n"
        "def retry_upload(path):\n    return upload_file(path)\n"
    )
    (tmp_path / "svc" / "client.py").write_text(
        "from svc.uploader import upload_file\n\ndef send():\n    return upload_file('x')\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_uploader.py").write_text(
        "from svc.uploader import upload_file\n\ndef test_u():\n    pass\n"
    )
    return tmp_path


def test_edit_sites_have_tests_and_dependents(repo: Path):
    nav = Navigator.for_repo(repo, use_git=False)
    sites = nav.edit_sites("upload_file fails on large files")
    assert sites
    top = sites[0]
    assert top.path == "svc/uploader.py"
    assert top.rank == 1
    assert 0.0 < top.confidence <= 1.0
    assert "upload_file" in top.symbols
    assert "tests/test_uploader.py" in top.suggested_tests
    assert "svc/client.py" in top.dependents
    assert top.rationale


def test_navigate_produces_worker_packet(repo: Path):
    nav = Navigator.for_repo(repo, use_git=False)
    result = nav.navigate("retry_upload should back off")
    packet = result.worker_packet()
    assert packet["candidate_files"]
    assert packet["candidate_files"][0] == "svc/uploader.py"
    assert "tests/test_uploader.py" in packet["verify_with"]
    assert "no LLM" in packet["navigation_method"]


def test_ledger_record_is_auditable(repo: Path):
    nav = Navigator.for_repo(repo, use_git=False)
    result = nav.navigate("fix upload_file", limit=3)
    rec = result.to_ledger_record(job_id="job-xyz")
    assert rec["kind"] == "navigation_decision"
    assert rec["job_id"] == "job-xyz"
    assert rec["ranked_files"]
    first = rec["ranked_files"][0]
    assert first["path"] == "svc/uploader.py"
    assert "signals" in first and "rationale" in first


def test_repo_map_renders(repo: Path):
    nav = Navigator.for_repo(repo, use_git=False)
    text = nav.repo_map()
    assert "svc/uploader.py" in text
