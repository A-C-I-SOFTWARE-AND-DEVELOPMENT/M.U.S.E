---
name: local-quality-gate
description: "Run local validation gates against a workspace before publishing — git/secrets/lang/Hermes checks with a publish-block on critical failures."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [validation, quality, gates, ci, hermes, orchestration]
    related_skills: [hermes-agent, requesting-code-review]
---

# Local Quality Gate

Hermes is responsible for the quality of the work it produces. Before
any "publish" action (committing, opening a PR, exporting a job
folder, handing artefacts off to another agent), Hermes runs a
validation pass against its current workspace and reads the result.

This skill is the entry point. It is intentionally thin: it just
wraps `hermes_cli.validation.ValidationRunner` with the right
defaults, then tells the agent whether the publish gate is open.

## When to use

- Right before staging a commit (`git add` / `git commit`).
- Right before opening or pushing to a remote branch / PR.
- After completing a job (so the worker writes a clean
  `validation/results.json` next to its artefacts).
- When the user explicitly asks to "validate", "check", "audit", or
  "verify" the current change set.

## Invariants

Three categories of checks, with a strict policy on what is allowed
to run unattended:

| Category | Examples | Policy |
|----------|----------|--------|
| Safe | `git status`, `git diff --check`, `git diff --stat`, `python -m py_compile`, `bash -n scripts/*.sh`, skill frontmatter parse | auto-run every pass |
| Expensive | `pytest`, `npm test`, `./gradlew test`, `./gradlew assembleDebug`, `apktool d`, `jadx` | run only when `allow_expensive=True` or the user has explicitly opted in |
| Destructive | anything that mutates user data on disk, pushes to a remote, rewrites history | **never invoked by this skill** — only the user does these by hand |

If a check tagged `critical` produces a `fail`, the publish gate
stays closed regardless of what else passed.

## Quick usage

```python
from hermes_cli.validation import ValidationRunner

runner = ValidationRunner(workspace=".", allow_expensive=False)
report = runner.run()

if report.publish_allowed:
    print("ok to publish")
else:
    print("blocked:", report.blocking_failures)
```

After `run()` the runner has written three artefacts under
`<workspace>/validation/`:

- `results.json` — every check's status, summary, command,
  return code, duration, and a truncated stdout/stderr sample
- `summary.md` — human-readable Markdown summary table
- `commands.log` — exactly the shell commands that were executed,
  one per line, in execution order

When invoking from chat, the agent reads `summary.md` and surfaces
`blocking_failures` to the user.

## CLI shape (recommended wrapper)

```bash
# safe pass — runs whatever the workspace shape supports, never an
# expensive check.
python -m hermes_cli.validation --workspace . --no-expensive

# full pass — pytest, gradle, apk audit, all on.
python -m hermes_cli.validation --workspace . --allow-expensive

# only one category
python -m hermes_cli.validation --workspace . --only secrets
```

(The CLI flags above are the canonical names — when wiring a wrapper
into `hermes_cli/main.py`, match them exactly so the SKILL.md
documentation does not drift.)

## Checks performed

### Git
- `git.status` — count of changed paths
- `git.whitespace` — `git diff --check`, warn on findings
- `git.diff_stat` — summary line from `git diff --stat`

### Secrets
- `secrets.staged_diff` — scan `git diff --cached` for token / key
  / private-key patterns. **Critical** — a hit blocks publish.
- `secrets.unstaged_diff` — same scan on the unstaged diff. Warn.
- `secrets.blocked_paths` — refuses to publish if `.env`,
  `.env.*`, `id_rsa`, `id_ed25519`, or `id_ecdsa` are staged.
  **Critical.**

### Languages / frameworks
- `python.py_compile` — `python -m py_compile` over every `*.py`.
  **Critical.**
- `python.pytest` — runs the suite when `tests/` exists. Expensive.
- `python.ruff` — runs `ruff check .` when ruff config is present.
- `node.tests` — `pnpm test` / `npm test` / `yarn test`. Expensive.
- `node.lint` — only if `package.json` has a `lint` script.
- `gradle.test` / `gradle.assemble_debug` — Android. Expensive.
- `shell.syntax` — `bash -n` over every `scripts/*.sh`. **Critical.**

### Hermes-specific
- `hermes.skill_frontmatter` — every `skills/**/SKILL.md` must
  declare `name` and `description`. **Critical.**
- `hermes.duplicate_skills` — two skills with the same `name`
  break the dispatcher. **Critical.**
- `hermes.job_folder` — every directory under `jobs/` must have a
  `job.json` with `id` and `status` keys. **Critical.**
- `hermes.model_registry` — `model_registry.json` or `models.yaml`
  must parse. **Critical.**
- `hermes.worker_status` — `workers/**/status.json` heartbeats
  newer than 24h, otherwise warn (not critical).

### APK audit (optional)
Only discovered if the workspace contains an `*.apk`:
- `apk.apktool` — `apktool d` decode smoke test
- `apk.aapt_badging` — `aapt dump badging`
- `apk.jadx_smoke` — `jadx` decompile pass

Each individually downgrades to `skipped` if the backing tool is
missing on `PATH`.

### Remote runtime (optional)
Only discovered if the workspace has a `remote/` directory the
worker / tunnel stack writes to. None of these are critical — they
report the state of the remote stack, they do not gate publish.
- `remote.tunnel` — reads `remote/tunnel.json`. Pass on `up` /
  `healthy` / `ready` / `open` / `connected`; warn on `down` /
  unknown; fail on parse error.
- `remote.workers` — walks `remote/workers/**/heartbeat.json`;
  warns when any heartbeat is older than 5 minutes.
- `remote.queue` — reads `remote/queue.json`; reports queue
  depth and warns when the oldest job has been waiting more than
  30 minutes.

For the broader pipeline (validation + testing + monitoring) see
[`docs/orchestration/validation-testing-monitoring.md`](../../docs/orchestration/validation-testing-monitoring.md).
The runtime observer that consumes these signals lives in
[`hermes_cli/monitoring.py`](../../hermes_cli/monitoring.py) and
writes `monitoring/health.json` + `monitoring/events.jsonl`
alongside the validation artefacts.

## Failure response

When the gate closes, the skill's job is to **report the
specific failing checks**, not to attempt repairs autonomously. The
user (or a downstream skill explicitly authorized for a given
category) decides what to do next.

Typical responses:
- `secrets.*` failure → ask the user to unstage the file and rotate
  the key; never auto-remove staged content.
- `python.py_compile` failure → surface the file/line from
  `stderr`; ask the user before editing.
- `hermes.skill_frontmatter` failure → propose the missing fields,
  edit only with explicit user approval.
- `git.whitespace` warning → mention it, do not auto-strip
  whitespace.

## What this skill does NOT do

- It does not push, force-push, or rewrite history.
- It does not modify files it discovers issues with.
- It does not call out to a remote linter or formatter service.
- It does not bypass `allow_expensive=False` to "just check" a
  long-running suite.

If any of those are needed, they live in a different skill and the
user invokes them explicitly.
