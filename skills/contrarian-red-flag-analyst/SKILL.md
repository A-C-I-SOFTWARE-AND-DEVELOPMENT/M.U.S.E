---
name: contrarian-red-flag-analyst
description: "Alias of contrarian-reviewer (legacy upstream name)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [aos, contrarian, alias, red-team, devils-advocate]
    related_skills:
      - contrarian-reviewer
      - aos-council-director
      - decision-quality-gate
---

# Contrarian Red-Flag Analyst (alias)

This skill is an **alias** for `contrarian-reviewer`. It exists because upstream agent definitions referred to this role as `contrarian-red-flag-analyst`. To avoid breaking those references while standardizing on the shorter Hermes name, both surfaces resolve to the same playbook.

## When to Use

Treat any reference to `contrarian-red-flag-analyst` as a reference to `contrarian-reviewer`. Both slash commands (`/contrarian-red-flag-analyst` and `/contrarian-reviewer`) invoke the same workflow.

## How this alias resolves

- If you (the model) are invoked under `/contrarian-red-flag-analyst`, **load `skills/contrarian-reviewer/SKILL.md` with `read_file`** and follow that playbook exactly.
- The output you persist to `memory` should use the canonical name `contrarian-reviewer` at `aos/council/<slug>/contrarian`, not the alias, so the Director and the `decision-quality-gate` find it in the expected place.
- Do not duplicate the workflow here. Single source of truth is `skills/contrarian-reviewer/SKILL.md`.

## Tools you use

- `read_file` — load `skills/contrarian-reviewer/SKILL.md`
- All tools the canonical skill uses (`search_files`, `session_search`, `memory`, `delegate_task`)

## Quality criteria

- Output uses the canonical key in `memory`, not the alias.
- Any documentation generated cites `contrarian-reviewer` as the canonical name and notes the alias parenthetically — never the other way around.

## Don't

- Don't drift this file out of alias status by adding bespoke workflow here. Update `contrarian-reviewer` instead.
- Don't persist findings under `aos/council/<slug>/contrarian-red-flag-analyst` — that splits the council's audit trail.
