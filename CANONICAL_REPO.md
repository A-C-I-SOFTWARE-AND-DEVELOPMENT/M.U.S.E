# Canonical Repository Declaration — JARVIS Prime

This document is the single source of truth for **which Hermes repository
hosts the JARVIS Prime runtime**, who is allowed to edit it, and which
actions are owner-gated. Wave 0 of the JARVIS Prime build plan installs
this declaration before any parallel feature lanes open.

If two repositories diverge, **this document wins** and the runtime in
the canonical repo wins. Anyone who finds a conflict must reconcile it
back into the canonical repo, not the other way around.

## Canonical Repository

- **Canonical:**
  `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`
- **Legacy / spec mirror:**
  `echerd27-design/hermes-agent`

All future JARVIS Prime runtime work — code under
`hermes_cli/jarvis_prime/`, supporting tests under `tests/jarvis_prime/`,
runtime-affecting docs under `docs/jarvis-prime-*`, and skills under
`skills/jarvis-prime/` — branches from the canonical repo's `main`.

`echerd27-design/hermes-agent` may continue to hold historical work,
spec drafts, or reference material, but it is **not** authoritative for
the runtime and should not be edited as if it were unless an explicit,
declared sync is in progress (see "Cross-Repository Work" below).

## Branching Rules

1. **Never edit `main` directly.** Every change lands as a branch and a
   reviewed pull request against `main`.
2. Every JARVIS Prime change goes on a dedicated feature branch named
   for its lane (for example, `feature/jarvis-foundation-lock`,
   `feature/jarvis-semantic-immune`, `feature/jarvis-runtime-enforce`,
   `feature/jarvis-cli`, `feature/jarvis-memory-persistence`,
   `feature/jarvis-mobile-focused`, `feature/jarvis-tests`).
3. Feature lanes converge into an integration branch
   (`integration/jarvis-prime-runtime`) before any merge to `main`.
4. Merges to `main` are **owner-gated**.

## Roles

- **Claude Code** — primary builder. Implements features on a feature
  branch, runs local verification, and reports evidence in PR.
- **Codex** — reviewer, bounded fix worker, refactorer, or second-pass
  engineer. Operates on a separate branch from the builder.
- **AOS Council** — multi-perspective reasoning when judgment is needed
  (architecture, security, contrarian review, scope control).
- **Owner (Jeremiah Echerd)** — sole approver for owner-gated actions
  listed below.

### Concurrency Rule

**Claude Code and Codex must not edit the same branch at the same
time.** If both need to work on the same lane, sequence the work
(builder first, then reviewer on a follow-up branch) or fan the work
out onto separate branches and reconcile through the integration
branch.

## Owner-Gated Actions

The following actions are **owner-gated** and require the exact
authorization phrase before they can be performed:

```
Yes, with authorization.
```

Owner-gated actions include, but are not limited to:

- merging anything to `main`;
- deploys of any kind (Hermes, gateway, JARVIS surfaces);
- publishing or releasing a package (pip / PyPI, GitHub release, NPM,
  Homebrew, Termux, container registry, app store);
- DNS changes, domain transfers, MX/A record updates;
- credential, secret, or API-key changes (rotation, addition, removal);
- public posting on owner-owned channels (X/Twitter, blog, website,
  Discord, Slack workspaces beyond local dev, customer comms);
- spending money (paid APIs, paid infra, paid tools, ads, subscriptions);
- destructive operations (force-push to shared branches, rewriting
  shared history, deleting branches/tags, dropping data, `rm -rf`,
  schema deletes);
- any change to this `CANONICAL_REPO.md` document itself.

JARVIS Prime runtime code must **preserve owner-gated actions as data**
(for example, in a `WorkPacket.owner_gated_actions` field) — it must
**not execute** them.

## Cross-Repository Work

If, for any reason, work needs to land in the legacy mirror
(`echerd27-design/hermes-agent`) as well as the canonical repo, follow
this protocol:

1. Declare which repo is canonical for that change up front (default:
   ACI canonical).
2. Land the change in the canonical repo first, with full review.
3. Cherry-pick or mirror into the legacy repo as a separate, clearly
   labelled commit.
4. Never have an open feature lane in both repos editing the same
   runtime files at the same time.

Anyone working in two Hermes repos in parallel without declaring which
is canonical is in violation of this document.

## Why This Exists

JARVIS Prime is the owner's local-first AI operating partner. Without a
single canonical source of truth, parallel work in mirrored repos will
silently diverge — runtime files will conflict, tests will pass in one
repo and fail in the other, and review effort will be wasted
reconciling drift instead of building. Wave 0 locks this down before
the parallel feature lanes in Wave 1 open.
