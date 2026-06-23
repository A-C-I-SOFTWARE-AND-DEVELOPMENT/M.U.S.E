# Mobile-first muse — documentation hub

This is the index for running **muse** from your phone: the
native Android cockpit, how it pairs with a muse backend, what it can
do, and how the safety model keeps a powerful personal assistant from
doing anything you didn't authorize.

> New to muse itself? Start with the repo [`README.md`](../../README.md)
> and the plain-English [`docs/README.md`](../README.md) operating manual.

---

## Start here (new user path)

Read these in order the first time:

1. **[JARVIS_MOBILE_NATIVE_USER_GUIDE.md](JARVIS_MOBILE_NATIVE_USER_GUIDE.md)**
   — install the app, pair it to a backend, mock vs. real mode, start a
   chat, run jobs, approve actions, voice, the live avatar, and the
   emergency stop. Everything a new user needs to operate muse from a
   phone.
2. **[JARVIS_CAPABILITY_AND_PERMISSION_GUIDE.md](JARVIS_CAPABILITY_AND_PERMISSION_GUIDE.md)**
   — what muse can do (the capability catalog), every Android
   permission it asks for and why, the persistent mic / device-control
   indicators, autonomy levels, and how to inspect, revoke, and recover.
3. **[JARVIS_CODING_FROM_PHONE_GUIDE.md](JARVIS_CODING_FROM_PHONE_GUIDE.md)**
   — drive real coding work (Codex / Claude Code lanes) from the phone,
   the owner-approval gate, and reviewing the resulting PR.

The older, still-accurate plain-English walkthrough lives at
[`mobile-app-guide.md`](mobile-app-guide.md).

## Developer path

- **[JARVIS_MOBILE_NATIVE_ARCHITECTURE.md](JARVIS_MOBILE_NATIVE_ARCHITECTURE.md)**
  — how the app and the loopback cockpit backend fit together: the route
  table, bearer auth, encrypted token storage, mock vs. real wiring, and
  the data-flow model.
- [`hermes-mobile-architecture.md`](hermes-mobile-architecture.md) — the
  module-level Android architecture (deep dive).
- [`hermes-mobile-backend-contract.md`](hermes-mobile-backend-contract.md)
  — the wire contract between app and gateway.
- [`app-api-client.md`](app-api-client.md),
  [`app-state-model.md`](app-state-model.md),
  [`app-screens.md`](app-screens.md),
  [`app-background-service.md`](app-background-service.md),
  [`app-voice-service.md`](app-voice-service.md) — per-subsystem specs.
- [`../android/hermes-apk-cockpit.md`](../android/hermes-apk-cockpit.md)
  and [`../android/hermes-apk-api-contract.md`](../android/hermes-apk-api-contract.md)
  — the canonical APK cockpit + API contract.
- [`../../apps/android/docs/ARCHITECTURE.md`](../../apps/android/docs/ARCHITECTURE.md)
  — the in-app architecture README, including **secure storage**.

## muse brains behind the cockpit

- **[../jarvis/JARVIS_HIGH_AUTONOMY_CODING_MODE.md](../jarvis/JARVIS_HIGH_AUTONOMY_CODING_MODE.md)**
  — the autonomy tiers (scoped, logged, revocable) and the owner gates
  that never lift.
- **[../jarvis/JARVIS_EVIDENCE_RAG_GUIDE.md](../jarvis/JARVIS_EVIDENCE_RAG_GUIDE.md)**
  — how muse does cited research without fabricating sources.
- [`../jarvis_architecture/JARVIS_SYSTEM_OVERVIEW.md`](../jarvis_architecture/JARVIS_SYSTEM_OVERVIEW.md)
  and [`../jarvis_architecture/JARVIS_OWNER_GATES_AND_PERSONAL_AUTHORITY.md`](../jarvis_architecture/JARVIS_OWNER_GATES_AND_PERSONAL_AUTHORITY.md).

## Voice & avatar

- [`../voice/voice-first-user-guide.md`](../voice/voice-first-user-guide.md)
  — voice-first capture and driving mode.
- [`../voice/driving-mode-safety.md`](../voice/driving-mode-safety.md),
  [`../voice/stt-provider-policy.md`](../voice/stt-provider-policy.md).
- [`../avatar/sentient-avatar-architecture.md`](../avatar/sentient-avatar-architecture.md)
  — the living avatar / Den.

## Security & privacy

- [`../security/private-local-security-guide.md`](../security/private-local-security-guide.md)
  — lock everything to private / local-only.
- [`../security/secrets-management.md`](../security/secrets-management.md),
  [`../security/autonomous-agent-safety.md`](../security/autonomous-agent-safety.md).
- The security-audit mapping (which safety control lives in which file,
  with its tests) is in the
  [Capability & Permission guide](JARVIS_CAPABILITY_AND_PERMISSION_GUIDE.md#security-audit-mapping).

## Going live

- **[../launch/MOBILE_NATIVE_LAUNCH_CHECKLIST.md](../launch/MOBILE_NATIVE_LAUNCH_CHECKLIST.md)**
  — the gate checklist before you trust the mobile cockpit with real
  authority.

## Roadmap

- **[NEXUS_UNIFIED_APP_PLAN.md](NEXUS_UNIFIED_APP_PLAN.md)** — the PWA-first
  single-codebase merge: collapse the native MUSE app + NEXUS PWA into one
  shell (PWA UI + native service bridge). Phased, owner-gated.

## Phone-as-backend (Termux)

If you run the backend on the *same* phone via Termux:

- [`../termux/hermes-phone-first-runtime.md`](../termux/hermes-phone-first-runtime.md),
  [`../termux/hermes-android-permissions.md`](../termux/hermes-android-permissions.md),
  [`../termux/hermes-wake-lock-policy.md`](../termux/hermes-wake-lock-policy.md).
- [`../hermes-local-orchestrator.md`](../hermes-local-orchestrator.md) —
  the clipboard-handoff workflow that predates the cockpit.
