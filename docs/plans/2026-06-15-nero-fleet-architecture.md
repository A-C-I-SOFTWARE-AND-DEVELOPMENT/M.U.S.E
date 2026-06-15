# Nero-Fleet Architecture — M.U.S.E Operating Layer Overhaul
**Owner:** Jeremiah Echerd · A-C-I Software & Development  
**Date:** 2026-06-15 · **Status:** INITIATED  
**Supersedes nothing** — additive to SYNAPSE master plan, REMAINING_WORK_PLAN, and jarvis-prime operating docs.

---

## 0. Executive summary

The Nero-Fleet vision separates **render compute** (UE5 Pixel Streaming on a local gaming rig) from **display** (Android cockpit + desktop terminals) and **truth** (Python gateway, GraphRAG, orchestrator, AXIOM chain). Nothing in this plan ports cognition to C++ or weakens verification gates. Visual layers consume the same measured telemetry the Observatory already specifies — they never invent state.

Three objectives, one coupling law:

> **The UI reflects actual system states, not mocked data.** Every celestial body, ship transit, and chain-status chip binds to a gateway route, ledger entry, or AXIOM event — or renders dormant with an honest `unavailable` reason.

---

## 1. What already exists (foundation audit)

| Vision element | Repo anchor | Maturity |
|---|---|---|
| UE5 automation surface | `hermes_cli/jarvis_prime/research_fabric/ue5.py`, `skills/creative/ue5-render/SKILL.md` | Remote Control + owner-gated offscreen render; Phase 3 exit in `docs/REMAINING_WORK_PLAN.md` |
| AXIOM verification kernel | `axiom/` (66 invariant tests), `hermes_cli/jarvis_prime/axiom_bridge.py` | Chain live; Phase 4 Axiom panel pending on Android |
| Neural Observatory (galaxy view) | `gateway/cockpit/handlers_observatory.py`, `observatory_metrics.py`, `docs/synapse/design/10-observatory-spec.md` | Routes + collector shipped; SSE stream kinds: `job.stage`, `gate.verdict`, `node.activate`, `route.decision` |
| Android thin client | `apps/android/` — WebView Observatory host at `/cockpit/observatory.html` | Paired cockpit; bearer auth; no provider keys on device |
| UE5 SYNAPSE client | `apps/synapse-ue/` — `SynapseObservatory` module consumes `/v1/observatory/*` | Stub gateway + C++ parsers; separate repo policy per master plan |
| Agent routing / modes | `hermes_cli/jarvis_prime/`, six modes, AOS council skill pack | Runtime shipped; hierarchy documented in `docs/jarvis-prime-operating-system.md` |
| Orchestration primitives | Job → Worker → Gate → Ledger in `hermes_cli/job_controller.py` | `job.stage` / `gate.verdict` wiring to observatory **pending** (documented seam in `observatory_metrics.py` §33–52) |
| GraphRAG cognition plane | `hermes_cli/jarvis_prime/graphrag/` | ~33k nodes; `node.activate` wired when `MUSE_OBSERVATORY=1` |

**Gap this plan closes:** naval fleet taxonomy as a **telemetry overlay** (not a rewrite of orchestrator models), Pixel Streaming deployment path for the spaceship cockpit, and the **Nero Solar System** as a second Observatory skin over the same wire contract.

---

## 2. Architecture — three layers

```
┌─────────────────────────────────────────────────────────────────┐
│  DISPLAY LAYER (thin clients)                                   │
│  Android cockpit · Desktop TUI/dashboard · Browser terminals    │
│  ← WebRTC Pixel Stream OR WebView/SSE fallback                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ bearer + SSE + Pixel Stream signaling
┌────────────────────────────▼────────────────────────────────────┐
│  TELEMETRY LAYER (Python gateway — source of truth)             │
│  /v1/observatory/* · Fleet Admiralty registry · AXIOM chain     │
│  GraphRAG · kanban/orchestrator ledgers · flywheel              │
└────────────────────────────┬────────────────────────────────────┘
                             │ Remote Control API (owner-gated spawn)
┌────────────────────────────▼────────────────────────────────────┐
│  RENDER LAYER (local gaming rig — ASUS ROG / Skytech / Legion)  │
│  UE5.6 + Pixel Streaming plugin · SynapseObservatory map        │
│  Spaceship cockpit shell ("Axiom Panel") · Nero Solar System    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 Reconciliation with SYNAPSE master plan

The master plan (`docs/plans/2026-06-10-project-synapse-master-plan.md`) locks **one UE5 app** with Python as brain. Nero-Fleet does not contradict that:

- **PC flagship:** native UE5 app *or* Pixel Streaming host — same `SynapseNet` gateway client, same contract.
- **Android:** always a **receiver** (Pixel Streaming player or scaled WebView fallback), never a local UE5 renderer.
- **New route families** remain additive (`/v1/fleet/*` optional; prefer extending `/v1/observatory/snapshot` with a `skin: "galaxy" | "nero_solar"` field before inventing parallel APIs).

---

## 3. Objective 1 — Fleet hierarchy (telemetry overlay)

### 3.1 Taxonomy → code mapping

| Naval role | Runtime entity | Python module | Reports to |
|---|---|---|---|
| **Admiralty Board** | M.U.S.E gateway + Memory Tree | `hermes_cli/jarvis_prime/fleet/registry.py` → `AdmiraltyNode` | — (root) |
| **Flagship** | Jarvis-Prime (modes: Operator, Strategy, Builder) | `FlagshipNode` | Admiralty |
| **Tactical Cruiser** | Hermes execution shell (CLI, tools, gateway agent loop) | `TacticalVesselNode` | Flagship |
| **Intelligence Frigate** | AOS Enterprise Council | `IntelligenceFleetNode` | Flagship |
| **Fleet ships** | Orchestrator workers / kanban assignees | `FleetShip` instances | parent fleet node |

Implementation lives in `hermes_cli/jarvis_prime/fleet/` — **no changes** to `orchestrator_models.Job` schema. Workers gain a read-only `fleet_role` annotation at dispatch time.

### 3.2 Telemetry contract

Each `FleetNode` exposes:

```json
{
  "id": "flagship",
  "kind": "flagship",
  "status": "active|idle|blocked|owner_gated",
  "active_jobs": 2,
  "last_event_ts": "2026-06-15T…",
  "chain_valid": true,
  "children": ["tactical", "intelligence"]
}
```

Surfaced via:

- `GET /v1/observatory/snapshot` — add optional `"fleet": { … }` block (additive field, contract generator regen).
- CLI: `python -m hermes_cli.jarvis_prime.fleet status`

### 3.3 Wiring seams (ordered)

1. **Done (this drop):** `fleet/nodes.py`, `fleet/registry.py`, `fleet/solar_map.py`, unit tests.
2. **Phase 1b:** Hook `job_controller` stage transitions → `observatory_metrics.record_job_stage` (already specified, not wired).
3. **Phase 1c:** Hook `gates.py` verdicts → `record_gate_verdict`.
4. **Phase 1d:** AOS council invocations → `IntelligenceFleetNode.record_audit(...)`.

---

## 4. Objective 2 — UE5 Pixel Streaming cockpit

### 4.1 Why Pixel Streaming

Native UE5 on Android is out of scope (master plan §9: scaled tier later). Pixel Streaming keeps Lumen/Nanite on the Legion/ROG host while Android remains a thin WebRTC client — matching the repo's "no provider keys on phone" posture.

### 4.2 Host pipeline (Windows — primary dev path)

| Step | Action | Owner gate |
|---|---|---|
| 1 | Install UE5.6 + **Pixel Streaming** plugin on render host | — |
| 2 | Build `SynapseObservatory` map with cockpit sub-level (`AxiomPanel`) | — |
| 3 | Launch with `-PixelStreamingURL=ws://HOST:8888` | `MUSE_UE5_ALLOW_SPAWN=1` |
| 4 | Run Cirrus/signaling server (bundled with PS plugin) | — |
| 5 | Android: WebView or native WebRTC player → signaling URL | bearer for API, separate from PS |

Draft scripts: `scripts/ue5/pixel-stream-host.ps1`, `scripts/ue5/pixel-stream-check.ps1`.

### 4.3 Android integration path

**Option A (fast):** Full-screen WebView to Pixel Streaming player URL (same pattern as `ObservatoryScreen.kt`).

**Option B (production):** Embed Epic's Pixel Streaming WebRTC player in a Compose `AndroidView` with hardware decode.

Fallback: existing `/cockpit/observatory.html` 2D/SSE view when PS host unreachable — `ObservatoryDormant` pattern already exists.

### 4.4 Axiom Panel (Phase 4 REMAINING_WORK_PLAN)

The spaceship cockpit embeds the Axiom panel as a diegetic HUD:

- `chain_valid` chip ← `GET /v1/cockpit/axiom/status` (new route, reads bridge only)
- Event tail ← `axiom_bridge tail`
- Pending improvements ← `flywheel pending`

No mock green checks — chip shows ✘ when chain breaks or bridge inert.

---

## 5. Objective 3 — Nero Solar System live sync

### 5.1 Celestial binding (measured only)

| Body | Represents | Data source |
|---|---|---|
| **Sun (Nero Core)** | MUSE gateway + Memory Tree root | Gateway health, memory tree node count, `chain_valid` |
| **Inner planets** | Active agent modes / orchestrator lanes | `fleet/registry` + kanban board depth |
| **Asteroid belt** | FTS5 session clusters | Session DB stats via cockpit route |
| **Outer planets** | AOS council audits / GraphRAG communities | `observatory/snapshot` clusters by type |
| **Comets / ships** | In-flight job packets | SSE `job.stage` (+ future `fleet.transit` overlay) |
| **Orbit speed** | Inverse measured stage latency | `stage_latency_ms` on events — never guessed |

Implementation: `hermes_cli/jarvis_prime/fleet/solar_map.py` maps snapshot + stream events → `{ bodies[], transits[] }`. UE5 reads the same JSON whether rendered locally or streamed.

### 5.2 Spatial routing algorithm

Gateway-side (Python, cached):

1. Force-directed layout for planet positions (seed = graph version hash — same as Observatory layout engine).
2. Great-circle splines for ship transits between source/dest planet ids.
3. Transit duration = measured `stage_latency_ms`; queue congestion = packet queue depth at station.

UE renders; UE does not compute layouts (master plan §3.1 LOD rule applies verbatim).

### 5.3 WebSocket vs SSE

The wire contract standardizes on **SSE** for `/v1/observatory/stream` (already implemented). Pixel Streaming carries video + input; telemetry rides SSE in parallel on the gateway — do not tunnel telemetry through WebRTC data channels (debuggability + contract freeze).

---

## 6. Phased execution & exit gates

| Phase | Weeks | Deliverable | Exit gate |
|---|---|---|---|
| **NF-0** | 1 | Fleet module + plan + tests | `pytest tests/jarvis_prime/test_fleet*.py` green; `fleet status` prints four nodes |
| **NF-1** | 2–3 | Wire orchestrator → observatory seams | Live `job.stage` on SSE when `MUSE_OBSERVATORY=1`; replay from JSONL |
| **NF-2** | 3–5 | `/v1/observatory/snapshot.fleet` + `solar_map` | Android/WebView renders JSON; dormant when collector off |
| **NF-3** | 4–8 | Pixel Streaming host scripts + UE map shell | 60fps stream to desktop browser; latency < 100ms LAN |
| **NF-4** | 6–10 | Android PS receiver + Axiom HUD | Owner sees chain status in cockpit; `chain_valid` matches bridge audit |
| **NF-5** | 10–16 | Full Nero Solar System in UE | Ship transits match live jobs; click → real job ledger |

Every phase exit requires `python -m hermes_cli.jarvis_prime.axiom_bridge audit` → `chain_valid: true` (or explicit bridge-inert note for CI).

---

## 7. Enhanced orchestration prompt (copy-paste)

Use with `/orchestrate` or Claude Code at repo root:

```
Goal: Nero-Fleet UI/UX overhaul — M.U.S.E operating layer.

Objectives:
1. Fleet hierarchy — implement telemetry overlay in hermes_cli/jarvis_prime/fleet/;
   map Jarvis-Prime→Flagship, Hermes→TacticalVessel, AOS→IntelligenceFleet;
   all nodes report to Admiralty registry; no orchestrator schema breaks.
2. UE5 Pixel Streaming — draft scripts/ue5/pixel-stream-*.ps1; Android receiver path;
   Axiom Panel as diegetic HUD (chain_valid, flywheel pending).
3. Nero Solar System — solar_map.py binds GraphRAG + jobs to celestial bodies;
   SSE job.stage drives ship transits; layout gateway-side; UE renders only.

Constraints:
- Verification gates and tamper-evident ledgers unchanged.
- UI shows measured state or honest unavailable — no mock telemetry.
- Owner gates: UE5 spawn, brain edits, recommendations apply — exact phrase only.
- Follow docs/plans/2026-06-15-nero-fleet-architecture.md phase order.

Start: NF-0 — read fleet module, run tests, wire job_controller seam NF-1.
```

---

## 8. Related documents

- `docs/plans/2026-06-10-project-synapse-master-plan.md` — SYNAPSE + Observatory canonical spec
- `docs/synapse/design/10-observatory-spec.md` — route family shapes
- `docs/REMAINING_WORK_PLAN.md` — Phases 3–4 (UE5 smoke, Axiom panel)
- `FABLE5_GOD_PROMPT.md` — continuous build loop
- `docs/contracts/cockpit-wire-contract.md` — pinned API surface
