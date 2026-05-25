# JARVIS Prime Build Plan — Waves 0 → 4

This document describes how JARVIS Prime is built in waves so that
parallel feature work does not collide on shared runtime files, and so
that no work reaches `main` without owner approval.

It is paired with [`CANONICAL_REPO.md`](../CANONICAL_REPO.md), which
declares which repo is canonical and which actions are owner-gated.
This document is concerned with **sequencing**: which wave does what,
which branch holds it, and what has to be true before the next wave can
begin.

## Branching Model

- Canonical repo: `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`.
- Default branch: `main`. **Never edited directly.**
- Each feature lane gets its own branch off the latest `main`.
- Feature lanes converge into the integration branch
  `integration/jarvis-prime-runtime` before any `main` merge.
- Merges to `main` require the owner's explicit authorization phrase:
  `Yes, with authorization.`

## Wave 0 — Foundation Lock

Branch: `feature/jarvis-foundation-lock`
(or the equivalent assigned branch — for example, the agent-assigned
`claude/jarvis-foundation-lock-*` branch — when running under a
managed harness).

Goal: make the repo safe, canonical, structured, and ready for the
parallel lanes that follow.

Scope:

- Canonical-repo declaration (`CANONICAL_REPO.md`).
- This wave-plan document.
- A standard `WorkPacket` dataclass at
  `hermes_cli/jarvis_prime/work_packet.py` (stdlib-only, no heavy
  imports at module load).
- Export `WorkPacket` (and its validation type) from
  `hermes_cli/jarvis_prime/__init__.py`.
- Baseline tests under `tests/jarvis_prime/`.

Out of scope (intentionally deferred):

- semantic immune layer
- runtime enforcement
- CLI expansion
- proposal / self-improvement persistence
- mobile / focused live mode
- real Claude / Codex dispatch
- GitHub publishing automation
- deployment automation

Exit criteria:

- All Wave 0 files exist on the foundation-lock branch.
- `hermes_cli.jarvis_prime` imports cleanly and exposes `WorkPacket`.
- `tests/jarvis_prime/` passes locally.
- Verification evidence (commands and outputs) is recorded in the PR.

## Wave 1 — Parallel Feature Lanes

Wave 1 opens once Wave 0 is merged into `main` (owner-gated). Each
lane is a separate branch, each owned by exactly one builder at a
time, and each pre-declares which files in `hermes_cli/jarvis_prime/`
it intends to touch.

Suggested lanes (names indicative, finalize at lane-kickoff time):

- `feature/jarvis-semantic-immune` — semantic immune layer (classify
  weak / dangerous / off-mission requests and route accordingly).
- `feature/jarvis-runtime-enforce` — runtime enforcement (verification
  gates, owner-gate refusal, file-scope respect).
- `feature/jarvis-cli` — CLI surface expansion (slash commands, mode
  classifier hooks, short mobile-mode responses).
- `feature/jarvis-memory-persistence` — durable memory and
  self-improvement persistence (lessons, decisions, proposals).
- `feature/jarvis-mobile-focused` — mobile / focused mode handling
  (short responses while moving, full depth at the desk).
- `feature/jarvis-tests` — broad test suite for runtime behavior.

Rules for Wave 1:

- One lane per builder; do not start a second lane in the same files.
- **Claude Code and Codex never edit the same branch concurrently.**
  If both are needed on the same lane, sequence: builder ships a
  branch, reviewer opens a follow-up branch.
- Any change touching a shared runtime file (anything other than the
  lane's own dedicated module) must explain why in the PR description.
- No lane merges to `main` directly. All lanes merge into the
  integration branch.

## Wave 2 — Integration

Branch: `integration/jarvis-prime-runtime`.

Goal: combine the Wave 1 lanes, resolve conflicts, run the full local
test suite, and produce a single reviewable surface.

Rules:

- Lanes merge into the integration branch in an order chosen at
  integration time (typically: enforcement and immune layer first,
  CLI and memory next, mobile/focused last).
- Conflicts are resolved on the integration branch, not on individual
  lanes (lanes stay tight to their own scope).
- The integration branch must pass `tests/jarvis_prime/` and the
  relevant existing Hermes tests before Wave 3 begins.

## Wave 3 — Codex Independent Review

Branch: `review/jarvis-prime-runtime` (or equivalent reviewer branch
off the integration branch).

Goal: independent review by Codex of the integrated runtime. Codex
operates in reviewer / bounded-fix mode — it does not co-edit the
integration branch with the builder.

Outputs:

- severity-ranked findings (blocking vs improvement);
- contrarian read of the strongest objection;
- proposed bounded fixes on a separate branch where appropriate.

## Wave 4 — Owner-Approved `main` Merge

Goal: merge the reviewed integration branch into `main`, behind the
owner authorization phrase.

Rules:

- The owner must explicitly approve with `Yes, with authorization.`
  before the merge proceeds.
- The PR description must include verification evidence (commands and
  outputs, not just "tests pass").
- Post-merge owner-gated actions (deploys, releases, public posting,
  DNS, credentials, spending) require their own authorization phrase
  per `CANONICAL_REPO.md`.

## Rules Summary

These rules apply across every wave:

1. **Do not edit `main` directly.**
2. **Each feature lane gets its own branch.**
3. **Shared runtime files require extra caution** — explain why in
   the PR if you touch them outside your lane.
4. **Claude Code and Codex never edit the same branch at the same
   time.**
5. **All feature branches merge into the integration branch first,
   not into `main`.**
6. **`main` merges require owner approval** with the exact phrase
   `Yes, with authorization.`.
7. **No "done" claim without verification evidence** — record the
   commands run and the actual results.
