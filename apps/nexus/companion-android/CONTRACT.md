# NEXUS Companion Daemon ↔ M.U.S.E. Backend Contract

The daemon is **thin**. It reimplements none of the PWA UI (no console, no
octagon, no agent list). It shares the same backend and auth as the PWA. This
file is the entire surface it depends on.

## Auth
Same bearer token as the PWA (paired once, stored in `EncryptedSharedPreferences`).
`Authorization: Bearer <token>` on every request. Base URL = the user's M.U.S.E.
gateway (`VITE_MUSE_BASE_URL` in the PWA).

## Persistent connection
- **Primary:** WebSocket `GET /api/ws` (upgrade). Server pushes JSON frames:
  ```jsonc
  { "type": "status", "idle": 3, "running": 1, "error": 0, "needsAuth": 0 }
  { "type": "event", "kind": "run-completed", "agentId": "...", "message": "..." }
  { "type": "auth-request", "id": "auth_42", "action": "deploy to prod",
    "risk": "owner-gated", "expiresAt": 1718600000000 }
  ```
- **Fallback:** poll `GET /api/agents/summary` every 30s when the socket drops.

The daemon holds this connection from a **foreground service** so frames arrive
even when the PWA is closed. It posts a persistent low-priority notification:
`"NEXUS daemon active — N agents"`.

## Authorization relay (owner-gated actions)
When M.U.S.E. defers an owner-gated action it emits an `auth-request` frame. The
daemon fires a **high-priority** notification with **Approve** / **Deny**
actions. Tapping either calls back:

```
POST /api/auth/:id/resolve   { "decision": "approve" | "deny" }
```

> The user's M.U.S.E. policy requires the literal owner phrase for the most
> sensitive gates; the daemon forwards the decision and M.U.S.E. enforces policy
> server-side. The daemon never bypasses a gate locally.

## Widget / Quick Settings tile
Both read the **last cached** status snapshot (`idle/running/error/needsAuth`)
written by the service. The widget tap and the QS tile both deep-link into the
installed PWA:

```
https://<nexus-host>/agents          # widget → agents tab
https://<nexus-host>/activity        # notification → activity
```

## Share-sheet target ("Send to M.U.S.E.")
Shared text/links POST a new goal:

```
POST /api/goals   { "text": "<shared content>", "source": "android-share" }
→ 201 { "goalId": "..." }
```

## Optional Termux bridge (stretch, OFF by default)
A narrow local IPC (`content://dev.aci.nexus.daemon.termux`) that a local Termux
process can poke to surface job status. **Disabled unless explicitly enabled** in
daemon settings. Security note: any local app could read an exported provider —
so it is `android:exported="false"` and guarded by a signature permission.

---
That is the complete contract. Endpoints mirror [`../ADAPTERS.md`](../ADAPTERS.md).
