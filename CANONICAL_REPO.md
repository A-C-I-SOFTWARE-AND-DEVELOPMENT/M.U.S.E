# Canonical Repository Declaration — JARVIS Prime

Status: Active
Owner: Jeremiah Echerd
Last updated: 2026-05-25
Wave: Wave 0 (Foundation Lock)

## Source of Truth

`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` is the **canonical source of
truth** for the JARVIS Prime runtime, its supporting documentation, and the
wave-based build plan.

All future JARVIS Prime runtime work must branch from `main` of this
repository (`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`).

## Mirror Repository

`echerd27-design/hermes-agent` should be treated as a **legacy / spec mirror**.
It may carry historical drafts, earlier exploration, or spec material.

The mirror is **not** the source of truth for runtime code. It may only be
synced when:

- the owner explicitly authorizes a sync, and
- the direction of the sync is declared in writing (ACI → mirror, or
  mirror → ACI), and
- the sync is documented in the commit message that performs it.

Default assumption: do not edit the mirror in parallel with the canonical
repo. If a divergence is discovered, the canonical repo wins unless the
owner says otherwise.

## Parallel Repository Rule

Do not edit multiple Hermes / JARVIS repositories in parallel without first
declaring, in the active task description, which repository is canonical for
that change. Parallel edits across repositories without a canonical
declaration are considered destructive and require owner authorization.

## Builder / Reviewer Roles

- **Claude Code** is the primary builder. It implements scoped changes on
  feature branches.
- **Codex** is the reviewer, bounded fix worker, refactorer, and second-pass
  engineer. It may not edit the same branch as Claude Code at the same time.
- A single feature branch is owned by exactly one of {Claude Code, Codex} at a
  time. Hand-off must be explicit.

## Owner-Gated Actions

The following actions require the exact owner authorization phrase
`Yes, with authorization.` before they may be performed. Without that phrase,
the worker stops and asks.

- Merging any branch into `main`.
- Deploys of any kind (preview, staging, production).
- Package publishing (PyPI, npm, Homebrew, app stores, container registries).
- App store submissions.
- DNS changes.
- Credential, secret, or OAuth changes.
- Public posting (social, blog, GitHub Discussions, press).
- Spending money or signing up for paid services.
- Destructive git operations (force push, history rewrite, branch deletion of
  shared branches).
- Destructive infrastructure operations (dropping tables, removing buckets,
  revoking keys in use).

## Non-Negotiable Rules

1. Do not edit `main` directly.
2. Use the explicitly assigned feature branch for the active wave / task.
3. Inspect the repo before making assumptions. Do not invent files, paths,
   commands, APIs, tests, or module names.
4. Do not call work done unless verification evidence is provided.
5. Keep JARVIS Prime runtime files stdlib-only at import time unless the
   repo already requires otherwise.
6. Preserve Termux compatibility.
7. Do not create duplicate JARVIS systems. Build on the existing
   `hermes_cli/jarvis_prime/` package and `skills/jarvis-prime/` skill.

## Pointers

- Runtime package: `hermes_cli/jarvis_prime/`
- Operating system spec: `docs/jarvis-prime-operating-system.md`
- Wave plan: `docs/jarvis-prime-wave-plan.md`
- Skill: `skills/jarvis-prime/SKILL.md`
