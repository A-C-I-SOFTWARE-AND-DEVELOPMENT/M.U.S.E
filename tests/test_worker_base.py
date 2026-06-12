"""Tests for :mod:`muse_cli.workers.base`.

Covers the five result records (``WorkerDetection``, ``WorkerPrompt``,
``WorkerRunResult``, ``WorkerArtifacts``, ``WorkerScore``), the
abstract :class:`WorkerAdapter` contract enforcement, and the shared
workspace primitives (``ensure_workspace``, ``write_prompt``,
``write_status``, ``collect_git_artifacts``, render helpers).

A small ``_FakeAdapter`` stands in for the real workers so we can
exercise the abstract base without depending on any external CLI.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from muse_cli.workers import (
    WorkerAdapter,
    WorkerArtifacts,
    WorkerDetection,
    WorkerError,
    WorkerPrompt,
    WorkerResult,
    WorkerRunResult,
    WorkerScore,
    WorkerStatus,
    WorkerTask,
)
from muse_cli.workers import base as worker_base
from muse_cli.workers.base import (
    collect_git_artifacts,
    detect_command,
    ensure_workspace,
    render_acceptance_block,
    render_context_block,
    render_files_block,
    result_as_dict,
    write_prompt,
    write_status,
)


# ── Fixtures ────────────────────────────────────────────────────────────


class _FakeAdapter(WorkerAdapter):
    """Minimal concrete adapter exercising the abstract base."""

    id = "fake"
    display_name = "Fake Worker"

    def __init__(self, *, available: bool = True) -> None:
        self._available = available

    def detect(self) -> WorkerDetection:
        return WorkerDetection(
            available=self._available,
            version="0.0.0",
            reason="ok" if self._available else "missing",
        )

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        return WorkerPrompt(
            text=f"do: {getattr(job, 'goal', job)}",
            role="builder",
            metadata={"job_id": getattr(job, "id", None)},
        )

    def run(self, job: Any) -> WorkerRunResult:
        return WorkerRunResult(ok=True, stdout="done", duration_seconds=0.01)

    def collect(self, job: Any) -> WorkerArtifacts:
        return WorkerArtifacts(files=("README.md",), notes="touched README")

    def score(self, artifacts: WorkerArtifacts) -> WorkerScore:
        return WorkerScore(
            value=1.0 if artifacts.files else 0.0,
            confidence=0.8,
            rationale="files were produced",
            components={"compiles": 1.0, "tests": 0.5},
        )


# ── Result records ──────────────────────────────────────────────────────


def test_worker_detection_defaults():
    d = WorkerDetection(available=True)
    assert d.available is True
    assert d.version == ""
    assert d.reason == ""
    assert d.details == {}


def test_worker_detection_carries_full_payload():
    d = WorkerDetection(
        available=False,
        version="",
        reason="codex not on PATH",
        details={"checked": ["/usr/local/bin"]},
    )
    assert d.available is False
    assert d.reason == "codex not on PATH"
    assert d.details["checked"] == ["/usr/local/bin"]


def test_worker_prompt_defaults():
    p = WorkerPrompt(text="hello")
    assert p.text == "hello"
    assert p.role == ""
    assert p.metadata == {}


def test_worker_run_result_defaults_to_success_shape():
    r = WorkerRunResult(ok=True)
    assert r.ok is True
    assert r.exit_code == 0
    assert r.stdout == ""
    assert r.stderr == ""
    assert r.duration_seconds == 0.0
    assert r.error == ""


def test_worker_artifacts_defaults_use_immutable_tuples():
    a = WorkerArtifacts()
    assert a.files == ()
    assert a.patches == ()
    assert a.logs == ()
    assert a.links == ()
    assert a.workspace_path == ""
    assert a.notes == ""


def test_dataclass_records_are_frozen():
    d = WorkerDetection(available=True)
    with pytest.raises(Exception):
        setattr(d, "available", False)


def test_worker_score_accepts_valid_range():
    s = WorkerScore(value=0.5, confidence=0.9, rationale="ok")
    assert s.value == 0.5
    assert s.confidence == 0.9


@pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0, -5.0])
def test_worker_score_rejects_out_of_range_value(bad):
    with pytest.raises(ValueError):
        WorkerScore(value=bad)


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_worker_score_rejects_out_of_range_confidence(bad):
    with pytest.raises(ValueError):
        WorkerScore(value=0.5, confidence=bad)


def test_worker_score_rejects_out_of_range_component():
    with pytest.raises(ValueError):
        WorkerScore(value=0.5, components={"tests": 1.5})


def test_worker_score_components_lower_bound_is_inclusive():
    s = WorkerScore(value=0.0, components={"tests": 0.0})
    assert s.components["tests"] == 0.0


# ── WorkerAdapter contract ──────────────────────────────────────────────


def test_worker_adapter_is_abstract():
    with pytest.raises(TypeError):
        WorkerAdapter()  # type: ignore[abstract]


def test_subclass_missing_id_fails_at_definition():
    with pytest.raises(TypeError, match="`id`"):

        class _NoId(WorkerAdapter):
            display_name = "x"

            def detect(self) -> WorkerDetection:
                return WorkerDetection(available=True)

            def prepare_prompt(self, job):
                return WorkerPrompt(text="")

            def run(self, job):
                return WorkerRunResult(ok=True)

            def collect(self, job):
                return WorkerArtifacts()

            def score(self, artifacts):
                return WorkerScore(value=0.0)


def test_subclass_missing_display_name_fails_at_definition():
    with pytest.raises(TypeError, match="`display_name`"):

        class _NoName(WorkerAdapter):
            id = "x"

            def detect(self) -> WorkerDetection:
                return WorkerDetection(available=True)

            def prepare_prompt(self, job):
                return WorkerPrompt(text="")

            def run(self, job):
                return WorkerRunResult(ok=True)

            def collect(self, job):
                return WorkerArtifacts()

            def score(self, artifacts):
                return WorkerScore(value=0.0)


def test_subclass_missing_abstract_method_cannot_instantiate():
    class _Partial(WorkerAdapter):
        id = "partial"
        display_name = "Partial"

        def detect(self) -> WorkerDetection:
            return WorkerDetection(available=True)

        # missing prepare_prompt / run / collect / score

    with pytest.raises(TypeError):
        _Partial()  # type: ignore[abstract]


def test_fake_adapter_round_trip():
    adapter = _FakeAdapter()
    detection = adapter.detect()
    assert detection.available is True

    prompt = adapter.prepare_prompt("ship it")
    assert "ship it" in prompt.text
    assert prompt.role == "builder"

    run_result = adapter.run("ship it")
    assert run_result.ok is True

    artifacts = adapter.collect("ship it")
    assert artifacts.files == ("README.md",)

    score = adapter.score(artifacts)
    assert score.value == 1.0
    assert 0.0 <= score.confidence <= 1.0


def test_fake_adapter_detection_reflects_state():
    assert _FakeAdapter(available=True).detect().available is True
    missing = _FakeAdapter(available=False).detect()
    assert missing.available is False
    assert missing.reason == "missing"


# ── Shared primitives ──────────────────────────────────────────────────


def test_worker_status_values_are_stable():
    # Persistence layers read these strings; treat them as a stable surface.
    assert WorkerStatus.HANDOFF_REQUIRED.value == "handoff_required"
    assert WorkerStatus.EXECUTED.value == "executed"
    assert WorkerStatus.COMMAND_NOT_FOUND.value == "command_not_found"
    assert WorkerStatus.FAILED.value == "failed"


def test_worker_error_is_an_exception():
    assert issubclass(WorkerError, Exception)


def test_worker_task_round_trips_defaults():
    task = WorkerTask(title="t", instructions="i")
    assert task.title == "t"
    assert task.instructions == "i"
    assert task.files == []
    assert task.acceptance_criteria == []
    assert task.metadata == {}


def test_detect_command_returns_bool_for_known_binary():
    # ``sh`` is on every POSIX PATH; we only assert the truthiness contract.
    assert isinstance(detect_command("sh"), bool)


def test_detect_command_returns_false_for_obviously_missing(tmp_path):
    assert detect_command("definitely-not-a-binary-9e8d") is False


def test_ensure_workspace_creates_directory(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    resolved = ensure_workspace(target)
    assert target.exists() and target.is_dir()
    assert resolved == target.resolve()


def test_ensure_workspace_is_idempotent(tmp_path):
    target = tmp_path / "ws"
    ensure_workspace(target)
    ensure_workspace(target)  # second call must not raise
    assert target.exists()


def test_write_prompt_writes_markdown_file(tmp_path):
    path = write_prompt(tmp_path, "# hi")
    assert path == tmp_path / "prompt.md"
    assert path.read_text(encoding="utf-8") == "# hi"


def test_write_status_serialises_result(tmp_path):
    result = WorkerResult(
        worker="fake",
        status=WorkerStatus.EXECUTED,
        workspace=tmp_path,
        prompt_path=tmp_path / "prompt.md",
        status_path=tmp_path / "status.json",
        command_available=True,
        exit_code=0,
    )
    path = write_status(tmp_path, result)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["worker"] == "fake"
    assert payload["status"] == "executed"
    assert payload["workspace"] == str(tmp_path)
    assert "timestamp" in payload


def test_result_as_dict_stringifies_paths_and_status(tmp_path):
    result = WorkerResult(
        worker="fake",
        status=WorkerStatus.HANDOFF_REQUIRED,
        workspace=tmp_path,
        prompt_path=tmp_path / "prompt.md",
        status_path=tmp_path / "status.json",
        command_available=False,
        handoff_command="claude --print prompt.md",
    )
    data = result_as_dict(result)
    assert data["workspace"] == str(tmp_path)
    assert data["status"] == "handoff_required"
    assert data["handoff_command"] == "claude --print prompt.md"


def test_render_files_block_handles_empty():
    assert render_files_block([]) == ""


def test_render_files_block_lists_files():
    out = render_files_block(["a.py", "b.py"])
    assert "## Files in scope" in out
    assert "`a.py`" in out and "`b.py`" in out


def test_render_acceptance_block_handles_empty():
    assert render_acceptance_block([]) == ""


def test_render_acceptance_block_lists_items():
    out = render_acceptance_block(["tests pass", "no new imports"])
    assert "tests pass" in out
    assert "no new imports" in out


def test_render_context_block_handles_empty():
    assert render_context_block(None) == ""
    assert render_context_block("") == ""


def test_render_context_block_includes_text():
    out = render_context_block("important")
    assert "## Context" in out
    assert "important" in out


# ── git artifact collection ────────────────────────────────────────────


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    cmds = [
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
        ["git", "config", "commit.gpgsign", "false"],
    ]
    for cmd in cmds:
        subprocess.run(cmd, cwd=str(path), check=True, capture_output=True)
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(path), check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=str(path), check=True
    )
    return path


def test_collect_git_artifacts_no_repo(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    patch, names = collect_git_artifacts(workspace, plain)
    assert patch is None and names is None


def test_collect_git_artifacts_captures_diff(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    patch, names = collect_git_artifacts(workspace, repo)
    assert patch is not None and patch.exists()
    assert names is not None and names.exists()
    assert "README.md" in names.read_text(encoding="utf-8")
    assert "changed" in patch.read_text(encoding="utf-8")


# ── module exports ──────────────────────────────────────────────────────


def test_base_module_does_not_leak_registry_symbols():
    # Registry symbols belong in ``registry``; the ABC + primitives stay in base.
    assert not hasattr(worker_base, "WorkerRegistry")
    assert not hasattr(worker_base, "register")
    assert not hasattr(worker_base, "default_registry")


def test_base_module_exports_all_primitives():
    expected = {
        "WorkerAdapter",
        "WorkerArtifacts",
        "WorkerDetection",
        "WorkerError",
        "WorkerPrompt",
        "WorkerResult",
        "WorkerRunResult",
        "WorkerScore",
        "WorkerStatus",
        "WorkerTask",
        "collect_git_artifacts",
        "detect_command",
        "ensure_workspace",
        "render_acceptance_block",
        "render_context_block",
        "render_files_block",
        "result_as_dict",
        "write_prompt",
        "write_status",
    }
    assert expected.issubset(set(worker_base.__all__))
