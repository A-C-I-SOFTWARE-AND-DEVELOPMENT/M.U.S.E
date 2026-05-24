# Skill — research-dossier-build

## Purpose

Produce a Research Dossier per
`docs/governance/05-research-dossier-standard.md` to justify a
non-trivial design, compliance, pricing, marketing, legal,
security, or product decision in HazMat Command.

## Triggers

- Any RC3 change per `docs/governance/03-change-risk-matrix.md`.
- Any new commercial claim per `governance/11`.
- Any new legal document per `governance/12`.
- Any pricing / packaging / vendor decision.
- Any change to a regulator-facing builder
  (`src/lib/documents/{shippingPaper172_202,placardSheet172_504,
  ergSheet172_602,trainingDossier172_704,dvirManifest}.ts`).
- Any change to the 49 CFR / TDG rule engines.

## Required Inputs

- The Decision Question (one sentence).
- The originating request / PR.
- The RC class.
- Who will consume the dossier.

## Research Required

Cite primary sources first. Use the source hierarchy from
`governance/05`:

1. 49 CFR Subchapter C / TDG schedules
2. NIST publications (SSDF, AI RMF, Privacy Framework, 800-53,
   800-218)
3. OWASP (SAMM, ASVS, MASVS)
4. ISO/IEC 27001:2022 + Annex A
5. GDPR + SCC, CCPA / CPRA
6. FTC truth-in-advertising
7. Google Play / Apple App Store policies
8. Vendor documentation (WorkOS, Square, Supabase, Sentry,
   Vercel, Base44, Capacitor)
9. Anthropic / OpenAI agent guidance
10. Practitioner commentary (friction signal only)

## Step-by-Step Method

1. Copy `docs/templates/research-dossier-template.md` to
   `docs/research/<YYYY-MM-DD>-<slug>.md`.
2. Fill the Decision Question and Why It Matters in one sentence
   each. If you can't, the question is not specific enough.
3. List the source hierarchy you'll consult.
4. Fetch and read each primary source; cite by URL + access date
   for external sources, file path + line number for repo
   sources.
5. Capture Market / Technical / Commercial Context and
   Competitor / Alternative Patterns.
6. Surface every contradiction or unknown found in the source
   set.
7. Enumerate 2–4 options. Each one paragraph.
8. Produce the Tradeoff Matrix with explicit criteria.
9. Recommend one option. State Confidence.
10. List What Would Change the Recommendation (falsification
    conditions).
11. State Go/No-Go for planning. If No-Go, list what's missing.
12. Link the dossier from the PR's Research artifacts field.

## Deliverable Format

A single markdown file under `docs/research/` matching the
template structure. Length is task-appropriate — 400–1,500 words
for most decisions; longer for benchmarks like the AEO install
research artifact.

## Quality Checklist

- [ ] Every claim cites a primary source or a repo path
- [ ] Tradeoff matrix has criteria as rows, options as columns
- [ ] Confidence rating ≤ what the evidence supports
- [ ] Falsification conditions are concrete
- [ ] Linked from the originating PR

## Escalation Triggers

- If no primary source exists for the question, escalate to the
  owner via `AskUserQuestion`.
- If the recommendation requires owner action (L4), file the
  dossier and surface the action explicitly.

## Related Agents

- Chief Research Analyst (Research & Evidence Bureau, division 02)
- Citation Integrity Agent (division 02)

## Related Artifacts

- `docs/templates/research-dossier-template.md`
- `docs/research/autonomous-enterprise-organization-benchmark-2026-05-17.md`
  (worked example)
