# Workflow — Codex Implementation Fabric

## Trigger

A council-approved execution blueprint (see
`workflows/deliberative-council-planning.md` step 10) or a
deterministic execution workflow (security-or-authz-change,
compliance-rule-change, complex-bug-fix, etc.) has produced a scoped
implementation task that is suitable for a bounded autonomous coding
agent under the contract defined in
`docs/governance/17-codex-bounded-implementation-fabric.md`.

**Not triggered by:**

- RC4 work (owner-only).
- Constitutional surface changes (`AGENTS.md`, `PUBLISH.md`,
  `SKIPPED.md`, `CLAUDE.md`, `.claude/rules/`, `.claude/agents/`,
  `.claude/skills/`, `.claude/hooks/`, `.claude/settings.json`).
- New commercial claims, new legal text, new pricing copy, new
  positioning copy.
- Any task without a packet allow-list and acceptance criteria.

## Required Divisions

Executive Command & Orchestration (chief-orchestrator) · Engineering
& Architecture Factory (packet author and dispatch caller) ·
Assurance, Security, Reliability & Compliance Office (RC3 wrap) ·
Principal Code Reviewer (independent diff review).

## Required Research Artifact

For RC2+: the upstream execution blueprint from Council Mode (or the
matching deterministic workflow's research dossier) is the gating
artifact. The Codex packet references it explicitly.

## Agent Topology

Sequential dispatch → execution → envelope verification → parallel
review wrap (principal-code-reviewer + RC3 security-office), then
owner handoff.

## Sequence

1. **Packet authorship** — Engineering Factory or
   chief-orchestrator drafts the Codex Task Packet using
   `templates/codex-task-package-template.md`. The packet
   includes:
   - mission (one paragraph),
   - upstream blueprint reference,
   - allow-listed paths (exact globs),
   - forbidden paths (exact globs; always includes constitutional
     surfaces),
   - required tests to write or pass,
   - acceptance criteria,
   - owner-only-wall list (forbidden actions),
   - time budget,
   - expected return-envelope shape.
2. **Pre-dispatch validation** — caller runs
   `npm run council-codex:check` and confirms the packet's allow-list
   does not include constitutional surfaces. If it does, the packet
   is rejected as invalid.
3. **Dispatch** — skill `codex-task-packet-dispatch` (manual-only
   per Wave 1) sends the packet to the Codex execution surface.
   In Wave 1 this is a dry-run only; Wave 2 wires the actual
   integration after a research dossier on the vendor and explicit
   owner approval.
4. **Execution (Codex)** — Codex receives the packet, produces the
   diff, runs the required tests, and emits the return envelope.
5. **Envelope verification** — skill `codex-return-envelope-verify`
   parses the envelope and asserts:
   - schema validity (all required fields present),
   - allow-list adherence (no files touched outside the allow-list),
   - forbidden-list adherence (no files touched in the
     forbidden-list),
   - re-run of the claimed test commands locally; results must
     match the envelope's claim,
   - no owner-only command invoked (cross-check against
     `.claude/hooks/block-owner-only-actions.mjs` patterns).
   Any failure rejects the envelope and triggers either re-dispatch
   with a tightened packet or escalation to chief-orchestrator.
6. **Principal code review** — `principal-code-reviewer` subagent
   reviews the diff independently. Builder ≠ reviewer.
7. **Security / compliance wrap (RC3 only)** —
   `assurance-security-compliance-office` subagent wraps the diff
   per the maker-checker discipline for RC3 surfaces. Cross-tenant
   negative tests, threat-model update, compliance-evidence-matrix
   update as applicable.
8. **Run-folder commit** — packet, envelope, review report,
   test-results envelope, and (if RC3) security review committed to
   the corresponding `docs/aos/runs/YYYY-MM-DD-<slug>/` folder at
   filenames `07-codex-task-package.md`, `08-implementation-summary.md`,
   `09-review-report.md`, `10-test-results.md`,
   `11-security-review.md`.
9. **PR readiness and owner handoff** — skill
   `pr-readiness-and-owner-handoff` assembles the PR body, links
   the run folder, surfaces any owner-action blockers. PR opened
   as draft per `AGENTS.md`.
10. **Owner approval and merge** — owner reviews per the two-gate
    publish flow in `PUBLISH.md`. Codex never merges.

## Parallelization Opportunities

- Principal code review and security/compliance wrap (RC3) can run
  in parallel once the envelope is verified.

## Maker-Checker Review Points

- Packet author ≠ envelope verifier ≠ code reviewer ≠ owner.
- For RC3: a third verifier (assurance-security-compliance-office)
  is mandatory.
- The owner is the only party who can merge.

## Final Outputs

Codex Task Packet · Return Envelope · Code diff · Test results ·
Independent code review · RC3 security review (if applicable) ·
Run-folder commit · Draft PR · Owner handoff.

## Acceptance Criteria

- Envelope verified clean (allow-list, forbidden-list, test re-run,
  no owner-only invocation).
- Principal code review verdict: `approve` or `request-changes`
  resolved.
- For RC3: security/compliance wrap verdict: clean or remediations
  applied.
- All run-folder artifacts (07–11) committed.
- `npm run council-codex:check` passes.
- `npm run agentos:check`, `npm run governance:check`,
  `npm run readiness:check` all pass.
- PR opened as draft; owner notified.

## Anti-patterns rejected on sight

- Codex packet whose allow-list includes a constitutional surface.
- Envelope whose diff touches files outside the allow-list.
- Envelope claiming tests passed without showing command output.
- A "Codex packet" used to author commercial claims, legal text, or
  pricing copy (these are Council Mode + Commercial / Legal
  Division work).
- Codex output reviewed by the same session that dispatched the
  packet (no maker-checker).
- Codex invoked on an RC3 surface without an upstream Council Mode
  synthesis on file.
- Skipping envelope verification on the assumption "the diff looks
  small."
- A Codex run that introduces a stub without a SKIPPED.md entry or
  a feature-flag without a registry update.
