# Skill — ocr-confidence-provenance-audit

## Purpose

Audit the OCR pipeline (`api/ocr/extract.mjs`,
`src/lib/provenance/**`, `src/components/ocr/**`) for confidence
calibration, provenance correctness, and proper labeling of
user-corrected vs. system-OCR'd fields.

## Triggers

- Any change to the OCR pipeline or provenance store.
- An OCR provider swap (Tesseract.js → Gemini, etc.).
- A reported confidence mis-calibration.
- A reported wrong-provenance badge in the UI.

## Required Inputs

- The provenance schema at `src/lib/provenance/types.ts`.
- The shim at `src/lib/provenance/provenanceStore.js`.
- The badge component `src/components/ocr/ProvenanceBadge.jsx`.
- The review panel `src/components/ocr/OcrReviewPanel.jsx`.

## Research Required

- 49 CFR §172.201 (shipping paper accuracy obligations) — drives
  why provenance matters.
- ISO 27001:2022 A.5.33 (records protection).

## Step-by-Step Method

1. Confirm every regulated field rendered in
   `OcrReviewPanel.jsx` carries a `<ProvenanceBadge>`.
2. Confirm the four provenance sources are correctly labeled:
   `system-default`, `imported`, `ocr` (with confidence), and
   `user-corrected` (with `before_value` + `after_value` +
   `correcting_actor`).
3. Confirm `recordCorrection` writes exactly one row per
   correction.
4. Confirm tenant isolation: a record written under
   `tenant_x` is not readable by `tenant_y`.
5. Confirm confidence ranges are reasonable (Tesseract reports
   0–100 per field; downstream code maps to display).
6. Cross-reference the `supabase-provenance` stub status. Until
   it clears, persistence is in-process only — UI must not
   imply cross-session durability.
7. Confirm `ensureErgBundle()` is invoked where ERG entries
   surface (today: `OcrReviewPanel.jsx` does NOT yet call it
   per `offline-erg-runtime` Remaining UI work).

## Deliverable Format

OCR Provenance Audit Memo: badge coverage table, provenance
source coverage, tenant isolation status, confidence-range
review, persistence gap.

## Quality Checklist

- [ ] All regulated fields badged
- [ ] All four sources represented
- [ ] Correction creates one row
- [ ] Tenant isolation confirmed (in-shim today)
- [ ] No durability overclaim in UI

## Escalation Triggers

- Wrong provenance label on a regulator-facing field → halt;
  Risk Controller (false-compliant output risk).
- Cross-tenant provenance read → release freeze under
  `governance/09` trigger 1.

## Related Agents

- OCR / Document Intelligence Engineer (Engineering Factory)
- Compliance Engine Engineer (Engineering Factory)
- Independent QA / V&V Agent (Assurance Office)

## Related Artifacts

- `tests/lib/provenance/provenanceStore.test.js`
- `tests/lib/provenance/types.test.js`
