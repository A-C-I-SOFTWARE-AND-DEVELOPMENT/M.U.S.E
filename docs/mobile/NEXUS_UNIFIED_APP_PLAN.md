# NEXUS unified app — single-codebase merge plan (PWA-first)

**Status:** PROPOSED — Phase 0 (this doc). Destructive phases are
**owner-gated** (`Yes, with authorization.`).
**Date:** 2026-06-18
**Branch:** `claude/nexus-mobile-launch-6rnm57`
**Decision owner:** Jeremiah Echerd.

## Decision record

We have **three front-ends to one backend** (the MUSE cockpit gateway,
`/v1/cockpit/*`):

| Surface | Package / path | What it is | Footprint |
|---|---|---|---|
| MUSE Android | `com.aci.hermes` · `apps/android` | Full **native** Kotlin/Compose app | 274 `.kt`, 28 screens |
| NEXUS Android | `dev.aci.nexus` · `apps/nexus/android` | Thin **WebView shell** of the PWA | 1 `.kt` (213 lines) + icons |
| NEXUS PWA | `apps/nexus/src` | React/TS **command center** over the gateway | the web app |

The owner chose, in order:

1. **Full single-codebase merge** (not embed / not two-binaries).
2. **PWA-first**: the NEXUS web app is the single product/UI codebase
   (it also powers web + desktop). The native app collapses to a **thin
   shell + native service modules** bridged to the web.

## Hard constraint that shapes everything

A PWA is sandboxed out of the capabilities that are the *whole point* of a
native MUSE body. These **cannot** move to web and **must** stay native,
exposed to the PWA over a JS bridge:

| Native service (`apps/android/.../service/`) | Why it can't be web |
|---|---|
| `VoiceLoopService` | always-on "Hey Muse" wake word, STT/TTS over BT |
| `JarvisAccessibilityService` | physically taps/swipes/launches apps |
| `JarvisOverlayService` | floating avatar over other apps (`SYSTEM_ALERT_WINDOW`) |
| `HermesService` / `WorkWatchService` | foreground services + local notifications/polling |
| `ObservatoryWallpaperService` | live wallpaper |
| launcher shortcuts · QS tile · deep links · notification actions | OS integration |

Everything **else** the native app draws (the 28 Compose screens — chat,
jobs, approvals, evidence, memory, autonomy, model, coding, diagnostics,
settings, …) is **already covered** by the PWA's 32-capability console.
Those screens are the **deletion target**.

## Target architecture

**One surviving shell = `apps/android` (`com.aci.hermes`)** — it already
owns all six native services; adding one WebView host to it is far less work
and risk than porting six complex services into the `apps/nexus/android`
shell. `apps/nexus/android` is **retired** (its WebView approach is absorbed
into `apps/android`). `apps/nexus/src` (the PWA) is the **single UI source of
truth**.

```
apps/nexus/src  (PWA, React/TS)      ← the only UI codebase (mobile+web+desktop)
        │  loaded in
        ▼
apps/android  (com.aci.hermes)       ← the only Android binary
  ├─ WebViewHostActivity             ← hosts the PWA full-screen
  ├─ NexusBridge (@JavascriptInterface)  ← PWA → native calls
  └─ service/*  (voice, a11y, overlay, FGS, wallpaper)  ← kept, driven by bridge
```

### Branding / package (owner call — default chosen for continuity)

Keep `applicationId = com.aci.hermes` so **existing installs update in
place** (Play/sideload treat a new applicationId as a separate app).
Relabel the launcher/app name to **NEXUS**. Alternative (fresh `dev.aci.nexus`
identity, clean break, no in-place update) is available on request.

## The keystone: the `NexusBridge` contract

The PWA detects it is inside the shell (`window.NexusBridge` present) and
gains the native-only powers; in a plain browser those controls degrade to an
honest "requires the NEXUS app" state (same pattern the PWA already uses for
"requires gateway"). Bridge surface (v1, all owner-gated server-side as
today):

| JS call | Native effect | Safety |
|---|---|---|
| `voice.start()` / `voice.stop()` | toggle `VoiceLoopService` | mic FGS notification + in-app indicator (no silent listen) |
| `overlay.show()` / `overlay.hide()` | `JarvisOverlayService` | `specialUse` FGS notification |
| `accessibility.status()` | is the a11y service enabled | read-only; enabling is an OS settings deep-link |
| `notify.post(event)` | local notification via existing channels | secret-redacted, structural bodies only |
| `approvals.surface(id)` | open the owner-gated approval flow | **no one-tap approve** — opens the queue |
| `emergencyStop.engage(level)` | soft-pause / hard-stop / lockdown | audited; resume requires explicit approval |
| `token.get()` / `token.set()` | read/write the cockpit bearer token | `EncryptedSharedPreferences`, never exposed to remote origins |
| `shell.info()` | version, build type, capabilities | — |

The bridge **only** loads for the trusted first-party origin (the bundled/
hosted PWA URL); arbitrary web content never sees `NexusBridge`.

## Phased execution (gates marked)

| Phase | Work | Destructive? | Gate |
|---|---|---|---|
| **0** | This plan + bridge contract spec | no | none — **this PR** |
| **1** | Add `WebViewHostActivity` + `NexusBridge` to `apps/android`; add the TS bridge client + shell-detection to the PWA. Behind a flag, **default OFF** — native screens still ship. Fully reversible. | no (additive) | none (additive, opt-in) |
| **2** | **Cutover:** flip the default UI to the PWA host; route the kept services through the bridge; Compose screens go dormant behind the flag. | changes default behavior | **OWNER-GATED** |
| **3** | **Cleanup:** delete the dormant Compose screens / viewmodels / nav / design-system; retire `apps/nexus/android`. | yes (deletes a shipped surface) | **OWNER-GATED** |
| **4** | **Release:** unify `nexus-android.yml` + `android-release.yml` into one signed, versioned release of the combined app. | publish | **OWNER-GATED** + signing secrets |

Each gated phase opens its own draft PR with the behavior change summarized,
and waits for the exact phrase `Yes, with authorization.` before merge to
`main` (per `CLAUDE.md` owner gates).

## Validation gates (every phase)

- Python untouched → `uv run ruff check` / `uv run ty check` stay clean.
- `apps/android`: `./gradlew :app:assembleDebug` + `:app:testDebugUnitTest`
  green; `ManifestPermissionAuditTest` still passes (no new permissions —
  the services already declare theirs).
- PWA: `npm run build` + `npm test` in `apps/nexus` green.
- Safety floor intact: `NoDirectDestructiveActionTest`, secret-redaction
  tests, owner-gate code unchanged.

## Risk & rollback

- **Biggest risk:** the bridge becomes a privilege-escalation path. Mitigation:
  bridge loads only for the first-party origin; every owner-gated action stays
  gated **server-side** exactly as today; `token.*` never reaches a remote
  origin.
- **WebView capability gaps** (camera/mic/file/notification permission
  prompts) are handled by the existing shell's permission bridges
  (`apps/nexus/android` already does this) — ported into the host activity.
- **Rollback:** Phases 1–2 are flag-flips (revert the flag). Phase 3 deletions
  are recovered by reverting the PR; the prior APK reinstalls over a bad one
  (local-only app, no server blast radius).

## What this PR (Phase 0) contains

Only this document. No code paths change; no files are deleted. It declares
the plan, the surviving shell, and the bridge contract so Phase 1 can begin
additively on owner approval.
