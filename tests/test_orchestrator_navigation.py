"""Navigator → orchestrator integration: submit → navigate → ledger → replay."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from muse_cli import orchestrator as orch
from muse_cli.orchestrator_replay import JobReplay


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    yield tmp_path


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "svc").mkdir(parents=True)
    (repo / "svc" / "__init__.py").write_text("")
    (repo / "svc" / "uploader.py").write_text(
        "def upload_file(p):\n    return open(p).read()\n"
    )
    (repo / "tests").mkdir()
    (repo / "tests" / "test_uploader.py").write_text(
        "from svc.uploader import upload_file\n\ndef test_u():\n    pass\n"
    )
    return repo


def test_navigate_job_records_ledger_and_returns_packet(
    isolated_home: Path, sample_repo: Path
):
    job = orch.submit_job("upload_file fails on large files")
    packet = orch.navigate_job(job.id, repo_root=str(sample_repo))
    assert packet is not None
    assert "svc/uploader.py" in packet["candidate_files"]

    # The ledger now has submit + navigation_decision.
    ledger = orch.get_ledger(job.id)[job.id]
    kinds = [e.get("kind") for e in ledger]
    assert "submit" in kinds
    assert "navigation_decision" in kinds

    # And replay reconstructs it read-only.
    replay = JobReplay.load(job.id)
    assert replay.by_kind("navigation_decision")
    assert "svc/uploader.py" in replay.render()


def test_navigate_job_blank_objective_is_noop(isolated_home: Path, sample_repo: Path):
    job = orch.submit_job("real prompt")
    assert orch.navigate_job(job.id, repo_root=str(sample_repo), issue="   ") is None


def test_run_orchestrate_navigates_before_dispatch(
    isolated_home: Path, sample_repo: Path, monkeypatch: pytest.MonkeyPatch
):
    """The live /orchestrate path now runs the navigator before dispatch."""
    monkeypatch.chdir(sample_repo)  # navigate_job defaults repo_root to cwd
    out = orch.run_orchestrate("upload_file fails on large files")
    assert "Orchestration job queued" in out

    jobs = orch.list_jobs()
    assert jobs, "a job should have been queued"
    jid = jobs[0].id
    kinds = [e.get("kind") for e in orch.get_ledger(jid)[jid]]
    assert "submit" in kinds
    assert "navigation_decision" in kinds  # navigation ran in the live path


def test_orchestrator_replay_command_renders_ledger(
    isolated_home: Path, sample_repo: Path, monkeypatch: pytest.MonkeyPatch
):
    """/orchestrator replay <job-id> surfaces the job's decision ledger."""
    monkeypatch.chdir(sample_repo)
    orch.run_orchestrate("upload_file fails on large files")
    jid = orch.list_jobs()[0].id

    out = orch.run_orchestrator(f"replay {jid}")
    assert "submit" in out or "navigation" in out  # rendered ledger content
    assert "⚠" not in out

    # Unknown id is handled, not crashed.
    assert "unknown job id" in orch.run_orchestrator("replay nope_123")
    # Missing id is handled.
    assert "requires a job id" in orch.run_orchestrator("replay")
