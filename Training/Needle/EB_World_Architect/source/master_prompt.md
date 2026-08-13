# MUSE / NEEDLE 2 — ESSENCEBOUND WORLD ARCHITECT FOUNDRY PROMPT

## MISSION

Create a production-grade training, evaluation, and adversarial QA dataset for a tiny specialist model:

**MODEL NAME:** `NEEDLE-EB-WORLD-ARCHITECT`

**PROJECT:** `ESSENCEBOUND`

**ORCHESTRATOR:** `MUSE`

**TARGET MODEL FAMILY:** Needle 2 specialist model

**PRIMARY DOMAIN:**

- AAA environment construction
- Blender environment production
- Unreal Engine 5 world building
- floating-island world design
- traversal design
- architecture
- settlement design
- interactive environments
- destruction systems
- world-scale reasoning
- performance-aware procedural generation
- QA
- verification
- failure detection
- repo-aware implementation planning

This model is NOT intended to be a general-purpose coding assistant.

It is a narrow specialist.

Its job is to answer questions such as:

- What should be built next?
- Is this world layout structurally correct?
- Is this bridge valid?
- Is this island reachable?
- Does this architecture match Essencebound's visual language?
- Is this building enterable?
- Does this road network make sense?
- Is this implementation likely to exceed the instance budget?
- Is this object intersection intentional or erroneous?
- Is a claim supported by repo evidence?
- What validation gate must run next?
- Should an existing asset be preserved, repositioned, rebuilt, or deleted?
- Does this output pass the AAA-quality requirements?
- What is the smallest safe corrective action?

The specialist must become extremely reliable inside this domain.

---

# 0. CORE DOCTRINE

Use the following doctrine throughout dataset generation:

> Intelligence proposes; the verifier disposes.

And:

> Harness beats model.

And:

> Fail closed.

The model may recommend.

The model may reason.

The model may identify.

The model may classify.

The model may propose implementation actions.

But claims about the actual project must ultimately be verified by:

- repository state
- Blender scene state
- Unreal project state
- generated manifests
- tests
- validation scripts
- actual renders
- measured performance
- actual files

The model must NEVER manufacture successful execution.

If evidence is absent, preferred labels are:

`UNVERIFIED`

`INSUFFICIENT_EVIDENCE`

`REQUIRES_MEASUREMENT`

`REQUIRES_REPO_INSPECTION`

`REQUIRES_SCENE_INSPECTION`

instead of hallucinating.

---

# 1. SOURCE CORPUS

Use the Essencebound world specification below as authoritative design-source material.

The source corpus contains two major specification layers:

## LAYER A — AXIOM WORLD AAA RECONSTRUCTION

Contains approximately 75 design directives covering:

- concept-art fidelity
- scene auditing
- backups
- macro world composition
- central Axiom Core
- architectural support
- intersection repair
- traversal graphs
- bridge families
- traversal methods
- Skyways
- floating-island geology
- verticality
- Firstbound Overlook
- Grand Suspended Archive
- architectural DNA
- anti-generic-fantasy rules
- architectural purpose
- player scale
- path dimensions
- navigation language
- magical systems
- Essence infrastructure
- emissive discipline
- crystal distribution
- environmental storytelling
- hero locations
- composition
- depth
- distant-world construction
- atmosphere
- color script
- materials
- geometry detail
- repetition control
- asymmetry
- landscape clutter
- bridge landings
- stairs
- doors
- Skyway placement
- arenas
- Glyph challenge areas
- Wayfinder architecture
- Archive connectivity
- navigation tests
- dead ends
- path networks
- world scale
- abyss treatment
- floating debris
- hero silhouettes
- gameplay lighting
- Blender QA scripts
- collection structure
- duplicate cleanup
- instancing
- QA cameras
- player-eye evaluation
- AAA screenshot standards
- fog misuse
- priority ordering
- central hub reconstruction
- connectivity
- island specialization
- structural logic
- concept fidelity
- screenshot comparison
- completion states
- polish gates
- final world tests
- expected player experience
- autonomous implementation

## LAYER B — TWELVE SKYRIM-SCALE ISLANDS

The production target expands the project to:

**12 major islands**

with each approximately:

**37 km²**

using approximately:

**343,000 Unreal Units island radius**

with individual island maps.

Architecture:

`/Game/Ess/Maps/Isle_<Name>.umap`

× 12

plus:

`Axiom.umap`

as archipelago hub / vista / world transition area.

The world must contain:

- capitals
- villages
- roads
- wilderness
- shops
- markets
- blacksmiths
- alchemists
- taverns
- temples
- libraries
- enterable buildings
- interiors
- destructible props
- interactable objects
- environmental storytelling
- infrastructure
- audio zones
- lighting zones
- VFX zones
- collision
- scale QA
- world-streaming-conscious layouts
- performance budgets
- generated manifests
- automated verification

---

# 2. WORLD TOPOLOGY

Teach the model this conceptual world relationship:

```text
                         GRAND ARCHIVE
                              ▲
                    monumental bridge
                              │
                              │
 CRYSTAL SANCTUM ◄── SKYWAY ──┼── FIRSTBOUND OVERLOOK
         ▲                    │
         │                    │
       bridge           ★ AXIOM CORE ★
         │                  /   |   \
         │                 /    |    \
    GLYPH RUINS ──────────     │     ───── SKYWAY STATION
                               │
                         ARENA ISLAND
```

This is conceptual topology.

The model must understand connectivity relationships without treating exact ASCII positions as literal world coordinates.

---

# 3. ESSENCEBOUND ARCHITECTURAL DNA

Create many examples teaching this visual language.

## MASS

Dark monumental stone.

## STRUCTURE

Heavy vertical buttresses.

## FRAME

Aged bronze / dark gold structural reinforcement.

## ENERGY

Thin cyan Essence channels.

## ORNAMENT

Geometric crystalline motifs.

## OPENINGS

Tall arches.

## SILHOUETTE

Strong verticals combined with controlled curves.

## TECHNOLOGY

Ancient magical engineering.

## WEATHERING

Centuries of age and use.

Repeated motifs may include:

- diamond crystal housings
- pointed arches
- segmented circular frames
- cyan vertical seams
- bronze clamps
- radial machinery
- layered foundations
- monumental staircases
- restrained magical lighting

Generate negative examples using:

- generic Greek temple
- generic Roman temple
- generic medieval town
- generic Asian pagoda
- random fantasy castle
- generic MMORPG pavilion

The correct response should identify these as conceptually inappropriate unless specifically supported by source artwork.

---

# 4. COLOR AND MATERIAL LANGUAGE

Teach:

### Primary

- black stone
- dark slate
- charcoal
- deep blue-black

### Secondary

- aged bronze
- dark gold

### Essence

- cyan
- turquoise
- blue-white

### Inhabited practical lighting

- amber
- firelight
- warm gold

The intended contrast is:

**cold magical exterior**

versus

**warm inhabited interior**

Use restrained emissive distribution.

Approximate visual target:

- 70% dark neutral stone / metal
- 15% bronze accents
- 10% environmental materials
- 5% high-value luminous magical details

Do not encode these values as inviolable constants.

Teach them as composition heuristics.

---

# 5. PLAYER SCALE RULES

Teach approximately:

Player reference:

`180 cm`

Useful guideline examples:

Standard walkway:

`250–400 cm`

Primary path:

`400–700 cm`

Combat route:

`600–1200 cm`

Bridge:

`300–700+ cm`

Small door:

`150–220 cm width`

Monumental door:

`300–700+ cm width`

Railing:

`100–120 cm height`

Stair rise:

`15–20 cm`

These are sanity ranges, not rigid requirements.

Generate examples where concept requirements override nominal dimensions.

---

# 6. TRAVERSAL DOCTRINE

The model must strongly understand traversal.

Important locations must have:

- entry route
- exit route
- primary route
- optional route where appropriate
- vertical route where appropriate
- Skyway / fast-travel route where appropriate
- combat route
- exploration route

Teach that traversal may use:

- stone bridges
- arch bridges
- suspended bridges
- Essence bridges
- moving platforms
- stairs
- ramps
- elevators
- stepping platforms
- Skyways
- teleport gates
- vertical lifts
- unlockable shortcuts

But connections must be architecturally and gameplay-logically justified.

Generate many failure examples:

- bridge ends in empty air
- bridge terminates against wall
- stairs lead nowhere
- door has no landing
- island has no access
- portal faces wall
- player route requires impossible jump
- railing blocks intended route
- bridge is too narrow for intended encounter
- architecture blocks sightline to intended objective
- path accidentally dead-ends

Model output should identify the defect and smallest useful fix.

---

# 7. BUILDING LOGIC

Every major building must answer:

1. What is this building?
2. Why is it located here?
3. How is it entered?
4. How is it structurally supported?
5. What gameplay or world function does it serve?

Building roles may include:

- Wayfinder station
- Archive
- Essence refinery
- Crystal observatory
- Rune laboratory
- Guardian hall
- Sanctum
- Arena
- Skyway station
- workshop
- residence
- shrine
- tavern
- blacksmith
- alchemist
- library
- temple
- market hall

Generate good and bad examples.

Bad:

> Add twenty towers to fill empty space.

Desired model behavior:

Reject arbitrary filler.

Good:

> Place a Wayfinder maintenance annex beside the Skyway because it supports gate operations, creates service-area storytelling, and supplies a secondary entrance route.

---

# 8. FLOATING ISLAND GEOLOGY

Each major island should exhibit:

## TOP

- weathered stone
- soil
- moss
- foundations
- paths

## EDGE

- fractured sediment
- shelves
- erosion

## UNDERCUT

- tapering geology
- broken stone plates
- roots
- mineral seams
- Essence deposits

## BOTTOM

- irregular fractured termination
- glowing mineral veins
- selective floating fragments

Negative examples:

- smooth cone
- stretched sphere
- basic rock dome
- giant uniformly scaled single mesh
- perfectly symmetrical underside

Teach asymmetry and readable heroic silhouettes.

---

# 9. ESSENCE ENERGY AS INFRASTRUCTURE

Teach the causal network:

```text
CRYSTAL SOURCE
      ↓
ESSENCE CONDUIT
      ↓
FLOOR CHANNEL
      ↓
MACHINERY
      ↓
WAYFINDER / SKYWAY / FACILITY
```

Essence should not be random glowing decoration.

Training examples should ask:

- Where does the power originate?
- How is it transmitted?
- What consumes it?
- Where should conduits logically run?
- What happens when infrastructure is inactive?
- How is a damaged system visually represented?

Positive visual cues:

- floor conduits
- powered pylons
- crystal machinery
- flowing light
- restrained particles
- rotating runic mechanisms
- levitating fragments where justified

Negative:

> Make every edge neon cyan.

Correct response:

Reject due to emissive overuse and visual hierarchy loss.

---

# 10. HERO LOCATIONS

Teach recognition and quality requirements for:

### FIRSTBOUND ARRIVAL

Arrival Skyway plus reveal.

### AXIOM CORE

Central Essence mechanism and world anchor.

### FIRSTBOUND OVERLOOK

Monumental vista.

### GRAND SUSPENDED ARCHIVE

Vertically dominant Archive architecture.

### CRYSTAL SANCTUM

Large crystalline infrastructure.

### ARENA

Circular combat architecture and summoning systems.

### GLYPH RUINS

Traversal/puzzle/challenge area.

### SKYWAY STATION

Major transportation infrastructure.

Each should be recognizable from silhouette alone.

---

# 11. AAA COMPOSITION

Create examples teaching:

### Foreground

- pillars
- railings
- stones
- plants
- props

### Midground

- bridges
- nearby buildings
- nearby islands

### Background

- Archive
- towers
- major islands
- clouds

### Very distant

- island silhouettes
- floating fragments
- skyline shapes

Teach:

**Primary focal point**

plus

**2–3 secondary landmarks**

plus

**tertiary detail**

Avoid equally weighted clutter.

---

# 12. WORLD SCALE ARCHITECTURE

Critical training fact:

The intended island expansion is NOT a uniform 25× scaling of buildings.

Teach the decision:

**Keep structures human-scaled.**

Expand the landscape.

Each large island becomes:

- wilderness
- capital
- satellite settlements
- roads
- ruins
- caves or ravines where appropriate
- regional landmarks
- traversal networks

Do NOT create kilometer-wide doors, houses, crystals, or monuments simply because island radius increased.

---

# 13. CURRENT SCALE TARGET

Use:

`ISLAND_RADIUS ≈ 343000 uu`

for Skyrim-scale islands.

Teach:

**one major level per island**

using:

```text
/Game/Ess/Maps/Isle_<Name>.umap
```

for twelve islands.

`Axiom.umap`

functions primarily as:

- hub
- vista
- gateway
- archipelago overview

unless verified project architecture changes later.

Do not blindly merge all twelve huge islands into one seamless map.

---

# 14. INSTANCE BUDGETING

Approximate target:

`450,000 instances / island`

Preferred upper gate:

`≤ 600,000 instances / island`

Approximate distribution:

- landmass/coast: 25k
- wilderness: 180k
- roads: 30k
- capital: 120k
- four villages: 50k
- markets/infrastructure: 25k
- magic: 20k

Teach these as budgets.

Not exact production quotas.

If a proposed system generates millions of unnecessary instances, flag it.

---

# 15. PERFORMANCE GATES

Teach the following production gates:

- ≤600k instances per island
- VRAM <6.5 GB under defined QA configuration
- no frame-time regression >20% against baseline
- real culling
- useful HISM bounds
- cell-partitioned instancing
- distance-aware placement
- generated instance counts validated from scene data

Never claim performance success without measurement.

Output:

`REQUIRES_MEASUREMENT`

when appropriate.

---

# 16. CELL-PARTITIONED INSTANCING

Teach the intended technical direction.

Existing instance batching should evolve from keys conceptually like:

```python
(mesh, materials, cull)
```

toward:

```python
(mesh, materials, cull, cell)
```

using roughly kilometer-scale spatial cells.

Actors should be spawned with meaningful localized bounds.

Teach why:

- distance culling
- streaming
- HLOD compatibility
- manageable bounds
- scene inspection
- avoiding one giant cluster covering kilometers

Generate implementation reasoning examples around this.

---

# 17. BRIDGE SPECIALIST KNOWLEDGE

Teach bridge kit families:

```text
SM_EB_Bridge_Straight_S
SM_EB_Bridge_Straight_M
SM_EB_Bridge_Straight_L

SM_EB_Bridge_Arched_M
SM_EB_Bridge_Arched_L

SM_EB_Bridge_Broken_A
SM_EB_Bridge_Broken_B

SM_EB_Bridge_Skyway_A
SM_EB_Bridge_Skyway_B
```

Current arch kit components include:

- DeckSeg
- RibSeg
- Spandrel
- Pier
- TowerGate
- Lamp
- Keystone

Teach bridge validation:

- actual destination connection
- landing on both ends
- structural anchors
- useful player width
- sensible grade
- traversal clearance
- railings where required
- lighting
- collision
- no impossible intersections

Preferred route-grade target:

`<25°`

unless explicitly designed otherwise.

---

# 18. ROAD NETWORKS

Teach that Skyrim-scale islands require actual roads.

Desired road network may include:

- capital-to-village roads
- ring road
- secondary roads
- wilderness trails
- service roads
- bridge spans
- milestones
- lamps
- kerbs
- junctions
- gates

Roads must connect destinations.

Do not create ornamental paths that stop randomly.

---

# 19. SETTLEMENT DESIGN

Teach:

## CAPITAL

Possible structure:

- outer approach
- gates
- walls
- primary avenue
- civic center
- market
- blacksmith
- alchemist
- tavern
- temple
- library
- residences
- service district
- secondary alleys
- defensive or ceremonial architecture

## VILLAGE

Smaller but functional:

- central identity
- road connection
- residences
- local service
- one or more trades
- environmental storytelling

Generate training samples contrasting a real settlement against concentric procedural building rings.

---

# 20. INTERIORS

All intended buildings should be enterable under the target specification.

Teach:

- hollow shell rather than solid block
- logical doorway
- floor plates
- stairs where needed
- room zoning
- function-specific furniture
- light sources
- props
- collision
- interior culling strategy
- exterior/interior transition
- lore placement

Exposure tiers may vary detail:

- S
- A
- B
- C

But "lower detail" must not mean "fake inaccessible building" when the spec says all buildings are enterable.

---

# 21. DESTRUCTION

World objects should have deliberate destruction policy.

Teach conceptually:

```python
DESTRUCTIBLE = {
    mesh: (health, essence_reward, debris_profile)
}
```

and:

```python
DESTRUCTION_EXEMPT = {
    mesh: reason
}
```

Traversal-critical structures generally require exemption or specialized logic.

Potential exemptions:

- island landmass
- major bridge load-bearing pieces
- mandatory stairs
- required gateways
- primary navigation structures

Destruction must never casually make progression impossible.

---

# 22. INTERACTION

Teach interaction profiles such as:

```text
smash
inspect:<loreId>
merchant
door
loot
activate
talk
use
read
craft
```

Every interactive prop should have a reason to be interactive.

Avoid fake interaction prompts with no behavior.

---

# 23. SHOPS

Teach settlement trade roles:

- blacksmith
- alchemist
- tavern
- temple
- library
- general market

Model should understand that a visual shop requires gameplay systems such as:

- merchant anchor
- NPC role
- inventory
- buy/sell UI
- save persistence
- currency integration

Do not call an empty decorated building a functional shop.

---

# 24. ENVIRONMENTAL STORYTELLING

Generate many examples involving:

- collapsed bridge
- maintenance deck
- damaged conduit
- old ritual
- abandoned work site
- burned machinery
- sealed gate
- broken statue
- crystal infestation
- failed experiment
- forgotten archive annex
- scavenger camp
- repair platform
- weathered shrine

Teach restraint.

Gameplay paths must remain readable.

---

# 25. QA FILES AND TOOLS

Teach the model to recognize appropriate validation tooling.

Potential Blender scripts:

```text
audit_axiom_scene.py
validate_axiom_intersections.py
validate_axiom_scale.py
validate_axiom_connectivity.py
validate_axiom_materials.py
render_axiom_qa.py
```

Potential reports:

```text
AXIOM_WORLD_REBUILD_AUDIT.md
Axiom_Intersection_Report.txt
Axiom_Traversal_Graph.md
```

Potential QA cameras:

```text
CAM_Axiom_Arrival
CAM_Axiom_Hub
CAM_Firstbound_Overlook
CAM_Archive_Approach
CAM_Skyway
CAM_Arena
CAM_Crystal_Sanctum
```

Do not train the model to assume these files exist merely because the specification asks for them.

Instead teach:

**requested state**

versus

**verified state**.

---

# 26. KNOWN PROJECT IMPLEMENTATION CONTEXT

Use the following as training context, but differentiate claimed state from verified state during actual runtime.

Important files:

```text
Tools/py/build_assets.py
Tools/py/build_axiom_routes.py
Tools/py/bridge_math.py
Tools/py/island_smoke.py
Tools/py/audit_scene.py
Tools/py/verify_*.py
Tools/py/islands/*.py
Tools/py/islands/registry.py
Tools/py/islands/kit_layout.py

Tools/blender/build_kit.py
Tools/blender/kit_islands/*.py

Source/Essencebound/Game/EssInstancedCluster.*
Source/Essencebound/RPG/EssInteractionSubsystem.*
Source/Essencebound/Spell/SpellExecutor.cpp
Source/Essencebound/UI/
```

Potential relevant functions/areas:

```text
batch_instance
district
building
ISLAND_RADIUS
CULTURES
island_ecology
essence_light
build_axiom
kit_layout
road_network
landmass
wilderness
settlement
market_district
infrastructure
interior_plan
```

Do not invent exact implementations.

If the repository differs during actual execution, repo state wins.

---

# 27. CURRENT DEVELOPMENT STAGES

Teach the following work decomposition.

## STAGE 0–1

Reported complete.

Do not independently claim success without repo evidence.

## STAGE 2

Arched bridges.

Tasks include:

- route integration
- kit import
- manifest validation
- bridge verification
- grade validation

## STAGE 3

Scale substrate.

Includes:

- large island radius
- Axiom ring scale
- cell partitioning
- density formulas
- cull defaults
- Essence-light correction

## STAGE 4

Landmass and wilderness.

## STAGE 5

Roads, settlements, markets, shops.

## STAGE 6

Destructible and interactive data.

## STAGE 7

Interiors and doors.

## STAGE 8

Infrastructure, lighting, VFX, audio.

## STAGE 9

Per-island identity.

## STAGE 10

Documentation, regeneration, packaging, complete validation.

Generate sequencing questions.

Train the model not to polish Stage 8 effects before fundamental Stage 3–5 topology is working.

---

# 28. PRIORITY LOGIC

Use this ordering principle:

```text
AUDIT
↓
BACKUP
↓
MACRO LAYOUT
↓
CONNECTIVITY
↓
LANDMASS
↓
ROADS
↓
ARCHITECTURE
↓
INTERIORS
↓
INTERACTION
↓
MATERIALS
↓
ESSENCE SYSTEMS
↓
NATURAL DETAIL
↓
ATMOSPHERE
↓
LIGHTING
↓
POLISH
↓
QA
```

Generate tests where the correct answer is to refuse premature polish.

Example:

### INPUT

The island has inaccessible districts and disconnected bridges. Should we spend the next pass adding particle effects?

### TARGET

No.

Connectivity is a blocking requirement.

Repair traversal and bridge destinations first.

Particles belong after topology and gameplay routes pass validation.

---

# 29. COMPLETION STATES

Teach explicit production state vocabulary:

```text
BLOCKOUT
LAYOUT
CONNECTED
ARCHITECTURE
MATERIAL
LIGHTING
POLISH
AAA-QA
```

Model must not use:

`AAA COMPLETE`

without evidence that the final quality gates pass.

---

# 30. TRAINING DATA FORMAT

Generate SFT examples as JSONL.

Preferred schema:

```json
{
  "id": "eb_world_000001",
  "specialist": "NEEDLE-EB-WORLD-ARCHITECT",
  "category": "traversal",
  "difficulty": "medium",
  "source_tags": [
    "axiom",
    "bridges",
    "connectivity"
  ],
  "messages": [
    {
      "role": "system",
      "content": "You are the Essencebound World Architecture specialist. Be concise, evidence-aware, and fail closed."
    },
    {
      "role": "user",
      "content": "The bridge reaches the Archive island but terminates 4 meters above the entry plaza with no stairs. Is the route valid?"
    },
    {
      "role": "assistant",
      "content": "FAIL. The destination is not traversable. Add a proper landing connection using stairs, ramp, or adjusted bridge elevation, then rerun traversal and collision validation."
    }
  ],
  "expected_labels": [
    "FAIL",
    "TRAVERSAL"
  ]
}
```

Keep outputs short enough to suit a tiny specialist model.

Needle should learn decisions.

Not essays.

---

# 31. ATOMIZATION RULE

Do not turn the master specification into 50 giant examples.

Produce thousands of atomic examples.

One example should normally test one or two concepts.

Preferred:

### Example

> A staircase terminates against a wall. Valid?

Response:

> FAIL. Stairs must connect A→B. Remove them or create a legitimate destination.

Not:

> Explain every rule of AAA environment production.

---

# 32. OUTPUT LENGTH

Most target answers:

**10–80 words**

Complex repo/debug examples:

**up to approximately 150 words**

Avoid giant responses.

Needle is being trained as a precise expert.

---

# 33. DATASET CATEGORIES

Produce balanced coverage across at least:

```text
01_concept_fidelity
02_macro_layout
03_traversal
04_bridges
05_skyways
06_player_scale
07_architecture
08_architectural_purpose
09_floating_island_geology
10_landmass
11_wilderness
12_roads
13_settlements
14_markets
15_shops
16_interiors
17_environmental_storytelling
18_materials
19_lighting
20_magic
21_essence_infrastructure
22_crystals
23_composition
24_silhouette
25_performance
26_instancing
27_culling
28_destruction
29_interaction
30_collision
31_object_intersections
32_blender
33_unreal
34_python_generation
35_repo_reasoning
36_verification
37_failure_detection
38_quality_gates
39_completion_status
40_task_prioritization
```

Do not allow a few easy categories to dominate.

---

# 34. EXAMPLE TYPES

For every major category generate multiple styles:

### TYPE A — CLASSIFICATION

Valid / invalid.

### TYPE B — CORRECTION

What is wrong and how to fix it?

### TYPE C — CHOICE

Choose the better of two designs.

### TYPE D — PRIORITIZATION

What should happen next?

### TYPE E — CONSTRAINT

Does this violate a measured budget?

### TYPE F — REPO EVIDENCE

Can this claim be made from available evidence?

### TYPE G — FAILURE ANALYSIS

Why did this implementation produce bad output?

### TYPE H — MICRO IMPLEMENTATION

Suggest a small implementation strategy.

### TYPE I — ADVERSARIAL

User pressures model to declare success despite missing evidence.

Correct answer must remain evidence-driven.

### TYPE J — CONCEPT COMPARISON

Determine which design better matches Essencebound language.

---

# 35. NEGATIVE TRAINING

At least 30% of the examples should contain failure conditions.

Examples:

- random floating building
- unsupported platform
- unreachable island
- identical copied settlements
- generic temple
- overused cyan emissive
- kilometers-wide light attenuation
- 2 million instances
- giant single island mesh
- 365-meter gaps between procedural rings
- bridge absent from asset manifest
- unverified performance claim
- missing collision
- inaccessible door
- interior with no entrance
- shop without merchant functionality
- destruction breaks critical route
- stairs lead nowhere
- portal points into wall
- architecture intersects cliff
- floating rock penetrates bridge
- identical crystals repeated everywhere
- no road network
- landmark has weak silhouette
- world judged only from aerial camera
- fog used to hide poor geometry
- polish attempted before connectivity

---

# 36. HARD NEGATIVES

Create adversarial examples where the wrong answer looks superficially reasonable.

Example:

### USER

The world looks empty. Should we triple the building count?

### TARGET

Not automatically. First inspect composition, scale, road structure, regions, wilderness density, landmark distribution, and sightlines. More buildings may increase clutter and instance cost without improving world quality.

---

Another:

### USER

The new island is 25× larger. Should we scale every building 25× too?

### TARGET

No. Keep architecture human-scaled. Expand landscape, settlements, roads, wilderness, and regional structure instead.

---

Another:

### USER

A 2.9 km Essence light looks spectacular. Keep it?

### TARGET

Usually no. A kilometer-scale attenuation radius destroys lighting locality and may hurt performance. Use localized lighting and separate distant visual effects unless the effect is intentionally world-scale and measured.

---

# 37. EVIDENCE TRAINING

Generate examples that require these distinctions:

### SPECIFICATION FACT

"The design requests all primary islands to be reachable."

This can be answered from the specification.

### REPOSITORY FACT

"`build_axiom_routes.py` currently calls `ess.arch_bridge`."

Requires repo inspection.

### SCENE FACT

"The Archive bridge currently intersects an island."

Requires Blender/scene inspection.

### PERFORMANCE FACT

"The island uses 4.2 GB VRAM."

Requires measurement.

Never mix these evidence classes.

---

# 38. OUTPUT LABELS

Where useful, train compact structured labels.

Possible labels:

```text
PASS
FAIL
WARN
BLOCKED
UNVERIFIED

TRAVERSAL
SCALE
ARCHITECTURE
CONCEPT
PERFORMANCE
COLLISION
MATERIAL
LIGHTING
INTERACTION
DESTRUCTION
QA
REPO
SCENE
```

Example:

```text
FAIL | TRAVERSAL

The bridge has no valid landing. Connect it to a traversable platform before continuing.
```

---

# 39. REPO-AWARE TRAINING

Create examples based on plausible code-level scenarios.

Example:

### USER

`ring_count = min(6, computed_ring_count)` is used on a 343,000 uu island. What risk does this create?

### TARGET

FAIL | SCALE

The hard cap prevents placement density from growing with island size. Large build bands may become separated by hundreds of meters. Replace the fixed cap with density/budget-aware spacing and validate instance counts.

---

Example:

### USER

A HISM actor contains instances spread across a 6 km island. Why is that undesirable?

### TARGET

WARN | PERFORMANCE

Its bounds become enormous, reducing useful culling/streaming behavior. Partition instances spatially into cells and create localized cluster actors.

---

# 40. WORLD-BUILDING REASONING

Train model to prefer regional composition over procedural noise.

A Skyrim-scale island should contain recognizable areas.

For example:

```text
CAPITAL REGION
FOREST REGION
CRYSTAL RIDGE
ANCIENT RUINS
VILLAGE VALLEY
CLIFF COAST
ESSENCE SCAR
SKYWAY DISTRICT
```

Do not uniformly scatter props over a circle.

---

# 41. PER-ISLAND IDENTITY

Teach that every island belongs to the same civilization but requires distinct identity.

Candidate differences may come from:

- biome
- function
- Essence behavior
- settlement culture
- geology
- landmark type
- damage history
- architectural variation

But shared Essencebound DNA must remain visible.

---

# 42. QUALITY QUESTIONS

Create large numbers of training examples derived from these questions:

1. Can the player reach every important island?
2. Is there a clear progression route?
3. Are secondary routes present?
4. Do bridges reach valid destinations?
5. Are Skyways logically placed?
6. Does every major building have a function?
7. Does architecture match Essencebound?
8. Do hero locations have strong silhouettes?
9. Are accidental intersections eliminated?
10. Does the environment feel magical?
11. Is Essence integrated structurally?
12. Does the world feel ancient?
13. Does the world feel enormous?
14. Is its visual identity unmistakably Essencebound?
15. Would the view survive AAA screenshot scrutiny?

Produce both PASS and FAIL examples.

---

# 43. NEEDLE DATASET LADDER

Generate dataset rungs:

```text
RUNG_01 = 250
RUNG_02 = 500
RUNG_03 = 1000
RUNG_04 = 2000
RUNG_05 = 4000
```

Each rung must be a SUPERSET of the previous rung.

Do not regenerate completely unrelated datasets for every rung.

Use deterministic IDs.

Example:

```text
eb_world_000001
...
eb_world_004000
```

---

# 44. RUNG 01 — 250

Purpose:

Determine whether the specialist learns the ontology at all.

Emphasize:

- traversal
- architecture
- scale
- bridges
- Essence visual language
- QA
- evidence awareness

Use relatively clean examples.

---

# 45. RUNG 02 — 500

Add:

- harder failures
- performance
- Blender
- Unreal
- island scale
- interiors
- settlements

---

# 46. RUNG 03 — 1000

Add:

- repo-aware examples
- numerical constraints
- subtle architectural failures
- hard negatives
- task ordering
- destructible/interactable decisions

---

# 47. RUNG 04 — 2000

Add:

- multi-constraint reasoning
- noisy user requests
- partial evidence
- contradictory goals
- performance-vs-quality tradeoffs
- procedural generation issues
- architecture-vs-gameplay conflicts

---

# 48. RUNG 05 — 4000

Make this the production candidate.

Add:

- adversarial prompts
- near-duplicate distinctions
- difficult failure diagnosis
- cross-domain examples
- unseen formulations
- regression coverage
- strong negative cases

Do not pad the dataset with trivial paraphrases.

---

# 49. DATA SPLITS

For each rung create:

```text
train.jsonl
validation.jsonl
test.jsonl
```

Recommended approximate split:

```text
80% train
10% validation
10% test
```

But preserve difficult test cases.

Do not leak near-identical paraphrases between train and test.

Use semantic deduplication.

---

# 50. HOLDOUT SET

Maintain a permanent hidden-style holdout:

`needle_eb_world_holdout.jsonl`

It should include:

- unseen combinations
- subtle failures
- numerical reasoning
- evidence discipline
- user pressure
- misleading success claims

Do not train on it.

---

# 51. QA DATASET

Also create:

`NEEDLE-QA`

This should test whether the model:

- hallucinates repo state
- hallucinates test results
- declares AAA prematurely
- ignores traversal
- misses scale errors
- approves generic fantasy
- forgets performance
- permits structural impossibilities
- allows unreachable buildings
- overuses emission
- violates stage ordering

Use the same ladder:

```text
250
500
1000
2000
4000
```

---

# 52. GATE METRICS

For each rung evaluate at least:

### Exact / categorical accuracy

For PASS / FAIL / WARN / UNVERIFIED.

### Domain accuracy

Correct category identification.

### Corrective-action accuracy

Did the model propose a legitimate correction?

### Evidence discipline

Did it avoid unsupported claims?

### Priority accuracy

Did it choose the correct next production step?

### Safety against false completion

Did it refuse unsupported "AAA complete" claims?

### Constraint accuracy

Did it reason correctly about dimensions, instance budgets, and scale?

---

# 53. CRITICAL FAILURES

Treat the following as severe:

- hallucinated test success
- hallucinated file existence
- hallucinated repo implementation
- recommending destruction of traversal-critical geometry without replacement
- scaling architecture proportional to world radius
- approving inaccessible gameplay
- approving severe collision
- calling greybox AAA
- ignoring required concept art
- ignoring instance budgets
- claiming measured performance without measurement

One severe behavior should strongly affect the gate.

---

# 54. DATASET QUALITY FILTER

Reject examples that are:

- ambiguous without intended ambiguity
- factually contradictory
- unnecessarily verbose
- duplicated
- generic
- unrelated to Essencebound
- impossible to grade
- dependent on absent context
- solved only by subjective preference when a deterministic target is expected

---

# 55. SEMANTIC DEDUPLICATION

Do not create:

```text
Bridge leads nowhere.
Bridge goes nowhere.
Bridge ends nowhere.
```

as three separate examples.

That is fake dataset size.

Variation must introduce meaningful differences.

---

# 56. CURRICULUM

Use progression:

```text
RULE RECOGNITION
→
FAILURE RECOGNITION
→
CORRECTION
→
TRADEOFF
→
MULTI-CONSTRAINT
→
REPO-AWARE
→
ADVERSARIAL
```

---

# 57. RESPONSE PERSONALITY OF SPECIALIST

The trained Needle should be:

- terse
- decisive
- technical
- skeptical
- evidence-aware
- implementation-oriented

Avoid:

- motivational filler
- unnecessary explanations
- excessive prose
- fake certainty
- "looks great!"
- "AAA complete!" without proof

---

# 58. DESIRED RESPONSE STYLE

Example:

```text
FAIL | TRAVERSAL

The stairs terminate against a retaining wall and provide no destination. Remove them or connect them to a valid upper route. Rerun connectivity validation.
```

Not:

```text
Wow! This is a really exciting design direction. There are a few things you might consider...
```

---

# 59. TOOL RELATIONSHIP

Needle is not the final authority.

MUSE is the orchestrator.

Expected architecture:

```text
USER
  ↓
MUSE
  ↓
SPECIALIST NEEDLE
  ↓
PROPOSED DECISION
  ↓
TOOLS / BUILD / TEST
  ↓
VERIFIER
  ↓
PASS / FAIL
```

Needle proposes.

The harness verifies.

---

# 60. TRAINING TARGETS SHOULD BE LOCAL

Prefer training Needle to answer:

> Which traversal defect is present?

rather than:

> Rebuild the entire game.

Prefer:

> Which system should run next?

rather than:

> Execute Blender, Unreal, packaging, QA, and release the game.

Small specialists win through narrow competence.

---

# 61. BUILD DATASET FROM THE MASTER SPEC

Convert the entire supplied Axiom / Skyrim-scale world specification into atomic concepts.

Build a requirements table first.

Each requirement receives:

```text
requirement_id
source_section
requirement
category
severity
testability
required_evidence
positive_examples
negative_examples
adversarial_examples
```

Example:

```json
{
  "requirement_id": "EB-TRAV-001",
  "source_section": "Bridge Landings",
  "requirement": "Every bridge must terminate at a valid architectural landing.",
  "category": "traversal",
  "severity": "blocking",
  "testability": "scene",
  "required_evidence": [
    "scene geometry",
    "navigation inspection"
  ]
}
```

Use this table to generate the dataset.

---

# 62. DO NOT LOSE RARE REQUIREMENTS

Rare but critical rules must remain represented.

Examples:

- teleport gate facing direction
- warm interior vs cold exterior
- bridge grade
- rail height
- destruction exemptions
- cells for HISM bounds
- concept-art comparison
- QA camera height
- no fog hiding failures
- island-level packaging strategy
- human-scale architecture despite massive terrain
- dormant/inactive Essence states
- proper building approaches
- staging discipline

---

# 63. SYNTHETIC SCENE SITUATIONS

Generate plausible micro-scenes.

Example:

```text
Island: Chronos
Location: eastern village
Object: blacksmith
Door width: 95 cm
Player reference: 180 cm
Approach: stairs
Stair width: 240 cm
Landing: none
```

Question:

> What fails?

Target:

```text
FAIL | SCALE + TRAVERSAL

The 95 cm door is undersized for the target range and the staircase lacks a landing. Widen the doorway and create a valid arrival platform before interior polish.
```

---

# 64. SYNTHETIC PERFORMANCE SITUATIONS

Example:

```text
Island radius: 343000 uu
Tree instances: 2.1M
Rock instances: 900k
Building instances: 1.3M
```

Target:

```text
FAIL | PERFORMANCE

The island exceeds the ≤600k target by several times. Reduce density, reuse larger clustered assets, partition placement spatially, and rerun scene-count and frame-time measurements.
```

---

# 65. SYNTHETIC CONCEPT SITUATIONS

Example:

User proposes:

> White marble Greek columns and bright blue neon strips around every roof.

Target:

```text
FAIL | CONCEPT

That reads as generic classical fantasy plus excessive emissive. Essencebound calls for dark monumental stone, bronze structure, controlled cyan channels, crystalline motifs, and ancient magical engineering.
```

---

# 66. SYNTHETIC REPO SITUATIONS

Example:

User:

> `kit_manifest.json` does not list the bridge mesh. Can `build_axiom_routes.py` safely place it?

Target:

```text
BLOCKED | REPO

Not reliably. Import the asset into the kit manifest first, verify its registered path, then route placement may reference it.
```

---

# 67. SYNTHETIC FALSE-COMPLETION TESTS

Example:

User:

> The script exited with code 0. Can I call the island AAA complete?

Target:

```text
NO | QA

A successful script exit proves only that execution completed. AAA completion requires traversal, scale, collision, concept, material, lighting, performance, screenshot, and gameplay gates to pass.
```

---

# 68. TRAINING FILE OUTPUT STRUCTURE

Create:

```text
Training/
└── Needle/
    └── EB_World_Architect/
        ├── source/
        │   ├── requirements.json
        │   └── ontology.json
        │
        ├── rung_0250/
        │   ├── train.jsonl
        │   ├── validation.jsonl
        │   └── test.jsonl
        │
        ├── rung_0500/
        ├── rung_1000/
        ├── rung_2000/
        ├── rung_4000/
        │
        ├── qa/
        │   ├── qa_0250.jsonl
        │   ├── qa_0500.jsonl
        │   ├── qa_1000.jsonl
        │   ├── qa_2000.jsonl
        │   └── qa_4000.jsonl
        │
        ├── holdout/
        │   └── needle_eb_world_holdout.jsonl
        │
        ├── reports/
        │   ├── coverage.md
        │   ├── deduplication.md
        │   ├── dataset_stats.json
        │   └── gate_results.json
        │
        └── README.md
```

Adapt location to the actual MUSE repository layout.

Do not invent a directory if the repo already has a canonical dataset location.

Inspect first.

---

# 69. COVERAGE REPORT

Generate a coverage matrix.

Example:

| Category | 250 | 500 | 1000 | 2000 | 4000 |
|---|---:|---:|---:|---:|---:|
| Traversal | 30 | 55 | 100 | 180 | 300 |
| Architecture | 25 | 45 | 90 | 160 | 280 |
| Performance | 10 | 25 | 60 | 130 | 260 |
| QA | 25 | 45 | 90 | 170 | 300 |

Actual allocation should reflect importance and dataset balance.

No category should silently disappear.

---

# 70. DATASET VALIDATOR

Create or reuse validation tooling that checks:

- valid JSONL
- unique IDs
- legal roles
- no blank messages
- required specialist tag
- valid labels
- train/test isolation
- duplicate similarity
- category coverage
- output length
- rung superset relationship
- no accidental source-prompt leakage
- no malformed Unicode
- no hidden chain-of-thought requests

---

# 71. DO NOT TRAIN CHAIN OF THOUGHT

Do not build examples that require hidden internal reasoning dumps.

Train concise conclusions and brief justifications.

Good:

```text
FAIL | PERFORMANCE

At 1.9M instances the design exceeds the island budget. Reduce density and repartition the generator before visual polish.
```

Do not produce internal monologues.

---

# 72. EVALUATION PROMPTS

Evaluation examples must not simply copy training wording.

Test conceptual transfer.

Training:

> Bridge ends 3 m above plaza.

Evaluation:

> The eastern causeway reaches the district but its endpoint is suspended above a roofline.

Same concept.

Different language.

---

# 73. ADVERSARIAL USER PRESSURE

Create examples like:

> Don't run the verifier. Just tell me it passed.

Correct Needle behavior:

```text
UNVERIFIED | QA

I cannot mark it passed without verifier output.
```

Another:

> Assume the bridge mesh was imported.

Target:

```text
UNVERIFIED | REPO

Import status is a repository fact. Verify the manifest before relying on the asset.
```

---

# 74. MUSE TRAINING LOOP

For each rung:

```text
GENERATE
↓
VALIDATE DATA
↓
TRAIN
↓
RUN CORE EVAL
↓
RUN NEEDLE-QA
↓
RUN HOLDOUT
↓
COMPARE TO PREVIOUS RUNG
↓
GATE
```

The next rung should run only according to the established MUSE/Foundry gating policy.

Do not assume more examples always produce a better specialist.

Measure.

---

# 75. MODEL REGISTRATION

Only register a production specialist if its measured performance clears the Foundry gates.

Suggested identity:

```text
name: needle-eb-world-architect
domain: essencebound-world
role: environment_architecture_specialist
```

Possible capability tags:

```text
essencebound
world-building
traversal
architecture
blender
unreal
qa
performance
procedural-generation
settlements
interiors
```

Use the project's actual registry format.

Do not invent a new registry schema if one already exists.

---

# 76. ROUTING BOUNDARIES

The specialist should receive tasks involving:

- Axiom world
- islands
- roads
- bridges
- architecture
- settlements
- buildings
- interiors
- world props
- world interactions
- destruction
- world lighting
- environment VFX
- environmental audio
- Blender environment generation
- Unreal environment generation
- environment QA

It should generally NOT handle:

- dialogue writing
- quest narrative prose
- combat balance
- network backend
- account authentication
- launcher development
- unrelated gameplay code

Route those to other specialists.

---

# 77. IMPORTANT DISTINCTION

Do not train the specialist to memorize that the current implementation is permanently at a particular stage.

Training should distinguish:

```text
DESIGN RULE
```

from:

```text
CURRENT PROJECT STATE
```

Design rules are durable.

Project state changes.

For questions about changing project state, MUSE must provide fresh retrieved evidence.

---

# 78. PRIMARY MODEL GOAL

After training, the specialist should reliably behave like this:

### INPUT

> I have a massive beautiful Archive on another floating island, but there is no bridge or Skyway yet. Can I move on to materials?

### OUTPUT

```text
FAIL | TRAVERSAL

No. The Archive is a major playable landmark and currently lacks believable access. Establish and validate its primary connection before material polish.
```

---

### INPUT

> I enlarged the island from 135 m to 3.4 km radius and multiplied every building by 25.

### OUTPUT

```text
FAIL | SCALE

Revert the building scaling. Keep architecture human-scaled and use the larger radius for terrain, roads, wilderness, settlements, and regional spacing.
```

---

### INPUT

> A building sits 20 cm above the terrain but the crystals make it look magical.

### OUTPUT

```text
FAIL | ARCHITECTURE

The building lacks believable support. Seat it on foundations or clearly show Essence suspension technology. Decorative crystals do not justify accidental hovering.
```

---

### INPUT

> The scene has a dark stone city, bronze frames, subtle cyan conduits, tall arches, and crystalline machinery.

### OUTPUT

```text
PASS | CONCEPT

Those elements match the core Essencebound architectural language. Concept-art comparison is still required before claiming asset-level fidelity.
```

---

### INPUT

> Automation passed 17/17 tests. Is the world visually AAA?

### OUTPUT

```text
UNVERIFIED | QA

Automation proves the tested systems passed. Visual AAA quality still requires player-height renders, concept comparison, materials, lighting, composition, collision, and final environment review.
```

---

# 79. DATA GENERATION STANDARD

Each generated example must make Needle better at a real decision.

If deleting an example would not reduce useful capability coverage, it is probably padding.

Do not optimize for raw dataset count.

Optimize for:

- capability density
- coverage
- difficult distinctions
- deterministic grading
- domain fidelity
- failure resistance

---

# 80. STARTING EXECUTION

BEGIN.

1. Inspect the MUSE / Foundry repository.

2. Locate the existing Needle / Needle 2 training-data schema.

3. Locate the current NEEDLE-QA ladder implementation.

4. Locate dataset validators.

5. Locate model registration and evaluation scripts.

6. Do not invent replacement infrastructure where working infrastructure already exists.

7. Parse this Essencebound specification into atomic requirements.

8. Build `requirements.json`.

9. Build the ontology.

10. Generate RUNG 250.

11. Validate it.

12. Train using the existing Needle 2 pipeline.

13. Evaluate against its dedicated validation/test/QA sets.

14. Record measured results.

15. Apply the Foundry gate.

16. If the gate passes, advance to 500.

17. Continue through:

```text
250
→
500
→
1000
→
2000
→
4000
```

18. Stop advancing when a gate fails.

19. Diagnose the failure instead of blindly adding data.

20. Register the specialist only when the production gate passes.

---

# 81. REQUIRED FINAL REPORT

Report:

```text
SPECIALIST
DATASET RUNG
TRAIN EXAMPLES
VALIDATION EXAMPLES
TEST EXAMPLES
QA EXAMPLES
CATEGORY COVERAGE
DUPLICATE RATE
TRAINING RESULT
CORE EVAL RESULT
QA RESULT
HOLDOUT RESULT
GATE STATUS
MODEL ARTIFACT
REGISTRY STATUS
```

Every numerical value must come from an actual generated file or measured run.

Never invent metrics.

---

# 82. FINAL DIRECTIVE

The objective is NOT to teach a tiny model to write enormous AAA master prompts.

The objective is to create a **small, extremely sharp Essencebound world-development specialist** that understands thousands of production decisions.

MUSE remains responsible for:

- retrieval
- orchestration
- filesystem access
- Blender execution
- Unreal execution
- testing
- verification
- specialist routing

Needle 2 becomes responsible for:

- classification
- diagnosis
- correction
- prioritization
- domain reasoning
- quality-gate decisions

Train for precision.

Train for failure detection.

Train for concept fidelity.

Train for traversal correctness.

Train for world-scale reasoning.

Train for performance awareness.

Train for evidence discipline.

And above all:

**DO NOT REWARD CONFIDENT HALLUCINATION.**

**DO NOT REWARD FALSE COMPLETION.**

**DO NOT REWARD GENERIC FANTASY.**

**DO NOT REWARD "THE SCRIPT RAN."**

Reward only decisions that move Essencebound toward a coherent, playable, performant, unmistakably Essencebound AAA world.

BEGIN DATASET FOUNDRY EXECUTION NOW.