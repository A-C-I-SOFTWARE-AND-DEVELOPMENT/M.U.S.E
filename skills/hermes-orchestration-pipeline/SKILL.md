---
name: hermes-orchestration-pipeline
description: "Phase-02 foundation contract for the Hermes multi-worker orchestration pipeline. Use when scaffolding a job folder, deciding what artifacts a worker is allowed to read or write, or when planning the controller that will run on top of this contract."
version: 0.2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [orchestration, pipeline, foundation, council, scaffold]
    related_skills:
      - model-router
      - github-publisher
      - developer-ux-command-center
---

# Hermes orchestration pipeline

This skill is the orchestrator-side companion to
`scripts/hermes-orchestrate.sh` and
`docs/orchestration/hermes-orchestration-pipeline.md`. It tells you the
folder contract every worker reads from and writes to, and the rules
you must follow when reasoning about a job in this phase.

## What this phase is

Phase 02 is a **scaffold pass**. The script creates the full job folder
contract under `.hermes-orchestrator/jobs/<job-id>/` with empty or
templated artifacts. It does **not** invoke any external model tool
yet. The controller that will fill the artifacts is a later phase
built on top of this contract.

If your reasoning depends on a worker having actually run, you are
ahead of the implementation. Stop and ask which phase the project is
on.

## How a job is created

The script accepts these flags (any other flag is an error):

- `--help` / `-h`
- `--list`
- `--status <job-id>`
- `--job-id <id>` (optional; auto-generated if omitted)
- `--root <path>` (default `.hermes-orchestrator`)
- `--mode plan|audit|build|debug|review|publish` (default `audit`)
- `--trusted-local` (sets `trusted_local: true` in `job.json`)

The first non-flag argument is the mission text. Multi-word missions
must be quoted.

Both invocation styles are supported and produce identical output:

```bash
bash scripts/hermes-orchestrate.sh "..."
chmod +x scripts/hermes-orchestrate.sh && ./scripts/hermes-orchestrate.sh "..."
```

Python detection is `python3` first, then `python`. The detected
binary is used for JSON escaping. If neither exists, the script exits.

## Folder contract (read this before touching a job)

Every job has exactly this shape. Workers may write only inside their
own `workers/<worker>/` subfolder; the orchestrator owns everything
else.

```
.hermes-orchestrator/jobs/<job-id>/
├── job.json
├── mission.md
├── status.json
├── decision-ledger.md
├── shared-context/
│   ├── repo-map.md
│   ├── evidence.md
│   ├── constraints.md
│   └── user-preferences.md
├── workers/
│   └── <worker>/
│       ├── prompt.md          # written by orchestrator, read by worker
│       ├── output.md          # written by worker
│       ├── patch.diff         # written by worker
│       └── status.json        # written by worker; orchestrator may overwrite on reclaim
├── merge/
│   ├── council-review.md
│   ├── scorecard.json
│   ├── conflict-report.md
│   ├── final-plan.md
│   └── final-patch.diff
├── github/
│   ├── branch.txt
│   ├── commit-message.txt
│   ├── pr-title.txt
│   └── pr-body.md
└── logs/
    └── orchestrator.log
```

Workers registered in this phase: `hermes-local`, `claude-code`,
`codex-cli`. The list lives in the script's `WORKERS` array; keep this
skill in sync if you change it.

## Rules

1. **Treat the folder contract as a wire protocol.** Any file an
   external worker (Claude Code, Codex) writes must land at the path
   above, with the name above, regardless of what the worker's
   internal preference would be. The next phase's controller relies on
   exact paths.
2. **Workers do not see each other's folders.** Cross-worker context
   is exchanged through `shared-context/` (orchestrator-controlled) or
   surfaced in `merge/council-review.md` during synthesis. Never have
   one worker read another worker's `output.md` directly.
3. **`decision-ledger.md` is append-only.** Phase 02 seeds the first
   row. Future entries should add rows; do not rewrite existing rows.
4. **`logs/orchestrator.log` is append-only and orchestrator-owned.**
   Workers must not write to it. Phase 02 writes the scaffold trace
   line.
5. **`trusted_local` is a single boolean in `job.json`.** Workers that
   intend to mutate local state outside the job folder must check it
   first. The `--trusted-local` flag is the only way to set it.
6. **Modes are recorded, not enforced.** Phase 02 records `mode` in
   `job.json` and `status.json` but does not branch on it. Later
   phases pick the mode up from `job.json` and route work
   accordingly.
7. **Do not promote a Phase-02 job to a PR.** `github/pr-body.md`
   explicitly says so; respect that until the merge artifacts are
   real.

## When in doubt

- Reach for `docs/orchestration/hermes-orchestration-pipeline.md`
  first — it is the human-readable spec.
- The script itself is the executable spec. If they disagree, prefer
  the script's behavior and file a bug against the docs.
- The related skills cover narrower slices:
  - `model-router` — choosing which worker(s) to dispatch.
  - `github-publisher` — turning `github/*` into a real branch + PR.
  - `developer-ux-command-center` — the surface the developer sees.
