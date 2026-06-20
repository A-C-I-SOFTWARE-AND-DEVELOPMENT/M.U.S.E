# Multi-agent isolated worker spawning

Phase 9 of the muse orchestrator adds a small primitive on top of
the worker adapter base ([`hermes_cli/workers/base.py`](../../hermes_cli/workers/base.py))
and the git worktree subsystem ([`hermes_cli/worktrees.py`](../../hermes_cli/worktrees.py)):
a way to spawn many *isolated agent instances* for the same job so
two adapters working on the same problem can never overwrite each
other's state.

The implementation lives in
[`hermes_cli/workers/isolation.py`](../../hermes_cli/workers/isolation.py).
Everything it does is observable on disk; nothing in this module
launches an external process, pushes to a remote, or deletes state
without an explicit `confirm=True`.

## Why isolation

muse already had two related building blocks:

| Module                                  | What it solves                                            |
|-----------------------------------------|-----------------------------------------------------------|
| `hermes_cli.worktrees`                  | Each worker gets its own `git worktree` + branch.         |
| `hermes_cli.orchestrator_parallel`      | A small executor that runs a plan of workers concurrently. |

Neither one captured the *per-instance* envelope a worker actually
needs: a folder for its prompt, a place to dump its logs, a state
file the orchestrator can read back, and a sidecar of metadata so a
human can audit what happened later. Isolation fills that gap and
makes it trivial to fan out N instances of the same `WorkerAdapter`
without colliding on filesystem paths or branch names.

## On-disk layout

```
<repo>/.hermes-orchestrator/
├── agents/
│   └── <job-id>/
│       └── <worker-id>/
│           └── <instance-id>/
│               ├── prompt.md      # text from WorkerAdapter.prepare_prompt
│               ├── state.json     # arbitrary per-instance state
│               ├── stdout.log     # append-only run logs
│               ├── stderr.log
│               └── instance.json  # sidecar metadata
└── worktrees/
    └── <job-id>/
        ├── <worker-id>-<instance-id>.worktree.json
        └── <worker-id>-<instance-id>/
            └── ...checkout of branch hermes/<job-id>/<worker-id>-<instance-id>...
```

Branches created for isolated instances follow the
`hermes/<job-id>/<worker-id>-<instance-id>` shape so two instances of
the same worker on the same job never collide.

All three path segments — `<job-id>`, `<worker-id>`, `<instance-id>`
— are sanitised through `worktrees.sanitize_segment` (charset
`[A-Za-z0-9_.-]`, length-capped) before they touch the filesystem or
a branch name. Inputs that sanitise down to nothing are rejected.

## Lifecycle

```text
   prepare_workspace ──▶  IsolatedWorkspace  ──▶  adapter.run(...)
                              │                          │
                              ▼                          ▼
                       write_state / append_log    workspace.working_dir()
                              │                          │
                              ▼                          ▼
                            list_workspaces / read_metadata
                              │
                              ▼
                       cleanup_workspace (confirm=True)
```

### Single-instance API

```python
from pathlib import Path
from hermes_cli.workers import isolation as iso

ws = iso.prepare_workspace(
    Path.cwd(),
    job_id="job-42",
    worker_id="claude-code",
    prompt="Refactor module X.",            # optional
    state={"goal": "remove dead branches"}, # optional
    metadata={"requested_by": "echerd27"},  # optional
    use_worktree=True,                       # opt-in per instance
    base_ref="main",                         # default: HEAD
    allow_dirty=False,                       # default: refuse dirty repo
)

iso.write_prompt(ws, "...updated prompt...")
iso.write_state(ws, {"status": "running"})
iso.append_log(ws, "stdout", "started\n")

# Later, in some other process:
for ws in iso.list_workspaces(Path.cwd(), job_id="job-42"):
    print(ws.instance_id, iso.read_state(ws))
```

### Adapter-driven spawning

`IsolatedSpawner` is the convenience wrapper for the common case
where the orchestrator wants to drive several `WorkerAdapter`s on the
same job:

```python
from hermes_cli.workers import IsolatedSpawner, get

spawner = IsolatedSpawner(
    repo=Path.cwd(),
    job_id="job-42",
    use_worktrees=True,
    base_ref="main",
)

a = spawner.spawn(get("claude-code"), job)
b = spawner.spawn(get("codex"), job)
c = spawner.spawn(get("aider"), job, use_worktree=False)  # per-spawn override

results = spawner.collect_all([a, b, c], job)
best = max(results, key=lambda r: r.score.value * r.score.confidence)
```

`spawn` calls `adapter.prepare_prompt(job)` and writes the rendered
prompt into the workspace. `collect` then drives `adapter.run` →
`adapter.collect` → `adapter.score`, persists stdout/stderr into the
workspace logs, and stores a small summary in `state.json` so the
artifacts survive a restart.

Per-instance worktree opt-in (`use_worktree=` on `spawn`) overrides
the spawner-wide default. That makes it easy to mix worktree-isolated
runs (a worker that mutates the working tree) with folder-only runs
(a reviewer that only writes back to its workspace).

## Cleanup

`cleanup_workspace` is the only function in the module that deletes
filesystem state, and it is opt-in three times over:

| Flag                  | Default | What it removes                                                            |
|-----------------------|---------|-----------------------------------------------------------------------------|
| `confirm=True`        | `False` | The instance folder (prompt, logs, state, sidecar).                         |
| `cleanup_worktree=True` | `False` | Also removes the attached worktree via `worktrees.cleanup_worktree`. The repo is inferred from the worktree's recorded path; pass `repo=` to override. |
| `delete_branch=True`  | `False` | Also drops the branch — uses the non-force `git branch -d` so an unmerged branch stays put. Only honoured when `cleanup_worktree=True`. |

Without `confirm=True` the call is a no-op that returns `False`. This
mirrors `worktrees.cleanup_worktree` and means a forgotten flag never
silently discards work.

After the folder is removed the helper also trims empty
`<job>/<worker>/` and `<job>/` parent dirs so an inspector doesn't
see hollow shells lying around after the last instance is gone.

## Safety summary

| Risk                                       | Mitigation                                                  |
|--------------------------------------------|-------------------------------------------------------------|
| Path traversal via job / worker id        | `worktrees.sanitize_segment` enforces a tight charset.       |
| Branch collisions between instances        | Instance id is spliced into the branch suffix.               |
| Concurrent state writes                    | `write_state` writes to `state.json.tmp` then `os.replace`.  |
| Silent deletion of workspaces or branches  | `confirm=True` (and `cleanup_worktree=True` / `delete_branch=True`) required. |
| Running on a dirty repo                    | Inherits `worktrees.create_worktree`'s `allow_dirty` default. |
| Leaking state into the user's repo         | Everything writes under `.hermes-orchestrator/`, already excluded via `.git/info/exclude`. |
| Adapter returning the wrong type           | `spawn`/`collect` validate `WorkerPrompt`/`WorkerRunResult`/`WorkerArtifacts`/`WorkerScore` before persisting. |

## Validation

```bash
python -m py_compile hermes_cli/workers/isolation.py
python -m pytest tests/test_worker_base.py tests/test_worker_registry.py tests/test_worker_isolation.py -q
```

## Cross-references

- [`worker-adapter-interface.md`](worker-adapter-interface.md) — the
  five-step adapter contract isolation composes with.
- [`parallel-workers-and-worktrees.md`](parallel-workers-and-worktrees.md)
  — the executor / worktree subsystem this module sits on top of.
- [`workers/`](workers/) — per-worker docs (Claude Code, Codex,
  Aider, Goose).
