# JARVIS Prime Wave Build Plan

This document describes the wave strategy used to bring JARVIS Prime to a
verified, owner-controlled main merge. Each wave has a defined scope, set of
branches, and exit criteria. Work that does not fit the current wave is
deferred — overbuilding a wave is treated the same as scope creep.

## Wave 0 — Foundation lock

**Goal:** make the repo safe, canonical, and structured before any parallel
feature work begins.

**Scope:**

- Canonical-repo documentation (`CANONICAL_REPO.md`).
- Wave plan and merge strategy (this document).
- Standard `WorkPacket` dataclass under `hermes_cli/jarvis_prime/work_packet.py`,
  stdlib-only, with `to_dict`, `from_dict`, and `validate`.
- Export `WorkPacket` from `hermes_cli/jarvis_prime/__init__.py`.
- Baseline tests under `tests/jarvis_prime/`.

**Branch:** `claude/jarvis-foundation-lock-g9i9x`.

**Exit criteria:**

- Documents present and accurate.
- `WorkPacket` importable and validating expected fields.
- Baseline tests pass locally.
- No runtime feature work merged into this branch.

## Wave 1 — Parallel feature lanes

**Goal:** bring up the JARVIS Prime runtime in parallel, one feature per
branch, each branch isolated and small.

**Lanes (each gets its own feature branch off `main`):**

- `feature/jarvis-semantic-immune-layer` — input classification, prompt
  injection / scope-creep filtering, soft refusal scaffolding.
- `feature/jarvis-runtime-enforcement` — gate enforcement, owner-auth phrase
  matching, owner-gated action dispatcher (deferred execution only).
- `feature/jarvis-cli-expansion` — `python -m hermes_cli.jarvis_prime` real
  CLI surface (subcommands, help, modes).
- `feature/jarvis-memory-self-improvement` — proposal persistence, durable
  lesson storage, memory pruning rules.
- `feature/jarvis-mobile-focused-mode` — short-response mobile mode, deferred
  long-form output for focused desktop mode.
- `feature/jarvis-test-suite` — broader test coverage layered on the Wave 0
  baseline (router, modes, gates, memory).

**Rules during Wave 1:**

- One lane = one branch. No mixing.
- Each lane branches from `main`, not from another feature lane.
- Shared runtime files (anything imported by more than one lane) require an
  explicit note in the PR description explaining why the change is needed
  and how it stays backward-compatible.
- Claude Code and Codex do not edit the same lane branch simultaneously.
  Ownership of a lane is recorded in the PR; handoffs are explicit.
- No lane may declare itself done without verification evidence (tests run,
  output captured, behavior described).

## Wave 2 — Integration

**Goal:** merge feature lanes into a single integration branch and resolve
cross-lane interactions.

**Branch:** `integration/jarvis-prime-runtime` (cut from latest `main`).

**Process:**

- Feature lanes merge into the integration branch in dependency order
  (semantic immune layer and runtime enforcement first, then memory, then
  CLI surface, then mobile mode, then test suite).
- Integration owner runs the full test suite on the integration branch.
- Conflicts are resolved on the integration branch, not on lane branches.
- No lane branch is deleted until after integration is verified.

## Wave 3 — Codex independent review

**Goal:** independent second-pass review by Codex on the integration branch.

- Codex reviews the diff between `main` and the integration branch.
- Findings are filed as PR comments or as bounded-fix branches off the
  integration branch.
- Bounded fixes merge back into the integration branch via PR.
- Claude Code does not edit the integration branch during the Codex review
  window.

## Wave 4 — Owner-approved main merge

**Goal:** ship to `main` with explicit owner authorization.

- Owner reviews the integration branch.
- Owner provides the exact phrase `Yes, with authorization.` to authorize
  the merge.
- Merge happens via PR; no force-push, no direct push to `main`.
- Post-merge: tag a checkpoint, archive the integration branch, retire the
  feature lane branches.

## Documented rules (all waves)

- Do not edit `main` directly.
- Each feature lane gets its own branch.
- Shared runtime files require extra caution and an explicit PR note.
- Claude Code and Codex must not edit the same branch at the same time.
- All feature branches merge into the integration branch before `main`.
- `main` merge requires owner approval.
- No "done" claim without verification evidence (commands run, results
  captured, behavior described).
- Owner-gated actions require the exact phrase `Yes, with authorization.`
  (see `CANONICAL_REPO.md` for the full list).
