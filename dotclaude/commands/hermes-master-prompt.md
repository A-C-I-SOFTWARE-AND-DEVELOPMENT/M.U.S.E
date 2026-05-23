---
description: Generate a copy/paste master prompt for Claude Code, Codex, Base44, AI Studio, or deep research
---

# /hermes-master-prompt

## Purpose

Generate a portable, copy/paste master prompt that drives another tool
(Codex, Base44, AI Studio, deep research, or another Claude session) to
execute a specific mission end-to-end.

## When to use

- You want to run the same task in a different tool.
- You want a reusable prompt for a recurring job.
- You want a prompt to hand to a collaborator.

## Agents activated

1. `prompt-systems-engineer` (owns the draft)
2. `repo-context-librarian` (if the prompt depends on repo facts)
3. Any specialist whose domain the prompt covers, as a reviewer
4. `hermes-final-synthesizer` (only if multiple variants were drafted and
   one must be chosen)

Skill invoked: `hermes-master-prompt`.

## Required workflow

1. Collect inputs: target surface, mission, constraints, definition of
   done, evaluation criteria.
2. Draft the prompt using the seven-part anatomy (role, engage-when,
   inputs, procedure, hard rules, output format, honesty floor).
3. Include a fenced output template the target will fill.
4. Include one test input that should hit a known edge case.

## Required output format

```
## Target surface
## Mission
## Required inputs
## Prompt (copy/paste, fenced)

\`\`\`
<the prompt>
\`\`\`

## How to evaluate the run
- Pass criteria
- Fail criteria
- Edge-case test input
```

## Validation requirements

- The prompt must include an output template.
- The prompt must name where the target gets any required context, not
  leave `[insert ...]` placeholders.
- For Claude Code subagent prompts, YAML frontmatter (`name`,
  `description`, `model`) is mandatory.
