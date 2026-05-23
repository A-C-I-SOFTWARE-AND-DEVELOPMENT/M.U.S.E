---
name: self-improvement-loop
description: "Close every job with a learning pass: read artifacts + scorecard, propose updates to skills/prompts/routing, record what to keep, what to drop, and what to try next."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [learning, curator, routing, scorecard, mission, monitor, private-local]
    related_skills:
      - best-coding-tool-mission
      - hermes-orchestration-pipeline
      - aos-full-agent-team
      - model-router
      - decision-quality-gate
      - research-validator
      - ai-improvement-radar
      - github-publisher
      - developer-ux-command-center
      - enterprise-monitor
      - enterprise-orchestrator
    related_docs:
      - docs/orchestration/self-improvement-loop.md
      - docs/orchestration/hermes-orchestration-pipeline.md
      - docs/orchestration/decision-ledger.md
      - docs/ai-intelligence/model-registry.yaml
      - docs/ai-intelligence/ai-improvement-radar.md
      - docs/competitive/openhuman-paperclip-research.md
      - docs/mission/best-coding-tool-mission.md
---

# Self-Improvement Loop

> Hermes learns from every job. (Principle 8)
> Current AI improvements update the routing policy. (Principle 9)

Load this skill at the **end of every coding job** — success,
partial, or failure. It is the pass that converts artifacts and
scorecards into durable improvement, so the next prompt is cheaper,
faster, or more correct than this one.

Full mission context: `docs/mission/best-coding-tool-mission.md`.
Operational details and storage layout:
`docs/orchestration/self-improvement-loop.md`.

## Inputs

The job's artifact directory, which by convention contains:

- `goal.txt` — the one-line intent and principles tagged.
- `routing.md` — the worker/model mix and rationale.
- `plan.md` / `plan.json` — the plan the orchestrator dispatched.
- `transcripts/` — per-worker transcripts.
- `diffs/` — proposed/applied patches.
- `scorecard.json` — the standing quality scorecard for each worker
  output (see below).
- `evidence/` — tests, logs, screenshots, eval runs.
- `publish.md` — externally visible actions and their undo paths.

If any of these are missing, the previous skill (`best-coding-tool-mission`)
was skipped. Flag it in the proposals and ask the user whether to
backfill or to treat this job as untrusted.

## Standing quality scorecard

The shape every worker output is graded against (axis = 0..10):

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

## What to do

### 1. Read, don't trust

Read `scorecard.json`, `transcripts/`, `diffs/`, and `evidence/`.
Re-derive the scores. Worker self-scores are a starting point, not a
verdict. Disagreements between worker self-score and your re-score
become their own learning signal (record them).

### 2. Bucket findings

Sort each finding into one of these kinds. Each kind has a default
target:

| kind | target |
|---|---|
| `skill_gap` | A skill SKILL.md (existing) — its prompt missed a case the job needed. |
| `new_skill` | A new directory under `skills/<area>/<name>/` — the job revealed a recurring need with no skill yet. |
| `routing_miss` | Routing policy — the wrong worker/model was picked for this kind of work. |
| `prompt_regression` | A worker prompt — the worker produced low-scorecard output because of how it was asked. |
| `tool_gap` | A tool / plugin under `tools/`, `plugins/`, `gateway/`, or `enterprise/` — the worker had no clean way to do something. |
| `evidence_gap` | The eval / test setup — we could not verify the change cheaply, so testability scored low. |
| `mission_drift` | A principle from `docs/mission/best-coding-tool-mission.md` was violated. The proposal must name which principle and how the change restores it. |

### 3. Write proposals

For each finding, write one proposal file as JSON. Default location:

```
~/.hermes/self-improvement/drafts/prop-<8hexchars>.json
```

Shape:

```json
{
  "kind": "skill_gap",
  "target": "skills/software-development/<skill-name>/SKILL.md",
  "summary": "One sentence.",
  "rationale": "Why this matters, with one or two scorecard axes that dropped.",
  "evidence": [
    "<job-id>/transcripts/builder-001.md",
    "<job-id>/scorecard.json#correctness"
  ],
  "evidence_event_count": 1,
  "proposed_change": "Concrete diff or prompt delta.",
  "scorecard_delta_expected": {
    "correctness": "+2",
    "speed": "+1"
  },
  "principles": ["P3", "P5"],
  "reversible": true,
  "extra": {}
}
```

### 4. Promotion policy

- **Apply directly** only for: appending a frontmatter tag, adding a
  known-good (domain, action) row to a policy table, bumping a
  routing weight by `<=` one notch. All must be reversible
  (Principle 7) and recorded in the proposal's `extra.previous_value`.
- **Promote to the curator drafts lane** (`agent/curator.py`) for
  prompt edits, new skills, removed skills, ACL changes, risk
  reclassifications. The curator runs the human or next-session
  review path.
- **Defer** if you cannot categorise the finding. Leave the
  proposal in `drafts/` and surface the count to the user with a
  one-line summary.

### 5. K=3 confirmation rule

Do not auto-promote a proposal whose `evidence_event_count == 1`
unless the proposal carries `extra.user_confirmed = true`. When the
same `kind` + `target` has fired across **three** consecutive jobs,
the loop auto-promotes to the curator drafts lane (this matches the
enterprise-council monitor's behavior; see
`skills/enterprise-council/monitor/SKILL.md`).

### 6. Update the routing policy (Principle 9)

If new models, providers, tools, or local executors appeared during
this job — or were noted as needed and missing — emit a
`routing_miss` proposal that names the capability and a one-line
weight change. Routing is a living artifact, not a constant.

### 7. Reversibility check on the loop itself

Every applied change must record its undo path in the proposal. If
this skill cannot describe how to revert one of its own applied
changes, it must downgrade that change to "promote to curator" and
not apply it (Principle 7 applies to learning too).

## What this skill must NOT do

- Modify a SKILL.md while another session is still running against it.
- Delete or rewrite an existing rule without leaving the previous
  value in `extra.previous_value`.
- Promote a single-event proposal without `extra.user_confirmed`.
- Write into a worker's transcripts or scorecards after the fact —
  history is append-only.

## Output contract

When you finish the loop, emit (and persist with the job) a short
trailer:

```text
Self-improvement loop complete.
Job: <job-id>
Proposals: <n total> (<n applied>, <n promoted>, <n deferred>)
K=3 promotions this run: <n>
Routing updates: <one line, or "none">
Next prompt should be: <one short line, e.g. "cheaper: prefer local builder for refactors of <200 LOC">
```

The trailer is what the user reads to know the loop actually closed.

## Where this fits in the larger system

The loop is the **closing pass** of every orchestrated job. It does
not pick workers, run research, gate decisions, or ship code — it
turns the artifacts those other skills produced into durable
improvements:

| Concern | Skill / doc |
|---|---|
| Job folder the loop reads from | [`hermes-orchestration-pipeline`](../hermes-orchestration-pipeline/SKILL.md) |
| Mission anchor (Principle 8 + Principle 9) | [`best-coding-tool-mission`](../best-coding-tool-mission/SKILL.md) |
| Decision ledger the loop mines | [`decision-quality-gate`](../decision-quality-gate/SKILL.md) (template: [`docs/orchestration/decision-ledger.md`](../../docs/orchestration/decision-ledger.md)) |
| Evidence re-derivation discipline | [`research-validator`](../research-validator/SKILL.md) |
| `routing_miss` proposals consumed by | [`model-router`](../model-router/SKILL.md) |
| Fresh capability signals feeding routing updates | [`ai-improvement-radar`](../ai-improvement-radar/SKILL.md) |
| Council that runs through this loop on close | [`aos-full-agent-team`](../aos-full-agent-team/SKILL.md) |
| Publishing the changes the loop produced | [`github-publisher`](../github-publisher/SKILL.md) |
| Terminal surface for inspecting proposals | [`developer-ux-command-center`](../developer-ux-command-center/SKILL.md) |

## Posture: private and local-first

- Proposals live on disk under `~/.hermes/self-improvement/drafts/`
  and `applied/`. Nothing is uploaded.
- The loop never calls an external API. It reads job artifacts and
  writes proposal files.
- The Android APK cockpit reads the trailer line and the proposals
  count from the same on-disk contract — the cockpit can surface a
  proposal to the user for approval, but the approval itself is
  recorded on disk through [`decision-quality-gate`](../decision-quality-gate/SKILL.md).

## Hermes backend is the engine; the APK is the cockpit

The loop runs on the Hermes backend at the end of every job. The
Android APK cockpit displays the trailer as the last thing the user
sees for a job (Principle 10: the APK is the cockpit, the backend is
the engine).

## How to invoke

```text
/reload-skills                              # after editing skills
/self-improvement-loop                      # close the current job
/ai-improvement-radar                       # upstream: fresh capability signals
/decision-quality-gate                      # upstream: the ledgers this loop mines
/model-router <task-type>                   # downstream: consumes routing_miss proposals
```
