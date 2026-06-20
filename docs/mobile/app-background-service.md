# Mobile cockpit — Background service

> The cockpit is a thin client, but it still has work to do when no
> Activity is visible: tail the events stream, drain the offline
> queue, hold the wake-lock while orchestrating in Termux, and surface
> push-style notifications when the gateway needs an on-device
> approval.

## 1. The service

`com.aci.hermes.service.HermesService` already exists as a stub. In
Phase 20 it becomes the single foreground service the cockpit runs
when there is work to keep alive in the background.

A second short-lived foreground service —
`com.aci.hermes.service.VoiceCaptureService` — runs only while the
mic is open. The two services are intentionally separate so revoking
microphone permission cannot disable event tailing or wake-lock
behaviour.

```
HermesService                  (foregroundServiceType="dataSync")
├── EventStreamWorker          collects EventRepository.stream(*)
├── JobStreamWorker            collects JobRepository.stream(filter)
├── OfflineQueueWorker         drains OfflineQueueRepository
├── WakeLockController         partial wake-lock, toggled from UI
└── NotificationDirector       maps gateway events → notifications
```

Each worker is a top-level coroutine on the service's
`serviceScope` (`SupervisorJob() + Dispatchers.Default`). One worker
crashing cancels only its own job; the others keep running.

## 2. Lifecycle

```
App launched / cold start
  └─ MainActivity.onCreate
        └─ AppContainer.lazy.cockpitClient initialised
        └─ HermesService.start(reason = APP_LAUNCH)

User toggles "Keep device awake while orchestrating" on
  └─ HermesService.requestWakeLock(true)

User backgrounds the app, gateway has running jobs
  └─ Service stays alive; foreground notification stays sticky
  └─ EventStreamWorker continues; JobStreamWorker continues

User backgrounds the app, gateway has no running jobs and no
queued offline writes
  └─ Service stops itself after a 60s grace window

User force-stops the app
  └─ Service dies; OS notification disappears
```

`startForeground` is called within 5 s of `onCreate`, with a
notification belonging to the *Cockpit status* channel
(`importance = LOW`). The notification's content reflects live state
(see §6).

## 3. Channels

```kotlin
object CockpitChannelIds {
    const val STATUS = "cockpit.status"                  // LOW, no sound
    const val APPROVAL_NEEDED = "cockpit.approval"       // HIGH, vibration
    const val DESTRUCTIVE_NEEDED = "cockpit.destructive" // HIGH, vibration + sound
    const val PUBLISH_RESULT = "cockpit.publish"         // DEFAULT
    const val OFFLINE_QUEUE = "cockpit.offline"          // LOW
    const val VOICE_ACTIVE = "cockpit.voice"             // LOW, on-going
    const val SERVICE_ERROR = "cockpit.error"            // DEFAULT
}
```

Channels are created in `HermesApplication.onCreate()` so they exist
before the first notification post.

## 4. Notification matrix

| Trigger | Channel | Notification |
|---|---|---|
| Foreground service running | `STATUS` | *muse cockpit is connected to <host>.* Subtext: queue summary. |
| Job moved to `waiting_approval` | `APPROVAL_NEEDED` | *Job <id> needs approval.* Actions: **Approve**, **Open**. |
| Backend requested destructive confirmation | `DESTRUCTIVE_NEEDED` | *Backend wants to force-push.* Actions: **Allow once**, **Deny**, **Open**. |
| Publish succeeded | `PUBLISH_RESULT` | *PR opened: <pr_url>* — tap opens the URL in the browser. |
| Publish failed | `PUBLISH_RESULT` | *Publish failed: <reason>.* Action: **Open job**. |
| Offline queue has pending writes | `OFFLINE_QUEUE` | *<n> pending writes — waiting for gateway.* Action: **Retry now**. |
| Voice service active | `VOICE_ACTIVE` | *Listening…* Action: **Stop listening**. |
| Streams disconnected >60 s | `SERVICE_ERROR` | *Lost connection to gateway.* Action: **Reconnect**. |

Notification taps deep-link to the relevant screen via the route
constants in
[`ui/navigation/Screen.kt`](../../apps/android/app/src/main/java/com/aci/hermes/ui/navigation/Screen.kt).

## 5. Offline queue drain

`OfflineQueueWorker`:

1. Subscribes to `OfflineQueueRepository.flow` and to
   `RuntimeRepository.reachability`.
2. While `reachability = Connected`, drains pending writes in FIFO
   order.
3. For each write:
   - Issue the original `POST` with the saved `Idempotency-Key`.
   - On `2xx` → mark confirmed in `DecisionLedgerCache`, drop the
     write from the queue.
   - On `4xx` (other than `429`) → mark failed in
     `DecisionLedgerCache` with the error code; drop from queue. The
     UI surfaces the failure on the next screen render.
   - On `5xx` or transport error → increment `attempts`, back off
     using `min(2^attempts * 2s, 60s)`; if `attempts >= 8`, mark the
     write **stuck**, raise a `SERVICE_ERROR` notification, and stop
     auto-retrying. Stuck writes only retry on explicit user action.
4. The queue UI badge ticks down in lockstep with the drain.

## 6. Wake-lock

Holding a partial wake-lock while orchestrating in Termux is the
single most-requested feature for on-device jobs. Phase 20 wires
this up:

- `WakeLockController.requestWakeLock(true)` calls
  `PowerManager.newWakeLock(PARTIAL_WAKE_LOCK, "hermes:cockpit").acquire()`.
- The status notification's subtext reads *"Holding wake-lock"*.
- `requestWakeLock(false)` or service destruction releases it.
- The wake-lock is **not** held automatically — the user toggles it
  from *Settings → Behaviour → Keep device awake while orchestrating*
  or from the Termux Control Panel.

CI greps for accidental wake-lock-without-release patterns. The
controller exposes only the boolean toggle; raw `WakeLock` is not
addressable from anywhere else.

## 7. Coupling with the gateway

The service does **not** poll. Everything it does is event-driven:

- SSE on `/v1/cockpit/jobs/stream` for state changes.
- SSE on `/v1/cockpit/events/stream` for the global event tail.
- Local Android signals (connectivity, Bluetooth) flip
  `RuntimeRepository.reachability`.
- The voice service emits its own phase flow to the
  `NotificationDirector`.

When the gateway pushes a future feature like `pushApprovalNeeded`,
the SSE stream is where it arrives — the cockpit does not grow a
second listening channel.

## 8. Battery and data hygiene

- Streams are torn down whenever there are no live UI consumers
  **and** no pending offline writes **and** no running jobs.
- The grace window is 60 s after the last consumer disconnects, so
  flipping back to the app within a minute does not pay a reconnect
  cost.
- The service registers a `ConnectivityManager.NetworkCallback` and
  pauses streams immediately on `onLost`. It resumes on
  `onAvailable` plus a 1 s settle.
- Re-subscribing uses the same `since=<last_event_ts>` semantics the
  gateway promises, so the cockpit never replays the entire stream
  on every reconnect.

## 9. Crash + ANR handling

- Uncaught throwable in a worker → caught at the supervisor boundary,
  logged to `LogBuffer`, posted as a `SERVICE_ERROR` notification.
  The other workers continue.
- Recurring crashes (>3 in 60 s) flip the service into a *degraded*
  state — the foreground notification reads
  *"Cockpit is in degraded mode. Open *Diagnostics* for details."*
  and the worker that's failing is left disabled until the user
  taps *Reset workers* in Diagnostics.
- The service never auto-resets the user's connection settings on
  failure. Failures fix forward, not by forgetting state.

## 10. Tests

- **Worker isolation:** unit tests forcibly throw inside one worker
  and assert the others keep running.
- **Drain ordering:** queue tests confirm FIFO and that backoff
  honours `attempts`.
- **Reconnect tests:** the SSE worker is fed a `IOException` and a
  retry budget; assert the resubscribe carries `since=` correctly.
- **Notification snapshot tests:** golden text for every entry in
  the §4 matrix so accidental wording changes show up in code
  review.

## 11. Files

| File | Purpose |
|---|---|
| `service/HermesService.kt` | existing scaffold; promoted to host the workers below |
| `service/notifications/CockpitChannelIds.kt` | NEW |
| `service/notifications/CockpitNotifications.kt` | NEW; renders the §4 matrix |
| `service/notifications/NotificationDirector.kt` | NEW; subscribes to repos and posts notifications |
| `service/workers/EventStreamWorker.kt` | NEW |
| `service/workers/JobStreamWorker.kt` | NEW |
| `service/workers/OfflineQueueWorker.kt` | NEW |
| `service/workers/WakeLockController.kt` | NEW |
| `data/queue/OfflineQueue.kt` / `PendingWrite.kt` | NEW (see state-model doc) |

## 12. Non-goals

- **No WorkManager.** muse orchestration is interactive; deferring
  to OS-scheduled `WorkRequest`s would smear latency across minutes
  and produce a worse UX than a foreground service. We accept the
  trade-off of higher battery usage while jobs are in flight.
- **No FCM / WebPush yet.** Phase 21 candidate; tracked as
  *not wired up* in
  [`apps/android/README.md`](../../apps/android/README.md) and
  Phase 18 §6.
- **No background recognition.** The mic is never opened without a
  visible foreground UI and an explicit user tap.
- **No silent retries on `4xx`.** A `403` is the user's problem to
  solve, not the cockpit's to paper over.
