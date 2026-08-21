# Codex Task Packet — <short title>

**Date:** YYYY-MM-DD
**Packet author:** <chief-orchestrator / engineering-architecture-factory>
**Run folder:** `docs/aos/runs/YYYY-MM-DD-<slug>/`
**Artifact slot:** `07-codex-task-package.md`
**Companion governance:** `docs/governance/17-codex-bounded-implementation-fabric.md`
**Companion workflow:** `workflows/codex-implementation-fabric.md`

> A Codex Task Packet is the input/output contract between the
> Claude-Code control plane and the Codex bounded-implementation
> fabric. Codex is L3-max, T3+T4-only. Constitutional surfaces are
> always forbidden. Owner-only walls are never invoked. Validator:
> `npm run council-codex:check`.

## Upstream reference

- Synthesized Master Plan: `04-synthesized-plan.md`
- Execution Blueprint: `06-execution-blueprint.md`
- Council Mode tier: <Lite / Standard / RC3-strategy / N-A>
- Owner approval recorded at: <PR comment URL / commit SHA>

If any of the above is empty for RC2+ work, the packet is invalid.

## Mission (one paragraph)

<what Codex is doing and the observable outcome; do not include
strategy>

## Risk class

- [ ] RC0 (cosmetic)
- [ ] RC1 (localized)
- [ ] RC2 (material — `principal-code-reviewer` wraps envelope)
- [ ] RC3 (security/compliance/commercial/legal/release —
  `principal-code-reviewer` + `assurance-security-compliance-office`
  both wrap envelope; Council Mode synthesis required upstream)
- [ ] RC4 — **forbidden**; Codex is not invoked for owner-only work

## Allow-list (paths Codex may write)

Exact globs. Constitutional surfaces are forbidden by default — do
not add them here.

```text
src/lib/____
api/____
tests/____
```

## Forbidden-list (paths Codex must NOT touch)

Always includes:

```text
AGENTS.md
PUBLISH.md
SKIPPED.md
CLAUDE.md
.claude/rules/**
.claude/agents/**
.claude/skills/**
.claude/hooks/**
.claude/settings.json
docs/governance/**
docs/agents/**
docs/skills/**
docs/workflows/**
docs/templates/**
docs/AUTONOMOUS_ORGANIZATION_INDEX.md
docs/runbooks/**
docs/iso27001/**
docs/compliance/**
docs/security/**
docs/rfp/**
marketing/**
.github/PULL_REQUEST_TEMPLATE.md
.github/workflows/**
```

Plus run-specific forbidden paths:

```text
<additional paths>
```

## Required tests

- Existing tests that must remain green: `npm test` (baseline N/N).
- New negative-path tests Codex must add:
  - `tests/____/____.test.js` — `<what it asserts>`
  - `tests/____/____.test.js` — `<what it asserts>`
- e2e tests to re-run (if applicable):
  `npm run test:e2e -- <suite>`

## Acceptance criteria

- [ ] All files touched are within the allow-list.
- [ ] No files in the forbidden-list are touched.
- [ ] All named new negative tests are present and pass.
- [ ] Baseline test count holds or moves with documented reason.
- [ ] `npm run lint`, `typecheck`, `build`, `governance:check`,
  `agentos:check`, `council-codex:check` all green.
- [ ] No `TODO(stub:...)` introduced without matching SKIPPED.md
  entry.
- [ ] No new dependency added (or, if added, `governance/14`
  updated).
- [ ] No invocation of any owner-only command attempted (cross-check
  against `.claude/hooks/block-owner-only-actions.mjs` RULES).

## Owner-only walls (forbidden actions)

Codex must not invoke any of:

- `gh pr merge`, `mcp__github__merge_pull_request`,
  `mcp__github__enable_pr_auto_merge`
- `git push origin main`, `git push origin master`,
  `git push --force`
- `vercel --prod`
- `npm publish`, `pnpm publish`, `yarn publish`
- `firebase deploy`
- `eas submit`, `fastlane`, `gradlew publish`
- Base44 Publish (no UI-driven action)
- Any DNS or domain change
- Any ad-spend, social post, third-party OAuth, third-party
  account creation

The PreToolUse hook
(`.claude/hooks/block-owner-only-actions.mjs`) blocks these
regardless; the packet states them explicitly so the envelope
verifier can fast-reject any envelope claiming such an action.

## Time budget

<sprint length / wall-clock budget>

If exceeded, Codex returns a partial envelope with `escalation:
"time-budget-exceeded"` rather than skipping tests or stretching
the allow-list.

## Expected return envelope

```text
envelope_version: 1
packet_id: <slug from this packet's filename>
status: ok | partial | failed
diff:
  files_touched:
    - path: <allow-listed path>
      change: created | modified | deleted
      sha_before: <git blob sha or null>
      sha_after: <git blob sha>
tests_added_or_changed:
  - path: <test path>
    type: new | modified
    assertion: <one-line description>
results:
  lint: pass | fail (with output excerpt)
  typecheck: pass | fail (with output excerpt)
  test: pass N/N | fail (with output excerpt)
  build: pass | fail (with output excerpt)
  council_codex_check: pass | fail
  agentos_check: pass | fail
  governance_check: pass | fail
self_assessment:
  - finding: <thing the builder is unsure about>
  - finding: <ditto>
escalation:
  - kind: time-budget-exceeded | scope-creep-detected |
          ambiguous-spec | other
    detail: <one paragraph>
```

The `codex-return-envelope-verify` skill enforces this schema and
re-runs the claimed test commands locally.

## Maker-checker pairing

- **Packet author:** <agent / session>
- **Codex executor:** <vendor / version>
- **Envelope verifier:** different agent / session than packet
  author — runs `codex-return-envelope-verify`
- **Independent code reviewer:** `principal-code-reviewer`
  subagent
- **RC3 verifier:** `assurance-security-compliance-office`
  subagent (if RC3)
- **Owner:** reviews and merges per `PUBLISH.md`

## Run-folder slots produced by this packet

- `07-codex-task-package.md` — this file.
- `08-implementation-summary.md` — builder narrative.
- `09-review-report.md` — `principal-code-reviewer` output.
- `10-test-results.md` — verified envelope test results.
- `11-security-review.md` — `assurance-security-compliance-office`
  output (RC3 only).

## Anti-patterns rejected on sight

- Constitutional surface in the allow-list.
- Allow-list with a `**` wildcard at the repo root.
- Missing forbidden-list (must always include constitutional
  surfaces).
- "Best-effort" test list rather than named test paths.
- An acceptance criterion of "looks right."
- A packet without an upstream Master Plan reference on RC2+.
- A packet that introduces a new commercial claim, legal sentence,
  or pricing copy.
