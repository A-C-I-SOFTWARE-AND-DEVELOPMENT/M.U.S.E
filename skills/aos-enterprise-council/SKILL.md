---
name: aos-enterprise-council
description: Verified AOS council operating registry.
version: 3.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows, termux]
metadata:
  hermes:
    tags: [aos, council, registry, slack, specialists, workers]
    activation_phrases:
      - "audit repo"
      - "audit the repo"
      - "audit this repo"
      - "build the app"
      - "enterprise hardening"
      - "launch readiness"
      - "improve the product"
      - "use the AOS team"
      - "activate the council"
      - "run the council"
      - "psychology audit"
      - "ux audit"
      - "codex orchestration"
      - "HazMat Command review"
      - "Nourish review"
    related_skills:
      - aos-council
      - autonomous-ai-agents
      - github-publisher
      - hermes-orchestration-pipeline
---

# AOS Enterprise Council

Use this skill to route AOS work through the verified Hermes operating registry.

## When to Use

- The request mentions auditing, hardening, launch readiness, council activation, or AOS / HazMat / Nourish review (see activation phrases in the frontmatter).
- A task needs multi-perspective judgment (architecture + UX + risk + scope + evidence) before commitment, deploy, or public claim.
- A specialist domain (compliance, security, product, hazmat, nutrition, pricing) is in scope and you want the right specialist routed, not improvised.

Do not use this skill for trivial cleanups, single-file edits, or work where one agent is clearly the right path.

## Prerequisites

- `operating-registry/registry.json` and `operating-registry/schema.json` present.
- Python 3.11+ available to run the verifier (`scripts/verify_registry.py`).
- Hermes runtime is loaded with this skill installed (`skills/aos-enterprise-council/`).
- For specialist invocation, the specialist's `required_inputs` are gathered or explicitly named as missing.

## How to Run

1. Load the registry: read `operating-registry/registry.json` and confirm `version` matches what you expect.
2. Pick the council size from `policies.default_slack_council_max` (default 6).
3. Route per the "Operating standard" and "Routing rules" sections below.
4. Run `scripts/verify_registry.py` before dispatching destructive or public-facing work — the verifier checks schema, IDs, path existence (skipping `status: planned`), and policy invariants.
5. For specialists, confirm `required_inputs` and `owner_gate` before dispatch.

## Quick Reference

- **Registry**: `operating-registry/registry.json`
- **Schema**: `operating-registry/schema.json`
- **Verifier**: `scripts/verify_registry.py`
- **Default Slack council members**: see "Default Slack council" below
- **Historical reference (read-only)**: `registry/AOS_AGENT_REGISTRY_COMPLETE.md`, `registry/AOS_SUBAGENT_REGISTRY_COMPLETE.md`, `registry/AOS_PROMPT_LIBRARY_COMPLETE.md`, `registry/AOS_WORKFLOW_LIBRARY_COMPLETE.md`, `source-snapshots/`

## Operating standard

Load `operating-registry/registry.json` before dispatching AOS work. The operating registry is the source of truth for daily work; the recovered registry remains historical reference only.

## Default Slack council

Use the small active council for normal Slack work:

1. council-director
2. evidence-architect
3. delivery-scope-controller
4. product-experience-architect
5. assurance-risk-director
6. contrarian-reviewer

Do not create more always-active agents.

## Routing rules

- Convert narrow procedures into skills, not agents.
- Convert execution lanes into workers, not decision agents.
- Summon domain specialists only when their required inputs exist.
- Keep personas separate from runnable agents.
- Keep product roles separate from workers and personas.
- Preserve recovered registries as historical references.

## Procedure

1. **Classify**: decide whether the task is decision (council), specialist domain (specialists), procedure (skills), or execution (workers).
2. **Verify**: run the verifier; reject dispatch if it reports failures.
3. **Dispatch**: invoke the chosen runnable subagent (`Agent(subagent_type=<id>)` for those backed by `.claude/agents/<id>.md`). For specialists without a runnable subagent, route by registry id and document the gap.
4. **Gate**: any merge, deploy, public post, credential change, or destructive action requires explicit "Yes, with authorization." from the owner.
5. **Record**: persist mission, evidence, scorecard, and decision via `memory` so the next session can pick up the trail.

## Pitfalls

- **Reading recovered registries as live.** `recovered-agent-sources/`, `registry/AOS_*`, and `source-snapshots/` are historical. Treating them as the operating set lets retired/duplicate agents back in.
- **Skipping path existence.** Older verifier versions silently passed even when registry paths were broken. Confirm you're on the verifier that resolves `path` via `_resolve_path` and honors `status`.
- **Inflating the active council.** The policy max is intentional. If a domain shows up repeatedly, promote a specialist or skill — don't grow the council.
- **Confusing skills, workers, and decision agents.** Worker-as-decision-agent is the most common drift; skills-as-agents is the next. Both undermine the small-council invariant.
- **Bypassing owner gates.** "I'll just merge it" without `Yes, with authorization.` violates the registry contract regardless of how trivial the change looks.

## Owner gates

Owner gates are allowed only with explicit authorization.

Current owner gate setting: Yes, with authorization.

## Verification

Run:

```bash
python skills/aos-enterprise-council/scripts/verify_registry.py
```

The verifier checks: JSON Schema validity (when `jsonschema` is available), unique IDs across sections, council size within `policies.default_slack_council_max`, owner-gate phrase, registered `path` exists on disk (unless `status: planned`), SKILL.md frontmatter description ≤60 chars + single sentence, separated-collection directories, and historical-reference paths.

Also review by hand for sanity:

- `operating-registry/registry.json`
- `runnable-agents/active-council.md`
- `specialists/README.md`
- `skills/README.md`
- `workers/README.md`
- `slack/SLACK_TEAM_USAGE_RULES.md`
- `migration/FIRST_PR_PLAN.md`

## Historical reference

The full recovered registry is preserved under `registry/` and `source-snapshots/`. Do not dispatch recovered entries directly until they are curated into the operating registry and pass verification.
