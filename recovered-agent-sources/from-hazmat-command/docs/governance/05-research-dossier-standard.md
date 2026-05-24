# 05 — Research Dossier Standard

**Status:** Installed 2026-05-17

A Research Dossier is a small, structured document that justifies a
non-trivial design, compliance, pricing, marketing, legal, security,
or product decision. It exists so future agents can audit the reasoning,
not just the outcome.

## When required

A dossier is **required** before:

- any RC3 change (`governance/03`);
- any new commercial claim that will appear on `/trust`,
  `marketing/`, `docs/rfp/answer-bank.md`, the `/Billing` page, or
  app-store metadata;
- any new legal document (NDA, MSA, SOW, DPA, pilot agreement, ToS,
  privacy policy, retention policy);
- any pricing or packaging decision;
- any new dependency, vendor selection, or architecture change that
  introduces a new tool or backend;
- any change to a regulator-facing document builder
  (`src/lib/documents/{shippingPaper172_202,placardSheet172_504,
  ergSheet172_602,trainingDossier172_704,dvirManifest}.ts`);
- any change to compliance evidence (`docs/iso27001/`,
  `docs/compliance/`);
- any change to the 49 CFR or TDG rule engines
  (`src/lib/regulatory/**`).

A dossier is **recommended** before any RC2 change that introduces
new file structure or a new agent / skill / workflow.

A dossier is **not required** for RC0 or RC1 changes (typos,
localized bug fixes covered by existing tests).

## Lightweight variant

If the decision is small and the answer is obvious from primary
sources, a "lightweight dossier" is acceptable: 200–400 words, only
the sections marked **L** below, plus one sentence per other section
documenting why depth was not warranted. Anything claimed as
"obvious" must still cite the primary source.

## Required structure

Use the template at
`docs/templates/research-dossier-template.md`. Required sections
(✓ = required, **L** = required in lightweight variant):

| # | Section | ✓ | **L** | Notes |
|---|---|---|---|---|
| 1 | **Decision Question** | ✓ | ✓ | One sentence. Specific. |
| 2 | **Why It Matters** | ✓ | ✓ | What breaks or fails to ship if this decision is wrong. |
| 3 | **Source Hierarchy** | ✓ |  | List sources by tier (primary regulation > authoritative standards > vendor docs > practitioner). |
| 4 | **Official Sources** | ✓ | ✓ | Direct citations: 49 CFR sections, TDG schedules, NIST publications, ISO controls, GDPR articles, FTC guides, vendor docs by URL. |
| 5 | **Market / Technical / Commercial Context** | ✓ |  | What HazMat Command's current state is on this question; what competitors / standards do. |
| 6 | **Competitor or Alternative Patterns** | ✓ |  | Concrete patterns from at least 2 alternatives. |
| 7 | **Practitioner Friction** |  |  | Optional. Only if relevant — informs but never authorizes. |
| 8 | **Contradictions / Unknowns** | ✓ |  | Anywhere sources disagree, or where we do not know. |
| 9 | **Options Compared** | ✓ |  | 2–4 options. Each with one paragraph. |
| 10 | **Tradeoff Matrix** | ✓ |  | Table with criteria as rows, options as columns. |
| 11 | **Recommendation** | ✓ | ✓ | One option, clearly stated. |
| 12 | **Confidence** | ✓ | ✓ | High / Medium / Low + one sentence why. |
| 13 | **What Would Change the Recommendation** | ✓ |  | Falsification conditions. |
| 14 | **Go/No-Go for Planning** | ✓ | ✓ | Explicit. If "no-go," what is missing. |

## Source hierarchy

Cite primary sources before practitioner commentary. HazMat-specific
ordering:

1. **49 CFR Subchapter C (US HazMat regulations) and equivalent
   Transport Canada TDG schedules** — for regulator-facing content.
2. **NIST publications** (SSDF, AI RMF, Privacy Framework, 800-53,
   800-218) — for security, governance, and SDLC questions.
3. **OWASP** (SAMM, ASVS, ASVS L1/L2, MASVS for mobile) — for
   application security.
4. **ISO/IEC 27001:2022** and Annex A controls — already mapped in
   `docs/iso27001/statement-of-applicability.md`.
5. **GDPR text and SCC (2021/914), CCPA / CPRA** — for privacy and
   data-handling.
6. **FTC truth-in-advertising guides** — for commercial claims.
7. **Google Play / Apple App Store policies** — for store submission
   (Capacitor Android relevant today; iOS deferred).
8. **Vendor documentation** — WorkOS, Square, Supabase, Sentry,
   Vercel, Base44, Capacitor — for integration specifics.
9. **Anthropic / OpenAI engineering documentation** — for
   agent-organization patterns.
10. **Practitioner commentary** — blog posts, GitHub discussions —
    only to confirm friction, never to authorize a decision.

## Where dossiers live

Save under `docs/research/<YYYY-MM-DD>-<short-slug>.md`. The Wave 1
benchmark for this install is at
`docs/research/autonomous-enterprise-organization-benchmark-2026-05-17.md`
and can be used as a worked example.

The agent that authored the dossier links it from the PR (in the
"Research artifacts" field of the PR template) and updates the
artifact registry (`governance/08`) by adding a line to
`docs/AUTONOMOUS_ORGANIZATION_INDEX.md` if it is a benchmark-class
dossier.

## Anti-patterns

- A "research dossier" that is mostly a recommendation with no
  source citations.
- Citing a Google search snippet without naming the underlying
  primary source.
- Skipping the Tradeoff Matrix because there's only one option being
  considered — that itself is a finding; document it.
- Marking confidence "High" with zero falsification conditions.
- Producing a dossier and then making a different decision in the
  implementation. The dossier must be updated or a follow-up
  decision memo issued.
