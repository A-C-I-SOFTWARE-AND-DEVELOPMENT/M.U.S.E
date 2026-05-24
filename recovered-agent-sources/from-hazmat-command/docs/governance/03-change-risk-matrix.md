# 03 — Change Risk Matrix

**Status:** Installed 2026-05-17

Every PR (and every plan large enough to need one) carries a Risk
Class — RC0 through RC4. The class decides:

- required authority level (`governance/02`);
- required research artifact (`governance/05`);
- required maker-checker reviewer count (`governance/06`);
- required tests / evidence;
- documentation expectations.

The PR template (`.github/PULL_REQUEST_TEMPLATE.md`) asks the
contributor to tag the PR with its RC class.

## Classes

| Class | Name | What | HazMat Command examples |
|---|---|---|---|
| **RC0** | Cosmetic | Pure typo, indentation, doc punctuation. No behavior change. | Fix a typo in a runbook; rename a comment heading |
| **RC1** | Low-risk functional | Localized behavior change with negligible blast radius. Existing tests cover the surface. | Add an aria-label to one button; update a non-regulatory label string; add a test for a previously-uncovered branch |
| **RC2** | Material product or governance change | Multi-file or cross-component change; new file structure; new governance content; new test surface; user-visible behavior change in a low-stakes area | Adding the autonomous OS docs (this install); adding a new skill or workflow; adding a UI panel to `/Settings`; new helper in `src/lib/` |
| **RC3** | Critical compliance / security / commercial / legal / release | Anything that touches tenant isolation, authz middleware, audit ledger, OCR provenance, RLS, regulator-facing document builders, payment flow, CSP, secrets, dependency graph, public commercial claims, legal documents, CI gates | Stage-3 authz hardening (R3-O); RLS migration application (`supabase-rls-applied`); OCR field-provenance store cutover (`supabase-provenance`); §172.202 shipping-paper template swap; certified FR translator publish (`certified-translator-engagement`); claims-substantiation update on `/trust`; pricing update on `/Billing`; new DPA template version |
| **RC4** | Owner-only operational decision | Not executable by an agent. Production DNS change, third-party account creation, ad spend, Play/App Store submission, merge to `main`. | The five owner-only walls in `AGENTS.md` plus DNS / Base44 Publish / Vercel production promotion |

## Required by class

| Requirement | RC0 | RC1 | RC2 | RC3 | RC4 |
|---|---|---|---|---|---|
| Authority level (`governance/02`) | L1 | L2 | L2 | L3 | L4 |
| Research dossier (`governance/05`) | No | Optional | Recommended | **Required** | N/A — owner |
| Independent reviewer (`governance/06`) | No | No | Recommended | **Required** | N/A — owner |
| Verifier (third role) | No | No | No | **Required for security/compliance/legal/commercial-claims work** | N/A |
| Tests added | No | If practical | Yes (for new code paths) | **Yes, including negative / cross-tenant cases where applicable** | N/A |
| Compliance evidence (`docs/iso27001/` or `docs/compliance/`) | No | No | If change touches an ISMS control | **Yes** | N/A |
| Threat-model entry (`docs/security/threat-model.md`) | No | No | If new attack surface | **Yes for security/authz/data changes** | N/A |
| Stub/flag impact (`SKIPPED.md`, `governance/10`) | No | If applicable | **Yes** | **Yes** | N/A |
| Doc-freshness sweep (`governance/15`) | No | No | Recommended | **Required** | N/A |

## How to decide RC

1. Does the change cross any of the surfaces listed in the RC3 row
   above? → **RC3**.
2. Is the change multi-file or does it introduce new structure /
   tests / docs without touching an RC3 surface? → **RC2**.
3. Is the change a localized behavior change covered by existing
   tests? → **RC1**.
4. Is it a pure cosmetic change with no behavior delta? → **RC0**.
5. Does the change require an action only the owner can perform? →
   **RC4** — stop, draft, hand to owner.

When in doubt, escalate one class up.

## HazMat Command RC3 surfaces (non-exhaustive)

These specific code paths are RC3 by default. A change to any of them
requires an independent reviewer and (for security/compliance/legal/
commercial) a third verifier.

- `api/_lib/authz.mjs` — single authz middleware
- `api/_lib/auditChain.mjs` — hash-chained audit ledger
- `api/audit/export.mjs` — regulator-export bundle
- `api/_lib/rate-limit.mjs` — tenant-aware rate limiter
- `api/scim/**` — SCIM 2.0 surface
- `api/auth/workos/**` — SSO surface
- `api/ocr/extract.mjs` — OCR endpoint
- `api/square/**` — billing surface
- `src/lib/provenance/**` — OCR field-provenance store
- `src/lib/documents/{shippingPaper172_202,placardSheet172_504,
  ergSheet172_602,dvirManifest,trainingDossier172_704}.ts` —
  regulator-facing builders
- `src/lib/documents/regressionHarness.ts` — visual regression
  harness for the above
- `src/lib/regulatory/**` — 49 CFR + TDG rule engines
- `src/lib/mfa/**` — MFA enrollment surface
- `src/lib/scim/**` — SCIM helpers
- `src/i18n/fr.json` — certified FR translation bundle (regulator-
  facing)
- `src/components/trust/**` — public trust portal artifacts
- `vercel.json` — CSP / headers / rewrites
- `scripts/audit-merkle-anchor.mjs` — nightly anchor producer
- `scripts/env-allowlist.json` — env-var allow-list
- `supabase/migrations/**` — schema migrations
- `tests/inventory/skipped-coverage.test.js` — coverage CI gate
  itself
- `docs/iso27001/**` — ISMS scaffolding
- `docs/compliance/**` — public-facing compliance artifacts
- `docs/security/threat-model.md` — STRIDE model
- `docs/rfp/answer-bank.md` — RFP answers (any change is a public
  commercial-claims change)
- `marketing/**` (any externally-visible page or copy)

A change to an RC2/RC1 file may still be tagged RC3 if it materially
alters one of the surfaces above (for example, a `src/pages/Settings/
Security.jsx` change that re-orders MFA enrollment steps).

## Anti-patterns

- Tagging an authz change RC2 to skip the independent reviewer rule —
  always RC3.
- Tagging a doc-only change touching `docs/rfp/answer-bank.md` as RC1
  to avoid the substantiation review — it is RC3 because it is a
  commercial claim.
- Bundling an RC3 change with a swath of RC0/RC1 changes to dilute
  the review — split the PR.
