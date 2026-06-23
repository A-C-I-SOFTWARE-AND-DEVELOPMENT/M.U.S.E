# 11 — Technical Design Document
### The SYNAPSE UE 5.6 application — modules, budgets, platforms, pipeline

**Project:** SYNAPSE — A muse Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

---

## 1. Architecture overview

```
┌────────────────────────── SYNAPSE (UE 5.6, C++/BP) ──────────────────────────┐
│  Maps: Game · Neural Observatory · Avatar & Den · Command Deck               │
│                                                                              │
│  SynapseUI (CommonUI)                                                        │
│  SynapseObservatory   SynapseFoundryClient   SynapseAgents (GAS)             │
│  SynapseNet (HTTP/SSE client)            SynapseCore (save/settings/consent) │
└──────┬──────────────────────┬───────────────────────────────┬───────────────┘
       │ Tier 1 (always)      │ Tier 2 (optional)             │ Tier 3 (optional)
       ▼                      ▼                               ▼
  Local GGUF brain       Hosted Brain service            Paired muse gateway
  (Fab runtime-LLM       (Foundry, image-gen,            (HTTP/SSE per frozen
  plugin, in-process,    heavy reasoning;                cockpit-wire-contract.md,
  ~3–4B Q4 ≈2.5GB)       capped free tier)               96 routes + additive
                                                          /v1/observatory|game|
                                                          foundry families)
```

- The game is **fully complete offline on tier 1** (master plan Decision 4, §4.8). Tiers 2–3
  only ever *add* (Foundry, Observatory live data, real-muse bridge).
- **Coupling rule:** nothing from `hermes_cli/jarvis_prime/`, GraphRAG, the orchestrator,
  gates, or ledgers is ported to C++. The UE app is a wire-contract client, period. New
  capabilities are additive route families regenerated via
  `scripts/generate_cockpit_contract.py` and frozen by
  `tests/gateway/test_cockpit_contract_freeze.py` (see `10-observatory-spec.md` §3).
- All design-doc siblings: `09-foundry-spec.md` (Foundry), `10-observatory-spec.md`
  (Observatory + routes), `13-audio-design.md` (audio), `01…03` (game/negotiation/combat).

---

## 2. Module-by-module specification

Six primary modules (master plan §5). Dependency rule: arrows point downward only —
`SynapseUI → {Observatory, FoundryClient, Agents} → Net → Core`. No upward includes;
cross-talk via delegates and GameplayTags. All our modules compile with warnings-as-errors.

### 2.1 SynapseCore (Runtime, no deps beyond Engine)

- **Save system** (§4 below): `USynapseSaveSubsystem` (UGameInstanceSubsystem).
- **Settings:** `USynapseSettings` (config-backed UDeveloperSettings + a runtime
  `USynapseUserSettings` SaveGame for player options incl. accessibility per
  `13-audio-design.md` §8).
- **Telemetry consent:** `USynapseConsentSubsystem` — the single authority for the two flags
  (`TelemetryConsent`, `FoundryEnabled`, per `09-foundry-spec.md` §2.1). **Every** network
  egress path queries this subsystem; consent-off short-circuits before any payload is built.
  Consent state is in the settings save, versioned, and logged (locally) on change.
- Project-wide types: `FSynapseVersion`, currency/resource types (Cycles, Synapse Thread,
  Checksum Shards), zone/act enums, the 8-domain enum.

### 2.2 SynapseNet (Runtime, deps: Core, HTTP, Json)

- **`UmuseGatewayClient` : UGameInstanceSubsystem.** The only code in the project that talks
  to a gateway.
  - **Auth:** bearer token loaded from a local **encrypted config**
    (`FPlatformMisc`-keyed AES via the platform keystore wrapper, §8; file
    `Saved/Config/muse_pairing.bin`). Tokens are acquired once via the open pairing routes
    (`POST /v1/cockpit/pair/start` → user reads code → `POST /v1/cockpit/pair/confirm`),
    never typed into code, never logged.
  - **Handshake:** on pairing (and each session start when paired): `GET /v1/health` (open) →
    `GET /v1/cockpit/capabilities` (bearer). The capabilities response gates feature flags
    (Observatory live mode, Foundry, voice) — the client negotiates, never assumes.
  - **SSE consumer:** streamed `FHttpRequest` with incremental body parsing
    (`event:`/`data:`/`id:` framing, `Last-Event-ID` resume); **reconnect with exponential
    backoff** 1s → 2s → 4s → … cap 60s, ±20% jitter, reset on 90s healthy; honors
    `retry:` hints and the `resync` event (`10-observatory-spec.md` §3.2).
  - **Typed delegate events:** one dynamic multicast delegate per event family —
    `OnJobStage`, `OnGateVerdict`, `OnNodeActivate`, `OnRouteDecision`, `OnChatToken`,
    `OnConnectionStateChanged` — payloads as USTRUCTs (`FObsJobStage`, …) so Blueprint binds
    directly.
  - **Threading:** all network and JSON parse **off the game thread** (FHttpModule completes
    on worker threads; our parser runs there too); marshaled to game thread via a coalescing
    queue drained once per tick (≤ 1 broadcast batch/frame).
- Request layer: thin typed wrappers per route group (`Jobs()`, `Approvals()`,
  `Observatory()`, …) returning `TFuture`/delegate pairs; every wrapper cites the contract
  route it implements in a comment — greppable against the contract version pin (§7).

### 2.3 SynapseAgents (Runtime, deps: Core, GameplayAbilities, GameplayTags, GameplayTasks)

- **`ASynapseAgentCharacter`** (base for all 24 roster agents + Foundry rares + the muse):
  owns the `UAbilitySystemComponent` (`InitAbilityActorInfo` on Possess/spawn), the
  `USynapseAttributeSet`, a `UAgentPersonalityComponent` (the bounded-axes card consumed by
  parley/banter/combat-AI), and the modular-part assembly component (mesh merge from the part
  bank — also used by Foundry recipes, `09-foundry-spec.md` §4.5).
- **`USynapseAttributeSet`:** the attribute schema is owned by `03-combat-gas-design.md`
  (vitality/resilience/throughput/latency/bandwidth family, Integrity as the party meter);
  this module implements it with standard `ATTRIBUTE_ACCESSORS`, clamping in
  `PreAttributeChange`, and meta-attributes for damage routing.
- **ASC wiring:** abilities granted from `UAgentDefinition` data assets (the vetted ability
  library registry — the same allowlist the Foundry validates against); RTwP Command Mode
  queues abilities via the ASC's ability queue + a custom `USynapseCommandQueueComponent`;
  pipelines (cross-agent combos) are GameplayEffect-applied tags consumed by trigger abilities.
- **GameplayTag registry ownership:** this module owns `Tags/SynapseTags.ini` — the single
  source for `Synapse.Domain.*` (8), `Synapse.Ability.*`, `Synapse.State.*`,
  `Synapse.Pipeline.*`, `Synapse.Parley.*`. Other modules request tags; they do not declare
  them. CI greps for native tag declarations outside this module and fails on hits.
- No replication anywhere — pure single-player (Decision 8); ASC runs `Minimal` replication
  mode and all prediction code paths are off.

### 2.4 SynapseObservatory (Runtime, deps: Core, Net, Niagara, UI)

Implements `10-observatory-spec.md` §2/§8: galaxy ISM renderer + cluster expansion manager,
station-spline Niagara packets, Brain Ladder strata, heat materials, and the owner-edit
interaction grammar (grab/re-wire/confirm) driving `SynapseNet` POSTs. Holds **no** policy
logic — verdict-card content arrives fully formed from the gateway.

### 2.5 SynapseFoundryClient (Runtime, deps: Core, Net, Agents)

Implements the client half of `09-foundry-spec.md`: consent-gated telemetry emission (T1–T5
event structs, fire-and-forget, built only if `USynapseConsentSubsystem` allows), delivery
sync (poll on session start when online), rare-encounter spawn + verdict-card UI feed, and
part-recipe assembly via `SynapseAgents`. Absent/disabled, it compiles out cleanly behind
`SYNAPSE_WITH_FOUNDRY=1`.

### 2.6 SynapseUI (Runtime, deps: Core, CommonUI, CommonInput)

One CommonUI widget library shared by the game's Neural Network screen and the Observatory
(master plan §4.5 "build once, ship twice"): node/edge cards, verdict cards, approval cards,
ledger timelines, the parley wheel, HUD. Input-agnostic (CommonInput handles pad/KBM/touch —
the Android tier reuses everything). Style assets in one `CommonUI` style chain; no per-widget
hardcoded colors (accessibility re-theming, `13-audio-design.md` §8 visual counterpart).

---

## 3. The local-LLM bridge (tier 1)

- **Buy, don't build (Decision/master plan §5):** a Fab runtime-LLM plugin (Runtime Local LLM
  or GenAI Llama class — llama.cpp-backed, GGUF, streaming, Win/Mac/Linux/Android). We wrap it
  behind our own interface so the vendor is swappable:

```cpp
class ILocalBrain {
public:
    virtual FBrainHandle StartCompletion(const FBrainRequest& Req,        // prompt, max_tokens,
                                          FOnBrainToken OnToken,           // stop seqs, temp
                                          FOnBrainDone OnDone) = 0;        // verdict parse hook
    virtual void Cancel(FBrainHandle) = 0;
    virtual FBrainModelInfo GetModelInfo() const = 0;                      // id, ctx, quant, VRAM
    virtual EBrainBackend GetBackend() const = 0;                          // CUDA | Vulkan | CPU
    virtual bool IsReady() const = 0;
};
```

  Only `SynapseNet`'s prompt-assembly service and the parley system touch `ILocalBrain`;
  nothing else includes the vendor plugin.
- **Model packaging:** one ~3–4B instruct GGUF **Q4 ≈ 2.5 GB**, shipped in its own **pak
  chunk** (chunk id 100) so Steam delta-patches don't re-ship it; loaded memory-mapped.
  **Swap path:** the model file is addressed by manifest (`Brain/model_manifest.json`: id,
  sha256, ctx, prompt template); a patched manifest + new chunk swaps models without code
  changes; BYO local model = drop-in GGUF + manifest edit (unsupported-but-not-blocked).
- **Prompt assembly service:** `UBrainPromptService` (Core) builds parley prompts from
  personality card + disposition state + closed verdict instruction block; output parsing
  enforces the `02-negotiation-system.md` law — the LLM returns flavor text + one verdict
  token from `{ACCEPT, COUNTER, PROBE, OFFENDED, WALK}`; unparseable → safe fallback verdict
  `PROBE` + wheel UI. **LLM text never mutates stats.**
- **Budgets (binding, from `02-negotiation-system.md`):** reply ≤ **120 tokens**; first token
  < 1.0 s and full reply ≤ **2.5 s on min-spec**; context window trimmed to ≤ 2k tokens per
  parley turn. Inference runs on its own thread pool; never on game or render threads.
- **Min-spec CPU fallback rules:** startup benchmark (one 32-token canned completion) buckets
  the device: GPU-offload full → partial (n_gpu_layers tuned) → **CPU-only**; if CPU-only
  measured throughput < 18 tok/s, free-form parley input is disabled by default and the
  structured **choice wheel** (always present for accessibility anyway) becomes the primary
  input — same verdicts, canned-variant flavor lines, zero content loss. Player can force
  free-form on with a "slow brain" warning.

---

## 4. Save system

- **Versioned `USaveGame` objects:** every save object carries `int32 SaveVersion` +
  `FGuid SaveId`; loaders run an explicit upgrade chain (`v1→v2→…`), never silent best-effort.
  Custom version registered with `FCustomVersion` for property-level deltas.
- **Slots:** **3 manual slots + an autosave ring of 5** (zone transitions, Gauntlet entry,
  pre-parley with rares, 10-min timer); ring entries are full saves, oldest overwritten.
- **Atomic write:** serialize → compress → write `slotN.sav.tmp` → flush → rename over
  `slotN.sav`; a torn write can only lose the newest attempt, never corrupt the prior file.
  Write on a background thread; a save icon (and input grace) on the game thread.
- **Cloud:** Steam Auto-Cloud over the save directory (≤ 100 MB quota budgeted; a full save
  targets ≤ 4 MB); cloud conflict UI defers to Steam's.
- **Save-data schema (top-level sections, each its own versioned struct):**
  1. `Profile` — Architect identity, muse persona/creator output, personality-question seeds.
  2. `World` — act, zone states, encounter/spawn tables consumed, Gauntlet clear flags (8).
  3. `Roster` — caught agents: id, level, attribute snapshot, granted abilities, personality
     card, part recipe (for Foundry rares — they are pure save data, `09-foundry-spec.md` §10).
  4. `NetworkGraph` — the player's mind-graph: wired nodes, edge list, synergy/promotion
     state (the §4.5 progression spine).
  5. `ParleyHistory` — **digests only**: per-agent verdict counts, disposition highwater,
     flags an agent "remembers" — never free-text transcripts (privacy parity with
     `09-foundry-spec.md` §2.3).
  6. `DenLayout` — placed items, room generation refs, buff assignments.
  7. `FoundryRares` — delivered/active candidate cards incl. verdict-card stats.
  8. `Economy` — Cycles, Synapse Thread, Checksum Shards, vendor states.
  9. `Settings` (separate file, not slot-bound) — options, accessibility, consent flags,
     pairing state ref (token itself stays in the encrypted config, never in saves).

---

## 5. Performance targets & budgets

- **Flagship (the Legion: Core Ultra 9 / RTX 5070 / 32 GB):** **60 fps at 1440p, High,
  Lumen + Nanite on**, all four maps. This is the Phase 2 exit-gate machine.
- **Min-spec (defined): GTX 1660 6 GB / 4-core 3.0 GHz / 16 GB RAM:** **30 fps at 1080p**,
  Scaled tier — Lumen off (SSGI/baked fallback), Nanite fallback meshes where unsupported,
  TSR upscale from 67%.

| System | Flagship budget (ms @ 60fps, GT = game thread) | Min-spec (ms @ 30fps) |
|---|---|---|
| World rendering (RT+GPU governed) | 9.0 GPU | 22.0 GPU |
| GAS / combat tick | 1.5 GT | 2.5 GT |
| Agent AI + RTwP command queue | 1.0 GT | 1.8 GT |
| Animation (24 shared-skeleton rigs) | 1.5 GT | 2.5 GT |
| Observatory graph (its map, `10-observatory-spec.md` §8) | 2.0 GT | 3.0 GT |
| UI (CommonUI) | 0.8 GT | 1.5 GT |
| Niagara (GT cost) | 0.7 GT | 1.0 GT |
| Audio (`13-audio-design.md`) | 0.5 GT | 0.8 GT |
| Net/SSE marshal + saves | 0.3 GT | 0.5 GT |
| Local LLM | 0 GT (own pool); ≤ 2 cores during parley | ≤ 2 cores; wheel-primary mode |
| **Game-thread total** | **≤ 8.3 / 16.6** | **≤ 13.6 / 33.3** |

- **Memory:** ≤ **12 GB system RAM** working set (incl. ≈ 2.5 GB mmap'd model — resident
  pressure managed by mmap eviction); VRAM tiers: 8 GB+ full, 6 GB scaled (texture pool
  cap 3.5 GB, model CPU-only).
- **Load times:** < **15 s** into any zone on SATA SSD min-spec (< 6 s NVMe flagship); zone
  streaming via World Partition; the LLM warm-loads asynchronously post-map-load (parley
  locked out behind a 5 s grace, wheel available instantly).
- Budgets enforced by `stat`-capture automation tests on both reference machines per milestone
  (§7); a budget regression is a release-gate failure, not a note.

---

## 6. Platform plan

- **Win64 / Steam first** (Phases 0–6). DX12 + SM6.
- **Android tier later** (Phase 7, master plan §9): same app, **mobile renderer** (forward,
  no Lumen/Nanite), **baked lighting fallbacks** baked from the same levels, **Vulkan**, LOD'd
  agents, touch CommonUI (free with §2.6). Device tiers: A (8 GB RAM, Adreno 740+/Mali
  Immortalis — full game tier), B (6 GB — Observatory + Command Deck + Den only), C —
  unsupported. **Arrival order: Observatory + Command Deck + Den first, game tier second.**
- **The Kotlin companion app stays** (master plan §9): it keeps the two Android-only
  superpowers UE cannot host — the floating overlay body and the accessibility "hands" —
  as a thin companion service beside the UE app.

---

## 7. Build & CI

- **Separate `SYNAPSE` repo + Git LFS** (UE binaries do not enter the muse monorepo);
  `.gitattributes` LFS-tracks `*.uasset *.umap *.png *.wav *.fbx` etc.
- **CI (per push):** UBT builds **Win64 Development + Shipping**
  (`Build.bat SynapseEditor Win64 Development` / `BuildCookRun … -clientconfig=Shipping`);
  warnings-as-errors on `Synapse*` modules.
- **Automation tests** headless via
  `UnrealEditor-Cmd.exe SYNAPSE.uproject -ExecCmds="Automation RunTests Synapse." -unattended
  -nopause -nullrhi -log` — covers Core save round-trips, Net parser/backoff (against a local
  stub), GAS ability specs, tag-registry lint.
- **Nightly cook:** full `BuildCookRun` content cook + package + smoke boot of the packaged
  build (boot-to-menu log assert).
- **Wire-contract version pin checked in CI:** the repo commits
  `synapse/contract.lock` = `{contract_version, sha256 of cockpit-wire-contract.json}`; a CI
  job fetches the pinned muse ref and **fails if the live contract artifact's hash/version
  differs from the lock** — upgrading the gateway contract is always an explicit, reviewed
  lock bump, mirroring `tests/gateway/test_cockpit_contract_freeze.py` from the client side.

---

## 8. Security & privacy

- **No secrets in code** — ever, including tests and logs (log scrubber strips
  `Authorization:` headers at the HTTP wrapper).
- **Bearer tokens in the platform keystore:** Windows DPAPI (CurrentUser) wrapping the AES key
  for `muse_pairing.bin`; Android Keystore on the mobile tier. Token revocation = delete file
  + re-pair.
- **TLS only** for tiers 2–3 (certificate validation on; no pinning v1.0 — revisit). The
  loopback/LAN paired-gateway case may be plain HTTP only when the host is explicitly
  RFC1918/localhost and the user confirmed the pairing screen warning.
- **Telemetry consent gates all egress** (§2.1): one subsystem, queried at every send site;
  hosted-brain calls and Foundry events are unreachable code paths when consent is off.
  Parley free-text never leaves the device on any tier (`09-foundry-spec.md` §2.3).

## 9. Steam integration

- **Achievements: ~30** — 8 Gauntlet clears, 8 domain-mastery (first ACCEPT per domain),
  roster milestones (6/12/24), network milestones, Den, finale, 3 hidden parley gems.
- **Cloud saves** per §4; **rich presence** (zone, act, "In Parley with «…»" — clip-bait by
  design); **overlay-safe rendering** (no exclusive fullscreen default; overlay required for
  the Foundry report path, `09-foundry-spec.md` §9).

## 10. Crash & diagnostics

- Sentry-class crash reporter (Sentry Unreal SDK or equivalent), **consent-gated** (own
  toggle, separate from gameplay telemetry), minidump + log tail, PII-scrubbed paths.
- **Session breadcrumbs:** ring buffer of the last 200 structured events (map loads, save ops,
  SSE state changes, parley starts — never parley text) attached to crash reports only.
- Release health: crash-free-sessions target ≥ 99.5% (the Phase 7 gate number, applied to PC
  from launch).

## 11. Engineering split (the ~70% promptable rule)

Master plan §5: **Claude Code owns the compile-loop C++**; **the owner drives the editor.**

- **Claude Code lane (~70%):** all `Synapse*` module C++, tests, CI scripts — validated
  headless, no editor required:
  - `Engine\Build\BatchFiles\Build.bat SynapseEditor Win64 Development -WaitMutex` (iterate
    until clean; warnings-as-errors),
  - `UnrealEditor-Cmd.exe <proj> -ExecCmds="Automation RunTests Synapse.<Suite>" -unattended
    -nullrhi -log` (prove behavior),
  - `RunUAT.bat BuildCookRun -project=<proj> -platform=Win64 -clientconfig=Development -build
    -cook -stage -pak` (prove packaging).
  No output, no done — paste the build/test log (master plan Prompt 0's validation rule,
  applied to every task).
- **Owner lane (~30%):** levels, lighting (the Lumen doctrine), Blueprint content wiring,
  animation/material taste, Niagara look-dev, mix sessions (`13-audio-design.md` §7). The
  fun part is deliberately the human part.
