---
name: hermes-orchestration-pipeline
description: "Phase-02 foundation contract for the Hermes multi-worker orchestration pipeline. Use when scaffolding a job folder, deciding what artifacts a worker is allowed to read or write, or when planning the controller that will run on top of this contract."
version: 0.2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [orchestration, pipeline, foundation, council, scaffold, private-local]
    related_skills:
      - aos-full-agent-team
      - model-router
      - github-publisher
      - developer-ux-command-center
      - decision-quality-gate
      - research-validator
      - ai-improvement-radar
      - self-improvement-loop
      - best-coding-tool-mission
    related_docs:
      - docs/orchestration/hermes-orchestration-pipeline.md
      - docs/orchestration/decision-ledger.md
      - docs/orchestration/self-improvement-loop.md
      - docs/ai-intelligence/model-registry.yaml
      - docs/ai-intelligence/model-routing-policy.md
      - docs/competitive/openhuman-paperclip-research.md
      - docs/mission/best-coding-tool-mission.md
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

## Posture: private and local-first

The pipeline is **private and local-first by default**:

- Every job folder lives on disk at
  `.hermes-orchestrator/jobs/<job-id>/` (or `~/.hermes/jobs/<job-id>/`
  in the later runtime). Nothing in the contract requires a cloud
  service.
- No telemetry, no remote config, no third-party data sharing.
- External AI tools (Claude Code, Codex, Aider, Goose, local models)
  are invoked only when the user is already logged in to them; the
  pipeline never relays prompts through a Hermes-owned cloud
  intermediary.
- The Hermes backend is the engine; the Android APK at
  [`apps/android`](../../apps/android/) is the cockpit. Every job is
  inspectable from the cockpit through the same on-disk contract
  described above — there is no separate cockpit-only state.

## Where this fits in the larger system

This skill scaffolds the substrate. The decisions made on top of it
are recorded by the wider orchestration stack:

| Concern | Skill / doc |
|---|---|
| Visible reasoning per decision | [`decision-quality-gate`](../decision-quality-gate/SKILL.md) writes a ledger into `decision-ledger.md` (template: [`docs/orchestration/decision-ledger.md`](../../docs/orchestration/decision-ledger.md)). |
| Evidence checks behind a ledger | [`research-validator`](../research-validator/SKILL.md). |
| Picking which worker / model runs the card | [`model-router`](../model-router/SKILL.md), backed by [`docs/ai-intelligence/model-registry.yaml`](../../docs/ai-intelligence/model-registry.yaml) and [`docs/ai-intelligence/model-routing-policy.md`](../../docs/ai-intelligence/model-routing-policy.md). |
| Tracking new AI coding-tool capabilities | [`ai-improvement-radar`](../ai-improvement-radar/SKILL.md) writes reports under `.hermes-orchestrator/ai-radar/`. |
| Harvesting comparable tools' features | [`docs/competitive/openhuman-paperclip-research.md`](../../docs/competitive/openhuman-paperclip-research.md) feeds the radar. |
| End-of-job learning pass | [`self-improvement-loop`](../self-improvement-loop/SKILL.md), see [`docs/orchestration/self-improvement-loop.md`](../../docs/orchestration/self-improvement-loop.md). |
| Mission anchor (Principle 1..10) | [`best-coding-tool-mission`](../best-coding-tool-mission/SKILL.md), see [`docs/mission/best-coding-tool-mission.md`](../../docs/mission/best-coding-tool-mission.md). |
| Council orchestration over this contract | [`aos-full-agent-team`](../aos-full-agent-team/SKILL.md). |
| Promoting `github/*` into a real branch + PR | [`github-publisher`](../github-publisher/SKILL.md). |
| Terminal surface for developers | [`developer-ux-command-center`](../developer-ux-command-center/SKILL.md). |

## How to invoke

Pick up new or edited skills, then drive the pipeline from any
session (CLI, gateway DM, or Android cockpit):

```text
/reload-skills                              # after editing skills
/aos-full-agent-team <goal>                 # full 16-specialist council
/hermes-orchestration-pipeline <job-id>     # drive a scaffolded job folder
/model-router <task-type>                   # pick a worker / model on purpose
/decision-quality-gate <decision-id>        # gate a proposed decision
/ai-improvement-radar                       # scan + write a radar report
/github-publisher <branch>                  # ship approved changes
```

## When in doubt

- Reach for `docs/orchestration/hermes-orchestration-pipeline.md`
  first — it is the human-readable spec.
- The script itself is the executable spec. If they disagree, prefer
  the script's behavior and file a bug against the docs.
- The related skills cover narrower slices:
  - `aos-full-agent-team` — full council over a single goal.
  - `model-router` — choosing which worker(s) to dispatch.
  - `decision-quality-gate` — recording the *why* in the ledger.
  - `ai-improvement-radar` — keeping the router's intelligence fresh.
  - `self-improvement-loop` — closing the loop after every job.
  - `github-publisher` — turning `github/*` into a real branch + PR.
  - `developer-ux-command-center` — the surface the developer sees.
