# Canonical Repo Declaration for JARVIS Prime

This document establishes which repository owns the canonical runtime
for JARVIS Prime and how parallel repository work must be coordinated.
It is part of the Wave 0 foundation lock and supersedes any earlier
implicit convention.

## Canonical source of truth

`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` is the canonical source of
truth for the JARVIS Prime runtime.

All JARVIS Prime runtime files — including but not limited to the
`hermes_cli/jarvis_prime/` package, its supporting docs under `docs/`,
the `skills/jarvis-prime/` skill, the `skills/jarvis-code-operator/`
skill, the wave plan in `docs/jarvis-prime-wave-plan.md`, and any
tests under `tests/jarvis_prime/` — are owned here.

## Legacy mirror

`echerd27-design/hermes-agent` is treated as a legacy / spec mirror.
It may carry older drafts or design-time notes that have not yet been
promoted into the canonical repo. Treat it as read-only context unless
a deliberate sync has been planned and announced. Do not assume that
a file in the mirror is current, and do not edit both repos in the
same change without first declaring which one is canonical for that
change.

## Branching policy

* All future JARVIS Prime runtime work branches from
  `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` `main`.
* Do not edit `main` directly.
* Do not edit multiple Hermes/JARVIS repositories in parallel without
  declaring which repo is canonical for that change. If a change must
  land in both, land it here first, then port.

## Worker assignments

* Claude Code is the primary builder for JARVIS Prime runtime changes.
* Codex is the reviewer, bounded fix worker, refactorer, and
  second-pass engineer. Codex must not edit a branch that Claude Code
  is actively editing.
* Claude Code and Codex must not edit the same branch at the same
  time. Coordinate handoff explicitly.

## Owner-gated actions

The following actions require explicit owner authorization with the
exact phrase `Yes, with authorization.` before they are executed:

* Merging into `main`.
* Production deploys.
* Package publishing (PyPI, npm, etc.).
* App-store submissions.
* DNS changes.
* Credential, token, OAuth, or secret changes.
* Public posting (social, blog, public PR comments outside this repo,
  etc.).
* Spending money or creating paid third-party accounts.
* Destructive repository operations: force-push to shared branches,
  history rewrites, branch deletions of shared branches, mass file
  deletions outside the declared `allowed_files`.

Owner authorization stands for the scope it was granted for. It is not
a blanket approval for future actions of the same kind.

## Verification before "done"

No work is "done" until verification evidence has been recorded. For
runtime changes, that means at minimum:

* Tests run with results captured.
* Diff reviewed.
* Rollback plan documented in the PR or WorkPacket.

If verification cannot be produced, the change is not done — it is
"awaiting verification" and must be labeled as such.
