# MUSE Mobile (native) — user guide

Operate MUSE from your Android phone, end to end. This guide
assumes no prior setup. By the end you will have the app installed,
paired to a backend, and you'll know how to chat, run jobs, approve
actions, use voice and the live avatar, and stop everything instantly.

> The app is a **cockpit**, not a self-contained MUSE. The phone arms
> switches and reads instruments; a M.U.S.E. **backend** does the thinking,
> runs the models, and executes work. See
> [`mobile-app-guide.md`](mobile-app-guide.md) for the flight-cockpit
> mental model and [`JARVIS_MOBILE_NATIVE_ARCHITECTURE.md`](JARVIS_MOBILE_NATIVE_ARCHITECTURE.md)
> for how the two halves talk.

---

## 1. Install the app

The native app lives in [`apps/android/`](../../apps/android/). It is a
Kotlin / Jetpack Compose app (package `com.aci.hermes`).

**Option A — build it yourself**

```bash
cd apps/android
./gradlew :app:assembleDebug
# APK lands in app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

See [`../../apps/android/docs/LOCAL_SDK_SETUP.md`](../../apps/android/docs/LOCAL_SDK_SETUP.md)
for the SDK / signing setup and
[`../../apps/android/docs/RELEASE_SIGNING.md`](../../apps/android/docs/RELEASE_SIGNING.md)
for a release build.

**Option B — sideload a prebuilt APK** from your release channel, then
open it. Android will ask you to allow installs from your source.

On first launch you land in **onboarding** (mock mode on, safety floor
applied) so you can explore before connecting anything real.

## 2. Start a backend

The app pairs with a loopback **cockpit API**. Run it wherever your
M.U.S.E. lives — a VPS, your home server, or Termux on this same phone:

```bash
muse cockpit serve            # binds 127.0.0.1:8765 by default
```

This is **loopback-only and bearer-authenticated** — it refuses to bind
a non-loopback host unless you pass `--allow-external` (don't, unless you
fully understand the exposure). Print the pairing token:

```bash
muse cockpit token            # prints the token to paste into the app
muse cockpit token --rotate   # rotate it (revokes the old one)
```

The token is generated once and stored owner-only (`0600`) under
`${HERMES_HOME}/cockpit/token`.

> Running the backend on the same phone? See the Termux guides under
> [`../termux/`](../termux/). The app's default endpoint
> (`http://127.0.0.1:8765`) already points at a local Termux gateway.

## 3. Connect the app to the backend

In **Settings → Connection**:

1. **Gateway endpoint** — the backend URL. Default is
   `http://127.0.0.1:8765` (local / Termux). For a remote backend use a
   secure tunnel — see [`../remote/secure-tunnel-options.md`](../remote/secure-tunnel-options.md).
2. **Pairing token** — paste the token from `muse cockpit token`.
3. The cockpit verifies with `GET /v1/health` and shows **Connected**.

Your token is stored **encrypted at rest** on the device (Android
Keystore-backed `EncryptedSharedPreferences`), not in plaintext. It is
the only secret the phone holds — your model/provider API keys never
leave the backend. See
[`JARVIS_CAPABILITY_AND_PERMISSION_GUIDE.md`](JARVIS_CAPABILITY_AND_PERMISSION_GUIDE.md)
and the architecture guide for details.

### Mock vs. real mode

| Mode | What it does | When to use |
|---|---|---|
| **Mock** (default on fresh install) | The app serves canned data — no backend needed. Chat, jobs, memory all return safe stub content. | Explore the UI, demo offline, develop without a backend. |
| **Real** | The app talks to the live cockpit. Chat streams the real MUSE; jobs, memory, approvals are real. | Actual use. Requires a paired, reachable backend. |

Toggle **Mock mode** in Settings. With mock mode **off** and a valid
endpoint + token, the app is live. An unpaired or unreachable backend
shows a typed **Unreachable** state — never silent fake data.

## 4. Start chatting

Open **Chat** (or the **Ask MUSE** bar on any screen) and type. The
reply streams token-by-token from the real MUSE turn on your backend.
Ask in plain English — "MUSE, companion mode, talk something through",
"strategy mode, help me reason about pricing", "prepare a build packet
for …". The full menu of phrased entry points is the **capability
catalog** (see the capability guide).

## 5. Jobs (orchestrated work)

Bigger goals become **jobs** — decomposed task graphs the backend runs.

- Dispatch from chat ("orchestrate: …") or the **Jobs** screen.
- Watch the task graph, phase status, and the decision ledger live.
- Cancel a running job from its detail screen.

Jobs are queued on the backend; the phone observes and steers. Read
[`../orchestration/getting-started.md`](../orchestration/getting-started.md)
for what a job actually is.

## 6. Approvals (the owner gate)

High-risk and irreversible actions **pause for you**. They appear in the
**Approvals** queue, tiered by risk (risky / serious / critical cards).

To authorize a gated action you reply with the **exact owner phrase**:

```
Yes, with authorization.
```

Nothing else ("yes", "go ahead", "approved") authorizes it. Gated
categories include spending money, posting publicly, OAuth/credential
changes, production deploys, force-push, package publish, and app-store
submission. This is enforced on the backend
(`hermes_cli/jarvis_prime/owner_auth.py`) and surfaced on the phone — the
app cannot bypass it. See
[`../jarvis_architecture/JARVIS_OWNER_GATES_AND_PERSONAL_AUTHORITY.md`](../jarvis_architecture/JARVIS_OWNER_GATES_AND_PERSONAL_AUTHORITY.md).

## 7. Memory

The **Memory** screen shows what MUSE remembers about you, with
provenance. You can add and delete entries. Memory writes are **redacted**
— secrets, tokens, and identifiers are stripped before anything is stored
(`MemoryRedactor`). Keep memory local-only with the **Privacy → local-only
memory** toggle (on by default). The Memory Tree's provenance and
contradiction rules are described in
[`../jarvis_architecture/JARVIS_MEMORY_TREE_AND_NATURAL_LANGUAGE_CODER_SPEC.md`](../jarvis_architecture/JARVIS_MEMORY_TREE_AND_NATURAL_LANGUAGE_CODER_SPEC.md).

## 8. Evidence / research

Ask MUSE to research a topic and it answers from a **cited evidence
store** (the Research Vault), never invented sources. It summarizes only
from stored citation text or excerpts you provide, and makes no network
calls of its own. See
[`../jarvis/JARVIS_EVIDENCE_RAG_GUIDE.md`](../jarvis/JARVIS_EVIDENCE_RAG_GUIDE.md).

## 9. Voice

Turn on **Voice** in Settings to talk to MUSE hands-free. On-device
STT/TTS drives a listen → think → speak loop. While the mic is live a
**persistent foreground-service notification and an in-app indicator**
are shown — MUSE can never listen silently. For the car, see
[`../voice/voice-first-user-guide.md`](../voice/voice-first-user-guide.md)
and [`../voice/driving-mode-safety.md`](../voice/driving-mode-safety.md).

## 10. The live avatar (the Den)

The **Live** screen is MUSE's animated body in its room (the *Den*) —
breathing, walking, reacting. You can adopt a persona, generate furniture,
and let the avatar float over other apps (an explicit overlay toggle). The
overlay and device-control surfaces run as clearly-typed foreground
services with their own indicators. See
[`../avatar/sentient-avatar-architecture.md`](../avatar/sentient-avatar-architecture.md).

## 11. Emergency stop

Every screen can reach the **Emergency Stop**. It has graduated levels:

| Level | Effect |
|---|---|
| **Soft pause** | New tasks won't start; inspection still works. |
| **Hard stop** | Also blocks send / delete / push / deploy actions. |
| **Lockdown** | Blocks every outbound action and mutation. |

Coming back **always** requires an explicit, audited **resume approval** —
there is no silent un-stop. Every transition and every blocked action is
written to the emergency-stop audit log. On the backend you can also run:

```bash
python -m hermes_cli.jarvis_prime stop --reason "..."
```

which clears pending owner gates and disables proactive ticks.

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| App shows **Unreachable** | Backend not running, wrong endpoint, or no token | Start `muse cockpit serve`; check endpoint; re-paste token from `muse cockpit token`. |
| **401 / "invalid bearer token"** | Token rotated or mistyped | Run `muse cockpit token`, paste the current value; or `--rotate` and re-pair. |
| Everything looks fake / canned | **Mock mode** is on | Settings → turn Mock mode off. |
| Chat replies are terse summaries, no prose | No local model reachable on the backend | Start your local model (e.g. Ollama) or configure a provider on the backend. |
| Voice button does nothing | Mic permission denied or Voice disabled | Grant mic permission; enable Voice in Settings. |
| Avatar overlay won't appear | "Draw over other apps" not granted | Grant `SYSTEM_ALERT_WINDOW` from the prompt; toggle overlay on. |
| Actions silently don't run | Emergency stop engaged | Check the stop banner; request + approve resume. |
| Token "lost" after update | One-time secure-storage migration | The app migrates the legacy plaintext token into encrypted storage automatically on launch; if it failed, just re-pair. |

More symptom→fix coverage:
[`../troubleshooting/muse-orchestration-troubleshooting.md`](../troubleshooting/muse-orchestration-troubleshooting.md)
and `muse doctor` on the backend.
