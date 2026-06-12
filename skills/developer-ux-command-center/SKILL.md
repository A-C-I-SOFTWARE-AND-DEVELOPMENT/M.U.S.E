---
name: developer-ux-command-center
description: "Developer-facing surface for the Hermes orchestration pipeline. Use to drive scripts/hermes-orchestrate.sh from a terminal: scaffold a job, list jobs, inspect status, and explain artifacts in plain prose."
version: 0.3.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [orchestration, developer-ux, cli, command-center]
    related_skills:
      - hermes-orchestration-pipeline
      - model-router
      - github-publisher
---

# Developer UX command center

The command surface a developer interacts with when driving the Hermes
orchestration pipeline from a terminal. Wraps `scripts/hermes-orchestrate.sh`
and the job folder contract; explains what the artifacts mean.

## Phase-03 reality check

In Phase 03 the script only scaffolds artifacts — it does not run any
external model tool. Every command below is real and works today; the
artifacts they produce are intentionally empty templates for the
controller in the next phase to fill in.

If a user asks "what did the worker say?" before the controller phase
ships, the honest answer is "nothing yet — Phase 03 only scaffolds the
folder." Do not invent worker output.

## The four developer commands

### 1. Scaffold a new job

```bash
bash scripts/hermes-orchestrate.sh --mode <m> "<mission text>"
```

- `<m>` is one of `plan`, `research`, `audit`, `build`, `validate`,
  `publish` (defaults to `audit`).
- Multi-word missions must be quoted.
- Add `--trusted-local` if the user has explicitly said this job may
  mutate local state without further prompts.
- Add `--job-id <id>` to pin the job id (useful for reproducible
  testing and for shared scripts).
- Add `--root <path>` to override the default `.hermes-orchestrator`
  root — e.g. for a sandboxed run during a demo.

The script prints the job id, the folder it created, the mode, and the
worker roster.

### 2. List existing jobs

```bash
bash scripts/hermes-orchestrate.sh --list
```

Prints one job id per line. Honors `--root`.

### 3. Inspect a job's status

```bash
bash scripts/hermes-orchestrate.sh --status <job-id>
```

Prints `status.json` for the job. In Phase 03 this is always
`"state": "scaffolded"` with `"current_stage": "research"` — that will
gain more states as the controller ships.

### 4. Read the help

```bash
bash scripts/hermes-orchestrate.sh --help
```

The script's own usage block is the canonical reference. If this skill
ever disagrees with `--help`, trust `--help` and file a doc bug.

### Invocation variants

Both `bash scripts/hermes-orchestrate.sh ...` and
`./scripts/hermes-orchestrate.sh ...` are supported. The second form
needs a one-time `chmod +x scripts/hermes-orchestrate.sh`. Suggest the
explicit `bash` form first — it works on a fresh checkout without any
permission changes.

## Reading a job folder for the user

When a developer says "what's in the job folder?" walk them through
the contract in this order — it mirrors the way the controller will
populate it:

1. `job.json` — the immutable header (mode, mission, workers,
   `trusted_local`).
2. `mission.md` — human-readable mission.
3. `decision-ledger.md` — what the orchestrator has decided so far
   (Phase 03 has one row: the scaffold).
4. `queue.json` — pending / in-flight / completed / failed task list
   (empty in Phase 03).
5. `checkpoints/` — append-only resume points (empty placeholder in
   Phase 03).
6. `shared-context/*` — the context every worker shares, including
   `tool-detection.json` for what's actually reachable on this host.
7. `phases/*.md` — one stage notebook per pipeline stage (`research`,
   `planning`, `approval`, `implementation`, `validation`, `publish`).
8. `workers/<worker>/` — per-worker prompt, output, patch, status.
   In Phase 03 every `status.json` says `not_started`.
9. `merge/*` — council synthesis (empty templates in Phase 03).
10. `validation/` — local validation gate outputs (empty placeholder).
11. `github/*` — branch + PR draft (templates in Phase 03; do not push).
12. `deploy/` — post-publish release notes / rollout plan (empty
    placeholder).
13. `logs/orchestrator.log` — append-only log; Phase 03 logs the
    scaffold trace.

Always link the developer to
`docs/orchestration/muse-orchestration-pipeline.md` for the full
contract — this skill is the conversational entry point, not the spec.

## Anti-patterns

- **Inventing flags.** The script accepts exactly the flags listed in
  the table above. `--dry-run`, `--watch`, `--worker` do not exist
  yet. If a developer asks for one, that is a feature request, not a
  forgotten flag.
- **Editing scaffolded artifacts by hand.** The controller assumes
  the artifacts are produced by orchestrator code. Hand-editing
  `status.json` or `decision-ledger.md` will desync the system. If
  the developer needs to mutate state, ask why and surface the
  underlying request.
- **Pushing a scaffold PR.** `github/pr-body.md` includes a
  do-not-merge banner. Honor it. See the `github-publisher` skill for
  the (future) publish flow.
- **Claiming a worker ran.** In Phase 03 no worker runs. If
  `workers/<w>/output.md` has content, someone wrote it out-of-band
  — trust `status.json`, not the prose.

## When to suggest the script vs. an MCP tool

The orchestration script is a local-disk pipeline. It does not call
GitHub, the API, or any MCP server directly. If the developer wants
something that lives outside the job folder — open an issue, post a
comment, look up a PR — reach for the GitHub MCP tools (`mcp__github__*`)
or the native plugin instead. Use the script only to create, list,
and inspect orchestration jobs.
