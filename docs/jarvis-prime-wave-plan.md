# JARVIS Prime — Wave Build Plan

This document defines how parallel work on JARVIS Prime is sequenced
so that the foundation is locked **before** parallel feature lanes
open, so that two workers never edit the same branch concurrently,
and so that no change reaches `main` without owner approval and
verification evidence.

Companion documents:

- `CANONICAL_REPO.md` — declares ACI as the canonical source.
- `docs/jarvis-prime-operating-system.md` — the operating spec.
- `docs/jarvis-verification-gates.md` — the eight gates.
- `hermes_cli/jarvis_prime/` — the runtime each Wave builds on.

## The waves at a glance

| Wave | Purpose                        | Branch shape                       |
| ---- | ------------------------------ | ---------------------------------- |
| 0    | Foundation lock                | `feature/jarvis-foundation-lock`   |
| 1    | Parallel feature lanes         | one `feature/<lane>` per lane      |
| 2    | Integration                    | `integration/jarvis-prime-runtime` |
| 3    | Codex independent review       | review-only, no branch mutation    |
| 4    | Owner-approved merge to `main` | PR into `main`                     |

## Wave 0 — Foundation lock

**Branch:** `feature/jarvis-foundation-lock`

**Goal:** make the repo safe, canonical, structured, and ready
for later granular parallel feature branches. Nothing about runtime
behavior changes. This Wave only adds the contract every later Wave
will write against.

Wave 0 must deliver:

1. `CANONICAL_REPO.md` declaring ACI as canonical and clarifying
   the legacy status of `echerd27-design/hermes-agent`.
2. This document (`docs/jarvis-prime-wave-plan.md`).
3. `hermes_cli/jarvis_prime/work_packet.py` — the standard
   `WorkPacket` dataclass plus a `validate()` that reports missing
   or invalid fields.
4. `hermes_cli/jarvis_prime/__init__.py` updated to export
   `WorkPacket` (and any companion validation type) without breaking
   the existing public surface.
5. Baseline tests under `tests/jarvis_prime/` that cover:
   - WorkPacket creation
   - serialization via `to_dict()`
   - reconstruction via `from_dict()` if implemented
   - validation passes on a complete packet
   - validation reports missing required fields
   - `confidence` outside `[0.0, 1.0]` is handled safely
   - invalid `risk_class` is reported
   - `owner_gated_actions` are retained as data, not executed
   - `hermes_cli.jarvis_prime` imports successfully

Wave 0 must **not** deliver any of the items listed under Wave 1.

**Exit criteria:** Wave 0 PR is open, baseline tests pass, the
owner has approved the merge. Wave 1 starts only after Wave 0
merges to `main`.

## Wave 1 — Parallel feature lanes

Each lane runs on its own branch off `main` (post-Wave-0). Lanes
must not edit each other's primary modules. Where two lanes share a
runtime file, they coordinate via owner-arbitrated hand-off, not by
editing the file concurrently.

| Lane                                  | Branch suggestion                          |
| ------------------------------------- | ------------------------------------------ |
| Semantic immune layer                 | `feature/jarvis-semantic-immune-layer`     |
| Runtime enforcement                   | `feature/jarvis-runtime-enforcement`       |
| CLI expansion                         | `feature/jarvis-cli-expansion`             |
| Memory / self-improvement persistence | `feature/jarvis-memory-self-improvement`   |
| Mobile / focused mode                 | `feature/jarvis-mobile-focused-mode`       |
| Test suite                            | `feature/jarvis-test-suite`                |

Each lane must:

- Branch from the latest `main` after Wave 0 merges.
- Stay scoped to its lane.
- Use the `WorkPacket` contract from Wave 0 for every job it
  produces.
- Run the eight verification gates from
  `docs/jarvis-verification-gates.md` before declaring work
  "done".
- Provide verification evidence (test output, command transcripts,
  diff summary) on every PR.

## Wave 2 — Integration

**Branch:** `integration/jarvis-prime-runtime`

Merge each Wave 1 feature branch into the integration branch one at
a time. Resolve cross-lane conflicts on the integration branch, not
on `main`. Re-run the full test suite after each merge. Do not open
the next Wave 1 merge into integration until the previous one is
green.

Integration is **not** owner-gated, but the merge **into** `main`
in Wave 4 is.

## Wave 3 — Codex independent review

Codex performs an independent review of the integration branch.

- Codex does not mutate the integration branch directly.
- Codex may open bounded-fix PRs against the integration branch
  for specific findings.
- Claude Code does not edit the integration branch while Codex is
  reviewing it.
- The owner arbitrates disagreements between reviewers.

## Wave 4 — Owner-approved merge to `main`

Only the owner approves the merge of
`integration/jarvis-prime-runtime` into `main`. JARVIS Prime
prepares the PR, runs the gates, and waits. No worker merges to
`main` autonomously.

The merge requires:

1. Green CI on the integration branch.
2. Resolved Codex review findings.
3. Verification evidence pasted in the PR body.
4. Owner reply containing the exact phrase
   `Yes, with authorization.`

## Cross-Wave rules

These rules apply to **every** Wave, not just one:

1. **Do not edit `main` directly.** Every change goes through a
   branch and a PR.
2. **Each feature lane gets its own branch.** No "kitchen sink"
   branches.
3. **Shared runtime files require extra caution.** Touching
   `hermes_cli/jarvis_prime/runtime.py`, `router.py`, `gates.py`,
   `owner_auth.py`, `memory.py`, or `__init__.py` requires the
   PR description to (a) name every other lane that might touch
   the same file, (b) explain why this lane needs to edit it now,
   and (c) propose a hand-off plan if another lane is already
   editing it.
4. **Claude Code and Codex never edit the same branch at the same
   time.** One worker per branch. Hand-offs are explicit and
   journaled.
5. **All feature branches merge into the integration branch first.**
   No feature branch goes directly to `main`.
6. **Main merge requires owner approval.** The exact phrase
   `Yes, with authorization.` is the only acceptable trigger.
7. **No `done` claim without verification evidence.** Every PR
   that claims to be ready to merge must include the commands
   that were run and their output (test results, type-check
   results, lint results, smoke runs).
8. **Owner-gated actions stay gated.** Deploy, package publish,
   app submission, DNS change, credential change, public posting,
   spending, and destructive operations are owner-gated regardless
   of which Wave is active.

## Common Wave 0 pitfalls to avoid

- Building Wave 1 features inside Wave 0. The Wave 0 branch is
  foundation only.
- Reintroducing pydantic, requests, or other heavy deps at import
  time. JARVIS Prime runtime is stdlib-only at import time.
- Breaking Termux compatibility. Termux is a first-class target.
- Creating a parallel JARVIS system instead of extending the
  existing one under `hermes_cli/jarvis_prime/`.
- Editing `main` because "it's just a doc change". No.
