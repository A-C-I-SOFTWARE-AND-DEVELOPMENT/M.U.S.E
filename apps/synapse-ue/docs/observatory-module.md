# SynapseObservatory — module documentation

`SynapseObservatory` is the Neural Observatory map module (TDD §2.4,
`docs/synapse/design/10-observatory-spec.md` in the M.U.S.E repo). This
drop ships the **data plane only**: the typed client for the additive,
read-only `/v1/observatory/*` route family — USTRUCT wire types
(`ObservatoryTypes.h`) plus a `UGameInstanceSubsystem`
(`UObservatorySubsystem`) that fetches, parses, and broadcasts. The
galaxy ISM renderer, station-spline Niagara packets, Brain Ladder
strata, and the owner-edit grammar are Phase 3 work that binds to this
subsystem's delegates. The module holds **no policy logic** — every
number rendered arrives fully formed from the gateway.

> **Phase 3 render layer now staged:** the galaxy ISM renderer +
> sacred-geometry / 4D-polytope layouts live in the
> **`SynapseObservatoryRender`** module (binds these delegates;
> `AObservatoryGalaxyActor`, `UObservatoryValidationViz`,
> `UObservatoryFlowComponent`), with the closed-form math in
> `SynapseCore/MuseSacredGeometry`. See
> [`docs/sacred-geometry.md`](sacred-geometry.md). Source-only,
> OWNER-BLOCKED on compile like the rest of the scaffold.

```
SynapseUI → {SynapseObservatory, FoundryClient, Agents} → SynapseNet → SynapseCore
```

All gateway traffic still flows through `SynapseNet` (the only module
that talks to a MUSE gateway): fetches are built by
`UMuseGatewayClient::CreateAuthorizedGetRequest` (an additive public
wrapper over its existing private request factory — base URL, timeout,
and bearer token handling live in exactly one place; the token is read
fresh from the settings token file and is never stored or logged by this
module), and the stream rides `UMuseSseClient`.

## Routes implemented (greppable per TDD §2.2)

| Route | Method on `UObservatorySubsystem` | Result delegate |
|---|---|---|
| `GET /v1/observatory/snapshot` (spec §3.1) | `FetchSnapshot()` | `OnSnapshot(bOk, FObsSnapshot)` |
| `GET /v1/observatory/metrics?window=&task_class=` (spec §3.3) | `FetchMetrics(Window, TaskClass)` | `OnMetrics(bOk, FObsMetricsRollup)` |
| `GET /v1/observatory/layout?cluster=&limit=` (spec §3.4) | `FetchLayout(ClusterId, Limit)` | `OnLayout(bOk, FObsClusterLayout)` |
| `GET /v1/observatory/recommendations` (spec §6) | `FetchRecommendations()` | `OnRecommendations(bOk, FObsRecommendations)` |
| `GET /v1/observatory/stream` SSE (spec §3.2) | `StartStream()` / `StopStream()` / `IsStreaming()` | see event map below |

Field names in `ObservatoryTypes.h` mirror the actual gateway responses
(`gateway/cockpit/handlers_observatory.py` + `observatory_metrics.py`)
exactly — including `layout_status` / `layout_algo`, `clusters_total` /
`clusters_truncated`, `heat_weights` / `min_n`, and the documented
`{"status": "unavailable"}` graph shape (surfaced as
`bGraphAvailable == false` → render the dormant dressing, never fake
data). Parsing is tolerant of additive unknown fields (spec §3
versioning rule).

### Nullable/optional JSON → `bHas*` booleans

USTRUCT members cannot be `TOptional` (UHT rejects it), so every field
the gateway may send as `null` or omit carries an explicit flag:
cluster/node `heat` (`bHasHeat` — null below the n ≥ 5 confidence gate,
spec §5: render cool-gray, never a guessed glow), `pos` (`bHasPos` —
null until the layout engine has solved that graph version),
`task_class`, `queue_pos`, ladder `model`/`share_1h`/percentiles, stage
percentiles, `fail_rate`, heat `score`, card `delta`,
`median_delta_pct`, `ci95`. `bHas* == false` means "not measured /
not computed" — the honesty rules make that state renderable, not
papered over.

## Delegate / event map

**Fetch results** (broadcast once per call, game thread; `bOk` = HTTP
2xx **and** the body parsed as the v1 shape — failures carry a
default-initialized struct):

| Delegate | Payload |
|---|---|
| `OnSnapshot` | `FObsSnapshot` — graph clusters/edges, station graph + active jobs, ladder tiers, embedded `FObsMetricsRollup` |
| `OnMetrics` | `FObsMetricsRollup` — stages, gates, models, cost_per_task_class, heat (+ `heat_weights`, `min_n`: the formula shows its work) |
| `OnLayout` | `FObsClusterLayout` — one cluster's member expansion; a 404 (stale id after graph rebuild) arrives as `bOk=false` → refetch the snapshot (`graph_version` mismatch is the tell) |
| `OnRecommendations` | `FObsRecommendations` — verdict cards; a `collecting` card has `bHasDelta=false` and null validation numbers by construction (spec §6 hard rule) |

**Stream events** (one typed delegate per spec §3.2 event type, game
thread):

| SSE `event:` | Delegate | Payload struct | Drives |
|---|---|---|---|
| `job.stage` | `OnJobStage` | `FObsJobStage` | pipeline packet movement/speed |
| `gate.verdict` | `OnGateVerdict` | `FObsGateVerdict` | gate flare (fail = red + retry-spline loop) |
| `node.activate` | `OnNodeActivate` | `FObsNodeActivate` | galaxy pulse Niagara (≤ 10/s, coalesced gateway-side) |
| `route.decision` | `OnRouteDecision` | `FObsRouteDecision` | Brain Ladder turn animation |
| `resync` | `OnResyncRequired(Reason)` | reason ∈ `gap` \| `graph_rebuilt` | listeners call `FetchSnapshot()` and rebuild |
| *every frame* (incl. unknown additive types, heartbeats) | `OnStreamEvent` | `FObsStreamEvent` (type + verbatim payload JSON + ts) | raw tap — nothing is silently dropped |

## Threading model (TDD §2.2, spec §8)

- **No network on the game thread.** Fetches go through `FHttpModule`
  (via `SynapseNet`); completions arrive on HTTP worker threads.
- **Bulk JSON parse off the game thread.** Snapshot/metrics/layout/
  recommendations bodies are parsed into their USTRUCTs **on the HTTP
  worker thread**; only the finished struct crosses to the game thread
  via `AsyncTask(ENamedThreads::GameThread, …)` with a
  `TWeakObjectPtr` guard.
- **All delegate broadcasts happen on the game thread.** No exceptions.
- **Stream frames:** `UMuseSseClient` delivers frames already on the
  game thread (its Prompt 0 contract), so the per-event payload parse
  runs there. This is a stated, bounded deviation: stream payloads are
  one-line deltas and `node.activate` is coalesced to ≤ 10/s
  gateway-side. The Phase 1 SynapseNet upgrade (worker-side parse + a
  coalescing queue drained ≤ once per tick) removes it; this module
  needs no changes when that lands, since it binds the same delegate.

### Known gap (documented, not papered over): `Last-Event-ID` resume

The Prompt 0 `UMuseSseClient` parses-and-ignores `id:` and does not send
`Last-Event-ID` on reconnect (Phase 1 work, tracked in
`docs/synapsenet.md`). Consequence: after a transport drop + backoff
reconnect, events that occurred during the gap are **lost** rather than
replayed from the gateway's 1,000-event ring. Mitigations now: (a) the
gateway emits `resync` when it knows a client is behind — handled; (b)
renderers should treat any reconnect as suspect and refetch the snapshot
(cheap, one call, spec §3.1 is designed for exactly this). The fix
belongs in `UMuseSseClient`, not here — per the no-hacking rule this
module does not reimplement or monkey-patch the SSE transport.

## LOD budget notes (spec §8 — what this data plane guarantees)

The renderer consumes this module under the locked budget; the data
plane is shaped so the renderer *can* hit it:

- Default LOD = the snapshot's ~200 super-node clusters (gateway-capped,
  `clusters_truncated` tells you if more existed) + cluster edges. UE
  never receives, holds, or solves the full 28.6k-node graph.
- Expansion = `FetchLayout` per cluster, gateway default 500 / hard cap
  2,000 members (`bTruncated` ⇒ top-degree members only). Budget allows
  **≤ 3 simultaneously expanded clusters** (oldest auto-collapses;
  min-spec tier: 1) — the *renderer* enforces that; this subsystem
  deliberately stays stateless and does not cache expansions.
- Positions are **gateway-computed** (`pos`, plus `layout_status` /
  `layout_algo` saying which algorithm actually ran); UE interpolates
  (2 s ease), it never runs layout physics.
- Heat/activation visuals are material-parameter updates driven by
  `heat` floats and `node.activate` deltas — zero per-node tick; nodes
  are ISM instances (~6 archetypes by `type`), edges one Niagara
  position buffer.
- Game-thread cost of this module ≈ delegate broadcasts + small stream
  payload parses; bulk document parsing is off-thread (see above).
  Budgets: graph rendering ≤ 2 ms game-thread / ≤ 3 ms render-thread /
  ≤ 60 MB graph buffers on the Legion reference tier.

## Owner-machine bring-up (source is staged; compile is owner work)

**State plainly: this module is compile-ready staged source. UE 5.6 /
UnrealBuildTool are not installed in the authoring container, so it has
NOT been compiled — compiling is the first action on the owner's
machine, and no compile claim is made until that log exists.**

### 1. Compile (UBT, warnings-as-errors is on for all Synapse* modules)

```bat
"C:\Program Files\Epic Games\UE_5.6\Engine\Build\BatchFiles\Build.bat" SynapseEditor Win64 Development -Project=<path>\Synapse.uproject -WaitMutex
```

Iterate until clean. The module is registered in `Synapse.uproject` and
both `Source/*.Target.cs` files; UBT picks it up from
`Source/SynapseObservatory/SynapseObservatory.Build.cs`.

### 2. PIE against the stub gateway (offline)

1. `python tools\stub_gateway.py` (default `127.0.0.1:8787`; token
   `synapse-dev-token` or `STUB_TOKEN`). The stub now serves all five
   observatory routes with spec-shaped canned payloads — validated by
   curl in the authoring container (snapshot/metrics/layout/
   recommendations 200-with-bearer + 401-without, 400 bad window, 400
   missing cluster, 404 unknown cluster, and the scripted SSE loop of
   all five event types incl. `resync` every 4th cycle).
2. Write the token to `<Project>\Saved\muse_token.txt`.
3. In the `L_GatewaySmoke` level blueprint (`docs/testmap-setup.md`),
   from BeginPlay: *Get ObservatorySubsystem* (Game Instance
   Subsystems) → *Bind Event to On Snapshot* / *On Job Stage* / *On
   Gate Verdict* / *On Node Activate* / *On Route Decision* / *On
   Resync Required* to Print String custom events → call
   **Fetch Snapshot**, **Fetch Metrics**, **Fetch Layout** (Cluster Id
   `c-1f2e3d4c`), **Fetch Recommendations**, then **Start Stream**.
4. Press Play; filter the Output Log on `LogSynapseObservatory`.
   Success = `/v1/observatory/snapshot -> HTTP 200 ok=true
   (clusters=2 active_jobs=1 tiers=2)`, the metrics/layout/
   recommendations lines, then one typed event print per second, a
   heartbeat hitting only the raw `OnStreamEvent` tap, and a
   `resync … snapshot refetch required` line within ~24 s.
5. Wire `OnResyncRequired` → `FetchSnapshot` to close the refetch loop.

### 3. PIE against a live gateway

Point `GatewayBaseUrl` (Project Settings → MUSE Gateway) at the real
gateway, pair (or copy a valid bearer token into
`Saved\muse_token.txt`), and repeat step 2's binds. Notes:

- Until the GraphRAG cache is built gateway-side, the snapshot's graph
  section is the documented unavailable shape → `bGraphAvailable=false`
  (`POST /v1/cockpit/graph/build` populates it).
- Until the metrics collector has recorded events, lists are honestly
  empty and heat is null — the dormant dressing is the correct render.
- `GET /v1/observatory/recommendations` is being added gateway-side in
  a parallel task; against an older gateway it 404s →
  `OnRecommendations(bOk=false)`. The USTRUCT here matches the agreed
  card shape (`{v, generated_at, cards:[{id,title,state,delta,
  validation{method,n_baseline,n_candidate,median_delta_pct,ci95,
  metric},evidence_refs,created_at}]}`).

## Validation matrix (honest, per the no-evidence-no-claim rule)

| Check | Where | Status |
|---|---|---|
| Stub: all 4 new JSON routes serve spec-shaped bodies; bearer 401s; 400 bad window; 400 missing / 404 unknown cluster; truncation via `limit` | authoring container, curl | **PROVEN** (transcript in the delivery report) |
| Stub: SSE scripted loop emits all five §3.2 event types with `id:`/`event:`/`data:` framing; `resync` slot at every 4th cycle | authoring container, `curl -N` + direct `_stream_script` check | **PROVEN** |
| `python3 -m py_compile tools/stub_gateway.py` | authoring container | **PROVEN** |
| UBT compile (`SynapseEditor Win64 Development`, warnings-as-errors) | owner's Legion (UE 5.6 + VS2022) | **NOT RUN — OWNER-BLOCKED**: UE/UBT not installed in the container. Careful manual UHT/UBT review done against the scaffold conventions (`#pragma once`, `generated.h` last, `SYNAPSEOBSERVATORY_API` macros, `GENERATED_BODY`, dynamic-delegate signatures, no engine-source edits) — that is a review, **not** a compile |
| PIE delegate smoke vs stub, then vs live gateway | owner's machine | **DEFERRED — OWNER-BLOCKED** (needs the compile above) |
