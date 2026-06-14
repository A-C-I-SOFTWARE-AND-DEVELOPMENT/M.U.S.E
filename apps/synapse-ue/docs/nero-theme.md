# Nero Solar System — theme spec for SynapseObservatory

**Date:** 2026-06-14 · Binds to the gateway's `layout_algo == "solar-orbital"` mode (shipped
gateway‑side; see `docs/synapse/NERO_FLEET_STATIC_ANALYSIS.md`). Render‑only: the module holds
no policy and invents no data — every number arrives from `/v1/observatory/*`.

## Principle

The "Nero Solar System" is a **dressing variant** of the existing Neural Observatory galaxy,
not a new data path. `UObservatorySubsystem` already parses `layout_algo` and the per‑cluster
`pos`/`radius`/`heat`/`type_mix` from `FObsSnapshot` (`ObservatoryTypes.h`). When the gateway is
queried with `?layout=solar`, it returns `layout_algo: "solar-orbital"` and solar `pos` values.
The renderer switches dressing on that label — it never recomputes positions.

## Fetch

Request the solar arrangement by adding `layout=solar` to the snapshot fetch in
`SynapseNet`'s authorized GET (the only module that talks to the gateway). Everything else —
delegates, SSE stream, parsing — is unchanged.

## Visual mapping (all from real fields)

| Element | Driven by | Dressing when `layout_algo == "solar-orbital"` |
|---|---|---|
| **Nero Core** (the sun) | gateway liveness / `queue.depth` from the stream | Emissive corona sphere at the origin `(0,0,0)`. The gateway reserves the origin (no cluster is placed there). Pulse amplitude ∝ queue depth; dim when idle. |
| **Planets** (clusters) | `FObsCluster.pos` (server‑computed), `radius`, `type_mix`, `heat` | One body per cluster at its server `pos`; mesh scale from `radius`; material tint from dominant `type_mix`; emissive from `heat` (`heat==null` ⇒ neutral grey, "no measured activations"). |
| **Orbit rings** | derived from each planet's `pos` (its orbital radius/plane) | Thin ring per occupied orbit; purely presentational, drawn from the planet positions the server already sent. |
| **Ships** (packets) | SSE `job.stage` along the station graph `Job→Navigator→Worker→Gate→Ledger` | Niagara/ISM packets travel core→planet (dispatch) or planet→planet (handoff); a `gate.verdict` FAIL flares red and bounces back. Identical logic to the galaxy theme; only the path anchors differ. |
| **Brain Ladder** | `route.decision` + `metrics_rollup` share | Unchanged from the galaxy theme; sits beneath the system. |

## Honesty (binding, same as the galaxy theme)

- `graph.status == "unavailable"` or snapshot `503` ⇒ dormant dressing: a dim core, **zero**
  planets, **zero** ships. Never fabricate bodies.
- Solar positions are deterministic *placement* of real clusters, not telemetry. Heat, ship
  motion, ladder brightness all come only from measured events.

## Implementation notes

- No new wire types: the solar overlay reuses `FObsSnapshot`/`FObsCluster`; the only signal
  is the `layout_algo` string the subsystem already parses.
- The 2 s layout interpolation contract holds — solar positions are deterministic per
  `graph_version`, so bodies only re‑settle when the graph genuinely changes.
- This is Phase‑3 renderer work that binds to existing `UObservatorySubsystem` delegates
  (`observatory-module.md`); it adds dressing, not policy.
