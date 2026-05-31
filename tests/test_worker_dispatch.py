"""Worker execution engine: registry adapter + gated dispatch + ledger."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from hermes_cli import orchestrator as orch
from hermes_cli.workers import registry as wr
from hermes_cli.workers.base import (
    WorkerAdapter,
    WorkerArtifacts,
    WorkerDetection,
    WorkerPrompt,
    WorkerRunResult,
    WorkerScore,
)
from hermes_cli.workers.local_planner import LocalPlannerWorker


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    yield tmp_path


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "svc").mkdir(parents=True)
    (repo / "svc" / "uploader.py").write_text(
        "def upload_file(p):\n    return open(p).read()\n"
    )
    (repo / "tests").mkdir()
    (repo / "tests" / "test_uploader.py").write_text(
        "from svc.uploader import upload_file\n\ndef test_u():\n    pass\n"
    )
    return repo


class _Job:
    def __init__(self, prompt: str) -> None:
        self.prompt = prompt
        self.id = "j"


def test_local_planner_is_registered() -> None:
    assert "hermes-local-planner" in wr.known_workers()


def test_local_planner_adapter_contract(sample_repo: Path) -> None:
    w = LocalPlannerWorker(str(sample_repo))
    assert w.detect().available
    job = _Job("upload_file fails on large files")
    run = w.run(job)
    assert run.ok and "uploader.py" in run.stdout
    arts = w.collect(job)
    assert any(f.endswith("uploader.py") for f in arts.files)
    score = w.score(arts)
    assert 0.0 <= score.value <= 1.0 and score.value > 0.5
    # non-destructive: it claims no edits / no commands
    assert "no edits" in arts.notes


def test_dispatch_local_planner_records_ledger_and_completes(
    isolated_home: Path, sample_repo: Path
) -> None:
    job = orch.submit_job("upload_file fails on large files")
    out = orch.dispatch_job(job.id, repo_root=str(sample_repo))
    assert out is not None and out.status == "completed"
    kinds = [e.get("kind") for e in orch.get_ledger(job.id)[job.id]]
    assert {"worker_dispatch", "worker_result", "worker_score"} <= set(kinds)
    assert any(a.endswith("uploader.py") for a in out.artifacts)


def test_dispatch_unknown_worker_is_recorded_not_raised(isolated_home: Path) -> None:
    job = orch.submit_job("do a thing")
    out = orch.dispatch_job(job.id, worker_id="does-not-exist")
    assert out is not None
    kinds = [e.get("kind") for e in orch.get_ledger(job.id)[job.id]]
    assert "worker_error" in kinds


def test_destructive_worker_blocked_without_owner_approval(isolated_home: Path) -> None:
    class FakeDestructive(WorkerAdapter):
        id = "fake-destructive"
        display_name = "Fake destructive"

        def detect(self):
            return WorkerDetection(available=True)

        def prepare_prompt(self, job):
            return WorkerPrompt(text="x")

        def run(self, job):
            raise AssertionError("must not run without owner approval")

        def collect(self, job):
            return WorkerArtifacts()

        def score(self, artifacts):
            return WorkerScore(value=1.0)

    wr.register(FakeDestructive(), replace=True)
    job = orch.submit_job("dangerous thing")

    # Ungated dispatch is refused — the owner gate is never bypassed.
    out = orch.dispatch_job(job.id, worker_id="fake-destructive")
    assert out is not None and out.status == "blocked"
    assert "worker_blocked" in [e.get("kind") for e in orch.get_ledger(job.id)[job.id]]

    # After the owner approves the execute phase, the gate opens (run attempted).
    orch.approve_phase(job.id, "execute")
    orch.dispatch_job(job.id, worker_id="fake-destructive")
    assert "worker_error" in [e.get("kind") for e in orch.get_ledger(job.id)[job.id]]
