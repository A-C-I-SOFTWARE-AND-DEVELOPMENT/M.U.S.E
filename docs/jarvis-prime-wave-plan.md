# JARVIS Prime — Wave Build Plan

This document describes how JARVIS Prime is built out wave-by-wave so
parallel work can proceed safely without duplicate systems, force-push
conflicts, or stale runtime drift. It is the companion to
[`CANONICAL_REPO.md`](../CANONICAL_REPO.md) and
[`docs/jarvis-prime-operating-system.md`](jarvis-prime-operating-system.md).

## Wave overview

| Wave | Purpose | Branch shape | Parallelizable? |
| --- | --- | --- | --- |
| 0 | Foundation lock | `feature/jarvis-foundation-lock` (single branch) | No |
| 1 | Feature lanes | `feature/jarvis-<lane>` (one per lane) | Yes, across lanes |
| 2 | Integration | `integration/jarvis-prime-runtime` (single branch) | No |
| 3 | Independent review | Codex review pass on the integration branch | No |
| 4 | Owner-approved merge to `main` | Owner gate | No |

## Wave 0 — Foundation lock (this branch)

Goals:

- Declare the canonical repo in [`CANONICAL_REPO.md`](../CANONICAL_REPO.md).
- Document the wave plan (this file).
- Add the standard `WorkPacket` model at
  `hermes_cli/jarvis_prime/work_packet.py` and export it from the
  package.
- Add baseline tests so later waves have a regression floor.

Constraints:

- Stdlib-only at import time for runtime files.
- Termux-compatible.
- No deploys, no merges to `main`, no force-push, no new feature work.
- Build on the existing JARVIS Prime runtime in
  `hermes_cli/jarvis_prime/`. **Do not create duplicate systems.**

Exit criteria:

- Canonical-repo doc lives at repo root.
- Wave-plan doc (this file) lives under `docs/`.
- `from hermes_cli.jarvis_prime import WorkPacket` succeeds.
- `WorkPacket().validate()` returns structured findings.
- New tests pass alongside the existing 159 JARVIS Prime tests.

## Wave 1 — Feature lanes (parallel)

Each lane is a separate `feature/jarvis-<lane>` branch. Lanes may run
in parallel **provided no two lanes edit the same runtime file at the
same time**. Each lane consumes the WorkPacket model from Wave 0 as
its handoff envelope.

Lanes:

1. **Semantic immune layer** — strengthen `epistemics.audit_response`,
   anti-hallucination guards, citation enforcement, hedge detection.
2. **Runtime enforcement** — tighten how `runtime.JarvisPrime`
   enforces mode → router → gate transitions and how it surfaces
   failed gates to the caller.
3. **CLI expansion** — extend `hermes_cli/jarvis_prime/__main__.py`
   subcommands and slash-command registration in `hermes_cli/main.py`.
4. **Memory / self-improvement persistence** — durable persistence
   for `memory.MemoryStore` and `self_update.ProposalBook`.
5. **Mobile / focused mode** — short-response shaping for Slack /
   Termux / voice surfaces; deferred-action queueing.
6. **Test suite** — broaden coverage, add property tests, harden the
   existing JARVIS Prime test surface.

Lane discipline:

- One owner per lane (Claude Code **or** Codex, not both).
- Lanes branch from `main` (the canonical ACI main), not from each
  other.
- Lanes that touch a shared runtime file (e.g. `runtime.py`, the
  package `__init__.py`, `gates.py`) must coordinate via an issue
  comment before pushing.
- Each lane PR opens against `integration/jarvis-prime-runtime` first,
  not `main`.

## Wave 2 — Integration

A single integration branch `integration/jarvis-prime-runtime` collects
every Wave 1 lane.

- Lanes merge into the integration branch in order of independence
  (least-shared-file first).
- After each lane merges, the full test suite runs against the
  integration branch.
- Cross-lane conflicts get resolved on the integration branch, never
  by reaching back into a feature branch.

## Wave 3 — Codex independent review

After integration is green, Codex performs an independent review pass:

- Runs the test suite.
- Audits diffs against `docs/jarvis-prime-operating-system.md` and the
  eight verification gates.
- Files findings as inline review comments on the integration PR.
- May land bounded fixes on a `fix/<scope>` branch — never directly
  on the integration branch and never on `main`.

Claude Code does not push to the integration branch while Codex is
reviewing it.

## Wave 4 — Owner-approved merge to `main`

`main` is owner-gated. The owner must reply with the exact phrase
`Yes, with authorization.` (see
`hermes_cli/jarvis_prime/owner_auth.py::AUTHORIZATION_PHRASE`) before
the integration branch is merged.

The merge itself is the owner's decision. JARVIS Prime, Claude Code,
and Codex must not merge to `main` automatically, even when all gates
pass.

## Standing rules (apply to every wave)

1. **Do not edit `main` directly.** All work lives on a branch.
2. **Each feature lane gets its own branch.** Lanes do not share a
   working tree.
3. **Shared runtime files require extra caution.** Touching
   `runtime.py`, the package `__init__.py`, `gates.py`, `modes.py`,
   `router.py`, or `owner_auth.py` requires a written reason in the
   commit message or PR body.
4. **Claude Code and Codex must not edit the same branch at the same
   time.** Hand off explicitly.
5. **All feature lanes merge into the integration branch first**, not
   into `main`.
6. **Main-branch merge requires owner approval** via the exact phrase.
7. **No "done" claim without verification evidence.** Tests, command
   transcripts, or explicit "tests not run because X" must be in the
   handoff.
8. **Stdlib-only runtime imports.** JARVIS Prime runtime files must
   not pull in heavy dependencies at module import time. Lazy-import
   plugin backends inside functions.
9. **Termux compatibility.** Avoid platform-specific or wheel-only
   dependencies in runtime files.
10. **Do not create duplicate JARVIS systems.** Extend the existing
    package; never fork a parallel runtime.

## Cross-references

- [`CANONICAL_REPO.md`](../CANONICAL_REPO.md) — canonical-repo
  declaration and owner-gate list.
- [`docs/jarvis-prime-operating-system.md`](jarvis-prime-operating-system.md) — runtime spec.
- [`docs/jarvis-verification-gates.md`](jarvis-verification-gates.md) — eight gates.
- [`docs/claude-codex-handoff-workflow.md`](claude-codex-handoff-workflow.md) — worker handoff protocol.
- [`hermes_cli/jarvis_prime/work_packet.py`](../hermes_cli/jarvis_prime/work_packet.py) — WorkPacket model.
