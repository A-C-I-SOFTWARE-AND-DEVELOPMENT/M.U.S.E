# Android release signing & Play submission — what's real, what's owner-gated

This page documents the **exact** secrets the CI release workflow
consumes, how to create the keystore, and what stands between today's
sideload-ready APK and a Google Play submission. It complements (and
stays consistent with) the app's own
[`apps/android/docs/RELEASE_SIGNING.md`](../../apps/android/docs/RELEASE_SIGNING.md)
and the workflow at
[`.github/workflows/android-release.yml`](../../.github/workflows/android-release.yml).

> **Owner-gated:** creating the keystore, setting the repository secrets,
> flipping `REQUIRE_RELEASE_SIGNING`, and anything Play Console (account,
> upload, store listing) are owner actions. CI never invents a signing
> identity; without the secrets it ships a clearly-marked debug-signed
> build instead of failing.

---

## 1. The GitHub secrets the workflow consumes (exact names)

Set under **Settings → Secrets and variables → Actions → Secrets**:

| Secret | What it is |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | base64 of your `.jks` keystore file |
| `ANDROID_KEYSTORE_PASSWORD` | keystore (store) password |
| `ANDROID_KEY_ALIAS` | key alias inside the keystore |
| `ANDROID_KEY_PASSWORD` | key password |

These are the only four. The workflow decodes
`ANDROID_KEYSTORE_BASE64` to `$RUNNER_TEMP/jarvis-release.jks` and passes
it to Gradle as the env var `ANDROID_KEYSTORE_FILE`, alongside
`ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, and
`ANDROID_KEY_PASSWORD` (the build also receives
`ANDROID_VERSION_CODE=${{ github.run_number }}` and an auto-derived
`ANDROID_VERSION_NAME`). `apps/android/app/build.gradle.kts` reads either
these env vars or a local `keystore.properties`.

One **repository variable** (not a secret) hardens the gate:

| Variable | Effect |
|---|---|
| `REQUIRE_RELEASE_SIGNING=true` | Fail the build if the APK ends up debug-signed (i.e. the keystore secrets are missing). Unset by default so forks/bring-up still publish a sideloadable debug-signed APK. |

The workflow verifies every APK with `apksigner verify --print-certs`:
anything whose signer is `CN=Android Debug` is flagged debug-signed; the
signer's SHA-256 fingerprint is surfaced in the job summary (public cert
digests only — never the key or passwords).

To produce the base64 value:

```bash
base64 -w0 jarvis-release.jks   # macOS: base64 -i jarvis-release.jks | tr -d '\n'
```

## 2. Generating the keystore (one time, owner)

```bash
keytool -genkeypair -v \
  -keystore jarvis-release.jks \
  -alias jarvis \
  -keyalg RSA -keysize 4096 -validity 10000 \
  -storepass '<store-pass>' -keypass '<key-pass>' \
  -dname "CN=muse O=ACI Software and Development, C=US"
```

Keep the `.jks` and both passwords backed up offline. **If you lose them
you can never ship an update to the same app listing** — Android requires
the same signing identity across updates (Play App Signing relaxes this
for the app key, but the upload key still gates your uploads; see §4).
The keystore and `keystore.properties` are gitignored; nothing secret is
ever committed.

For local signed builds:

```bash
cd apps/android
cp keystore.properties.example keystore.properties   # fill in path + passwords
./gradlew :app:assembleRelease
```

## 3. The three release channels (what CI publishes today)

- **One-button versioned release** — Actions → "Android release" → Run
  workflow (no input). Auto-version `<UTC date>.<commit count>`, tag
  `android-v<version>`, asset `jarvis-prime-<version>.apk`.
- **Rolling `android-latest`** — every push touching `apps/android/**`
  refreshes the prerelease with the stable asset name
  `jarvis-prime-android.apk`.
- **Hand-named** — push an `android-v1.2.3` tag (or pass the workflow's
  `tag` input).

All three are GitHub Release **APKs for sideload**. None of them upload
to Google Play — that pipeline does not exist yet.

## 4. Play Console upload basics (owner-gated, not yet wired)

What a Play submission would actually take, honestly:

1. **A Play Console developer account** ($25 one-time, identity
   verification).
2. **An Android App Bundle, not an APK.** Google Play requires `.aab` for
   new apps. The workflow currently runs `:app:assembleRelease` (APK
   only); a Play path needs `:app:bundleRelease` plus signing — a small,
   additive workflow change, but it is **not built today**.
3. **Play App Signing** (strongly recommended): Google holds the app
   signing key; your keystore from §2 becomes the *upload key*. A lost
   upload key can then be reset through Play support — unlike the
   raw-keystore model where loss is fatal.
4. **Target API level**: Play requires recent targets; the app currently
   sets `compileSdk = 35`, `targetSdk = 35`, `minSdk = 26`
   (`apps/android/app/build.gradle.kts`), which meets the 2026 requirement.
5. Store listing assets (icon, screenshots, feature graphic), content
   rating questionnaire, and a **privacy policy URL** (mandatory because
   the app declares sensitive permissions like `RECORD_AUDIO` and
   `CAMERA`).

## 5. Privacy / Data-safety form — what to declare

Answers must be derived from the app's real behavior, not aspiration.
What the code actually does (see the release-notes claim baked into
`android-release.yml` and the manifest at
`apps/android/app/src/main/AndroidManifest.xml`):

- **Network**: the app's only network traffic is to the user's own local
  Hermes cockpit gateway (default `127.0.0.1:8765`) once paired — never to
  remote AI providers — and it holds no API keys. Unpaired, it runs fully
  offline against an on-device mock. In the Data safety form this supports
  declaring **no data collected and no data shared** with third parties,
  but the owner must re-verify against the shipping build before
  attesting (the form is a legal declaration).
- **Declared permissions to account for** (each needs a stated purpose in
  the listing and, where "dangerous", a runtime-prompt justification):
  `INTERNET`, `POST_NOTIFICATIONS`, `RECORD_AUDIO` (voice capture),
  `CAMERA`, `BLUETOOTH_CONNECT`, `SYSTEM_ALERT_WINDOW`, the
  `FOREGROUND_SERVICE*` family (data sync / microphone / special use —
  special-use services require a Play declaration of why), and
  `QUERY_ALL_PACKAGES` — this last one triggers a dedicated Play policy
  review and needs a strong justification or removal/narrowing to a
  `<queries>` element before submission.
- **Account/IDs**: no accounts, no advertising ID usage to declare (no ad
  SDKs in the app).

Pre-submission checklist (owner):

- [ ] Re-audit the manifest + network code of the exact build being
      submitted; align the Data safety form with it.
- [ ] Publish a privacy policy URL.
- [ ] Resolve or justify `QUERY_ALL_PACKAGES` and
      `FOREGROUND_SERVICE_SPECIAL_USE`.
- [ ] Add a `bundleRelease` (.aab) lane to `android-release.yml`.
- [ ] Enroll in Play App Signing; keep the §2 keystore as upload key.
- [ ] Content rating questionnaire + store listing assets.

Until those land, the supported distribution channel is the signed (or
clearly-marked debug-signed) sideload APK from GitHub Releases, as
documented in
[`one-command-install.md`](one-command-install.md).
