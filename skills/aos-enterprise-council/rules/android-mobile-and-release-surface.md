---
paths:
  - "android/**"
  - "capacitor.config.json"
  - "PLAY_STORE.md"
  - "PUBLISH.md"
  - "vercel.json"
  - "docs/releases/**"
---

# Android, mobile, and release surface

**Path scope (auto-activates):** mobile and release-adjacent files
per the `paths` frontmatter above. Original list: `android/**`,
`capacitor.config.json`,
`PLAY_STORE.md`, `vercel.json`, `PUBLISH.md`-adjacent edits,
`docs/releases/**`, mobile-related entries in `marketing/**`.

**Authority:** `AGENTS.md` (owner-only wall #5 — no Play Store
submission), `PUBLISH.md` (G0–G4 release governance),
`docs/governance/09-release-freeze-and-safety-budget-policy.md`,
`docs/skills/mobile-capacitor-release-check.md`.

Mobile + release-adjacent surfaces sit next to owner-only walls.
The risk is not "the change is wrong" — the risk is "the change
quietly publishes". Stay inside the wall.

## Discipline

1. **No store submission. Ever.** Owner-only wall #5 (AGENTS.md):
   Play Store / App Store submission is owner-only. Agents do not
   call `gradlew bundleRelease` to upload, do not interact with
   Play Console, do not interact with App Store Connect.
2. **No production release action.** No `vercel --prod`. No DNS
   change at IONOS or Cloudflare. No Base44 Publish click. Vercel
   "Promote to Production" is owner-only.
3. **Preserve buildability.** Mobile changes still pass
   `npx cap sync android` cleanly. If a dependency upgrade breaks
   the Capacitor build, that is a finding — escalate.
4. **Permissions discipline.** `AndroidManifest.xml` permission
   changes are RC3 because they can break a Play Store submission
   that the owner will eventually file. Justify every new
   permission with a feature that needs it; cite the file.
5. **User experience parity.** A mobile-visible change is not done
   until you have walked the screen on the live dev server or a
   built APK in an emulator, OR you have explicitly said "I did
   not test on device" in the PR.
6. **Release notes are facts.** `docs/releases/**` carry only
   verified statements about what shipped, with the test count and
   the merge SHA. No speculation about future features.
7. **PUBLISH.md is canonical.** If you read advice elsewhere in
   the repo that conflicts with PUBLISH.md, PUBLISH.md wins.

## Anti-patterns rejected on sight

- A commit that adds `vercel --prod`, `firebase deploy --only`,
  `eas submit`, `fastlane`, or similar production-promote tooling.
- A change to `vercel.json` that flips production routing without
  an owner sign-off note.
- A new Android permission with no justifying code path.
- A release note that promises a future feature.
- A Capacitor plugin upgrade with no smoke test note.
