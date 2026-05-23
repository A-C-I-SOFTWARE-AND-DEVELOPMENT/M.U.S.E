---
name: developer-ux-command-center
description: "The Android APK cockpit's view onto the Hermes orchestration pipeline. Surfaces job state, decision ledger entries, model-router picks, and approval prompts on the device the developer is actually carrying."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [android, linux, macos, windows]
metadata:
  hermes:
    status: stub
    tags: [android, cockpit, ux, command-center, orchestration, mobile]
    related_skills:
      - hermes-orchestration-pipeline
      - aos-full-agent-team
      - decision-quality-gate
      - model-router
      - github-publisher
    homepage: https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent
---

# Developer UX Command Center (stub)

The cockpit-side counterpart to the orchestration pipeline. The
Hermes backend is the **engine**; the Android APK at
[`apps/android`](../../apps/android/) is the **cockpit**. This skill
defines what the cockpit shows and what it lets the developer trigger.

> **Status: Phase 1 placeholder.** This stub exists so the
> `developer-ux-command-center` references already in `AGENTS.md`,
> `README.md`, and the Phase 8 integration docs resolve to a real
> file. The behaviour below is the *intended* contract, to be
> implemented by the next Phase 1 pass.

## Intended surfaces

| Surface | What it shows / does |
|---|---|
| Job kanban | Status of each active job folder (queued / running / waiting-approval / shipped). |
| Decision ledger viewer | Append-only feed of `ledger.jsonl` entries, filterable per job. |
| Model router pick | Which model the router chose for the active step, with rationale. |
| Approval prompts | Push a confirmation to the phone when `decision-quality-gate` needs a human. |
| Pipeline handoff | "Pipeline run" alongside the existing manual `ChatGPT / Claude / Codex` handoff buttons. |

## Posture

- **Cockpit, not engine.** Nothing in this skill runs the pipeline on
  the device. The cockpit only issues commands to the backend the user
  controls.
- **No third-party telemetry.** The cockpit never sends task content
  to anyone except the backend the user has configured.
- **Local-first.** All ledger reads come from the backend's filesystem
  over the user's gateway; no third-party cloud is in the path.

## Companion docs

- `docs/hermes-local-orchestrator.md` — cockpit contract (manual + pipeline handoff).
- `AGENTS.md` — Orchestration pipeline skills (canonical contract).
- `apps/android/README.md` — Android cockpit build / install notes.
