# Mobile-native launch checklist

The gate to run through before you trust the native muse cockpit with
real authority on a phone. Pairs with the general
[`LAUNCH_GATE_CHECKLIST.md`](LAUNCH_GATE_CHECKLIST.md) (CI / merge
ceremony) and the safety reference in the
[Capability & Permission guide](../mobile/JARVIS_CAPABILITY_AND_PERMISSION_GUIDE.md#security-audit-mapping).

This checklist verifies the **runtime safety posture**, not the merge
ceremony. The owner gate (`Yes, with authorization.`) and the safety
floor are never waived here.

---

## 1. Build & test green

- [ ] `Build debug APK` and `Lint` pass (`android-build.yml`).
- [ ] Android JVM unit tests pass, including **`SecureTokenMigrationTest`**,
      `SecretRedactorTest`, `MemoryRedactorTest`, `PrivacyRedactorTest`,
      `CapabilityCatalogTest`, `CapabilityRepositoryTest`,
      `ManifestPermissionsTest`, `ManifestPermissionAuditTest`,
      `ApprovalStoreTest`, `NoDirectDestructiveActionTest`.
- [ ] Python unit (muse + redact + orchestrator) passes.

## 2. Secrets never leak

- [ ] Provider API keys are **not** present on the device — only the
      cockpit bearer token (`SettingsRepository` holds no provider keys).
- [ ] Bearer token is stored **encrypted at rest**
      (`EncryptedPrefsSecureTokenStore`), not in plaintext DataStore.
- [ ] Legacy plaintext token migrates on first launch and **no plaintext
      copy remains** afterwards (`SecureTokenMigrationTest`).
- [ ] Backend logs and tool output are redacted (`agent/redact.py`
      `RedactingFormatter`); spot-check a verbose log for `sk-…`, `ghp_…`,
      bearer headers, JWTs — all masked.
- [ ] No secret appears in memory entries (`MemoryRedactor`).

## 3. Backend exposure

- [ ] `hermes cockpit serve` is **loopback-only** (no `--allow-external`
      in normal operation); remote access is via a tunnel.
- [ ] Every route except `GET /v1/health` rejects a missing/invalid token
      (401).
- [ ] Agentic execute lanes are **refused** when the cockpit is bound
      non-loopback.
- [ ] The cockpit token file is owner-only (`0600`) at
      `${HERMES_HOME}/cockpit/token`.

## 4. Permissions & consent (Android)

- [ ] Manifest declares only the permissions documented in the
      [permission guide](../mobile/JARVIS_CAPABILITY_AND_PERMISSION_GUIDE.md#3-android-permissions--what--why);
      `ManifestPermissionAuditTest` passes.
- [ ] Capabilities requiring a system permission show a
      `PermissionEducationCard` **before** the OS dialog.
- [ ] With a permission **denied**, the dependent capability is disabled
      (not silently working) — verify mic, overlay, accessibility.
- [ ] `isAdvanced` capabilities are hidden until opted in.

## 5. Indicators (no silent activity)

- [ ] Starting the voice loop shows the **mic foreground-service
      notification** + in-app indicator + Android's mic dot.
- [ ] The avatar overlay shows its `specialUse` FGS notification.
- [ ] Background sync shows the `HermesService` notification.

## 6. Blocked high-risk actions

- [ ] An owner-gated action (spend / deploy / push / publish) **pauses**
      and is not executable without the exact phrase.
- [ ] `NoDirectDestructiveActionTest` passes (no destructive action
      bypasses approval).
- [ ] In **Lockdown** autonomy, outbound actions are greyed out / refused.

## 7. Emergency stop drill

- [ ] Engage **Soft pause** → new tasks won't start; inspection still works.
- [ ] Escalate to **Hard stop** → send/delete/push/deploy are blocked and
      audited.
- [ ] **Lockdown** → every mutation blocked.
- [ ] Resume requires an explicit, audited **approval** — confirm there is
      no silent un-stop.
- [ ] The emergency-stop audit log records each transition and each blocked
      action and can be exported.
- [ ] Backend `python -m hermes_cli.jarvis_prime stop` clears pending gates.

## 8. Owner can inspect, revoke, recover

- [ ] **Inspect:** Memory (with provenance), Audit/ledger, Approvals
      history, emergency-stop export all open and show real data.
- [ ] **Revoke:** Lockdown, capability revoke, OS-permission revoke,
      unpair (clear token), and `hermes cockpit token --rotate` each take
      effect.
- [ ] **Recover:** **Reset all settings** wipes both stores; re-pairing
      with a fresh token restores a clean state; reverting a feature
      branch / dropping a PR undoes write work.

## 9. Docs match reality

- [ ] [`../../apps/android/docs/ARCHITECTURE.md`](../../apps/android/docs/ARCHITECTURE.md)
      "Secure storage" section matches the encrypted-token implementation.
- [ ] The mobile guides under [`../mobile/`](../mobile/README.md) describe
      the shipped flows (install, pair, mock/real, approvals, voice,
      avatar, emergency stop).

> If any box is unchecked, the mobile cockpit is **not** launch-ready for
> real authority. Fix the gap or keep autonomy at Manual / Lockdown until
> it's closed.
