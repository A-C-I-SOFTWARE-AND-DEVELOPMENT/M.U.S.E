# Goose worker

The Goose worker is the M.U.S.E. adapter for
[Block/Goose](https://block.github.io/goose/), an open-source local
agent runtime with a recipe + extension model. Like every M.U.S.E.
worker, the adapter only invokes the user's local `goose` CLI — M.U.S.E.
never talks to a hosted provider on the user's behalf.

## When to use Goose

Goose is the right tool when the task is:

- **Recipe-driven** — there is (or you can write) a Goose recipe that
  encodes the workflow.
- **Extension-driven** — the task leans on Goose extensions
  (developer, files, web fetch, MCP servers, …) more than on raw shell.
- **Provider experimentation** — you want to try the same task across
  Goose-supported providers without re-plumbing prompts.
- **Desktop / CLI workflows** — the task runs comfortably on the
  user's machine without needing a hosted long-running agent.

Reach for a different worker when the change is a tight git-native
edit (use Aider), a one-shot ad-hoc fix (any CLI agent works), or
something that needs a hosted long-running agent.

## Lifecycle

```
Caller
  │
  ▼
workers.goose.run(task, workspace, execute=False, ...)
  │
  ├─ ensure_workspace(workspace)
  ├─ render_prompt(task)            ➜ workspace/prompt.md
  ├─ detect_command("goose")
  ├─ build_handoff_command(...)
  │
  ├─ execute=False (default) ────────────────────────────────────┐
  │     └─ write status.json with status="handoff_required"     │
  │                                                              │
  └─ execute=True                                                │
        ├─ command missing  ➜ status="command_not_found"        │
        └─ subprocess.run(goose run --no-session ...)           │
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
status file, then surfaces a copy-pasteable command for the user:

```text
goose run --no-session \
          --recipe recipes/summarize.yaml \
          --with-extension developer \
          --with-extension files \
          --instructions /tmp/ws/prompt.md
```

The user reviews, runs, and stays in control. **M.U.S.E. never invokes
Goose automatically with auto-approval flags.**

## Safe defaults

When `execute=True`, the worker passes only conservative arguments:

| Argument               | Why                                                |
| ---------------------- | -------------------------------------------------- |
| `run`                  | Goose's non-interactive subcommand.                |
| `--no-session`         | Avoids polluting the user's interactive history.   |
| `--instructions FILE`  | Feeds the worker-tuned prompt.                     |
| `--recipe FILE`        | Optional; only when caller supplies one.           |
| `--with-extension X`   | Optional; only the extensions caller requested.    |

Flags M.U.S.E. **never** adds automatically:

- Any "auto-approve / yes-to-all" toggle.
- Anything that pushes, force-updates, or resets the working tree.
- Anything that installs extensions silently — if a needed extension
  is missing, the prompt asks the user to install it first.

If the user wants any of those, they pass them via
`GooseConfig.extra_args` on their own initiative.

## Configuration

```python
from hermes_cli.workers import WorkerTask
from hermes_cli.workers.goose import GooseConfig, run

result = run(
    WorkerTask(
        title="Summarize today's logs",
        instructions="Use the files extension to read ./logs/today.txt "
                     "and produce a 5-bullet executive summary in summary.md.",
        files=["logs/today.txt"],
    ),
    workspace="/tmp/hermes/goose-001",
    config=GooseConfig(
        recipe="recipes/summarize.yaml",
        extensions=("developer", "files"),
        timeout_seconds=900,
    ),
)
```

`GooseConfig` fields:

- `command` — binary name (default `"goose"`).
- `recipe` — optional path to a Goose recipe YAML.
- `extensions` — tuple of `--with-extension` values.
- `extra_args` — tuple of extra arguments appended after the safe set.
- `timeout_seconds` — wall-clock cap when `execute=True` (default 900).

## Failure modes

| `WorkerStatus`        | When                                                   |
| --------------------- | ------------------------------------------------------ |
| `handoff_required`    | Default — prompt written, user runs the printed cmd.  |
| `command_not_found`   | `execute=True` but `goose` is not on `PATH`.           |
| `executed`            | `goose` returned a code; output + diff captured.       |
| `failed`              | Timed out, OSError on launch, or the worker erred.     |

Even on the failure paths, `status.json` is always written so the
dashboard can render the box.

## Limits

- M.U.S.E. does not install Goose or any extensions for the user.
- The worker drives a single `goose run` invocation; long-running
  interactive sessions are out of scope.
- Recipe and extension paths are passed through verbatim — the user
  is responsible for keeping them accessible to the `goose` process.
- The adapter never automates unsupported subscription UIs; only the
  local `goose` CLI is invoked.
