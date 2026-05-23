---
name: aos-full-agent-team
description: "Spawns the standard Agent-Operating-System team (planner / builder / reviewer / architect) and assigns work via the kanban dispatcher. Driven by the hermes-orchestration-pipeline and gated by decision-quality-gate."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows, android]
metadata:
  hermes:
    status: stub
    tags: [orchestration, agent-team, kanban, planner, builder, reviewer, architect]
    related_skills:
      - hermes-orchestration-pipeline
      - decision-quality-gate
      - model-router
      - research-validator
      - self-improvement-loop
      - github-publisher
    homepage: https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent
---

# AOS Full Agent Team (stub)

This skill is the **roster** end of the Hermes orchestration pipeline.
When invoked it materialises the standard Agent-Operating-System team
roles for a given goal and hands them off to the kanban dispatcher.

> **Status: Phase 1 placeholder.** The Phase 1 "agent-skills" branch
> that was supposed to author this skill was not produced before the
> coordinator merge. This stub exists so that the references already
> committed in `AGENTS.md`, `README.md`, and the Phase 8 integration
> docs resolve to a real file. Treat the contract below as the
> *intended* behaviour, to be implemented by the next Phase 1 pass.

## Intended invocation

```text
/aos-full-agent-team <goal>
```

The dispatcher reads the job folder (`prompt.md`, `inputs/`, `outputs/`,
`ledger.jsonl`, `status.json`) and materialises four roles:

| Role | Responsibility |
|---|---|
| Planner | Produce the decomposition and acceptance criteria for the goal. |
| Architect | Pick a target shape, constraints, and trade-offs. Records in the ledger. |
| Builder | Implement against the plan; one builder per parallelisable lane. |
| Reviewer | Validate against the plan, ledger, and `decision-quality-gate`. |

Each role is resolved to a concrete model by `model-router` using
`docs/ai-intelligence/model-registry.yaml`.

## Companion docs

- `AGENTS.md` — Orchestration pipeline skills (the canonical contract).
- `docs/orchestration/hermes-orchestration-pipeline.md` — pipeline driver.
- `docs/orchestration/decision-ledger.md` — ledger lifecycle.
- `docs/ai-intelligence/model-routing-policy.md` — model assignment rules.
