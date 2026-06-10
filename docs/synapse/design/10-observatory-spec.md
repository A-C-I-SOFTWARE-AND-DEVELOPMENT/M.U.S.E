# 10 — Neural Observatory Specification
### The cockpit visualization map + the additive `/v1/observatory/*` route family

**Project:** SYNAPSE — A M.U.S.E. Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

---

## 1. Purpose & scope

The Neural Observatory is the UE5 map (`SynapseObservatory` module) that renders MUSE's actual
mind: the GraphRAG graph as a flyable galaxy, live orchestrator jobs as light-packets, and the
three-tier brain ladder animating each turn's routing. It is the master plan §3 deliverable
(Phase 3, weeks 17–26).

**Coupling rule (binding):** this document *specifies* a new, strictly **additive, read-only**
gateway route family. No gateway code changes in this sprint. Implementation later adds the
routes gateway-side, re-runs `scripts/generate_cockpit_contract.py`, and commits the regenerated
`docs/contracts/cockpit-wire-contract.md`/`.json` in the same PR; the new surface is then pinned
by `tests/gateway/test_cockpit_contract_freeze.py` exactly like the existing 96 routes. The
existing contract is **not modified by hand** and not modified here.

---

## 2. The three visual systems

### 2.1 The Graph galaxy

GraphRAG's real graph (28.6k nodes / 51.6k edges per master plan Appendix A) rendered as a
navigable galaxy.

- **LOD strategy is mandatory (master plan §3.1):** the gateway pre-clusters into **~200
  super-nodes** (communities by type: code, docs, memory, ledger). UE renders super-nodes at
  default LOD; zooming/clicking a cluster requests its expansion **on demand**
  (`GET /v1/observatory/layout?cluster=`). UE never holds or solves the full 28k-node graph.
- **Layout is computed gateway-side** in Python (networkx/igraph force-directed, cached,
  recomputed on graph rebuild) and streamed as positions. UE renders; it does not run physics.
- **Data requirements:** per super-node — id, type-mix, member count, 3D position, radius, heat
  (§5), label; per expanded node — id, type, position-within-cluster, degree, heat, source ref;
  per edge (super and expanded) — endpoints, weight, heat. Activations arrive as SSE
  `node.activate` deltas (§3.4) and drive a pulse Niagara effect.

### 2.2 The Pipelines

Live orchestrator jobs flowing as Niagara light-packets along splines through the canonical
stations: `Job → Navigator → Worker → Gate → Ledger`.

- **Data requirements:** the station graph (static, from the snapshot), plus per-job SSE events
  (`job.stage`, `gate.verdict`) carrying job id, stage, task class, timestamps. Each packet is
  clickable → opens the real job record via the **existing** `GET /v1/cockpit/jobs/{id}` and
  `GET /v1/cockpit/jobs/{id}/ledger` routes (no new routes needed for click-through).
- Packet color = task class; speed = inverse of measured stage latency (so congestion is
  *visible* as slow packets queuing at a station); a gate FAIL flares red and the packet loops
  back along the retry spline.

### 2.3 The Brain Ladder

Three glowing strata — **local GGUF / hosted brain / paired gateway** — with each conversational
turn's routing decision animating the path it took.

- **Data requirements:** SSE `route.decision` events (turn id, chosen tier, model id, reason
  string, latency ms, token counts) sourced from the existing `_brain_hint` routing data
  (`gateway/cockpit/agent.py`); plus rolling per-tier aggregates from
  `GET /v1/observatory/metrics` for the strata's ambient brightness (brightness ∝ share of
  recent traffic).

---

## 3. The `/v1/observatory/*` route family (complete proposed spec)

Common semantics, all four routes:

- **Auth:** `bearer` (shared/per-device token, identical to the existing cockpit auth model).
  None are open; none are owner-gated — they are **read-only and strictly additive**. They
  mutate nothing.
- **Errors:** `401` missing/bad bearer; `400` malformed query param (body
  `{"error": "bad_request", "detail": "<param>: <why>"}`); `404` unknown cluster id;
  `503 {"error": "collector_unavailable"}` if the metrics collector hasn't started (UE shows
  the Observatory in "dormant" dressing, no fake data). All errors are JSON with an `error`
  string field, matching house style.
- **Versioning:** every response carries `"v": 1`. Additive fields only; breaking changes bump
  the contract version via the generator.

### 3.1 `GET /v1/observatory/snapshot`

One call to boot the map: cluster layout + station graph + ladder state + latest rollup.

Query params: none.

Response `200`:

```json
{
  "v": 1,
  "generated_at": "2026-06-10T18:00:00Z",
  "graph": {
    "graph_version": "g-2026-06-10-0312",          // changes when GraphRAG rebuilds
    "node_count": 28600, "edge_count": 51600,
    "clusters": [{
      "id": "c-017", "label": "gateway/cockpit", 
      "type_mix": {"code": 0.8, "docs": 0.2},       // fractions by member type
      "members": 412,
      "pos": [12.4, -3.1, 88.0],                    // gateway-computed layout, arbitrary units
      "radius": 4.2,
      "heat": 0.31                                   // §5 normalized heat ∈ [0,1]
    }],
    "cluster_edges": [{"a": "c-017", "b": "c-042", "weight": 96, "heat": 0.12}]
  },
  "stations": {
    "nodes": ["job", "navigator", "worker", "gate", "ledger"],
    "active_jobs": [{
      "job_id": "jb-91ac", "task_class": "code", "stage": "worker",
      "stage_entered_at": "2026-06-10T17:59:41Z", "queue_pos": null
    }],
    "queue_depth": 3
  },
  "ladder": {
    "tiers": [{
      "tier": "local",                               // enum: local | hosted | paired
      "model": "qwen2.5-3b-instruct-q4",
      "share_1h": 0.62,                              // fraction of routed turns, last hour
      "p50_latency_ms": 840, "p95_latency_ms": 2390
    }]
  },
  "metrics_rollup": { "window": "1h", "...": "same shape as §3.3 response" }
}
```

### 3.2 `GET /v1/observatory/stream` (SSE)

Live deltas. Standard SSE framing (`event:`/`data:` lines, `id:` = monotonic sequence,
`retry: 5000`), same transport pattern as the existing `GET /v1/cockpit/events/stream` and
`/v1/cockpit/jobs/stream`. Supports `Last-Event-ID` replay from a ring of the last 1,000 events;
older gaps signal `event: resync` telling the client to refetch the snapshot. Heartbeat comment
`: ping` every 15 s.

Event types and payload schemas (all payloads carry `"ts"` ISO-8601):

| Event | Payload |
|---|---|
| `job.stage` | `{"job_id": str, "task_class": str, "stage": "queued\|navigator\|worker\|gate\|ledger\|done\|failed", "queue_depth": int, "stage_latency_ms": int\|null, "ts": str}` |
| `gate.verdict` | `{"job_id": str, "gate": "planning\|build\|review\|test\|security\|release\|owner\|rollback", "verdict": "pass\|fail\|override", "attempt": int, "detail_ref": "/v1/cockpit/jobs/{id}/validation", "ts": str}` |
| `node.activate` | `{"cluster_id": str, "node_id": str\|null, "kind": "query\|write\|promote", "weight": float, "ts": str}` — GraphRAG touch events, batched ≤ 10/s with coalescing |
| `route.decision` | `{"turn_id": str, "tier": "local\|hosted\|paired", "model": str, "reason": str, "latency_ms": int, "tokens_in": int, "tokens_out": int, "ts": str}` |
| `resync` | `{"reason": "gap\|graph_rebuilt", "ts": str}` |

### 3.3 `GET /v1/observatory/metrics?window=`

Rollups for heat, ladder brightness, and the Recommendation Engine's baselines.

Query params: `window` ∈ `{15m, 1h, 24h, 7d}` (default `1h`); optional
`task_class` filter.

Response `200`:

```json
{
  "v": 1, "window": "1h", "from": "...", "to": "...",
  "stages": [{
    "stage": "worker", "task_class": "code",
    "count": 41, "p50_ms": 92000, "p95_ms": 311000,
    "queue_wait_p95_ms": 14000, "retries": 6
  }],
  "gates": [{
    "gate": "test", "task_class": "code",
    "passes": 35, "fails": 6, "overrides": 1, "fail_rate": 0.146
  }],
  "models": [{
    "tier": "local", "model": "qwen2.5-3b-instruct-q4",
    "calls": 412, "p95_latency_ms": 2390,
    "tokens_in": 181000, "tokens_out": 52000, "est_cost_usd": 0.0
  }],
  "cost_per_task_class": [{"task_class": "code", "usd": 0.41, "n": 41}],
  "heat": [{"key": "stage:worker:code", "score": 0.83,
             "evidence_ref": "/v1/cockpit/ledger?stage=worker&class=code"}]
}
```

### 3.4 `GET /v1/observatory/layout?cluster=`

On-demand cluster expansion for the galaxy LOD.

Query params: `cluster` (required, super-node id); optional `limit` (default 500 members,
server-capped at 2,000 — clusters above the cap return their top-degree members plus
`"truncated": true`).

Response `200`:

```json
{
  "v": 1, "cluster": "c-017", "graph_version": "g-2026-06-10-0312",
  "truncated": false,
  "nodes": [{"id": "n-...", "type": "code", "label": "handlers.py",
              "pos": [0.4, 1.1, -0.2],        // local space, relative to cluster center
              "degree": 14, "heat": 0.05,
              "source_ref": "gateway/cockpit/handlers.py"}],
  "edges": [{"a": "n-...", "b": "n-...", "weight": 3}]
}
```

`404 {"error": "unknown_cluster"}` if the id is stale (client refetches the snapshot —
`graph_version` mismatch is the tell).

---

## 4. Gateway-side metrics collector (`metrics.py`) — design

A new module in `gateway/cockpit/` (implemented in Phase 3, not now), **stdlib-only** per house
style, in-process with the gateway.

- **What it timestamps:** every job stage transition, every gate verdict (+ attempt number),
  queue depth at each enqueue/dequeue, model call latency + tier + model id, token spend
  (in/out, est. cost from the model policy table), and every retry. Hook points are thin
  `metrics.emit(kind, **fields)` calls at the orchestrator/ledger seams — emit never raises and
  never blocks (drop-on-full bounded queue, depth 10k).
- **Storage:** (a) an **append-only JSONL ring** at `~/.hermes/observatory/events-<date>.jsonl`,
  ring-pruned to 7 days / 512 MB, whichever first — this feeds the SSE stream and click-through
  evidence; (b) **SQLite rollups** (`~/.hermes/observatory/metrics.db`, WAL mode): per-minute
  aggregate rows folded into 15m/1h/24h/7d windows by a background thread on a 60 s tick —
  this serves `/metrics` and `/snapshot` in O(window rows), never by scanning JSONL.
- **Overhead budget: < 1% CPU** of the gateway process and < 8 MB RSS for the queue+rollup
  thread; enforcement = a self-metric (`collector.cpu_ms_per_min`) surfaced in `/metrics` and a
  perf test in the Phase 3 PR. If the bounded queue overflows, events drop and a
  `collector.dropped` counter increments — the collector degrades, never the gateway.
- The collector is the **single source** for all four routes; routes are pure reads over its
  stores plus the GraphRAG layout cache.

---

## 5. Bottleneck heat math (measured-only)

Heat is computed per key (`stage:<stage>:<class>`, `gate:<gate>:<class>`, `edge:<a>:<b>`) from
**real measurements only** over the selected window:

```
inputs (per key, per window):
  L  = p95 stage latency            → l = L / max(p95 across keys of same kind)
  Q  = p95 queue wait               → q = Q / max(...)
  F  = gate failure rate            → f = F            (already ∈ [0,1])
  R  = retries / attempts           → r = R clamped to [0,1]
  C  = cost per task in class       → c = C / max(...)

heat = clamp01( 0.30·l + 0.20·q + 0.25·f + 0.15·r + 0.10·c )
confidence gate: keys with n < 5 in window report heat = null (rendered cool-gray,
                 tooltip "insufficient data (n=X)") — never a guessed glow.
```

Weights are config (`observatory.heat_weights`), defaults above; the formula and current
weights are returned in `/metrics` responses so the UI can show its work. **Click-through:**
every heat entry carries `evidence_ref` — a filtered **existing** `GET /v1/cockpit/ledger`
query (and from there `GET /v1/cockpit/ledger/{job}/{index}` detail). Hot means "these specific
ledger entries are slow/failing," and the player-owner can read every one. No vibes, no
invented scores (master plan §3.3).

---

## 6. The Recommendation Engine (honest by construction)

Pipeline per master plan §3.4, gateway-side, surfaced in the Observatory as floating verdict
cards near the hot element they address:

1. **Baseline:** rolling measured baselines per task class (latency, success rate, gate-pass
   rate, cost) from the §4 SQLite rollups.
2. **Hypothesis:** rule-based generators (top-heat key → its known lever table) plus
   model-suggested candidates, all expressed as a bounded `PolicyDelta` (e.g. "route `code`
   tasks ≤ 300 LOC to local coder model"; "raise Review-gate strictness on `release` class").
3. **Validation:** offline **replay** of recent real tasks under the candidate policy —
   `batch_runner` is the harness — or shadow-routing a small live sample. Minimum n = 50
   replayed tasks before a card may state any number.
4. **Verdict card:** *"Route short code tasks to qwen-coder-local: median latency −38%
   (n=212 replayed tasks, 95% CI −31%…−44%), success rate unchanged (Δ +0.4pp, n.s.)."*
   Every number links to the replay batch record and the underlying ledger entries.
5. **Apply** is owner-gated (§7), with one-click rollback to the pre-apply policy snapshot.

**Hard rule:** the engine never states a percentage it did not measure. Below threshold the
card renders the explicit collecting state — *"insufficient evidence (n=7) — collecting"* —
with no projected numbers, no grayed-out fake stats. This rule is testable and will be tested
(a card with an unmeasured claim is a release-gate failure).

---

## 7. Owner-gated brain edits from the Observatory

The Observatory **extends, never bypasses,** the existing owner-phrase mechanism (10 existing
owner-gated routes, see the wire contract census). Edits map onto **existing** POST patterns:

| Observatory interaction | Existing route pattern it drives |
|---|---|
| Re-pin a model route / flip paid routing | `POST /v1/cockpit/model-routes/override` (owner-phrase) |
| Raise/lower autonomy | `POST /v1/cockpit/autonomy` (owner-phrase) |
| Apply a recommendation (policy delta) | `POST /v1/cockpit/approvals/{id}` over a staged proposal (owner-phrase) |
| Skill enable/disable | proposal → `POST /v1/cockpit/approvals/{id}` (owner-phrase) |
| Memory curation (approve/supersede) | `POST /v1/cockpit/memory/tree/{id}/decision`; promote via `POST /v1/cockpit/evidence/{id}/promote` (owner-phrase) |
| Rollback an applied edit | `POST /v1/cockpit/ledger/{job}/{index}/rollback` |

**Physical interaction grammar:** (1) **grab** a routing strand on the Brain Ladder (or a gate
dial, or a memory node) — the strand detaches and follows the cursor, valid targets glow;
(2) **re-wire** — drop it on the new model/tier/level; a diff card appears showing exactly
which POST will fire with which body; (3) **confirm phrase** — the owner types/speaks the
exact authorization phrase into the card (the same `owner_auth.AUTHORIZATION_PHRASE` contract;
the UE client never stores the phrase). Cancel at any step snaps the strand back. **Every edit
writes a ledger entry and a rollback point** before taking effect; the card's final state shows
the ledger ref. No edit path exists in the Observatory that does not terminate in one of the
table's routes.

---

## 8. UE LOD & performance budget

- **Nodes:** Instanced Static Meshes — one ISM component per node archetype (≈ 6 archetypes by
  type), so the default-LOD galaxy is ~200 super-node instances + ≤ 2,000 expanded-node
  instances across at most 3 simultaneously-expanded clusters (oldest auto-collapses).
- **Edges:** a single Niagara system fed a position buffer (no per-edge actors); pipeline
  packets are one Niagara system per station-graph spline set.
- **Budgets (Observatory map, default LOD, Legion/RTX 5070 reference):** graph rendering
  **≤ 2 ms game-thread**; ≤ 3 ms render-thread; ≤ 60 MB for graph buffers; SSE/JSON parse off
  game-thread (`SynapseNet` worker, see `11-technical-design.md` §2.2) with a coalesced ≤ 1
  game-thread marshal per frame. Layout interpolation (new snapshot positions) is a 2 s ease,
  not a per-frame solve. Min-spec tier: clusters cap at 1 expanded, edge density halved, packet
  pool 64 — still 30 fps per `11-technical-design.md` §5.
- Heat/activation visuals are material-parameter updates on ISM custom data — zero
  per-node tick.

---

## 9. Command Deck map (summary)

The fourth UE map is the classic cockpit — chat, jobs, approvals — built entirely over
**existing** routes; it needs nothing from the new family. Route groups it consumes:

- **Chat:** `POST /v1/jarvis/chat` (ndjson stream), `GET /v1/cockpit/sessions`.
- **Jobs:** `GET/POST /v1/cockpit/jobs`, `GET /v1/cockpit/jobs/stream` (SSE),
  `/v1/cockpit/jobs/{id}` + ledger/diff/files/validate/validation subroutes,
  `POST .../{id}/run|approve|publish` (owner-phrase), `GET /v1/cockpit/jobs/lanes`,
  `POST /v1/cockpit/orchestrate`.
- **Approvals & audit:** `GET /v1/cockpit/approvals`, `POST /v1/cockpit/approvals/{id}`
  (owner-phrase), `GET /v1/cockpit/audit`, `GET /v1/cockpit/audit/{id}/proof`,
  `GET /v1/cockpit/events`, `GET /v1/cockpit/events/stream` (SSE), `GET /v1/cockpit/ledger`.
- **Status & models:** `GET /v1/health`, `GET /v1/cockpit/capabilities`,
  `GET /v1/cockpit/runtime/status`, `GET /v1/cockpit/runtime/workers`,
  `GET /v1/cockpit/models`, `GET /v1/cockpit/model-routes`, `GET /v1/cockpit/diagnostics`,
  `POST /v1/cockpit/emergency-stop`.
- **Pairing:** `POST /v1/cockpit/pair/start`, `POST /v1/cockpit/pair/confirm` (open routes,
  first-run only).

Widgets are the shared CommonUI library (`SynapseUI`) — the same components skin the in-game
Neural Network screen (master plan §4.5: build once, ship twice).

---

## 10. Cross-references

- `09-foundry-spec.md` — the same measured-claims-only doctrine, applied player-side.
- `11-technical-design.md` — `SynapseNet` SSE consumer, `SynapseObservatory` module,
  performance tiers, contract-version pin in CI.
- `docs/contracts/cockpit-wire-contract.md` — the frozen 96-route surface this family joins.
- `scripts/generate_cockpit_contract.py` + `tests/gateway/test_cockpit_contract_freeze.py` —
  the only path by which these routes become real.
- Master plan §3 (all of it), Appendix A (graph scale, owner-gated route census).
