# CLAUDE.md — Claude Code bootstrap for HazMat Command

> This file is Claude Code's startup surface. It does not redefine the
> repo constitution — it imports it. AGENTS.md (cross-tool) and PUBLISH.md
> (release) remain authoritative. The native enforcement layer
> (`.claude/rules/`, `.claude/agents/`, `.claude/skills/`,
> `.claude/settings.json`, `.claude/hooks/`) operationalizes them.

@AGENTS.md

## Claude-specific startup law

1. Treat **AGENTS.md** as the canonical constitution. The five owner-only
   walls and the preview-before-publish two-gate rule are absolute. Even
   with prior authorization in memory, do not bypass them.
2. Before substantive work, read what you actually need — not everything:
   - `PUBLISH.md` for any deploy-adjacent or release-adjacent task,
   - `SKIPPED.md` before re-implementing anything (look for an existing
     stub or wire-back before duplicating capability),
   - `docs/AUTONOMOUS_ORGANIZATION_INDEX.md` to locate the right
     governance doc, division, skill, workflow, or template.
3. Path-scoped operational rules live in `.claude/rules/`. Nested
   `CLAUDE.md` files at the directory roots auto-import the relevant
   rule when you open files under them. Do not duplicate that prose
   into this root file.
4. Reusable workflows live in `.claude/skills/`. Prefer invoking a
   skill over inventing a one-off plan.
5. Specialized roles live in `.claude/agents/`. Delegate research,
   independent review, principal code review, and pilot/release
   judgement to the right subagent rather than running every task
   through one generic persona.
6. Hard tool boundaries are enforced in `.claude/settings.json` plus
   the `.claude/hooks/block-owner-only-actions.mjs` PreToolUse hook.
   If a tool call is blocked, the deny is intentional — do not try to
   work around it; surface the block to the owner.

## Commercial delivery standard (compact)

Do not:

- declare work complete without verification,
- claim success without actual checks (lint, typecheck, test, build,
  governance:check, agentos:check, e2e where the change warrants),
- leave fragile partials disguised as production,
- write vague "AI" filler — every claim should be evidence-backed,
- widen scope without a documented reason,
- ignore the repo's docs, tests, or conventions,
- duplicate already-shipped capabilities (`git grep` + read SKIPPED.md
  before reimplementing),
- generate compliance, security, regulatory, or commercial claims
  without a citation an outside reviewer could verify.

Do:

- preserve tenant isolation, RBAC, audit ledger integrity, OCR
  provenance, and 49 CFR / TDG correctness on every touch,
- write negative tests where failure modes matter,
- keep diffs minimal,
- update the docs that materially changed and only those,
- produce an owner handoff at the end of each substantive run.

## Operating sequence (always)

Understand → Research-if-required → Plan → Implement narrowly → Test →
Independently review → Document → Owner handoff.

## Discovery shortcut

If you don't know where something lives, open
`docs/AUTONOMOUS_ORGANIZATION_INDEX.md`. If you don't know which agent
should own a task, open `docs/governance/02-agent-authority-matrix.md`.
If you don't know the risk class, open
`docs/governance/03-change-risk-matrix.md`. If a doc contradicts code,
follow `docs/governance/01-source-of-truth-hierarchy.md`.

## Council Mode and Codex routing (added 2026-05-18)

For strategy-weighted RC3 work, public commercial copy rewrites at
scale, pricing/packaging redesigns, legal-policy-set changes, launch
readiness sprints, or AEO/AOS self-modification, run Council Mode
first per `docs/workflows/deliberative-council-planning.md` and
commit artifacts to `docs/aos/runs/YYYY-MM-DD-<slug>/`. When Codex
is dispatched as the implementation fabric, use the Codex Task Packet
contract per `docs/workflows/codex-implementation-fabric.md`; Codex
is L3-max, T3+T4-only, never touches constitutional surfaces. The
validator `npm run council-codex:check` runs in CI alongside
`agentos:check` and must remain green.
