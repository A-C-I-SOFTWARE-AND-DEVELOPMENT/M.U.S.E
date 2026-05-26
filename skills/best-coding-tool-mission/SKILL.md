---
name: best-coding-tool-mission
description: "Anchor every job to Hermes' mission as the best private local-first developer command center: one prompt, routed work, scored output, reversible publishes, learning loop."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mission, routing, quality, scorecard, local-first, jeremiah]
    related_skills: [self-improvement-loop, enterprise-orchestrator, enterprise-monitor]
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
