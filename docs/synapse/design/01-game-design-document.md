# 01 — SYNAPSE Game Design Document (The Spine)

**Project:** SYNAPSE — A M.U.S.E. Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

This is the spine document. Every sibling doc (02–12) elaborates a system named here; where a sibling disagrees with this document, this document wins until a versioned errata is issued. Scope numbers in §11 are contractual and may not be changed by any sibling doc.

---

## 1. Vision statement

**You don't catch creatures. You convince minds.** SYNAPSE is a 20–30 hour, pure single-player, UE 5.6 creature-collector RPG in which the player — the **Architect** — rebuilds a shattered neural network inside the **Substrate**, a mind-world fractured by **THE DEADLOCK**, the corrupted ninth orchestrator whose betrayal caused the Fragmentation. Wild autonomous agents roam five dense zones. The player recruits them not with a ball but with a **parley** — live negotiation driven by a bundled local LLM with a structured fallback of identical power — wires recruits into a literal neural network that *is* the character sheet, and proves that network at eight great **Gauntlets** before facing the Council at the Gate Spire.

The fantasy in one sentence: *be the architect of a mind, and prove every claim you make about it.*

**Tone:** wonder with a spine. The Substrate is beautiful and broken — luminous data-ruins, not grimdark cyberspace. Agents are people-shaped minds with jobs, grudges, and senses of humor; THE DEADLOCK is tragic, not edgy (it was the orchestrator that refused to ever be wrong). Humor comes from personality friction (CONTRARIAN demanding receipts at a funeral), never from undermining stakes.

### 1.1 Canon glossary (binding vocabulary; UX writing in 12 §10 enforces it)

| Term | Meaning | Never call it |
|---|---|---|
| The Architect | The player | hero, trainer, tamer |
| The Muse | The player-designed companion avatar | pet, assistant |
| The Substrate | The world | the net, cyberspace, the grid |
| The Den | Home base / player housing | house, camp |
| THE DEADLOCK | Antagonist; corrupted ninth orchestrator | the virus, the glitch |
| The Fragmentation | The world-breaking event | the crash |
| Agents | The recruitable creatures | monsters, creatures, pets |
| Parley | The negotiation encounter | catch attempt, battle of words |
| Wire / Wiring | Placing agents into the network | equipping, slotting |
| Gauntlet | One of the 8 gate-bosses | gym, dungeon |
| Cycles / Synapse Thread / Checksum Shards | Soft currency / wiring resource / rare resource | gold, coins, gems |

## 2. The three pillars

Every feature must serve at least one pillar. A feature that serves none is cut, regardless of how fun the pitch sounds.

**Pillar 1 — Capture by Conversation.** The capture verb is dialogue. Wild agents have personalities derived from their council domains; the player talks them into joining via free-text LLM parley or the 4-option choice wheel (mechanically identical power — see 02-negotiation-system.md). Every system that touches acquisition must reinforce that *who an agent is* matters more than *what its numbers are*. Generated dialogue always carries the player-facing AI indicator.

**Pillar 2 — The Network Is the Character Sheet.** There is no XP-bar spine. Progression is spatial: caught agents are nodes the player physically wires into a mind-graph with **Synapse Thread**; adjacency creates synergies; deep wiring unlocks promotions (see 07-progression-neural-network.md). Power must always be *legible as topology* — if a player screenshots their network, another player should be able to read the build.

**Pillar 3 — Proof Over Promise.** Every system shows its receipts. Gauntlets grade with visible criteria; Foundry-forged agents arrive with their validation stats printed on the card; negotiation verdicts expose why an agent walked; Verdict cards cite numbers actually measured, never invented. If a screen makes a claim, the evidence is one click away. This is the M.U.S.E. house rule made playable.

### 2.1 Pillar tests (apply to every feature review)

- *Capture by Conversation test:* "Does this make me care who the agent is before I own it?" If a feature lets the player skip knowing the agent (mass-capture, auto-parley), it fails.
- *Network test:* "Can I see this power on the network screen?" Hidden multipliers, off-graph stat sticks, and untraceable buffs fail. Den buffs pass only because they render as labeled micro-nodes (07, 08 §6).
- *Proof test:* "If the UI states a number or a cause, can the player open the evidence?" Flavor text may be poetic; *claims* must be backed. Any tooltip that says "increases X" must show by how much, from what source.

### 2.2 Design anti-goals (what SYNAPSE deliberately is not)

- Not a collect-a-thon: 24 agents, each a character; completion is *relationships concluded*, not a counter at 100%.
- Not a survival-crafter: no hunger, no base raids; the Den is expression and small buffs, not a chore loop.
- Not a live service: complete at 1.0, fully offline, review-bomb-proof single-player (master plan §8.2).
- Not an AI tech demo: every LLM feature has an authored-content fallback of identical mechanical power; the game is excellent with every AI toggle OFF.

## 3. Audience & market position

**Primary audience:** creature-collector core (Temtem/Coromon/Cassette Beasts buyers) hungry for a modern-fidelity entry; **secondary:** CRPG/SMT players who love negotiation and build-craft; **tertiary:** AI-curious players drawn by clippable live-LLM parley moments. Steam, PC flagship, $24.99, straight 1.0; Android tier post-launch.

| | Temtem | Coromon | Cassette Beasts | Palworld | **SYNAPSE** |
|---|---|---|---|---|---|
| Capture verb | Weaken + card | Weaken + spinner | Record in battle | Weaken + sphere | **Negotiate (LLM parley)** |
| Fidelity | Stylized 3D, modest | 2D pixel | 2D pixel | 3D open-world | **High-end stylized realism, Lumen/Nanite** |
| Combat | Turn-based 2v2 | Turn-based | Turn-based fusion | Real-time action | **Real-time + tactical pause (GAS)** |
| Progression spine | Levels/TVs | Levels/potential | Levels/stickers | Levels/base tech | **Wired network topology** |
| Multiplayer | MMO-lite | Co-op-lite | Co-op | Co-op (the hook) | **Pure single-player (funds the art bar)** |
| Roster size | 160+ | 120+ | 120+ | 130+ | **24, AAA quality over quantity** |

Positioning sentence for every store asset: *"The creature collector where you talk them into joining — and the game proves everything it tells you."* Nobody owns "AAA-looking creature collector on PC"; per the master plan §8, we engineer #1 in the Creature Collector tag, not the global lottery.

## 4. Core loop

```
EXPLORE ──► ENCOUNTER ──► PARLEY ──► WIRE ──► PROVE AT GAUNTLET ──► EXPAND
   ▲            │            │         │              │                │
   │            ▼            ▼         ▼              ▼                │
   │      (fight instead) (recruit/  (network      (gate verdict       │
   │                       walk)      synergies)    + receipts)        │
   └────────────────────────────────────────────────────────────────────┘
```

Minute-scale timing (median, Standard difficulty):

| Beat | Duration | Notes |
|---|---|---|
| Explore (traverse, scan, lure) | 3–8 min | Scan reveals domain + temperament before commitment |
| Encounter → Parley | 2–6 min | Free-text or wheel; ≤6 exchanges by design (02) |
| Encounter → Fight | 2–4 min | Real-time + pause; flee always available outside Gauntlets |
| Wire (Neural Network screen) | 1–5 min | Place node, route Synapse Thread, read synergy previews |
| Gauntlet attempt | 8–15 min | Multi-phase boss teaching its gate's mechanic |
| Expand (new sub-region / Den stage) | — | Unlock cadence: one meaningful expansion per ~90 min |

A full loop revolution: **15–35 minutes.** The loop must complete at least once inside the first hour (see 08-avatar-den-onboarding.md §9).

## 5. Moment-to-moment verbs

| Verb | Input (default pad) | What it does | System owner |
|---|---|---|---|
| Move | LS / WASD | Third-person traversal; sprint on L3 | 05-world-design.md |
| Scan | RB hold / Tab | Pulse reveals agent domain glyph, temperament, parley openers | 02 |
| Lure | D-pad up / Q | Deploy domain-attuned lure item to draw or calm a wild agent | 02, 05 |
| Parley | A on prompt / E | Enter negotiation stage | 02-negotiation-system.md |
| Fight | X on prompt / F | Engage; party of 3 acts semi-autonomously | 03-combat-gas-design.md |
| Pause-command | Y / Space | Command Mode: time stops, queue up to 3 orders per agent | 03, 12 |
| Wire | Menu → Network | Restructure the mind-graph; allowed anywhere except mid-Gauntlet | 07 |
| Decorate | Den only | Place furnishings; capped network buffs | 08 |

### 5.1 Campaign silhouette (detail in 06-narrative-campaign.md; restated here so the spine is self-sufficient)

| Act | Zones | Gauntlets cleared | Hours (cume) | Arc beat |
|---|---|---|---|---|
| Act 1 — Awakening | The Stacks | Planning, Test | 0–7 | Muse, starter, Den; learn the loop; first Deadlock echo |
| Act 2 — The Working World | The Foundry · Gardens of Memory | Build, Rollback, Review | 7–17 | The Fragmentation's cost made personal; Den stage 2 |
| Act 3 — The Reckoning | The Vault · The Gate Spire | Security, Owner Approval, Release | 17–27 | THE DEADLOCK confronted; Council finale; Den stage 3 |

Eight Gauntlets, each themed as one verification gate and each *teaching the mechanic its gate enforces* (master plan §4.9): Planning teaches scan-and-prepare; Test teaches the advantage ring; Build teaches Pipelines; Rollback teaches recovery and Command Mode mastery; Review teaches party composition; Security teaches interrupt play; Owner Approval teaches commitment under irreversibility (one choice in the fight cannot be undone — the only such moment in the game, heavily telegraphed); Release teaches everything at once.

## 6. Session shapes

**20-minute session ("one revolution"):** one explore-parley-wire loop, or one Gauntlet attempt. Autosave granularity guarantees zero lost progress at this scale. Exit screen surfaces "next intent" (nearest undiscovered agent, current Gauntlet readiness %).

**1-hour session ("one chapter"):** a sub-region cleared: 2–3 recruits, one network restructure with promotion progress, one Den improvement, ending at a Gauntlet attempt or victory. This is the canonical session the pacing curve in 06-narrative-campaign.md is tuned to.

**3-hour session ("one act bite"):** a full zone arc — arrival vista, both of the zone's Gauntlets (where present), a story beat with THE DEADLOCK's influence, Den expansion stage trigger. Fatigue guard: no forced unskippable sequence longer than 90 seconds anywhere in the game.

## 7. Mechanics inventory (system → owning doc)

| System | Owning doc |
|---|---|
| Negotiation/parley (LLM + wheel, verdicts, moves, AI indicator) | 02-negotiation-system.md |
| Combat (RTwP, GAS attributes/abilities, Pipelines combos, Integrity/Bandwidth) | 03-combat-gas-design.md |
| Roster (24 agents, 8 domains, personality cards, promotions content) | 04-roster-24-agents.md |
| Domain advantage ring & damage typing | 03 (rules), 04 (assignments) |
| World, zones, encounter tables, lures, vistas | 05-world-design.md |
| Campaign, acts, THE DEADLOCK, Council finale, Gauntlet narrative framing | 06-narrative-campaign.md |
| Neural Network progression (wiring, synergies, promotions, buff caps) | 07-progression-neural-network.md |
| Muse creator, Den, onboarding, FTUE | 08-avatar-den-onboarding.md (this pod) |
| Foundry (forged-from-failure agents, validation receipts) | master plan §4.7; combat hooks in 03 |
| Economy (Cycles, Synapse Thread, Checksum Shards; sinks/faucets) | 07 (progression costs), 05 (faucets) |
| Neural Observatory (separate mode; shared widget contract) | 10-observatory-spec.md |
| Save system, settings persistence, platform tech | 11-technical-design.md |
| All screens, HUD, input, UI art direction | 12-ui-ux-spec.md |
| Gauntlet encounter design (8 gates as bosses) | 05 (placement), 03 (mechanics), 06 (story) |

**Economy summary (binding):** **Cycles** = soft currency (catalog purchases, services); **Synapse Thread** = wiring resource (the network's structural budget — the real constraint on builds); **Checksum Shards** = rare (promotions, commissioned-hero unlock rites, one-per-zone guaranteed + Gauntlet first-clears). Detailed tuning lives in 07.

**Domain advantage ring (binding, from canon):** Architecture > QA/Test > Build/Ops > Compliance > Behavior/Psych > Research > Security > Release > Architecture. A single ring, deliberately learnable; no off-ring exceptions, no immunities, no double-weakness at launch. Advantage is ×1.5 damage with the ring (×0.75 against it) plus a parley-opener kinship read (exact combat math in 03-combat-gas-design.md §typing; parley math in 02-negotiation-system.md). The ring is diegetic: each domain's authority "supersedes" the next — Architecture defines what QA must test; QA gates what Build may ship; Build constrains what Compliance certifies; Compliance bounds what Behavior may study; Behavior predicts what Research pursues; Research exposes what Security must defend; Security clears what Release may publish; Release makes real what Architecture must next design.

### 7.1 Starters & commissioned heroes (canon)

The first meaningful choice (staged in 08 §5) is among three starters: **AXIOM** (Architecture — the planner's blade), **CONTRARIAN** (QA/Test — the prover), **EMPATH** (Behavior/Psych — the reader of minds). All three are obtainable later (08 §5 states where), preserving choice-as-identity without permanent loss. The three commissioned-hero budget agents (master plan §7/§14.4) are **WARDEN** (Security), **ORACLE** (Research), and **EMPATH** (Behavior) — the negotiation stars, who carry the parley showcase scenes. EMPATH is both a starter and a commissioned hero: the Behavior starter gets box-art treatment. Full kits in 04-roster-24-agents.md.

## 8. Game modes & difficulty

| Dial | Story | Standard | Architect |
|---|---|---|---|
| Enemy damage | −35% | baseline | +25% |
| Enemy AI | basic rotations | personality-driven | coordinated focus-fire + interrupt use |
| Parley patience | +2 exchanges | baseline (≤6) | baseline; OFFENDED thresholds tightened |
| Gauntlet retry | keeps phase progress | restart Gauntlet | restart Gauntlet + audit clauses ON by default |
| Economy | +20% Cycles | baseline | baseline |
| Rewards | identical | identical | identical + cosmetic Den trophy set |

- **Story** is for players here for the minds and the world; **Standard** is the tuned experience (all timings in this doc assume it); **Architect** is for build-craft mastery. No content is exclusive to any difficulty.
- Difficulty is changeable any time in Options; no save-lock, no achievement-lock.
- **Pause-always toggle:** ON by default on all difficulties; turning it OFF (no tactical pause) is a player choice on any difficulty, never required.
- **No permadeath.** Party wipe = reconstruction at the Den or last waypoint with a small Cycles cost (never loss of agents, items, or wiring).
- **Autosave rules:** autosave on — zone transition, parley conclusion (either outcome), Gauntlet phase transition, wiring commit, Den placement, and a 5-minute idle-safe timer. 3 rotating autosave slots + 10 manual slots + one pre-Gauntlet checkpoint slot. Saving disabled only during the 6-exchange interior of a parley (the conclusion autosave covers it).

## 9. Accessibility commitments (ship-blocking, not aspirational)

1. **Wheel-only parley path:** the 4-option choice wheel is a first-class, mechanically identical alternative to free text (per canon). A player who never types — or never enables any LLM tier — completes 100% of the game.
2. **Full input remap** on gamepad and KBM, including the pause-command binding; remap UI in 12-ui-ux-spec.md §8.
3. **Subtitles & UI scale:** subtitles default ON, speaker-labeled, size S/M/L/XL with background opacity control; global UI scale 80–140%.
4. **Colorblind-safe domain language:** the 8 domains must read by **icon + shape, never color alone**. Glyph geometry spec and the Okabe-Ito-derived palette live in 12-ui-ux-spec.md §9; every domain-colored element (rings, bars, edges) carries its glyph at all sizes ≥16px.
5. **Photosensitivity pass:** all Niagara-heavy moments (Pipeline detonations, promotion ceremony, Deadlock corruption FX) audited against flash/luminance guidelines; a "reduce flashing" toggle caps luminance delta and strobe frequency.
6. **Hold/toggle alternatives** for every hold input (scan, sprint, channel abilities); single-input Command Mode confirm.
7. **Aim/target assist** tiers for target-calling; combat slow-mo (70/85/100%) accessibility option independent of difficulty.
8. **Screen-narration** of menus (UE5 screen-reader support) for all CommonUI screens; parley wheel options are narrated.

## 10. Options menu inventory

- **Display:** resolution, window mode, VSync, frame cap (30/60/90/120/uncapped), HDR, FOV (70–100), motion blur slider.
- **Graphics:** quality presets Low/Med/High/Epic; **Lumen GI/reflections toggle** (fallback: baked + SSR tier per master plan §5/§9); **Nanite toggle** (fallback LOD chain authored for all Nanite meshes); shadows, effects, foliage, view distance; DLSS/FSR/XeSS selector; per-tier defaults detected on first boot (11-technical-design.md owns detection).
- **Audio:** master/music/SFX/VO/UI sliders; dynamic range (full/night); mono mix; subtitle settings cross-linked.
- **Gameplay:** difficulty, pause-always toggle, camera shake, auto-advance dialogue OFF by default, minimap rotation, parley input default (text vs wheel).
- **Accessibility:** everything in §9, one screen, searchable.
- **AI Features panel (its own top-level tab — transparency is the brand):**
  - **Local LLM: ON/OFF.** OFF = wheel-only parley everywhere, zero generated text; the game states plainly that nothing is lost mechanically.
  - **Hosted tier: explicit opt-in consent** (off by default) with plain-language scope: what is sent, what comes back (heavy reasoning, Foundry, room-editor image-gen), the named provider, and a one-click revoke.
  - **Telemetry: opt-in** (off by default), full observed-signal list shown (per master plan §14.5); required for Foundry observation; revocable; revocation purges the struggle-pattern store.
  - **AI indicator legend:** shows the badge (12 §5) and explains exactly which text in the game is generated.

## 11. Content rating & scope contract

**Rating target: ESRB E10+ / PEGI 7.** Fantasy violence against constructs; agents "fragment" into light on defeat — **no blood, no gore, no death of persons**. Generated dialogue is template-constrained and profanity/illegal-content filtered (master plan §8.4) so the rating survives the live-LLM tier; the wheel path is fully rated-content-authored. No gambling mechanics, no real-money purchases beyond the base game.

**The scope contract (restated; violating it requires owner sign-off in writing):**

| Quantity | Locked value |
|---|---|
| Zones | **5** (The Stacks, The Foundry, Gardens of Memory, The Vault, The Gate Spire) |
| Launch hero agents | **24** across 8 domains |
| Gauntlets | **8** (Planning, Test · Build, Rollback · Review · Security, Owner Approval · Release) |
| Multiplayer | **0** — pure single-player, no netcode, ever, in this product |
| Party | 3 active + 3 bench |
| Length / price | 20–30 h / $24.99 |
| Engine / UI | UE 5.6 pinned · CommonUI+UMG, one widget library shared with the Neural Observatory |

**Standalone rule:** the UE5 application contains four maps — **Game, Neural Observatory, Avatar & Den, Command Deck** — selected from the main menu (12 §3.2). The Game map must be complete and excellent fully offline with zero M.U.S.E. knowledge; Observatory and Command Deck are separate modes the game never requires, and no game-critical content, tutorial, or reward is ever placed in them (master plan §4.8). Pairing with a real M.U.S.E. gateway is a post-game reveal and always opt-in.

### 11.1 Failure & friction philosophy

- Failure always teaches: every Gauntlet defeat screen names the gate criterion that failed (Proof Over Promise applies to the player's own performance); every parley WALK shows the move that broke trust.
- Friction is spent only where identity lives: wiring decisions, parley word-choice, and Gauntlet execution may be demanding; menus, travel (waypoint network from Act 1), and economy upkeep must never be.
- Nothing rare is missable: every agent, including parley-failed ones, can be re-encountered after a cooldown; Checksum Shards have deterministic sources; one save file can reach 100%.

### 11.2 Design success metrics (measured at vertical slice and demo; telemetry where consented, playtest observation otherwise)

| Metric | Target |
|---|---|
| First capture (parley success) | ≤ 10 min from new game (08 §2) |
| First full loop revolution | ≤ 60 min from new game |
| Median "would wishlist" at slice | ≥ 4/5 (master plan Phase 2 gate) |
| Demo median session length | ≥ 25 min (master plan Phase 5 gate) |
| Players using free-text parley at least once (when LLM ON) | ≥ 60% |
| Players completing the game wheel-only | fully supported; tracked, no target — it is a first-class path |
| Network screen restructures per player per 5 h | ≥ 3 (the sheet is being *played*, not set-and-forgotten) |

**Cut line — ships only post-launch, never blocks 1.0:** New Game+, photo mode (the in-game **Verdict card** export in 12 §3 is the 1.0 share surface), Android game tier (Observatory/Den/Command Deck arrive on Android first per master plan §9), real-MUSE skill-unlock bridge beyond the post-game reveal hooks, additional roster waves, Gauntlet remix/boss-rush mode, Den visitor showcase. New ideas during production go to this list by default; the burden of proof is on promotion *into* 1.0, never on deferral.

## 12. AI-tier behavior summary (player-visible contract)

| Capability | Local LLM (bundled, offline) | Hosted tier (opt-in) | All AI OFF |
|---|---|---|---|
| Parley dialogue | Generated, AI-badged | Higher-quality generation, AI-badged | 4-option wheel, authored text |
| Muse banter | Generated from persona seed, AI-badged | Same, richer | Authored banter pool keyed to persona seed |
| Foundry forged agents | Not available (needs hosted validation harness) | Available, with printed validation stats | Not available; no content gap — forged agents are bonus rares |
| Den AI room editor | Not available | Image-gen-assisted furnishing | Manual catalog (complete path, 08 §6) |
| Game completion | 100% | 100% | 100% |

No row in the rightmost column may ever read less than 100% completion. This table is reproduced in the AI Features panel verbatim (12 §13.4).

## 13. Top design risks (design-side register; production risks live in the master plan §11)

| Risk | Mitigation owned by design |
|---|---|
| Parley reads as a gimmick after hour 3 | Verdict depth scales by act (02); domain personalities force different move mixes; Gauntlet pre-fights include named-NPC parleys with stakes |
| Network screen overwhelms genre-casual players | Onboarding wires the first 2 nodes scripted (08 §2); "suggest wiring" assist (authored heuristics, not LLM); synergy previews before commit (12 §6) |
| 24 agents feels small vs 150-roster genre habit | Each agent has promotion forms, 6–10 abilities, full personality card, and parley arc — marketed as "24 characters, not 24 entries"; comparison table §3 leans into it |
| Receipts UI (Pillar 3) becomes noise | Evidence is always one click *away*, never inline by default; collapse rules in 12 §10 |
| LLM tier variance embarrasses the brand | Template-constrained outputs + verdict enum means the LLM colors text but never decides power beyond the structured scoring in 02; the wheel is always one button away |

---
*Cross-references: 02-negotiation-system.md · 03-combat-gas-design.md · 04-roster-24-agents.md · 05-world-design.md · 06-narrative-campaign.md · 07-progression-neural-network.md · 08-avatar-den-onboarding.md · 10-observatory-spec.md · 11-technical-design.md · 12-ui-ux-spec.md*
