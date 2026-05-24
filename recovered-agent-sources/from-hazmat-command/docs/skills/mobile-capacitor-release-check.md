# Skill — mobile-capacitor-release-check

## Purpose

Pre-flight a Capacitor Android release. Confirms `npx cap sync`
works, the Web Share Target / Android intent landing
(`src/pages/SharedUpload.jsx`, `MainActivity.java`,
`public/sw.js`) is intact, brand assets are in place, and Play
Store policy alignment is current. Submission itself is L4
owner-only.

## Triggers

- Any change to `android/`, `capacitor.config.json`,
  `public/manifest.json`, `public/sw.js`,
  `src/pages/SharedUpload.jsx`.
- Any Play Store listing update.
- Pre-pilot if the demo includes the Android app.

## Required Inputs

- `capacitor.config.json` (app id `com.hazmatcommand.app`).
- `public/manifest.json` (PWA + share_target declaration).
- `public/icons/` (192/512/1024/maskable; navy `#0f1620` + gold
  `#d4a830`).
- `PLAY_STORE.md` for the submission playbook.

## Research Required

- Google Play policies (current version).
- Capacitor 8 release notes for any breaking changes.
- PWA share_target spec (W3C).

## Step-by-Step Method

1. Run `npm run build && npx cap sync android` and confirm a
   clean sync.
2. Open `android/` in Android Studio (owner-driven if signed
   build needed); confirm the app id matches
   `capacitor.config.json`.
3. Confirm `public/manifest.json` declares `share_target` for
   POST to `/SharedUpload` and the icon set is complete.
4. Confirm `MainActivity.java` reads `EXTRA_STREAM`,
   base64-encodes, and evaluates JS to populate
   `window.__hazmatSharedIntent`.
5. Confirm the service worker (`public/sw.js`) intakes the
   share-target post in production builds (intentionally
   unregisters in dev).
6. Brand color check: `navy #0f1620` + `gold #d4a830` in all
   icon variants.
7. Cross-reference `PLAY_STORE.md` for the current
   "Deliberately left NOT-DONE" list and confirm the demo
   does not promise items still on it.
8. Generate signing keystore + signed AAB is **owner-only** —
   document the next owner action if the agent has prepared
   everything except the signing step.

## Deliverable Format

Mobile Release Check Memo: sync status, share-target
verification, brand audit, owner-action checklist.

## Quality Checklist

- [ ] Clean `cap sync`
- [ ] App id matches
- [ ] manifest.json + sw.js intact
- [ ] Share-target end-to-end verified (mock multipart in dev)
- [ ] Brand assets correct
- [ ] No demo claim relying on a still-stubbed feature

## Escalation Triggers

- Any sync failure → halt; route to Mobile / Capacitor Engineer.
- A Play Store policy alignment risk (e.g. a feature added that
  needs an updated data-safety form) → halt store-listing
  update; route to App Store & Platform Policy Agent.

## Related Agents

- Mobile / Capacitor Engineer (Engineering Factory)
- App Store & Platform Policy Agent (Legal Office)
- Pilot Demo Architect (Product Studio)

## Related Artifacts

- `PLAY_STORE.md`
- `docs/runbooks/` (when an Android-specific runbook lands)
