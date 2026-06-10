# ACI Base44 Import Handoff

## Correct source repository

Base44 must clone this repository:

```text
https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent.git
```

Use branch:

```text
main
```

Do not use the personal mirror unless explicitly instructed. The ACI organization repository is the source of truth for this build.

## Project identity

This is the ACI Hermes Agent implementation.

ACI means:

- Accountability
- Communication
- Information
- Software & Development

Hermes must be treated as the operating foundation for ACI's agent workflow, not as a blank Base44 app.

## Base44 import rules

Base44 must:

1. Clone the entire repo.
2. Preserve the existing Python project structure.
3. Preserve `README.md`, `pyproject.toml`, lock files, scripts, docs, CLI code, gateway code, tools, skills, memory systems, dashboard code, Android companion app code, and configuration files.
4. Treat the GitHub repo as canonical.
5. Never rebuild Hermes from scratch.
6. Never flatten this into a simple frontend project.
7. Never hardcode secrets or provider keys.
8. Preserve upstream license and attribution.
9. Make changes in small reviewable commits.
10. Validate changes with the best available install, lint, test, and smoke checks.

## Required ACI layers

Base44 must account for these ACI layers during audit and planning:

1. Hermes Core
   - Existing Hermes CLI, gateway, scheduler, tools, providers, terminal backends, memory, and skills.

2. ACI Agent Suite
   - Structured ACI agents with roles, duties, boundaries, validation rules, and reusable prompts or skills.

3. ACI AOS Layer
   - Autonomous Operating System coordination for request intake, planning, delegation, execution, review, correction, validation, and memory update.

4. ACI SU Layer
   - Supervisory Unit layer for top-level coordination, quality gates, conflict resolution, and approval of major changes.

5. ACI Audit and Validation Layer
   - Evidence capture, acceptance criteria, test results, risk notes, and rollback notes for major changes.

6. ACI Memory and Skills Layer
   - Reusable project knowledge, agent lessons, decisions, prompts, coding standards, and workflow patterns.

7. ACI Orchestration Bridge
   - Integration path for Base44, Codex, Claude Code, Termux, GitHub, shell tools, and future MCP/API tools.

## Required ACI agents to plan for

Base44 should plan repo locations and implementation strategy for:

- SU Agent / Supervisory Unit
- AOS Council Agent
- Code Architect Agent
- Mobile and Termux Agent
- Codex Bridge Agent
- Claude Code Bridge Agent
- Base44 Integration Agent
- Security and Secrets Agent
- QA and Test Agent
- Product Strategy Agent

Do not blindly implement these agents before completing the repo audit. First identify the correct Hermes conventions for skills, prompts, docs, tools, and configuration.

## First Base44 task

Run a complete repository understanding pass before making changes:

1. Identify runtime, package manager, entrypoints, CLI commands, gateway services, docs, scripts, tools, skills, memory system, providers, tests, Android app, and deployment targets.
2. Read `README.md`, `pyproject.toml`, lock files, scripts, docs, and all major source directories.
3. Produce a repo map.
4. Identify what Base44 can safely edit and what should be delegated to Codex, Claude Code, Termux, GitHub Actions, Docker, or shell execution.
5. Identify required environment variables and secrets without exposing or hardcoding them.
6. Propose where ACI agents, AOS council definitions, SU rules, validation gates, and memory policies should live.
7. Produce a staged plan before implementation.

## Copy/paste prompt for Base44

```text
Clone and import the entire repository from GitHub:

https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent.git

Use branch: main.

This is the ACI Hermes Agent build. ACI means Accountability, Communication, Information, Software & Development.

Treat this GitHub repo as the source of truth. Do not start from scratch. Do not generate a disconnected Base44 prototype. Do not flatten the Python CLI/gateway architecture into a frontend-only app.

Preserve Hermes Core while planning the ACI Agent Suite, ACI AOS layer, ACI SU supervisory layer, ACI audit/validation layer, ACI memory/skills layer, and ACI orchestration bridge for Base44, Codex, Claude Code, Termux, GitHub, shell tools, and future MCP/API tools.

Before modifying code, perform a full repo audit. Read README.md, pyproject.toml, lock files, scripts, docs, source folders, tools, skills, memory systems, gateway code, CLI code, dashboard code, Android app code, and tests. Produce a repo map, identify safe edit zones, identify risky areas, identify secrets and environment requirements without exposing secrets, then propose a staged implementation plan.

Required ACI agents to account for:
- SU Agent / Supervisory Unit
- AOS Council Agent
- Code Architect Agent
- Mobile and Termux Agent
- Codex Bridge Agent
- Claude Code Bridge Agent
- Base44 Integration Agent
- Security and Secrets Agent
- QA and Test Agent
- Product Strategy Agent

Rules:
- Keep the repo canonical.
- Preserve package structure.
- Preserve upstream attribution and license.
- Do not hardcode secrets.
- Use small reviewable commits.
- Validate every change with the best available checks.
- Every major recommendation must include reason, risk, affected files, validation method, and rollback plan.
```
