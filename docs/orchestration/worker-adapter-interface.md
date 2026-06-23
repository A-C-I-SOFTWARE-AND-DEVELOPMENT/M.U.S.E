# Worker Adapter Interface (Phase 7)

> Status: **design / pre-implementation**. Pair this document with
> `job-controller-roadmap.md` and `orchestrator-command-roadmap.md`.
> The Python skeletons in `hermes_cli/workers/` implement the import
> shape described here but raise `NotImplementedError` for any method
> that would actually drive an external tool.

## 1. Goal

Every external coding agent muse can hand off to — Claude Code,
Codex, Aider, Goose, ChatGPT, plus muse' own local agent — needs
to be reachable through a uniform Python interface so the Job
Controller can pick between them without special-casing each one.

A *worker adapter* is the bridge: it translates a muse `Job`
(prompt + plan + context) into whatever the external tool wants,
runs it, and returns a `WorkerRun` result that the controller can
record in the decision ledger.

## 2. Required surface

Every adapter under `hermes_cli/workers/` MUST expose a single
subclass of `WorkerAdapter` (defined in
`hermes_cli/workers/base.py`).

```python
class WorkerAdapter:
    name: str
    description: str
    capabilities: frozenset[str]   # e.g. {"code", "review", "plan"}

    def available(self) -> AvailabilityReport: ...
    def prepare(self, job: Job) -> PreparedRun: ...
    def run(self, prepared: PreparedRun) -> WorkerRun: ...
    def cancel(self, run: WorkerRun) -> None: ...
    def collect_artifacts(self, run: WorkerRun) -> ArtifactBundle: ...
```

Each method is described below. All inputs and outputs are plain
dataclasses (no provider SDK types leak into the controller).

### 2.1 `available() -> AvailabilityReport`

Lightweight probe. May call `shutil.which`, read environment
variables, or check for a known config file. MUST NOT make a
network call, log in, or mutate any state.

```python
@dataclass
class AvailabilityReport:
    ok: bool
    reason: str | None = None        # human-readable if not ok
    version: str | None = None       # e.g. "codex 0.18.2"
    missing: tuple[str, ...] = ()    # missing binaries / env vars
```

If `ok` is `False`, the model router skips this adapter without
penalty (no failed-run is recorded).

### 2.2 `prepare(job) -> PreparedRun`

Translates the user's `Job` into the concrete command line, env
vars, working directory, and prompt file the worker needs. Pure
function on its inputs — does not start the worker.

```python
@dataclass
class PreparedRun:
    job_id: str
    worker: str
    argv: tuple[str, ...]
    env: Mapping[str, str]
    cwd: pathlib.Path
    stdin_payload: str | None = None
    notes: tuple[str, ...] = ()      # human-readable preflight notes
```

`prepare` is also what `/orchestrator open <job-id>` calls when the
user wants to inspect the exact handoff before it runs.

### 2.3 `run(prepared) -> WorkerRun`

Actually executes the worker. Blocking call. The controller is
sequential by default (see `job-controller-roadmap.md` §8), so
adapters do not need to manage their own concurrency primitives.

```python
@dataclass
class WorkerRun:
    run_id: str
    job_id: str
    worker: str
    status: Literal["succeeded", "failed", "cancelled", "skipped"]
    exit_code: int | None
    started_at: datetime
    ended_at: datetime
    stdout_path: pathlib.Path
    stderr_path: pathlib.Path
    error_summary: str | None = None
```

`run` MUST stream stdout/stderr to the per-run log files described
in the storage layout section of `job-controller-roadmap.md`. It
MUST NOT keep large outputs in memory.

### 2.4 `cancel(run) -> None`

Best-effort cancel. Used by `/orchestrator status` when the user
explicitly aborts a job. Adapters that wrap an interactive CLI
should send the CLI's own quit signal (e.g. `q\n` for some TUIs)
rather than `SIGKILL` when possible, so the CLI can flush state.

### 2.5 `collect_artifacts(run) -> ArtifactBundle`

After a run completes, gather anything worth surfacing back to the
user: a unified diff, a patch file, a new branch name, a Gist URL,
etc.

```python
@dataclass
class ArtifactBundle:
    diff_path: pathlib.Path | None = None
    patch_path: pathlib.Path | None = None
    branch: str | None = None
    extra: Mapping[str, str] = field(default_factory=dict)
```

The bundle is what `/orchestrator publish <job-id>` consumes when
the user picks a winning run.

## 3. Capability tags

`WorkerAdapter.capabilities` is the model router's only lever for
matching prompts to workers. Reserved tags for Phase 7:

| Tag           | Meaning                                                                                 |
| ------------- | --------------------------------------------------------------------------------------- |
| `code`        | Can write or edit source code in a repository.                                          |
| `review`      | Can produce a code review without writing.                                              |
| `plan`        | Can produce a structured plan-of-record.                                                |
| `chat`        | Can answer a free-form question (no repo required).                                     |
| `local`       | Runs entirely on the user's machine (no remote call).                                   |
| `handoff`     | Does not execute itself — produces a prompt for the user to paste into an external UI.  |
| `interactive` | Requires a PTY / terminal session (not pipe-friendly).                                  |
| `long-task`   | Suitable for background execution; the controller may detach and poll.                  |

Capabilities are advisory. The router treats them as soft hints,
not hard filters, except for `handoff` (which means "no `run` is
actually performed — the user must complete the loop").

## 4. Failure semantics

An adapter signals failure by returning `WorkerRun(status="failed")`
with `error_summary` populated. Adapters MUST NOT raise an
exception out of `run` — failures are data, not exceptions, so the
controller can log them in the ledger and move on. Only programmer
errors (e.g. a bug inside the adapter) should propagate.

`cancel` may raise if the run id is unknown; the controller treats
that as a no-op.

## 5. Adapter inventory (Phase 7)

| Module                                    | Worker name        | Status     | Notes                                                                                 |
| ----------------------------------------- | ------------------ | ---------- | ------------------------------------------------------------------------------------- |
| `hermes_cli/workers/hermes_local.py`      | `hermes_local`     | skeleton   | Drives muse' own one-shot pipeline (`muse -z`).                                   |
| `hermes_cli/workers/codex.py`             | `codex`            | skeleton   | Wraps `codex exec` (OpenAI Codex CLI).                                                |
| `hermes_cli/workers/claude_code.py`       | `claude_code`      | skeleton   | Wraps `claude` (Claude Code CLI), respects PTY requirement.                           |
| `hermes_cli/workers/aider.py`             | `aider`            | skeleton   | Wraps `aider` with `--yes` and a scoped file list.                                    |
| `hermes_cli/workers/goose.py`             | `goose`            | skeleton   | Wraps `goose run` (Block's Goose CLI).                                                |
| `hermes_cli/workers/chatgpt_handoff.py`   | `chatgpt_handoff`  | skeleton   | `handoff` capability — builds a prompt and surfaces it for manual paste.              |

Each skeleton lists its expected binary, env vars, and known quirks
in its module docstring. None of them import the external SDK at
module load time; all of that is deferred until `available()` or
`run()` is called for the first time.

## 6. Adding a new adapter

1. Create `hermes_cli/workers/<name>.py`.
2. Subclass `WorkerAdapter` and set `name`, `description`,
   `capabilities`.
3. Implement `available`, `prepare`, `run`, `cancel`,
   `collect_artifacts`. Leave the body raising
   `NotImplementedError` if the work is still pending — the
   controller will treat the worker as unavailable until then.
4. Register the adapter in `hermes_cli/workers/__init__.py`
   (the `BUILTIN_ADAPTERS` tuple).
5. Update `worker-adapter-interface.md` (this file) with the new
   row in §5.
6. Add a unit test under `tests/orchestrator/` that imports the
   adapter and exercises `available()` in a sandboxed PATH.

## 7. Non-goals

- This document does **not** describe the model router. See
  `orchestrator-command-roadmap.md` §6 for `/model-router explain`.
- It does not describe how AI Radar capability data is collected or
  refreshed. See `orchestrator-command-roadmap.md` §5
  (`/ai-radar update`).
- It does not specify the publish step's exact mechanics — that
  depends on the target worker and lives in each adapter's
  `collect_artifacts` plus the controller's publish handler.
