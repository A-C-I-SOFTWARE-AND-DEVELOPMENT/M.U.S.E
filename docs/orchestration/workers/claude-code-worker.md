# Claude Code worker

The Claude Code worker is the local handoff adapter for Anthropic's
official `claude` CLI. It lives at
[`hermes_cli/workers/claude_code.py`](../../../hermes_cli/workers/claude_code.py)
and is meant to be invoked by an orchestrator (the enterprise council,
the kanban dispatcher, the Android orchestrator on a desktop bridge,
or a one-off script) whenever M.U.S.E. wants Claude Code's opinion on
architecture, complex refactor planning, code review, risk review, or
a final pre-merge review.

## What this worker is

- A pure-Python adapter that **prepares a workspace** on disk and
  **collects artifacts** the upstream tool writes back. Everything it
  does is observable on the filesystem.
- The single supported execution path is the official local `claude`
  binary, invoked in non-interactive mode. The adapter never:
  - scrapes or automates the Anthropic web UI,
  - hits the Anthropic API directly,
  - reads cookies or credentials out of other apps,
  - drives any unofficial control surface.
- The default mode is `handoff_required`. The adapter materialises
  the prompt and a status file, then waits for a human (or a
  separately-invoked official CLI) to drive the run.

## Files the worker writes

When `prepare_workspace(task, base_dir)` runs successfully you get:

```
<base_dir>/workers/claude-code/
├── prompt.md      # Structured handoff prompt, fed to claude
└── status.json    # Machine-readable run metadata + detection snapshot
```

The prompt has fixed section headings — `Mission`, `Repo evidence`,
`Decision ledger`, `Architecture questions`, `Risk questions`,
`Review checklist`, `Expected output`, `Scoring axes`, `Run mode`,
`Detection snapshot`. The downstream judge can rely on those headings
being present, in that order.

`status.json` captures:

- `worker` — always `"claude-code"`,
- `mode` — `"handoff_required"` or `"execute"`,
- `mission` and `decision_ledger` from the input task,
- `expected_artifacts` / `required_artifacts` arrays,
- `scoring_weights` (see below),
- `detection` — the `shutil.which` + `--version` probe result,
- `handoff_required` — convenience boolean.

## Files the worker reads back

Claude Code is asked to write the following into the same directory:

| File                       | Required | Purpose                                      |
| -------------------------- | -------- | -------------------------------------------- |
| `output.md`                | yes      | Narrative summary of findings & recs         |
| `architecture-review.md`   | yes      | Answers to architecture questions            |
| `risk-review.md`           | yes      | Risk surface, blast radius, go/no-go         |
| `patch.diff`               | no       | Unified diff if concrete code edits proposed |
| `status.json`              | yes      | Verdict + per-axis scores                    |

`patch.diff` is intentionally optional — a pure review run never
emits one, but a refactor-planning run almost always does. The
collector treats its absence as a normal "no edits proposed" signal
rather than an incomplete run.

The `status.json` Claude Code writes back must include:

```jsonc
{
  "worker": "claude-code",
  "verdict": "approve" | "revise" | "block",
  "confidence": 0.0,        // 0.0–1.0
  "scores": {
    "architecture_fit": 0.0,
    "risk_control":     0.0,
    "maintainability":  0.0,
    "correctness":      0.0,
    "repo_fit":         0.0
  }
}
```

## Scoring axes

Claude Code is scored on the axes it is best suited to evaluate. The
default weights are exported as `SCORING_WEIGHTS` and are also written
into every `status.json` so they can be audited per-run:

| Axis              | Weight | Why                                                                                |
| ----------------- | ------ | ---------------------------------------------------------------------------------- |
| `architecture_fit`| 0.30   | Does the change match existing module boundaries and design intent?                |
| `risk_control`    | 0.25   | Are blast radius, reversibility, and migration risk explicitly addressed?          |
| `maintainability` | 0.20   | Will future readers understand it without spelunking?                              |
| `correctness`     | 0.15   | Does it actually do the right thing? (Codex tends to lead on this axis.)           |
| `repo_fit`        | 0.10   | Does the diff respect this repo's conventions, naming, and existing helpers?       |

`score(axis_scores)` in the adapter combines per-axis self-reports into
a single 0.0–1.0 number using these weights. Missing axes are treated
as zero so a worker that skips the heavy axes gets penalised.

## Detection

```python
from hermes_cli.workers import claude_code

det = claude_code.detect()
print(det.available, det.path, det.version, det.notes)
```

Detection logic:

1. `shutil.which("claude")` — if missing, return `available=False` and
   record a note pointing at the install docs.
2. `claude --version` — best-effort probe with a 5-second timeout.
   Any failure (non-zero exit, timeout, unparseable output) downgrades
   to `version=None` and adds a note. The function **never raises**;
   the orchestrator can call it from a hot path safely.

The version string is parsed loosely (semver-ish) so future CLI
versions that prefix or suffix the number still match.

## Run modes

```python
prepared = claude_code.prepare_workspace(task, tmp_path)            # handoff (default)
prepared = claude_code.prepare_workspace(task, tmp_path, mode="execute")
```

`handoff_required` (default):

- Workspace is materialised, but M.U.S.E. will never invoke the CLI.
- `run_claude_cli(prepared)` refuses to do anything in this mode.
- The user (or a separate operator workflow) drives `claude`
  themselves.

`execute`:

- Caller is opting into having M.U.S.E. shell out to the local CLI.
- `run_claude_cli(prepared, allow_execute=True)` is the **only**
  supported entrypoint. Both gates are required:
  - `prepared.mode == "execute"`, **and**
  - `allow_execute=True` on the call.
- The invocation is `claude --print <prompt.md>` with the workspace as
  `cwd`. No interactive session, no auto-approve flag, no API key
  injection.

## Failure modes

| Symptom                                          | Cause                                          | Adapter response                                       |
| ------------------------------------------------ | ---------------------------------------------- | ------------------------------------------------------ |
| `claude` not on PATH                             | CLI not installed                              | `detect()` returns `available=False` with a note; `prepare_workspace` still writes the prompt so a human can drive it. |
| `claude --version` hangs                         | Old build, stuck plugin, etc.                  | 5s timeout, `version=None`, note recorded.             |
| Worker writes only some required artifacts       | Run aborted, prompt ignored, disk full         | `collect_artifacts(prepared).complete == False` and `missing_required` lists the gaps. |
| Worker writes malformed `status.json`            | LLM JSON drift                                 | `collected.status is None`, `status.json` is added to `missing_required`. |
| `run_claude_cli` called without `allow_execute`  | Caller forgot the explicit opt-in              | Returns `ExecutionResult(invoked=False, error=...)` — no shell-out. |
| `run_claude_cli` called in handoff mode          | Mode mismatch between prepare + run            | Same refusal; the prepared workspace would need to be re-prepared in execute mode. |

## Example

```python
from pathlib import Path
from hermes_cli.workers import claude_code

task = claude_code.WorkerTask(
    mission="Review the proposed kanban swarm scheduler for safety regressions.",
    repo_evidence=[
        "hermes_cli/kanban_swarm.py:80-220",
        "tests/test_kanban_swarm.py",
    ],
    decision_ledger="docs/plans/2026-05-15-acp-zed-edit-approval-diffs.md",
    architecture_questions=[
        "Does the new dispatcher preserve the single-scheduler invariant?",
        "Are the blackboard comments still bounded in size?",
    ],
    risk_questions=[
        "What happens if a worker crashes mid-update?",
        "Can a malicious worker poison the blackboard?",
    ],
    review_checklist=[
        "Confirm verifier still waits on every worker.",
        "Confirm synthesizer cannot run before verifier.",
    ],
)

prepared = claude_code.prepare_workspace(task, Path("/tmp/hermes-run"))
# ... operator runs `claude --print prompt.md` in prepared.workdir ...
result = claude_code.collect_artifacts(prepared)
if not result.complete:
    raise SystemExit(f"missing: {result.missing_required}")
weighted = claude_code.score(result.status["scores"])
print(f"Claude Code score: {weighted:.3f} — verdict {result.status['verdict']}")
```

## Tests

The unit tests at
[`tests/test_worker_claude_code.py`](../../../tests/test_worker_claude_code.py)
cover:

- `detect()` when the binary is absent,
- `detect()` when the binary is present but the version probe fails or
  times out,
- prompt generation (sections, expected output, scoring axes),
- handoff-mode `status.json` content and refusal of `run_claude_cli`,
- artifact collection with all-present, missing-required, and
  malformed-status.json cases,
- score weighting (clamping, missing axes, extra axes).

Run them with:

```bash
python -m py_compile hermes_cli/workers/claude_code.py
python -m pytest tests/test_worker_claude_code.py -q
```
