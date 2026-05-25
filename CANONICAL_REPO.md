# Canonical Repository for JARVIS Prime

## Status

**`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` is the canonical source of truth for the JARVIS Prime runtime.**

All future JARVIS Prime runtime work — code under `hermes_cli/jarvis_prime/`, the operating-system doc set under `docs/jarvis-*.md`, the JARVIS skill packs under `skills/jarvis-*/`, and the JARVIS test surface under `tests/jarvis_prime/` — branches from this repo's `main` and merges back into this repo's `main` after the integration and review waves complete.

`echerd27-design/hermes-agent` is treated as a **legacy / spec mirror**. It may continue to receive personal-fork edits and historical content, but no JARVIS runtime change should be authored there in parallel with active ACI work unless an intentional sync has been declared in advance.

No one should edit multiple Hermes/JARVIS repositories in parallel without first declaring which repository is canonical for that change. Drift between forks is the failure mode this document exists to prevent.

## Branching Discipline

- **Do not edit `main` directly** in either repo.
- All JARVIS Prime runtime work branches from `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` `main`.
- Each wave of work and each feature lane gets its own branch (see `docs/jarvis-prime-wave-plan.md`).
- Feature branches merge into the integration branch first (`integration/jarvis-prime-runtime`), not into `main`.
- `main` merges in this canonical repo are **owner-gated** (see Owner Gates below).

## Worker Roles

- **Claude Code** is the primary builder. Claude Code authors implementation, refactors, and tests within its assigned branch.
- **Codex** is the reviewer, bounded fix worker, refactorer, and second-pass engineer. Codex operates on its own branch or on a clearly handed-off branch — never simultaneously with Claude on the same branch.
- Claude Code and Codex **must not edit the same branch at the same time**. Hand-offs are explicit: the previous worker pushes, declares done, and only then does the next worker check out.

## Owner Gates

The following actions require explicit owner authorization with the exact phrase `Yes, with authorization.` before they may be performed:

- Merges to `main` in either repository.
- Deploys to any environment (production, staging, preview).
- Package publishing (PyPI, npm, container registries, etc.).
- App store or distribution submissions.
- DNS changes.
- Credential, token, secret, or OAuth changes.
- Public posting (social, blog, marketing, partner channels).
- Spending money.
- Force-pushes to shared branches.
- Destructive git operations on shared branches (`reset --hard`, branch deletion, history rewrite).
- Any change to the legal, compliance, security, health, financial, or other regulated surface.

If an owner-gated action is required, the work packet records the action as data and stops short of execution until the authorization phrase is captured.

## Non-Goals For This Document

This document does not define the runtime architecture, the work-packet schema, or the wave plan. Those live in:

- `docs/jarvis-prime-operating-system.md` — operating contract, modes, routing, memory and verification rules.
- `docs/jarvis-prime-wave-plan.md` — wave build strategy and per-wave rules.
- `hermes_cli/jarvis_prime/work_packet.py` — standard work-packet data contract.

This document only fixes which repository is canonical and which actions are owner-gated, so that parallel forks and parallel workers do not silently diverge.
