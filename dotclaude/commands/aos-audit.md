---
description: Audit the current AOS / agent system for governance, validation, hallucination risk, and real autonomy
---

# /aos-audit

## Purpose

Audit an existing or proposed multi-agent / AOS system against honest-
autonomy criteria. Surface theater, name overclaims, require fixes before
any public "autonomous" claim.

## When to use

- Before any public, investor, or customer claim of "autonomous" /
  "agentic" / "AI-powered".
- After adding or modifying an agent.
- When the system is failing silently — work appears done but outcomes are
  wrong.

## Agents activated

1. `repo-context-librarian` (first)
2. `aos-systems-architect` (proposes target design)
3. `aos-audit-validator` (mandatory — runs the checklist)
4. `security-privacy-risk-officer` (if the system handles user data, runs
   shell, or hits external APIs)
5. `prompt-systems-engineer` (reviews agent prompts for vagueness, role
   stacking, missing output formats)
6. `hermes-final-synthesizer` (last)

Skill invoked: `aos-governance-system`.

## Required workflow

1. Mission brief: which system, which public claim is being evaluated.
2. Repo map highlighting agent files, skill files, command files,
   memory/log paths.
3. Architect names the intended boundaries, escalation, memory model,
   audit trail.
4. Auditor walks the ten-item checklist with PASS / FAIL / N-A per item,
   evidence cited.
5. Security officer reviews any tool surface (shell, network, file system,
   external APIs).
6. Prompt engineer reviews each agent prompt.
7. Synthesizer produces verdict and required fixes.

## Required output format

```
## System under audit
## Public claim being evaluated
## Boundary, escalation, memory, audit trail (architect)
## Checklist results (auditor — 10 items with PASS/FAIL/N-A + evidence)
## Theater detected (concrete, not vague)
## Real capability confirmed
## Security findings on the agent surface
## Prompt findings
## Required fixes before the public claim is honest
## Verdict: HONEST | OVERCLAIMED | UNVERIFIABLE
## Single next action
```

## Validation requirements

- Every checklist finding cites file:line or a log excerpt.
- "Probably fine" is never PASS.
- Missing audit logs → audit-trail item is FAIL, not "unclear".
- Verdict HONEST requires zero FAILs on items 1, 4, 5, 6, and 7 of the
  AOS governance checklist (boundary, validation gate, audit trail, no
  silent fallback, no self-grading).
