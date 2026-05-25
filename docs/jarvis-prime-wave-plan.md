# JARVIS Prime — Wave Build Plan

This document describes how JARVIS Prime runtime work is sequenced
into waves, what each wave delivers, and the rules that keep parallel
lanes from colliding.

Read this alongside:

- `CANONICAL_REPO.md` — canonical repo + owner-gated action list.
- `docs/jarvis-prime-operating-system.md` — runtime spec.
- `docs/jarvis-verification-gates.md` — the eight gates.

## Wave 0 — Foundation lock

**Branch:** `feature/jarvis-foundation-lock`

Deliverables:

- `CANONICAL_REPO.md` declaring the source of truth.
- This wave-plan doc.
- Standard `WorkPacket` model at
  `hermes_cli/jarvis_prime/work_packet.py`, exported from
  `hermes_cli.jarvis_prime`.
- Baseline tests for the `WorkPacket` model.

Goal: make the repo safe, canonical, and structured before any
parallel lanes open.

## Wave 1 — Parallel feature lanes

Wave 1 opens multiple feature branches that can run in parallel
because they touch disjoint surfaces:

- **Semantic immune layer** — JARVIS-side defenses against
  jailbreaks, prompt injection, and goal drift.
- **Runtime enforcement** — wire the WorkPacket + gates into the
  routing flow so dispatches must carry a packet that passes the
  gates.
- **CLI expansion** — extend `python -m hermes_cli.jarvis_prime`
  surface area (subcommands, JSON output, packet helpers).
- **Memory / self-improvement persistence** — durable storage for
  proposals, durable lessons, and post-run retrospectives.
- **Mobile / focused mode** — short-form mobile-voice responses,
  defer-risky-work-until-focused behavior.
- **Test suite** — broaden coverage across the runtime, including
  gate evaluators and the router.

Each lane lives on its own feature branch off `main`. Lanes must
not edit shared runtime files concurrently — see the rules below.

## Wave 2 — Integration

**Branch:** `integration/jarvis-prime-runtime`

All Wave 1 feature branches merge into this integration branch
first. Integration is where cross-lane regressions surface and get
fixed before reaching `main`. The integration branch is the only
place where it is acceptable to fix conflicts between lanes.

## Wave 3 — Codex independent review

Codex performs an independent review of the integration branch:
diff review, gate review, test review, and a contrarian pass that
identifies the strongest objection. Codex may push tightly scoped
fixes, but does not edit the integration branch at the same time as
Claude.

## Wave 4 — Owner-approved main merge

The owner reviews the integration branch and Codex's findings, then
either merges to `main` or requests another integration pass. Main
merge requires the exact phrase `Yes, with authorization.` per the
owner-gated action contract in `CANONICAL_REPO.md`.

## Rules

These rules apply to every wave:

1. **Do not edit `main` directly.** Every change goes through a
   feature branch and (from Wave 2 on) an integration branch.
2. **Each feature lane gets its own branch.** No mixing lanes on
   one branch.
3. **Shared runtime files require extra caution.** If a feature
   lane must touch `hermes_cli/jarvis_prime/__init__.py`, the
   router, or any other file used by more than one lane, the change
   must be small, explained in the commit, and merged into
   integration before sibling lanes rebase.
4. **Claude Code and Codex must not edit the same branch at the
   same time.** Hand off explicitly; never overlap.
5. **All feature branches merge into the integration branch
   first.** Direct feature-to-main merges are forbidden.
6. **Main merge requires owner approval.** Use the exact
   authorization phrase.
7. **No "done" claim without verification evidence.** "Done" means
   the relevant tests / CLI smoke checks ran, with output captured
   in the handoff.

## Handoff format

Every wave handoff includes, at minimum:

1. Branch
2. Mission completed
3. Files changed
4. What was added
5. What was intentionally not added
6. Tests run (exact commands)
7. Test results (raw output references, not summaries-without-proof)
8. Known risks
9. Rollback plan
10. Recommended next branch

This mirrors the WorkPacket schema in
`hermes_cli/jarvis_prime/work_packet.py`.
