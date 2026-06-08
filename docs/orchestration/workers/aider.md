# Aider worker

The Aider worker is the M.U.S.E. adapter for [Aider](https://aider.chat),
a git-native pair-programming CLI. It is one of the local CLI agents
M.U.S.E. can hand work to without ever calling a hosted API on the
user's behalf — the user already has Aider installed and configured.

## When to use Aider

Aider is the right tool when the change is:

- **Git-native** — Aider tracks the diff and keeps the working tree
  honest.
- **Small or medium** — Aider's repo-map shines on focused changes
  inside a handful of files.
- **Repo-map guided** — Aider already knows how to crawl the repo for
  symbols; let it pick neighboring files when the task touches a
  module.
- **Lint or test repair** — Aider can drive a tight edit ➜ run ➜ fix
  loop locally.
- **Pair programming** — when the human wants to stay in the loop and
  review each suggestion.

Reach for a different worker when the task needs an extension/recipe
(use Goose), a long autonomous run (use a hosted agent), or
filesystem-wide refactors that the repo-map cannot summarize.

## Lifecycle

```
Caller
  │
  ▼
workers.aider.run(task, workspace, execute=False, ...)
  │
  ├─ ensure_workspace(workspace)
  ├─ render_prompt(task)            ➜ workspace/prompt.md
  ├─ detect_command("aider")
  ├─ build_handoff_command(...)
  │
  ├─ execute=False (default) ────────────────────────────────────┐
  │     └─ write status.json with status="handoff_required"     │
  │                                                              │
  └─ execute=True                                                │
        ├─ command missing  ➜ status="command_not_found"        │
        └─ subprocess.run(aider --no-auto-commits ...)          │
              ├─ capture stdout/stderr ➜ output.md              │
              ├─ collect_git_artifacts ➜ patch.diff +           │
              │                          changed-files.txt      │
              └─ status="executed" or "failed"                  │
                                                                ▼
                                              caller surfaces WorkerResult
```

## Workspace layout

```
workspace/
├── prompt.md          # always written
├── status.json        # always written (machine-readable for the dashboard)
├── output.md          # only when execute=True and the binary launched
├── patch.diff         # only when the workspace's repo_root is a git checkout
└── changed-files.txt  # only when the workspace's repo_root is a git checkout
```

## Default mode is handoff-required

`run(..., execute=False)` is the default. M.U.S.E. writes the prompt and
the status file, then surfaces the printed command for the user to run:

```text
aider --no-auto-commits --no-stream --no-pretty --no-check-update \
      --no-show-release-notes --no-analytics \
      tests/test_login.py app/auth.py \
      --message-file /tmp/ws/prompt.md
```

The user copies, runs, and stays in control. **No background launch.
No automated yes.**

## Safe flags only

When `execute=True`, the worker passes only the conservative flag set
documented as safe for non-interactive use:

| Flag                       | Why                                       |
| -------------------------- | ----------------------------------------- |
| `--no-auto-commits`        | Human commits, not the orchestrator.      |
| `--no-stream`              | Deterministic captured output.            |
| `--no-pretty`              | No ANSI in captured logs.                 |
| `--no-check-update`        | No background network noise.              |
| `--no-show-release-notes`  | Quiet startup.                            |
| `--no-analytics`           | No telemetry on the user's behalf.        |

Flags M.U.S.E. **never** adds automatically:

- `--yes-always` (auto-applies every suggestion)
- `--auto-commits`
- anything that pushes, force-updates, or resets the working tree.

If the user wants any of those, they pass them via
`AiderConfig.extra_args` on their own initiative.

## Configuration

```python
from hermes_cli.workers import WorkerTask
from hermes_cli.workers.aider import AiderConfig, run

result = run(
    WorkerTask(
        title="Fix the broken auth test",
        instructions="The login flow regression test fails after the "
                     "session-cookie refactor. Track down the breakage and fix it.",
        files=["tests/test_login.py", "app/auth.py"],
    ),
    workspace="/tmp/hermes/aider-001",
    config=AiderConfig(model="sonnet", timeout_seconds=600),
)
```

`AiderConfig` fields:

- `command` — binary name (default `"aider"`).
- `model` — optional `--model NAME` passthrough.
- `extra_args` — tuple of extra arguments appended after the safe set.
- `timeout_seconds` — wall-clock cap when `execute=True` (default 600).

## Failure modes

| `WorkerStatus`        | When                                                   |
| --------------------- | ------------------------------------------------------ |
| `handoff_required`    | Default — prompt written, user runs the printed cmd.  |
| `command_not_found`   | `execute=True` but `aider` is not on `PATH`.           |
| `executed`            | `aider` returned a code; output + diff captured.       |
| `failed`              | Timed out, OSError on launch, or the worker erred.     |

Even on the failure paths, `status.json` is always written so the
dashboard can render the box.

## Limits

- M.U.S.E. does not install Aider for the user — that is a deliberate
  choice to avoid silently pulling network dependencies.
- The worker cannot drive Aider's interactive `/commands`; it sends a
  single prompt via `--message-file`.
- `patch.diff` is collected against `repo_root` after the run; if the
  workspace is outside a git checkout, no diff is produced and that
  is reported truthfully in `status.json`.
