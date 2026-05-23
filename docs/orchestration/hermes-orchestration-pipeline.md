# Hermes Orchestration Pipeline

> **Status: Phase 1 placeholder.** The Phase 1 "agent-skills" branch
> that was supposed to author the canonical `hermes-orchestration-pipeline`
> skill and its narrative companion was not produced before the coordinator
> merge. This file captures the contract already referenced in
> `AGENTS.md`, `README.md`, and the Phase 8 integration docs so external
> links resolve. Treat it as the **intended** behaviour, to be filled out
> in detail by the next Phase 1 pass.

The Hermes orchestration pipeline is the local-first driver that ties
together the agent team, the decision ledger, the model router, the
AI improvement radar, the competitive harvester, the self-improvement
loop, and the GitHub publisher. The Hermes backend is the **engine**;
the Android APK at [`apps/android`](../../apps/android/) is the
**cockpit**.

## Job folder contract

Every job runs out of a directory with a fixed layout:

```text
<job-id>/
├── prompt.md         # the original goal
├── inputs/           # any attached context (files, transcripts, etc.)
├── outputs/          # whatever the workers produced
├── ledger.jsonl      # append-only decision ledger for this job
└── status.json       # queued / running / waiting-approval / shipped / failed
```

Skills read inputs and **append** to `ledger.jsonl`; they never
overwrite history.

## Pipeline stages

1. **Intake** — `hermes-orchestration-pipeline` reads `prompt.md` and
   normalises it into a goal + acceptance criteria.
2. **Team materialisation** — `aos-full-agent-team` spawns planner /
   builder / reviewer / architect lanes.
3. **Model assignment** — `model-router` resolves each lane to a
   concrete model using
   [`docs/ai-intelligence/model-registry.yaml`](../ai-intelligence/model-registry.yaml)
   and
   [`docs/ai-intelligence/model-routing-policy.md`](../ai-intelligence/model-routing-policy.md).
4. **Research gates** — `research-validator` cross-checks external
   claims before they enter the ledger.
5. **Decision gates** — every non-trivial decision passes through
   `decision-quality-gate` and is appended to `ledger.jsonl`.
6. **Improvement signals** — `ai-improvement-radar` and the
   competitive harvester feed `self-improvement-loop`, which can
   propose patches to Hermes itself.
7. **Ship** — `github-publisher` turns approved change sets into
   branches, PRs, and releases.

## Invocation

```text
/reload-skills
/aos-full-agent-team <goal>
/hermes-orchestration-pipeline <job-id>
/model-router <task-type>
/decision-quality-gate <decision-id>
/ai-improvement-radar
/github-publisher <branch>
```

These slash commands work in the CLI, on any messaging gateway, and
from the Android cockpit's "Pipeline run" handoff.

## Posture

**Private and local-first.** No telemetry, no remote config, no
third-party data sharing in the pipeline itself. The cockpit talks
only to the backend the user controls; the backend talks only to
the official AI tools the user is already logged into. The decision
ledger stays on the backend's filesystem.

## Companion docs

- [`docs/orchestration/decision-ledger.md`](decision-ledger.md) — ledger schema and lifecycle.
- [`docs/orchestration/self-improvement-loop.md`](self-improvement-loop.md) — how Hermes proposes patches to itself.
- [`docs/orchestration/job-controller-roadmap.md`](job-controller-roadmap.md) — Phase 7 job controller design.
- [`docs/orchestration/orchestrator-command-roadmap.md`](orchestrator-command-roadmap.md) — slash-command surface.
- [`docs/orchestration/worker-adapter-interface.md`](worker-adapter-interface.md) — uniform worker contract.
- [`docs/orchestration/final-hermes-orchestration-integration-report.md`](final-hermes-orchestration-integration-report.md) — Phase 10 integration report.
- [`docs/hermes-local-orchestrator.md`](../hermes-local-orchestrator.md) — Android cockpit contract.
