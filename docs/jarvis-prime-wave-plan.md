# JARVIS Prime — Wave Build Plan

Status: Active
Owner: Jeremiah Echerd
Canonical repo: `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`
Reference: `CANONICAL_REPO.md`, `docs/jarvis-prime-operating-system.md`

JARVIS Prime is built in waves. Each wave has a narrow scope, a single
authoritative branch, and explicit hand-off gates. Waves do not overlap.
A wave is not "done" without verification evidence.

## Wave 0 — Foundation Lock

Goal: Make the repository safe, canonical, structured, and ready for later
granular parallel feature branches.

In scope:

- Canonical repo declaration (`CANONICAL_REPO.md`).
- This wave plan document (`docs/jarvis-prime-wave-plan.md`).
- The `hermes_cli/jarvis_prime/` package skeleton and exports.
- The `WorkPacket` model and its validation contract
  (`hermes_cli/jarvis_prime/work_packet.py`).
- Baseline tests for the `WorkPacket` model
  (`tests/jarvis_prime/`).

Out of scope:

- Semantic immune layer.
- Runtime enforcement changes.
- CLI surface expansion.
- Proposal / self-improvement persistence.
- Mobile live mode.
- Real Claude Code or Codex dispatch wiring.
- GitHub publishing automation.
- Deployment automation.

## Wave 1 — Parallel Feature Lanes

Wave 1 begins only after Wave 0 is merged to `main` (owner-gated).

Each lane below gets its own feature branch. Two lanes never share a branch.
Claude Code and Codex never edit the same branch at the same time.

Lanes:

- **Semantic immune layer.** Classification, mode selection, prompt-injection
  resistance, and "do not silently agree" hardening.
- **Runtime enforcement.** Repo inspection, owner-gate enforcement, refusal
  paths, and verification gate wiring.
- **CLI expansion.** New `hermes jarvis ...` subcommands and arguments,
  surfaced through the existing `hermes_cli` entry points.
- **Memory / self-improvement persistence.** Durable lesson capture,
  decision ledger, and curated memory updates with redaction.
- **Mobile / focused mode.** Short-form mobile-voice responses, deferred
  long-form work, and resumable task packets.
- **Test suite.** Broader unit, integration, and contract tests for the
  JARVIS Prime runtime.

## Wave 2 — Integration

Goal: Merge all Wave 1 lanes into a single integration branch and resolve
cross-lane conflicts in isolation from `main`.

Integration branch: `integration/jarvis-prime-runtime`.

Rules:

- All Wave 1 feature branches merge into the integration branch first.
- Integration branch never merges to `main` without passing Wave 3 review.
- Integration runs the combined test suite and verification gates.

## Wave 3 — Codex Independent Review

Goal: Independent second-pass review of the integration branch by Codex.

Rules:

- Codex reads, comments, and may apply bounded fixes only when the change is
  scoped, low-risk, and within Codex's review remit.
- Codex does not edit any Wave 1 feature branch directly.
- Codex's findings are recorded in the integration branch's PR thread.
- If Codex requests a substantive change, it is applied on the originating
  lane branch and re-integrated, not patched in place.

## Wave 4 — Owner-Approved Main Merge

Goal: Merge the reviewed integration branch into `main` only after the owner
explicitly authorizes the merge.

Rules:

- The owner must respond with the exact phrase
  `Yes, with authorization.` before the merge runs.
- The merge commit message must reference the integration branch, the
  Wave 1 lanes, and the verification evidence.
- The merge is the only path by which JARVIS Prime runtime changes land on
  `main`.

## Cross-Wave Rules

- Do not edit `main` directly under any wave.
- Each feature lane gets its own branch.
- Shared runtime files (anything imported by more than one lane) require
  extra caution: a short note in the PR description explaining why the
  shared file had to be touched.
- Claude Code and Codex must not edit the same branch at the same time.
  Hand-off must be explicit.
- All feature branches merge into the integration branch first, never
  directly into `main`.
- Merging to `main` requires owner authorization with the exact phrase
  above.
- Work is not "done" without verification evidence. Verification evidence
  means: the commands that were run, the output observed, and whether the
  observed behavior matched the acceptance criteria.

## Verification Evidence Standard

For each wave, the worker reports:

1. Branch worked on.
2. Mission completed.
3. Files changed.
4. Tests run (exact commands).
5. Test results (pass / fail counts, failing test names if any).
6. Known risks.
7. Rollback plan.
8. Recommended next branch.

Missing items block hand-off.
