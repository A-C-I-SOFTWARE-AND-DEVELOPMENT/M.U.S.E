# AEO / AOS Council Engine Master Reference

Date: 2026-05-17
Owner: Jeremiah Echerd
Repository context: Hermes Agent with AOS/Council planning layer

## Executive Definition

The AEO / AOS Council Engine is a governed, evidence-backed deliberation and execution-control system for high-stakes AI-assisted software and enterprise planning.

Its purpose is to improve decisions before autonomous or semi-autonomous agents execute. It does this by forcing role-based review, evidence gathering, plan comparison, risk analysis, and acceptance criteria before implementation.

## Core Thesis

Before agents execute, they should deliberate.

The Council Engine is not just a prompt library, not just a multi-agent framework, and not just an AI coding workflow. It is a structured decision layer that sits above implementation tools such as Claude Code, Codex, Base44, Cursor, or other coding agents.

## Operating Model

1. Define the mission.
2. Gather evidence.
3. Generate multiple candidate approaches.
4. Review through specialized expert roles.
5. Compare options using a decision scorecard.
6. Stress-test the preferred plan.
7. Produce a revised master plan.
8. Convert the plan into bounded implementation tasks.
9. Validate with tests, QA, and retrospective notes.

## Council Roles

- AOS Council Director: orchestrates the process.
- Evidence Architect: gathers facts and verifies repository state.
- Principal Systems Architect: reviews technical design.
- Product Experience Architect: reviews user workflow and demo clarity.
- Commercial Strategist: reviews buyer fit, packaging, and positioning.
- Assurance Risk Director: reviews security, compliance, reliability, and test posture.
- Delivery Scope Controller: converts plans into practical implementation phases.
- Contrarian Reviewer: challenges assumptions and identifies gaps.
- Codex Dispatch Governor: converts approved work into narrow implementation tasks.

## Quality Bar

The system should produce outputs that are:

- Evidence-backed
- Role-reviewed
- Risk-aware
- Implementation-ready
- Testable
- Reversible where possible
- Clear enough for another agent or developer to execute

## Fit With Hermes

Hermes provides the runtime environment: memory, skills, plugins, tools, scheduler, terminal backends, and messaging surfaces.

The AOS/Council layer provides planning, review, governance, and execution control. It should be implemented primarily through docs, skills, Claude agents, Claude commands, optional plugins, and context files rather than invasive changes to Hermes core.
