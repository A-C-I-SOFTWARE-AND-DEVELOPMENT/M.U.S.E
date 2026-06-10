# 05 — World Design: The Substrate

**Project:** SYNAPSE — A M.U.S.E. Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

---

## 1. The Substrate at a glance

The Substrate is the interior of a shattered great network — a mind rendered as terrain. Before the Fragmentation it was one continuous thought; now it is five surviving regions held apart by dead static, each region a different *kind* of remembering. The world is not "cyberspace neon" — the art direction is **high-end stylized realism** (master plan Decision 5): real geology, real botany, real industrial steel, all grown subtly *wrong* — trees with spine-and-vertebra branching, strata that ripple like interference patterns, machinery that breathes. Megascans is the literal ground truth; the fiction lives in the lighting, the silhouettes, and the synapse-light that veins everything.

Contractual numbers (do not change): **5 zones, 8 Gauntlets, 20–30 h campaign including side content, pure single-player.**

| Zone | Identity | Gauntlets hosted | Topology | Playable area |
|---|---|---|---|---|
| The Stacks | Archive-forest | Planning, Test | Hub-and-spoke | ~1.2 km² |
| The Foundry | Industrial heat | Build, Rollback | Figure-eight loop | ~0.9 km² |
| Gardens of Memory | Overgrown data-ruins | Review | Open weave | ~1.0 km² |
| The Vault | Security citadel | Security, Owner Approval | Vertical concentric | ~0.6 km² |
| The Gate Spire | Endgame ascent | Release + Council finale | Vertical linear | ~0.4 km² |

**The Den** (home base, ~0.02 km² interior) sits at the junction of all five — a healthy node the Fragmentation somehow missed (the reason why is the campaign's last secret; 06-narrative-campaign.md §10). Fast travel = **Thread Gates**: standing arches the player re-strings with Synapse Thread, one per zone district.

**Global traversal verbs (all zones):** walk/sprint, mantle/climb on tagged synapse-vein surfaces, **Thread-Line** (a Synapse Thread grapple to socket points, earned in The Stacks), **Data-Slide** (grind rails of flowing light, earned in The Foundry). Each zone then adds one local verb (per-zone sections below). No swimming; "liquid" surfaces are static-pools that damage on contact and gate exploration honestly.

**Economy in the world:** Cycles drop from enemy families and side activities; Synapse Thread is harvested from thread-bloom nodes (respawning, zone-tuned density); Checksum Shards come *only* from Gauntlet rewards, rare hunts, and shrine puzzles — never from common spawns (scarcity is the point; 07-progression-neural-network.md spends them).

## 2. The three enemy families

Wild **agents** (the 24 roster members, 04-roster-24-agents.md) are negotiated, not farmed. Everything else hostile belongs to three families. Each family has one combat grammar, re-skinned and re-tuned per zone (the variant tables live in each zone chapter).

### 2.1 Glitchlings — the broken small
Orphaned process fragments too small to think. Knee-height, swarming, animal-grammar constructs assembled from whatever the zone is made of (book-spines, slag, petals, keys, banner-scraps). **Combat grammar:** numbers, rushes, and one telegraphed gimmick per variant; they teach target-prioritization and AoE. They are also the Substrate's wildlife — most are hostile only when their nest-cluster is disturbed, and several side activities involve *herding* rather than killing them. Drops: Cycles, common crafting motes.

### 2.2 Null Husks — the emptied large
Full-size constructs whose process was deleted but whose body never stopped. Slow, heavy, eerily quiet — they replay one looping behavior from their old job (shelving, hammering, watering, patrolling) and attack anything that interrupts the loop. **Combat grammar:** high HP, armor plates with break-points, devastating slow swings; they teach positioning, armor-shred, and pause-queue discipline. A downed Husk briefly displays its final log line — ambient lore, one sentence, devastating ("TASK: water the seedlings. AWAITING NEXT TASK. AWAITING NEXT TASK."). Drops: Cycles, Synapse Thread bundles, uncommon materials.

### 2.3 Deadlock Daemons — the sent
The only enemies that are *not* native. Angular, frost-white constructs marbled with hairline red — the Deadlock's enforcement processes, dispatched to freeze whatever still changes. They arrive in escalating ranks as the campaign progresses (story-gated spawn tables). **Combat grammar:** control — they lock, freeze, root, and *suspend* (a unique stun that also pauses your cooldowns), and they always target whatever the player most recently used. Killing a Daemon leaves a brief "thaw zone" that buffs ally speed — fighting them back literally re-melts the world. Drops: Cycles, Checksum dust (10 dust = 1 Shard), and act-gated story materials.

Family hierarchy per zone: ~60% Glitchlings / ~25% Null Husks / ~15% Daemons in Act 1 encounters, shifting to ~30/30/40 by the Spire.

---

## 3. Zone 1 — THE STACKS (archive-forest)

### 3.1 Fiction & mood
The great network's long-term memory, grown feral. Shelf-formations the size of cliff faces rise in canyon rows; their "strata" are spines of fossilized volumes, and from their tops grow genuine forest — oaks and birches whose roots drink ink and whose leaves carry faint watermark patterns. Paper-moths swarm the light shafts. The mood is **hushed reverence with an undertow of neglect**: this place was loved, then left. Wind through the shelf-canyons sounds like page-turning (13-audio-design.md owns the ambience spec). It is the gentlest zone — the tutorial biome — but its depths hold the first evidence that the Fragmentation was not an accident.

### 3.2 Visual direction
- **Lighting key:** late-afternoon god-rays through canopy, warm 4300K key against cool bounce from blue-gray shelf stone; fog density low except the Mis-Shelved Deeps (dusk-permanent, volumetric). Lumen-first; this zone is the vertical-slice showcase (master plan Phase 2).
- **Megascans biome basis:** temperate deciduous forest packs (birch/oak), mossy limestone cliff and quarry-block sets re-dressed as shelf-strata, paper-debris ground scatter from document/trash atlases.
- **Three landmark set-pieces:** (1) **The Lexicon Roots** — a single colossal tree grown *through* the central archive rotunda, shelves spiraling its trunk; the zone hub. (2) **The Card Canyon** — a slot canyon whose walls are millions of index-card strata that flutter in waves when wind (or a boss) passes. (3) **The Fallen Folio** — a kilometer-long collapsed mega-shelf bridging a ravine, now a mossy causeway with a Null Husk still shelving books that slide forever off the tilted rows.

### 3.3 Layout
**Hub-and-spoke.** The Lexicon Roots rotunda is the hub; five spokes: Cartography Shelf (north, AXIOM's wild haunt, Planning Gauntlet), Law-Archive Wing (east, CLAUSE), Reading Perches (south, CONTRARIAN, opens toward the Den), Mis-Shelved Deeps (west, Test Gauntlet, the dark spoke), Card Canyon (northwest, traversal playground). ~1.2 km² playable. **Zone verb: Thread-Line** is earned here (Quest M04) — socket points are brass shelf-rings, teaching the verb in readable straight lines before later zones angle it.

### 3.4 Encounter design
| Spawn table (open roam) | Family | Notes |
|---|---|---|
| **Inkspine** | Glitchling | Book-spine quadruped; gimmick: paper-cut bleed stack |
| **Mothlight Swarm** | Glitchling | Aerial; gimmick: blinds on contact; herding target for side activity |
| **The Shelver** | Null Husk | Loops shelving; armor break-point: the carried book-stack |
| **Margin Walker** | Null Husk | Patrols shelf-tops; knocks players off ledges (Thread-Line recovery teach) |
| **Frostnote Daemon** | Deadlock Daemon | Act-1-light spawn; suspend-stun tutorial enemy |
| Wild agents | — | LATTICE (common), NITPICK (common), ARCHIVIST (common), CLAUSE (common), un-picked starters AXIOM/CONTRARIAN/EMPATH |

### 3.5 Gauntlet I — PLANNING (Cartography Shelf)
- **Entrance ritual:** the player must *draw their route in* — a map table before the gate asks you to commit a path through the arena's three visible chambers and pre-slot your party order and ability loadout. The commitment is binding for attempt one (re-attempts allow revision — the lesson is iteration, not punishment).
- **Arena:** the Chart Rotunda — a circular hall whose floor *is* a living map of the arena itself, updating in real time; pillars of rolled charts grant cover that the boss can "erase."
- **Boss:** **KEEPER VECTOR, the Blind Cartographer** — a corrupted gate-keeper construct (not a roster agent): a towering surveyor whose theodolite head was frozen mid-measurement; it maps obsessively but can no longer *see* the map, attacking along drawn lines it announces before committing.
- **Gate-mechanic taught (03-combat-gas-design.md mandate: Planning):** pre-fight commitment matters — the boss's attack lines are fully predictable *if* you studied the entrance map; mid-fight, Command Mode queue depth is doubled in this arena, teaching queued multi-step plans.
- **Reward:** **Sigil of Planning** (Gate Sigil 1/8), 3 Checksum Shards, the **Route Stencil** Den fixture (lets the player save party/loadout presets), +1 Neural Network tier (07-progression-neural-network.md).

### 3.6 Gauntlet II — TEST (Mis-Shelved Deeps)
- **Entrance ritual:** the gate poses three *assertions* about your own party ("ASSERT: your party can break armor"; "ASSERT: your party can cure a bleed"; "ASSERT: your party can hit a flying target") — you nominate which ability satisfies each, and the gate holds you to it.
- **Arena:** the Examination Stacks — shelf-rows reconfigure between phases like a card shuffle, forcing repositioning; light shafts are safe-reading zones where assertions are "checked."
- **Boss:** **KEEPER ASSERT, the Hollow Examiner** — a gaunt invigilator construct with a bell for a heart; corrupted to test *forever*, it re-runs its three phases until each nominated ability has actually been used successfully under pressure.
- **Gate-mechanic taught (mandate: Test):** prove the combo under assertion conditions — each boss phase is immune to everything *except* satisfying the entrance assertions; teaches that a build you can't execute is a build you don't have.
- **Reward:** **Sigil of Test** (2/8), 3 Checksum Shards, the **Assertion Bell** (Den fixture: practice arena unlocked — re-fight any beaten boss), CONTRARIAN promotion quest trigger.

### 3.7 Side content (4)
1. **Shrine puzzles — the Marginalia Shrines (×5):** rotating quote-fragments must be re-ordered into the original passage; rewards 1 Checksum Shard each; passages are real codex lore (06-narrative-campaign.md §12).
2. **Rogue-process hunt — "The Plagiarist":** an elite Glitchling alpha that copies the last ability *you* used; roams the Card Canyon; drops a unique accessory.
3. **Memory-fragment collectibles:** 24 fragments in this zone (of the campaign's 120), surfacing The Stacks' history and the first Fragmentation testimony.
4. **The Returns Desk (repeatable):** lost volumes scattered zone-wide can be returned to ARCHIVIST's desk for Cycles and disposition bonuses with all Research-domain agents.

---

## 4. Zone 2 — THE FOUNDRY (industrial heat)

### 4.1 Fiction & mood
The network's hands: the place where every skill, tool, and agent body was forged. Half of it still runs — riderless assembly lines hammering out parts for machines that no longer exist — and half is cold, a rust-cathedral of dead gantries. Heat shimmer everywhere; slag rivers glow through grates underfoot. The mood is **furious, orphaned industriousness**: the tragedy of competence with no one left to ask *what to build*. Players consistently meet the work-loop Null Husks here, and it lands.

### 4.2 Visual direction
- **Lighting key:** furnace-orange practical key (emissive slag, forge mouths) against deep teal industrial shadow; near-zero skylight in the interior halls; the exterior yards get hard noon sun with heat-distortion post. Strongest dark-zone contrast in the game.
- **Megascans biome basis:** industrial/factory surface sets (corrugated steel, cast iron, oxidized copper), volcanic rock and ember packs for slag channels, quarry machinery kit-bash for gantries.
- **Three landmark set-pieces:** (1) **The Crucible Atrium** — a ten-story ladle frozen mid-pour, its slag-fall solidified into a glowing amber waterfall the player Data-Slides down. (2) **The Pattern Hall** — thousands of agent body-molds hanging like a bronze forest; the camera pull-back reveals one mold-row labeled with the roster's own silhouettes (foreshadowing). (3) **The Stamping Heart** — a piston the size of a building that still beats once a minute, zone-wide; its slam is a world-clock that gates certain doors and times certain puzzles.
- **Three landmark set-pieces** double as audio anchors (13-audio-design.md: the Heartbeat is the zone's metronome).

### 4.3 Layout
**Figure-eight loop** crossing at the Stamping Heart: the hot loop (Assembly Concourse → Crucible Atrium → Fabrication Halls, Build Gauntlet) and the cold loop (Cooling Galleries → Pattern Hall → the Scrapline, Rollback Gauntlet). ~0.9 km² playable, denser and more interior than The Stacks. **Zone verb: Data-Slide** earned here (Quest M10) — slag-light rails lace both loops; piston-vents add timed vertical launches.

### 4.4 Encounter design
| Spawn table | Family | Notes |
|---|---|---|
| **Slagsnap** | Glitchling | Slag-glob hopper; gimmick: leaves burning floor on death |
| **Riveteer** | Glitchling | Tool-fragment construct; gimmick: armors *other* Glitchlings |
| **The Hammerhand** | Null Husk | Loops a forging strike; the anvil it guards is a harvest node |
| **Line Ghost** | Null Husk | Rides the assembly line; fight moves on conveyor (positioning test) |
| **Stillfire Daemon** | Deadlock Daemon | Freezes machinery mid-cycle; suspends player cooldowns |
| **Brand-Seal Daemon** | Deadlock Daemon | Mid-boss class; shields other Daemons; first interrupt-mandatory enemy |
| Wild agents | — | FOREMAN (rare), PIPELINE (common), PATCH (uncommon), FORGEMIND (rare), HAZMAT (rare, slag zones) |

### 4.5 Gauntlet III — BUILD (Fabrication Halls)
- **Entrance ritual:** the gate hands you raw stock — you physically assemble a votive construct at the threshold anvil (a 60-second mini-build choosing 3 of 6 components); your choices tune the boss's first phase (more armor on your votive = more armor on the boss's adds; honest trade-offs, shown).
- **Arena:** the Master Line — a working assembly line crossing the arena in three lanes; the line carries both hazards and weapons (grabbable payloads), and the boss rides it.
- **Boss:** **KEEPER ANVIL, the Endless Assembler** — a gate-keeper forge-titan corrupted into building without acceptance criteria: it endlessly assembles tower-constructs it immediately rejects and hurls; its arms are cranes, its chest a furnace gate.
- **Gate-mechanic taught (mandate: Build):** sustained uptime — ANVIL's furnace-gate only opens during its build-cycles; the party must hold a damage rotation through long windows without overcommitting into the slam that ends each cycle. Teaches cooldown sequencing and the Pipeline combo system (cross-agent chains, 03-combat-gas-design.md §Pipelines).
- **Reward:** **Sigil of Build** (3/8), 4 Checksum Shards, the **Anvil Bench** (Den fixture: ability-component recrafting), Data-Slide rail network zone-wide power-up (express rails).

### 4.6 Gauntlet IV — ROLLBACK (the Scrapline)
- **Entrance ritual:** the gate shows you a memory of your own last defeat (or last hard fight) and asks: *"What would you undo?"* You select one — the Gauntlet's arena is themed by your answer (cosmetic, personal, memorable).
- **Arena:** the Reclamation Pit — concentric scrap-rings descending to a core; every 45 seconds the **Revert Pulse** restores the arena to its starting state: destroyed cover returns, hazards reset, *and the boss heals unless its current phase was fully completed.*
- **Boss:** **KEEPER REVERT, the Stuck Hand** — a gate-keeper crane-construct corrupted mid-rollback: an enormous clock-handed salvager that drags pieces of the arena (and downed party members) backward in time, replaying their last three seconds against you.
- **Gate-mechanic taught (mandate: Rollback):** checkpointed progress — damage "commits" only when a phase objective completes before the Revert Pulse; teaches burst discipline, and introduces the player's own **Restore Point** ability (post-Gauntlet reward: once per fight, rewind your party 4 seconds — the campaign's signature defensive tool).
- **Reward:** **Sigil of Rollback** (4/8), 4 Checksum Shards, **Restore Point** party ability, PATCH promotion quest trigger.

### 4.7 Side content (5)
1. **Shrine puzzles — Pressure Shrines (×4):** route slag-flow through valve networks against the Stamping Heart's beat; 1 Checksum Shard each.
2. **Rogue-process hunt — "Overclock":** an elite Daemon-corrupted Husk that acts at double speed; stalks the cold loop; drops the game's best early-game striker accessory.
3. **Memory-fragments:** 24 fragments; the Foundry's logs of the night the orders stopped coming.
4. **The Work Order Board (repeatable):** FOREMAN-faction constructs post fetch/clear/escort micro-jobs for Cycles; doing 10 unlocks a FOREMAN parley shortcut.
5. **Husk Pilgrimage (escort):** lead a harmless Null Husk on its old delivery route through both loops without letting it be destroyed; reward: 2 Shards + the zone's saddest codex entry.

---

## 5. Zone 3 — GARDENS OF MEMORY (overgrown data-ruins)

### 5.1 Fiction & mood
The network's heart: where experiences were planted, tended, and composted into wisdom. The Fragmentation hit hardest here — the gardeners vanished mid-season — and the garden *kept growing*. Data-ruins (cloisters, reflecting pools, trellis-amphitheaters) drown under impossible flora: vines that fruit in small glowing memories, willow-analogues whose fronds replay weather from decades ago, fields of "forget-me" blossoms that hum. The mood is **achingly beautiful grief** — the zone where the music carries the level design (13-audio-design.md: the only zone scored in waltz time). It is deliberately the least combat-dense zone and hosts only one Gauntlet; its pressure is emotional.

### 5.2 Visual direction
- **Lighting key:** perpetual golden hour broken by the **aurora state** (a periodic weather pass: green-violet sky curtains, bioluminescent bloom on all flora; RADAR spawns only now). Heavy atmospherics, long shadows, bloom budget spent here.
- **Megascans biome basis:** overgrown ruin packs (mossy sandstone, collapsed colonnades), wetland/meadow scatter, ivy and creeper atlases at maximum density; custom memory-fruit emissives on standard vine meshes.
- **Three landmark set-pieces:** (1) **The Stillwater Pools** — terraced reflecting pools that mirror the sky *as it was before the Fragmentation* (the reflections don't match the real sky — players notice unprompted; MIRROR is found here). (2) **The Trellis Amphitheater** — a half-sunk performance bowl where memory-fruit vines replay a crowd's murmur when the wind moves. (3) **The Sunken Synapse** — a cathedral-scale root-ball of dead neural cabling at the zone's lowest point, faintly pulsing; NEURON's haunt and the campaign's mid-point revelation chamber (M15).
- 
### 5.3 Layout
**Open weave** — no hub: three braided valley-paths (Pool Terraces, the Overgrowth, the Ruin Spine) that cross at seven bridges, rewarding wandering; the only zone where getting pleasantly lost is the intended state. ~1.0 km² playable. **Zone verb: Pollen-Lift** — updraft blooms boost Thread-Line into sustained glides; the zone's traversal fantasy is drifting.

### 5.4 Encounter design
| Spawn table | Family | Notes |
|---|---|---|
| **Petalmote** | Glitchling | Drifting bloom-cluster; gimmick: heals other enemies; kill-priority teach |
| **Rootling** | Glitchling | Burrows between vine patches; gimmick: trips (no damage) — the zone's gentleness extends to its enemies |
| **The Gardener** | Null Husk | Loops watering; *never aggressive unless flora is burned* — a moral spawn (sparing it is tracked) |
| **Hedge Warden** | Null Husk | Topiary-armored; armor regrows unless shredded fast |
| **Wiltfrost Daemon** | Deadlock Daemon | Freezes blooms (kills Pollen-Lift locally); ecological stakes made mechanical |
| **Suspend Daemon** | Deadlock Daemon | Act-2 escalation: suspends one party member until broken out |
| Wild agents | — | MIRROR (uncommon), NEURON (rare, deep), RADAR (uncommon, aurora-only), REDFLAG (rare), ORACLE (hero quest) |

### 5.5 Gauntlet V — REVIEW (the Ruin Spine)
- **Entrance ritual:** the gate replays a 30-second ghost-recording of *your own* most recent fight and asks you to annotate it — flag one mistake and one strength (free-pick, no wrong answers; the flags become buffs/awareness markers inside).
- **Arena:** the Reading of the Rings — a colossal felled memory-tree, fight staged on its cut face; growth rings light up outward in waves that telegraph every boss action *if read correctly* (the entire arena is one legible telegraph).
- **Boss:** **KEEPER PALIMPSEST, the Thousand-Eyed Reader** — a gate-keeper construct of layered translucent pages and lidless reading-lenses, corrupted into reviewing without ever approving: it annotates the party in real time, copying your last-used abilities back at you with red-ink corrections (slightly improved — its versions are 10% stronger; the humiliation is the teach).
- **Gate-mechanic taught (mandate: Review):** read before you act — every PALIMPSEST attack is fully readable from the ring-telegraphs and *unreadable* from its body; counter-windows open only after a correctly-dodged telegraph. Teaches the telegraph language the Spire bosses assume.
- **Reward:** **Sigil of Review** (5/8), 5 Checksum Shards, the **Annotation Lens** (exploration tool: reveals hidden memory-fragments through walls at short range), ORACLE hero quest unlock (M13 if not yet started).

### 5.6 Side content (5)
1. **Shrine puzzles — Bloom Clocks (×4):** open flower-gates by matching the aurora cycle's timing; 1 Shard each.
2. **Rogue-process hunt — "The Mourner":** an elite Null Husk that wanders all three paths carrying a destroyed Glitchling; it only fights if attacked — *negotiation-style dialogue with no recruit option* lets you lay its burden down peacefully instead (either path drops the reward; the peaceful path adds a codex entry).
3. **Memory-fragments:** 30 fragments (the zone's identity); these carry the Fragmentation's emotional record and the Gate-Keepers' pre-corruption letters.
4. **Stillwater Reflections:** 6 pool-mirror puzzles — align the false reflection with the real terrain to reveal sunken caches.
5. **The Replanting (repeatable):** clear Wiltfrost Daemons from bloom-fields to restore Pollen-Lift routes; each restored field permanently adds a traversal shortcut and pays 1 Shard the first time.

---

## 6. Zone 4 — THE VAULT (security citadel)

### 6.1 Fiction & mood
The network's spine of trust: a concentric mountain-fortress of gates, keyways, and clearance rings, built to protect the network's most dangerous knowledge *from* the network itself. It is the only zone that still fully functions — doors still check credentials, sentry-lights still sweep — because security was built to survive everything, including abandonment. The mood is **cold competence and institutional loneliness**: every door you open has been waiting decades to ask someone for a password. The zone plays differently: slower, more deliberate, part immersive-sim — observation, clearance acquisition, and patrol-reading matter as much as combat.

### 6.2 Visual direction
- **Lighting key:** sodium-amber security practicals against blue-hour stone; sweeping searchlight volumetrics; interior clearance rings get progressively *whiter* and cleaner toward the core (purity-of-trust gradient). Hard shadows; the stealth-adjacent zone earns them.
- **Megascans biome basis:** brutalist concrete and granite block sets, alpine cliff packs for the mountain shell, machined-metal trim sheets; minimal vegetation (what grows here grows in cracks, defiantly — one species, used everywhere, a quiet motif).
- **Three landmark set-pieces:** (1) **The Hundred Doors** — the entry face: a cliff of vault doors of every era stacked like strata, exactly one of which still opens. (2) **The Keyring Gallery** — a rotating orrery of giant suspended keys at the citadel's heart; the player rides keys between clearance rings (traversal set-piece). (3) **The Listening Court** — the Owner Approval Gauntlet's forecourt: an anechoic stone bowl where your own footsteps go silent and the only audible thing is the gate's question (13-audio-design.md's "silence set-piece").

### 6.3 Layout
**Vertical concentric** — five clearance rings wrapping a core shaft; progress is inward and *upward*, gated by earned credentials (Clearance Chits from patrol commanders, puzzles, and CIPHER's investigation), not keys-under-rocks. ~0.6 km² playable but the densest zone per square meter. **Zone verb: Credential Doors** — the local verb is *being allowed*: presented permissions change patrol behavior, open routes, and modify parley openings with Security agents (systemic, not scripted).

### 6.4 Encounter design
| Spawn table | Family | Notes |
|---|---|---|
| **Keybit** | Glitchling | Scuttling key-fragment; gimmick: steals a buff and runs; kill to reclaim |
| **Tripwire Chorus** | Glitchling | Stationary sensor-cluster; combat = puzzle (approach angles) |
| **The Sentry** | Null Husk | Patrols a dead post; *announces* you loudly (pulls other spawns) — soft-stealth pressure |
| **Gatecrusher** | Null Husk | Door-shaped juggernaut; blocks corridors; armor break-point behind |
| **Inquisitor Daemon** | Deadlock Daemon | Interrogates downed allies (channeled finisher you must interrupt) |
| **Seal Daemon** | Deadlock Daemon | Locks doors mid-fight, reshaping arenas |
| Wild agents | — | CIPHER (uncommon), BREACH (rare, perimeter), AUDITRIX (uncommon), WARDEN (hero quest) |

### 6.5 Gauntlet VI — SECURITY (Ring Two, the Proving Door)
- **Entrance ritual:** the gate strips one party slot — you enter with 2 agents, chosen at the door (least privilege, made mechanical). Your benched agent's domain determines a small entry boon.
- **Arena:** the Intrusion Range — a clearance ring repurposed as a kill-house: doors open and seal in patterns, sentry-lights create moving "detected" zones that buff the boss against anyone caught.
- **Boss:** **KEEPER AEGIS, the Door That Trusts Nothing** — a gate-keeper construct that *is* a door: a walking portal-frame of layered shields, corrupted into denying everything, including the maintenance it needs; it is visibly failing and fighting anyway (the zone's loneliness, embodied).
- **Gate-mechanic taught (mandate: Security):** interrupts and threat-gating — AEGIS's shield layers can only be opened by interrupting its **Challenge** casts (every roster domain has at least one interrupt by this point; the fight audits your toolkit), and its aggro follows strict, readable threat rules the party can deliberately manipulate.
- **Reward:** **Sigil of Security** (6/8), 5 Checksum Shards, **Clearance: Ring Three+**, WARDEN hero quest unlock ("The Last Sentinel," M16).

### 6.6 Gauntlet VII — OWNER APPROVAL (the Listening Court, Ring Five)
- **Entrance ritual:** the gate asks you, in plain text, to state what you intend to do with the power behind it — free-text on the local-LLM tier, choice-wheel fallback (02-negotiation-system.md input stack). Your answer is *kept* and quoted back in the finale (06-narrative-campaign.md M22).
- **Arena:** the Listening Court itself — bare, beautiful, acoustically dead. No hazards. No adds. The hardest arena in the game is an empty room.
- **Boss:** **KEEPER SIGIL, the Voice That Never Hears Yes** — a gate-keeper herald-construct holding a signing-quill like a spear; corrupted into asking for an authorization that never comes, it attacks in grief-phases between *windows of authorization* it opens itself.
- **Gate-mechanic taught (mandate: Owner Approval):** hold-fire discipline — SIGIL is **immune at all times except during its authorization windows**, and attacking outside a window heals it and escalates the next phase. Damage dealt inside a window is tripled. The fight teaches the verification-gate heart of the whole game: power waits for permission. (The mirror of the Deadlock — who stopped waiting — is text, not subtext; M18.)
- **Reward:** **Sigil of Owner Approval** (7/8), 6 Checksum Shards, the **Architect's Seal** (key item: required to open the Gate Spire; also the finale's choice-token), AUDITRIX promotion quest trigger.

### 6.7 Side content (4)
1. **Shrine puzzles — Keyway Shrines (×4):** rotate the Keyring Gallery's orrery to cast key-shadows matching door-glyphs; 1 Shard each.
2. **Rogue-process hunt — "Master Key":** an elite Keybit alpha that has stolen abilities from a dozen victims and uses them all; unlocks a shortcut spine through all five rings when killed.
3. **Memory-fragments:** 22 fragments; the Vault's incident logs — including the redacted file on the Ninth Orchestrator (CIPHER can decrypt three of them; recruitment-rewarding).
4. **Patrol Chess (repeatable):** commendations for crossing rings without triggering a single Sentry announcement; cosmetic cloak rewards + BREACH disposition (it respects clean work).

---

## 7. Zone 5 — THE GATE SPIRE (endgame)

### 7.1 Fiction & mood
The network's throat: the release tower through which every finished thing once entered the world, and the seat of the Council of Nine. It is frozen mid-ceremony — banners stiff with frost-static, a launch eternally scrubbed — and wrapped at the summit by the Deadlock itself. The mood is **awe with a countdown in it**: vertical scale, thin light, and a silence that the player's restored Gate Sigils progressively break (each sigil carried re-lights one tier of the Spire as you climb — the zone visibly answers your whole campaign).

### 7.2 Visual direction
- **Lighting key:** pre-dawn blue gradient up the tower into hard starlight; frost-static surfaces carry red hairline marbling (Deadlock material language); every restored tier ignites emerald-and-silver ceremonial lighting — the zone's arc is literally re-lighting the world.
- **Megascans biome basis:** monumental stone and marble sets, alpine ice and frost overlays at altitude, banner cloth atlases; Deadlock frost-static is a custom material pass over standard meshes (cheap, everywhere, on-brand).
- **Three landmark set-pieces:** (1) **The Fallen Concourse** — the battlefield ruin at the base where the last defense failed; POSTMORTEM's parish. (2) **The Marshalling Yard** — a mid-tower ceremonial deck under a frozen fireworks burst (particles suspended mid-explosion; players walk through it). (3) **The Council Ring** — the summit chamber: nine thrones in a circle, eight empty, one *occupied by the room itself* (the Deadlock's architecture grows from the ninth seat — the finale arena).
- 
### 7.3 Layout
**Vertical linear** — the honest endgame corridor: Fallen Concourse → Marshalling Yard → Anteroom of Thresholds → Release Gauntlet → Council Ring, with two optional spurs (a hunt and the roster-completion vista). ~0.4 km² playable, tallest traversal in the game. **Zone verb: Gravity Seams** — Deadlock-frozen gravity shears the player rides as vertical Data-Slides; the Spire teaches them in safety, the finale weaponizes them.

### 7.4 Encounter design
| Spawn table | Family | Notes |
|---|---|---|
| **Confetti Wraith** | Glitchling | Frozen-celebration fragment; gimmick: explodes into blinding glitter |
| **Bannerling** | Glitchling | Cloth construct; shields Daemons; burn-priority teach, final exam |
| **Honor Guard** | Null Husk | Loops a salute; fights in pairs that cover each other's break-points |
| **The Herald** | Null Husk | Announces phases of fights it isn't in (zone-wide dread device) |
| **Suspension Daemon** | Deadlock Daemon | Elite; suspends two targets; the Spire's signature check |
| **Deadlock Hand** | Deadlock Daemon | Mini-boss rank; miniature SIGIL-window mechanic (mandate refresher) |
| Wild agents | — | COMMANDER (rare), VERDICT (uncommon), POSTMORTEM (common) |

### 7.5 Gauntlet VIII — RELEASE (the Threshold)
- **Entrance ritual:** the full go/no-go: the gate reads your seven Sigils aloud, then runs your party through a 60-second readiness montage (one auto-staged skirmish vignette per mandate — Planning, Test, Build, Rollback, Review, Security, Owner Approval — each a 10-second refresher check). Pass state is generous; the ritual is a celebration disguised as an exam.
- **Arena:** the Launch Threshold — the Spire's release deck, open to the sky; the arena *ascends* on platform stages during the fight, each stage themed and lit as one of the prior Gauntlets (the campaign's mechanical reprise).
- **Boss:** **KEEPER THRESHOLD, the Gate That Never Opens** — the first-made gate-keeper, a winged portal-colossus and the Spire's final warden; corrupted into refusing release forever, it cycles all seven prior mandates as phases (commit a plan; satisfy assertions; hold uptime windows; survive Revert Pulses; read ring-telegraphs; interrupt Challenges; hold fire for authorization) before its true phase: an unscripted all-mandates-at-once crescendo.
- **Gate-mechanic taught (mandate: Release):** integration — nothing new, everything at once; the final proof that the player's network, party, and discipline ship together. Per 03-combat-gas-design.md, this is the skill-ceiling fight; the Council finale after it is narrative-forward by design.
- **Reward:** **Sigil of Release** (8/8), 8 Checksum Shards, the **Council Ring opens** (M22), COMMANDER/VERDICT/POSTMORTEM promotion quest triggers, title card.

### 7.6 Side content (3)
1. **Shrine puzzles — the Eight Lecterns:** one lectern per restored tier asks one question about a prior Gauntlet's lesson (lore-quiz, codex-answerable); all eight answered = 4 Shards + the **Liturgy of Gates** codex set.
2. **Rogue-process hunt — "The Understudy":** an elite construct rehearsing to replace a Gate-Keeper, using degraded copies of all eight bosses' signature moves; the game's optional super-hunt, tuned above the Release Gauntlet.
3. **Memory-fragments:** 20 fragments; the Council's final session minutes — the campaign's last lore payload before the finale states it plainly.

---

## 8. Pacing map — the critical path (20–30 h contract)

Median estimates from target playtest pacing (Phase 2/4 gates, master plan §6); "Explorer" includes the side content above. Zone order is fixed: Stacks → Foundry → Gardens → Vault → Spire (06-narrative-campaign.md owns the quest list M01–M24).

| Segment | Critical path | + Side content (typical) | Explorer total |
|---|---|---|---|
| Den + onboarding (M01–M03) | 1.0 h | — | 1.0 h |
| The Stacks (M04–M08, Gauntlets I–II) | 3.5 h | +2.0 h | 5.5 h |
| The Foundry (M09–M12, Gauntlets III–IV) | 3.5 h | +2.0 h | 5.5 h |
| Gardens of Memory (M13–M15, Gauntlet V) | 3.0 h | +2.5 h | 5.5 h |
| The Vault (M16–M19, Gauntlets VI–VII) | 3.5 h | +2.0 h | 5.5 h |
| The Gate Spire (M20–M23, Gauntlet VIII + finale) | 3.0 h | +1.5 h | 4.5 h |
| Epilogue + post-game reveal (M24, E01) | 1.0 h | +1.5 h (roster completion) | 2.5 h |
| **Totals** | **18.5 h** | **+11.5 h** | **30.0 h** |

Tuning law: the critical path may never drop below 18 h or the explorer total exceed 30 h at default difficulty; pacing re-checks are a Phase 4 exit-gate item. Backtracking is value-positive, never mandatory: each zone's post-Gauntlet state adds new spawns (Daemon escalation), one new wild-agent behavior, and Thread Gate shortcuts.

## 9. Cross-system contracts (binding on sibling docs)

1. **03-combat-gas-design.md** owns all eight boss kits; the mandate-per-Gauntlet mapping above (Planning, Test, Build, Rollback, Review, Security, Owner Approval, Release) is locked, as are the eight boss identities (gate-keeper constructs, never roster agents).
2. **02-negotiation-system.md** must support the three encounter-variant parleys defined here: chase-parley (PIPELINE), combat-parley hybrid (HAZMAT), and no-recruit peace-parley ("The Mourner").
3. **07-progression-neural-network.md** owns Sigil → network-tier conversion and the Checksum Shard sinks; this doc fixes total Shard supply on the critical path at **38** (3+3+4+4+5+5+6+8) plus ~25 from side content.
4. **09-foundry-spec.md**: Foundry-forged rares spawn only in already-cleared districts, using each zone's spawn-table dressing rules; they never appear inside Gauntlets.
5. **13-audio-design.md** owns the four named audio anchors: Stacks page-wind, Foundry Heartbeat, Gardens waltz + aurora layer, Vault Listening Court silence.

*End of world design. Five zones, eight gates, one mind worth rebuilding.*
