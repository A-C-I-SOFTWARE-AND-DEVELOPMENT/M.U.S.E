# Demo — Android cockpit + Termux runtime

Two ways to use M.U.S.E. Orchestration from a phone, and one hybrid
that combines them. None of these require an app-store install — the
Android app side-loads from CI artifacts, and Termux is open-source
on F-Droid.

| Mode | Backend lives… | Best for |
|---|---|---|
| **Cockpit + remote backend** | On your VPS / laptop | Day-to-day, "approve from anywhere" |
| **Cockpit + Termux backend** | On the phone itself | Travel, no-internet field work |
| **Termux-only** | On the phone, no cockpit | Power users, scripts, demos |

The cockpit is the native Android app at
[`apps/android`](../../apps/android/). It is a **thin client** — it
does not embed a model and it does not run agents itself. It talks
to a M.U.S.E. gateway, wherever that gateway happens to live.

## Cockpit, in 60 seconds

Side-load the debug APK:

```bash
# from a workstation with adb
cd apps/android
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

…or grab the latest CI artifact from
`.github/workflows/android-build.yml` and copy it to the phone.

First launch shows the **Connection** screen. Three modes:

1. **Remote M.U.S.E. gateway** (recommended). Paste the URL of a
   running gateway (e.g. `https://hermes.your-domain.tld`) and a
   bearer token. Tap **Test connection**.
2. **Local Termux gateway**. Default URL `http://127.0.0.1:8080`.
   Requires Termux + M.U.S.E. installed on the same device — see the
   Termux section below.
3. **Mock mode**. Sandboxed UI with canned responses. No backend
   required. Good for exploring the orchestrator pane before
   wiring anything up.

Pick one, tap **Connect**, and you're at the dashboard. The
foreground service starts and stays alive while the app is open.
Persistent notification has a **Stop** action so you can shut it
down without uninstalling.

## Driving the orchestrator from the phone

### Start a job

The cockpit's bottom-nav has an **Orchestrator** pane. Tap **+ New
job**, paste your goal, optionally pick a delivery target, tap
**Run**. Same wire format as `/orchestrate`, same result.

### Watch jobs

The Orchestrator pane lists active jobs, one row per job, color-
coded by state. Tap a job to drill into its task graph. Tap a card
to see its trace.

### Respond to escalations

When a card escalates (HIGH-risk mutation, repeated judge failure,
or explicit `kanban_block`), you get an Android notification. Swipe
into the cockpit, the escalation banner shows the card, the
proposed mutation, and three buttons: **Approve**, **Deny**,
**Defer**. Tap one. The response goes back over the gateway and the
worker resumes.

If the phone is locked, the notification has the same three
actions. You never have to unlock to triage.

## Cockpit + remote backend (recommended)

Run the gateway on your VPS or home server:

```bash
ssh user@your-vps
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
muse setup           # wizard, includes provider keys
muse gateway setup   # pick auth, set bearer token
muse gateway start   # foreground, or use systemd
```

Open `https://hermes.your-domain.tld/v1/health` from the phone to
confirm reachability. Paste the URL + bearer into the cockpit. Done.

Tradeoffs:

- ✓ Real models, big context, fast — your VPS does the heavy lift.
- ✓ Jobs survive the phone disconnecting.
- ✓ Multi-device — laptop and phone watch the same jobs.
- ✗ Needs a server (a $5 VPS is fine).
- ✗ Needs network to your server.

## Cockpit + Termux backend

When you want everything on the phone — no server, no network round
trip.

### Install Termux

From F-Droid (preferred — the Play Store build is frozen):
<https://f-droid.org/en/packages/com.termux/>

### Install M.U.S.E. in Termux

```bash
pkg update && pkg upgrade -y
pkg install -y python rust git binutils-is-llvm \
    clang libjpeg-turbo libxml2 libxslt openssl rustc

# Termux constraints file pins Android-compatible versions.
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | \
  PIP_CONSTRAINT=https://raw.githubusercontent.com/NousResearch/hermes-agent/main/constraints-termux.txt bash
```

On Termux, M.U.S.E. installs `.[termux]` instead of `.[all]` — the full
extra pulls Android-incompatible voice deps. Everything orchestration
needs is in `.[termux]`.

### Start the gateway in Termux

```bash
muse setup           # at minimum, pick a provider and add a key
muse gateway setup   # bearer auth, bind to 127.0.0.1 only
muse gateway start   # leave Termux open or use termux-services
```

The gateway binds to loopback by default. The Android cockpit on the
same device can reach it at `http://127.0.0.1:8080`. Nothing on the
LAN can.

### Wire up the cockpit

In the cockpit's **Settings → Connection**, switch to **Local Termux
gateway**, paste the bearer token, tap **Test connection**, then
**Connect**.

That's a fully self-contained M.U.S.E. Orchestration setup on one
device, no cloud, no network. The orchestrator profile, kanban
dispatcher, judge, worker — all of it runs inside the Termux
sandbox.

Tradeoffs:

- ✓ Genuinely offline. Survives airplane mode. Survives a flight.
- ✓ No server bill. No data leaves the device.
- ✗ Model choice is limited to what Termux can reach — typically a
  remote API key still (OpenRouter, Anthropic, …). For *fully*
  offline, point at a local llama.cpp / Ollama server also running in
  Termux.
- ✗ Long jobs drain battery. Keep the device charging.
- ✗ Some heavy tools (browser automation, video gen) are not
  realistic in Termux. Stick to text / code / web fetch.

## Termux-only (no cockpit)

For demos, scripts, or just preference, you can drive the whole
orchestration loop from the Termux shell. Skip the cockpit entirely.

```bash
# Termux
muse
> /orchestrate Audit this repo and write a short report.
> /orchestrator status
```

…or scripted:

```bash
bash scripts/hermes-orchestrate.sh "Audit this repo and write a short report." \
  --deliver file
```

The output file lands in `~/.hermes/jobs/<id>/output/`, which is
just the Termux home dir. `pkg install vim` if you need an editor.

## Hybrid — phone-driven escalations on a remote backend

The most common production setup:

- **Backend on a server** (laptop / VPS / home box). Long-running,
  full toolset, real models.
- **Android cockpit on the phone.** Notifications for escalations,
  approve/deny from anywhere.
- **Termux on the phone** as a fallback — when the server is
  unreachable, you still have a working M.U.S.E. you can talk to.

The cockpit's connection setting can store multiple profiles. Tap
the profile picker on the connection screen to switch between
"remote-VPS" and "local-termux" without re-entering credentials.

## Common questions

**Does the cockpit work without a Google account?**
Yes. There is no Google Play Services dependency in the debug build.
F-Droid builds are forthcoming.

**Does Termux need root?**
No. M.U.S.E. runs entirely in the Termux user sandbox.

**Can I run the orchestrator and watch the same job from both
phones?**
Yes — both cockpits point at the same gateway, the dashboard is
just a view. You won't see merge conflicts; the job state lives in
SQLite on the gateway side.

**What happens if the phone reboots while a job is running?**
On a remote backend: the job keeps running on the server, the
cockpit reconnects when it comes back. On a Termux backend: M.U.S.E.
checkpoints the job in SQLite, but the in-flight workers die.
Restart M.U.S.E. and run `muse orchestrator resume <job-id>` to
re-spawn any `running` cards.

## See also

- [`apps/android/README.md`](../../apps/android/README.md) — the
  cockpit's own README (build, modes, architecture).
- [`apps/android/docs/ARCHITECTURE.md`](../../apps/android/docs/ARCHITECTURE.md)
  — wire format and the "no embedded Python" decision.
- [`docs/hermes-local-orchestrator.md`](../hermes-local-orchestrator.md)
  — the older, simpler Android-only handoff flow (predates the
  orchestration system; still useful for the "just hand off to ChatGPT/Codex
  via clipboard" workflow).
- [private-local-mode.md](private-local-mode.md) — full offline
  configuration when even the model has to live on the device.
