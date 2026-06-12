# M.U.S.E. Local Orchestrator (Android)

M.U.S.E. is a **private personal orchestration tool**. It runs on a single
device, helps the user organize work, and hands tasks off to the
official AI tools the user is already logged into. It is not a
commercial product and it is not on the Play Store.

## What M.U.S.E. is

- A local Android app that runs `HermesService` as a foreground service
  while the app is alive.
- A dashboard that lists official AI tools (Codex / OpenAI, ChatGPT,
  Claude Code, Claude) and a local task list.
- A structured-prompt builder that drafts a handoff prompt for each
  task, tuned for the target tool's role (builder / planner / reviewer
  / architect).
- A clipboard + deep-link handoff helper that requires an explicit user
  tap for every external action.

## What M.U.S.E. is not

- **Not** a commercial subscription app — no Google Play Billing, no
  in-app purchases, no paywall, no product IDs.
- **Not** an unofficial OpenAI / Anthropic API proxy. The Android app
  does not call those APIs at all in the primary workflow. There are
  no provider API key fields wired up, and the `Use API keys` toggle
  in Settings stays off by default.
- **Not** a credential broker. M.U.S.E. does not scrape cookies, extract
  tokens, automate hidden login flows, or read another app's storage.
- **Not** an autonomous agent. Every external action (copy to
  clipboard, open external app) requires a tap.

## Lifecycle

```
App launch
    │
    ▼
MainActivity.onCreate
    │  ├─ ContextCompat.startForegroundService(Intent(this, HermesService))
    │  └─ (Android 13+) request POST_NOTIFICATIONS once
    ▼
HermesService.onStartCommand
    │  ├─ Log: "M.U.S.E. local orchestrator started"
    │  ├─ Log: "Launch source: app_start"
    │  ├─ Log: "Mode: local_subscription_tools"
    │  └─ startForeground(NOTIFICATION_ID, notification,
    │                     FOREGROUND_SERVICE_TYPE_DATA_SYNC)
    ▼
Dashboard (Orchestrator screen)
    │
    └─ User creates / opens tasks → PromptBuilder → manual handoff
```

`HermesService` is declared `android:exported="false"` and has no
intent-filter. The persistent notification surfaces a Stop action so
the user can shut the service down at any time without uninstalling
the app.

## Why this design avoids direct API billing without bypassing
authentication

M.U.S.E. does not call OpenAI, Anthropic, or any other provider directly
from the device. It prepares a structured prompt, the user copies that
prompt into the official ChatGPT / Codex / Claude / Claude Code app
they are already logged into, and the official tool handles
authentication and billing on its own terms. No keys are stored on the
device, no cookies are scraped, no automated login is attempted.

This means M.U.S.E. piggy-backs on the user's existing subscriptions
(which are paid through the providers' normal channels) instead of
duplicating their billing surface — and it does so without crossing
any of the lines provider terms care about.

## Manifest exposure

```xml
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />

<service
    android:name=".service.HermesService"
    android:exported="false"
    android:foregroundServiceType="dataSync" />
```

`FOREGROUND_SERVICE_DATA_SYNC` is required because the project targets
SDK 35 and the service declares `foregroundServiceType="dataSync"`.
There is no intent-filter; no other process can start `HermesService`.

## Local storage

- **Settings** — DataStore Preferences (`hermes_settings`). Holds
  theme, orchestrator preferences, and the safety / clipboard / external-
  app toggles. No secrets.
- **Tasks** — JSON file at `filesDir/hermes_tasks.json` via
  `kotlinx.serialization.json`. Small dataset, single file, easy to
  inspect via `adb shell run-as com.aci.hermes.debug cat ...` while
  debugging.
- **No EncryptedSharedPreferences blob.** The legacy `SecureKeyStore`
  was removed when the in-app Chat / Provider flow was retired.

## Limitations

- M.U.S.E. cannot silently consume ChatGPT / Claude subscriptions like an
  API. Every handoff is a user-driven copy/paste or deep link.
- M.U.S.E. cannot drive Claude Code unless using its official allowed
  workflows. There is no headless Claude / Codex driver in this app.
- The Android app cannot directly run desktop CLI tools without a
  bridge. The "Open tool" action is best-effort: it tries known
  package names, falls back to the official web URL if the user has
  enabled external opening, and otherwise tells the user to do it
  manually.
- Manual handoff may be required (and that is the default mode).
- Provider usage limits, rate limits, and account suspensions still
  apply — they are provider-side concerns.
- This app is not Play Store-ready and is not intended to be. There is
  no telemetry, no analytics, no remote config, and no in-app updates.

## Backend pipeline integration

The Android app is the **cockpit**. The M.U.S.E. backend (CLI + gateway
running on a VPS, home server, laptop, or Termux on the same device) is
the **engine**. The cockpit never runs the orchestration pipeline by
itself — it issues commands, displays state, and surfaces approvals.

When the user creates a task in the cockpit, it can be handed off in two
ways:

1. **Manual handoff** (default) — copy the structured prompt to the
   clipboard or deep-link into the official ChatGPT / Claude / Codex
   app, as described above. The orchestration pipeline is not used.
2. **Pipeline handoff** — the cockpit hits the backend gateway with a
   job-folder request. The backend then runs the orchestration
   pipeline described in `AGENTS.md` ("Orchestration pipeline skills"):

   - `hermes-orchestration-pipeline` reads the job folder.
   - `aos-full-agent-team` spawns planner / builder / reviewer / architect roles.
   - `model-router` resolves task type to model using
     `docs/ai-intelligence/model-registry.yaml` and
     `docs/ai-intelligence/model-routing-policy.md`.
   - `decision-quality-gate` validates each non-trivial decision against
     `docs/orchestration/decision-ledger.md`.
   - `research-validator` cross-checks external claims.
   - `ai-improvement-radar` and the competitive feature harvester at
     `docs/competitive/openhuman-paperclip-research.md` feed the
     `self-improvement-loop`, which can propose patches to M.U.S.E.
     itself via `github-publisher`.

Cockpit invocations map onto the same slash commands that work in the
CLI and on any messaging gateway:

```text
/reload-skills
/aos-full-agent-team <goal>
/hermes-orchestration-pipeline <job-id>
/model-router <task-type>
/decision-quality-gate <decision-id>
/ai-improvement-radar
/github-publisher <branch>
```

**Posture stays private and local-first.** The cockpit never sends task
content to a third party on its own — only the backend the user
controls. The pipeline ledger (`ledger.jsonl` per job folder) stays on
the backend's filesystem; the cockpit reads summaries over the gateway.

## Resetting

Settings → Reset all settings and tasks clears both the DataStore
Preferences file and the `hermes_tasks.json` file. If you ever want to
nuke the app from orbit, use Android's system Settings → Apps → M.U.S.E.
Agent → Storage → Clear data — that drops the entire app's
`filesDir`.
