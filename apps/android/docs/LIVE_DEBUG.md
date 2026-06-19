# Live debug — run the gateway on your PC and wire the app to it

This is the no-gaps path to exercise the **paired (networked) cockpit** end to
end on your own machine: start the real Hermes cockpit gateway, then point the
muse Android app at it. Everything stays on your PC (loopback) unless
you deliberately opt into the Wi-Fi path.

> The app needs the `INTERNET` permission to reach the gateway — even over
> loopback. Use a build from `main` (the debug APK below) which declares it.

## TL;DR

```bash
# from the repo root
pip install -e ".[all,dev]"        # once
scripts/dev/live-cockpit.sh        # starts the gateway, smoke-tests it, prints wiring
```

The script prints your pairing token and the exact endpoint to enter for each
setup (emulator / USB / Wi-Fi). `--lan` binds your LAN for a physical phone;
`--smoke` just tests an already-running gateway.

## 1. Start the gateway

```bash
hermes cockpit token        # prints the bearer token (saved in ~/.hermes/cockpit/)
hermes cockpit serve        # binds 127.0.0.1:8765, prints the URL + token
```

`hermes cockpit serve` runs the real, bearer-authenticated, **loopback-only**
cockpit API backed by the live Hermes/JARVIS subsystems (chat, runtime status,
jobs, approvals, memory, evidence, diagnostics, …). Add `--allow-external` only
for the Wi-Fi path below.

Confirm it's healthy before touching the app:

```bash
TOKEN=$(hermes cockpit token)
curl -s http://127.0.0.1:8765/v1/health                                    # {"ok":true,...}
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/v1/cockpit/runtime/status
curl -s -N -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"prompt":"hello","history":[]}' http://127.0.0.1:8765/v1/jarvis/chat   # NDJSON stream
```

A request without the token must return `401` — that's the auth gate working.

## 2. Get the debug APK

- **From CI:** download the `hermes-agent-debug-apk` artifact from the latest
  `Android build` run on `main`.
- **Local:** `cd apps/android && ./gradlew assembleDebug` →
  `app/build/outputs/apk/debug/app-debug.apk` (installs as `com.aci.hermes.debug`,
  side-by-side with any release build).

## 3. Wire the app to your PC

The app's default endpoint is `http://127.0.0.1:8765`, which on a device means
the device itself — so match your setup:

| Setup | Gateway command | Endpoint in the app |
| --- | --- | --- |
| **Emulator on this PC** (recommended — fully local) | `hermes cockpit serve` | `http://10.0.2.2:8765` |
| **USB phone** (secure, no LAN) | `hermes cockpit serve` + `adb reverse tcp:8765 tcp:8765` | `http://127.0.0.1:8765` |
| **Phone on same Wi-Fi** | `hermes cockpit serve --allow-external` ⚠️ exposes the agent on your LAN | `http://<your-PC-LAN-IP>:8765` |

`10.0.2.2` is the Android emulator's alias for the host loopback. `adb reverse`
tunnels the phone's `127.0.0.1:8765` to the PC, so neither of the first two
paths exposes anything on the network.

## 4. Pair in the app

**Settings → Connection** → set the **gateway endpoint** (from the table) and
paste the **bearer token**. The token is stored in `EncryptedSharedPreferences`.
Once it's set the app switches from the offline mock to the live gateway: the
gateway pill flips to **Online**, and Chat / Jobs / Approvals / Diagnostics hit
your PC.

## 5. Real chat replies need a local model

The chat **stream and agent turn work without a model**, but generated prose
degrades to the agent summary with a note like
`(model generation unavailable: Connection refused)` when no model is reachable.
For real replies, run one locally:

```bash
hermes models bootstrap     # free-first local model setup
# or run Ollama yourself: `ollama serve` then `ollama pull llama3.1`
```

See [`GEMMA_LOCAL_MODE.md`](GEMMA_LOCAL_MODE.md) for local model options.
Jobs, approvals, memory, evidence and diagnostics do not need a model.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| App says *"can't reach the local gateway"* | Wrong endpoint for your setup — see the table (`10.0.2.2` for emulator, `adb reverse` for USB). |
| `401` on every call | Token mismatch — re-copy from `hermes cockpit token` and re-paste in Settings → Connection. |
| Chat returns a short summary, not prose | No local model — run `hermes models bootstrap` / Ollama. |
| Wi-Fi phone can't connect | Gateway must run with `--allow-external`, and your firewall must allow port 8765. |
