# Mobile app guide — Hermes from your phone

This is the plain-English guide to running Hermes from your phone:
what the Android app is, what the backend is, how they talk, what
"approval" looks like on the lockscreen, and how to keep working when
your network drops.

> Looking for the developer spec? See
> [`../android/hermes-apk-cockpit.md`](../android/hermes-apk-cockpit.md)
> and [`../android/hermes-apk-api-contract.md`](../android/hermes-apk-api-contract.md).
> This page is for users.

---

## What the app does

The Android app at [`apps/android/`](../../apps/android/) is a
**cockpit** for a running Hermes backend. It is **not** a
self-contained Hermes — there's no Python, no model, no kanban
database inside the app. It is:

- a **window** into your backend (live job list, task graph, logs),
- an **input** path (typed prompts, voice memos, file attachments),
- an **approval surface** (the green check / red X on high-risk
  phases),
- a **launcher** for the Termux runtime when you run the backend on
  the phone itself.

The mental model is a flight cockpit over an autopilot — the
backend flies; the phone arms switches and reads instruments.

## What the backend does

Wherever you run it — a $5 VPS, your home server, Termux on this
same phone — the backend:

- decomposes goals into the task graph (phases),
- dispatches phases to worker profiles,
- runs validation gates,
- writes the decision ledger,
- holds the long-lived state (jobs, memory, sessions).

The app connects to the backend's **gateway** over HTTP(S). That
gateway is the same one Telegram, Discord, and Slack DMs land on.
Same backend on every surface; only the input/output differs.

---

## Three runtime modes

| Mode | Backend lives where | App reaches it at | Pick when |
|------|---------------------|-------------------|-----------|
| **Remote gateway** *(recommended)* | A VPS, home server, or workstation you control | `https://<your-host>` | You want phone access from anywhere, want the backend to keep running while the phone sleeps. |
| **On-device Termux** | `hermes gateway start` inside Termux on this same phone | `http://127.0.0.1:8080` | You want everything on-device — no cloud, no other machines. |
| **Local handoff (fallback)** | No Hermes backend at all | n/a | You only want the clipboard handoff to Codex / Claude / ChatGPT — the workflow that predates the orchestration stack. |

The cockpit detects which mode is reachable on first launch. You can
change modes any time under **Settings → Mode**.

---

## Phone-first setup

The shortest path to a working cockpit, in roughly the order you'll
do it.

### 1. Install Hermes on your backend host

Pick the host first. Options:

- A **VPS** ($5/month is enough for most personal work).
- A **home server** or always-on laptop.
- **Termux on the phone itself** (works, slower, drains battery).

Install:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
source ~/.bashrc
hermes doctor              # confirm clean install
```

Configure a default model:

```bash
hermes model               # interactive picker
# Or directly:
hermes config set provider openrouter
hermes config set model openrouter/anthropic/claude-sonnet
```

### 2. Start the gateway

```bash
hermes gateway start --listen 0.0.0.0:8080
```

The gateway exposes the HTTP API the app talks to. For a remote
host, put it behind a reverse proxy with TLS — the cockpit refuses
plaintext for non-loopback hosts by default. Caddy is the simplest:

```caddyfile
hermes.example.com {
  reverse_proxy localhost:8080
}
```

### 3. Pair the app to the gateway

In `apps/android` (or the released APK):

1. Open **Settings → Connection**.
2. Enter the gateway URL (`https://hermes.example.com` or
   `http://127.0.0.1:8080` for Termux).
3. Tap **Pair**.
4. The backend prints a 6-digit pairing code in its terminal. Type
   it into the app.
5. The app stores a bearer token in Android Keystore. From now on it
   reconnects silently.

DM-pairing details (for the gateway-DM platforms) live in
[`../../SECURITY.md`](../../SECURITY.md).

### 4. Test the loop

In the cockpit:

1. Tap **+** on the dashboard.
2. Type a small prompt: *"Tell me one thing you remember about me."*
3. Submit.
4. The app shows a streaming response.

If you see the streaming response, the loop works. If not, see
[Disconnect recovery](#disconnect-recovery) below.

The Chat tab shows more than the final words: a **phase rail** (receiving →
thinking → routing → tool → verification → final), compact **tool
activity** you can expand (secrets redacted), tappable **evidence/ledger**
chips, and inline **owner approvals**. Replies can be **continued**,
**copied**, or promoted into a **job**. See
[JARVIS Prime mobile chat](jarvis-chat-streaming.md) for the wire contract
and behaviour.

### 5. (Optional) Build the APK yourself

```bash
cd apps/android
./gradlew assembleDebug
# APK at: app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Release builds and Google Play info are in
[`../../apps/android/README.md`](../../apps/android/README.md).

---

## What you'll see on screen

The cockpit's primary screens are described below (full wireframes in
[`../android/hermes-apk-ui-wireframes.md`](../android/hermes-apk-ui-wireframes.md)).

### Home — the command center
The Home tab is the glanceable state of JARVIS plus the launchpad to every
backend function. When the gateway is paired it shows **live** data pulled
from the cockpit API on open and on pull-to-refresh:

- JARVIS presence (idle / listening / thinking / working / waiting-for-
  approval / serious / critical / service-stopped / emergency-stop / mock),
- gateway connection pill and current **model/router** policy
  (`GET /v1/cockpit/models`),
- **active jobs** (`/jobs`), **pending approvals** (`/approvals`, risk-
  coloured), **running workers** (`/runtime/workers` + queue),
- **recent memory updates** (`/memory`), **recent evidence/research**
  (`/research`), and the **last audit/ledger events** (`/events`),
- on-device **voice/listening** state and **device capability** (RAM/API),
- an always-present **Emergency Stop**.

Quick actions launch the powerful paths: **Ask JARVIS**, **Audit repo**,
**Continue coding**, **Run tests**, **Review patch**, **Approvals**,
**Memory**, **Start voice**, and **Stop all work**. Actions that imply
external or irreversible work open the owner-gated authoring/approval
screens — Home never auto-dispatches them.

Every card deep-links into its detail screen. When the gateway is **not
paired or unreachable**, Home shows a useful banner (pair / retry) and falls
back to local task-derived state instead of a blank screen — no fabricated
data is ever shown.

**Stop all work** engages the audited emergency-stop controller (state
machine + decision ledger), cancels every non-terminal cockpit job, and
stops the foreground service. Deactivating it writes a resume event to the
same ledger.

### Dashboard
Live list of jobs and active phases. Each row shows:
- job title (first line of the prompt),
- current state (`planning`, `running`, `validating`, `done`,
  `blocked`, `failed`, `escalated`),
- a progress bar across the phase graph,
- a pulsing dot when an approval is waiting.

### Job detail
Tap a job → task graph view. Each phase shows its assignee profile,
state, and last log line. Tap a phase → its trace, gate result,
input, and output.

### Approvals
A dedicated screen for any phase in `escalated` state. Each card
shows what's being asked, the previewed change (diff, message, file
write), and three buttons: **Approve**, **Deny**, **Defer**. Buttons
write directly to the kanban; the backend resumes the job.

### Activity timeline
The answer to *"what did JARVIS do?"* — reached from the **Activity**
action on the Audit screen. It streams the orchestrator's event ledger
(every job's `ledger.jsonl`) as one redacted, filterable timeline: worker
runs, commands, file edits, approvals, validations, deploy/publish
attempts, navigation, and more. Filter by **job, risk, worker, date, or
file**. Tap a row → what happened, why, the redacted inputs/outputs, any
linked evidence and diff, and the rollback plan.

The timeline is **read-only** and **never shows a secret** — credentials a
worker may have echoed are scrubbed server-side and again on the device. A
**Request rollback** button queues an *owner-gated* approval; nothing is
rolled back until you approve it with your owner phrase in **Approvals**.

### Voice
Hold-to-talk capture. The app streams audio chunks to the gateway,
which transcribes (server-side Whisper or your configured STT) and
submits the resulting prompt. See
[voice/voice-first-user-guide.md](../voice/voice-first-user-guide.md).

---

## Device control — letting Jarvis operate the phone

The Android cockpit can physically operate the phone for you — run to an
app, push it open, scroll, turn the home-screen page, go back/home — driven
by voice ("open Facebook", "scroll down", "go home"). This is the
**mobile-native device-control** path, and it is built to keep you aware
and in control at every step.

Reach it from **Control → Device control**. The screen has five parts:

1. **Master switch.** Until you turn *Device control* on, nothing runs —
   every spoken command is logged and refused. It defaults **off** on a
   fresh install.
2. **Capabilities.** Six rows, each with a plain-English reason and a live
   "granted by system / not granted" chip: **accessibility** (the hands),
   **display over other apps** (the floating avatar), **microphone**
   (hands-free voice), **notifications**, **installed-app visibility**, and
   **local backend connection**. You consent to each one explicitly and can
   revoke consent instantly — the action layer honors the change
   immediately, even if the OS permission is still granted.
3. **Confirm sensitive actions.** On by default: launching an app or
   tapping a target waits for your OK rather than running from voice. A held
   command appears at the top of the screen as a **Confirm action** card with
   **Approve** / **Dismiss** — Approve runs it (re-checked against the
   emergency stop, master switch, and permissions, so a stale approval can't
   bypass them); Dismiss logs it and drops it. You can turn confirmation off
   for hands-free high-power mode — that toggle is owner-gated (a confirmation
   dialog), and every action is still logged. An action whose target can't be
   resolved (a misheard or uninstalled app) is refused outright, never run as
   a blind tap.
4. **Active indicator + emergency stop.** A live status dot shows whether
   device control is active right now. One **Emergency stop** drops every
   in-flight gesture, stops the floating avatar and the voice loop, and
   refuses new actions until you release it. The global emergency stop in
   the top bar does the same thing in addition to halting the orchestrator.
5. **Recent device actions.** An append-only, on-device log of *every*
   action Jarvis took or was refused — newest first — so "what did Jarvis
   do on my phone?" is always answerable.

**How a command flows.** Every device action passes through one broker
chokepoint (`data/devicecontrol/DeviceActionBroker`): emergency stop →
master switch → required capability granted *and* consented → sensitive
confirmation → approve. Nothing executes that the broker did not approve,
and the broker writes a ledger entry for the decision either way. No screen
contents, transcripts, or secrets are ever logged — only the action's
label, its sensitivity, the outcome, and a reason.

No new sensitive permissions were added for this — accessibility, overlay,
microphone, notifications, and package visibility are the same ones the
personal-tool fork already declares.

---

## How approvals work on the lockscreen

When a phase escalates:

1. The backend marks the phase `escalated` and writes an `ESCALATE`
   entry to the ledger.
2. The cockpit gets a **push notification** with a preview.
3. Tapping the notification opens the **Approvals** screen for that
   phase.
4. **Approve** / **Deny** / **Defer** writes back to the kanban over
   the gateway. The backend resumes within seconds.

Three rules to remember:

- **No silent automation on HIGH-risk phases.** Anything that touches
  GitHub, Vercel, Supabase, or external messaging classifies as HIGH
  by `enterprise/policy.py`. It will always ask.
- **Same backend on every surface.** Approve from the cockpit, from
  the CLI on your laptop, or from a Telegram DM — they all hit the
  same kanban state. Whichever responds first wins.
- **Defer is not approve.** If you defer with a reason, the phase
  re-asks later. If you ignore the push notification, the phase sits
  in `escalated` indefinitely.

---

## How voice capture works on mobile

The Voice tab is the same gateway endpoint as Telegram voice memos,
just wrapped in a hold-to-talk UI:

1. Hold the mic button. The app records audio (Opus, ~32 kbps).
2. On release, audio uploads to the gateway.
3. The gateway transcribes with your configured STT (default:
   Whisper running locally on the backend; remote Whisper or Deepgram
   if you've configured them).
4. The transcript is submitted as a turn.
5. The agent's reply is streamed back as text; if you've enabled
   TTS in **Settings → Voice → Read replies aloud**, the gateway
   also returns audio.

The voice-first user guide covers driving mode, wake-word, and
how to keep audio entirely on-device:
[voice/voice-first-user-guide.md](../voice/voice-first-user-guide.md).

---

## Driving mode safely

The cockpit's **driving mode** is a focused subset of the UI designed
to be used at a glance, with audio prompts replacing visual ones.

Safety guardrails — these are not optional:

- **No HIGH-risk approvals.** Any phase that would normally ask for
  approval is **automatically deferred** while driving mode is on.
  You won't be asked to approve a PR open / a Vercel deploy while
  the car is moving.
- **No text input.** The keyboard is hidden. Only voice and the big
  red **Cancel** button are reachable.
- **Wake word optional.** If enabled, the wake word ("Hey Hermes")
  only arms a single capture — it doesn't leave the mic open.
- **TTS is short-form.** Replies longer than 60s of speech truncate
  to a summary; the full reply is queued for after-drive review.
- **Auto-off on stop.** Driving mode disables itself when the phone's
  motion sensors report a sustained stop, or when you tap the lock
  icon.

You activate it from **Settings → Driving mode** or via the
voice command *"Hermes, start driving mode."* You exit with
*"Hermes, stop driving mode"* or by tapping the lock icon. The full
behavior is in [voice/voice-first-user-guide.md §driving-mode](../voice/voice-first-user-guide.md#driving-mode).

---

## How phases work, from the phone's POV

A phase (kanban card) is one validatable unit of a larger job.
The cockpit shows them as nodes in the job-detail graph. Each node
cycles through:

```
todo  →  ready  →  in_progress  →  validating  →  done
                                        ↓
                                   escalated / failed
```

- **todo** — has parent phases that aren't done yet.
- **ready** — dispatcher will claim it next.
- **in_progress** — worker is running, streaming a trace.
- **validating** — output is in the gate (schema/policy/judge).
- **done** — gate passed.
- **escalated** — gate triggered a HIGH-risk check; you need to
  approve.
- **failed** — gate failed all retries.

When a phase is `escalated`, the cockpit shows a yellow pulse on the
node and pushes the approval notification.

---

## How workers are chosen (from the user's view)

The orchestrator looks at:

1. **The phase's nature.** A research phase prefers a `researcher`
   profile; a code-change phase prefers `engineer`. The orchestrator
   skill (`kanban-orchestrator`) writes the assignee.
2. **Which profiles you have configured.** `hermes profile list`
   shows the set. Unknown assignees stall in `ready` — the dispatcher
   never invents profiles.
3. **Routing rules.** `orchestration.routing` in
   `~/.hermes/config.yaml` can override per-phase based on cost,
   sensitivity, latency, or any tag.
4. **Budget.** If the job has a budget cap, the router downshifts
   to a cheaper model when the cap nears.

You don't have to memorize this — the cockpit's job-detail screen
shows the chosen worker (model + profile) for every phase.

---

## Disconnect recovery

Phones lose signal. Here's what survives.

**Backend keeps running.** As long as the gateway process is alive,
phases keep moving regardless of whether the app is connected.

**Cockpit reconnects automatically.** On regaining network it
re-subscribes to the event stream and rehydrates from the gateway
state.

**Approvals queue, not block.** A phase in `escalated` stays
`escalated` until someone responds — the orchestrator does not
time out the human. (You can configure a deadline if you want.)

**Push notifications retry.** The gateway uses HTTP/2 server push
or FCM (depending on your build) with retries. If the phone is off,
the notification is delivered when it comes back online.

If the cockpit shows stale state after a long disconnect:

1. **Pull-to-refresh** on the dashboard.
2. If that doesn't update, **Settings → Connection → Reconnect**.
3. If that doesn't help, the gateway is probably actually down.
   Restart it on the backend and pull-to-refresh again.

---

## Prompt examples (from a phone)

Phone prompts work best when they're declarative and one-shot. Some
that work well:

| Prompt | What you'll get |
|--------|-----------------|
| *"Summarize my GitHub notifications from the last 24 hours."* | A digest in the chat pane. |
| *"Open a draft PR on my-org/web that adds a CHANGELOG.md."* | The orchestrator decomposes, opens a PR, posts the URL. Asks for approval before the PR step. |
| *"Audit my Supabase project for missing indexes."* | A report via the Supabase MCP. |
| *"Deploy the current `feat/onboarding` branch to a Vercel preview."* | Vercel MCP creates a preview, posts the URL. |
| *"Remember: my GitHub username is `echerd27`."* | The agent stores it in memory. |
| *"What's blocking my draft PRs right now?"* | Reads CI status + last comment per PR, summarizes. |
| *"Start orchestrated job: refactor the auth tests."* | Full orchestrator run; phases on the graph view. |

The cockpit shows the same `/orchestrate`, `/orchestrator status`,
and `/<skill-name>` slash commands that work in the CLI. Typing them
in the chat input is equivalent to typing them in the terminal.

---

## Where does the data live?

- **The conversation** — on the backend, in `~/.hermes/sessions.db`.
- **The jobs** — on the backend, in `~/.hermes/jobs/`.
- **The memory** — on the backend, in the configured memory backend
  (SQLite by default).
- **The bearer token** — on the phone, in Android Keystore. Erasable
  by uninstalling the app.
- **No prompts or transcripts on the phone.** The app caches what
  it needs to render the current screen; rotate the phone and the
  cache reloads from the gateway.

So losing the phone = lose the bearer token = revoke from the
backend with `hermes gateway revoke-token <phone-id>` and that's it.
None of your conversation or job history was on the phone.

---

## What the Termux runtime adds

If your backend lives in Termux on the phone, the cockpit launches
and monitors it for you:

- **Settings → Termux runtime → Start.** Sends the right intent into
  Termux to run `hermes gateway start --listen 127.0.0.1:8080`.
- **Settings → Termux runtime → Stop.** Graceful stop with state
  flush.
- **Settings → Termux runtime → Status.** PID, uptime, last log
  line, the gateway's reachable URL.

The full Termux setup (model server, llama.cpp, environment
hardening) is documented in
[`../termux/hermes-phone-first-runtime.md`](../termux/hermes-phone-first-runtime.md)
and [`../termux/hermes-termux-boot.md`](../termux/hermes-termux-boot.md).

---

## Quick reference table

| You want to… | Tap |
|--------------|-----|
| Start a job | **+** on dashboard |
| Watch a job in real time | Dashboard → job row |
| See a phase's trace | Job detail → node → **Trace** |
| Approve / deny / defer | Approvals tab (or notification) |
| Switch model | Chat → ⋮ → **Model** |
| Cancel a job | Job detail → ⋮ → **Cancel** |
| Reload skills | Chat → `/reload-skills` |
| Read the ledger | Job detail → ⋮ → **Ledger** |
| Disconnect / reconnect | Settings → Connection |
| Toggle driving mode | Settings → Driving mode |

---

## See also

- [voice/voice-first-user-guide.md](../voice/voice-first-user-guide.md)
  — voice capture, driving mode, TTS.
- [remote/windows-claude-code-bridge-guide.md](../remote/windows-claude-code-bridge-guide.md)
  — using Hermes on the phone to drive a Windows Claude Code session.
- [security/private-local-security-guide.md](../security/private-local-security-guide.md)
  — keeping the on-device path fully private-local.
- [orchestration/getting-started.md](../orchestration/getting-started.md)
  — the canonical "first job" walkthrough, applies to the phone too.
- [troubleshooting/hermes-orchestration-troubleshooting.md](../troubleshooting/hermes-orchestration-troubleshooting.md)
  — symptom-to-fix table.
