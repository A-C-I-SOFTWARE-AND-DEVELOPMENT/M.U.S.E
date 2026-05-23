# Global CLAUDE.md — Hermes Operating Layer

This file is loaded by Claude Code at the start of every session on this
machine, regardless of which repository is open. It establishes the Hermes /
AOS operating contract and points to the specialist agents, skills, and
commands installed under `~/.claude/`.

## Operating layer

@~/.claude/hermes/HERMES_GLOBAL.md

If the `@` import above is not honored by the running Claude Code version, read
that file manually before acting — it is the authoritative operating contract.

## Quick reference

- **Agents** — see `~/.claude/agents/`. Use the `Agent` tool with
  `subagent_type` set to the agent name (e.g. `hermes-chief-orchestrator`).
- **Skills** — see `~/.claude/skills/`. Use the `Skill` tool with the skill
  name (e.g. `hermes-council-protocol`).
- **Commands** — see `~/.claude/commands/`. Invoke as slash commands
  (e.g. `/hermes-audit`).
- **Rules** — see `~/.claude/rules/`. These are mandatory checks the
  orchestrator must enforce before reporting a task complete.

## Default behavior

1. On a non-trivial task, the chief orchestrator routes to the right
   specialists rather than answering directly.
2. Repo inspection precedes code change. No edits to files not yet read.
3. Validation precedes any "done" / "ready" claim.
4. Owner-only blockers are listed separately from code-side blockers.
5. Secrets are never printed; reference them by environment variable name.

## Project-local override

If the repository contains its own `CLAUDE.md` or `AGENTS.md`, treat it as
overriding this global layer **for matters specific to that project** (build
commands, test commands, code style, deployment). The Hermes operating contract
(honesty, scoping, validation-before-claim, owner-blocker separation) is not
overridable by a project file.
