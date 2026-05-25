# Canonical Repo — JARVIS Prime Runtime

This document declares the single source of truth for JARVIS Prime
runtime work and the rules that govern parallel forks.

## Canonical source of truth

**`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` is the canonical
repository for JARVIS Prime runtime.**

All new runtime code, tests, gates, and skill files for JARVIS Prime
land here first. The package path is `hermes_cli/jarvis_prime/` and
the activation skill lives at `skills/jarvis-prime/SKILL.md`.

## Mirror / legacy fork

**`echerd27-design/hermes-agent` is treated as a legacy / spec mirror
unless intentionally synced.**

It may carry historical specs, design notes, and pre-fork artifacts.
Do not assume parity with the canonical repo. Any sync from the mirror
into the canonical repo (or vice versa) is an explicit, owner-approved
operation — never an implicit one.

## Branching rule

All future JARVIS Prime runtime work branches from
`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` `main`.

No one should edit multiple Hermes / JARVIS repos in parallel without
first declaring which repo is canonical for the change. Splitting
runtime edits across forks creates merge conflicts that destroy work
and erase test evidence.

## Implementer / reviewer roles

- **Claude Code** is the primary builder. It implements features,
  tests, and refactors against an open feature branch.
- **Codex** is the reviewer and bounded fix worker. It reviews diffs,
  applies tightly scoped fixes, and performs second-pass refactors —
  but does not edit the same branch concurrently with Claude.
- **The owner** (Jeremiah Echerd) approves merges to `main`, owner-gated
  actions, and any deviation from these rules.

Claude and Codex must **not** edit the same branch at the same time.
If both need to touch related work, sequence them on separate branches
that merge into the integration branch.

## Owner-gated operations

The following actions are owner-gated. They require the **exact phrase**
`Yes, with authorization.` from the owner before execution:

- merge to `main`
- production deploy
- package publish (PyPI, npm, app store)
- app store submission
- DNS change
- credential / secrets change
- OAuth change
- spending money
- public posting
- destructive operations (force push, history rewrite, mass delete)

These align with `OWNER_GATED_ACTIONS` in
`hermes_cli/jarvis_prime/owner_auth.py` and the spec in
`docs/jarvis-prime-operating-system.md`.

## What this document is not

- It is not a license — see `LICENSE`.
- It is not the contribution guide — see `CONTRIBUTING.md` and
  `AGENTS.md`.
- It is not the wave build plan — see
  `docs/jarvis-prime-wave-plan.md`.
- It is not the runtime spec — see
  `docs/jarvis-prime-operating-system.md`.
