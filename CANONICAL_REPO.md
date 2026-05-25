# Canonical Repository Declaration — JARVIS Prime

This document is the single, authoritative answer to the question
"which repo is real?" for everything JARVIS Prime touches.

## Canonical source of truth

**`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`** is the canonical
source of truth for the JARVIS Prime runtime and every dependency
required to operate it.

- The JARVIS Prime runtime (`hermes_cli/jarvis_prime/`) lives here.
- The verification gates (`docs/jarvis-verification-gates.md`) live
  here.
- The operating-system spec
  (`docs/jarvis-prime-operating-system.md`) lives here.
- The activation skill (`skills/jarvis-prime/SKILL.md`) lives here.
- The Wave build plan (`docs/jarvis-prime-wave-plan.md`) lives here.

If two repositories ever disagree, this one wins.

## Legacy / mirror repository

**`echerd27-design/hermes-agent`** is treated as a legacy spec mirror.

- It may contain earlier drafts, prototype branches, and historical
  context from before the ACI fork was created.
- It **must not** be edited as a parallel canonical source.
- Changes flow **into** it from ACI, not the other way around, and
  only when an owner explicitly requests a sync.

If a contributor needs to inspect echerd27-design for historical
reference, that is fine. Editing it in parallel with ACI is not.

## Branching rules

1. **Do not edit `main` directly.** All work happens on a branch.
2. **All future JARVIS runtime work branches from ACI `main`.** Not
   from a feature branch, not from a legacy mirror. Branch from the
   tip of `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent@main`.
3. **No parallel canonical work across repositories.** Before
   starting work, declare which repo is canonical for the task
   (this one) and stay there. If a task must cross repos, an owner
   approves the cross-repo plan first.
4. **Feature lanes live on their own branches.** See
   `docs/jarvis-prime-wave-plan.md` for the Wave-by-Wave plan and
   the per-lane branch names.
5. **Claude Code and Codex never edit the same branch at the same
   time.** One worker per branch. Hand-off is explicit.

## Worker responsibilities

| Worker      | Role                                          |
| ----------- | --------------------------------------------- |
| Claude Code | Primary builder. Implements features and       |
|             | refactors. Owns first-pass quality.            |
| Codex       | Reviewer, bounded fix worker, refactorer, or  |
|             | second-pass engineer. Does **not** initiate    |
|             | net-new features without owner direction.      |
| Owner       | Approves merges to `main`. Authorizes          |
|             | owner-gated actions. Sets direction.           |

These responsibilities mirror the routing model documented in
`docs/jarvis-prime-operating-system.md` and the routing rules in
`docs/aos-jarvis-agent-routing.md`. JARVIS Prime is the orchestrator
that decides which worker handles which packet; this file just
declares the canonical surface they operate on.

## Owner-gated actions

The following actions require explicit owner authorization. JARVIS
Prime will prepare them but **must not execute** them until the
owner replies with the exact phrase:

> Yes, with authorization.

Owner-gated actions include (non-exhaustive, see
`hermes_cli/jarvis_prime/owner_auth.py::OWNER_GATED_ACTIONS` for the
authoritative set):

- Merging any branch into `main`.
- Force-pushing to any shared branch.
- Deploying to production (any environment exposed beyond the
  owner's local machine).
- Publishing packages (PyPI, npm, Maven, Gradle, etc.).
- Submitting to app stores (Play Store, App Store, F-Droid, etc.).
- DNS changes.
- Credential, secret, or OAuth changes.
- Posting publicly on the owner's behalf (social, blog, GitHub
  Releases, etc.).
- Spending money or creating third-party accounts.
- Regulated claims (legal, compliance, security, health, financial).
- Destructive operations (mass delete, registry mutation, hard
  reset of shared branches, deletion of recovered sources).

If the owner has not authorized the action with the exact phrase,
the action is deferred. No exceptions, no paraphrases.

## What this file is not

- This file does **not** override `AGENTS.md`. Where this file is
  silent, `AGENTS.md` rules.
- This file does **not** replace the operating-system spec at
  `docs/jarvis-prime-operating-system.md`. It only declares which
  repo the spec applies to.
- This file does **not** authorize any owner-gated action. It only
  documents which actions are gated.

## Update policy

Edits to this file are themselves owner-gated. A worker may propose
changes, but the owner must approve before they merge to `main`.
