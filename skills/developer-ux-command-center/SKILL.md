---
name: developer-ux-command-center
description: "Developer-facing surface for the Hermes orchestration pipeline. Use to drive scripts/hermes-orchestrate.sh from a terminal: scaffold a job, list jobs, inspect status, and explain artifacts in plain prose."
version: 0.2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [orchestration, developer-ux, cli, command-center, android, cockpit, private-local]
    related_skills:
      - hermes-orchestration-pipeline
      - aos-full-agent-team
      - model-router
      - github-publisher
      - decision-quality-gate
      - ai-improvement-radar
      - self-improvement-loop
      - best-coding-tool-mission
    related_docs:
      - docs/orchestration/hermes-orchestration-pipeline.md
      - docs/orchestration/decision-ledger.md
      - docs/hermes-local-orchestrator.md
      - apps/android/README.md
---

# Developer UX command center

The command surface a developer interacts with when driving the Hermes
orchestration pipeline from a terminal. Wraps `scripts/hermes-orchestrate.sh`
and the job folder contract; explains what the artifacts mean.

## Phase-02 reality check

In Phase 02 the script only scaffolds artifacts — it does not run any
external model tool. Every command below is real and works today; the
artifacts they produce are intentionally empty templates for the
controller in the next phase to fill in.

If a user asks "what did the worker say?" before the controller phase
ships, the honest answer is "nothing yet — Phase 02 only scaffolds the
folder." Do not invent worker output.

## The four developer commands

### 1. Scaffold a new job

```bash
bash scripts/hermes-orchestrate.sh --mode <m> "<mission text>"
```

- `<m>` is one of `plan`, `audit`, `build`, `debug`, `review`, `publish`
  (defaults to `audit`).
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

Prints `status.json` for the job. In Phase 02 this is always
`"state": "scaffolded"` — that will gain more states as the controller
ships.

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
   (Phase 02 has one row: the scaffold).
4. `shared-context/*` — the context every worker shares.
5. `workers/<worker>/` — per-worker prompt, output, patch, status.
   In Phase 02 every `status.json` says `not_started`.
6. `merge/*` — council synthesis (empty templates in Phase 02).
7. `github/*` — branch + PR draft (templates in Phase 02; do not push).
8. `logs/orchestrator.log` — append-only log; Phase 02 logs the
   scaffold trace.

Always link the developer to
`docs/orchestration/hermes-orchestration-pipeline.md` for the full
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
- **Claiming a worker ran.** In Phase 02 no worker runs. If
  `workers/<w>/output.md` has content, someone wrote it out-of-band
  — trust `status.json`, not the prose.

## When to suggest the script vs. an MCP tool

The orchestration script is a local-disk pipeline. It does not call
GitHub, the API, or any MCP server directly. If the developer wants
something that lives outside the job folder — open an issue, post a
comment, look up a PR — reach for the GitHub MCP tools (`mcp__github__*`)
or the native plugin instead. Use the script only to create, list,
and inspect orchestration jobs.

## Hermes backend is the engine; the APK is the cockpit

The developer terminal surface (this skill) and the
[Android APK](../../apps/android/) (the cockpit) are two faces of the
**same engine** — the Hermes backend running on a VPS, home server,
laptop, or Termux on phone. They share:

- The same job folder contract (`.hermes-orchestrator/jobs/<job-id>/`).
- The same `decision-ledger.md` per job.
- The same `status.json` lifecycle.
- The same routing decisions emitted by
  [`model-router`](../model-router/SKILL.md).
- The same publish gates enforced by
  [`github-publisher`](../github-publisher/SKILL.md).

There is no cockpit-only state. The cockpit reads the folders this
script scaffolds; this script can inspect jobs the cockpit launched.
See [`docs/hermes-local-orchestrator.md`](../../docs/hermes-local-orchestrator.md)
for the cockpit ↔ backend contract.

## Posture: private and local-first

- All jobs live on disk. No telemetry, no remote config, no
  third-party data sharing.
- External AI tools (Claude Code, Codex, Aider, Goose, local models)
  are invoked only when the developer is already logged in to them.
- The Android APK cockpit connects to the backend via a gateway the
  developer controls — there is no Hermes-owned cloud relay.

## Where this fits in the larger system

| Concern | Skill / doc |
|---|---|
| Visible reasoning per decision | [`decision-quality-gate`](../decision-quality-gate/SKILL.md) (template: [`docs/orchestration/decision-ledger.md`](../../docs/orchestration/decision-ledger.md)) |
| Worker / model selection | [`model-router`](../model-router/SKILL.md), backed by [`docs/ai-intelligence/model-registry.yaml`](../../docs/ai-intelligence/model-registry.yaml) |
| New AI tool capability tracking | [`ai-improvement-radar`](../ai-improvement-radar/SKILL.md) |
| Council orchestration | [`aos-full-agent-team`](../aos-full-agent-team/SKILL.md) |
| Closing the loop after a job | [`self-improvement-loop`](../self-improvement-loop/SKILL.md) |
| Mission anchor | [`best-coding-tool-mission`](../best-coding-tool-mission/SKILL.md) |

## How to invoke

```text
/reload-skills                              # after editing skills
/developer-ux-command-center                # load this skill into a session
/hermes-orchestration-pipeline <job-id>     # drive a scaffolded job folder
/aos-full-agent-team <goal>                 # full team for a single goal
/model-router <task-type>                   # pick a worker / model on purpose
/decision-quality-gate <decision-id>        # gate a proposed decision
/ai-improvement-radar                       # scan + write a radar report
/github-publisher <job-id>                  # ship approved changes
```
