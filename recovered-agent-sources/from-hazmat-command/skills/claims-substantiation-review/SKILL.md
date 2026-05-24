---
name: claims-substantiation-review
description: Use whenever externally-visible copy is being added or edited (marketing, RFP, trust portal, in-app onboarding text). Classifies each claim C1–C6 per docs/governance/11-commercial-claims-substantiation-policy.md and either substantiates it with a citation or labels it aspirational. Aligned with docs/skills/claims-substantiation-review.md (the AEO SOP).
---

# claims-substantiation-review

## When to use

Any externally-visible copy change: marketing pages, RFP answers,
trust portal, in-app onboarding, public ToS / Privacy, README,
release notes that face customers, store listings, press copy.

## Method

1. **Extract every claim.** Read the proposed copy line by line.
   Pull each factual / performance / compliance / security claim
   into a list.
2. **Classify per the policy.**
   - C1 — verifiable factual (e.g., "supports 5 roles").
   - C2 — benchmarked performance (must cite the benchmark).
   - C3 — compliance / regulatory (must cite the standard).
   - C4 — security control (must trace to evidence under
     `docs/security/`, `docs/iso27001/`, `docs/compliance/`).
   - C5 — competitive comparison (must cite competitor doc / test).
   - C6 — aspirational (must carry an aspirational label per the
     policy).
3. **Substantiate or label.** For each claim: cite or label
   aspirational. No middle ground.
4. **Reject overstatements.** "Industry-leading", "best-in-class",
   "enterprise-grade", "100% accurate", "AI-powered" are rejected
   on sight unless cited.
5. **Output substantiation record.** Use
   `docs/templates/claims-substantiation-template.md` and commit
   under `docs/research/` or `docs/commercial/` per repo
   convention.

## Output

- A claim-by-claim list with classification, source / label, and
  approved final wording.
- The substantiation record committed.

## Anti-patterns

- A marketing edit that adds a new C2 / C3 / C4 claim with no
  citation.
- An aspirational claim without the label.
- A competitor claim ("faster than X") with no benchmark.
