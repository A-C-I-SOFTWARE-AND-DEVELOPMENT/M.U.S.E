# Skill — app-store-policy-audit

## Purpose

Verify a Capacitor Android release against current Google Play
policies. iOS is deferred (no iOS surface today). Submission
itself is L4 owner-only per `AGENTS.md`.

## Triggers

- Any change to the Capacitor / Android surface.
- Listing copy update (`PLAY_STORE.md`).
- Google Play policy change announcement.
- New permission requested by the app.

## Required Inputs

- `PLAY_STORE.md` (current submission playbook).
- `android/` directory (the Capacitor scaffold).
- `capacitor.config.json` (app id `com.hazmatcommand.app`).
- `public/manifest.json`.
- Permission set requested by the app.

## Research Required

- Current Google Play Developer Program Policies.
- Data safety form requirements.
- Target API level requirements (Play's annual ratchet).

## Step-by-Step Method

1. Confirm target API level meets Play's current floor.
2. Confirm permissions requested are justified — every
   permission must have a clear in-app use case.
3. Confirm the Data Safety form aligns with the privacy policy
   and DPA disclosures.
4. Confirm the feature graphic uses the brand colors (navy
   `#0f1620` + gold `#d4a830`). `PLAY_STORE.md` has noted a
   prior gradient that doesn't match brand — flag if recurring.
5. Confirm listing copy does not overclaim any capability
   under stub mode (no "real-time email sync" unless the
   email integration is live; no "biometric MFA" unless
   `webauthn-platform-config` is cleared).
6. Confirm no "Deliberately left NOT-DONE" item from
   `PLAY_STORE.md` is implied as shipped in the listing.

## Deliverable Format

Play Store Policy Audit Memo: per-policy table of (compliant,
risk, recommended action).

## Quality Checklist

- [ ] Target API level OK
- [ ] Permissions justified
- [ ] Data Safety form matches privacy posture
- [ ] Brand colors correct
- [ ] No overclaim in listing
- [ ] Deliberately-NOT-DONE list respected

## Escalation Triggers

- A policy violation risk → halt listing update; route to App
  Store & Platform Policy Agent + Mobile Engineer.

## Related Agents

- App Store & Platform Policy Agent (Legal Office)
- Mobile / Capacitor Engineer (Engineering Factory)
- ASO / SEO & Store Conversion Agent (Commercial Office)

## Related Artifacts

- `PLAY_STORE.md`
- `docs/templates/claims-substantiation-template.md`
