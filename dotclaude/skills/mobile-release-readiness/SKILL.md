---
name: mobile-release-readiness
description: Play Store / App Store readiness check — versioning, signing, permissions, icons, screenshots, privacy declarations, closed/internal testing tracks, release notes. Use before any store upload or after a store rejection.
---

# Mobile Release Readiness

## Use when

- Preparing an Android (.aab) or iOS build for submission.
- Debugging a store rejection.
- Auditing a mobile project before going to production.

## Both stores

1. App name consistent across binary, listing, splash, in-app.
2. Bundle id / application id matches the store record.
3. Version code (Android) / build number (iOS) strictly increasing.
4. Signing config valid; release key not in repo; rotation documented.
5. Privacy policy URL live and linked in the listing.
6. Required permissions justified in code and in the listing; no unused
   declared permissions.
7. Icons present at every required size; iOS icons opaque.
8. Screenshots at every required device size; current UI / copy.
9. Release notes drafted.
10. Crash reporting enabled; symbols upload configured for release.

## Android (Play Console)

- Target SDK at or above current Play requirement.
- Data safety form filled, matches actual SDK behavior.
- Internal / closed testing track tested on a real device.
- App bundle builds reproducibly with release config.

## iOS (App Store Connect)

- Capabilities in Xcode match entitlements.
- ATT prompt present if any tracker SDK is bundled.
- TestFlight build available; external testers added if needed.
- Export compliance answered.

## Output

```
## Project
## Stores targeted
## Checklist (per item: PASS | FAIL | N-A with reason)
## Store-rejection risks if submitted today
## Owner-only steps (Play Console, App Store Connect, signing, legal)
## Code-side steps (versions, manifest, plist, build config)
## Verdict: READY | FIX REQUIRED | NOT READY
```

## Hard rules

- Never claim signed without showing signing config check.
- Never claim a permission is justified without finding its use in source.
- Privacy declarations must match what the binary actually does, including
  third-party SDKs.
