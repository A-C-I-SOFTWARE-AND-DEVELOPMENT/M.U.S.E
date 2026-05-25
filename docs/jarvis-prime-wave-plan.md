# JARVIS Prime Wave Build Plan

## Purpose

JARVIS Prime is built in deliberate waves, not as a single sprint, so that
parallel work cannot stomp on the same runtime files and so that no
unverified or owner-gated change reaches `main` by accident.

This document defines the wave boundaries, the rules that apply to every
wave, and what each wave is and is not allowed to do.

The canonical repository for all of this work is
`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`. See `CANONICAL_REPO.md`.

## Standing Rules (apply to every wave)

1. Do not edit `main` directly.
2. Each feature lane gets its own branch. No "and while I was in there" edits to
   unrelated lanes.
3. Shared runtime files (`hermes_cli/jarvis_prime/__init__.py`,
   `runtime.py`, `router.py`, `modes.py`, `gates.py`, `memory.py`,
   `work_packet.py`) require extra caution: list the file in the work
   packet's `allowed_files`, explain in commit message why a shared file
   was touched, and avoid touching them from two lanes at the same time.
4. Claude Code and Codex must not edit the same branch at the same time.
   Hand-offs are explicit: the previous worker pushes, declares done, and
   only then does the next worker check out.
5. All feature branches merge into the integration branch first
   (`integration/jarvis-prime-runtime`), not directly into `main`.
6. Main merges in the canonical repo require owner approval with the
   exact phrase `Yes, with authorization.`.
7. No work may be called "done" without verification evidence: command
   run, expected output observed, or an explicit reason verification was
   skipped.
8. Risk class, allowed files, protected files, non-goals, acceptance
   criteria, and rollback plan belong in the work packet (see
   `hermes_cli/jarvis_prime/work_packet.py`).

## Wave 0 — Foundation Lock

**Status: in progress.**

Goal: make the repo safe, canonical, structured, and ready for the
parallel feature lanes that follow.

In scope:

- Canonical-repo documentation (`CANONICAL_REPO.md`).
- Wave build-strategy documentation (this file).
- Standard `WorkPacket` data contract under
  `hermes_cli/jarvis_prime/work_packet.py` (stdlib-only,
  Termux-compatible, no network).
- Export `WorkPacket` and its validation finding type from
  `hermes_cli.jarvis_prime`.
- Baseline tests for the work-packet model under
  `tests/jarvis_prime/`.

Out of scope (deferred to later waves):

- Semantic immune layer.
- Runtime enforcement changes.
- CLI expansion.
- Memory / self-improvement persistence beyond the data contract.
- Mobile / focused mode runtime.
- Real Claude / Codex dispatch.
- GitHub publishing automation.
- Deployment automation.

## Wave 1 — Parallel Feature Lanes

Goal: build the runtime concurrently, one lane per branch, against the
foundation locked in Wave 0.

Lanes (each gets its own branch under `feature/jarvis-*`):

- Semantic immune layer — classification, intent guarding, refusal
  envelope.
- Runtime enforcement — gates, owner-authorization phrase capture,
  verification-gate plumbing.
- CLI expansion — `python -m hermes_cli.jarvis_prime ...` subcommands,
  packet introspection, dry-run handoffs.
- Memory / self-improvement persistence — durable decisions, lessons,
  routing improvements; no secrets, no temporary emotions.
- Mobile / focused mode — short-form mobile responses, deferred risky
  work, focused-mode expansion.
- Test suite — broader coverage for routing, modes, gates, memory rules,
  and verification gates.

Lane rules:

- Each lane declares its `allowed_files` and `protected_files` in the
  branch's first work packet.
- A lane that needs to touch a shared runtime file must coordinate
  before pushing; do not race other lanes on shared files.
- Each lane provides its own tests under `tests/jarvis_prime/<lane>/`
  or extends the existing module.

## Wave 2 — Integration

Goal: bring the Wave 1 lanes together on a single integration branch and
prove they cooperate.

- Integration branch: `integration/jarvis-prime-runtime`.
- Each Wave 1 feature branch merges into the integration branch in a
  controlled order, with the test suite run after each merge.
- Conflicts on shared runtime files are resolved on the integration
  branch, not on lane branches.
- No deploys, no publishing, no public posting from this branch.

## Wave 3 — Codex Independent Review

Goal: independent second-pass review of the integrated runtime.

- Codex reviews `integration/jarvis-prime-runtime` (or a review-only
  branch cut from it).
- Codex may push bounded fixes on its own branch and propose them back
  to the integration branch as PRs.
- Claude Code does not edit the integration branch during this wave.

## Wave 4 — Owner-Approved `main` Merge

Goal: land the reviewed, tested runtime on `main` in the canonical repo
with owner authorization recorded.

- Merge to `main` requires the exact phrase `Yes, with authorization.`
  captured against the merge work packet.
- Tag and release work is itself owner-gated.
- No deploys, package publishing, app submissions, DNS changes,
  credential changes, public posting, spending, or destructive
  operations happen as a side effect of the merge — those are separate
  owner-gated actions per `CANONICAL_REPO.md`.

## Wave Transition Checklist

Before declaring a wave complete:

- All in-scope deliverables for the wave exist in the repo.
- Verification evidence is recorded (commands run, outputs observed, or
  explicit skip reasons).
- No out-of-scope work was performed.
- The next wave's entry conditions are met (canonical repo set,
  foundation files present, integration branch available, etc.).
- The recommended next branch is named in the handoff.
