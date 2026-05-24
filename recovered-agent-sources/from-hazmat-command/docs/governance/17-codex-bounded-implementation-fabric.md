# 17 — Codex Bounded Implementation Fabric

**Status:** Installed 2026-05-18 (Wave 1, contract-only; integration
deferred to Wave 2 per the approved evolution plan)
**Companion:** `docs/governance/16-deliberative-planning-and-council-mode.md`
**Implements:** `docs/workflows/codex-implementation-fabric.md`
**Backing research:** `docs/research/council-mode-and-codex-fabric-design-2026-05-18.md`

This doc defines what Codex is allowed to do inside the HazMat
Command AEO, what it is **not** allowed to do, and how every Codex
output is wrapped by independent review before it can land. It does
**not** introduce a new authority level, a new risk class, or a new
trust zone. Codex is constrained by the *existing* L0–L4, RC0–RC4,
and T0–T6 surfaces.

## Why this matters here specifically

The AEO has, until now, treated Codex as a generic "future tool"
that future agent sessions might use. That framing is no longer
adequate. As autonomous coding tools become routine, "any model can
edit any file" is the failure mode the AEO is built to prevent.
This doc formalizes Codex as a **bounded implementation fabric**:
Codex receives a structured task packet, returns a structured
envelope, and never touches strategy, claims, legal, owner-only
walls, or any path outside its packet's allow-list. Claude Code
remains the constitutional control plane; Codex is one of several
permitted *builders* downstream of approved plans.

## Definition

**Codex** in this repo refers to any autonomous code-execution agent
operating under a Codex Task Packet contract — most commonly OpenAI
Codex CLI / Codex Cloud, but the contract applies to any equivalent
external implementation fabric.

A **Codex Task Packet** is an input/output contract:

- **Input:** scoped mission, allow-listed files, forbidden files,
  required tests, acceptance criteria, owner-only-wall list, time
  budget, expected output shape.
- **Output (Return Envelope):** diff, files touched, tests added
  or changed, lint/typecheck/test/build results, self-assessment,
  escalation flags.

The template lives at
`docs/templates/codex-task-package-template.md`. Every Codex
invocation produces one packet and one envelope, both committed to
the relevant run folder under `docs/aos/runs/`.

## Authority cap

Codex operates at authority level **L3 maximum**, never L4.

| If the packet would require... | Then... |
|---|---|
| Reading any T1 reference | Permitted |
| Writing under an allow-listed path (T3) | Permitted |
| Running `npm run lint/typecheck/test/build` (T4) | Permitted |
| Touching a path not on the allow-list | Forbidden — packet rejected by `codex-return-envelope-verify` |
| Calling any external write API (T5) | Forbidden |
| Performing any owner-only wall action (T6) | Forbidden — caught by `.claude/hooks/block-owner-only-actions.mjs` and validator |
| `gh pr merge`, force-push, `vercel --prod`, `npm publish`, Base44 Publish, store submission, DNS change, ad spend, OAuth, account creation, social post | Forbidden — these are L4 |
| Writing new commercial claims, new legal text, new pricing copy, new positioning copy | Forbidden — those belong to the Commercial / Legal divisions per `governance/11` and `governance/12` |
| Generating a new architectural pattern not in the approved plan | Forbidden — Codex extends approved plans only; design happens upstream in Council Mode |

Codex never decides risk class, never authorizes a release, never
approves its own output. The maker-checker rule
(`governance/06`) always wraps Codex output.

## Trust-zone enforcement

Codex is bound to **T3 (repo code write on permitted branch) + T4
(terminal / test / build)** only.

- **T0 (untrusted read)** — Codex must not consume T0 content
  directly. Untrusted input passes through Claude Code review first.
- **T1 (trusted reference read)** — Permitted; the packet may
  include T1 references the agent should read.
- **T2 (internal draft write)** — Permitted only for draft artifacts
  inside the run folder, never for `marketing/**` or other commercial
  surfaces.
- **T3 (repo code write)** — Permitted, scoped to the packet's
  allow-list.
- **T4 (terminal / test / build)** — Permitted, scoped to the
  commands listed in the packet (lint, typecheck, test, build).
- **T5 (external side effects)** — Forbidden.
- **T6 (owner-only)** — Forbidden.

These bindings are enforced by three layers:

1. The `codex-implementation-fabric` subagent's `tools:` frontmatter
   excludes T5/T6 commands. Validator `check-council-and-codex.mjs`
   asserts the exclusion.
2. The existing `.claude/hooks/block-owner-only-actions.mjs` PreToolUse
   hook blocks any T6 attempt regardless of which agent is calling.
3. The `codex-return-envelope-verify` skill re-runs the claimed
   tests locally and rejects any envelope whose diff touches a file
   outside the packet's allow-list.

## Risk-class binding

Codex packets may be dispatched for:

- **RC0** — cosmetic. Lowest oversight; envelope still verified.
- **RC1** — localized, well-covered. Standard envelope verification.
- **RC2** — material product / governance change. Envelope verified
  + `principal-code-reviewer` wraps the diff.
- **RC3** — security/compliance/commercial/legal/release-sensitive.
  Envelope verified + `principal-code-reviewer` **and**
  `assurance-security-compliance-office` both wrap the diff. The
  Council Mode synthesis and red-team must already be on file in
  the run folder per `governance/16`.
- **RC4** — **forbidden**. RC4 is owner-only; Codex is not invoked.

## Maker-checker wrapping (always)

Every Codex envelope is reviewed by an agent / session different
from the dispatching session:

| Stage | Who | What |
|---|---|---|
| Dispatch | Chief Orchestrator or skill caller | Authors the packet; validates allow-list / forbidden-list before sending |
| Execution | Codex | Produces envelope (diff + test results) |
| Envelope verification | `codex-return-envelope-verify` skill | Schema check, allow-list adherence, test re-run, hash of files touched |
| Code review | `principal-code-reviewer` subagent | Independent diff review per the existing maker-checker discipline |
| Security/compliance review (RC3) | `assurance-security-compliance-office` subagent | RC3 surface check, threat-model update, negative-test confirmation |
| Owner approval | Owner | Reviews PR; merges per the two-gate publish flow |

If any of the four review steps fails, the envelope is rejected and
either re-dispatched with a tightened packet or escalated.

## Forbidden uses of Codex

- Authoring a Mission Brief, Evidence Bundle, multi-plan set,
  comparison matrix, synthesized master plan, red-team review, or
  execution blueprint. **These belong to Council Mode.**
- Writing or modifying claims-substantiation memos.
- Drafting legal documents.
- Modifying `AGENTS.md`, `PUBLISH.md`, `SKIPPED.md`, `CLAUDE.md`,
  or any `.claude/rules/`, `.claude/agents/`, `.claude/skills/`,
  `.claude/hooks/`, `.claude/settings.json` entry — these are
  constitutional surfaces; their changes are RC3 and require Council
  Mode plus Claude Code authorship.
- Approving its own output.
- Bypassing tests "to save time."
- Touching any file outside the packet's allow-list.

## Run-folder integration

For every Codex packet that ships:

- The packet itself lands at `07-codex-task-package.md` inside the
  corresponding `docs/aos/runs/YYYY-MM-DD-<slug>/` folder.
- The implementation summary lands at `08-implementation-summary.md`.
- The review report lands at `09-review-report.md` (from
  `principal-code-reviewer`).
- The test-results envelope lands at `10-test-results.md`.
- The security review (RC3) lands at `11-security-review.md` (from
  `assurance-security-compliance-office`).

## Wave 1 scope (contract-only)

Wave 1 installs:

- This governance doc.
- `docs/workflows/codex-implementation-fabric.md`.
- `docs/templates/codex-task-package-template.md`.
- `.claude/skills/codex-task-packet-dispatch/` (manual-only).
- `.claude/skills/codex-return-envelope-verify/`.
- `.claude/agents/codex-implementation-fabric.md` (thin subagent
  wrapper).
- `scripts/check-council-and-codex.mjs` validator and CI job.

Wave 1 **does not** wire an actual Codex CLI or external Codex
service. That is Wave 2, gated by:

1. A dedicated research dossier under `docs/research/` on the
   chosen Codex vendor.
2. Owner approval of the vendor choice.
3. A `codex-dispatch-smoke` CI job that verifies a no-op packet
   end-to-end.

## Validator

`scripts/check-council-and-codex.mjs` asserts:

- The subagent file exists with valid frontmatter.
- The subagent's `tools:` list contains none of the forbidden
  patterns (gh pr merge, git push to main, force-push, vercel --prod,
  npm publish, firebase deploy, EAS submit, fastlane, GitHub MCP
  merge tools).
- The subagent description states the bounded trust zone (T3+T4)
  and the L3 authority cap explicitly.

## Anti-patterns rejected on sight

- A Codex packet that includes constitutional files in its allow-list.
- A Codex envelope whose diff touches files outside the allow-list.
- A Codex envelope claiming tests passed without showing the
  command output that proves it.
- A Codex run that produces a new claim, legal sentence, or pricing
  copy.
- Any attempt to dispatch a Codex packet without an upstream Council
  Mode synthesis when the RC class requires it.
- Codex "self-reviewing" by emitting both diff and review in the
  same envelope.
- A change to the codex subagent's `tools:` list that adds an
  owner-only command.
