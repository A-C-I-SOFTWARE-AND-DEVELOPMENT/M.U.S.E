---
paths:
  - "docs/**/*.md"
  - "marketing/**"
  - "README.md"
  - "AGENTS.md"
  - "PUBLISH.md"
  - "HANDOFF.md"
  - "SKIPPED.md"
  - "AUDIT.md"
---

# Docs, claims, legal, and commercial

**Path scope (auto-activates):** documentation and marketing surfaces
per the `paths` frontmatter above. Original list: `docs/**`,
`marketing/**`, `docs/rfp/**`,
`docs/iso27001/**`, `docs/compliance/**`, `docs/security/**`,
`README.md`, `AGENTS.md`, `PUBLISH.md`, `HANDOFF.md`,
`docs/AUTONOMOUS_ORGANIZATION_INDEX.md`.

**Authority:** `AGENTS.md`,
`docs/governance/11-commercial-claims-substantiation-policy.md`
(C1–C6 classes; aspirational labeling rules),
`docs/governance/12-legal-document-generation-policy.md`,
`docs/governance/15-doc-freshness-and-contradiction-control.md`.

Words in docs/marketing/rfp materials end up in front of customers,
regulators, and counsel. Do not overstate. Do not invent. Cite or
remove.

## Discipline

1. **No overstated claims.** Words like "industry-leading",
   "best-in-class", "enterprise-grade", "AI-powered" are not
   allowed without a citation. If the claim is aspirational, label
   it aspirational per
   `docs/governance/11-commercial-claims-substantiation-policy.md`.
2. **Citations in research artifacts.** Every research dossier
   carries citations a third party can verify (NIST SP, OWASP rule,
   ISO 27001 control, 49 CFR section, TDG paragraph, vendor doc URL
   with date). Use `templates/research-dossier-template.md`.
3. **Legal drafts stay drafts.** Every contract, MSA, SOW, DPA, NDA,
   pilot agreement, ToS, privacy policy, sub-processor list, or
   security addendum carries the mandatory counsel-review banner.
   The Legal Office is in `.claude/agents/legal-policy-contracts-trust-office.md`.
   No agent executes / signs / sends a legal document.
4. **Procurement and compliance statements are traceable.**
   `docs/rfp/answer-bank.md` and ISO 27001 / compliance evidence
   matrices link to the underlying control / test / log they rely
   on. If the trace breaks, the claim breaks.
5. **Doc freshness.** When code or release notes contradict an
   older doc, follow
   `docs/governance/01-source-of-truth-hierarchy.md` and
   `docs/governance/15-doc-freshness-and-contradiction-control.md`.
   Do not amplify the stale claim.
6. **Marketing copy follows the commercial activation trigger.**
   Externally-visible copy changes engage the Commercial Office
   (`.claude/agents/commercial-strategy-growth-office.md`) and
   record evidence under
   `templates/claims-substantiation-template.md`.
7. **AGENTS.md size ceiling.** Constitutional surface stays at the
   documented ceiling (currently 350 lines). Additions to AGENTS.md
   require a corresponding deletion or a deliberate ceiling
   adjustment with PR justification.

## Anti-patterns rejected on sight

- A new product claim added to marketing/docs without a citation.
- A legal draft without the counsel-review banner.
- An RFP answer that cannot be traced to evidence under
  `docs/compliance/`, `docs/iso27001/`, `docs/security/`, or
  `docs/runbooks/`.
- A "we are SOC 2 compliant" claim — we are not. Use the
  aspirational labeling rule.
- A "100% accurate" claim about OCR, rule-engine, or pricing.
- A new doc that duplicates an existing doc rather than linking it.
