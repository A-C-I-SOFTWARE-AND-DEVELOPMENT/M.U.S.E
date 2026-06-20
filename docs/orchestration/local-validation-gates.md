# Local Validation Gates

Phase 14 of the local orchestrator gives muse a publish-blocking
quality gate. Before any "publish" action — committing,
opening a PR, exporting a job folder, handing artefacts off to
another agent — muse runs `hermes_cli.validation.ValidationRunner`
against the workspace and checks the result. If a check tagged
`critical` produces a `fail`, the publish gate stays **closed**
regardless of what else passed.

This document is the design reference. The user-facing entry point
is the [`local-quality-gate` skill](../../skills/local-quality-gate/SKILL.md).

## Goals

1. **Catch obvious mistakes locally.** Don't ship a commit that
   stages a `.env`, leaves a Python file with a syntax error, or
   ships a SKILL.md that the loader can't parse.
2. **Be honest about cost.** Safe checks run every pass.
   Expensive ones (full test suite, gradle build, apktool) require
   `allow_expensive=True` so the agent doesn't accidentally burn
   ten minutes of CPU on a tiny change.
3. **Never become a substitute for human review.** The gate's
   value is in flagging mechanical regressions; it does not opine
   on code quality and it does not auto-fix anything.

## Policy

Every check falls into exactly one of four bands:

| Band | Behaviour | Examples |
|------|-----------|----------|
| **Safe** | runs unattended on every pass | `git status`, `git diff --check`, `python -m py_compile`, `bash -n scripts/*.sh`, skill frontmatter parse, job folder contract, model-registry parse, worker status heartbeat |
| **Expensive** | runs only when `allow_expensive=True` | `pytest`, `npm test`, `pnpm test`, `./gradlew test`, `./gradlew assembleDebug`, `apktool d`, `aapt dump badging`, `jadx` |
| **Destructive** | never invoked by the runner | anything that mutates user data on disk, pushes to a remote, rewrites history |
| **Critical** | a `fail` blocks publish | secrets in staged diff, blocked-path stage, `py_compile`, shell syntax, skill frontmatter, duplicate skill name, job folder contract, model registry parse |

"Critical" is orthogonal to the cost band — a check can be
critical and safe (like `secrets.staged_diff`), or critical and
expensive (`python.pytest` once `allow_expensive=True`).

## Lifecycle

```
caller
   │
   ▼
ValidationRunner(workspace, allow_expensive)
   │
   ├── discover checks (workspace shape — git? python? skills/? jobs/? apk?)
   ├── filter via `only=` / `skip=` if requested
   │
   ▼
for each check:
   │
   ├── if expensive and not allow_expensive → STATUS_BLOCKED, skip
   ├── else run check_fn() in a subprocess with timeout
   │       (returns CheckResult)
   │
   ▼
aggregate → ValidationReport(publish_allowed, blocking_failures, …)
   │
   ▼
write validation/results.json, validation/summary.md, validation/commands.log
```

`ValidationRunner` is intentionally standalone — it has no Hermes-CLI
dependencies beyond the standard library, plus an optional
`pyyaml` for full YAML parse paths (a minimal fallback parser
ships in the module so it still works in slimmed-down test envs).

## Inferred checks

The runner does not run *every* check on every workspace — that
would be noise. It infers what's relevant from the directory shape:

| Trigger | Checks added |
|---------|--------------|
| `.git/` exists | `git.status`, `git.whitespace`, `git.diff_stat`, `secrets.staged_diff`, `secrets.unstaged_diff`, `secrets.blocked_paths` |
| `pyproject.toml` or any `*.py` | `python.py_compile` |
| `tests/` or `test/` directory | `python.pytest` (expensive) |
| `[tool.ruff*]` in `pyproject.toml` | `python.ruff` |
| `package.json` | `node.tests` (expensive); `node.lint` only if `package.json` declares a `lint` script |
| `gradlew` or `build.gradle` | `gradle.test`, `gradle.assemble_debug` (expensive) |
| `scripts/*.sh` | `shell.syntax` |
| `skills/` | `hermes.skill_frontmatter`, `hermes.duplicate_skills` |
| `jobs/` | `hermes.job_folder` |
| `model_registry.json` or `models.yaml` | `hermes.model_registry` |
| `workers/` | `hermes.worker_status` |
| any `*.apk` | `apk.apktool`, `apk.aapt_badging`, `apk.jadx_smoke` (expensive) |

If the relevant binary isn't on `PATH` (e.g. `apktool` not
installed), the individual check resolves to `STATUS_SKIPPED`, not
`STATUS_ERROR`.

## Statuses

Every `CheckResult.status` is one of:

| Status | Meaning |
|--------|---------|
| `pass` | the check ran and was satisfied |
| `fail` | the check ran and the result violates the rule (blocks publish if `critical`) |
| `warn` | the check ran and surfaced something noteworthy but not blocking |
| `skipped` | the check is not relevant to this workspace, or its tool is missing |
| `blocked` | the check is expensive and `allow_expensive=False` — *not* run |
| `error` | the runner itself crashed inside the check (treat as a bug to fix) |

## Output artefacts

After every `run()` the runner writes:

### `validation/results.json`

```json
{
  "workspace": "/abs/path/to/repo",
  "publish_allowed": true,
  "blocking_failures": [],
  "started_at": 1747948800.123,
  "finished_at": 1747948802.456,
  "duration_ms": 2333,
  "checks": [
    {
      "name": "git.status",
      "category": "git",
      "status": "pass",
      "summary": "3 changed path(s)",
      "critical": false,
      "command": "git status --short",
      "returncode": 0,
      "duration_ms": 12,
      "metadata": {"changed_paths": 3, "paths": ["src/x.py", ...]}
    },
    …
  ]
}
```

Consumers (the agent, an external dashboard, a CI step) parse this
file. Schema invariants:

- `publish_allowed` is the single boolean to read.
- `blocking_failures` is the sorted list of `name`s that closed
  the gate — empty when `publish_allowed: true`.
- Every check entry has `name`, `category`, `status`, `summary`,
  `critical`. The rest is best-effort metadata.

### `validation/summary.md`

A Markdown rendering of the same information, intended for humans
and for `cat`-ing into a PR comment. Header captures the workspace,
the gate state (`OPEN` / `BLOCKED`), a status-counts breakdown, and
the duration; the body lists every check with status and one-line
summary.

### `validation/commands.log`

The exact shell commands the runner executed, one per line, in the
order they ran. Useful when:

- A check failed and you want to reproduce by hand.
- You're auditing what the runner is actually doing in your repo.
- You're debugging a `STATUS_ERROR` and need to see the call that
  raised.

## Failure semantics for the agent

When the gate closes, the agent's response is constrained:

1. Read the `blocking_failures` list from `results.json`.
2. Surface each failure's `summary` and `category` to the user.
3. Propose the *smallest* corrective action that maps to each
   failure (e.g. "unstage `.env` and add it to `.gitignore`").
4. **Do not** edit files, force-push, amend commits, or rotate
   credentials autonomously.
5. After the user resolves a failure, re-run the gate — never
   trust a "should be fixed now" assumption.

## Where this fits in the orchestrator

Phase 13 (the local orchestrator) defines task hand-offs and the
job folder contract. Phase 14 is the safety net under those
hand-offs: every job's worker writes a `validation/` directory into
its job folder, the orchestrator reads `validation/results.json`
before marking the job `ready_for_review`, and the user-facing
dashboard surfaces blocking failures alongside the artefacts.

For the existing job folder contract (`jobs/<id>/job.json` with
`id` + `status` keys, optional `logs/` directory), see
[`docs/hermes-local-orchestrator.md`](../hermes-local-orchestrator.md).

## Extending the runner

To add a new check:

1. Pick the right `CATEGORY_*` constant in
   `hermes_cli/validation.py`.
2. Add a discovery clause inside `_discover_checks()` — gate it
   on a cheap workspace-shape probe so the check only appears
   when it's relevant.
3. Implement the runner as a method returning a `CheckResult`
   (or fall through to `STATUS_SKIPPED` when the relevant
   external tool is missing — never error out on missing tools).
4. Tag it `critical=True` only if a failure should genuinely
   block publish for every user.
5. Tag it `expensive=True` if it takes more than ~5s on a small
   workspace.
6. Add a unit test under `tests/test_validation_gates.py`
   covering both the pass and fail outcomes.

The runner has zero global state — each `ValidationRunner(...)`
is independent. That's deliberate: it keeps the module callable
from a worker subprocess without coordination overhead.
