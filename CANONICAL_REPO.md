# Canonical Repository — JARVIS Prime Runtime

This document declares the canonical source of truth for the JARVIS
Prime runtime and the coordination rules every contributor (human or
agent) must follow before editing.

## Canonical repository

**`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` is the canonical
source of truth for the JARVIS Prime runtime.**

All JARVIS Prime runtime code lives under
[`hermes_cli/jarvis_prime/`](hermes_cli/jarvis_prime/) in this repo.
Specifications live under [`docs/`](docs/) (notably
[`docs/jarvis-prime-operating-system.md`](docs/jarvis-prime-operating-system.md)
and [`docs/jarvis-verification-gates.md`](docs/jarvis-verification-gates.md))
and the activation skill at
[`skills/jarvis-prime/SKILL.md`](skills/jarvis-prime/SKILL.md).

`echerd27-design/hermes-agent` is a **legacy / spec mirror**. Treat it
as read-only with respect to JARVIS Prime runtime work unless a sync
from ACI → echerd27-design has been intentionally scheduled. Do not
develop new JARVIS Prime features there.

## Branching and main

- **Do not edit `main` directly in either repo.**
- All future JARVIS Prime runtime work branches from `main` of
  `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`.
- Pull requests target the integration branch (see
  [`docs/jarvis-prime-wave-plan.md`](docs/jarvis-prime-wave-plan.md))
  before being considered for `main`.
- Main merges are **owner-gated** and require the exact phrase
  `Yes, with authorization.` from the owner.

## Cross-repo coordination rule

**Nobody edits multiple Hermes / JARVIS repos in parallel without
declaring which repo is canonical for the change.**

If a change must land in both repos, declare which repo is canonical
for that change up-front, land it there first, then mirror. Do not
let two repos drift in parallel — the merge cost is paid by whoever
notices the drift last.

## Agent roles

| Agent | Role | Allowed |
|---|---|---|
| Claude Code | Primary builder | Implement features, write tests, run verification, draft PRs |
| Codex | Reviewer / bounded fix worker / refactorer / second-pass engineer | Review PRs, apply scoped fixes when explicitly delegated, refactor on its own branch |
| Owner (Jeremiah Echerd) | Decides, authorizes, merges to `main` | Owner-gated actions |

**Claude Code and Codex must not edit the same branch at the same
time.** If both are needed on the same area, sequence them: Claude
finishes and pushes, then Codex starts from that commit on its own
branch.

## Owner-gated actions

The following actions require the exact authorization phrase
`Yes, with authorization.` before they may be executed:

- Merging anything to `main` in either repo.
- Deployments (production, staging that is publicly visible, etc.).
- Package publishing (PyPI, npm, mobile app stores, etc.).
- App store submissions (Play Store, App Store).
- DNS changes.
- Credential / secret changes (rotating, adding, removing keys).
- Public posting (social media, blog, public GitHub Discussions).
- Spending money (API top-ups, new SaaS subscriptions, paid models).
- Force-push, history rewrites, branch deletion of shared branches.
- Any other destructive operation on shared state.

The canonical list lives in
[`hermes_cli/jarvis_prime/owner_auth.py`](hermes_cli/jarvis_prime/owner_auth.py)
(`OWNER_GATED_ACTIONS`). Extend the source-of-truth list there before
performing a new category of gated action — never in an ad-hoc PR.

## Cheat sheet (before editing)

1. Confirm you are in `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`.
2. Confirm you are on the correct feature branch — never `main`.
3. Confirm no other agent is editing the same branch.
4. Inspect existing JARVIS Prime files before creating new ones.
5. Keep import-time dependencies stdlib-only for JARVIS Prime
   runtime files (Termux compatibility).
6. Do not claim work is done without verification evidence.
7. Owner-gated actions stay queued until the owner replies
   `Yes, with authorization.`.

## Related docs

- [`docs/jarvis-prime-operating-system.md`](docs/jarvis-prime-operating-system.md)
- [`docs/jarvis-verification-gates.md`](docs/jarvis-verification-gates.md)
- [`docs/jarvis-prime-wave-plan.md`](docs/jarvis-prime-wave-plan.md)
- [`skills/jarvis-prime/SKILL.md`](skills/jarvis-prime/SKILL.md)
- [`AGENTS.md`](AGENTS.md)
- [`CLAUDE.md`](CLAUDE.md)
