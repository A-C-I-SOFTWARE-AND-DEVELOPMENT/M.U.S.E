# Release signing — Jarvis Prime Android app

The release APK is signed with **your own keystore**. Nothing secret is ever
committed: the keystore (`*.jks`) and `keystore.properties` are gitignored,
and CI signs from GitHub Actions secrets.

There are two ways to produce a signed release APK.

---

## 1. Locally

```bash
cd apps/android
cp keystore.properties.example keystore.properties
# edit keystore.properties with your keystore path + passwords
./gradlew :app:assembleRelease
# -> app/build/outputs/apk/release/app-release.apk
```

`build.gradle.kts` reads `keystore.properties` (or the env vars below). If
neither is present, the release build **falls back to debug signing** so it
still yields an installable APK instead of failing.

### Creating a keystore (one time)

```bash
keytool -genkeypair -v \
  -keystore jarvis-release.jks \
  -alias jarvis \
  -keyalg RSA -keysize 4096 -validity 10000 \
  -storepass '<store-pass>' -keypass '<key-pass>' \
  -dname "CN=Jarvis Prime, O=ACI Software and Development, C=US"
```

Keep `jarvis-release.jks` and its passwords safe and backed up. **If you lose
them you can never ship an update to the same app listing** (Play Store
requires the same signing identity across updates).

---

## 2. In CI (GitHub Actions) — `android-release.yml`

The workflow publishes a downloadable APK three ways:

- **One-button versioned release (recommended)** — **Actions → Android release
  → Run workflow** with **no input** cuts a permanent versioned GitHub Release.
  The version is auto-derived from the repo's real history as
  `<UTC build date>.<total commit count>` (e.g. `2026.06.05.107`), so it always
  reflects the actual time and work done — nothing to hand-edit. Tag:
  `android-v<version>`, asset: `jarvis-prime-<version>.apk`.
- **Rolling `android-latest`** — every push that touches `apps/android/**`
  refreshes a single prerelease tagged `android-latest` whose asset name is
  stable (`jarvis-prime-android.apk`), so the download URL never changes. The
  APK inside still carries the real date+commit version.
- **Hand-named versioned release** — pushing a tag like `android-v1.0.0` (or
  Run workflow with the optional `tag` input) cuts a permanent release stamped
  with exactly that version, for when you want a marketing version instead of
  the auto date+commit one.

All three also upload the APK as a 90-day workflow artifact.

Every run executes an **`apksigner verify --print-certs`** step that fails if
the APK does not verify and reports whether it is **release-signed** or
**debug-signed** (debug keystore identity is `CN=Android Debug`). The signer
fingerprint is written to the job summary. To make CI **fail** when only a
debug-signed APK would be produced, set the repo/org Actions **variable**
`REQUIRE_RELEASE_SIGNING=true` (Settings → Secrets and variables → Actions →
Variables).

Set these four repository secrets (**Settings → Secrets and variables →
Actions**):

| Secret | Value |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | `base64 -w0 jarvis-release.jks` output |
| `ANDROID_KEYSTORE_PASSWORD` | the store password |
| `ANDROID_KEY_ALIAS` | the key alias (e.g. `jarvis`) |
| `ANDROID_KEY_PASSWORD` | the key password |

Generate the base64 blob:

```bash
base64 -w0 jarvis-release.jks > keystore.b64   # paste into ANDROID_KEYSTORE_BASE64
```

If `ANDROID_KEYSTORE_BASE64` is unset (e.g. a fork), the workflow still
builds, but the APK is debug-signed and labelled as such — it never fails for
lack of secrets.

### Cutting a release

**One button (recommended):** Actions → **Android release** → **Run workflow**
→ leave the tag blank → **Run workflow**. CI builds, signs, computes the
version from the repo's history (`<date>.<commits>`), and publishes
`jarvis-prime-<version>.apk` to a permanent versioned GitHub Release.

**Hand-named version (optional):**

```bash
git tag android-v1.0.0
git push origin android-v1.0.0
# CI builds, signs, and publishes jarvis-prime-1.0.0.apk to the GitHub Release.
```

---

## 3. Rollback

Because the app is **local-only and sideloaded**, a release has no server-side
blast radius — there is nothing to take down, and any prior APK simply
reinstalls over a bad one. Rolling back the *published download* is still
quick:

- **Re-publish a known-good build (preferred).** Actions → **Android release**
  → **Run workflow** against a known-good commit/SHA (or revert the offending
  commit on the branch). The run rebuilds and **clobbers** the
  `jarvis-prime-android.apk` asset on `android-latest` back to the good build —
  the download URL is unchanged.
- **Pull the rolling release entirely.** `gh release delete android-latest
  --cleanup-tag` removes the prerelease and its tag. The next qualifying push
  recreates it.
- **A bad versioned release.** `gh release delete android-v<x.y.z>
  --cleanup-tag` (and re-tag once fixed). Versioned assets are immutable by
  convention — prefer a new patch version over editing one in place.
- **Recover a previous APK without rebuilding.** Every run keeps the APK as a
  workflow artifact for 90 days (Actions → the run → Artifacts) — download and
  re-upload it with `gh release upload android-latest <file> --clobber`.

No keystore or secret is ever touched by a rollback; signing inputs live only
in GitHub Actions secrets and your local keystore.

---

## Versioning

Neither `versionCode` nor `versionName` is hard-coded for CI builds — both come
from the environment so the published build reflects reality:

- **`versionCode`** — `app/build.gradle.kts` reads `ANDROID_VERSION_CODE`
  (falling back to `1` locally); `android-release.yml` sets it to the workflow
  **run number**. This gives every APK a unique, monotonically increasing
  `versionCode`, so a freshly downloaded build actually supersedes the one
  already installed — Android treats an equal `versionCode` as "not newer" and
  would otherwise refuse the sideload update.
- **`versionName`** — read from `ANDROID_VERSION_NAME` (falling back to a
  static string locally). CI computes it from the repo's real history as
  `<UTC build date>.<total commit count>` (e.g. `2026.06.05.107`), so the
  human-facing version always reflects the actual **time** (build date) and
  **work** (commit count) rather than a hand-edited placeholder. A pushed
  `android-v<x>` tag or the optional Run-workflow `tag` input overrides it with
  an explicit version when you want a marketing string instead.

## Notes
- `minSdk 26` (Android 8.0+), `targetSdk`/`compileSdk 35`.
- The app is a **local orchestrator** — no API keys or remote-provider URLs are
  baked into the build. Its only network traffic is to the user's own local
  Hermes gateway (default `127.0.0.1:8765`); signing secrets are the only
  sensitive inputs, and they live only in your keystore / GitHub secrets.
- Release integrity: every CI build runs `apksigner verify --print-certs` and
  reports the signer identity (release vs. debug) to the job summary. GitHub
  Actions secrets supply the signing key; set `REQUIRE_RELEASE_SIGNING=true` to
  make a debug-signed build fail closed.
