# Skill — tdg-crossborder-review

## Purpose

Audit cross-border (US ↔ Canada) hazmat consignment correctness:
the TDG dataset (Schedule 1 / 2 / 3) ingested in Stage 4 (R4-X),
the border-mode toggle, and the bilingual EN/FR rendering layer.

## Triggers

- A change to `src/lib/regulatory/tdg/**`.
- A change to `src/lib/documents/bilingualRender.ts`.
- A Canadian-bound or Canadian-origin consignment flow added /
  modified.
- A TDG regulation update.
- A new certified-translator round (closes
  `certified-translator-engagement`).

## Required Inputs

- The current TDG dataset: 125 Schedule 1 entries, 30 Schedule 2
  special provisions, 22 Schedule 3 ERAP requirements.
- The border-mode toggle implementation.
- `src/i18n/fr.json` + `src/i18n/fr.cert-log.md` (or whichever
  cert log exists today; see `certified-translator-engagement`).

## Research Required

- Transport Canada TDG Regulations (SOR/2001-286), specifically
  Schedule 1, 2, 3.
- CANUTEC ERG 2024.
- US-Canada cross-border guidance from PHMSA and TC.

## Step-by-Step Method

1. For a sample consignment (UN number, class, packing group),
   confirm both PHMSA and TDG records resolve.
2. Confirm the border-mode toggle correctly routes the
   consignment through the right rule engine.
3. Confirm ERAP entries (Schedule 3) fire when applicable.
4. Confirm the bilingual rendering layer
   (`bilingualRender.ts`) substitutes FR strings when
   `locale: 'fr'` is set.
5. **Critical:** if the rendered output is regulator-facing FR,
   confirm `src/i18n/fr.cert-log.md` marks the relevant
   section `certified: true`. If not, the renderer must refuse
   (R4-Q+1 follow-up gate) — flag as a compliance gap if the
   gate is not yet wired.
6. Run `npm test -- tdg`, `npm test -- bilingualRender`,
   `npm run i18n:check`.

## Deliverable Format

A TDG Cross-Border Memo: sampled consignment outcomes,
border-mode correctness, bilingual gate status.

## Quality Checklist

- [ ] Schedule 1/2/3 lookups correct
- [ ] Border-mode routing correct
- [ ] ERAP firing logic correct
- [ ] `i18n:check` exit 0
- [ ] FR cert-log gate respected (or gap flagged)

## Escalation Triggers

- A Canadian-regulator-facing FR PDF generated without certified
  strings → Risk Controller.
- A TDG rule mismatch with the US 49 CFR equivalent that
  would mis-route a consignment → Risk Controller.

## Related Agents

- Canadian TDG Research Agent (Research Bureau)
- Compliance Engine Engineer — bilingual (Engineering Factory)
- HazMat Market Positioning Agent (Commercial — Canadian
  readiness)

## Related Artifacts

- `docs/runbooks/translation-pipeline.md`
- `docs/iso27001/statement-of-applicability.md` A.5.31
