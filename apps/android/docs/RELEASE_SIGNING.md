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

Pushing a tag like `android-v0.1.0` builds a signed release APK and attaches
it to a GitHub Release as a downloadable asset (also uploaded as a workflow
artifact). Manual runs are available via **Actions → Android release → Run
workflow**.

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

```bash
git tag android-v0.1.0
git push origin android-v0.1.0
# CI builds, signs, and publishes jarvis-0.1.0.apk to the GitHub Release.
```

---

## Notes
- `minSdk 26` (Android 8.0+), `targetSdk`/`compileSdk 35`.
- The app is a **local orchestrator** — no API keys or backend URLs are baked
  into the build; signing secrets are the only sensitive inputs, and they
  live only in your keystore / GitHub secrets.
