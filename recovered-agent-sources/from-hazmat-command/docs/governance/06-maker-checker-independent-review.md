# 06 — Maker-Checker Independent Review

**Status:** Installed 2026-05-17

For RC3 work the builder cannot be the sole verifier. Maker-checker
separation reduces the risk of confirmation bias and lets the AEO
catch defects an individual agent would miss.

## Three roles

- **Builder.** The agent that produced the change.
- **Independent reviewer.** A different agent / session / human who
  reviews the change end-to-end. Cannot be the Builder.
- **Verifier.** A third role required for security, compliance,
  legal, and commercial-claims work. Verifies evidence cited
  (test results, regulatory citations, threat-model entries,
  claims-substantiation memos) actually resolves to what the PR
  claims it does.

## When required

| Work | Builder | Independent reviewer | Verifier |
|---|---|---|---|
| RC0 / RC1 | required | optional | optional |
| RC2 (general) | required | recommended | not needed |
| RC2 with public-claim or doc-restructure impact | required | **required** | not needed |
| RC3 (general engineering) | required | **required** | not needed |
| RC3 security / authz / tenant isolation | required | **required** | **required** |
| RC3 compliance evidence (`docs/iso27001/**`, `docs/compliance/**`, `docs/security/**`, `docs/rfp/answer-bank.md`) | required | **required** | **required** |
| RC3 commercial claim (any externally-visible surface) | required | **required** | **required** |
| RC3 legal document | required | **required** | **required** |
| RC3 release-policy change | required | **required** | **required** |

## HazMat-specific examples

- **Compliance rule change** — e.g. tightening the §172.504
  placard threshold rule.
  - Builder: Compliance Engine Engineer (Engineering Factory).
  - Reviewer: Independent QA/V&V Agent (Assurance Office).
  - Verifier: Compliance Evidence Agent (Assurance) — confirms
    the change is reflected in `docs/iso27001/statement-of-
    applicability.md` A.5.31 and the `docs/rfp/answer-bank.md` if
    cited.

- **Security/authz change** — e.g. adding a new role to
  `api/_lib/authz.mjs::requireTenant`.
  - Builder: Security/Authz Engineer (Engineering Factory).
  - Reviewer: Principal Security Architect (Assurance).
  - Verifier: Threat Modeling Agent — STRIDE entry in
    `docs/security/threat-model.md` updated.

- **Pricing recommendation** — e.g. changing the Team plan from
  $79 to $99.
  - Builder: Pricing Science Agent (Commercial Office).
  - Reviewer: Chief Commercial Officer + Packaging & Entitlements
    Agent.
  - Verifier: Claims Substantiation Agent — Pricing Study
    artifact exists and supports the new price; `governance/11`
    C5 evidence aligns with `src/pages/Billing.jsx`.

- **Legal agreement** — e.g. drafting the Pilot Agreement.
  - Builder: Contract Drafting Agent (Legal Office).
  - Reviewer: Legal Consistency Auditor.
  - Verifier: External counsel via the owner (counsel-review
    banner per `governance/12`).

- **Public marketing claim** — e.g. updating the `/trust` portal
  attestation pill copy.
  - Builder: HazMat Market Positioning Agent (Commercial).
  - Reviewer: UX/UI Trust Agent (Product Studio).
  - Verifier: Claims Substantiation Agent + Compliance Evidence
    Agent.

## How to capture the evidence

The PR template has fields for Builder, Independent reviewer,
Verifier, and Maker-checker evidence link. Reviews can be:

- In-PR review comments (most common); the verifier writes a
  short approval note in the PR description.
- A separate review memo committed under `docs/research/` or
  `docs/governance/` with a short link from the PR.
- A subagent task contract result captured under
  `docs/governance/08-artifact-registry-and-memory-discipline.md`.

The form does not matter; the discipline does. A PR claiming RC3
status without a captured independent review is incomplete and
fails G0 (Agent Evidence Gate) under `PUBLISH.md`.

## Anti-patterns

- The Builder reviewing their own work and claiming the maker-
  checker step is satisfied.
- A reviewer who only LGTM'd the PR with no notes — there must be
  a specific evidence pointer.
- Treating CI (G1) as the independent reviewer. CI is a tool, not
  an agent — it has no judgment about evidence quality.
- Using the same subagent as Builder and Reviewer in parallel.
  Parallelism with the same role identity is concurrency, not
  separation of duties.
