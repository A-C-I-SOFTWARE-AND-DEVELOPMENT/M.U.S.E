# Skill — erg-source-validation

## Purpose

Verify the offline ERG bundle's source integrity and per-entry
correctness against the published PHMSA ERG 2024 and (when
ingested) the CANUTEC ERG 2024.

## Triggers

- Bundle rebuild (`scripts/build-erg-bundle.mjs`).
- Adding TC-specific entries (closes `tc-erg-2024`).
- A customer reports an incorrect Guide reference for a UN number.
- §172.602 ERG sheet builder (`src/lib/documents/
  ergSheet172_602.ts`) regression.

## Required Inputs

- The current bundle output and its SHA-256.
- `scripts/build-erg-bundle.mjs` source.
- `src/lib/documents/ergRuntime.ts` (single-flight boot, key
  normalisation).
- `src/lib/documents/ergBundle.ts` (loader).
- The published PHMSA ERG 2024 PDF reference.

## Research Required

- PHMSA ERG 2024 (363 entries today).
- CANUTEC ERG 2024 for the TC-specific entries (open
  `tc-erg-2024` stub).
- 49 CFR §172.602 (ERG access on the vehicle).

## Step-by-Step Method

1. Run `scripts/build-erg-bundle.mjs` to produce a fresh
   bundle.
2. Confirm SHA-256 of the bundle matches expectations; update
   the constant if the bundle legitimately changed.
3. Sample 10 random UN numbers; cross-check the Guide
   assignment, ERG entry name, initial-isolation distance,
   protective-action distance against the published ERG 2024.
4. Confirm the bundle's `source` discriminator
   (`phmsa-erg-2024` today) is set per entry.
5. If TC entries are being added: verify the parser merges
   under `source: 'tc-erg-2024'` and the placard nomenclature
   translator for class 9 / TIH works.
6. Run `npm test -- erg` and the §172.602 builder tests.
7. Confirm the runtime helper at
   `src/lib/documents/ergRuntime.ts` correctly serves
   `getErgEntry(un)` from the verified bundle.

## Deliverable Format

An ERG Source Validation memo: sampled UN checks, source
discriminator coverage, test results.

## Quality Checklist

- [ ] Sampled UN checks pass
- [ ] Source discriminator correct per entry
- [ ] `npm test -- erg` green
- [ ] §172.602 sheet builder consumes the verified bundle

## Escalation Triggers

- A misassigned Guide number → Risk Controller; release freeze
  under `governance/09` trigger 3 (false-compliant output from
  §172.602 builder).

## Related Agents

- PHMSA / ERG Source Agent (Research Bureau)
- OCR / Document Intelligence Engineer (Engineering Factory)
- Compliance Engine Engineer (Engineering Factory)

## Related Artifacts

- `scripts/build-erg-bundle.mjs`
- `tests/lib/documents/ergBundle.test.js` (when present)
