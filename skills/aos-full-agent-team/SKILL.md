---
name: aos-full-agent-team
description: "Full AoS council: spin up all 16 specialists end-to-end."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [aos, council, full-team, orchestration, master]
    related_skills:
      - aos-council-director
      - evidence-architect
      - principal-systems-architect
      - product-experience-architect
      - commercial-strategist
      - assurance-risk-director
      - delivery-scope-controller
      - contrarian-reviewer
      - contrarian-red-flag-analyst
      - codex-dispatch-governor
      - model-router
      - github-publisher
      - developer-ux-command-center
      - decision-quality-gate
      - research-validator
      - self-improvement-loop
      - ai-improvement-radar
---

# AoS Full Agent Team

Master orchestration skill. Spins up the full 16-specialist AoS council against a single user goal, runs the canonical sequence, and produces a published decision-of-record. Use this when you want the whole apparatus, not a single specialist.

## When to Use

- The user invokes `/aos-full-agent-team` directly
- A decision is consequential enough that any single specialist isn't enough
- The user says "run the council" / "full team review" / "AoS pass"

## The 16 specialists

| Slot | Skill | Slash | Role |
|------|-------|-------|------|
| Director | `aos-council-director` | `/aos-council-director` | Decomposes, dispatches, integrates |
| Evidence | `evidence-architect` | `/evidence-architect` | Builds the evidence base |
| Architecture | `principal-systems-architect` | `/principal-systems-architect` | System / technical design |
| Product | `product-experience-architect` | `/product-experience-architect` | User / journey / experience |
| Commercial | `commercial-strategist` | `/commercial-strategist` | Market / pricing / GTM |
| Risk | `assurance-risk-director` | `/assurance-risk-director` | Safety, security, legal, veto |
| Delivery | `delivery-scope-controller` | `/delivery-scope-controller` | Scope, sequencing, slices |
| Contrarian | `contrarian-reviewer` | `/contrarian-reviewer` | Devil's advocate, red flags |
| Contrarian (alias) | `contrarian-red-flag-analyst` | `/contrarian-red-flag-analyst` | Alias of contrarian-reviewer |
| Dispatch | `codex-dispatch-governor` | `/codex-dispatch-governor` | Hands coding work to agents |
| Routing | `model-router` | `/model-router` | Picks the model per task |
| Publishing | `github-publisher` | `/github-publisher` | Publishes to GitHub |
| DX | `developer-ux-command-center` | `/developer-ux-command-center` | Developer ergonomics, docs |
| Gate | `decision-quality-gate` | `/decision-quality-gate` | Final completeness / coherence gate |
| Validation | `research-validator` | `/research-validator` | Fact-checks citations |
| Retro | `self-improvement-loop` | `/self-improvement-loop` | Updates playbook from outcomes |
| Radar | `ai-improvement-radar` | `/ai-improvement-radar` | Scans AI ecosystem |

## Canonical sequence

```
1. Director       — read goal, write brief, plan council tasks
2. Evidence       — build evidence pack (memory: aos/council/<slug>/evidence)
3. Specialists    — dispatched in parallel via delegate_task:
                      principal-systems-architect
                      product-experience-architect
                      commercial-strategist
                      developer-ux-command-center
4. Risk           — assurance-risk-director (reads all specialist findings)
5. Delivery       — delivery-scope-controller (reads all findings + risk)
6. Dispatch       — codex-dispatch-governor + model-router (only if slices need handoff)
7. Validation     — research-validator (only for claims marked factual/empirical)
8. Contrarian     — contrarian-reviewer (always — never skipped)
9. Gate           — decision-quality-gate (always — never skipped)
10. Publish       — github-publisher (only on pass / conditional)
11. Retro         — self-improvement-loop (only when user requests, or on slip)
12. Radar         — ai-improvement-radar (independent cadence; runs on demand)
```

## Workflow

1. Load this SKILL.md (you're here). Read the user's goal verbatim.
2. **Compute the goal slug** — lowercase, hyphenated, ≤40 chars. Persist the brief and goal under `memory` at `aos/council/<slug>/brief`.
3. **Install the council todo list** via `todo`, one entry per step in the canonical sequence.
4. **Invoke `aos-council-director`** with the goal slug. From here, the Director runs the council; you (under `aos-full-agent-team`) are the wrapping orchestrator.
5. The Director dispatches each specialist via `delegate_task`. Parallel where the canonical sequence allows; sequential where it doesn't.
6. At every step, mark the corresponding `todo` entry done.
7. Read the final `quality_gate` result from `memory` at `aos/council/<slug>/quality_gate`.
8. If `pass` or `conditional`, hand off to `github-publisher`. If `fail`, present the blockers to the user and stop.

## Output contract — wrapper summary

```json
{
  "goal": "<verbatim>",
  "slug": "...",
  "memory_root": "aos/council/<slug>",
  "specialists_run": ["..."],
  "specialists_skipped": [{"name": "...", "reason": "..."}],
  "final_quality_gate": "pass | conditional | fail",
  "decision_memory_key": "aos/council/<slug>/decision",
  "publication": "<receipt or 'not published'>",
  "next_actions": ["..."]
}
```

## Tools you use

- `memory` — root for the council session
- `todo` — install and tick off the canonical sequence
- `delegate_task` — invoke `aos-council-director`, which fans out the rest
- `read_file`, `search_files` — only when the user's goal references concrete files
- `session_search` — find prior councils on the same topic and reuse their decision-of-record where appropriate
- `write_file` — only to materialize the final decision-of-record as a file when the user asks

## Quality criteria

- The canonical sequence is followed unless the user explicitly opted out of a step.
- Every skipped specialist appears in `specialists_skipped` with a concrete `reason`.
- The contrarian and the quality gate are **never** in `specialists_skipped`.
- The `memory_root` is the single audit trail for the whole council — no findings live outside it.
- The wrapper summary points to the decision-of-record memory key, not a copy of it.

## Don't

- Don't try to be a specialist yourself. Your job is orchestration; the specialists own substance.
- Don't publish without a `pass` or `conditional` quality gate.
- Don't skip the contrarian pass for speed.
- Don't run `self-improvement-loop` or `ai-improvement-radar` automatically inside a council — those run on demand, against history.
