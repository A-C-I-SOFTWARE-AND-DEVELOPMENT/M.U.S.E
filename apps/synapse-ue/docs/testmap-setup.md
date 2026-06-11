# Phase 0 test map — editor setup (owner's machine)

The Prompt 0 validation map is a **Blueprint level asset** and therefore is
built in-editor, in the standalone SYNAPSE repo — binary assets never land
in the monorepo staging tree (see `Content/.gitkeep`).

Prerequisite: the project compiles (`Build.bat SynapseEditor Win64
Development …`, see README) and a gateway — real or
`tools/stub_gateway.py` — is reachable at the configured
`GatewayBaseUrl` (default `http://127.0.0.1:8787`), with the bearer token
written to `<Project>/Saved/muse_token.txt`.

## The 6 steps

1. **Create the map.** File → New Level → *Basic*. Save as
   `/Game/Maps/L_GatewaySmoke`. Set it as the default map: Edit → Project
   Settings → Maps & Modes → *Editor Startup Map* and *Game Default Map* →
   `L_GatewaySmoke` (or edit `Config/DefaultEngine.ini` per its comment).

2. **Open the Level Blueprint.** Toolbar → Blueprints → *Open Level
   Blueprint*. All wiring below happens on the **Event BeginPlay** graph.

3. **Get the subsystem.** From BeginPlay, add node *Get
   MuseGatewayClient* (category `Game Instance Subsystems`). This is
   `UMuseGatewayClient` — it exists automatically; nothing to spawn.

4. **Bind the delegates.** From the subsystem node, add *Bind Event to On
   Gateway Health* and *Bind Event to On Capabilities*. Wire each to a
   custom event whose body is a **Print String** node:
   - Health event → print `Health ok=<bOk> body=<RawJson>` (Append node).
   - Capabilities event → print `Capabilities=<RawJson>`.
   Set *Duration* ≈ 30 and tick *Print to Log* on both Print String nodes.

5. **Fire the calls.** After both Bind nodes (sequence them), call
   **Check Health** then **Fetch Capabilities** on the subsystem.

6. **Play-in-Editor and verify.** Press Play, then check the Output Log
   (filter on `LogSynapseNet`). Success is proven by ALL of:

   ```
   LogSynapseNet: MuseGatewayClient ready. Gateway=http://127.0.0.1:8787 TokenFile=... Token=<redacted>
   LogSynapseNet: /v1/health -> HTTP 200 ok=true
   LogSynapseNet: /v1/cockpit/capabilities -> HTTP 200 (… bytes)
   ```

   plus the two on-screen Print String lines containing
   `"ok": true` / `"service": …` (health) and `"api_version"` +
   `"owner_gate_required": true` (capabilities). A
   `/v1/cockpit/capabilities -> HTTP 401` warning means the token file is
   missing or doesn't match — fix `Saved/muse_token.txt` and replay.

Optional SSE smoke: construct a `MuseSseClient` object (Construct Object
from Class), bind *On Sse Event* to a Print String, call *Start* with
`/v1/observatory/stream`, and watch the stub's scripted Observatory loop
print (~1 event/s: `job.stage`, `node.activate`, `route.decision`,
`gate.verdict`, a `heartbeat` each cycle, and a `resync` every 4th cycle).
For the typed-delegate version of this smoke (the `ObservatorySubsystem`
path), see `docs/observatory-module.md`.
