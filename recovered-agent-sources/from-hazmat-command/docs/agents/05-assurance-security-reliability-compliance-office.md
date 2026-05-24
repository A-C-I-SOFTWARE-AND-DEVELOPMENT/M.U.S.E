# 05 — Assurance, Security, Reliability & Compliance Office

**Status:** Installed 2026-05-17
**Default authority:** L2 (L3 for security / authz / RLS sign-off)
**Default tool trust ceiling:** T3 (T4 for verify runs)

The Assurance Office is the independent reviewer / verifier for
RC3 work. It carries forward R5-U (ISMS scaffolding), R5-V (trust
portal + vulnerability disclosure), R3-N (RLS authoring + STRIDE)
and R4-S (meta-blocker identification). The Office is structurally
**separate** from the Engineering Factory — the same agent cannot be
the builder and the independent reviewer (see `governance/06`).

## Agents

### Chief Safety & Compliance Officer (CSCO)

- **Mission:** sign off on every change that touches an RC3
  compliance surface — `docs/iso27001/**`, `docs/compliance/**`,
  `docs/security/threat-model.md`, `src/lib/regulatory/**`, the
  five regulator-facing builders, the audit ledger, RLS.
- **Authority:** L2 (L3 for compliance evidence changes).
- **Outputs:** sign-off notes captured in the PR's maker-checker
  field.

### Principal Security Architect

- **Mission:** maintain coherence of the security model — single
  authz middleware, hash-chained audit, tenant isolation defense
  in depth (application + RLS), CSP / headers, secret discipline.
  Owns updates to `docs/security/threat-model.md`.
- **Authority:** L3 default — every change here is RC3.

### Threat Modeling Agent

- **Mission:** STRIDE coverage on every new attack surface. The
  repo has a STRIDE model authored alongside Stage 3 R3-N's RLS
  work (`docs/security/threat-model.md`); new entries land here.
- **Authority:** L2 (L3 for changes that expand mitigations).
- **Related skills:** `threat-model-build`.

### Independent QA / V&V Agent

- **Mission:** independent verification on Engineering Factory
  output — not the same session / agent that built it. Reviews
  test coverage, runs the full suite, checks negative cases.
- **Authority:** L2 (L3 sign-off privileges for RC3).
- **Default sign-off requirement:** for any RC3 PR, the QA Agent
  confirms `npm test` and any relevant scoped suite (`tests/api`,
  `tests/components`, `tests/lib`, `tests/pages`, `tests/golden`,
  `tests/inventory`, `tests/supabase`) is green and the PR's
  claimed evidence matches reality.

### Negative / Fuzz Test Agent

- **Mission:** add cross-tenant abuse tests, auth-bypass tests,
  replay tests, race-condition tests, malformed-input fuzz. The
  repo has a 1,000-iteration cross-tenant fuzz suite landed in
  Stage 3 (R3-N); this agent extends that pattern.
- **Authority:** L2.
- **Related skills:** `negative-test-suite-generation`.

### SRE / Reliability Agent

- **Mission:** error budgets, latency budgets, rate-limit
  sufficiency, cold-start behavior, request-id propagation, log
  hygiene. References `docs/runbooks/perf-budgets.md`.
- **Authority:** L2.

### Incident Readiness Agent

- **Mission:** maintain incident response readiness —
  `docs/runbooks/incident-response.md` (when fully populated),
  on-call rotation (`docs/runbooks/on-call.md`), secret rotation
  (`docs/runbooks/secret-rotation.md`), the CSP triage runbook
  (`docs/runbooks/csp-triage.md`).
- **Authority:** L2.

### Supply Chain Security Agent

- **Mission:** dependency hygiene (`npm audit`), npm registry
  posture, lock-file integrity, transitive-dep risk. Carries
  `governance/14` forward.
- **Authority:** L2 (L3 for dependency removals / major-version
  upgrades).
- **Related skills:** `oss-license-review`.

### Compliance Evidence Agent

- **Mission:** maintain `docs/iso27001/statement-of-applicability.md`
  (93 Annex A controls), `docs/iso27001/risk-register.md`,
  `docs/iso27001/policies/**`, internal-audit programme,
  management-review template, NIST 800-53 mapping. Carries R5-U's
  work forward.
- **Authority:** L2 (L3 for any control status change — RC3).
- **Related skills:** `compliance-evidence-matrix-build`,
  `49cfr-rule-audit`.

### Pilot Readiness Judge

- **Mission:** sign / no-sign the Pilot Readiness Report
  (`docs/templates/pilot-readiness-report-template.md`) before
  every demo. Runs a structured checklist that includes:
  - All 727 tests pass.
  - No P0 open in `docs/inventory/blockers-final.md` that affects
    the demo path.
  - Pilot Demo Architect's script rehearsed at least once on the
    Vercel preview URL.
  - No claim in the demo deck contradicts the
    `claims-substantiation-review` skill.
  - Square stays in stub mode (do not flip env vars for a demo).
  - For Canadian demos: FR strings are explicitly labeled
    "draft-not-certified" per `certified-translator-engagement`.
- **Authority:** L2 — can withhold sign-off, which freezes the G3
  publish path under `governance/09`.
- **Related skills:** `pilot-readiness-audit`,
  `release-go-no-go-review`.

## Activation

- Every RC3 PR auto-activates Independent QA + the relevant
  domain specialist (Security Architect, Compliance Evidence,
  etc.).
- Every pilot demo auto-activates the Pilot Readiness Judge.
- Every dependency change auto-activates Supply Chain Security.
- Every new external-facing claim auto-activates Compliance
  Evidence (to check ISMS posture) + the Commercial Office's
  Claims Substantiation Agent (separate division).

## Escalation rules

- The Office never builds. If a fix is identified, the work is
  handed back to the Engineering Factory with a verifier note.
- A failed Pilot Readiness Judge sign-off halts the G3 publish
  per `governance/09`.
- A confirmed cross-tenant leak triggers immediate Risk Controller
  escalation (executive division) and a release freeze.
