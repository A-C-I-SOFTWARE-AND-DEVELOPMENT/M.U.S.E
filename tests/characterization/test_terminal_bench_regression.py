"""Characterization tests for the recorded Terminal-Bench runner failure.

WHY THIS FILE EXISTS
====================

Two artifacts sit at the repository root and disagree about the same task:

    terminal-bench-test.jsonl     2026-07-20T13:24:17
        {"task_id": "sample_create_file", ..., "setup_exit_code": 0,
         "test_exit_code": 1, "score": 0, "completed": false,
         "api_calls": 1}                      <-- and NO "error" field

    terminal-bench-results.jsonl  2026-07-20T13:35:13
        {"task_id": "sample_create_file", ..., "test_exit_code": 0,
         "score": 1, "completed": true, "api_calls": 2}

Eleven minutes apart, same task, same model, no code change: a failure and
then a pass. **Both states matter.** The failing row is the interesting one,
because of what it does not contain. ``api_calls: 1`` with an empty
conversation means the very first provider call raised; the runner caught it
in ``except Exception: ... break``, logged the message to stderr where the
artifact never saw it, ran ``test_script`` anyway, and recorded the resulting
non-zero exit as ``score: 0`` — a number that reads as "the agent tried and
failed" about a run in which the agent never took a turn.

That is defect **D1**, and it still reproduced on 2026-08-16 against the
pre-fix runner: pointing the runner at a closed port produced a row that
matched the recorded July failure field for field, including the missing
``error`` key.

Investigating it surfaced defect **D2** in the same file. ``run_batch``
appended a ``{"__summary__": ...}`` row to the very ``results.jsonl`` that
``research_fabric.verifier.terminal_bench.verify`` grades. That verifier
counts every row and scores a row with no ``score`` as a failure, so the
recorded **1/1 (100%) passing run above grades as 0.5000** — below
``catalog.ABSOLUTE_FLOOR = 0.80``. A perfect Terminal-Bench run failed the
promotion ratchet's floor. ``test_summary_row_used_to_halve_a_perfect_run``
below reproduces that on the real recorded artifact.

SCOPE NOTE (§29.2): the runner's built-in ``SAMPLE_TASKS`` are a runner
sanity fixture. Nothing here is, or supports, an official Terminal-Bench
score.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Optional

import pytest

from benchmarks import terminal_bench_runner as tbr
from benchmarks.terminal_bench_runner import (
    STATUS_PROVIDER_ERROR,
    STATUS_RUNNER_ERROR,
    STATUS_SCORED,
    STATUS_SETUP_FAILED,
    TerminalBenchRunner,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# The two recorded artifacts this file descends from.
RECORDED_FAILURE = REPO_ROOT / "terminal-bench-test.jsonl"
RECORDED_PASS = REPO_ROOT / "terminal-bench-results.jsonl"


# ---------------------------------------------------------------------------
# Scripted provider + environment doubles
# ---------------------------------------------------------------------------


class _FakeFunction:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, idx: int, name: str, arguments: str) -> None:
        self.id = f"call_{idx}"
        self.type = "function"
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content: Optional[str], tool_calls: Optional[list]) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeResponse:
    def __init__(self, message: _FakeMessage) -> None:
        self.choices = [_FakeChoice(message)]


class _Completions:
    def __init__(self, client: "ScriptedClient") -> None:
        self._client = client

    def create(self, **kwargs: Any) -> _FakeResponse:
        return self._client._next(kwargs)


class _Chat:
    def __init__(self, client: "ScriptedClient") -> None:
        self.completions = _Completions(client)


class ScriptedClient:
    """The smallest thing the runner will accept as an OpenAI client.

    ``script`` is a list of turns consumed in order. A turn is either:

    * an ``Exception`` instance — raised, standing in for a provider failure;
    * a ``list`` of ``(tool_name, arguments_dict)`` — an assistant turn with
      tool calls;
    * a ``str`` — a final assistant message with no tool calls.

    Running past the end of the script raises, so an over-eager loop is a
    loud failure rather than a hang.
    """

    def __init__(self, script: list, base_url: str = "https://example.invalid/v1") -> None:
        self.script = list(script)
        self.base_url = base_url
        self.calls: list[dict[str, Any]] = []
        self.chat = _Chat(self)

    def _next(self, kwargs: dict[str, Any]) -> _FakeResponse:
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("ScriptedClient exhausted: runner made an extra call")
        turn = self.script.pop(0)
        if isinstance(turn, BaseException):
            raise turn
        if isinstance(turn, list):
            tool_calls = [
                _FakeToolCall(i, name, json.dumps(args))
                for i, (name, args) in enumerate(turn)
            ]
            return _FakeResponse(_FakeMessage(None, tool_calls))
        return _FakeResponse(_FakeMessage(str(turn), None))


class FakeEnvironment:
    """In-memory stand-in for LocalEnvironment.

    ``responses`` maps a substring of the command to ``(output, returncode)``.
    Anything unmatched returns ``("", 0)``. ``cleaned_up`` records that the
    runner released the environment.
    """

    def __init__(self, responses: Optional[list] = None) -> None:
        self.responses = list(responses or [])
        self.commands: list[str] = []
        self.cleaned_up = 0

    def execute(self, command: str, timeout: Optional[int] = None) -> dict[str, Any]:
        self.commands.append(command)
        for needle, output, returncode in self.responses:
            if needle in command:
                return {"output": output, "returncode": returncode}
        return {"output": "", "returncode": 0}

    def cleanup(self) -> None:
        self.cleaned_up += 1


@pytest.fixture
def fake_env(monkeypatch):
    """Install a FakeEnvironment factory and hand back a setter for it."""
    holder: dict[str, FakeEnvironment] = {}

    def install(env: FakeEnvironment) -> FakeEnvironment:
        holder["env"] = env
        return env

    def factory(**_kwargs: Any) -> FakeEnvironment:
        return holder["env"]

    monkeypatch.setattr(tbr, "create_environment", factory)
    install(FakeEnvironment())
    return install


def _runner(client: ScriptedClient, **over: Any) -> TerminalBenchRunner:
    kwargs: dict[str, Any] = dict(
        model="kimi-k3",
        base_url="https://example.invalid/v1",
        api_key="test-key-not-real",
        env_type="local",
        max_iterations=3,
        command_timeout=5,
        api_retries=0,          # offline and fast
        retry_backoff_seconds=0.0,
    )
    kwargs.update(over)
    runner = TerminalBenchRunner(**kwargs)
    runner.client = client
    return runner


TASK = {
    "id": "sample_create_file",
    "instruction": "Create a file at /tmp/bench_hello.txt containing 'hello terminal-bench'.",
    "setup_script": "rm -f /tmp/bench_hello.txt",
    "test_script": "test -f /tmp/bench_hello.txt",
    "tags": ["easy", "file"],
}


# ---------------------------------------------------------------------------
# The recorded failure itself
# ---------------------------------------------------------------------------


def test_recorded_artifacts_still_disagree_about_the_same_task() -> None:
    """Pin the two recorded states this file descends from.

    If either artifact is ever rewritten, this test says so loudly rather
    than letting the provenance quietly evaporate.
    """
    assert RECORDED_FAILURE.is_file(), f"missing recorded failure: {RECORDED_FAILURE}"
    assert RECORDED_PASS.is_file(), f"missing recorded pass: {RECORDED_PASS}"

    fail_row = json.loads(RECORDED_FAILURE.read_text(encoding="utf-8").splitlines()[0])
    pass_row = json.loads(RECORDED_PASS.read_text(encoding="utf-8").splitlines()[0])

    assert fail_row["task_id"] == pass_row["task_id"] == "sample_create_file"

    # The failure: one API call, no conversation past the prompt, score 0 ...
    assert fail_row["score"] == 0
    assert fail_row["completed"] is False
    assert fail_row["api_calls"] == 1
    assert fail_row["setup_exit_code"] == 0       # the environment was fine
    assert fail_row["test_exit_code"] == 1
    # ... and, the whole point, no recorded reason.
    assert "error" not in fail_row, (
        "the recorded failure carried no error field — that is the defect"
    )

    # The pass, eleven minutes later, same task and model.
    assert pass_row["score"] == 1
    assert pass_row["completed"] is True
    assert pass_row["api_calls"] == 2
    assert fail_row["metadata"]["model"] == pass_row["metadata"]["model"]


# ---------------------------------------------------------------------------
# D1 — a provider error is no longer recorded as a score of 0
# ---------------------------------------------------------------------------


def test_provider_error_is_not_scored_and_keeps_its_reason(fake_env) -> None:
    """The exact shape of the July failure, now recorded honestly."""
    fake_env(FakeEnvironment(responses=[("test -f", "", 1)]))
    boom = ConnectionError("Connection error.")
    runner = _runner(ScriptedClient([boom]))

    row = runner.run_task(dict(TASK))

    assert row["status"] == STATUS_PROVIDER_ERROR
    assert row["scored"] is False
    # ABSENT, never zero: the agent never took a turn.
    assert row["score"] is None
    assert row["api_calls"] == 1
    assert row["completed"] is False
    # The reason survives into the artifact instead of dying on stderr.
    assert row["error"]["type"] == "ConnectionError"
    assert "Connection error." in row["error"]["message"]
    assert row["error"]["attempts"] == 1
    # test_script still ran, and its exit code is kept as a diagnostic.
    assert row["test_exit_code"] == 1


def test_transient_provider_failure_is_retried_and_the_task_still_scores(fake_env) -> None:
    """The 'later passed' state, reproduced automatically.

    The July fix was a human re-running the command eleven minutes later.
    A bounded retry does the same thing without a human.
    """
    fake_env(FakeEnvironment(responses=[("test -f", "", 0)]))
    client = ScriptedClient([
        ConnectionError("Connection error."),   # attempt 1 — transient
        "done, the file is written",            # attempt 2 — succeeds
    ])
    runner = _runner(client, api_retries=1, retry_backoff_seconds=0.0)

    row = runner.run_task(dict(TASK))

    assert row["status"] == STATUS_SCORED
    assert row["scored"] is True
    assert row["score"] == 1
    assert row["error"] is None
    assert len(client.calls) == 2, "the transient failure was not retried"


def test_a_real_task_failure_is_still_scored_zero(fake_env) -> None:
    """The fix must not launder genuine failures into 'unscored'.

    The agent ran, finished, and test_script rejected its work. That is a
    measurement, and it stays a zero.
    """
    fake_env(FakeEnvironment(responses=[("test -f", "", 1)]))
    runner = _runner(ScriptedClient(["I could not do it"]))

    row = runner.run_task(dict(TASK))

    assert row["status"] == STATUS_SCORED
    assert row["scored"] is True
    assert row["score"] == 0
    assert row["completed"] is True
    assert row["error"] is None


def test_setup_failure_is_unscored_not_a_zero(fake_env) -> None:
    """A task whose environment never got set up was never attempted."""
    fake_env(FakeEnvironment(responses=[("rm -f", "mkdir: permission denied", 1)]))
    runner = _runner(ScriptedClient([]))

    row = runner.run_task(dict(TASK))

    assert row["status"] == STATUS_SETUP_FAILED
    assert row["scored"] is False
    assert row["score"] is None
    assert row["setup_exit_code"] == 1
    assert "permission denied" in row["error"]["message"]


# ---------------------------------------------------------------------------
# D1 at batch level — unscored rows never enter the denominator
# ---------------------------------------------------------------------------


def _two_task_batch() -> list[dict[str, Any]]:
    a = dict(TASK, id="task_a")
    b = dict(TASK, id="task_b")
    return [a, b]


def test_batch_keeps_unscored_rows_out_of_results_jsonl(tmp_path, fake_env) -> None:
    fake_env(FakeEnvironment(responses=[("test -f", "", 0)]))
    client = ScriptedClient([
        "task a done",                          # task_a scores 1
        ConnectionError("Connection error."),   # task_b: provider dies
    ])
    runner = _runner(client)
    out = tmp_path / "results.jsonl"

    summary = runner.run_batch(_two_task_batch(), output_file=str(out))

    scored = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert [r["task_id"] for r in scored] == ["task_a"]
    assert all(r["scored"] is True for r in scored)

    sidecars = TerminalBenchRunner.sidecar_paths(str(out))
    unscored_text = Path(sidecars["unscored"]).read_text(encoding="utf-8")
    unscored = [json.loads(x) for x in unscored_text.splitlines() if x.strip()]
    assert [r["task_id"] for r in unscored] == ["task_b"]
    assert unscored[0]["status"] == STATUS_PROVIDER_ERROR
    assert unscored[0]["error"]["type"] == "ConnectionError"

    # Accuracy is over scored tasks only: 1/1, not 1/2.
    assert summary["scored"] == 1
    assert summary["unscored"] == 1
    assert summary["passed"] == 1
    assert summary["accuracy"] == 1.0
    assert summary["accuracy_basis"] == "scored_tasks_only"
    assert summary["unscored_by_status"] == {STATUS_PROVIDER_ERROR: 1}

    # And the summary is a sidecar, not a row in the graded file (D2).
    written = json.loads(Path(sidecars["summary"]).read_text(encoding="utf-8"))
    assert written["accuracy"] == 1.0


def test_batch_with_nothing_scored_reports_absent_not_zero(tmp_path, fake_env) -> None:
    """A run that measured nothing must not report 0% accuracy.

    0.0 reads as "every task was attempted and failed". The truth is that no
    task was measured at all.
    """
    fake_env(FakeEnvironment())
    client = ScriptedClient([
        ConnectionError("Connection error."),
        ConnectionError("Connection error."),
    ])
    runner = _runner(client)
    out = tmp_path / "results.jsonl"

    summary = runner.run_batch(_two_task_batch(), output_file=str(out))

    assert summary["accuracy"] is None
    assert summary["scored"] == 0
    assert summary["unscored"] == 2
    assert out.read_text(encoding="utf-8").strip() == ""


def test_runner_exception_is_recorded_as_unscored(tmp_path, monkeypatch, fake_env) -> None:
    """An exception outside the provider call is also not a benchmark zero."""
    fake_env(FakeEnvironment())
    runner = _runner(ScriptedClient([]))

    def explode(_task):
        raise RuntimeError("environment creation blew up")

    monkeypatch.setattr(runner, "run_task", explode)
    out = tmp_path / "results.jsonl"
    summary = runner.run_batch([dict(TASK)], output_file=str(out))

    assert summary["scored"] == 0
    assert summary["unscored_by_status"] == {STATUS_RUNNER_ERROR: 1}
    unscored_path = Path(TerminalBenchRunner.sidecar_paths(str(out))["unscored"])
    row = json.loads(unscored_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["error"]["type"] == "RuntimeError"
    assert "blew up" in row["error"]["message"]


# ---------------------------------------------------------------------------
# D2 — the summary row was graded as a failed task
# ---------------------------------------------------------------------------


def _verify(run_dir: Path):
    from hermes_cli.jarvis_prime.research_fabric.verifier import terminal_bench as verifier

    return verifier.verify(run_dir)


def test_summary_row_used_to_halve_a_perfect_run(tmp_path) -> None:
    """Reproduce D2 on the real recorded artifact.

    ``terminal-bench-results.jsonl`` records 1 task, 1 passed. Graded with
    the legacy layout, the ``__summary__`` row is counted as a second,
    failing task and the run scores 0.5 — under ABSOLUTE_FLOOR = 0.80.
    """
    from hermes_cli.jarvis_prime.research_fabric.catalog import ABSOLUTE_FLOOR

    legacy = tmp_path / "legacy"
    legacy.mkdir()
    shutil.copy(RECORDED_PASS, legacy / "results.jsonl")

    score = _verify(legacy)
    assert score.raw["total"] == 2, "the __summary__ row is counted as a task"
    assert score.correctness == pytest.approx(0.5)
    assert score.correctness < ABSOLUTE_FLOOR, (
        "a 1/1 Terminal-Bench run graded below the promotion floor"
    )


def test_runner_no_longer_writes_a_summary_row_into_the_graded_file(
    tmp_path, fake_env
) -> None:
    """The same perfect run, written by the fixed runner, grades as 1.0."""
    fake_env(FakeEnvironment(responses=[("test -f", "", 0)]))
    runner = _runner(ScriptedClient(["done"]))
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    out = run_dir / "results.jsonl"

    runner.run_batch([dict(TASK)], output_file=str(out))

    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) == 1
    assert all("__summary__" not in r for r in rows)

    score = _verify(run_dir)
    assert score.raw["total"] == 1
    assert score.correctness == pytest.approx(1.0)


def test_include_summary_row_restores_the_legacy_layout(tmp_path, fake_env) -> None:
    """The old layout is opt-in, not deleted — but it still miscounts."""
    fake_env(FakeEnvironment(responses=[("test -f", "", 0)]))
    runner = _runner(ScriptedClient(["done"]))
    run_dir = tmp_path / "legacy_run"
    run_dir.mkdir()
    out = run_dir / "results.jsonl"

    runner.run_batch([dict(TASK)], output_file=str(out), include_summary_row=True)

    lines = [x for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(lines) == 2
    assert "__summary__" in json.loads(lines[1])
    # Documenting why the default is off.
    assert _verify(run_dir).correctness == pytest.approx(0.5)


def test_all_unscored_batch_fails_closed_at_the_verifier(tmp_path, fake_env) -> None:
    """No measurement must never look like a graded 0 to the ratchet.

    An empty results file makes the verifier report ``ran=False``, which is
    the fail-closed branch. What it must NOT do is report a confident zero
    from rows that were never measurements.
    """
    fake_env(FakeEnvironment())
    runner = _runner(ScriptedClient([ConnectionError("Connection error.")]))
    run_dir = tmp_path / "dead_run"
    run_dir.mkdir()

    runner.run_batch([dict(TASK)], output_file=str(run_dir / "results.jsonl"))

    score = _verify(run_dir)
    assert score.ran is False
    assert score.accepted is False


# ---------------------------------------------------------------------------
# End-to-end against the real shell environment
# ---------------------------------------------------------------------------


def _bash_available() -> bool:
    if shutil.which("bash"):
        return True
    try:
        from tools.environments.local import _find_bash

        return bool(_find_bash())
    except Exception:
        return False


@pytest.mark.skipif(not _bash_available(), reason="no bash on this host")
def test_end_to_end_sample_task_scores_one_with_a_working_provider(tmp_path) -> None:
    """Reproduce the *passing* recorded state through the real environment.

    Only the provider is scripted; setup_script, the terminal tool and
    test_script all run for real, which is what the recorded 13:35 row did.
    """
    task = dict(tbr.SAMPLE_TASKS[0])
    client = ScriptedClient([
        [("terminal", {"command": "printf 'hello terminal-bench\\n' > /tmp/bench_hello.txt"})],
        [("terminal", {"command": 'echo "TERMINAL_BENCH_FINAL_OUTPUT done"'})],
    ])
    runner = _runner(client, command_timeout=60)
    out = tmp_path / "results.jsonl"

    summary = runner.run_batch([task], output_file=str(out))

    assert summary["scored"] == 1, f"task was not scored: {summary}"
    assert summary["passed"] == 1, f"expected the sample task to pass: {summary}"
    assert summary["accuracy"] == 1.0
    row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert row["status"] == STATUS_SCORED
    assert row["test_exit_code"] == 0
    assert row["completed"] is True
