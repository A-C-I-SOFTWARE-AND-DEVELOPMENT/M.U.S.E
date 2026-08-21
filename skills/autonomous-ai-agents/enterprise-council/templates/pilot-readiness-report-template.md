# Pilot Readiness Report — <pilot / demo name>

**Date:** YYYY-MM-DD
**Demo target date:** YYYY-MM-DD
**Author:** Pilot Readiness Judge (Assurance Office)
**Demo branch / commit:** <branch + SHA>
**Vercel preview URL:** <url>

## Pre-Flight Checklist

- [ ] `npm test` reports 727/727 (or current baseline) green on demo commit
- [ ] `npm run lint` clean
- [ ] `npm run typecheck` clean
- [ ] `npm run build` exit 0
- [ ] `npm run i18n:check` exit 0
- [ ] `npm test -- tests/inventory/skipped-coverage.test.js` 5/5
- [ ] `npm run governance:check` exit 0 (if AEO governance touched)
- [ ] No open P0 in `docs/inventory/blockers-final.md` affecting demo path
- [ ] Square stays in stub mode (do not flip env vars for demo)
- [ ] For Canadian demos: FR rendering labeled "draft-not-certified" per `certified-translator-engagement`
- [ ] No claim in demo deck contradicts `governance/11` substantiation

## Demo Path Rehearsed

- [ ] Sign-up / login
- [ ] Onboarding
- [ ] Load create
- [ ] Document upload
- [ ] OCR review with provenance badges
- [ ] Validation pass (49 CFR rule engine)
- [ ] Assignment (with any required-endorsement check — note wire-up status)
- [ ] Audit timeline
- [ ] Trust portal walk
- [ ] Any custom demo step: <add here>

## Risks / Known Limitations to Disclose

- <e.g. "Square is in demo mode; we'll show the upgrade flow but no real charge">
- <e.g. "Bilingual FR rendering visible but labeled draft per CTTIC/OTTIAQ/ATIO pending">

## Freeze-Window Honored

- [ ] No governance-doc commit in the 24h before demo (per `PUBLISH.md` pilot-week freeze)
- [ ] No runtime change in the 24h unless owner-approved safety update

## Sign-Off

- [ ] **GO** — demo is shippable
- [ ] **NO-GO** — <reason; remediation plan; routed to Risk Controller>

**Pilot Readiness Judge:** <date>
**Risk Controller (if NO-GO):** <date>
