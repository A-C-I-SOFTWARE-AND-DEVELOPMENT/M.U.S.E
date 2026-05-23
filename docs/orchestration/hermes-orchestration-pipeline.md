# Hermes orchestration pipeline

A small, file-on-disk pipeline that turns a one-line user mission into a
council-reviewed plan, patch, and PR draft. Workers cooperate by reading
and writing a fixed folder contract under `.hermes-orchestrator/jobs/`.

This document is the source of truth for the **Phase 02 foundation**:
the script that creates the folder contract, the flags it accepts, and
the files every later phase will rely on.

## Status of this phase

Phase 02 is a scaffold pass. `scripts/hermes-orchestrate.sh` creates
every artifact described below but does not yet invoke any external
model tool. The controller that fills the artifacts in (calls Hermes
locally, dispatches to Claude Code / Codex, runs the council merge,
opens the PR) is built on top of this contract in a later phase.

If you are reading this and the script does more than create files,
the docs are out of date — please file an issue.

## Invocation

The script lives at `scripts/hermes-orchestrate.sh` and can be invoked
two ways:

```bash
# Run via bash, no chmod required:
bash scripts/hermes-orchestrate.sh "Refactor the gateway config loader"

# Or make it executable once and run it directly afterwards:
chmod +x scripts/hermes-orchestrate.sh
./scripts/hermes-orchestrate.sh "Refactor the gateway config loader"
```

Both forms are supported and produce the same artifacts.

### Flags

| Flag                | Description                                                                 |
|---------------------|-----------------------------------------------------------------------------|
| `--help`, `-h`      | Print usage and exit.                                                       |
| `--list`            | List existing jobs under `<root>/jobs/` and exit.                           |
| `--status <job-id>` | Print `status.json` for the named job and exit.                             |
| `--job-id <id>`     | Use this job id instead of an auto-generated one.                           |
| `--root <path>`     | Override orchestrator root. Default: `.hermes-orchestrator`.                |
| `--mode <m>`        | One of `plan`, `audit`, `build`, `debug`, `review`, `publish`. Default: `audit`. |
| `--trusted-local`   | Sets `trusted_local: true` in `job.json`. Later phases use this to skip extra confirmation prompts before touching local state. |

Any non-flag argument is taken as the mission text. Quote multi-word
missions.

### Modes

The mode does not yet branch behavior in this phase — it is recorded in
`job.json`, `status.json`, and the auto-generated branch name so later
phases can route work without re-parsing the mission.

| Mode      | Intended use                                                          |
|-----------|-----------------------------------------------------------------------|
| `plan`    | Decompose a goal; no patch expected.                                  |
| `audit`   | Inspect code or config; produce findings, no mutation expected.       |
| `build`   | Implement a feature; produce a patch.                                 |
| `debug`   | Reproduce, diagnose, fix a bug; produce a patch.                      |
| `review`  | Critique existing code or a PR; produce a review document.            |
| `publish` | Promote a previously scaffolded job to a branch + PR draft.           |

### Python detection

The script needs Python only for safe JSON escaping. It detects
`python3` first, falls back to `python`, and uses the detected binary
for every JSON encoding. If neither is on `PATH`, the script exits with
a clear error.

## Folder contract

For every job, the script creates:

```
.hermes-orchestrator/jobs/<job-id>/
├── job.json                          # mode, mission, trusted_local, workers, created_at
├── mission.md                        # human-readable mission and metadata
├── status.json                       # state + timestamps; mutated as the job progresses
├── decision-ledger.md                # append-only log of orchestration decisions
├── shared-context/
│   ├── repo-map.md                   # scoped layout of the target repo
│   ├── evidence.md                   # files read, commands run, observations
│   ├── constraints.md                # hard limits (security, scope, no-touch paths)
│   └── user-preferences.md           # style and tooling preferences for this user
├── workers/
│   ├── hermes-local/
│   │   ├── prompt.md
│   │   ├── output.md
│   │   ├── patch.diff
│   │   └── status.json
│   ├── claude-code/
│   │   └── ...same four files
│   └── codex-cli/
│       └── ...same four files
├── merge/
│   ├── council-review.md             # synthesis of worker outputs
│   ├── scorecard.json                # per-worker scores
│   ├── conflict-report.md            # per-file conflicts between worker patches
│   ├── final-plan.md                 # plan that survives council review
│   └── final-patch.diff              # merged patch to apply
├── github/
│   ├── branch.txt                    # hermes/<mode>/<job-id> by default
│   ├── commit-message.txt
│   ├── pr-title.txt
│   └── pr-body.md
└── logs/
    └── orchestrator.log              # one append-only file per job
```

Every file is created in Phase 02. Files that future phases populate
contain a brief stub explaining what will live there.

## Workers registered in this phase

Three worker slots are scaffolded for every job:

- `hermes-local` — the Hermes brain running on the user's machine.
- `claude-code` — Claude Code CLI, when the user has it available.
- `codex-cli` — Codex / ChatGPT CLI, when the user has it available.

The list lives in `scripts/hermes-orchestrate.sh` (the `WORKERS` array)
and in `skills/model-router/SKILL.md`. Keep the two in sync if you add
or remove a worker.

## What the script does **not** do (yet)

- It does not run any external model tool. No subprocess fires Claude,
  Codex, or even `hermes` itself.
- It does not look at the repo. `shared-context/repo-map.md` is a stub.
- It does not generate prompts beyond a minimal templated header.
- It does not open a PR. `github/*` is text on disk; nothing is pushed.

All of the above is intentional. The whole point of Phase 02 is to lock
the folder contract so the controller in the next phase can be written
against a stable surface.

## Validation

The following sequence should succeed end-to-end on a clean checkout:

```bash
bash -n scripts/hermes-orchestrate.sh
bash scripts/hermes-orchestrate.sh --help
bash scripts/hermes-orchestrate.sh --job-id test-foundation --mode audit "Test orchestration folder"
test -f .hermes-orchestrator/jobs/test-foundation/job.json
test -f .hermes-orchestrator/jobs/test-foundation/decision-ledger.md
test -f .hermes-orchestrator/jobs/test-foundation/workers/hermes-local/status.json
test -f .hermes-orchestrator/jobs/test-foundation/merge/scorecard.json
test -f .hermes-orchestrator/jobs/test-foundation/github/pr-body.md
rm -rf .hermes-orchestrator/jobs/test-foundation
```

If any step fails, the script and these docs disagree about reality —
fix the script, not the docs, unless the user explicitly approved a
contract change.
