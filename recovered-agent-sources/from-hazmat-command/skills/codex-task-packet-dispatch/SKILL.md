---
name: codex-task-packet-dispatch
description: Manual-only. Owner-triggered. Drafts and dispatches a Codex Task Packet per docs/templates/codex-task-package-template.md and docs/governance/17-codex-bounded-implementation-fabric.md. Wave 1 is contract-only — validates packet shape, confirms maker-checker pairing, refuses any packet whose allow-list includes a constitutional surface. Wave 2 wires actual dispatch after a research dossier + owner vendor approval.
disable-model-invocation: true
---

# codex-task-packet-dispatch

## When to use

Owner explicitly invokes Codex on a scoped implementation slice
under an owner-approved Execution Blueprint. Manual-only because
Codex is a bounded-implementation fabric whose authority cap (L3)
and trust zone (T3+T4) are constitutional constraints; auto-
invocation would silently widen the agent's surface.

## Inputs

- `06-execution-blueprint.md` with the named Codex packet.
- Draft packet at `07-codex-task-package.md` (or to be authored
  here).
- The maker-checker pairing recorded in the run folder.

## Method

1. If the draft packet does not exist, copy
   `docs/templates/codex-task-package-template.md` to
   `07-codex-task-package.md` and fill it from the Execution
   Blueprint's Codex Packets entry. Constitutional surfaces are
   excluded from the allow-list.
2. Run the pre-dispatch checklist:
   - Allow-list excludes `AGENTS.md`, `PUBLISH.md`, `SKIPPED.md`,
     `CLAUDE.md`, `.claude/**`, `docs/governance/**`,
     `docs/agents/**`, `docs/skills/**`, `docs/workflows/**`,
     `docs/templates/**`, `.github/**`, `marketing/**`.
   - Forbidden-list includes the constitutional default set.
   - Owner-only-wall list explicitly enumerated.
   - Tests named (not "best effort").
   - Acceptance criteria observable.
   - Time budget set.
   - Return-envelope schema referenced.
3. Invoke `codex-implementation-fabric` subagent to audit the
   packet. Receive a `ready` / `block` / `escalate` verdict.
4. If `block` or `escalate`, fix the packet or escalate to the
   owner. Do not dispatch.
5. **Wave 1:** stop here. Record the dispatch-readiness verdict
   in `07-codex-task-package.md`. Do not call any external Codex
   surface in Wave 1.
6. **Wave 2 (deferred):** dispatch to the owner-approved Codex
   vendor. Capture the return envelope.
7. Hand the envelope to `codex-return-envelope-verify`.

## Output

`07-codex-task-package.md` populated and validated. Wave 2 also
produces an envelope file (`08-implementation-summary.md` plus
`10-test-results.md`).

## Anti-patterns

- Constitutional surface in the allow-list.
- Forbidden-list missing the constitutional default set.
- Auto-invoking this skill (it is manual-only by design).
- Dispatching before chief-orchestrator confirms maker-checker
  pairing.
- Authoring strategy, claims, legal text, pricing, or positioning
  copy in the packet's mission (those belong to Council Mode).
- Wiring an external Codex vendor in Wave 1 (deferred).
