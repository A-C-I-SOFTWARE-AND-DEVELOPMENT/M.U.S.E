# Security & Privacy (v1.5 Standalone Local)

v1.5 is local-first and privacy-preserving by construction. This document is
the security model plus a **Google Play Data Safety** mapping so the listing is
accurate.

## Security model

- **No bundled provider keys.** The app ships none and calls no provider
  directly. Provider credentials live only on a backend you control
  (`~/.hermes/.env`), never on the phone.
- **One secret on device: the cockpit bearer token.** Stored in
  `EncryptedSharedPreferences` backed by the **Android Keystore**
  (`MasterKey.AES256_GCM`, hardware-backed where available). See
  `EncryptedPrefsSecureTokenStore`. A legacy plaintext token is migrated once
  and the plaintext copy removed.
  Ref: <https://developer.android.com/privacy-and-security/keystore>.
- **Owner gates are server-enforced.** Spend / deploy / publish / OAuth /
  credential change / force-push / package-publish / app-store submission and
  the coding `execute` lane all require the exact phrase
  `Yes, with authorization.`, verified by the gateway. The app never stores,
  caches, or fabricates it; the coding cockpit cannot bypass it.
- **No fabricated state.** Unreachable/unsupported backends produce honest
  empty/error states. Coding tasks queue offline rather than inventing a packet.
- **Redaction in depth.** Logs/diagnostics run through `SecretRedactor`;
  memory rejects secret-like content server-side. Coding prompts never embed
  the owner phrase or tokens.
- **Local data is app-private and backup-excluded.** Coding tasks
  (`hermes_coding_tasks.json`), settings (DataStore), and logs (in-memory ring
  buffer) stay in the app sandbox; `backup_rules.xml` /
  `data_extraction_rules.xml` exclude them from cloud backup and device
  transfer. "Clear local data" wipes them.

## Network posture

- Default endpoint is loopback. Cleartext is only meaningful for `127.0.0.1` /
  an owner LAN gateway the user configures; there is no analytics, no FCM, no
  telemetry call. Notifications are local poll-based.
- The app makes **no outbound provider calls**. The only network it does is to
  the owner-configured cockpit gateway.

## Google Play Data Safety mapping

The coding cockpit itself collects/transmits **no** personal data off-device by
default. Data *processed locally* or *sent only to your own backend*:

| Data type | Used? | Where | Notes |
|---|---|---|---|
| Files & docs (repo paths, task text, work packets) | Yes (local) | App storage + your backend | Sent only to the gateway you pair; never to us. |
| Messages / chat content (prompts, JARVIS replies) | Yes (local) | Your backend | Streamed to your gateway when paired; not stored by the app. |
| Audio / voice | Optional | On-device STT; your backend for transcription | `RECORD_AUDIO`, opt-in, foreground-service indicator. |
| Photos / camera | Optional | On-device ML Kit only | Presence-mode attention; frames never stored or transmitted. |
| App activity (in-app navigation) | Local only | Device | No analytics SDK. |
| Device/identifiers | No | — | No advertising ID, no device identifiers collected. |
| Contacts / calendar / location | No | — | Not used. |

Recommended Data Safety answers: **no data shared with third parties**; data
**may be collected** only insofar as the user pairs and sends it to *their own*
backend; **encrypted in transit** to that backend; user can **request deletion**
(Clear local data + unpair). Update this table if a future capability changes
what is collected.

## Owner checklist
- Pair only backends you control; prefer loopback / LAN.
- Set the four `ANDROID_KEYSTORE_*` CI secrets for a properly-signed release
  (see [`RELEASE_DOWNLOAD.md`](RELEASE_DOWNLOAD.md)).
- Keep "Mock mode" for demos; it touches no network.
