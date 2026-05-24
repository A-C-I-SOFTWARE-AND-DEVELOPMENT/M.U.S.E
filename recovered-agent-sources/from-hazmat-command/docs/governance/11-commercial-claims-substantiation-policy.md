# 11 — Commercial Claims Substantiation Policy

**Status:** Installed 2026-05-17

Every externally-visible commercial claim made by HazMat Command
must be either (a) tied to repository evidence, or (b) explicitly
labeled aspirational. This policy operationalizes FTC
truth-in-advertising guidance and the anti-claims discipline already
established in `docs/iso27001/README.md` ("scaffold not certify").

## What counts as a commercial claim

A claim is any externally-visible statement that a reasonable buyer
could interpret as a representation about HazMat Command's
capabilities, security posture, compliance status, customer base, or
pricing. Surfaces include:

- the public marketing site (`marketing/`) and any future copy on
  `hazmatcommandcore.org`;
- the `/trust` portal (`src/components/trust/**`,
  `src/pages/Trust.jsx`);
- the `/Billing` page (`src/pages/Billing.jsx`, including plan
  cards);
- app-store metadata (`PLAY_STORE.md` and the Play Console listing);
- the RFP answer bank (`docs/rfp/answer-bank.md`) and the dry-run
  scorecard (`docs/rfp/dry-run.md`);
- sales decks, one-pagers, case studies, blog posts, ad copy, email
  campaigns;
- press / PR statements;
- in-app onboarding copy that promises capability.

Internal docs (`docs/runbooks/`, `docs/governance/`, `HANDOFF.md`,
this file) are not commercial claims for the purposes of this policy
— but the moment any of their content is reproduced externally, this
policy applies.

## Claim classes

| Class | Definition | HazMat examples | Required substantiation |
|---|---|---|---|
| **C1 — Factual capability** | A statement about what the product does today, verifiable in code or tests | "Generates §172.202 shipping papers" | A reproducible test or screenshot citing the responsible code path (e.g., `src/lib/documents/shippingPaper172_202.ts` + `tests/lib/documents/shippingPaper172_202.test.js`) |
| **C2 — Technical / security** | A statement about how the product behaves under attack or load | "Tenant-isolated", "Hash-chained audit ledger", "RS256 JWKS signature verification" | Code reference + test reference + threat-model entry. For tenant-isolation: `api/_lib/authz.mjs::requireTenant`, the RLS migration files, the 1,000-iteration cross-tenant fuzz, and `docs/security/threat-model.md`. |
| **C3 — Compliance / regulatory** | A statement about meeting a regulation or framework | "49 CFR §172.202 compliant", "ISO 27001 scaffolded", "GDPR Art. 28 DPA available" | Direct citation to the regulation/standard + the artifact that meets it. ISO 27001 is "scaffolded, not certified" today — must be labeled accordingly per `docs/iso27001/README.md`. |
| **C4 — Customer / traction** | A statement about who uses the product, how many, or with what outcome | "Used by N carriers", "Reduced inspection prep time by X%" | Customer reference must be on file with written permission. Quantitative claims require source data and methodology citation. The customer-name scrub in the v1.0.0 release notes confirms no current customer is named in-repo. |
| **C5 — Pricing / commercial terms** | A statement about price, plan, entitlement, or trial | "Solo $29 · Team $79 · Fleet $199 · Enterprise", "10-day pilot" | Must match the live plan registry in `src/pages/Billing.jsx` and the `governance/10` feature-flag registry. Any discrepancy is a defect. |
| **C6 — Aspirational** | A statement of future intent | "Will support FMCSA Drug & Alcohol Clearinghouse integration", "Targeting SOC 2 Type II in 2027" | Must be labeled with explicit forward-looking language. Cannot imply current capability. |

## Substantiation workflow

For any new commercial claim:

1. **Identify the class** (C1–C6).
2. **Locate or create evidence:**
   - C1: file + test path
   - C2: file + test path + threat-model entry
   - C3: regulation citation + ISMS evidence
   - C4: signed customer reference + methodology
   - C5: live plan registry + flag registry
   - C6: forward-looking labeling
3. **Run the `claims-substantiation-review` skill** (`docs/skills/`)
   — a maker-checker workflow under `governance/06`.
4. **Capture the result in a Claims Substantiation memo** using
   `docs/templates/claims-substantiation-template.md`. The memo is
   linked from the PR description that introduces the claim.
5. **Counsel-review the claim** for C3 (regulatory) and C4
   (customer-reference) classes per `governance/12`.
6. **Publish the claim** only after CI is green, the memo is filed,
   and the owner approves.

## Aspirational labeling rules

If a claim is aspirational (C6), it must:

- use one of: "intended", "planned", "in progress", "targeting",
  "roadmap";
- not use: "supports", "has", "is", "delivers" in the present tense
  for the capability claimed;
- carry a date or condition: "by Q4 2026", "once Supabase is
  provisioned", "after WorkOS procurement";
- live alongside the stub or blocker it depends on
  (`SKIPPED.md` entry name).

Examples taken from current SKIPPED.md entries:

| Capability | Today's status | Aspirational copy |
|---|---|---|
| Real Sentry telemetry | Stubbed (`sentry-dsn`) — SDK loads when `VITE_SENTRY_DSN` is set | "Sentry-ready — production telemetry activates once the DSN is provisioned" |
| Hardware-MFA enforcement | Stubbed (`mfa-enforcement`, `webauthn-platform-config`) | "MFA enrollment surface live; hardware-MFA enforcement planned after WorkOS procurement" |
| External time-stamp anchoring | Stubbed (`rfc3161-tsa-procurement`, `opentimestamps-calendar`) | "Audit chain hash-anchored internally; RFC 3161 + OpenTimestamps external anchoring planned" |
| Certified French rendering | Bundle live but flagged "draft-not-certified" (`certified-translator-engagement`) | "Bilingual rendering available; certified French copy pending CTTIC/OTTIAQ/ATIO translator engagement — do not use FR for regulator-facing PDFs until the certification log marks each section certified" |

## Existing repo claims to preserve

These claims are already substantiated and may be reused without
additional review:

| Claim | Evidence |
|---|---|
| "49 CFR §§172.202, .504, .602, .704, 396.11 document set" | `docs/releases/v1.0.0-enterprise-ready.md`; `src/lib/documents/*.ts` |
| "Hash-chained tamper-evident audit ledger" | `api/_lib/auditChain.mjs`; threat-model entry; STRIDE coverage |
| "Tenant isolation enforced at application layer" | `api/_lib/authz.mjs::requireTenant`; `tests/api/_lib/authz.test.js`; `tests/supabase/cross-tenant-fuzz.test.js` (1,000 iterations) |
| "RS256 JWKS signature verification" | `api/_lib/workos.mjs::verifyViaJwks`; `tests/api/_lib/workos.test.js` |
| "SCIM 2.0 Users + Groups + ServiceProviderConfig" | `api/scim/v2/*.mjs`; SCIM test suite |
| "8 tenant-scoped tables with RLS migrations authored" | `supabase/migrations/20260515_rls_*.sql`; `docs/security/rls-policy-catalog.md`; `tests/supabase/rls.policy.test.js` |
| "Bilingual EN/FR rendering layer" | `src/i18n/`; `npm run i18n:check`; `src/lib/documents/bilingualRender.ts` |
| "ISO 27001:2022 scaffolding (93-control SoA, risk register, 11 policies, internal audit programme, management-review template)" | `docs/iso27001/` — explicitly labeled "scaffold, not certify" |
| "Brand colors navy `#0f1620` + metallic gold `#d4a830`" | `src/lib/brandColors.js`; `AGENTS.md` |

Any change to these claims (text or capability scope) triggers a new
substantiation review.

## Anti-patterns

- "AI-powered hazmat compliance" — drops the operator-first voice
  AGENTS.md establishes and is a marketing cliche; replace with the
  capability claim plus the evidence.
- "Industry-leading audit trail" — superlative without comparison;
  replace with the specific property (hash-chained + RFC-3161
  anchored when those vendors are provisioned).
- "Trusted by the largest carriers" — C4 claim without signed
  references; remove until a reference is on file.
- "SOC 2 / ISO 27001 certified" — false today; allowed only with
  "scaffolded, not certified" qualifier per
  `docs/iso27001/README.md`.
- Reproducing language from a vendor's marketing site without
  verifying it matches HazMat's behavior.
