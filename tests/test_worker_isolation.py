"""Tests for :mod:`muse_cli.workers.isolation`.

Each filesystem-touching test runs against an isolated ephemeral
directory (``tmp_path``) and, when worktrees are involved, an
ephemeral git repository — we never touch the host's working copy.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from muse_cli import worktrees as wt
from muse_cli.workers import (
    CollectedRun,
    IsolatedSpawner,
    IsolatedWorkspace,
    IsolationError,
    SpawnResult,
    WorkerAdapter,
    WorkerArtifacts,
    WorkerDetection,
    WorkerPrompt,
    WorkerRunResult,
    WorkerScore,
)
from muse_cli.workers import isolation as iso


# ── helpers / fixtures ────────────────────────────────────────────────


def _run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, check=True
    )
    return proc.stdout


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", "-b", "main"], path)
    _run(["git", "config", "user.email", "test@example.com"], path)
    _run(["git", "config", "user.name", "Test"], path)
    _run(["git", "config", "commit.gpgsign", "false"], path)
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    _run(["git", "add", "README.md"], path)
    _run(["git", "commit", "-q", "-m", "init"], path)
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return _init_repo(tmp_path / "repo")


class _FakeAdapter(WorkerAdapter):
    id = "fake"
    display_name = "Fake Worker"

    def __init__(
        self,
        *,
        worker_id: str = "fake",
        prompt_text: str = "do the thing",
        run_ok: bool = True,
        stdout: str = "stdout-bytes",
        stderr: str = "stderr-bytes",
        files: tuple[str, ...] = ("README.md",),
        score: float = 0.75,
    ) -> None:
        self._prompt_text = prompt_text
        self._run_ok = run_ok
        self._stdout = stdout
        self._stderr = stderr
        self._files = files
        self._score = score
        # mutate the class id so two adapter instances can have distinct ids
        # without colliding in the registry layer; here we only care about
        # this *instance's* id, which the spawner reads off the class attr.
        type(self).id = worker_id  # type: ignore[misc]
        type(self).display_name = f"Fake {worker_id}"  # type: ignore[misc]

    def detect(self) -> WorkerDetection:
        return WorkerDetection(available=True)

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        return WorkerPrompt(text=self._prompt_text, role="builder")

    def run(self, job: Any) -> WorkerRunResult:
        return WorkerRunResult(
            ok=self._run_ok,
            stdout=self._stdout,
            stderr=self._stderr,
            duration_seconds=0.001,
        )

    def collect(self, job: Any) -> WorkerArtifacts:
        return WorkerArtifacts(files=self._files, notes="ok")

    def score(self, artifacts: WorkerArtifacts) -> WorkerScore:
        return WorkerScore(value=self._score, confidence=0.5)


# ── id + path helpers ────────────────────────────────────────────────


def test_new_instance_id_unique_and_sortable():
    ids = sorted({iso.new_instance_id() for _ in range(8)})
    assert len(ids) == 8
    assert all(i.startswith("i-") for i in ids)


def test_new_instance_id_custom_prefix():
    instance = iso.new_instance_id(prefix="judge")
    assert instance.startswith("judge-")


def test_new_instance_id_sanitizes_unsafe_prefix():
    instance = iso.new_instance_id(prefix="bad/prefix")
    # prefix sanitization replaces "/" with "-"
    assert instance.startswith("bad-prefix-")


def test_agents_root_under_orchestrator_dir(tmp_path):
    expected = tmp_path / ".hermes-orchestrator" / "agents"
    assert iso.agents_root(tmp_path) == expected


def test_workspace_path_layout(tmp_path):
    expected = (
        tmp_path / ".hermes-orchestrator" / "agents" / "job1" / "fake" / "inst1"
    )
    assert iso.workspace_path(tmp_path, "job1", "fake", "inst1") == expected


def test_workspace_path_sanitizes_segments(tmp_path):
    # ``../`` etc. is reduced to a safe charset before becoming a path.
    p = iso.workspace_path(tmp_path, "../bad", "../bad", "../bad")
    assert ".." not in str(p)


# ── prepare_workspace happy path ─────────────────────────────────────


def test_prepare_workspace_creates_envelope(tmp_path):
    ws = iso.prepare_workspace(
        tmp_path,
        job_id="job-1",
        worker_id="fake",
        prompt="hello",
        state={"k": "v"},
        metadata={"requested_by": "tester"},
    )
    assert ws.root.exists() and ws.root.is_dir()
    assert ws.prompt_path.read_text(encoding="utf-8") == "hello"
    assert json.loads(ws.state_path.read_text(encoding="utf-8")) == {"k": "v"}
    assert ws.stdout_log.exists()
    assert ws.stderr_log.exists()
    assert ws.metadata_path.exists()
    assert ws.worktree is None
    assert ws.metadata == {"requested_by": "tester"}


def test_prepare_workspace_writes_sidecar_metadata(tmp_path):
    ws = iso.prepare_workspace(
        tmp_path, job_id="job-1", worker_id="fake", prompt="x"
    )
    payload = json.loads(ws.metadata_path.read_text(encoding="utf-8"))
    assert payload["job_id"] == "job-1"
    assert payload["worker_id"] == "fake"
    assert payload["instance_id"] == ws.instance_id
    assert payload["worktree"] is None


def test_prepare_workspace_assigns_unique_instance_ids(tmp_path):
    ws1 = iso.prepare_workspace(
        tmp_path, job_id="job-1", worker_id="fake", prompt="a"
    )
    ws2 = iso.prepare_workspace(
        tmp_path, job_id="job-1", worker_id="fake", prompt="b"
    )
    assert ws1.instance_id != ws2.instance_id
    assert ws1.root != ws2.root


def test_prepare_workspace_with_explicit_instance_id(tmp_path):
    ws = iso.prepare_workspace(
        tmp_path,
        job_id="job-1",
        worker_id="fake",
        instance_id="judge-alpha",
        prompt="x",
    )
    assert ws.instance_id == "judge-alpha"
    assert ws.root.name == "judge-alpha"


def test_prepare_workspace_refuses_existing_target(tmp_path):
    iso.prepare_workspace(
        tmp_path,
        job_id="job-1",
        worker_id="fake",
        instance_id="i1",
        prompt="x",
    )
    with pytest.raises(IsolationError, match="already exists"):
        iso.prepare_workspace(
            tmp_path,
            job_id="job-1",
            worker_id="fake",
            instance_id="i1",
            prompt="x",
        )


def test_prepare_workspace_rejects_unknown_repo_path(tmp_path):
    with pytest.raises(IsolationError, match="does not exist"):
        iso.prepare_workspace(
            tmp_path / "no-such-dir",
            job_id="j",
            worker_id="w",
        )


def test_prepare_workspace_empty_prompt_writes_empty_file(tmp_path):
    ws = iso.prepare_workspace(
        tmp_path, job_id="job-1", worker_id="fake"
    )
    assert ws.prompt_path.read_text(encoding="utf-8") == ""
    assert json.loads(ws.state_path.read_text(encoding="utf-8")) == {}


# ── prepare_workspace with worktrees ─────────────────────────────────


def test_prepare_workspace_with_worktree_creates_branch(repo):
    ws = iso.prepare_workspace(
        repo,
        job_id="job-A",
        worker_id="fake",
        instance_id="inst-1",
        prompt="x",
        use_worktree=True,
    )
    assert ws.worktree is not None
    assert ws.worktree.branch == "hermes/job-A/fake-inst-1"
    assert ws.worktree.path.exists()
    assert (ws.worktree.path / "README.md").exists()
    assert ws.working_dir() == ws.worktree.path
    assert ws.worktree_branch() == "hermes/job-A/fake-inst-1"


def test_prepare_workspace_per_instance_branch_isolation(repo):
    ws1 = iso.prepare_workspace(
        repo,
        job_id="job-A",
        worker_id="fake",
        instance_id="inst-1",
        use_worktree=True,
    )
    ws2 = iso.prepare_workspace(
        repo,
        job_id="job-A",
        worker_id="fake",
        instance_id="inst-2",
        use_worktree=True,
    )
    # Two instances of the same worker on the same job get distinct branches.
    assert ws1.worktree.branch != ws2.worktree.branch  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    assert ws1.worktree.path != ws2.worktree.path  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture


def test_prepare_workspace_worktree_refuses_non_git(tmp_path):
    with pytest.raises(IsolationError, match="worktree setup failed"):
        iso.prepare_workspace(
            tmp_path,
            job_id="job-A",
            worker_id="fake",
            use_worktree=True,
        )


def test_prepare_workspace_worktree_refuses_dirty(repo):
    (repo / "dirty.txt").write_text("x", encoding="utf-8")
    with pytest.raises(IsolationError, match="worktree setup failed"):
        iso.prepare_workspace(
            repo,
            job_id="job-A",
            worker_id="fake",
            use_worktree=True,
        )


def test_prepare_workspace_worktree_allow_dirty(repo):
    (repo / "scratch.txt").write_text("x", encoding="utf-8")
    ws = iso.prepare_workspace(
        repo,
        job_id="job-A",
        worker_id="fake",
        use_worktree=True,
        allow_dirty=True,
    )
    assert ws.worktree is not None


def test_working_dir_without_worktree_returns_root(tmp_path):
    ws = iso.prepare_workspace(
        tmp_path, job_id="job-1", worker_id="fake"
    )
    assert ws.working_dir() == ws.root


# ── per-workspace IO ─────────────────────────────────────────────────


def test_write_and_read_prompt(tmp_path):
    ws = iso.prepare_workspace(
        tmp_path, job_id="job", worker_id="fake", prompt="initial"
    )
    iso.write_prompt(ws, "updated")
    assert iso.read_prompt(ws) == "updated"


def test_write_state_is_atomic(tmp_path):
    ws = iso.prepare_workspace(tmp_path, job_id="job", worker_id="fake")
    iso.write_state(ws, {"phase": "running"})
    assert iso.read_state(ws) == {"phase": "running"}
    # Ensure no stale .tmp lingers next to the state file.
    leftovers = list(ws.root.glob("state.json.tmp"))
    assert leftovers == []


def test_read_state_handles_empty_file(tmp_path):
    ws = iso.prepare_workspace(tmp_path, job_id="job", worker_id="fake")
    ws.state_path.write_text("", encoding="utf-8")
    assert iso.read_state(ws) == {}


def test_append_log_stdout(tmp_path):
    ws = iso.prepare_workspace(tmp_path, job_id="job", worker_id="fake")
    iso.append_log(ws, "stdout", "line one")
    iso.append_log(ws, "stdout", "line two\n")
    contents = ws.stdout_log.read_text(encoding="utf-8")
    assert contents == "line one\nline two\n"


def test_append_log_stderr(tmp_path):
    ws = iso.prepare_workspace(tmp_path, job_id="job", worker_id="fake")
    iso.append_log(ws, "stderr", "boom")
    assert ws.stderr_log.read_text(encoding="utf-8") == "boom\n"


def test_append_log_rejects_unknown_kind(tmp_path):
    ws = iso.prepare_workspace(tmp_path, job_id="job", worker_id="fake")
    with pytest.raises(IsolationError, match="unknown log kind"):
        iso.append_log(ws, "trace", "nope")  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture


# ── metadata round-trip ──────────────────────────────────────────────


def test_read_metadata_round_trip(tmp_path):
    ws = iso.prepare_workspace(
        tmp_path,
        job_id="job-1",
        worker_id="fake",
        instance_id="i-1",
        prompt="x",
        metadata={"k": "v"},
    )
    hydrated = iso.read_metadata(tmp_path, "job-1", "fake", "i-1")
    assert hydrated.job_id == ws.job_id
    assert hydrated.worker_id == ws.worker_id
    assert hydrated.instance_id == ws.instance_id
    assert hydrated.root == ws.root
    assert hydrated.metadata == {"k": "v"}
    assert hydrated.worktree is None


def test_read_metadata_round_trip_with_worktree(repo):
    ws = iso.prepare_workspace(
        repo,
        job_id="job-1",
        worker_id="fake",
        instance_id="i-1",
        use_worktree=True,
    )
    hydrated = iso.read_metadata(repo, "job-1", "fake", "i-1")
    assert hydrated.worktree is not None
    assert hydrated.worktree.branch == ws.worktree.branch  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    assert hydrated.worktree.path == ws.worktree.path  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture


def test_read_metadata_missing_raises(tmp_path):
    with pytest.raises(IsolationError, match="no instance metadata"):
        iso.read_metadata(tmp_path, "job", "fake", "missing")


# ── list_workspaces ──────────────────────────────────────────────────


def test_list_workspaces_empty_returns_empty(tmp_path):
    assert iso.list_workspaces(tmp_path) == []


def test_list_workspaces_finds_each_instance(tmp_path):
    iso.prepare_workspace(tmp_path, job_id="job-a", worker_id="w1")
    iso.prepare_workspace(tmp_path, job_id="job-a", worker_id="w1")
    iso.prepare_workspace(tmp_path, job_id="job-a", worker_id="w2")
    iso.prepare_workspace(tmp_path, job_id="job-b", worker_id="w1")
    found = iso.list_workspaces(tmp_path)
    keys = {(w.job_id, w.worker_id) for w in found}
    assert keys == {("job-a", "w1"), ("job-a", "w2"), ("job-b", "w1")}
    assert len(found) == 4


def test_list_workspaces_filters_by_job(tmp_path):
    iso.prepare_workspace(tmp_path, job_id="job-a", worker_id="w1")
    iso.prepare_workspace(tmp_path, job_id="job-b", worker_id="w1")
    only_a = iso.list_workspaces(tmp_path, job_id="job-a")
    assert {w.job_id for w in only_a} == {"job-a"}


def test_list_workspaces_filters_by_worker(tmp_path):
    iso.prepare_workspace(tmp_path, job_id="job-a", worker_id="w1")
    iso.prepare_workspace(tmp_path, job_id="job-a", worker_id="w2")
    only_w1 = iso.list_workspaces(tmp_path, job_id="job-a", worker_id="w1")
    assert {w.worker_id for w in only_w1} == {"w1"}


def test_list_workspaces_skips_malformed_metadata(tmp_path):
    ws = iso.prepare_workspace(tmp_path, job_id="job-a", worker_id="w1")
    ws.metadata_path.write_text("not json", encoding="utf-8")
    # A second well-formed instance must still show up.
    iso.prepare_workspace(tmp_path, job_id="job-a", worker_id="w1")
    found = iso.list_workspaces(tmp_path)
    assert len(found) == 1


# ── cleanup_workspace ────────────────────────────────────────────────


def test_cleanup_workspace_without_confirm_is_no_op(tmp_path):
    ws = iso.prepare_workspace(tmp_path, job_id="job", worker_id="fake")
    assert iso.cleanup_workspace(ws) is False
    assert ws.root.exists()


def test_cleanup_workspace_with_confirm_removes_folder(tmp_path):
    ws = iso.prepare_workspace(tmp_path, job_id="job", worker_id="fake")
    assert iso.cleanup_workspace(ws, confirm=True) is True
    assert not ws.root.exists()


def test_cleanup_workspace_removes_empty_parent_dirs(tmp_path):
    ws = iso.prepare_workspace(tmp_path, job_id="job", worker_id="fake")
    parent_worker = ws.root.parent
    parent_job = parent_worker.parent
    iso.cleanup_workspace(ws, confirm=True)
    assert not parent_worker.exists()
    assert not parent_job.exists()


def test_cleanup_workspace_with_worktree(repo):
    ws = iso.prepare_workspace(
        repo,
        job_id="job",
        worker_id="fake",
        instance_id="i1",
        use_worktree=True,
    )
    wt_path = ws.worktree.path  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    assert iso.cleanup_workspace(
        ws, confirm=True, cleanup_worktree=True, repo=repo
    ) is True
    assert not wt_path.exists()


def test_cleanup_workspace_with_worktree_can_drop_branch(repo):
    ws = iso.prepare_workspace(
        repo,
        job_id="job",
        worker_id="fake",
        instance_id="i1",
        use_worktree=True,
    )
    branch = ws.worktree.branch  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    iso.cleanup_workspace(
        ws,
        confirm=True,
        cleanup_worktree=True,
        delete_branch=True,
        repo=repo,
    )
    branches = _run(["git", "branch", "--list", branch], repo).strip()
    assert branches == ""


def test_cleanup_workspace_infers_repo_from_worktree(repo):
    ws = iso.prepare_workspace(
        repo,
        job_id="job",
        worker_id="fake",
        instance_id="i1",
        use_worktree=True,
    )
    # No explicit ``repo=`` — cleanup recovers it from the worktree path.
    assert iso.cleanup_workspace(
        ws, confirm=True, cleanup_worktree=True
    ) is True


# ── IsolatedSpawner ──────────────────────────────────────────────────


def test_spawner_spawn_writes_prompt(tmp_path):
    spawner = IsolatedSpawner(tmp_path, job_id="job-1")
    adapter = _FakeAdapter(worker_id="alpha", prompt_text="hello world")
    result = spawner.spawn(adapter, job="anything")
    assert isinstance(result, SpawnResult)
    assert result.prompt.text == "hello world"
    assert result.workspace.prompt_path.read_text(encoding="utf-8") == "hello world"
    assert result.workspace.metadata["adapter"] == "_FakeAdapter"
    assert result.workspace.metadata["display_name"] == "Fake alpha"
    assert result.workspace.metadata["prompt_role"] == "builder"


def test_spawner_spawn_multiple_instances_isolated(tmp_path):
    spawner = IsolatedSpawner(tmp_path, job_id="job-1")
    adapter = _FakeAdapter(worker_id="alpha")
    r1 = spawner.spawn(adapter, job="x")
    r2 = spawner.spawn(adapter, job="x")
    assert r1.workspace.root != r2.workspace.root
    assert len(spawner.spawned()) == 2


def test_spawner_spawn_with_prompt_override(tmp_path):
    """prompt_override skips ``prepare_prompt`` and uses the caller's text."""

    class _Counter(_FakeAdapter):
        prepare_calls = 0

        def prepare_prompt(self, job):
            type(self).prepare_calls += 1
            return WorkerPrompt(text="from-adapter")

    spawner = IsolatedSpawner(tmp_path, job_id="job-1")
    result = spawner.spawn(
        _Counter(worker_id="beta"),
        job="x",
        prompt_override="explicit",
    )
    assert result.prompt.text == "explicit"
    assert result.workspace.prompt_path.read_text(encoding="utf-8") == "explicit"
    assert _Counter.prepare_calls == 0


def test_spawner_rejects_non_adapter(tmp_path):
    spawner = IsolatedSpawner(tmp_path, job_id="job-1")
    with pytest.raises(IsolationError, match="WorkerAdapter"):
        spawner.spawn("not an adapter", job="x")  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture


def test_spawner_validates_adapter_prompt_return(tmp_path):
    class _Bad(_FakeAdapter):
        def prepare_prompt(self, job):
            return "not a prompt"  # type: ignore[return-value]

    spawner = IsolatedSpawner(tmp_path, job_id="job-1")
    with pytest.raises(IsolationError, match="WorkerPrompt"):
        spawner.spawn(_Bad(worker_id="gamma"), job="x")


def test_spawner_per_spawn_worktree_override(repo):
    spawner = IsolatedSpawner(repo, job_id="job-1", use_worktrees=False)
    adapter = _FakeAdapter(worker_id="alpha")
    no_wt = spawner.spawn(adapter, job="x")
    with_wt = spawner.spawn(adapter, job="x", use_worktree=True)
    assert no_wt.workspace.worktree is None
    assert with_wt.workspace.worktree is not None


def test_spawner_collect_drives_run_collect_score(tmp_path):
    spawner = IsolatedSpawner(tmp_path, job_id="job-1")
    adapter = _FakeAdapter(worker_id="alpha", score=0.9)
    spawn = spawner.spawn(adapter, job="x")
    result = spawner.collect(spawn, job="x")
    assert isinstance(result, CollectedRun)
    assert result.run.ok is True
    assert result.score.value == 0.9

    # stdout/stderr were appended to the per-instance logs
    assert "stdout-bytes" in spawn.workspace.stdout_log.read_text(encoding="utf-8")
    assert "stderr-bytes" in spawn.workspace.stderr_log.read_text(encoding="utf-8")

    # state.json reflects the run summary
    state = iso.read_state(spawn.workspace)
    assert state["ok"] is True
    assert state["score"] == 0.9
    assert state["confidence"] == 0.5
    assert state["files"] == ["README.md"]


def test_spawner_collect_all_runs_each(tmp_path):
    spawner = IsolatedSpawner(tmp_path, job_id="job-1")
    a = _FakeAdapter(worker_id="alpha", score=0.4)
    b = _FakeAdapter(worker_id="beta", score=0.7)
    s_a = spawner.spawn(a, job="x")
    s_b = spawner.spawn(b, job="x")
    results = spawner.collect_all([s_a, s_b], job="x")
    assert [r.score.value for r in results] == [0.4, 0.7]


def test_spawner_cleanup_drops_workspace(tmp_path):
    spawner = IsolatedSpawner(tmp_path, job_id="job-1")
    adapter = _FakeAdapter(worker_id="alpha")
    spawn = spawner.spawn(adapter, job="x")
    assert spawner.cleanup(spawn, confirm=True) is True
    assert not spawn.workspace.root.exists()
    assert spawner.spawned() == []


def test_spawner_cleanup_without_confirm_is_no_op(tmp_path):
    spawner = IsolatedSpawner(tmp_path, job_id="job-1")
    adapter = _FakeAdapter(worker_id="alpha")
    spawn = spawner.spawn(adapter, job="x")
    assert spawner.cleanup(spawn) is False
    assert spawn.workspace.root.exists()
    assert len(spawner.spawned()) == 1


def test_spawner_collect_validates_run_return(tmp_path):
    class _BadRun(_FakeAdapter):
        def run(self, job):
            return "not a run result"  # type: ignore[return-value]

    spawner = IsolatedSpawner(tmp_path, job_id="job-1")
    spawn = spawner.spawn(_BadRun(worker_id="alpha"), job="x")
    with pytest.raises(IsolationError, match="WorkerRunResult"):
        spawner.collect(spawn, job="x")


def test_spawner_repo_and_job_id_exposed(tmp_path):
    spawner = IsolatedSpawner(tmp_path, job_id="job-1")
    assert spawner.repo == tmp_path.resolve()
    assert spawner.job_id == "job-1"


# ── package-level exports ────────────────────────────────────────────


def test_public_api_exports_isolation_surface():
    import muse_cli.workers as pkg

    for name in (
        "IsolatedSpawner",
        "IsolatedWorkspace",
        "IsolationError",
        "SpawnResult",
        "CollectedRun",
        "prepare_workspace",
        "list_workspaces",
        "cleanup_workspace",
        "new_instance_id",
    ):
        assert hasattr(pkg, name), name
        assert name in pkg.__all__, name


def test_isolated_workspace_is_frozen(tmp_path):
    ws = iso.prepare_workspace(tmp_path, job_id="job", worker_id="fake")
    assert isinstance(ws, IsolatedWorkspace)
    with pytest.raises(Exception):
        setattr(ws, "root", tmp_path / "other")
