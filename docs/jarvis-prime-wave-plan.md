# JARVIS Prime Wave Build Plan

This document is part of the Wave 0 foundation lock. It records the
agreed sequence for building JARVIS Prime so that later parallel work
does not collide on shared runtime files.

## Wave 0: Foundation lock

Goal: make the repo safe, canonical, structured, and ready for later
granular parallel feature branches.

Scope:

* Declare the canonical repo (`CANONICAL_REPO.md`).
* Document this wave plan (`docs/jarvis-prime-wave-plan.md`).
* Create the `hermes_cli/jarvis_prime/` package with the standard
  `WorkPacket` model and a minimal `__main__` entry point.
* Add baseline tests under `tests/jarvis_prime/`.
* Export `WorkPacket` and `WorkPacketValidationFinding` from
  `hermes_cli.jarvis_prime`.

Out of scope for Wave 0: semantic immune layer, runtime enforcement
changes, CLI expansion, proposal persistence, mobile live mode, real
Claude/Codex dispatch, GitHub publishing automation, deployment
automation.

## Wave 1: Parallel feature lanes

Each lane gets its own feature branch off `main`. Lanes intentionally
do not share files; if they must, the shared file is owned by exactly
one lane and the others rebase onto it.

Lanes:

1. **Semantic immune layer** — classifier, allow/deny rules,
   trust scoring.
2. **Runtime enforcement** — gates, owner-auth checks, dispatch
   guards, allowed/protected file enforcement.
3. **CLI expansion** — `python -m hermes_cli.jarvis_prime`
   subcommands (`route`, `validate`, `inspect`, etc.).
4. **Memory / self-improvement persistence** — durable lesson store,
   proposal log, retrospective hooks.
5. **Mobile / focused mode** — short-form mobile responses,
   focused-mode expansion.
6. **Test suite** — broader coverage including router, gates,
   memory, and CLI surfaces.

## Wave 2: Integration branch

All Wave 1 feature branches merge into a single integration branch:

```
integration/jarvis-prime-runtime
```

Integration is where conflicts between lanes are resolved. Direct
merges from feature branches to `main` are not allowed.

## Wave 3: Codex independent review

Codex reviews the integration branch end-to-end:

* Independent diff review against the wave plan and acceptance
  criteria.
* Bounded fixes only — no scope expansion.
* Surfaces risks, regressions, and any missing verification.

While Codex is reviewing, Claude Code does not edit the same branch.

## Wave 4: Owner-approved main merge

`main` merges happen only after explicit owner approval recorded as:

```
Yes, with authorization.
```

Owner approval is per-merge, not standing.

## Rules

* Do not edit `main` directly.
* Each feature lane gets its own branch off `main`.
* Shared runtime files (anything under `hermes_cli/jarvis_prime/`)
  require extra caution — call out the shared file in the PR and the
  WorkPacket.
* Claude Code and Codex must not edit the same branch at the same
  time.
* All feature branches merge into the integration branch first, never
  straight to `main`.
* Main merges require owner approval (`Yes, with authorization.`).
* No "done" claim without verification evidence (tests run, diff
  reviewed, rollback plan documented).
