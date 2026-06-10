# SynapseNet — module documentation (Prompt 0)

`SynapseNet` is the **only** module in the SYNAPSE UE 5.6 project that
talks to a MUSE gateway (TDD §2.2,
`docs/synapse/design/11-technical-design.md` in the M.U.S.E repo). It is a
pure wire-contract client over
`docs/contracts/cockpit-wire-contract.md` (96 routes, bearer auth, 6 open
routes) — nothing from `hermes_cli/jarvis_prime/`, GraphRAG, the
orchestrator, gates, or ledgers is ever ported into C++ (the coupling
rule, master plan §1).

## Architecture

```
SynapseUI → {SynapseObservatory, SynapseFoundryClient, SynapseAgents} → SynapseNet → SynapseCore
```

| Class | Type | Role |
|---|---|---|
| `UMuseGatewaySettings` | `UDeveloperSettings` (Config=Game) | `GatewayBaseUrl` (default `http://127.0.0.1:8787`), `TokenFilePath` (default `<Saved>/muse_token.txt`), token read-from-file helpers |
| `UMuseGatewayClient` | `UGameInstanceSubsystem` | Phase 0 handshake: `GET /v1/health` (open) and `GET /v1/cockpit/capabilities` (bearer). Delegates `OnGatewayHealth(bool, FString)` / `OnCapabilities(FString)` |
| `UMuseSseClient` | `UObject` (BlueprintType) | Streamed-request SSE consumer; `OnSseEvent(EventType, Data)`; reconnect with backoff; consumed by SynapseObservatory at Phase 3 |

Contract routes implemented so far (each cited at its call site, greppable):

- `GET /v1/health` — open; liveness probe. Response:
  `{ok, service, api_version, gateway_version, time}`.
- `GET /v1/cockpit/capabilities` — bearer; feature negotiation. Response:
  `{api_version, gateway_version, subsystems, available_workers,
  detected_clis, execute_allowed, owner_gate_required, generated_at}`.
  The client negotiates against this document — it never assumes.

## Threading rules (binding)

1. **No network on the game thread.** Requests go through `FHttpModule`;
   completion and progress callbacks arrive on HTTP worker threads.
2. **All delegate broadcasts happen on the game thread**, marshaled via
   `AsyncTask(ENamedThreads::GameThread, …)` with a `TWeakObjectPtr` guard
   so a dying subsystem/object never gets a stale callback.
3. SSE parsing state (`PendingBuffer`, `ParsedChars`, backoff) is
   game-thread-owned; worker threads only snapshot the body-so-far and
   hand it over.
4. Phase 1 upgrade (TDD §2.2): replace per-callback `AsyncTask` with a
   coalescing queue drained once per tick (≤ 1 broadcast batch/frame).

## Config & token handling (security rule)

- The bearer token is **read from a file at runtime**
  (`UMuseGatewaySettings::ReadBearerToken`, default
  `<ProjectSavedDir>/muse_token.txt`). It is never a UPROPERTY/config
  default, never compiled in, never serialized, **never logged** — log
  lines print `<redacted>` and the file *path*, never the value.
- `Saved/` is gitignored; the token filename is additionally ignored
  belt-and-braces.
- Phase 1 replaces the plain file with the DPAPI/Keystore-wrapped
  `Saved/Config/muse_pairing.bin` populated by the pairing flow
  (`POST /v1/cockpit/pair/start` → owner reads code →
  `POST /v1/cockpit/pair/confirm`, which returns the per-device token once).
- TLS-only for non-loopback gateways (TDD §8); plain HTTP is acceptable
  only for the localhost/RFC1918 paired case.

## SSE framing rules

- Frames are split on a blank line (`\n\n`); CRLF is normalized to LF
  before splitting.
- Within a frame: `event:` sets the event type (default `message`);
  multiple `data:` lines are joined with `\n` (one leading space after the
  colon is stripped, per the SSE spec); `:` lines are comments/keep-alives
  and are ignored.
- `id:` and `retry:` are parsed-and-ignored in Prompt 0. Phase 1 adds
  `Last-Event-ID` resume and honoring `retry:` hints + the `resync` event
  (10-observatory-spec.md §3.2).
- Requests carry `Accept: text/event-stream`, bearer auth, and **no total
  timeout** (a healthy stream is long-lived; dead links surface via the
  completion handler).

## Error & backoff policy

- HTTP request failure / disconnect while streaming ⇒ reconnect after the
  current backoff delay: **1s → 2s → 4s → … capped at 30s** (Prompt 0
  scope; the full TDD policy is cap 60s with ±20% jitter and reset after
  90s healthy — tracked for Phase 1). Backoff resets to 1s as soon as a
  frame parses successfully.
- `Stop()` (and `BeginDestroy`) cancels the in-flight request and any
  pending reconnect ticker; the completion handler checks owner intent
  (`bWantStream`) so cancellation never triggers a reconnect.
- `FetchCapabilities` on non-2xx (e.g. `401 {"error": "missing or invalid
  bearer token"}` when unpaired) broadcasts `OnGatewayHealth(false, body)`
  and logs a pairing hint — never the token.
- One-shot requests use a 15s timeout.

## Validation matrix (honest)

| Check | Where | Status |
|---|---|---|
| Stub gateway serves `/health` + `/v1/health` 200 with contract shape | this container, `tools/stub_gateway.py` | **PROVEN** (transcript in repo README/PR) |
| Capabilities 401 without bearer, 200 with bearer, contract field names | this container, curl | **PROVEN** |
| SSE heartbeat frames every 2s (`event:`/`id:`/`data:` framing, `retry:` hint) | this container, `curl -N` | **PROVEN** |
| `Build.bat SynapseEditor Win64 Development` compiles clean, warnings-as-errors | owner's Legion (UE 5.6 + VS2022) | **DEFERRED — OWNER-BLOCKER**: UE/UBT not installed in this container |
| PIE log shows live `/v1/health` + capabilities responses (test map) | owner's Legion, per `docs/testmap-setup.md` | **DEFERRED — OWNER-BLOCKER**: needs editor + pairing |
| `Automation RunTests Synapse.` (Net parser/backoff against local stub) | owner's Legion / future CI | **DEFERRED** — automation specs land with Phase 1 |
| Real-gateway handshake (pairing flow, per-device token) | owner's machine running the MUSE gateway | **DEFERRED — OWNER-BLOCKER: pairing needed** |
