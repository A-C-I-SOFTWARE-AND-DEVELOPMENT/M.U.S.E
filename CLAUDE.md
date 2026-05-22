# Claude Code Instructions for Hermes + AOS

## Purpose

This repository is a Hermes Agent codebase with an added AOS/Council planning layer for Jeremiah Echerd's software-building workflow.

Hermes supplies the runtime: agent loop, tools, skills, memory, plugins, terminal backends, scheduler, and messaging surfaces. The AOS/Council layer supplies planning discipline, evidence review, role-based analysis, quality review, and implementation checklists.

## Default Workflow

For architecture, product strategy, security, compliance, public-facing claims, automation, release readiness, or large repository changes, use this sequence before implementation:

1. Mission brief
2. Evidence bundle
3. Multiple candidate plans
4. Council review and scorecard
5. Synthesized plan
6. Red-team critique
7. Revised final plan
8. Execution blueprint
9. Implementation
10. Tests, validation, and retrospective

## Project Agents

Use these project agents as the default AOS Council bench:

- `aos-council-director`
- `evidence-architect`
- `principal-systems-architect`
- `product-experience-architect`
- `commercial-strategist`
- `assurance-risk-director`
- `delivery-scope-controller`
- `contrarian-red-flag-analyst`
- `codex-dispatch-governor`

## Routing

Use `aos-council-director` for broad planning, deep research, governance, repo-readiness, product strategy, or architecture.

Use `evidence-architect` when conclusions depend on repo state, logs, docs, code, or external assumptions.

Use `assurance-risk-director` and `contrarian-red-flag-analyst` before high-impact implementation.

Use `codex-dispatch-governor` after a task has been narrowed into implementation work with acceptance criteria and validation commands.

## Required Context Files

Before major work, read:

- `docs/context/AEO_AOS_Council_Engine_Master_Reference_2026-05-17.md`
- `docs/governance/16-deliberative-planning-and-council-mode.md`
- `AGENTS.md`
- Relevant files in `.claude/agents/`
- Relevant files in `.claude/commands/`

## Output Standard

For major tasks, produce:

- Executive verdict
- Evidence reviewed
- Agent perspectives
- Decision scorecard
- Recommended plan
- Blockers and risks
- Execution checklist
- Validation commands
- Rollback notes
- Open questions only when blocking

## Hermes Integration Notes

Prefer adding AOS/Council capability as repo-native docs, skills, Claude agents, commands, and optional plugins rather than hardcoding fragile behavior into Hermes core.

If implementation requires tool changes, follow `AGENTS.md`: create the tool implementation, register it with the registry, and expose it through the correct toolset. If implementation can live as a skill or plugin, prefer that path first.
