---
name: research-dossier-build
description: Use when an RC3 change, new commercial claim, new legal document, pricing decision, vendor choice, regulator-facing change, or 49 CFR / TDG rule-engine change is being proposed. Produces a research dossier under docs/research/ using docs/templates/research-dossier-template.md with primary-source citations.
---

# research-dossier-build

## When to use

Activated automatically by `chief-orchestrator` whenever the
Research-Before-Plan rule in `AGENTS.md` applies. Manually invoke
this skill any time a decision needs evidence a third party can
verify.

## Inputs

- The proposed change (1-paragraph problem statement).
- The decision the dossier must support.
- Initial source URLs / regulatory references known to the
  requester (optional).

## Method

1. Open `docs/templates/research-dossier-template.md`. Copy it to
   `docs/research/<topic>-<YYYY-MM-DD>.md`.
2. Identify primary sources. For regulatory: the 49 CFR section,
   the TDG paragraph, the ERG page, the UN/DOT number. For
   standards: the NIST SP, the OWASP rule page, the ISO 27001
   control list entry. For vendors: the vendor's own current docs
   page (with access date).
3. Quote, do not paraphrase, on binding clauses.
4. Distinguish:
   - **Officially supported** — the source covers the exact case.
   - **Inferred** — extrapolation; flag the open question.
5. Run `docs/skills/source-contradiction-analysis.md` if two
   sources disagree. Recommend the safer reading.
6. Produce the verdict: **supports** / **does not support** /
   **inconclusive** for the proposed action.
7. Add the file to the index reference list in the dossier and
   confirm `npm run governance:check` still passes (the index
   validator covers index links, not new research files).

## Output

`docs/research/<topic>-<YYYY-MM-DD>.md` with:

- problem statement,
- decision to support,
- primary-source citations with access dates,
- supported / inferred distinction,
- contradictions surfaced,
- verdict,
- recommended next step.

## Anti-patterns

- Citing a tutorial when the underlying standard exists.
- Paraphrasing 49 CFR / TDG text instead of quoting it.
- "Officially supported" with no URL and no section number.
- A verdict with no underlying citation.
