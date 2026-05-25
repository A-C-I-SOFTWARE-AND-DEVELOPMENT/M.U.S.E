# JARVIS Prime Wave Plan

This document is the build strategy for the JARVIS Prime runtime inside
`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` (see `CANONICAL_REPO.md`).
It exists so that Claude Code, Codex, AOS Council agents, and the owner
all agree on what work happens in what order, on what branch, with what
gates.

Documentation only — no runtime behavior is defined here.

## Wave 0 — Foundation Lock (current wave)

Goal: make the repo safe, canonical, and structured before any parallel
feature work begins.

Scope:

- Canonical repo declaration (`CANONICAL_REPO.md`).
- Wave plan documentation (this file).
- Standard `WorkPacket` model at `hermes_cli/jarvis_prime/work_packet.py`
  with stdlib-only imports.
- Export of `WorkPacket` from `hermes_cli.jarvis_prime`.
- Baseline tests at `tests/jarvis_prime/` covering WorkPacket creation,
  serialization, validation, and import surface.

Out of scope for Wave 0:

- semantic immune layer;
- runtime enforcement changes;
- CLI expansion;
- proposal / self-improvement persistence;
- mobile live mode;
- real Claude / Codex dispatch;
- GitHub publishing automation;
- deployment automation.

Branch: `feature/jarvis-foundation-lock` (or the session-assigned
equivalent — see commit history). One branch only. No parallel edits.

## Wave 1 — Parallel Feature Lanes

Once Wave 0 lands, Wave 1 opens parallel feature lanes. Each lane is its
own branch, owned by a single agent at a time. Suggested lanes:

- **Semantic immune layer.** Detection of weak prompts, scope drift,
  evasion attempts, and mission deviation, returning structured signals
  rather than silently overriding the owner.
- **Runtime enforcement.** Gate hooks (planning, build, review, owner)
  that consume `WorkPacket` and refuse to advance when invariants are
  missing.
- **CLI expansion.** `hermes` subcommands or skill commands that wrap
  JARVIS Prime modes, classification, and packet drafting.
- **Memory / self-improvement persistence.** Durable storage of
  lessons, owner preferences, and outcome reviews, scoped so it cannot
  silently overwrite owner-authored facts.
- **Mobile / focused mode.** Termux / Slack short-response surface vs
  desktop focused-mode long-form surface; deferral of risky work until
  focused mode.
- **Test suite.** Expanded unit and integration coverage for each lane
  above; not a place to dump everyone else's missing tests.

## Wave 2 — Integration

Branch: `integration/jarvis-prime-runtime`.

Each Wave 1 feature branch merges here first (not into `main`). The
integration branch is where cross-lane conflicts get resolved and where
the full Wave 1 surface is exercised together. No new features are
added directly to the integration branch — only conflict resolution,
test fixes, and small wiring tweaks.

## Wave 3 — Codex Independent Review

Codex reviews `integration/jarvis-prime-runtime` independently of the
implementing agent. Findings come back as a structured report and (if
authorized) bounded fix commits on a separate branch that merges back
into the integration branch.

## Wave 4 — Owner-Approved Main Merge

The owner reviews the integration branch and either:

- approves the merge into `main` with the exact phrase
  **`Yes, with authorization.`**, or
- returns it with specific blockers.

No agent merges to `main` without that phrase.

## Cross-Wave Rules

- Do not edit `main` directly.
- Each feature lane gets its own branch.
- Shared runtime files (anything imported by more than one lane) require
  extra caution: read the file fully, explain the change, and prefer an
  additive change over a rewrite.
- Claude Code and Codex must not edit the same branch at the same time.
- All feature branches merge into the integration branch first, never
  straight to `main`.
- The owner must approve any `main` merge.
- No `done` claim without verification evidence: command run, output
  captured, success or named-failure stated.
- Owner-gated actions (deploy, publish, DNS, secrets, public posting,
  spending, destructive ops) require the owner authorization phrase.
- Keep JARVIS Prime runtime imports stdlib-only unless the repo already
  requires the dependency elsewhere.
- Preserve Termux compatibility — no hard requirement on tools that do
  not run on Android / Termux.
