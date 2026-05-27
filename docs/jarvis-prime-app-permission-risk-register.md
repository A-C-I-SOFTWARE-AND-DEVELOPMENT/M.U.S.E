# Jarvis Prime — Android permission risk register

This register defines, by name, the Android permissions the Jarvis
Prime cockpit may declare, the ones it must **never** declare, and
the policy that governs adding new ones.

The policy mirrors the Jarvis Prime operating principles
(`docs/jarvis-prime-operating-system.md`) — Jarvis Prime is a
*partner*, not a surveillance tool. Every permission declared
becomes a Play Console disclosure, a privacy-policy line, and a
trust commitment to the owner.

---

## 1. Policy

1. **No permission is added without a working use case in the same
   wave.** Declaring early "to reserve it" is forbidden — Play
   Console flags unused sensitive permissions and the manifest is
   the truth.
2. **No permission is escalated silently.** Adding a *new* permission
   on a release upgrade resets `runtime-permission` state for
   sensitive perms; that is by design but must be surfaced in
   release notes and in-app onboarding.
3. **Every permission is justified in this register with: name,
   purpose, scope (when active), data leaving the device, and the
   feature flag that gates it.**
4. **Anything in §3 ("must never be added") is rejected at PR
   review.** A reviewer requires a fresh entry in §2 plus a
   user-flow design before the rule can be reconsidered.
5. **Owner approval applies to permission changes.** Adding
   `RECORD_AUDIO`, expanding service types, or adding `INTERNET`
   on the path to a regulated workflow follows the owner-gated
   action set in `docs/jarvis-prime-operating-system.md` §Owner
   Gates.

---

## 2. Permissions currently declared

`apps/android/app/src/main/AndroidManifest.xml` (as audited
2026-05-26):

| # | Permission | Purpose | Scope | Data off-device? | Feature flag |
|---|---|---|---|---|---|
| P-01 | `android.permission.POST_NOTIFICATIONS` | Required on Android 13+ to display the foreground service notification and (Wave 2) per-approval notifications. | App lifetime. | No. | Always on (the persistent service notification is part of the cockpit's identity). |
| P-02 | `android.permission.FOREGROUND_SERVICE` | Required to start `HermesService` in the foreground. | App lifetime. | No. | Always on. |
| P-03 | `android.permission.FOREGROUND_SERVICE_DATA_SYNC` | Specialisation of P-02; matches the manifest `foregroundServiceType="dataSync"`. | App lifetime. | No. | Always on. |

That is the entire list today. No `INTERNET`, no `RECORD_AUDIO`,
no `READ_*`, no `WRITE_*`, no `<queries>` block, no
`SCHEDULE_EXACT_ALARM`, no location, no camera, no contacts.

---

## 3. Permissions that must NEVER be added

Each row is a hard "no" with the reason. A reviewer must reject any
PR adding any of these. If a future requirement seems to need one,
the answer is to redesign the workflow, not add the permission.

### 3.1 Sensitive identifiers / personal data

| Permission | Why not |
|---|---|
| `READ_CONTACTS` | Jarvis Prime never reads address books. Any "share with a teammate" workflow goes through the gateway side, not contacts scraping. |
| `WRITE_CONTACTS` | Same as above. |
| `READ_SMS`, `RECEIVE_SMS`, `SEND_SMS`, `READ_CELL_BROADCASTS` | SMS is not a Jarvis surface. |
| `READ_PHONE_STATE`, `READ_CALL_LOG`, `MANAGE_OWN_CALLS`, `ANSWER_PHONE_CALLS` | Telephony is not a Jarvis surface. |
| `READ_CALENDAR`, `WRITE_CALENDAR` | Calendar integration belongs on the gateway side via the platform's OAuth, not on-device read. |
| `BODY_SENSORS`, `ACTIVITY_RECOGNITION` | Body data is regulated and out of scope. |
| `USE_FINGERPRINT`, `USE_BIOMETRIC` | Reserved for a future locked-screen unlock; not required for the cockpit and not added until that workflow has its own design. |

### 3.2 Location

| Permission | Why not |
|---|---|
| `ACCESS_FINE_LOCATION` | Driving mode is a user-controlled toggle, not a location inference. |
| `ACCESS_COARSE_LOCATION` | Same. |
| `ACCESS_BACKGROUND_LOCATION` | Background location triggers Play Console review; not justified by the cockpit charter. |

### 3.3 Storage (legacy + sweeping)

| Permission | Why not |
|---|---|
| `READ_EXTERNAL_STORAGE` (legacy) | `filesDir` and SAF cover everything the cockpit needs. |
| `WRITE_EXTERNAL_STORAGE` (legacy) | Same. |
| `MANAGE_EXTERNAL_STORAGE` | This is the "all files access" permission — Play Console requires a strict declared use. Not justified. |
| `MANAGE_MEDIA` | Same. |

### 3.4 Overlay / accessibility / device admin

| Permission | Why not |
|---|---|
| `SYSTEM_ALERT_WINDOW` | Jarvis must not draw over other apps. Approval notifications use the standard notification channel and lockscreen surface. |
| `BIND_ACCESSIBILITY_SERVICE` | Accessibility services are heavyweight, easy to abuse, and Play Console scrutinises them. Not a Jarvis pathway. |
| `BIND_DEVICE_ADMIN`, `BIND_DEVICE_ADMIN`-like | The cockpit does not enroll the device. |
| `MANAGE_DEVICE_POLICY` | Same. |
| `BIND_NOTIFICATION_LISTENER_SERVICE` | Reading other apps' notifications is not in scope. |
| `BIND_VPN_SERVICE` | Not a Jarvis pathway. |

### 3.5 Install / packages

| Permission | Why not |
|---|---|
| `REQUEST_INSTALL_PACKAGES` | The cockpit does not sideload. Termux install instructions point users at F-Droid / GitHub releases. |
| `INSTALL_PACKAGES` | System-level only; out of scope. |
| `QUERY_ALL_PACKAGES` | Use a narrow `<queries>` block for `com.termux`/`com.termux.files` only. Sweeping access is rejected by Play Console for most categories anyway. |
| `PACKAGE_USAGE_STATS` | Usage stats are sensitive; not in scope. |

### 3.6 Background / boot / alarms

| Permission | Why not |
|---|---|
| `RECEIVE_BOOT_COMPLETED` | The cockpit does not start at boot. Persistent state lives on the gateway. |
| `SCHEDULE_EXACT_ALARM` | Exact-alarm requests now require runtime grant on Android 14+ and need a strict use case. Cockpit notifications are gateway-driven, not alarm-driven. |
| `USE_EXACT_ALARM` | Same. |
| `WAKE_LOCK` | The Termux-bridge wake-lock work item lives in Termux's process, not Jarvis. The cockpit must not hold wake locks. |
| `HIGH_SAMPLING_RATE_SENSORS` | Not applicable. |

### 3.7 Camera / extra audio

| Permission | Why not |
|---|---|
| `CAMERA` | The cockpit is voice-and-text. No camera path. |
| `RECORD_AUDIO` for background capture | The Wave 4 voice intake permission is foreground-only and gated behind `voice_enabled`. Background recording is forbidden. |

### 3.8 Catch-all

| Pattern | Why not |
|---|---|
| Any permission flagged `signatureOrSystem` only | Cockpit is a regular user-installed app. |
| Any permission introduced for a feature not yet designed | Policy §1.1. |

---

## 4. Permissions that may be added (with conditions)

These are pre-approved to land in the listed wave, **provided** the
feature ships in the same PR and the in-app onboarding explains the
ask.

| Permission | Wave | Conditions |
|---|---|---|
| `INTERNET` | W1 | Must ship with the gateway client + offline fallback. No standalone "telemetry" use. |
| `ACCESS_NETWORK_STATE` | W1 | Used to render *Offline* state on the connection card; no scanning behavior. |
| `<queries><package android:name="com.termux" />` | W1 | Only `com.termux` and `com.termux.files`. No `QUERY_ALL_PACKAGES`. |
| `RECORD_AUDIO` | W4 | Lazy-requested when the user enables voice intake. Never on startup. Revoked path documented in Settings. |
| `FOREGROUND_SERVICE_MICROPHONE` | W4 | Service type flips to `dataSync\|microphone` while voice capture is active; flips back to `dataSync` otherwise. |
| (NTH) `TIRAMISU+ themed icons API` (no permission, manifest only) | W0 | Adds a monochrome icon variant; not a permission, listed here for symmetry. |

A permission landing without the matching feature flag (`internet_enabled`,
`voice_enabled`, `termux_bridge_enabled`) is rejected at review.

---

## 5. Audit hooks

- **Manifest diff alarm.** CI workflow should fail if the manifest
  declares any permission not in §2 + §4 (Wave 5 follow-up — see the
  roadmap).
- **Play Console "Sensitive permissions" panel.** Reviewed each
  release; entries here must match.
- **In-app About screen.** Lists the active permissions and the
  feature flag gating each. Sourced from this register so the user
  can see exactly what is granted and why.
- **Owner-gated change set.** Adding any §4 permission to a release
  branch requires the owner-authorization phrase
  (`Yes, with authorization.`) in the PR description, mirroring
  `hermes_cli/jarvis_prime/owner_auth.py`.

---

## 6. Cross-references

- Audit body: [`jarvis-prime-app-deep-audit.md`](jarvis-prime-app-deep-audit.md)
- Gap map: [`jarvis-prime-app-final-gap-map.md`](jarvis-prime-app-final-gap-map.md)
- Roadmap: [`jarvis-prime-app-finish-roadmap.md`](jarvis-prime-app-finish-roadmap.md)
- Operating system: [`jarvis-prime-operating-system.md`](jarvis-prime-operating-system.md)
- Driving mode safety: [`voice/driving-mode-safety.md`](voice/driving-mode-safety.md)
- Owner auth runtime: `hermes_cli/jarvis_prime/owner_auth.py`
