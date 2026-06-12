# M.U.S.E. APK ↔ Termux intent bridge

> When the M.U.S.E. gateway runs **inside Termux on the same Android
> device**, the cockpit APK can drive it via Android's intent system
> instead of going through a network round-trip first. This document
> defines that bridge.

The cockpit's [Termux Control Panel](muse-apk-cockpit.md#37-android--termux-control-panel)
is the only screen that uses these intents directly. Every other screen
talks to the gateway over HTTP/SSE as described in the
[API contract](muse-apk-api-contract.md).

---

## 1. Why intents, not exec / shell

The APK has no shell access into the Termux sandbox. The supported
public-API path between two cohabiting Android apps is the Intent
system. Termux exposes a documented `RUN_COMMAND` intent for exactly
this — it lets another app start commands inside the Termux userland
without prompting the user every time, as long as the user has granted
the *Run external apps* permission to Termux.

M.U.S.E. uses three intents only:

1. **`com.termux.RUN_COMMAND`** — for **start / stop / restart** of
   the gateway and for **tailing logs**.
2. **`ACTION_MAIN`** with the Termux launcher component — for the
   *Open Termux* action when the user wants a shell.
3. **`ACTION_VIEW`** with `file://` or `content://` — only when the
   user opted into *Open job folder in Termux:Files*.

All three are triggered by an **explicit on-device tap**. The cockpit
never sends an intent in the background, on app launch, on push
delivery, or as a side-effect of any network response.

---

## 2. Prerequisites on the device

The cockpit performs these checks the first time the *Termux Control
Panel* is opened and again every time *Refresh* is tapped. Each check
is best-effort and reversible.

| Check | How | Failure UX |
|------|-----|------------|
| Termux installed | `PackageManager.getPackageInfo("com.termux")` | Install card linking to F-Droid + GitHub release page. Cockpit does not sideload. |
| `RUN_COMMAND` permission granted | Send a no-op `RUN_COMMAND` and inspect the result code. | Instruction card with a button that fires `ACTION_APPLICATION_DETAILS_SETTINGS` for `com.termux` so the user can flip *Run external apps*. |
| `hermes` binary on `$PATH` inside Termux | `RUN_COMMAND` with `/data/data/com.termux/files/usr/bin/command -v hermes` (background mode, capture stdout) | Card explaining the Hermes-Termux install one-liner; no auto-install. |
| Gateway reachable on `127.0.0.1:8080` | Loopback `GET /v1/health` with a short timeout. | The *Start gateway* button becomes the primary action; status flips to *Gateway not running*. |

These checks **do not** read shell output and **do not** evaluate
arbitrary commands — the cockpit only inspects exit codes and short
captured stdout from `command -v`. Anything richer goes through the
HTTP API once the gateway is up.

The hermes-side install path (Termux pkgs + Python venv) is documented
in the repo's main README and in `apps/android/README.md` §2; this
document does not duplicate it.

---

## 3. The RUN_COMMAND envelope

Termux's `RUN_COMMAND` intent takes a fixed schema. The cockpit fills
it as follows for every action.

| Extra | Value |
|------|-------|
| `com.termux.RUN_COMMAND_PATH` | absolute path to the binary inside the Termux prefix (e.g. `/data/data/com.termux/files/usr/bin/hermes`) |
| `com.termux.RUN_COMMAND_ARGUMENTS` | `String[]` of arguments |
| `com.termux.RUN_COMMAND_WORKDIR` | `/data/data/com.termux/files/home` unless the action targets a job workspace |
| `com.termux.RUN_COMMAND_BACKGROUND` | `true` for fire-and-forget; `false` for *Open Termux* so the user sees the session |
| `com.termux.RUN_COMMAND_SESSION_ACTION` | `0` (background) or `1` (open new session, switch to it) |

The intent is sent **explicit** to the
`com.termux/.app.RunCommandService` component name. No package query
helpers are used (the cockpit doesn't declare `<queries>` in the
manifest — see *Limitations* below).

The Kotlin-side wrapper that fills this envelope is
[`TermuxIntentBridge.kt`](../../apps/android/app/src/main/java/com/aci/hermes/data/termux/TermuxIntentBridge.kt)
(stub landing in this phase; full implementation in a follow-up).

---

## 4. Bridge actions

Each action below maps to one method on `TermuxIntentBridge`.

### 4.1 Backend status

**Goal:** answer the question *"is `muse gateway` running inside Termux right now?"*

**How:**

1. Fast path: `GET http://127.0.0.1:8080/v1/health` with a 1500 ms
   call timeout. 2xx → up.
2. Fallback: `RUN_COMMAND` invoking `muse gateway status --plain`
   in background mode, capturing exit code. `0` → up, `1` → down,
   anything else → unknown.

The cockpit never claims *down* off the HTTP failure alone — flaky
loopback during boot is real; the bridge cross-checks via the CLI
exit code before flipping the status pill.

### 4.2 Local API URL

The cockpit treats `http://127.0.0.1:8080` as the canonical local
URL. It exposes a toggle in *Settings → Connection* labelled *"Use
on-device Termux gateway"* which, when on, overrides whatever URL is
otherwise configured. The override is purely local — there is no
"discovery" protocol, no mDNS, no implicit fallback. If the user
points at a different port (because they ran `muse gateway start
--port 8181`), they enter it explicitly.

### 4.3 Wake-lock controls

The cockpit's foreground service holds a partial wake-lock when the
*"Keep device awake while orchestrating"* toggle is on. The wake-lock
is **owned by the cockpit process**, not by Termux — the bridge does
not ask Termux to hold its own wake-lock because:

- Termux already has its own wake-lock notification (`termux-wake-lock`).
- The cockpit's wake-lock is what keeps the foreground notification
  alive on aggressive battery-saver OEMs while the cockpit is the
  active surface; the gateway in Termux is responsible for its own
  lifetime independently.

Toggle behaviour:

| Toggle | Action |
|--------|--------|
| OFF → ON | `HermesService` acquires `PowerManager.PARTIAL_WAKE_LOCK` and tags it `hermes:cockpit:awake`. |
| ON → OFF | Release the wake-lock; the foreground notification stays (the service is still running). |
| App closed | Wake-lock is released on `onTaskRemoved`. There is no headless wake-lock. |

### 4.4 Start the gateway

```
RUN_COMMAND_PATH       = /data/data/com.termux/files/usr/bin/hermes
RUN_COMMAND_ARGUMENTS  = ["gateway", "start", "--no-banner"]
RUN_COMMAND_WORKDIR    = /data/data/com.termux/files/home
RUN_COMMAND_BACKGROUND = true
```

After firing, the cockpit polls `GET /v1/health` every 750 ms for up
to 12 s. Success → flip the *Backend status* card to *up*. Timeout →
keep the card on *unknown*, surface *"Gateway didn't come up in 12 s
— check Termux"* with an *Open Termux* shortcut.

### 4.5 Stop the gateway

```
RUN_COMMAND_PATH       = /data/data/com.termux/files/usr/bin/hermes
RUN_COMMAND_ARGUMENTS  = ["gateway", "stop"]
RUN_COMMAND_BACKGROUND = true
```

After firing, poll `GET /v1/health` until the connection refuses (≤6
s). Flip status to *down* when that happens. The bridge **does not**
escalate to `kill -9`; if `muse gateway stop` doesn't work, the
cockpit tells the user instead of asking Termux to send SIGKILL.

### 4.6 Restart the gateway

`RUN_COMMAND` with `["gateway", "restart"]`. The CLI sends `SIGUSR1`
internally (see `gateway/restart.py`), which the cockpit doesn't need
to know about — it just watches `/v1/health` flap and confirms a new
*started_at* timestamp via `/v1/cockpit/runtime/status` once that route
exists.

### 4.7 Open job folder

The cockpit only offers this when *Settings → Behaviour → Allow Termux
intents from this app* is on. The flow:

1. Read `workspace_path` from the Job object.
2. Fire `ACTION_VIEW` with a `content://` URI from `FileProvider`
   pointing at the workspace path — Termux:Files registers a handler
   for these.

When Termux:Files is not installed, the bridge falls back to a
`RUN_COMMAND` that runs `cd <workspace_path> && exec $SHELL` in a
foreground session, so the user lands in the directory in a normal
Termux shell.

### 4.8 Copy worker prompt

Implemented entirely in the cockpit process — no intent required. The
last dispatched prompt is kept in-memory in `OrchestratorViewModel`
(it's not persisted past process death; secrets-in-prompts hygiene).
The button fires `ClipboardManager.setPrimaryClip(...)` with a label
of `"M.U.S.E. — last worker prompt"`.

### 4.9 Approve publish

This is **not** a Termux intent — it's a regular cockpit action
hitting `POST /v1/cockpit/jobs/{id}/approve`. The Termux Control Panel
just surfaces a *one-tap shortcut* to the most recent job whose state
is `waiting_for_approval` and whose pending decision is *publish*. The
button always opens the standard confirm sheet first.

### 4.10 Approve destructive command

Same shape — `POST /v1/cockpit/approvals/{id}`. Surfaces under
*Pending approvals* on the Control Panel. The confirm sheet quotes
the backend's `summary` field verbatim so the user is never staring
at a vague "approve?" prompt.

### 4.11 View logs

Two paths:

1. **In-app:** route to the *Logs and Events* screen with the source
   filter pre-set to `gateway`. This is the default.
2. **In Termux:** `RUN_COMMAND` (foreground) with
   `["logs", "tail", "-f"]` and `SESSION_ACTION=1` so the user
   lands in a Termux session already tailing. Offered only as a
   secondary action — most users do not need to leave the cockpit.

---

## 5. Permissions and manifest changes

These changes belong in `apps/android/app/src/main/AndroidManifest.xml`
when the bridge is wired live. They are listed here so the cockpit
review can confirm the surface before the code change lands.

```xml
<uses-permission android:name="com.termux.permission.RUN_COMMAND" />
<uses-permission android:name="android.permission.WAKE_LOCK" />

<!-- Optional: lets PackageManager see Termux on Android 11+ so the
     install-status check returns the right answer. Without this the
     bridge falls back to launching by component name and accepting
     ActivityNotFoundException as "not installed". -->
<queries>
    <package android:name="com.termux" />
</queries>
```

`WAKE_LOCK` is not currently in the manifest — the existing local
orchestrator doesn't need it. It is added together with the wake-lock
toggle and not before.

---

## 6. Failure modes

| Failure | UX |
|---------|----|
| Intent fires but Termux is killed by OEM background limits | After 12 s poll timeout, cockpit shows a one-line tip about disabling battery optimisations for Termux, with a button that opens `Settings → Battery → App` for `com.termux`. |
| `RUN_COMMAND` returns `RESULT_CANCELED` | Card explaining the *Run external apps* toggle in Termux's per-app settings; link out. |
| Loopback HTTP succeeds but `/v1/cockpit/runtime/status` 404s | Card *"backend predates Phase 18 — cockpit screens disabled"* with link to the cockpit doc §4.4. |
| User revokes `WAKE_LOCK` permission | Wake-lock toggle silently becomes a no-op; the wake-lock acquire call is wrapped in `try { … } catch (SecurityException) { … }` and degrades to "we asked, OS said no". |

---

## 7. Security stance

- **No silent intents.** Every intent fires from an explicit on-device
  tap or, in the wake-lock case, an explicit toggle.
- **No shell evaluation.** `RUN_COMMAND` arguments are always a fixed
  `String[]`; the cockpit never concatenates user input into a command
  line.
- **No credential pass-through.** Provider API keys, GitHub PATs, and
  the gateway bearer token are not passed through `RUN_COMMAND` extras.
  The gateway's own config is the authoritative store for those.
- **Component-explicit intents.** The cockpit always sets the target
  component name on intents it sends to Termux — there is no implicit
  intent that another package could intercept.

---

## 8. Testing the bridge

Manual:

```bash
# 1. On a debug build with mock-mode off and the bridge enabled,
#    confirm Termux is installed and 'Run external apps' is granted.
adb shell pm list packages com.termux
adb shell appops get com.termux RUN_IN_BACKGROUND

# 2. Inside Termux, install M.U.S.E. and start the gateway once manually:
#      curl -fsSL https://hermes.example/install | bash
#      muse gateway start --no-banner
#    Confirm http://127.0.0.1:8080/v1/health from the host.

# 3. In the cockpit:
#    - Open Termux Control Panel; status should be 'up'.
#    - Tap 'Stop gateway'; status should flip to 'down' within 6 s.
#    - Tap 'Start gateway'; status should flip back to 'up' within 12 s.
#    - Toggle 'Keep device awake'; check `dumpsys power | grep cockpit`
#      shows the partial wake-lock acquired.

# 4. Negative paths:
#    - Disable 'Run external apps' for Termux; tap Start → cockpit
#      should surface the permission card, not hang.
#    - Uninstall Termux; cockpit should switch to the install card.
```

Automated tests live alongside the bridge implementation in
`apps/android/app/src/test/java/com/aci/hermes/data/termux/` (added
together with the live implementation; the stub shipping in this phase
is intentionally not under test yet).

---

## 9. Limitations

- No background, push-driven actions. The cockpit cannot, by design,
  approve a publish for the user from a notification — Android push
  is not a trusted decision channel.
- No daemon-mode "always on" intent listener inside Termux. The bridge
  only emits one-shot `RUN_COMMAND` calls; it does not host a
  long-running RPC channel.
- No script generation. The bridge does not write scripts into the
  Termux home directory; everything it runs is a binary already in the
  M.U.S.E. Termux install.
