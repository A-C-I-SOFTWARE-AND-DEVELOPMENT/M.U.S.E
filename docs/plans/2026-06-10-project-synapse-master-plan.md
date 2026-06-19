# PROJECT SYNAPSE — Master Plan v1.0
### One brain. One UE5 world. Three shipping products.
**Owner:** Jeremiah Echerd · A-C-I Software & Development
**Date:** 2026-06-10 · **Status:** OWNER REVIEW
**Working title:** **SYNAPSE** *(subtitle: "A muse Game")* — trademark/name search is Task 0.4. Backups: *Synaptic Hunters*, *muse Substrate*.

---

## 0. Locked decisions (from our Q&A)

| # | Decision | Locked answer |
|---|---|---|
| 1 | What is the app | muse (Multi-Use Synaptic Entity) — the repo at `A-C-I-SOFTWARE-AND-DEVELOPMENT/muse` |
| 2 | Where UE5 lives | **Everything in one UE5 app** — game + cockpit + Neural Observatory + avatar/Den. Python gateway stays the brain; UE5 is a C++ client over the frozen 96-route cockpit wire contract |
| 3 | Dev machine | Legion / Core Ultra 9 / RTX 5070 — **GO** (verify 32GB RAM, keep 250GB free) |
| 4 | AI brain on Steam | **Hybrid 3-tier ladder:** bundled local GGUF model (always works, offline) → hosted server (foundry, image-gen, heavy reasoning) → BYO muse-gateway/API-key pairing |
| 5 | Art direction | **High-end stylized realism** — Lumen/Nanite, Fab/Megascans environments, small hero roster done stunningly. PC is the visual flagship; Android ships a scaled tier later |
| 6 | Resources | **Full-time, $10k+** |
| 7 | Combat | **Real-time with tactical pause** (FF7R-style), built on Gameplay Ability System |
| 8 | Multiplayer | **Pure single-player.** No netcode. This decision funds the art bar |

---

## 1. What ships — three products, one brain

**P1 — muse Platform v1.0 (the finished, installable app).** The existing repo, completed end-to-end and packaged as one-command installers per platform. This is the brain everything else talks to.

**P2 — SYNAPSE (the UE5 application).** One C++/Blueprint application containing four "maps": the **Game**, the **Neural Observatory** (the cockpit visualization), the **Avatar & Den**, and the **Command Deck** (chat/jobs/approvals — the classic cockpit). Ships on Steam (PC flagship) and later Android (scaled rendering tier, same app).

**P3 — The Hosted Brain (service).** A small server you operate: the agent foundry, image-gen for the room editor, heavy-reasoning escalation, and telemetry ingestion. Capped free tier; degrades gracefully to local when offline.

**Coupling rule (the one law of this architecture):** nothing in `hermes_cli/jarvis_prime/`, GraphRAG, the orchestrator, the gates, or the ledgers gets ported to C++. The UE5 app consumes the gateway over HTTP/SSE per `docs/contracts/cockpit-wire-contract.md` (96 routes, pinned by `test_cockpit_contract_freeze.py`). New capabilities are **additive route families** (`/v1/observatory/*`, `/v1/game/*`, `/v1/foundry/*`) added gateway-side, regenerated into the contract, and frozen the same way.

---

## 2. Requirement traceability (original asks → plan sections)

| Ask | Where it lands |
|---|---|
| Finish entire app, everything functional | §10 (P1 workstream) |
| Installable package, everything included | §10.3 |
| Cockpit on Android + desktop with neural network & vector pipeline visualization, interactive | §3 (Neural Observatory), §9 (Android tier) |
| Friction/bottleneck visualization + fact-based recommendations ("do X → 21% increase") | §3.3–3.4 (honest measurement engine) |
| Make changes to the brain from the cockpit | §3.5 |
| C++ + Unreal, visually stunning, full animation/interaction | §5 (stack), §6 (phases), Decision 5 |
| Expand the avatar/room idea | §4.6 |
| Pokémon-like game catching agents/skills into your neural network | §4 |
| muse autonomously builds characters & tailored agents from observed user struggle, validated + tested | §4.7 (The Foundry) |
| Research AAA/indie mechanics, character selection → onboarding | §4.6, §8.1 (research digest) |
| Standalone game, not a muse add-on | §4.8 |
| #1 on Steam | §8 (honest math + engineered targets) |

---

## 3. The Neural Observatory (the cockpit visualization, in UE5)

### 3.1 What you see
A 3D, flyable, living rendering of muse's actual mind:

- **The Graph.** GraphRAG's real graph (~28k nodes / ~52k edges) rendered as a galaxy. **LOD strategy is mandatory:** the gateway pre-clusters into ~200 super-nodes (communities by type: code, docs, memory, ledger); zooming expands clusters on demand. Force-directed layout is computed **gateway-side** in Python (networkx/igraph, cached) and streamed as positions — UE renders, it does not solve 28k-node physics per frame.
- **The Pipelines.** Live orchestrator jobs as light-packets flowing through stations: `Job → Navigator → Worker → Gate → Ledger`. Niagara particle systems on splines; each packet is clickable → the real job record.
- **The Brain Ladder.** Local model ↔ hosted ↔ paired-gateway routing shown as three glowing strata; each turn's routing decision animates the path it took (data already exists in `_brain_hint` routing).

### 3.2 Data plumbing (new, additive)
Gateway-side: a `metrics.py` collector (stdlib, matching house style) that timestamps every job stage, gate verdict, queue depth, model latency, token spend, and retry. Exposed as `GET /v1/observatory/snapshot` (positions + cluster summaries), `GET /v1/observatory/stream` (SSE deltas: job events, gate events, node activations), `GET /v1/observatory/metrics?window=`. All read-only, bearer-auth, added to the frozen contract via the generator.

### 3.3 Bottleneck visualization
Heat is **computed from real measurements only**: p95 stage latency, queue wait time, gate failure rate, retry count, token cost per task class. Hot paths glow red; clicking a hot edge opens the evidence: the actual ledger entries behind the heat. No vibes, no invented scores — this is the visual front-end to data the system already records.

### 3.4 The Recommendation Engine — honest by construction
The "21% increase" feature, built so it would pass `aos-audit-validator`:

1. **Baseline:** rolling measured baselines per task class (latency, success rate, gate-pass rate, cost) from the metrics store.
2. **Hypothesis:** rule-based + model-suggested candidates ("route `code` tasks ≤300 LOC to local coder model," "raise Review-gate strictness on `release` class").
3. **Validation:** offline **replay** of recent real tasks under the candidate policy (batch_runner is the natural harness), or shadow-routing a small live sample.
4. **Verdict card:** *"Route short code tasks to qwen-coder-local: median latency −38% (n=212 replayed tasks, 95% CI −31%…−44%), success rate unchanged (Δ +0.4pp, n.s.)."* Every number links to ledger entries.
5. **Apply** is an owner-gated action (§3.5) with one-click rollback.

**Hard rule:** the engine never states a percentage it did not measure. If sample size is too small, the card says "insufficient evidence (n=7) — collecting." This is the difference between a control room and a slot machine.

### 3.5 Editing the brain from the cockpit
Owner-gated POSTs (existing `owner-phrase` mechanism, ledger-logged, reversible): model routing pins & weights (`model_policy.json` overrides), mode policies, skill enable/disable, memory-tree curation (approve/supersede), autonomy level, foundry on/off. In the Observatory these are physical interactions — grab a routing strand, re-wire it, confirm with the owner phrase. Every edit writes a ledger entry and a rollback point. The 10 existing owner-gated routes already model this pattern; we extend it, never bypass it.

---

## 4. SYNAPSE — the game (design core)

### 4.1 Fantasy & premise
You are an **Architect** dropped into the **Substrate** — a vast mind-world where autonomous agents roam wild. Your task: rebuild a shattered neural network by **recruiting** specialized agents, wiring them into your growing mind, and proving the network at the eight great **Gauntlets**. The Den is your home node; your muse avatar is your first companion.

### 4.2 The differentiator: capture by conversation
You don't throw a ball. You **negotiate** (Shin Megami Tensei lineage, modernized): approach a wild agent, enter a parley, and *talk it into joining* — live dialogue powered by the bundled local LLM, with each agent's personality derived from its real council role (a Security agent is paranoid and tests your intentions; a QA agent demands proof; a Research agent can be lured with a mystery). Structured fallbacks (choice wheels) keep it playable on min-spec and fully offline. This is simultaneously the genre hook nobody has shipped at quality, the showcase for the local AI tier, and the infinitely-clippable streamer moment.

### 4.3 Roster — the AOS Enterprise Council made flesh
**24 launch hero agents** (not 151 — AAA quality over quantity), drawn from the real 233-role council registry, across **8 domains that double as the type chart**: Architecture, Security, QA/Test, Research, Build/Ops, Behavior/Psych, Compliance (HazMat heritage), Release. Domain interactions form advantages (Security counters Release; QA counters Build; Research counters Security…). Each agent ships with: a commissioned-or-curated AAA model, a shared-skeleton rig, 6–10 GAS abilities, a personality card (drives negotiation + combat banter), and a **real capability** — because caught agents map to actual muse skills (§4.5).

### 4.4 Combat — real-time with tactical pause, on GAS
Party of 3 active agents fighting semi-autonomously per personality; **pause = Command Mode** (the orchestrator fantasy made literal): queue abilities, swap members, target-call, trigger **Pipelines** — chained cross-agent combos (Research *marks* → Security *exploits* → Build *detonates*). Built entirely on Unreal's Gameplay Ability System (attributes, gameplay effects, ability queues, tags) — battle-tested, single-player-simple without replication burden.

### 4.5 Progression — the network IS the character sheet
No XP bars as the spine; instead a **Neural Network screen**: caught agents are nodes you physically wire into your mind-graph. Adjacency creates synergies; deeper wiring unlocks evolved forms ("promotions" — the agent's council senior role). And the bridge that makes this *not just a game*: wiring an agent into your network can unlock its **real counterpart** in your actual muse install (owner-gated, cosmetic-by-default, opt-in) — catch the QA agent in-game, gain the QA skill in your real cockpit. The Observatory and the in-game network screen share one UI system: build once, ship twice.

### 4.6 Avatar, Den, and onboarding-as-character-creation
Onboarding **is** designing your muse a character creator that doubles as muse's persona setup (the existing `/v1/cockpit/avatar/persona` endpoint pattern). Research-informed beats from the genre greats: a meaningful starter choice (Pokémon), an aesthetic-identity creator (Palworld/Temtem), and a personality-shaping question sequence (Persona/SMT) whose answers seed the avatar's negotiation style. The **Den** expands the existing room concept (`/v1/cockpit/avatar/room*` endpoints are live): your in-game base, furnishable via the AI room editor once the image-gen provider is wired (P3 unblocks the one documented gap), with placed items granting small network buffs so decoration feeds the loop.

### 4.7 The Foundry — agents born from your struggle (the genuinely new thing)
The autonomous system specified by the owner, run honestly:

1. **Observe:** telemetry (opt-in, disclosed) detects struggle patterns — repeated deaths to a Gauntlet, failed negotiations with a domain, economy stalls.
2. **Hypothesize:** the hosted muse proposes a tailored helper agent/skill ("this player loses to burst damage in Security fights → candidate: a Mitigation-class agent with interrupt tools").
3. **Build:** generated via the existing skill-creation loop (stats, GAS ability set from a vetted component library, personality card; art from a pre-approved modular part bank — no raw live-gen 3D).
4. **Validate:** simulated battle harness replays the player's failure scenarios with and without the candidate; promote only on a measured win (the benchmark-wall pattern, verbatim).
5. **Ship:** the agent **spawns in that player's world as a discoverable rare**, its card showing real validation stats: *"Forged for you. In 400 simulations of your last 6 defeats, survival 31% → 64%."*

Steam compliance is designed-in (§8.4): this is live-generated content → disclosed, guardrailed (template-constrained generation, profanity/illegal filters, no live-gen raw art), player-facing AI indicator on negotiation dialogue, and the overlay report path honored.

### 4.8 Standalone-game test (so it's never "a muse add-on")
SYNAPSE must clear all five: (1) complete and excellent **fully offline** with zero muse knowledge required; (2) a real campaign — 5 zones, 8 Gauntlets, a Council finale, 20–30h; (3) self-contained fiction (the Substrate stands alone; muse integration is a post-game reveal, not a prerequisite); (4) its own Steam identity, capsule, and community; (5) reviewable as a creature-collector RPG, full stop. Market reality supporting the bet: Temtem moved 500k+ copies in a month, Coromon passed 100k, Steam now runs a dedicated Creature Collector Fest, and the genre still lacks its Stardew-scale indie king — demand is proven, the throne is open, and *negotiation-by-AI at AAA fidelity* is a differentiator no incumbent has.

### 4.9 World scope (fixed, do not grow)
Five dense zones, AAA-lit, Megascans-built: **The Stacks** (archive-forest), **The Foundry** (industrial heat), **The Vault** (security citadel), **Gardens of Memory** (overgrown data-ruins), **The Gate Spire** (endgame). Eight Gauntlets distributed across them — each themed as one of the verification gates: *Planning, Build, Review, Test, Security, Release, Owner Approval, Rollback* — bosses that teach the mechanic their gate enforces. The Council awaits at the Spire.

---

## 5. Tech stack & project setup

| Layer | Choice | Note |
|---|---|---|
| Engine | **Unreal Engine 5.6** (pin minor version for the project's life) | Lumen + Nanite on PC; mobile renderer tier for Android |
| Language split | **C++ core, Blueprint glue** | C++: gateway client, GAS abilities base, save system, observatory data, LLM bridge. BP: content wiring, UI flows, encounter scripting |
| Combat | **Gameplay Ability System** | + GameplayTags as the lingua franca |
| UI | **CommonUI** + UMG | One widget library shared by game network screen & Observatory |
| VFX | **Niagara** | Graph edges, pipeline packets, ability VFX |
| Local LLM | **Fab plugin (Runtime Local LLM or GenAI Llama)** — buy, don't build | GGUF, streaming, Blueprint+C++, Win/Mac/Linux/Android. Bundle one ~3–4B instruct model (Q4) ≈ 2.5GB |
| Repo | **New repo `SYNAPSE` + Git LFS** | UE binary assets do not belong in the muse monorepo. Coupling = pinned wire-contract version checked in CI |
| Module map | `SynapseCore`, `SynapseNet` (gateway client, SSE), `SynapseAgents` (GAS), `SynapseObservatory`, `SynapseFoundryClient`, `SynapseUI` | |
| Claude Code workflow | Claude Code writes/compiles C++ headless via UnrealBuildTool & `UnrealEditor-Cmd` automation tests; **the owner** drives the editor for levels/art/Blueprint visual work | Honest split: ~70% of engineering is promptable; lighting/art taste is the owner's to learn — it's also the fun part |
| Assets | Fab + Quixel Megascans (included with UE) for environments; 3 commissioned hero creatures; modular creature part-bank for the rest | |

---

## 6. Phases & gates (full-time; every phase exits through a GO/NO-GO with evidence — the house rule)

| Phase | Weeks | Deliverable | Exit gate (evidence required) |
|---|---|---|---|
| **0 — Foundation** | 1–3 | UE5.6 + VS2022 installed; SYNAPSE repo + LFS + CI; UE fundamentals sprint (GAS + Lumen courses); name/trademark search; **GPL/clean-room legal re-audit started (§8.5)** | Empty packaged build runs; UE C++ app calls gateway `/health` and `/v1/cockpit/capabilities` with bearer auth |
| **1 — The Spine** | 4–8 | `SynapseNet` client (auth, SSE), GAS skeleton, 1 gray-box agent, RTwP pause loop, local-LLM plugin integrated | **The Moment:** negotiate one wild agent into joining via live local-LLM dialogue, then win one paused-command fight. Captured on video |
| **2 — Vertical Slice** | 9–16 | One zone (The Stacks) at full AAA lighting, 5 agents, 1 Gauntlet (Test), Den + avatar onboarding v1, network screen v1 | 20-minute slice; 5 external playtesters; median "would wishlist" ≥ 4/5; stable 60fps on the Legion |
| **3 — Observatory & Brain** | 17–26 (parallel lane) | `/v1/observatory/*` routes + metrics collector (gateway PR, contract regenerated); UE Observatory map; recommendation engine v1 (replay-validated); owner-gated brain edits | One real recommendation card produced from ≥100 replayed tasks, applied via owner phrase, rolled back cleanly — ledger screenshots as proof |
| **4 — Production** | 17–40 | Remaining 4 zones, 24 agents, 8 Gauntlets, Council finale, save system, options/accessibility, foundry server v1 | Full campaign playable start→finish by an outsider without dev help |
| **5 — Market engine** | 30→launch | Steam page live (week 30 at the latest — the wishlist clock starts here), capsule art commissioned, trailer, demo build, Discord, devlog cadence; enter **Creature Collector Fest**; pick the **last Next Fest before launch** | 2,000+ wishlists before Next Fest (target 5,000); demo session length ≥ 25 min median |
| **6 — Launch (PC/Steam)** | ~64–80 (mo. 16–20) | 1.0 premium release, **$24.99**, single-player complete; AI disclosure finalized; press/creator kit out 6 weeks prior | 7,000+ wishlists (Popular Upcoming threshold); ship decision per §8.3 |
| **7 — Android tier + muse bridge** | post-launch | Mobile renderer pass, touch UI for Observatory/Den first, game tier where hardware allows; deepen game↔real-muse unlocks | Play-store track green; crash-free ≥ 99.5% |

**P1 (muse Platform v1.0) runs as a parallel lane in weeks 4–20** — see §10. Timeline honesty: vertical slice month ~4, demo month ~9–10, launch month 16–20. Anyone promising a Steam-topping UE5 RPG faster than that is selling something.

---

## 7. Budget — the $10k

| Item | $ | Why |
|---|---|---|
| Capsule + key art (pro illustrator) | 1,200 | The data is brutal: most wishlists come from people who never play the demo — the store page converts. Highest-ROI dollars in the plan |
| 3 hero creature commissions (model+rig+anims) | 3,600 | The box-art agents; the rest of the roster = curated Fab bases + modular part-bank + a material pass |
| Fab asset packs (env/VFX/UI/anim) | 1,000 | Buy speed |
| Music license / composer mini-score | 800 | Identity |
| SFX + light VO (negotiation barks) | 500 | The parley scenes carry the game |
| Tools (Rive, audio, misc subs) | 300 | |
| Steam Direct fee | 100 | |
| Hosted brain: 12 mo small GPU/API budget | 1,200 | Capped free tier; BYO-key offloads enthusiasts |
| Trailer edit + festival/marketing | 700 | |
| Contingency | 600 | Something always |
| **Total** | **10,000** | |

---

## 8. The Steam strategy — engineered targets, honest math

### 8.1 What the genre research says (digest)
Negotiation/relationship capture (SMT/Persona lineage) is beloved and almost never executed in 3D at fidelity; Palworld proved the genre explodes when a fresh verb meets meme-ability; Temtem/Coromon/Cassette Beasts/Monster Sanctuary prove a steady mid-market exists even for retro art — and nobody owns "AAA-looking creature collector on PC." Character-selection patterns worth stealing for onboarding: meaningful starter (Pokémon), identity creator (Temtem/Palworld), personality questions that mechanically matter (Persona). Steam's own **Creature Collector Fest** is a free amplification slot purpose-built for this game.

### 8.2 The funnel, by the numbers
Store page live ≥ 12 months pre-launch. Demo out **months** before the one allowed Next Fest (pre-fest wishlist count is the strongest success predictor, r≈0.82; entering with <1,000 rarely breaks out — we enter with 2,000–5,000+). Thresholds we steer by: **7,000** wishlists ≈ Popular Upcoming; **30–50k** ≈ Gold-tier ($250k+) launches. Launch with a 10% discount week, 1.0-complete, review-bomb-proof single-player.

### 8.3 The honest sentence about "#1"
\#1 *global* top-seller is a lottery (Palworld was a 10-year-anomaly with co-op virality we deliberately cut). What we **engineer**: #1 in the Creature Collector tag, New & Trending front page, top-10 Popular Upcoming, and a Next Fest demo in the most-played lists. What we **design for** is the viral vector that buys lottery tickets: 30-second clips of players *talking* a paranoid Security agent into joining, and the Foundry card that says *"this agent was forged from your failures — and here's the proof."* If lightning strikes, the architecture is ready; if it doesn't, the floor is a healthy premium indie.

### 8.4 Steam AI compliance (drafted in, day one)
Two-tier disclosure per the Jan-2026 rules: **Pre-generated** — "AI-assisted concepting and code; all shipped art human-curated/edited." **Live-generated** — "Agent negotiation dialogue and Foundry agent descriptions are generated at runtime by a bundled local language model (named) and our service; guardrails: template-constrained outputs, allowlisted ability/art components (no live-gen art assets), profanity/illegal-content filters, player-facing AI indicator, and support for Steam's in-overlay reporting." Dev-efficiency AI use (Claude Code) is explicitly exempt. We wear the label proudly — transparency is the brand.

### 8.5 Legal gate (blocking, cheap, do it now)
The prior repo audit flagged the **OpenHuman GPL-3.0 clean-room reimplementation** question. Before any commercial sale: a license re-audit of everything the *shipping products* touch (SYNAPSE links nothing GPL — verify; gateway distribution posture for P1 — verify), the name search, and a one-hour IP consult (~$300, fits contingency). A Steam takedown after launch costs 100× more than this.

---

## 9. Android (the second screen, sequenced honestly)
Same UE5 app, mobile rendering tier: baked/cheaper lighting, LOD'd agents, touch CommonUI. **Order of arrival:** Observatory + Command Deck + Den first (they're UI-heavy and shine on phone, pairing with the gateway exactly like the Kotlin cockpit does today), the full game tier second on capable devices. The existing Kotlin app remains the home of the two Android-only superpowers UE cannot host — the floating overlay body and the accessibility "hands" — kept as the thin companion service.

---

## 10. P1 — Finish muse Platform v1.0 (parallel lane, weeks 4–20)

**10.1 Definition of done:** the held PR chain resolved per the `R00` decision matrix (#131 → #142 → #143 → #147 → #149 → #150 rebased and landed, owner-authorized at each gate); image-gen provider wired (unblocks the room editor — also feeds P3); voice engine concretes bound; live gateway default-on after pairing; test suite green; docs current.
**10.2 Everything-functional audit:** run `aos-audit-validator` against the README's claims table; every UNSUPPORTED/PARTIAL becomes a ticket; v1.0 means the claims table is all SUPPORTED.
**10.3 The installable package:** one command per platform — Windows `install.ps1` (exists — harden), Linux/WSL/macOS installer + Homebrew (packaging/ exists), Termux path (constraints file exists), Docker compose, Android APK (release-signed), Tauri desktop bundle — each bundling model bootstrap (`muse models bootstrap`), first-run pairing, and a smoke-test that proves the install with output, per the no-evidence-no-claim rule.

---

## 11. Risk register (top 7, honest)

| Risk | Mitigation |
|---|---|
| UE5 learning curve (owner is a beginner) | Phase 0 sprint; C++ via Claude Code with compile-loop validation; Blueprint for everything visual; vertical-slice gate at week 16 is the go/no-go reality check |
| Scope creep (this plan's natural predator) | The numbers are contractual: 5 zones, 24 agents, 8 Gauntlets, 0 multiplayer. New ideas go to a post-launch list |
| AAA art bar slips into uncanny mediocrity | Lighting-first doctrine; one art bible; hero-asset budget; cut a zone before cutting quality |
| GPL/licensing surprise | §8.5 gate in Phase 0, blocking |
| Hosted-tier cost runaway | Hard caps, queue limits, BYO-key path, local-tier fallback is always complete |
| AI-content backlash | No live-gen shipped art; human-curated everything visible; proud, specific disclosure; the Foundry shows its validation receipts |
| Solo burnout | Phase gates are also rest gates; demo at month 9–10 gives a real-world morale injection; the parallel P1 lane gives variety |

---

## 12. First 7 days (exact)

1. Verify RAM (upgrade to 32GB if 16) and free 250GB (external NVMe fine).
2. Install: Visual Studio 2022 (Game Dev with C++ workload), Epic Launcher → UE 5.6, Git LFS.
3. Create `SYNAPSE` repo (private), `.gitattributes` for LFS, CI stub that builds Win64 Development.
4. Name/trademark search for "SYNAPSE" in games (USPTO + Steam search); book the $300 IP consult; open the GPL re-audit ticket.
5. Buy + integrate the local-LLM Fab plugin into a blank C++ project; load a 3–4B GGUF; stream one reply in-PIE.
6. Run **Prompt 0** (below) in Claude Code to scaffold modules + the gateway client.
7. Watch, hands-on: one GAS crash-course and one Lumen lighting walkthrough; recreate the lighting in a Megascans test room. That room becomes The Stacks' first corner.

---

## 13. Prompt 0 — Claude Code master prompt (Hermes structure)

> **Role:** Senior UE5 C++ engineer scaffolding a production game client.
> **Task:** In the SYNAPSE UE 5.6 C++ project, create modules `SynapseCore` and `SynapseNet`. `SynapseNet` implements `UmuseGatewayClient` (UGameInstanceSubsystem): bearer-token auth from a local config (never hardcoded), `GET /health`, `GET /v1/cockpit/capabilities`, and an SSE consumer for streaming routes, with delegates broadcasting typed events to Blueprint.
> **Context:** Gateway contract = `cockpit-wire-contract.md` in repo docs (96 routes; bearer auth; 6 open routes). Target: Win64 first. Engine 5.6 pinned. HTTP via FHttpModule; SSE via streamed response parsing.
> **Constraints:** No engine-source edits. No plugins beyond engine defaults for this task. All network off the game thread. No secrets in code or logs. Compile must pass via UBT command line; warnings-as-errors for our modules.
> **Output:** Module files, Build.cs files, the subsystem, a minimal test map BP that prints `/health` + capabilities on BeginPlay, and a `docs/synapsenet.md`.
> **Validation:** Paste the successful UBT build output and the PIE log lines showing the live gateway responses. No output, no done.
> **Fallback:** If the gateway is unreachable, implement and demonstrate against a 20-line Python stub server matching the two routes, and flag OWNER-BLOCKER: pairing needed.

---

## 14. Owner decisions still open (answer when ready, defaults will hold)
1. Game name sign-off after the trademark search (default: SYNAPSE).
2. Price (default $24.99; revisit at wishlist data).
3. Early Access vs straight 1.0 (default: straight 1.0 for a single-player premium; revisit only if Phase 4 slips).
4. Which 3 agents get the commissioned-hero budget (default: one each from Security, Research, Behavior — the negotiation stars).
5. Telemetry consent copy + what the Foundry may observe (default: opt-in at first run, full list shown).

*Every phase exit is a GO/NO-GO with evidence — the same standard the existing gates enforce. Build the spine, earn the slice, then we scale the mountain.*

---

## Appendix A — Repo verification (2026-06-10)

Every repo-facing claim in this plan was verified against the working tree on the date above, per the no-evidence-no-claim rule. Evidence paths:

| Plan claim | Verified against |
|---|---|
| 96 routes, 6 open routes, bearer auth | [`docs/contracts/cockpit-wire-contract.md`](../contracts/cockpit-wire-contract.md) — "Census (real counts)" section |
| Contract freeze test pins the contract | `tests/gateway/test_cockpit_contract_freeze.py` (regenerates in-memory, asserts equality with committed artifacts) |
| Contract generator (path for additive `/v1/observatory/*`, `/v1/game/*`, `/v1/foundry/*` families) | `scripts/generate_cockpit_contract.py` |
| 10 existing owner-gated routes (owner-phrase mechanism) | Wire contract: `POST` approvals/{id}, autonomy, coding/execute, evidence/{id}/promote, jobs/{id}/approve, jobs/{id}/publish, jobs/{id}/run, learning/{id}, model-routes/override, pair/confirm |
| `/v1/cockpit/avatar/persona` (GET/POST) and `/v1/cockpit/avatar/room*` live | Wire contract: `GET/POST /v1/cockpit/avatar/room`, `DELETE /v1/cockpit/avatar/room/{id}`, `POST /v1/cockpit/avatar/room/{id}/place` |
| `/v1/cockpit/learning` family exists | Wire contract: `GET /v1/cockpit/learning`, `GET /v1/cockpit/learning/export`, `POST /v1/cockpit/learning/{id}` |
| `_brain_hint` routing data exists | `gateway/cockpit/agent.py` (`_brain_hint(turn, mode)`) |
| GraphRAG graph scale | [`docs/jarvis_architecture/GRAPHRAG_KNOWLEDGE_GRAPH.md`](../jarvis_architecture/GRAPHRAG_KNOWLEDGE_GRAPH.md) — actuals **28.6k nodes / 51.6k edges** (plan body's ~28k/~52k stands; this is the precise figure) |
| Held PR chain #131→#142→#143→#147→#149→#150 + R00 decision matrix | [`docs/aci/reports/R00_REMAINING_SPRINT_DECISION_MATRIX.md`](../aci/reports/R00_REMAINING_SPRINT_DECISION_MATRIX.md), [`docs/aci/reports/R00_CURRENT_LAUNCH_STACK_AUDIT.md`](../aci/reports/R00_CURRENT_LAUNCH_STACK_AUDIT.md) |
| `aos-audit-validator` exists | `dotclaude/agents/aos-audit-validator.md` (agent definition; routed via `.claude/commands/aos-audit.md`) |
| Installers & packaging surface for §10.3 | `scripts/install.ps1`, `packaging/` (incl. Homebrew), `constraints-termux.txt`, `muse models bootstrap` (`hermes_cli/main.py`, `hermes_cli/setup.py`) |

No SYNAPSE / Neural Observatory / `/v1/observatory|game|foundry` artifact existed in the repo before this document — all such route families are future, additive, gateway-side work gated by the contract generator + freeze test, per the coupling rule in §1.
