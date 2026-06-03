# JARVIS capability & permission guide

A powerful personal assistant on your phone earns that power one explicit
grant at a time. This guide covers **what JARVIS can do**, **what it asks
for and why**, how you **see** when it's active, and how you **inspect,
revoke, and recover**. It ends with the **security-audit mapping** tying
each safety control to the code and tests that enforce it.

---

## 1. Capabilities (what JARVIS can do)

The phone surfaces a curated **capability catalog**
(`apps/android/app/src/main/java/com/aci/hermes/data/capability/CapabilityCatalog.kt`).
The full agent surface is hundreds of specialists; exposing all of them on
a phone would be hostile. The catalog is the small, opinionated day-to-day
subset — conversation modes (companion, strategy), build/coding packets,
research, orchestration, and more. Each entry carries a plain-English
example prompt and the lane it routes to.

- Less-common entries are marked `isAdvanced` and appear only when you opt
  in.
- Adding a capability to the catalog only changes **visibility** — it does
  not register a new agent. The underlying lane must already exist on the
  gateway.
- Open the **Capabilities** screen to browse, search, and launch.

## 2. Explicit capability consent

Capabilities that touch the device or the outside world are **opt-in**.
The app does not silently acquire abilities:

- The first time a capability needs a system permission, you see a
  `PermissionEducationCard` explaining **what** is requested and **why**
  before the OS dialog appears.
- Device-control and voice surfaces stay dormant until you enable them in
  Settings *and* grant the OS permission.
- `CapabilityRepository` tracks which capabilities you've enabled; nothing
  outside that set runs.

## 3. Android permissions — what & why

Declared in
[`apps/android/app/src/main/AndroidManifest.xml`](../../apps/android/app/src/main/AndroidManifest.xml):

| Permission | Why JARVIS asks | Gated by |
|---|---|---|
| `POST_NOTIFICATIONS` | Show job/approval/voice notifications | OS runtime prompt |
| `FOREGROUND_SERVICE` + `FOREGROUND_SERVICE_DATA_SYNC` | Keep syncing with the backend while backgrounded | Foreground notification |
| `RECORD_AUDIO` + `FOREGROUND_SERVICE_MICROPHONE` | The hands-free voice loop | Mic runtime prompt + persistent mic indicator |
| `SYSTEM_ALERT_WINDOW` | The floating avatar body draws over other apps | "Draw over other apps" grant + overlay toggle |
| `FOREGROUND_SERVICE_SPECIAL_USE` (`on_screen_assistant_avatar`) | Run the avatar overlay service | FGS notification |
| `BLUETOOTH_CONNECT` | Use a headset for the voice loop | OS runtime prompt |
| `QUERY_ALL_PACKAGES` | Let JARVIS launch/automate the apps you name | Used only behind accessibility + your action |
| `BIND_ACCESSIBILITY_SERVICE` (`JarvisAccessibilityService`) | JARVIS's "hands" — taps, swipes, app launches | System accessibility toggle (you enable it explicitly) |

**Android system permissions remain technical gates JARVIS cannot
bypass.** A standing owner-authorized profile reduces *repeated* approval
friction, but it never grants a permission the OS hasn't.

## 4. Persistent indicators (you always know when it's active)

- **Microphone:** the voice loop runs as a `microphone` foreground service
  (`VoiceLoopService`) — a persistent system notification plus an in-app
  indicator (`VoiceLoopState`). JARVIS cannot listen silently. Android's
  own top-bar mic dot is also lit.
- **Device control / avatar:** the overlay runs as a `specialUse`
  foreground service with its own notification; the accessibility "hands"
  appear in the system accessibility settings whenever enabled.
- **Background sync:** `HermesService` shows a foreground notification
  while it watches jobs.

## 5. Autonomy levels (scoped power)

`data/jarvis/AutonomyMode.kt` — an owner-controlled dial, never reset
implicitly by the runtime:

| Mode | Behaviour |
|---|---|
| **Manual** | JARVIS acts only when you tap a step. |
| **Assisted** | JARVIS proposes; each action waits for owner approval. |
| **Trusted (low risk)** | JARVIS runs low-risk steps; destructive actions still require approval. |
| **Lockdown** | JARVIS is paused — no external actions, no handoffs, no automation. |

Even at the highest tier, **owner-gated and irreversible actions still
pause** for the authorization phrase. See
[`../jarvis/JARVIS_HIGH_AUTONOMY_CODING_MODE.md`](../jarvis/JARVIS_HIGH_AUTONOMY_CODING_MODE.md).

## 6. Emergency stop (instant brakes)

Reachable from every screen (`EmergencyStopButton`), backed by
`data/emergency/EmergencyStopController.kt`:

- **Soft pause** → no new tasks start. **Hard stop** → also blocks
  send/delete/push/deploy. **Lockdown** → blocks every mutation.
- Engage never downgrades; escalation only climbs.
- Returning to active **always** goes through an audited resume request →
  approval. There is no silent un-stop.
- Every transition and every blocked action is written to the
  emergency-stop audit log; you can export it.
- Backend equivalent: `python -m hermes_cli.jarvis_prime stop`.

## 7. Inspect, revoke, recover (owner control)

- **Inspect:** Memory screen (with provenance), Audit/ledger screen,
  emergency-stop audit export, Approvals history.
- **Revoke:** switch Autonomy to Lockdown; engage Emergency Stop; revoke a
  capability in the Capabilities screen; revoke an OS permission in Android
  settings; **unpair** (clear the cockpit token) in Settings; rotate the
  backend token with `hermes cockpit token --rotate`.
- **Recover:** **Settings → Reset all settings** wipes both stores
  (DataStore + encrypted token). Re-pair with a fresh token. Work happens
  on isolated feature branches on the backend, so reverting a branch /
  dropping a PR fully undoes write work.

## 8. Security-audit mapping

Every hardening requirement, mapped to the code that enforces it and the
test that proves it. **None of these gates may be weakened.**

### Secrets

| Requirement | Enforced by | Tested by |
|---|---|---|
| Secrets never in logs / tool output; redacted | `agent/redact.py` (`redact_sensitive_text`, `RedactingFormatter`, `mask_secret`, `safe_log_summary`; on by default, snapshot-locked against runtime opt-out), `tools/tokenjuice/scrub.py` | Python redaction suite; Android `data/audit/SecretRedactor.kt` → `SecretRedactorTest` |
| Secrets never in memory | `data/memory/MemoryRedactor.kt`; local-only-memory default | `MemoryRedactorTest` |
| Identities redacted | `data/social/PrivacyRedactor.kt` | `PrivacyRedactorTest` |
| Provider API keys never on device | Keys live in gateway `~/.hermes/.env`; app holds only the bearer token | `SettingsRepository` design |
| Bearer token encrypted at rest + safe migration | `data/preferences/SecureTokenStore.kt` (`EncryptedPrefsSecureTokenStore`, `CockpitTokenMigration`) | `SecureTokenMigrationTest` |

### Backend

| Requirement | Enforced by |
|---|---|
| Auth required on every route (except health) | `gateway/cockpit/auth.py`, `server.py` bearer check |
| Loopback-only / safe network policy | `server.py` refuses non-loopback bind without `--allow-external`; execute lanes disabled off-loopback |
| Redacted responses / logs | `agent/redact.py` `RedactingFormatter`; handlers never echo the token |

### Owner gates & autonomy

| Requirement | Enforced by |
|---|---|
| Owner gates / approval phrase | `hermes_cli/jarvis_prime/owner_auth.py` (15 `OWNER_GATED_ACTIONS`), `gates.py` |
| High autonomy scoped / logged / revocable | `AutonomyMode.kt`; decision ledger / audit; Lockdown + emergency stop |

### Android device safety

| Requirement | Enforced by | Tested by |
|---|---|---|
| Explicit capability consent | `CapabilityCatalog.kt`, `CapabilityRepository.kt`, `PermissionEducationCard.kt` | `CapabilityCatalogTest`, `CapabilityRepositoryTest` |
| Manifest permissions audited / minimal | `AndroidManifest.xml` | `ManifestPermissionsTest`, `ManifestPermissionAuditTest` |
| Persistent mic / device indicators | `VoiceLoopService` (FGS microphone), `JarvisOverlayService` (FGS specialUse) | — (manifest FGS types) |
| Emergency stop + blocked high-risk actions | `EmergencyStopController.kt` (`isBlocked`/`guard`) | emergency-stop controller + `NoDirectDestructiveActionTest` |
| Approvals required for risky actions | `approval/state/ApprovalStore.kt`, risk-tiered cards | `ApprovalStoreTest` |

For the launch-time verification of all of the above, see
[`../launch/MOBILE_NATIVE_LAUNCH_CHECKLIST.md`](../launch/MOBILE_NATIVE_LAUNCH_CHECKLIST.md).
