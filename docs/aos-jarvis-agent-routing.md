# AOS and MUSE Agent Routing Plan

This document defines the routing plan for MUSE and the AOS council. It is a plan only: it does not mutate the AOS registry, does not activate new default agents, and does not claim the registry is fixed.

> **Agent routing vs. model routing.** This page is about *which agent /
> council member* handles a request. For *which LLM* runs a given task class
> (evidence-backed, mobile-first), see
> [`ai-intelligence/model-routing-task-classes.md`](ai-intelligence/model-routing-task-classes.md).

## Goals

- Keep the active reasoning layer small enough for daily Slack and Termux work.
- Separate decision agents from skills, workers, personas, product roles, and archived recovered sources.
- Preserve recovered source material as historical reference while operating from a smaller verified registry.
- Require owner review before broad registry mutation, default-agent expansion, or production publishing.

## Small Active Core Council

The default active council should stay small and mission-focused. It is the daily operating set for Slack, Termux, GitHub planning, and local verification.

**Current operating council** — the runnable Claude Code subagents that exist under `.claude/agents/` today:

| Subagent (file)             | Role bucket               |
| --------------------------- | ------------------------- |
| `aos-council-director`      | executive routing / chair |
| `principal-systems-architect` | architecture              |
| `assurance-risk-director`   | security / risk review    |
| `product-experience-architect` | product / UX review    |
| `contrarian-reviewer`       | red-team / counter-position |
| `delivery-scope-controller` | scope + release gate      |
| `evidence-architect`        | evidence / memory curator |
| `codex-dispatch-governor`   | codex routing / review    |
| `commercial-strategist`     | product strategy          |

These are the 9 invocable subagents Claude Code can route to via `Agent(subagent_type=<name>)`. They should not be expanded automatically just because additional recovered roles exist.

**Target role names** (aspirational, used in this doc for clarity; map to the current files above): `executive-router` → `aos-council-director`; `security-compliance-reviewer` → `assurance-risk-director`; `product-ux-reviewer` → `product-experience-architect`; `qa-release-gate` → `delivery-scope-controller`; `memory-evidence-curator` → `evidence-architect`; `codex-reviewer` → `codex-dispatch-governor`. `claude-code-builder` has no dedicated subagent file yet — invoke via `Agent(subagent_type=general-purpose)` with a build-mission prompt until one is added.

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
