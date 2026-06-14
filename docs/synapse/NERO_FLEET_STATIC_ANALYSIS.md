# Nero‑Fleet Vision — Repository Static Analysis

**Date:** 2026-06-14 · **Owner:** Jeremiah Echerd · **Status:** analysis (informs the
Pixel‑Streaming pivot recorded in `docs/plans/2026-06-14-nero-fleet-streaming-pivot-addendum.md`)

This report grounds the "Nero‑Fleet" vision (Fleet hierarchy · UE5 spaceship cockpit ·
Nero Solar System telemetry) against what the repository **actually contains today**. The
headline finding: the vision is, in large part, **already built** under the name
**Project SYNAPSE** ("A M.U.S.E. Game"). The correct move is to reconcile onto it, not
greenfield a parallel stack.

## 1. Vision claim → repository reality

| Vision claim | Repo reality (file‑level, verified) | Verdict |
|---|---|---|
| `ue5-render` skill + Axiom panel "prepping for UE5" | `skills/creative/ue5-render/SKILL.md`; UE5 Remote‑Control automation `hermes_cli/jarvis_prime/research_fabric/ue5.py` (ping/discover/console/py/render; owner‑gated spawn `MUSE_UE5_ALLOW_SPAWN`; axiom‑chained); Axiom panel `gateway/cockpit/handlers.py:104` (`axiom_panel`) + route `/v1/cockpit/axiom` (`server.py:63`) | **REAL** — but it is *offscreen render automation*, not streaming |
| "Build a UE5 spaceship cockpit" | **Real UE5 project** `apps/synapse-ue/` (`Synapse.uproject`, UE 5.6; C++ modules `SynapseCore`, `SynapseNet`, `SynapseObservatory`; `ObservatoryTypes.h` 845 L, `ObservatorySubsystem.cpp` 761 L; gateway client `MuseGatewayClient.cpp`, SSE client `MuseSseClient.cpp`) | **REAL** native client — **no Pixel Streaming present** anywhere in it |
| "Build a Nero Solar System live telemetry view" | **Neural Observatory already ships:** browser renderer `gateway/cockpit/static/observatory.js` (1810 L, vendored three.js r180) **and** native UE map `SynapseObservatory`, both consuming `/v1/observatory/*` (`gateway/cockpit/handlers_observatory.py`) with gateway‑computed force‑directed 3D layout (`gateway/cockpit/observatory_layout_engine.py`) | **REAL** — "Nero" is a **re‑theme**, not a new build |
| "Ships travel between planetary nodes" | Observatory **Pipelines**: packets flow `Job→Navigator→Worker→Gate→Ledger` from SSE `job.stage`/`gate.verdict`; browser analogue `upsertPacket()` in `observatory.js` | **REAL** |
| "Android thin client as Pixel‑Streaming vessel" | `apps/android/` is a deliberate **REST thin client** (`HermesCockpitClient` over `HttpURLConnection`); **zero WebRTC/streaming**; explicit non‑goals (no provider keys, no auto‑approve) | **REAL but opposite intent** — would need a new receiver |
| "Fleet Admiral ↔ AOS Council / orchestration lanes" | Orchestrator primitives `Job`/`WorkerSpec`/`JobState`/`JobMode`/`WorkerRole` (`hermes_cli/orchestrator_models.py`); jarvis_prime mode layer; AOS registry `skills/aos-enterprise-council/registry/` | **REAL** — no `Fleet*` class exists yet (see `docs/jarvis_architecture/FLEET_HIERARCHY.md`) |

## 2. The architecture that already exists

- **Two servers, two auth models.** Dashboard SPA server `hermes_cli/web_server.py` (port
  9119, `X-Hermes-Session-Token`) serves the React app in `web/` — which currently has **no**
  observatory page and **cannot** reach the cockpit. Cockpit `gateway/cockpit/server.py`
  (port 8765, bearer) owns `/v1/cockpit/*` and `/v1/observatory/*` and serves the existing
  `observatory.js` renderer.
- **`/v1/observatory/*` family** (read‑only, additive, contract‑frozen): `snapshot`,
  `metrics`, `layout`, `stream` (SSE deltas `node.activate`, `job.stage`, `gate.verdict`,
  `route.decision`). Layout is computed **gateway‑side** and streamed as positions — "UE
  renders; it never runs physics" (`docs/synapse/design/10-observatory-spec.md` §2.1).
- **No‑mock invariant is already the house rule.** `observatory.js` header: *"When telemetry
  is off it says so — nothing on this page is invented."* `503 collector_unavailable` /
  `graph.status:"unavailable"` ⇒ dormant dressing; `heat==null` ⇒ neutral, never guessed.

## 3. The conflict the vision created (and the owner's resolution)

The owner's own design authority — `docs/plans/2026-06-10-project-synapse-master-plan.md` —
**locks** (Decision 2 + the "one law" Coupling Rule) that *UE5 is a **native C++ client** over
the frozen 96‑route wire contract*, with a **native scaled Android renderer** (Phase 7) and the
Kotlin thin client retained (Decision 5; tech‑design §242) — i.e. **explicitly not Pixel
Streaming**. The vision's "offload rendering to a rig, stream to Android" contradicts this.

**Owner decision (2026‑06‑14, after the conflict was surfaced):** **pivot to Pixel Streaming**
as the primary delivery model, and **apply the Nero theme to the native UE5 SynapseObservatory
map**. This overrides Decisions 2/5 + the Coupling Rule and is **owner‑gated + architecturally
significant** → it lands on a feature branch as a **draft PR**; merge to `main` waits for the
exact phrase `Yes, with authorization.` The pivot is documented in
`docs/plans/2026-06-14-nero-fleet-streaming-pivot-addendum.md`.

## 4. What was implemented in this pass (runnable + tested here)

The one slice buildable *and verifiable* in a GPU‑less container is the gateway‑side **"Nero
Solar System" layout mode** that both renderers (browser `observatory.js` and native
`SynapseObservatory`) consume unchanged:

- `gateway/cockpit/observatory_layout_engine.py` — new `solar_layout()` / `solar_layout_algo()`
  (`ALGO_SOLAR = "solar-orbital"`): Nero Core reserved at the origin; clusters orbit as
  planets, heavier (more‑member) clusters on inner orbits, packed onto tilted rings of growing
  capacity. Same determinism + `[-100,100]³` box contract as `super_layout`.
- `gateway/cockpit/handlers_observatory.py` — `GET /v1/observatory/snapshot?layout=solar`
  overlays solar positions onto the per‑request cluster copy (the cached force‑directed summary
  is never mutated); reports `layout_algo: "solar-orbital"`. Any other value keeps the default.
- `tests/gateway/test_observatory_layout.py` — 7 new tests (determinism, in‑box, off‑the‑core,
  mass→inner‑orbit, edge‑independence, edge cases, handler overlay + cache‑integrity). **Verified:
  `ruff` clean, `ty` clean, 24/24 pass.**

## 5. Remaining work (phased; see the plan + addendum)

- **UE Nero theme** (`apps/synapse-ue`, owner builds on rig): renderer switches to solar
  dressing when `layout_algo == "solar-orbital"`. Spec: `apps/synapse-ue/docs/nero-theme.md`.
- **Pixel Streaming pivot** (owner‑gated): `deploy/pixelstreaming/` + master‑plan addendum;
  the `.uproject`/`DefaultEngine.ini` enablement is documented as a reviewable patch (not
  blind‑applied, since UE builds cannot be validated in this environment).
- **Android WebRTC receiver** (own phase): opt‑in, feature‑flagged; does **not** replace the
  REST thin client.
- **Fleet hierarchy** (`docs/jarvis_architecture/FLEET_HIERARCHY.md`): both approaches with
  pros/cons; owner picks. Recommended: the additive overlay.
