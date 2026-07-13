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


def test_dispatch_records_decision_verdict_in_ledger(
    isolated_home: Path, sample_repo: Path
) -> None:
    # The unified verdict is composed at the execute boundary and recorded so the
    # cockpit can render one verdict. The ungated local planner -> auto.
    job = orch.submit_job("verdict at dispatch")
    orch.dispatch_job(job.id, repo_root=str(sample_repo))
    dispatch = next(
        e for e in orch.get_ledger(job.id)[job.id] if e.get("kind") == "worker_dispatch"
    )
    verdict = dispatch.get("decision_verdict")
    assert verdict is not None
    assert verdict["tier"] == "auto"
    assert verdict["action_type"] == "orchestrator.worker_execute"


def test_blocked_dispatch_records_ask_verdict(isolated_home: Path) -> None:
    class FakeDestructive2(WorkerAdapter):
        id = "fake-destructive-2"
        display_name = "Fake destructive 2"

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

    wr.register(FakeDestructive2(), replace=True)
    job = orch.submit_job("dangerous thing")
    orch.dispatch_job(job.id, worker_id="fake-destructive-2")
    blocked = next(
        e for e in orch.get_ledger(job.id)[job.id] if e.get("kind") == "worker_blocked"
    )
    verdict = blocked.get("decision_verdict")
    assert verdict is not None
    assert verdict["tier"] == "ask"
    assert "owner_required" in verdict["reason_codes"]


def test_load_builtins_registers_both_workers() -> None:
    from hermes_cli.workers import load_builtins, known_workers

    load_builtins()
    ids = known_workers()
    assert "hermes-local-planner" in ids
    assert "aider-handoff" in ids


def test_aider_handoff_adapter_is_non_executing(sample_repo: Path) -> None:
    from hermes_cli.workers.aider_handoff import AiderHandoffWorker

    w = AiderHandoffWorker(str(sample_repo))
    assert w.requires_approval is False  # handoff only — safe ungated
    det = w.detect()
    assert det.available  # handoff prep doesn't need the binary
    job = _Job("upload_file fails on large files")
    run = w.run(job)
    assert run.ok
    assert "aider" in run.stdout  # a ready handoff command, not execution output
    assert run.details["status"] == "handoff_required"  # never executed
    arts = w.collect(job)
    assert "handoff prepared" in arts.notes
    assert 0.0 <= w.score(arts).value <= 1.0


def test_dispatch_aider_handoff_runs_ungated(
    isolated_home: Path, sample_repo: Path
) -> None:
    job = orch.submit_job("upload_file fails on large files")
    out = orch.dispatch_job(
        job.id, worker_id="aider-handoff", repo_root=str(sample_repo)
    )
    assert out is not None and out.status == "completed"  # ungated, no approval needed
    kinds = [e.get("kind") for e in orch.get_ledger(job.id)[job.id]]
    assert {"worker_dispatch", "worker_result", "worker_score"} <= set(kinds)


import pytest as _pytest


@_pytest.mark.parametrize(
    "worker_id", ["aider-handoff", "goose-handoff", "codex-handoff", "claude-handoff"]
)
def test_all_handoff_workers_registered_and_non_executing(
    worker_id: str, isolated_home: Path, sample_repo: Path
) -> None:
    from hermes_cli.workers import known_workers, load_builtins

    load_builtins()
    assert worker_id in known_workers()

    job = orch.submit_job("upload_file fails on large files")
    out = orch.dispatch_job(job.id, worker_id=worker_id, repo_root=str(sample_repo))
    # Handoff workers are non-destructive → run ungated and complete.
    assert out is not None and out.status == "completed"
    led = orch.get_ledger(job.id)[job.id]
    kinds = [e.get("kind") for e in led]
    assert {"worker_dispatch", "worker_result", "worker_score"} <= set(kinds)
    # And the result is a staged handoff, not an execution.
    result = next(e for e in led if e.get("kind") == "worker_result")
    assert result["ok"] is True


def test_builtin_worker_roster() -> None:
    from hermes_cli.workers import builtin_worker_classes

    ids = {c.id for c in builtin_worker_classes()}
    assert ids == {
        "hermes-local-planner",
        "aider-handoff",
        "goose-handoff",
        "codex-handoff",
        "claude-handoff",
        "aider-execute",
        "goose-execute",
        "codex-execute",
        "claude-execute",
        "sia",
        "autoresearch",
        "llm-jepa",
    }


def test_claude_execute_completes_the_orphaned_agentic_path() -> None:
    """claude-execute wraps the previously-orphaned Claude Code execute path and
    is owner-gated (never runs the tool without an approved execute phase)."""
    from hermes_cli.workers.claude_handoff import ClaudeExecuteWorker

    w = ClaudeExecuteWorker()
    assert w.id == "claude-execute"
    assert w.requires_approval is True
    # detect() reports the *real* binary presence (honest either way).
    assert isinstance(w.detect().available, bool)


# ── Live execute layer (gated; degrades honestly when the CLI is absent) ──

from pathlib import Path as _Path  # noqa: E402

from hermes_cli.workers.base import WorkerResult, WorkerStatus  # noqa: E402
from hermes_cli.workers.handoff_base import ProceduralExecuteWorker  # noqa: E402


class _FakeConfig:
    command = "fake-bin"


class _FakeModule:
    def __init__(self) -> None:
        self.run_calls: list[bool] = []

    def detect_command(self, command: str) -> bool:
        return True  # pretend the binary is present

    def render_prompt(self, task) -> str:
        return "prompt body"

    def run(self, task, workspace, *, execute=False, repo_root=None) -> WorkerResult:
        self.run_calls.append(execute)
        ws = _Path(workspace)
        return WorkerResult(
            worker="fake",
            status=WorkerStatus.EXECUTED,
            workspace=ws,
            prompt_path=ws / "prompt.md",
            status_path=ws / "status.json",
            command_available=True,
            exit_code=0,
        )


_FAKE_MODULE = _FakeModule()


class _FakeExecuteWorker(ProceduralExecuteWorker):
    id = "fake-execute"
    display_name = "Fake (execute)"
    tool_label = "Fake"
    worker_module = _FAKE_MODULE
    config_cls = _FakeConfig


def test_execute_worker_actually_runs_with_execute_true(sample_repo: Path) -> None:
    w = _FakeExecuteWorker(str(sample_repo))
    assert w.requires_approval is True
    assert w.detect().available is True
    result = w.run(_Job("do the thing"))
    assert _FAKE_MODULE.run_calls and _FAKE_MODULE.run_calls[-1] is True  # execute=True
    assert result.ok is True  # EXECUTED → ok
    assert result.exit_code == 0


def test_execute_worker_is_gated_without_owner_approval(
    isolated_home: Path, sample_repo: Path
) -> None:
    job = orch.submit_job("edit the uploader")
    out = orch.dispatch_job(
        job.id, worker_id="aider-execute", repo_root=str(sample_repo)
    )
    assert out is not None and out.status == "blocked"
    assert "worker_blocked" in [e.get("kind") for e in orch.get_ledger(job.id)[job.id]]


def test_execute_worker_blocks_honestly_when_binary_absent(
    isolated_home: Path, sample_repo: Path
) -> None:
    # Approve the execute phase, but the aider binary isn't installed here →
    # detect() reports unavailable → dispatch blocks; no execution attempted.
    job = orch.submit_job("edit the uploader")
    orch.approve_phase(job.id, "execute")
    out = orch.dispatch_job(
        job.id, worker_id="aider-execute", repo_root=str(sample_repo)
    )
    assert out is not None and out.status == "blocked"
    dispatch = next(
        e for e in orch.get_ledger(job.id)[job.id] if e.get("kind") == "worker_dispatch"
    )
    assert dispatch["available"] is False
