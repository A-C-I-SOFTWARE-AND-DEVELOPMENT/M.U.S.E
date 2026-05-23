---
name: best-coding-tool-mission
description: "Anchor every job to Hermes' mission as the best private local-first developer command center: one prompt, routed work, scored output, reversible publishes, learning loop."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mission, routing, quality, scorecard, local-first, jeremiah, private-local, cockpit]
    related_skills:
      - self-improvement-loop
      - hermes-orchestration-pipeline
      - aos-full-agent-team
      - model-router
      - decision-quality-gate
      - research-validator
      - ai-improvement-radar
      - github-publisher
      - developer-ux-command-center
      - enterprise-orchestrator
      - enterprise-monitor
    related_docs:
      - docs/mission/best-coding-tool-mission.md
      - docs/orchestration/hermes-orchestration-pipeline.md
      - docs/orchestration/decision-ledger.md
      - docs/orchestration/self-improvement-loop.md
      - docs/ai-intelligence/model-registry.yaml
      - docs/ai-intelligence/model-routing-policy.md
      - docs/ai-intelligence/ai-improvement-radar.md
      - docs/competitive/openhuman-paperclip-research.md
      - apps/android/README.md
---

# Best Coding Tool Mission

> Hermes strives to be the best private local-first developer command
> center. Its mission is to make one prompt enough to plan, research,
> route, build, validate, self-improve, and publish software work.

Full text and rationale: `docs/mission/best-coding-tool-mission.md`.

Load this skill at the **start of every coding job** (plan, patch,
review, deploy, doc, refactor). It is the contract you commit to
before you spend any worker tokens.

## Product principles (the 10 rules)

1. One prompt starts everything.
2. Hermes chooses the best worker/model mix.
3. Every decision has visible evidence and validation.
4. Every job has durable artifacts.
5. Every worker output is scored.
6. Every merge is reviewed.
7. Every publish is reversible.
8. Hermes learns from every job.
9. Current AI improvements update the routing policy.
10. The Android APK is the cockpit; Hermes backend is the engine.

If a proposed step would silently violate one of these, **stop and
escalate** — propose the change in the job's artifact directory and
ask the user, do not just bypass.

## What this skill makes you do, per job

### 1. Declare intent

Before any worker is dispatched, write a one-line statement of the
job's goal and tag which principles it primarily advances. Example:

```text
Goal: Add native GitHub PR review gate.
Principles: P3 (visible evidence), P6 (every merge reviewed), P7 (reversible publish).
```

This line goes at the top of the job's artifact directory (see the
self-improvement loop skill for the directory layout).

### 2. Pick the worker/model mix on purpose

Routing is *your* job, not the user's (Principle 2). Record what you
picked and why, in one short paragraph. Cheap model + tight loop for
easy work; capable model + reviewer for hard or irreversible work.
Local-first executors before cloud when the task fits on-device
(Principle 10, Principle Local-first fit).

### 3. Score every output

Every worker output — plan, patch, review, deploy plan, doc — gets
graded against the **standing quality scorecard** (below). The
scorecard travels with the job and is what the reviewer reads first
(Principle 5).

```json
{
  "correctness": 0,
  "maintainability": 0,
  "testability": 0,
  "architecture_fit": 0,
  "developer_experience": 0,
  "ui_ux": 0,
  "speed": 0,
  "cost_efficiency": 0,
  "local_first_fit": 0,
  "jeremiah_fit": 0
}
```

Each axis is 0–10. Any axis `<= 4` blocks merge by default. A
reviewer (different worker or the user) may override with an
explicit, recorded reason.

### 4. Make publishes reversible

Before any externally visible action (`git push`, PR create / merge,
release tag, deploy, Slack/Discord/Telegram send, GitHub issue
comment), record the undo path in the job's artifact directory:

| action | undo |
|---|---|
| `git push` to a feature branch | `git push --delete origin <branch>` |
| PR merge | revert commit on default branch, re-open issue |
| release tag / GitHub release | delete tag + release, redeploy previous tag |
| deploy | redeploy previous artifact / image SHA |
| external message | post a retraction in the same channel |

If there is no clean undo, do not ship (Principle 7) — escalate to
the user.

### 5. Close the loop

When the job ends (success, partial, or failure), hand off to
`self-improvement-loop`. That skill turns this job's artifacts and
scorecard into proposals — updated skills, prompts, routing weights,
or new skills entirely (Principle 8, Principle 9). Do not finish a
job without invoking it.

## When to invoke this skill

- The user opens a new coding job from the Android cockpit or the
  CLI/TUI.
- A new plan starts under `docs/plans/` or `.plans/`.
- A new branch is cut for development work.
- Before the orchestrator dispatches any worker for a job that will
  produce a diff, a deploy, or an external message.

## When NOT to invoke this skill

- Pure conversational Q&A that produces no artifact and no external
  action.
- Internal subroutines that are already executing under a job that
  loaded this skill — load it once per job, not once per step.

## Output contract

When you load this skill, emit (and persist with the job) a short
preamble:

```text
Mission anchor active.
Goal: <one line>
Principles primarily advanced: <Pn, Pn, ...>
Worker/model plan: <one short paragraph>
Reversibility plan: <one line per externally visible action, or "none planned">
Scorecard required at: <path-to-scorecard.json>
```

This preamble is the durable artifact that proves the mission was
honored, not just intended.

## Where each principle is enforced

Each of the 10 principles is **operationalised** by a concrete skill or
doc in this repo. The mission anchor is the *what*; the table below is
the *where*:

| Principle | Where it is enforced |
|---|---|
| P1 — One prompt starts everything | [`hermes-orchestration-pipeline`](../hermes-orchestration-pipeline/SKILL.md), `scripts/hermes-orchestrate.sh` |
| P2 — Best worker/model mix | [`model-router`](../model-router/SKILL.md), [`docs/ai-intelligence/model-registry.yaml`](../../docs/ai-intelligence/model-registry.yaml), [`docs/ai-intelligence/model-routing-policy.md`](../../docs/ai-intelligence/model-routing-policy.md) |
| P3 — Visible evidence and validation | [`decision-quality-gate`](../decision-quality-gate/SKILL.md), [`research-validator`](../research-validator/SKILL.md), [`docs/orchestration/decision-ledger.md`](../../docs/orchestration/decision-ledger.md) |
| P4 — Durable artifacts | Job folder contract in [`hermes-orchestration-pipeline`](../hermes-orchestration-pipeline/SKILL.md), [`docs/orchestration/self-improvement-loop.md`](../../docs/orchestration/self-improvement-loop.md) |
| P5 — Scored worker outputs | Scorecard in [`self-improvement-loop`](../self-improvement-loop/SKILL.md), [`aos-full-agent-team`](../aos-full-agent-team/SKILL.md) |
| P6 — Reviewed merges | [`aos-full-agent-team`](../aos-full-agent-team/SKILL.md) (contrarian + quality gate), [`decision-quality-gate`](../decision-quality-gate/SKILL.md) |
| P7 — Reversible publishes | [`github-publisher`](../github-publisher/SKILL.md), `publish.md` in the job folder |
| P8 — Hermes learns from every job | [`self-improvement-loop`](../self-improvement-loop/SKILL.md) |
| P9 — Current AI improvements update routing | [`ai-improvement-radar`](../ai-improvement-radar/SKILL.md), [`docs/competitive/openhuman-paperclip-research.md`](../../docs/competitive/openhuman-paperclip-research.md) |
| P10 — Android APK is the cockpit; backend is the engine | [`developer-ux-command-center`](../developer-ux-command-center/SKILL.md), [`apps/android/README.md`](../../apps/android/README.md), [`docs/hermes-local-orchestrator.md`](../../docs/hermes-local-orchestrator.md) |

## Posture: private and local-first

The mission is explicitly **private and local-first**:

- Every artifact lives on the user's disk. No telemetry, no remote
  config, no third-party data sharing in the pipeline.
- External AI tools are invoked only when the user is already logged
  in. The Hermes backend never relays prompts through a Hermes-owned
  cloud intermediary.
- The Hermes backend is the engine; the Android APK is the cockpit.

## How to invoke

```text
/reload-skills                              # after editing skills
/best-coding-tool-mission                   # load this skill at job start
/aos-full-agent-team <goal>                 # full team for a goal
/hermes-orchestration-pipeline <job-id>     # drive a job folder
/model-router <task-type>                   # pick a worker / model
/decision-quality-gate <decision-id>        # gate a decision
/ai-improvement-radar                       # scan + write a radar report
/self-improvement-loop                      # close the job
/github-publisher <job-id>                  # ship approved changes
```
