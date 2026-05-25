# JARVIS Prime Wave Plan

This document describes how JARVIS Prime is being built out in waves,
which work belongs in which wave, and the rules every wave must
follow.

It is the companion to `CANONICAL_REPO.md` at the repo root, which
declares the canonical repository and ownership rules. Read that file
first if you have not.

---

## Why waves

JARVIS Prime is the owner's local-first operating partner. Building it
in one giant branch invites overlapping edits, conflicting assumptions,
and "done" claims that never actually got verified. Waves keep the
work parallelizable where it is safe, and serialized where it is not.

The wave plan also makes it explicit which wave a given change belongs
to, so reviewers can reject scope creep early instead of after the fact.

## Wave 0 — Foundation Lock (this branch)

Goal: make the repo safe, canonical, structured, and ready for the
parallel feature lanes in Wave 1.

In scope:

- Canonical repo declaration (`CANONICAL_REPO.md`).
- Wave plan (this document).
- Standard `WorkPacket` data model and validation
  (`hermes_cli/jarvis_prime/work_packet.py`).
- Package export of `WorkPacket` from `hermes_cli.jarvis_prime`.
- Baseline tests under `tests/jarvis_prime/` that exercise the
  `WorkPacket` model and the package import surface.

Out of scope (defer to later waves):

- semantic immune layer
- runtime enforcement changes
- CLI expansion (new `hermes jarvis ...` subcommands)
- proposal / self-update persistence
- mobile live mode
- real Claude / Codex dispatch
- GitHub publishing automation
- deployment automation

Exit criteria: branch is mergeable into a Wave 1 integration target,
import surface is stable, tests pass locally.

## Wave 1 — Parallel feature lanes

Each lane gets its own branch off ACI `main`. Lanes are designed so
they do not contend for the same files.

Lanes:

- **semantic-immune-layer** — request classification, prompt-injection
  detection, refusal policy, allow / deny lists.
- **runtime-enforcement** — gates, owner-auth checks, risk-class
  routing, dry-run vs execute discipline.
- **cli-expansion** — `hermes jarvis ...` surface, mode flags, mobile
  vs focused output shaping.
- **memory-self-improvement-persistence** — durable lesson store,
  proposal persistence, self-update queue (data only; no auto-apply).
- **mobile-focused-mode** — short-form mobile/voice replies, deferred
  long output, focused-mode expansion.
- **test-suite** — broader coverage for runtime, gates, memory, and
  mode routing.

Lane rules (all lanes):

- Branch from ACI `main`. Do not branch from another in-flight lane.
- Each lane has one driving editor (Claude Code **or** Codex, not
  both, at a time) until the lane is paused or handed off in writing.
- Lanes must not edit each other's primary files. Shared runtime
  files (the `WorkPacket` model, package `__init__`, anything in
  `hermes_cli/jarvis_prime/runtime.py` once it exists) require extra
  caution and an explicit note in the PR description.

## Wave 2 — Integration

A dedicated integration branch combines the Wave 1 lanes:

```text
integration/jarvis-prime-runtime
```

Rules:

- Lanes merge into the integration branch **first**, not into `main`.
- Integration owner resolves cross-lane conflicts and re-runs the full
  test suite. Lane authors do not silently rewrite each other's code
  during integration.
- Anything that cannot be reconciled cleanly is bounced back to its
  lane for a fix; it is not papered over inside the integration
  branch.

## Wave 3 — Independent review

Codex performs an independent review of the integration branch.

- Codex is the reviewer here, not the author. It must not have been
  the primary editor on the lanes it is reviewing.
- Review output: findings list, severity, suggested fixes, and a
  clear pass / hold recommendation.
- Owner decides which findings block merge and which are deferred.

## Wave 4 — Owner-approved main merge

The integration branch merges into `main` **only** after:

- Wave 3 review is complete.
- All blocking findings are resolved.
- Owner replies with the exact authorization phrase:
  `Yes, with authorization.`

## Rules that apply to every wave

1. Do not edit `main` directly.
2. Each feature lane gets its own branch.
3. Shared runtime files require extra caution and an explicit PR
   note describing why the change touches them.
4. Claude Code and Codex must not edit the same branch at the same
   time.
5. All feature branches merge into the integration branch first, not
   into `main`.
6. Main merges are owner-gated. So are deploys, package publishing,
   app submissions, DNS changes, credential changes, public posting,
   spending, and destructive git operations.
7. No "done" claim without verification evidence — the commands run,
   the actual output, the files changed, and a rollback note.
