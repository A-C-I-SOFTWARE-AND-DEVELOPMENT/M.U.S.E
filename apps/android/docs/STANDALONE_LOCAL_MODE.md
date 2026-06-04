# Standalone Local Mode (v1.5)

The Jarvis Prime Android app runs as a **standalone-local coding cockpit**: a
control plane you can use every day for coding work, that is local-first,
privacy-preserving, and never routes provider traffic through a central
company backend. There are no bundled API keys; the only secret the app holds
is a cockpit bearer token, stored in the Android Keystore.

## The four modes

| Mode | Backend | What works |
|---|---|---|
| **A — Mock / Demo** | none | Dashboard, **New Coding Task → Work Packet → Code Handoff**, model/guardrail/memory previews. Demo data is clearly labelled (`demo`). Useful the moment you install. |
| **B — Local device** | Termux Hermes / `localhost` cockpit on the phone | Real classification, packet building, memory inbox, model status, gated execute. |
| **C — Owner backend** | your LAN/VPS Hermes gateway | Same as B over the network: base URL + bearer token (Keystore). |
| **D — BYO cloud/provider** | your own keys, owner-configured | Opt-in only; no bundled keys; secrets in the secure store. Kept behind a future flag where not yet safe to enable. |

Mode is implicit: the app uses **Mock** when *Settings → Mock mode* is on,
**paired** (B/C) when a gateway token is set, and an **offline** path otherwise.

## The coding flow

1. **New Coding Task** (Home → "New coding task"). Describe the task in plain
   English; optionally give a repo path. "Preview risk" classifies it
   (risk class / worker / owner gates) via the backend `coding/audit` lane.
2. **Generate work packet** builds a bounded packet via `coding/plan`:
   mission, risk class, allowed / forbidden files, acceptance criteria,
   verification plan, rollback plan, owner-gated actions, suggested worker +
   model lane.
3. **Work Packet detail** gives two exits:
   - **Copy Claude Code prompt** — an offline-safe, packet-driven prompt with
     the invariant safety block, for a desktop Claude Code / Codex session.
   - **Send to backend** — a *gated* execute (`coding/execute`). Without the
     owner phrase the gateway **stages** the job and the app shows the owner
     gate; nothing risky runs unprompted. The phrase is verified server-side
     and never stored on the phone.
4. **Code Handoff Hub** lists every saved task grouped by state (queued
   offline / planned / blocked on owner / executing / handed off / done) so
   you can pick a queued task back up once a backend is online.

## Offline-first behaviour

- With **no backend reachable**, a task is saved and **queued offline**; you
  can still copy a prompt and sync later. Generate never dead-ends — it always
  lands on a saved task you can open.
- Coding tasks persist locally in `hermes_coding_tasks.json` (app-private
  storage, excluded from cloud backup). "Clear local data" removes them.

## What it deliberately does not do

- No provider API calls from the app process; no central proxy.
- No bundled keys; no silent exfiltration; no fabricated "ready" states.
- No bypass of owner gates, memory gates, or guardrails. Execute is always
  gated server-side; the app cannot authorize on your behalf.

See also: [`API_CONTRACT.md`](API_CONTRACT.md),
[`SECURITY_PRIVACY.md`](SECURITY_PRIVACY.md),
[`GEMMA_LOCAL_MODE.md`](GEMMA_LOCAL_MODE.md),
[`RELEASE_DOWNLOAD.md`](RELEASE_DOWNLOAD.md), and the user guide
[`docs/mobile/mobile-app-guide.md`](../../../docs/mobile/mobile-app-guide.md).
