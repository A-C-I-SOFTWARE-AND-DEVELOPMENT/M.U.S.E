# AOS and JARVIS Agent Routing Plan

This document defines the routing plan for JARVIS Prime and the AOS council. It is a plan only: it does not mutate the AOS registry, does not activate new default agents, and does not claim the registry is fixed.

## Goals

- Keep the active reasoning layer small enough for daily Slack and Termux work.
- Separate decision agents from skills, workers, personas, product roles, and archived recovered sources.
- Preserve recovered source material as historical reference while operating from a smaller verified registry.
- Require owner review before broad registry mutation, default-agent expansion, or production publishing.

## Small Active Core Council

The default active council should stay small and mission-focused. It is the daily operating set for Slack, Termux, GitHub planning, and local verification.

Default active council:

- executive-router
- principal-systems-architect
- security-compliance-reviewer
- product-ux-reviewer
- contrarian-reviewer
- qa-release-gate
- memory-evidence-curator
- claude-code-builder
- codex-reviewer

These are runnable decision agents or bounded builder/reviewer roles. They should not be expanded automatically just because additional recovered roles exist.

## Domain Specialists

Domain specialists are activated only when the task needs that domain. Examples include legal/compliance, logistics, HazMat, nutrition, pricing, career strategy, investor narrative, UX research, data engineering, or release management.

A specialist entry must include:

- when to use
- when not to use
- required inputs
- required output
- verification method
- owner gate if needed

Specialists should not become always-active agents unless they are repeatedly needed in the default daily workflow and pass owner review.

## Super-Specialist Skills

Super-specialist skills are narrow procedures. They should be skills, not agents, when they describe repeatable methods such as PR handoff, memory correction, Slack triage, code review templates, registry verification, or routing checklists.

A skill should include modern SKILL.md structure, a short description, prerequisites, procedure, pitfalls, and verification. It should not make strategic decisions by itself.

## Worker Templates

Worker templates are execution lanes. They should receive scoped packets and return evidence. They are not decision agents.

Common worker template types:

- Claude Code implementation worker.
- Codex review worker.
- test verification worker.
- docs update worker.
- repo audit worker.
- migration worker.
- Slack triage worker.

Workers must declare inputs, boundaries, allowed files or directories, verification commands, and handoff format.

## Personas and Reference Only

Personas are reference-only. They may simulate audience, tone, customer viewpoint, stakeholder pressure, or critique style. They should not be treated as runnable agents or default council members.

Personas can influence a review, but they do not own execution or approval.

## Product Roles and Reference Only

Product roles are reference-only. They represent stakeholder needs such as founder, customer, operator, driver, admin, reviewer, buyer, investor, or support agent.

Product roles can shape requirements, acceptance criteria, and risk review. They should not be activated as autonomous agents by default.

## Archived Recovered Sources

Archived recovered sources preserve the full recovered registry as historical reference. They should remain available for research, migration, and audit, but they are not the operating registry.

The operating registry should be smaller, verified, and explicit about which entries are runnable agents, skills, workers, personas, product roles, and archived recovered sources.

## Needs Owner Review

Owner review is required before:

- adding always-active agents;
- changing the default active council;
- mutating the AOS registry;
- deleting recovered historical sources;
- promoting reference-only material into runnable agents;
- merging, publishing, deploying, or changing credentials.

## Migration Direction

1. Preserve recovered sources under archive.
2. Create a verified operating registry.
3. Classify every entry as runnable agent, skill, worker, persona, product role, or archive.
4. Convert narrow procedures into skills.
5. Convert execution lanes into workers.
6. Keep the daily council small.
7. Verify with scripts before commit and PR handoff.
