# NEXUS Companion Daemon (Android)

A **thin, always-on** Kotlin/Jetpack Compose companion for NEXUS. It is the ~10%
of NEXUS that genuinely needs the metal — unbounded background execution,
widgets, tiles, share targets — while the other ~90% (console, octagon, agent
orchestration) lives in the fast-moving PWA.

## What it does (and only this)
1. **Foreground service** — persistent WebSocket to the M.U.S.E. backend so
   agent status and owner-gated authorization prompts arrive with the PWA closed.
   Posts a low-priority `"NEXUS daemon active — N agents"` notification.
2. **Home-screen widget** — compact idle/running/error/needs-auth board; tap →
   opens the installed PWA.
3. **Quick Settings tile** — toggle the daemon connection.
4. **Share-sheet target** — "Send to M.U.S.E." turns shared text/links into a goal.
5. **Authorization relay** — high-priority Approve/Deny notification for deferred
   owner-gated actions, calling back to the backend.

It does **NOT** reimplement the console UI, octagon, or agent list.

## Build
```bash
cd apps/nexus/companion-android
./gradlew :app:assembleDebug      # requires Android SDK 34, min SDK 26
```
Pair once with the M.U.S.E. gateway (base URL + token); credentials are held in
`EncryptedSharedPreferences`.

## Contract
The complete backend dependency surface is in [`CONTRACT.md`](./CONTRACT.md);
endpoints mirror the PWA's [`../ADAPTERS.md`](../ADAPTERS.md).

> Min SDK 26. The optional Termux bridge is OFF by default (see CONTRACT.md).
