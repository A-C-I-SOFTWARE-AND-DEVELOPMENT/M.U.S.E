---
name: evidence-bundle-build
description: Use immediately after mission-brief-build. Assembles repo facts, external citations, prior decisions, applicable standards, and risks into 01-evidence-bundle.md using docs/templates/evidence-bundle-template.md. Every claim in downstream plans must trace back to an item in this bundle.
---

# evidence-bundle-build

## When to use

Council Mode step 2, after `00-mission-brief.md` exists. Also used
by deterministic workflows when a lightweight evidence bundle is
preferred over a full research dossier.

## Inputs

- The mission brief at `00-mission-brief.md`.
- Initial source URLs / regulatory references the requester
  already has (optional).
- Live repo facts (paths to read for current state, baseline test
  count, open PRs, ADRs that bind).

## Method

1. Copy `docs/templates/evidence-bundle-template.md` to
   `01-evidence-bundle.md` in the run folder.
2. Build the A (internal) table — facts grounded in repo paths,
   tests, ADRs, release notes, SKIPPED entries, claims-policy
   constraints. Each row carries the source path and date checked.
3. Build the B (external) table — primary citations with URLs and
   access dates. For regulatory: 49 CFR section, TDG paragraph,
   ERG page. For standards: NIST SP, OWASP rule, ISO/IEC control.
   For vendors: vendor doc URL.
4. For each evidence item used by downstream plans, fill the C
   (metadata) table — confidence, relevance, falsifiability.
5. Run `docs/skills/source-contradiction-analysis.md` if two
   sources disagree. Record the safer reading.
6. If a Research Dossier under `docs/research/` is required per
   `docs/governance/05-research-dossier-standard.md` (RC3, new
   claim, new vendor, regulator-facing, pricing/packaging change,
   major positioning), produce it first and reference it from the
   Evidence Bundle.
7. Note gaps explicitly. If a gap is gating, escalate to the
   owner before generating plans.
8. Write the Verdict: Sufficient / Sufficient-with-caveats /
   Insufficient.

## Output

`01-evidence-bundle.md` — the citation source every downstream
plan, red-team critique, and synthesis must reference.

## Anti-patterns

- Citing a tutorial when the underlying standard exists.
- Paraphrasing 49 CFR / TDG when the binding text is short enough
  to quote.
- "Officially supported" with no URL and no section number.
- An empty C (metadata) table on RC3 work.
- Pushing the evidence bundle to plan generation while the verdict
  is "Insufficient."
