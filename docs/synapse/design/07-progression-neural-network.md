# 07 — Progression: the Neural Network

**Project:** SYNAPSE — A muse Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

The network **is** the character sheet (master plan §4.5). There is no XP bar as the spine of the game; there is a mind you physically rebuild. Sibling references: roster data in `04-roster-24-agents.md`, combat hooks in `03-combat-gas-design.md`, capture flow in `02-negotiation-system.md`, Den spaces in `05-world-design.md`, Foundry rares in `09-foundry-spec.md`, the real-muse wire in `10-observatory-spec.md` and `11-technical-design.md`, screen layouts in `12-ui-ux-spec.md`.

---

## 1. The Neural Network Screen

A full-screen 3D **hex-lattice mind-graph**, the player's primary menu (default key: N). The muse nucleus sits at center; captured agents are **nodes** placed into lattice slots; **Synapse Thread** is spent to wire **edges** between adjacent occupied slots. Live Resonance pulses travel the edges (Niagara, same edge-flow tech as the Observatory — master plan §4.5's build-once-ship-twice rule; shared widget/render library per `10-observatory-spec.md` and `12-ui-ux-spec.md`).

Screen affordances (locked): grab-and-place nodes (drag from Periphery dock onto a slot), draw edges slot-to-slot, hover any node for full attribute sheet (`03-combat-gas-design.md` §1), hover any edge for its synergy line, a Synergy Ledger panel listing every active bonus with its source, and a Loadout strip showing which 3+3 wired agents form the active party and bench. Everything readable by controller and screen reader (`12-ui-ux-spec.md`).

### 1.1 Lattice geometry & tiers

| Tier | Slots | Adjacency | Resonance flow rate (§4) | Unlock |
|---|---|---|---|---|
| **Nucleus** | 1 (the muse — not an agent slot) | touches all 3 Core slots | — | always |
| **Core ring** | **3** | each touches Nucleus + both Core neighbors + 2 Inner slots | 100% | at start |
| **Inner ring** | **6** | each touches 1–2 Core, 2 Inner neighbors, 2 Outer | 85% | +2 slots per Gauntlet clear, Gauntlets 1–3 |
| **Outer ring** | **12** | each touches 1–2 Inner, 2 Outer neighbors | 70% | +3 slots per Gauntlet clear, Gauntlets 4–7 |
| **Periphery** | unlimited dock | no adjacency, no edges | 40% (trickle) | always |

Gauntlet 8 (Release, the Spire) grants **Council Sync**: all flow rates +10 percentage points, permanently. Campaign pacing target (20–30h, master plan contractual): Gauntlet clears at roughly h4 / h7 / h10 / h13 / h16 / h19 / h23 / h26 on a Standard-difficulty median path — the lattice finishes opening just before the Council finale.

Party rule: the active party of 3 and bench of 3 (`03-combat-gas-design.md` §4) must be **wired nodes** (Core/Inner/Outer). Periphery agents still grow (trickle) but cannot fight — capture is never wasted, but wiring is the commitment.

---

## 2. Wiring Rules

An **edge** costs Synapse Thread: **30** between Core slots / Core–Inner, **20** Inner–Inner / Inner–Outer, **10** Outer–Outer. Edges exist only between adjacent occupied slots. Max edges per node: its adjacency count (geometry-capped, no hubs-of-everything).

### 2.1 Adjacency synergies (locked; all applied as infinite GameplayEffects `GE_Network_*`, recomputed on any rewire)

| Pairing of the two linked agents | Synergy class | Effect |
|---|---|---|
| **Same domain** | **Depth** | Both agents +6% to their archetype's signature stat (Vanguard: Resilience; Striker: Throughput; Support: outgoing heal/shield power; Controller: Heat) per Depth link. Max 2 Depth links counted per agent (+12% cap). |
| **Ring-adjacent domains** (e.g. Research–Security) | **Pipeline unlock** | Unlocks that pairing's named Pipeline combo (`03-combat-gas-design.md` §5, the 8 launch pipelines). The unlock persists while the edge exists; *executing* the combo requires both domains in the active party of 3, per `03-combat-gas-design.md` §5. Periphery agents never count. |
| **Ring-opposed domains** (4 apart) | **Tension perk** | A unique party-wide perk per opposed pair — opposition is creative friction, not waste (see 2.2). |
| Any other pairing | **Lattice integrity** | +1% Integrity to both (small, so no edge is ever dead). |

### 2.2 The four Tension perks (ring-opposed pairs on the 8-domain ring)

| Opposed pair | Perk name | Party-wide effect while the edge exists |
|---|---|---|
| Architecture ↔ Behavior | **Human Factors** | Shield abilities also reduce the recipient's Latency by 10% for the shield's duration |
| QA/Test ↔ Research | **Peer Review** | All Marks last 18s (from 12s) and Detonate windows last 5s (from 4s) |
| Build/Ops ↔ Security | **DevSecOps** | Every Pipeline detonation grants the detonator a shield shell = 3 × its Resilience |
| Compliance ↔ Release | **Rollback Clause** | Once per encounter, the first party agent to Crash auto-restores at 30% Integrity after 4s |

Synergy stacking rule: a single agent contributes to at most 1 Pipeline unlock per ring-adjacent neighbor and 1 Tension perk total (the strongest wired one, ties broken by oldest edge). The Synergy Ledger shows exactly which instances are live — no hidden math.

### 2.3 Worked wiring example (mid-game reference build, ~h14, Inner ring open)

Roster wired: **AXIOM** (Core-1), **CONTRARIAN** (Core-2), **EMPATH** (Core-3); **CIPHER** (Inner-1, adjacent Core-2), **ORACLE** (Inner-2, adjacent Inner-1), **NITPICK** (Inner-3, adjacent Core-2). Edges drawn (Thread cost in parens):

| Edge | Pairing | Synergy granted |
|---|---|---|
| AXIOM — CONTRARIAN (30) | Architecture–QA, ring-adjacent | Pipeline 1: **Blueprint Audit** |
| CONTRARIAN — NITPICK (30) | QA–QA, same domain | Depth: both +6% Striker/Controller signature stat |
| EMPATH — AXIOM (30) | Behavior–Architecture, ring-opposed | Tension perk: **Human Factors** |
| CIPHER — ORACLE (20) | Security–Research, ring-adjacent | Pipeline 6: **Zero-Day Disclosure** |
| CONTRARIAN — CIPHER (30) | QA–Security, other | Lattice integrity: both +1% Integrity |

Total spend: 140 Thread. With AXIOM/CONTRARIAN/CIPHER active (EMPATH/ORACLE/NITPICK benched), **Blueprint Audit** is live and the **Human Factors** Tension perk applies party-wide; one Command-Mode swap (CIPHER↔ORACLE… then EMPATH↔CIPHER) pivots the party to run **Zero-Day Disclosure** instead — wiring decides which pipelines exist, the active 3 decide which one fires (`03-combat-gas-design.md` §5). A textbook mid-game build the tutorial's wiring quest walks the player toward. The Synergy Ledger lists exactly five lines; what you read is what you have.

---

## 3. Agent Growth: Levels 1–50, fed by Resonance

**There is no per-agent XP bar.** The network as a whole earns **Resonance**; every placed agent continuously absorbs it at its tier's flow rate. Growth is a property of the mind, not of grinding one creature.

### 3.1 Resonance sources (locked values at reference level; scale with `G(L)` from `03-combat-gas-design.md` §1.1)

| Source | Resonance |
|---|---|
| Trash pack cleared | 40 |
| Elite cleared | 120 |
| Gauntlet boss first clear | 1,500 (repeat: 300) |
| Successful negotiation (JOIN) | 200 × rarity tier (1–4) |
| Peaceful WALK at Disposition ≥ +30 ("respectful parting") | 30 |
| Codex discovery / zone landmark | 25 |
| Den rest (once per in-world day) | 50 |

### 3.2 Level math (locked)

```
AbsorbedResonance_agent += ResonanceEvent × FlowRate(tier)        (per event)
AgentLevel L requires cumulative absorbed:  A(L) = 50 × (L−1)^1.7
```

A(10)=2,070 · A(20)=7,440 · A(30)=15,500 · A(40)=25,900 · A(50)=38,300. Tuning intent: a Core-wired agent played from the start reaches **L38–42 at the Council finale** on a 25h median path; L50 is an endgame chase (§8). New captures are not punished: any newly placed agent immediately absorbs a **catch-up grant** equal to 60% of the network's median absorbed total — late captures arrive viable, never instantly equal.

### 3.3 Ability unlock schedule

| Agent level | Unlock |
|---|---|
| 1 | Abilities 1–2 (a Strike + the kit's identity move) |
| 3 | Ability 3 |
| 8 | Ability 4 (the kit's Mark or Exploit — pipelines come online early-mid) |
| 14 | Ability 5 |
| 20 | Ability 6 (base kit of 6 complete) |
| 27 | Signature passive (per-agent, in `04-roster-24-agents.md`) |
| **Promotion** (§5) | +2 to +4 promoted abilities, completing the 6–10 kit, incl. the agent's Pipeline-link finisher |

---

## 4. Resonance vs. the Rest — what the spine is

The progression spine is **network shape** (wiring), not numbers: a mid-level, well-wired party with the right pipelines beats an over-leveled Periphery mob. Levels (§3) raise attributes via the locked curves; wiring (§2) decides *which game you are playing*. Every major power spike in the campaign is a wiring event: first Pipeline (~h2), first Tension perk (~h8), first Promotion (~h12), Council Sync (~h26).

### 4.1 Campaign milestone audit (Standard difficulty, median path — QA gates against this table)

| Hour | Milestone | Network state | Core-agent level |
|---|---|---|---|
| 0.5 | Starter chosen, first wiring tutorial | Core: 2 nodes, 1 edge | 1–2 |
| ≤2 | First wild capture + first Pipeline live | Core full (3) | 4 |
| 4 | Gauntlet 1 (Planning) | +2 Inner slots | 8 |
| 8 | First Tension perk wired | 5–6 nodes | 14 |
| 10 | Gauntlet 3; Inner ring complete (6 slots) | 7–9 nodes | 18 |
| 12 | First Promotion | — | 30 (one agent) |
| 16 | Gauntlet 5; Outer opening | 10–14 nodes | 26 |
| 23 | Gauntlet 7; Outer complete (12 slots) | 15–20 nodes | 34 |
| 26 | Gauntlet 8 + Council finale; Council Sync | full lattice (21 slots) | 38–42 |
| 30–45 | Endgame (§8): full-roster promotion chase, L50 horizon | — | →50 |

Resonance budget audit: summing §3.1 sources over the median path (8 first-clears, ~110 trash packs, ~30 elites, 16–20 captures, ~60 discoveries, daily Den rests) yields ≈ 41,000 raw Resonance → ≈ 36,900 absorbed at Core flow with Council Sync — landing inside the L38–42 window by construction, with A(40) = 25,900 comfortably cleared and A(50) = 38,300 deliberately out of campaign reach. If content changes move the budget by more than ±10%, retune §3.1 source values, never the `A(L)` curve.

---

## 5. Promotions — the senior-council forms

Each agent has exactly one evolved form: its **senior council** identity. Promotion is permanent, changes silhouette/VFX (authored art, never live-generated — master plan §8.4), upgrades the personality card one register ("seniority"), and completes the ability kit (§3.3).

**Requirements (all four, locked):** agent level ≥ **30** · agent wired at **Core or Inner** · **Gauntlet proof** — clear the agent's proof Gauntlet with that agent in the active party (table below) · pay **3 Checksum Shards + 2,000 Cycles + 25 Synapse Thread** at the Den's Promotion Loom.

Proof-Gauntlet mapping (domain → gate it must prove): Architecture→Planning · QA/Test→Test · Build/Ops→Build · Compliance→Owner Approval · Behavior/Psych→Review · Research→Rollback (post-incident evidence is research) · Security→Security · Release→Release.

### 5.1 The 24 promotions (locked names — authoritative sheets in `04-roster-24-agents.md`)

| Agent | Domain | Promotion | | Agent | Domain | Promotion |
|---|---|---|---|---|---|---|
| AXIOM (starter) | Architecture | **AXIOM PRIME** | | FOREMAN | Build/Ops | **OVERSEER** |
| LATTICE | Architecture | **SUPERSTRUCTURE** | | PIPELINE | Build/Ops | **MAINLINE** |
| FORGEMIND | Architecture | **OMNIFORGE** | | PATCH | Build/Ops | **HOTFIX** |
| WARDEN (hero) | Security | **HIGH WARDEN** | | EMPATH (starter + hero) | Behavior/Psych | **RESONANCE** |
| CIPHER | Security | **CRYPTARCH** | | MIRROR | Behavior/Psych | **PRISM** |
| BREACH | Security | **ZERO-DAY** | | NEURON | Behavior/Psych | **CORTEX** |
| CONTRARIAN (starter) | QA/Test | **DEVIL'S ADVOCATE** | | HAZMAT | Compliance | **QUARANTINE** |
| NITPICK | QA/Test | **SCRUTINY** | | CLAUSE | Compliance | **COVENANT** |
| REDFLAG | QA/Test | **BLACK SWAN** | | AUDITRIX | Compliance | **VERITAS** |
| ORACLE (hero) | Research | **DELPHI** | | COMMANDER | Release | **STRATEGOS** |
| ARCHIVIST | Research | **CODEX** | | VERDICT | Release | **ARBITER** |
| RADAR | Research | **HORIZON** | | POSTMORTEM | Release | **PHOENIX** |

Naming note (intentional, locked): EMPATH's senior form **RESONANCE** shares its name with the network's Resonance resource (§3) — the lore beat is that EMPATH, promoted, *becomes* the embodiment of what the network feels. The UI always renders the promotion in agent-name styling and the resource with its icon; no string is ever ambiguous in context (`12-ui-ux-spec.md` owns the styling rule).

Shard math is intentional: all 24 promotions cost 72 Shards; the campaign supplies ~20 (§6) — promoting the full council is the endgame chase (§8), promoting your favorites (4–6) is the campaign's natural arc.

---

## 6. The Economy

**There are no microtransactions in SYNAPSE. None. No currency packs, no cosmetic store, no paid Foundry rolls. $24.99 buys the whole game (master plan locked decision), and this paragraph is binding on every future content drop.**

### 6.1 Cycles (currency)

| Sources | Typical amount | Sinks | Typical cost |
|---|---|---|---|
| Combat salvage (per pack/elite) | 25 / 90 | Vendor consumables (Restore kits, Bandwidth cells) | 40–150 |
| Gauntlet clear (first / repeat) | 1,200 / 250 | Gear mods (attribute trinkets, 2 slots/agent) | 300–1,500 |
| Den contracts board (3 rotating, zone tasks) | 150–400 | Den furnishings (§7) | 100–2,500 |
| Selling surplus materials | market table | Promotion fee | 2,000 |
| Exploration caches | 50–200 | Field respec (§7.2 — Den respec is free) | 150/edge |
| Negotiation OFFER refunds (failed parley returns 100%) | — | Fast-travel relay activation (one-time each) | 250 |

Faucet/sink balance target: a median player banks 8,000–12,000 Cycles at Council with 4 promotions purchased — comfortable, never trivial. Tuned in `DT_Economy`.

### 6.2 Synapse Thread (wiring resource)

Sources: harvest nodes in all 5 zones (respawn per in-world day, 3–8 each) · every JOIN grants 10 × rarity tier · gauntlet rewards (40 each) · dismantling salvage gear. Sinks: edges (10/20/30 per §2) · promotions (25) · Den crafting recipes. Budget: campaign supplies ~600 Thread; a fully-wired 21-slot lattice costs ~380 — rewiring experimentation is funded, hoarding is unnecessary.

### 6.3 Checksum Shards (rare)

Sources (campaign ~20): 8 Gauntlet first-clears (boss drop, `03-combat-gas-design.md` §7) · 8 hidden world caches (one guaranteed per zone + 3 extra in the Spire, per `01-game-design-document.md` §economy; placement in `05-world-design.md`) · 2 story grants · Foundry rare captures, 1 each (`09-foundry-spec.md`). Endgame remix gauntlets drop 1 per clear (§8). Sinks: Promotions (3 each) · **commissioned-hero unlock rites** (1 each for WARDEN and ORACLE's quest finales, per `01-game-design-document.md`; EMPATH's rite is free if taken as starter) · the four master Den schematics (1 each, §7). Shards are never random drops — every Shard has an address, and `01-game-design-document.md`'s 100%-completable rule holds: one save file can earn every Shard sink.

---

## 7. The Den — buffs, respec, and home

### 7.1 Placed-item network buffs

Furnishing the Den (room system per master plan §4.6; AI room editor when P3's image-gen is wired) feeds the loop: placed items grant small **network buffs**. Four item classes — Trophy (combat stats), Comfort (Resonance gain +%), Infrastructure (economy rates), Memorabilia (parley meters' starting values). Each item grants +1–2%.

**Hard caps (locked):** maximum **+5% to any single stat** from Den items combined, regardless of how many are placed; at most **6 buff-bearing items** active at once (the rest are decoration, which is its own reward). Buffs apply as one aggregated `GE_DenBuffs` rebuilt on any placement change. The Den is flavor-forward, never a mandatory optimization chore.

### 7.2 Respec rules (locked)

- **In the Den: rewiring is free, unlimited, instant.** Experimentation is the point. Loadout presets: 5 named wiring layouts, one-click swap (Den only).
- **In the field:** rewiring costs **150 Cycles per edge changed**, allowed only out of combat, and **never inside an active Gauntlet** (commit to your plan — the Planning boss already taught you why).
- Nodes (agent placement) follow the same rule as edges; moving an agent re-prices its edges.

---

## 8. Endgame Loops (post-Council)

1. **Remix Gauntlets.** All 8 Gauntlets reopen with stacked mutation seeds — deterministic weekly seeds derived from the save (pure single-player, fully offline-capable; no server required). Each remix adds 2–3 modifiers (e.g. *Hot Pipelines Only* — only pipeline damage counts during burn windows; *Flaky Suite* — HEISENBUG's test cases re-roll twice). Reward: 1 Checksum Shard + 300 Resonance × modifier count. This funds the full-roster promotion chase (§5.1).
2. **Foundry rares.** The telemetry-driven, validation-receipted forged agents per `09-foundry-spec.md` spawn as discoverable rares with their proof cards (master plan §4.7) — each is a fresh negotiation (`02-negotiation-system.md`) and a Shard on capture.
3. **Network mastery challenges.** Authored constraint fights (Den terminal): clear a remix with no Depth links; with exactly one domain; with Tension perks only. Rewards: cosmetic node skins + titles.
4. **The L50 horizon.** A(50)=38,300 absorbed Resonance — roughly 12–18h of endgame play for Core agents. Hitting L50 on any agent unlocks its **Apex bark set** and a gold lattice trace. Numbers, not power: L50 grants no new abilities, so the campaign's balance ceiling holds.

---

## 9. The Real-muse Bridge (owner-gated, cosmetic-by-default, opt-in)

The post-game reveal (master plan §4.5, §4.8): wiring an agent into your in-game network can unlock its **real counterpart** in a paired muse install — catch CONTRARIAN, gain the contrarian-reviewer skill in your actual cockpit. Design-level handshake (wire details, schemas, and route specs are owned by `10-observatory-spec.md` and `11-technical-design.md`):

1. **Opt-in.** Settings → muse Bridge, **off by default**. Enabling runs the existing gateway pairing flow; the game functions identically with the bridge off, forever (standalone-game test, master plan §4.8).
2. **Manifest.** On every capture and promotion, the game appends a signed entry to a local **Unlock Manifest**: `{agent_id, council_role, event: caught|promoted, save_id, timestamp, save_hash}`.
3. **Sync.** When paired and online, SYNAPSE posts the manifest to the additive `/v1/game/unlocks` route family (gateway-side, contract-regenerated and frozen per the master plan §1 coupling rule — nothing ported to C++).
4. **Cosmetic tier (auto):** the gateway applies cosmetic unlocks immediately — cockpit badge per caught agent, Observatory node skin, avatar accessory, promotion flair. No owner gate needed; cosmetic-by-default is the contract.
5. **Functional tier (owner-gated):** enabling the agent's *real* council skill (the mapping is the roster's source-role column, `04-roster-24-agents.md`) is staged as a **proposal** in the muse cockpit and activates only on the exact owner phrase **`Yes, with authorization.`** — the existing owner-gate mechanism, ledger-logged, with one-click rollback. The game never flips a real capability by itself.
6. **Integrity.** The gateway validates manifest signatures and save hashes; replayed or edited manifests are rejected and ledgered. Unlocks are idempotent per save.

The player-facing fiction: the Substrate was your muse all along; the Council you rebuilt is the council you now command for real. The bridge is the reward for finishing — never a requirement for starting.

---

## 10. Implementation Map (UE 5.6)

| System | Construct |
|---|---|
| Lattice model | `USynapseNetworkModel` (plain UObject graph: slots, nodes, edges; serialized in `USynapseSaveSubsystem`) |
| Synergy application | `USynapseNetworkSubsystem` recomputes on rewire → applies/removes `GE_Network_Depth`, `GE_Network_Tension_*`, pipeline-unlock tags `Combo.Pipeline.*` to roster ASCs |
| Resonance | `USynapseResonanceSubsystem`: event bus in, per-agent absorbed totals out; level-ups fire `Event.Agent.LevelUp` → ability grants per §3.3 |
| Promotions | DataTable `DT_Promotions` (requirements, costs, promoted kit, mesh/VFX swap ids); executed at the Den Promotion Loom interactable |
| Network screen | `W_NeuralNetwork` (CommonUI), shared node/edge render layer with the Observatory map (`10-observatory-spec.md`) — one widget library, two products |
| Economy | `DT_Economy` (all §6 values), `USynapseWalletComponent` on the player state |
| Den buffs | `USynapseDenSubsystem` → single aggregated `GE_DenBuffs` with the +5%/6-item clamps enforced in code, not content |
| Bridge | `USynapseBridgeSubsystem` (manifest write/sign/sync; feature-flagged; zero references from core game modules so the offline build strips clean) |

### 10.1 Edge-case rules (locked, so nobody has to ask)

- A Crashed or benched agent's wiring synergies stay live (the network is a mind, not a formation); only Pipeline *execution* needs the active 3 (§2.1).
- Removing a node refunds its edges' Thread at 100% in the Den, 50% in the field; the agent returns to Periphery, keeping its absorbed Resonance forever.
- Promotion survives rewiring: once promoted, always promoted, anywhere in the lattice (the requirements gate the rite, not the state).
- Save data (per `11-technical-design.md` save schema): full lattice topology, per-agent absorbed Resonance, promotion flags, Den placement, bridge manifest cursor. The network screen is reconstructable from save alone — no derived state is authoritative.
- New Game+ carries the lattice *shape* (slots unlocked, presets) but resets nodes to Periphery and agents to L1 with a 1.5× Resonance rate — the campaign's wiring lessons replay at speed.

Everything in this document is data-driven through the named DataTables; balance passes never require code changes. Build it, wire it, prove it at the Gate.
