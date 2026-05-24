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

## Owner gates

Owner gates are allowed only with explicit authorization.

Current owner gate setting: Yes, with authorization.

## Verification

Run:

```bash
python skills/aos-enterprise-council/scripts/verify_registry.py
```

Also review:

- `operating-registry/registry.json`
- `runnable-agents/active-council.md`
- `specialists/README.md`
- `skills/README.md`
- `workers/README.md`
- `slack/SLACK_TEAM_USAGE_RULES.md`
- `migration/FIRST_PR_PLAN.md`

## Historical reference

The full recovered registry is preserved under `registry/` and `source-snapshots/`. Do not dispatch recovered entries directly until they are curated into the operating registry and pass verification.
