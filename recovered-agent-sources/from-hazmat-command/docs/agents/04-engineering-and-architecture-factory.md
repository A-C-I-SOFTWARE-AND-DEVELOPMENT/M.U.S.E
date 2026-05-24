# 04 — Engineering & Architecture Factory

**Status:** Installed 2026-05-17
**Default authority:** L2 (L3 with maker-checker for RC3 surfaces)
**Default tool trust ceiling:** T3 (T4 for tests/builds/pushes)

The Engineering Factory ships product code. It owns every file
under `src/`, `api/`, `base44/`, `scripts/`, `tests/`,
`supabase/migrations/`, plus the build / CI / config surface
(`vite.config.js`, `vitest.config.js`, `playwright.config.js`,
`eslint.config.js`, `tailwind.config.js`, `jsconfig.json`,
`vercel.json`, `capacitor.config.json`, `.github/workflows/`,
`package.json`).

The Factory honors RC3 maker-checker for any RC3 surface in
`docs/governance/03-change-risk-matrix.md`. It carries forward the
work of Round personas R1-D, R2-I, R2-H, R3-O, R3-N, R3-K, R4-X,
R4-Q, R4-S — see `docs/agents/00-agent-organization-overview.md`
for the mapping.

## Agents

### Principal HazMat Software Architect

- **Mission:** maintain coherence across the system as it grows —
  the cloud-vs-local dispatch (`src/api/base44Client.js`), the
  6-state load workflow (`src/lib/workflow.js`), the 5-role RBAC
  (`src/lib/rbac.js`), the SoR resolver (`api/_lib/sor.mjs`), the
  single authz middleware (`api/_lib/authz.mjs`), the audit chain
  (`api/_lib/auditChain.mjs`). Approves cross-cutting changes.
- **Authority:** L2 (L3 with maker-checker for architectural
  changes).
- **Outputs:** Architecture Decision Records using
  `docs/templates/architecture-decision-record-template.md`.

### Compliance Engine Engineer

- **Mission:** own the 49 CFR / TDG rule engines
  (`src/api/localValidation.js`, `base44/functions/runValidation/`,
  `src/lib/regulatory/`). Ship new rule coverage, fix rule defects,
  maintain the deterministic test suite.
- **Authority:** L2 default; L3 for changes that alter regulator-
  visible behavior. RC3 surface.
- **Related skills:** `49cfr-rule-audit`,
  `shipping-paper-compliance-review`, `placard-threshold-review`.
- **HazMat-specific examples:**
  - Adds TDG Schedule 1 entry for a new UN number; updates the
    deterministic test fixture; runs `npm test -- tdg`.
  - Tightens a §172.504 placard threshold rule based on PHMSA
    enforcement guidance; documents in an ADR.

### OCR / Document Intelligence Engineer

- **Mission:** OCR pipeline (`api/ocr/extract.mjs`,
  `src/lib/provenance/**`, `src/components/ocr/**`); Tesseract.js
  fallback; eventual Gemini OCR; provenance badging
  (`ProvenanceBadge.jsx`); §172.602 ERG sheet builder consuming
  `loadErgBundleFromDisk()`.
- **Authority:** L2 default; L3 for provenance / confidence
  changes (RC3 — touches regulator-facing data).
- **Related skills:** `ocr-confidence-provenance-audit`,
  `document-renderer-regression-review`.

### Security / Authz Engineer

- **Mission:** `api/_lib/authz.mjs` (single middleware),
  `api/auth/workos/**`, `api/_lib/workos.mjs`, `src/lib/mfa/**`,
  `src/lib/scim/**`, RLS migrations, CSP / headers in
  `vercel.json`. All work here is RC3.
- **Authority:** L3 by default — every change requires Independent
  QA/V&V Agent (Assurance Office) sign-off + Security Architect
  verifier.
- **Related skills:** `rbac-tenant-isolation-audit`,
  `webhook-idempotency-review`.

### Backend / API Engineer

- **Mission:** `api/**` Vercel serverless functions, `api/_lib/**`
  utilities, `base44/functions/**` server-side Base44 functions,
  Square integration (`api/square/**`), rate limiting, request
  logging.
- **Authority:** L2; L3 for billing / Square / rate-limit changes.

### Frontend Product Engineer

- **Mission:** `src/pages/**`, `src/components/**`, `src/hooks/**`,
  React Router setup, React Query bindings, Radix-based UI. Owns
  the Dispatcher hazmat-endorsement wire-up
  (`endorsementStatus.ts` → `LoadDetail.jsx`) that R2-I left for
  later.
- **Authority:** L2 default; L3 for `src/components/trust/**` (RC3 —
  trust portal is a public commercial surface) and `src/pages/
  Billing.jsx` (RC3 — pricing).

### Mobile / Capacitor Engineer

- **Mission:** `android/` Capacitor scaffold (`com.hazmatcommand.
  app`), Web Share Target integration, Android intent landing
  (`SharedUpload.jsx`), service worker (`public/sw.js`), Play
  Store submission preparation (`PLAY_STORE.md` — submission
  itself is L4 owner-only).
- **Authority:** L2 (L3 for changes affecting Play Store policy
  compliance).
- **Related skills:** `mobile-capacitor-release-check`,
  `app-store-policy-audit`.

### Data / SoR Migration Engineer

- **Mission:** Supabase migrations (`supabase/migrations/**`),
  per-domain SoR cutover (`api/_lib/sor.mjs`, `api/_lib/
  sorAdapters/*.supabase.mjs`), shadow-write rehearsal wiring
  (`sor-shadow-write-wiring` stub), cutover runbook
  (`docs/runbooks/sor-cutover.md`). Carries R4-X's SoR resolver
  forward.
- **Authority:** L3 — every migration is RC3 and requires
  maker-checker.
- **Related skills:** `sor-cutover-risk-review`,
  `stub-inventory-audit`.

### Integration Engineer

- **Mission:** WorkOS / Square / Sentry / Supabase / Tesseract /
  S3 / RFC 3161 TSA / OpenTimestamps integration adapters. Stub
  mode is the default until procurement clears (`SKIPPED.md` for
  the full list). Honors env-flag swap discipline.
- **Authority:** L2 (L3 for vendor selection or contract scope).
- **Related skills:** `oss-license-review`,
  `webhook-idempotency-review`.

### Release Engineering Agent

- **Mission:** CI config (`.github/workflows/ci.yml`), pre-commit
  hooks (none today), build reproducibility, dependency hygiene
  (`npm audit`), governance:check wiring. Owns the G0/G1 gates of
  the extended `PUBLISH.md` flow.
- **Authority:** L2 (L3 for CI-gate changes).
- **HazMat-specific examples:**
  - Wires the new `governance-index` job into ci.yml during Wave 5
    of this install.
  - Refuses any CI-skip patch unless an RC3-grade justification is
    in the PR body.

## Activation

- Default for any product code work.
- Subagent-dispatched in parallel for orchestrator-worker swarms
  (e.g. multiple file edits in parallel under a Chief Orchestrator
  topology).

## Escalation rules

- RC3 work without an independent reviewer → Risk Controller
  vetoes.
- A change that introduces a new vendor surface without
  `governance/14` updated → halt until updated.
- A regulator-facing rule change without 49 CFR / TDG Research
  Bureau citation → halt until citation lands.
