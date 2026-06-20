# Codex Worker

The Codex worker is the muse orchestrator's adapter for the **official
local Codex CLI** from OpenAI. It is shipped as
`hermes_cli/workers/codex.py` and is designed to be safe-by-default: it
prefers handoff (the operator drives Codex themselves) over execution,
and it never automates anything Codex does not officially support.

## What this worker does

1. **Detects** whether the `codex` CLI is installed on the local
   machine, recording the resolved path and a best-effort version
   string. Detection never raises — a missing binary just returns
   `available=False`.
2. **Writes a structured prompt** to
   `<workspace>/workers/codex/prompt.md` covering mission, repository
   evidence, files to inspect, files likely to edit, the exact
   implementation task, acceptance criteria, validation commands, and a
   "do not change" list.
3. **Writes `status.json`** alongside the prompt so the orchestrator (or
   the operator running the handoff) can see what state the worker is
   in.
4. **Defaults to handoff-required mode.** The worker does not invoke
   Codex unless the caller explicitly opts in.
5. When (and only when) execution is enabled and the CLI is present,
   shells out to the **official local `codex` binary**. We do not call
   `chatgpt.com`, do not scrape cookies, do not drive a web UI, and do
   not proxy a subscription.

## Output contract

After a run — whether handoff or executed — the orchestrator looks for
the following files in the worker directory:

| File                | Purpose                                            |
| ------------------- | -------------------------------------------------- |
| `output.md`         | Narrative report of what the worker did            |
| `patch.diff`        | Unified diff of all proposed edits                 |
| `changed-files.txt` | Newline-delimited list of modified paths           |
| `test-output.txt`   | Captured stdout/stderr of validation commands      |
| `status.json`       | Machine-readable status (`success`/`failed`/etc.)  |

The prompt instructs Codex to emit every file even when the run fails,
so the orchestrator never has to guess from absence.

## Modes

| Mode                 | When it applies                                                  |
| -------------------- | ---------------------------------------------------------------- |
| `handoff-required`   | Default. Codex is missing OR execution wasn't explicitly enabled |
| `executed`           | Codex CLI was detected and the operator opted into execution     |
| `execution-failed`   | Execution was attempted but the CLI errored or timed out         |

If the operator requests execution but the CLI isn't installed, the
worker downgrades to `handoff-required` and records the reason in
`status.json` — it does not crash and does not invent a fallback path.

## Enabling execution

There are two equivalent ways to opt into execution; both require the
official `codex` binary to be on `PATH`:

* **Per-call:** pass `execute=True` to `run_worker(...)`.
* **Per-process:** set `HERMES_CODEX_WORKER_EXECUTE=1` in the
  environment before invoking the orchestrator.

Even with execution enabled, the adapter only spawns the local CLI it
detected via `shutil.which("codex")`. It will not search alternate
locations, will not proxy through a remote shell, and will not retry
into a web surface.

## Python API

```python
from pathlib import Path
from hermes_cli.workers.codex import CodexTask, run_worker

task = CodexTask(
    mission="Make the Codex worker default to handoff mode.",
    task="Implement run_worker() in hermes_cli/workers/codex.py.",
    repo_evidence="Phase 09 plan — see PHASE 09 prompt.",
    files_to_inspect=["hermes_cli/workers/codex.py"],
    files_likely_to_edit=["hermes_cli/workers/codex.py"],
    acceptance_criteria=[
        "Default mode is handoff-required.",
        "Execution only runs when explicitly enabled.",
    ],
    validation_commands=[
        "python -m py_compile hermes_cli/workers/codex.py",
        "python -m pytest tests/test_worker_codex.py -q",
    ],
    do_not_change=["muse core orchestrator APIs."],
)

result = run_worker(task, workspace=Path.cwd())
print(result.mode, result.prompt_path)
```

## What this worker explicitly will not do

* It will **not** call OpenAI APIs directly to mimic a Codex session.
* It will **not** automate any web/app UI to drive Codex.
* It will **not** read cookies, browser storage, or another app's
  credential store.
* It will **not** retry past an execution failure into an unofficial
  surface.

Every external action is either an explicit subprocess launch of the
official CLI the operator authorized, or a handoff that requires the
operator to copy/paste the prompt themselves.
