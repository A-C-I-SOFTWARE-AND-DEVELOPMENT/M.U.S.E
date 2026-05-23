---
name: hermes-master-prompt
description: Generate a copy/paste master prompt for Claude Code, Codex, Base44, AI Studio, or deep research, on a specific mission. Use when the owner needs a portable prompt that another tool can execute end-to-end.
---

# Hermes Master Prompt

## Use when

- The owner needs to drive a different tool (Codex, Base44, AI Studio,
  deep research) with one prompt.
- A reusable prompt is needed for a recurring task.

## Required inputs

- **Target surface** — Claude Code, Codex, Base44, AI Studio, deep
  research, or other (name it).
- **Mission** — one sentence.
- **Constraints** — repo / branch, files allowed, files forbidden,
  validation commands, deadline.
- **Definition of done** — executable, not aspirational.

## Procedure

1. Pick the target surface; load its known quirks (token budget, tool
   availability, expected I/O).
2. Draft the prompt using the seven-part anatomy: role, engage-when,
   inputs required, procedure, hard rules, output format, honesty floor.
3. Include a fenced output template the target will fill.
4. Include one example input that should hit a known edge case.

## Output

```
## Target surface
## Mission
## Required inputs
## Prompt (copy/paste)

\`\`\`
<the prompt>
\`\`\`

## How the owner evaluates the run
- pass criteria
- fail criteria
- a test input that should hit the edge case
```

## Hard rules

- Never deliver a prompt without an output template.
- Never deliver a prompt that requires the target to fabricate context
  ("[insert architecture here]") without telling the owner where to get
  it.
- For Claude Code subagent prompts, always include YAML frontmatter.
