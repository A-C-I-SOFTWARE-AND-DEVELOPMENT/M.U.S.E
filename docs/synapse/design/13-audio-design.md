# 13 — Audio Design Document
### The sound of the Substrate

**Project:** SYNAPSE — A muse Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

---

## 1. Sonic identity

**Organic-synthetic.** The Substrate is a mind, and minds are warm: the palette is **warm
analog pads** (tape-saturated, slow-breathing) interwoven with **granular data textures** —
micro-grains of clicks, shimmers, and resampled speech-formants that read as "thought."
Nothing purely cold or purely natural: every natural source gets a synthetic artifact (a
bird call bit-crushed at the tail), every synth gets an organic one (pad layers breathe with
recorded room tone).

**The Substrate hums.** A continuous, barely-conscious low hum (root drone, 50–60 Hz region,
−38 LUFS ambient bed) underlies every zone, modulating subtly with the player's network size —
the world audibly *more alive* as the mind rebuilds. Its absence is a weapon: DEADLOCK
presence kills the hum first, and players learn to fear the silence before the fight.

THE DEADLOCK's signature is **reversal**: its motif and SFX palette are built from the
game's own sounds played backwards (§4.5) — the mind's music, undone.

---

## 2. Music direction

**Budget:** composer mini-score, **$800** (master plan §7). Scope is engineered to that
number — a focused commission plus systematic reuse, not wall-to-wall score.

**Commissioned deliverables (the mini-score):**

| Cue | Spec |
|---|---|
| Main theme | 2:30, full palette; the motif (a rising 5-note "synapse" figure) that every other cue quotes |
| 5 zone beds | 2:00 loops, one per zone (Stacks / Foundry / Vault / Gardens of Memory / Gate Spire), each = main-motif fragments + zone palette, delivered as **stems** (pad / texture / melodic) |
| Combat layer system | One modular combat set: drum/bass core loop + 2 intensity layers + 8 short domain stingers, stem-delivered |
| Parley underscore | 1:30 loop in 3 stems (neutral / warming / souring) |
| Council finale | 3:00 through-composed, the one linear luxury |

All delivered dry, 48 kHz/24-bit stems with tempo/key sheet so MetaSounds can do the
arranging in-engine. Zone variety beyond the beds comes from in-engine recombination
(stem muting, granular reprocessing of the composer's own material) — systematic, not
more commission.

### 2.1 Vertical layering spec

Every musical state is a **MetaSounds-driven stem mix**, never a hard cue swap:

- **Exploration:** zone bed, pad + texture stems; melodic stem fades in near points of
  interest (proximity parameter).
- **Tension:** enemy-awareness parameter (0–1) crossfades in the combat core loop at −12 dB,
  filtered (LPF 800 Hz opening with tension).
- **Combat:** full core + intensity layers per §3; exits by de-layering over 4 bars, back to
  the bed — seamless both directions, beat-quantized transitions (1-bar grid).

---

## 3. Interactive music rules

- **Combat layers keyed to party Integrity and pipeline combos** (canon meters,
  `03-combat-gas-design.md`):
  - Layer 1 (core): always on in combat.
  - Layer 2 (pressure): party average Integrity < 60% → in; > 75% → out (hysteresis so it
    never flutters).
  - Layer 3 (peril/triumph): Integrity < 30% → peril variant; an executed 3-agent **Pipeline
    combo** → triumph variant for 8 bars + the domain stinger of the finishing agent.
  - Gauntlet bosses: same system + a per-gauntlet ostinato stem (8 gauntlets × 30 s loop —
    in-engine reprocessing of zone material, not new commission).
- **Parley underscore follows the Disposition meter** (`02-negotiation-system.md`):
  neutral stem at parley start; Disposition rising ≥ 60 crossfades the warming stem;
  falling ≤ 35 crossfades souring; verdict moments punctuate — ACCEPT resolves to the main
  motif (the synapse figure completes), OFFENDED/WALK cuts to the reversed motif tail +
  hum dropout for 2 s. PROBE/COUNTER get short neutral ticks, not full punctuation —
  the meter must stay readable by ear alone (§8).

---

## 4. SFX taxonomy

### 4.1 UI
Granular data family: soft grain-clicks (hover), confirm = two-grain rising pair echoing the
synapse motif's first interval, cancel = single damped grain, error = detuned dyad. Network
screen wiring sounds are the *same family as the Observatory map* — one sound language for
"mind," game and cockpit alike.

### 4.2 Traversal & world
Footsteps per surface (12 surface types, 6 variations each); zone ambience = hum bed + 2
spot-emitter layers; interactables share a "data-resonance" ping family pitched per zone key.

**Per-zone soundscape briefs (the five zones, master plan §4.9):**

| Zone | Hum character | Spot emitters | Granular texture source |
|---|---|---|---|
| The Stacks | Wooden, library-warm; hum filtered through "shelf" comb resonances | Page-flutter swarms, distant index-card clicks, creaking data-boughs | Resampled paper + book-spine creaks |
| The Foundry | Industrial; hum gains a 4-on-the-floor sub-pulse synced to forge cycles | Hammer-on-anvil (pitched to zone key), steam vents, molten pours | Metal shop recordings, bit-crushed |
| The Vault | Pressurized, near-silent; the *quietest* zone — tension by subtraction | Lock tumblers, surveillance servo pans, distant shutter slams | Mechanical keyboards + vault doors |
| Gardens of Memory | Lush, detuned-nostalgic; hum has a slow chorus wobble | Bit-crushed birdsong, water-over-data trickles, wind-chime fragments of the main motif | Field recordings, granular-frozen |
| The Gate Spire | Cathedral; hum becomes an organ-like stacked drone, all five zone keys layered | Council murmur beds, vast door groans, the eight gate-bell partials | All four prior zones' banks, recombined |

Each zone sits in its own key (Stacks=D, Foundry=A, Vault=F♯, Gardens=G, Spire=D across
octaves) so the data-resonance pings and stingers always land harmonically on the active bed.

### 4.3 The 8 domain ability palettes (material signatures)

Every domain owns a **material signature** — combat reads by ear:

| Domain | Material signature |
|---|---|
| Architecture | Stone + deep choir pad; abilities land with slow attack, long tail (mass) |
| Security | **Sub-bass + metal shutter**; clamps, slams, lock-clicks; hard gate transients |
| QA/Test | Glass tick-tock + relay clicks; precise, metronomic, short tails |
| Research | **Glass + whisper-data**; airy shimmers, reversed whispers, page-flutter grains |
| Build/Ops | Industrial servo + pneumatic hiss; rhythmic, mechanical layering |
| Behavior/Psych | Warm vocal formants + heartbeat sub; the most "human" palette |
| Compliance | Stamped brass + paper snap + a single bell partial; bureaucratic finality |
| Release | Airlock whoosh + rising whoosh-to-chime; openings, launches, departures |

Pipeline combos chain the three agents' signatures into one composite hit (mark-tick →
exploit-slam → detonate-bloom) — the combo is audible as a sentence.

### 4.4 Gauntlet bosses
Each of the 8 bosses = its domain signature **scaled up** (octave-down layers, longer
convolution tails) + one unique mechanic-telegraph sound that is **always the loudest
pre-attack cue** (readability rule: telegraph ≥ 6 dB over bed, also drives §8 cues).

### 4.5 The Fragmentation / DEADLOCK motif
THE DEADLOCK's palette is **reversed audio**: the main motif recorded, reversed, and
granular-stretched = its leitmotif; its ability SFX are reversed transients of the eight
domain signatures (the player has heard every sound before — backwards is *wrong* in a way
they feel before they name it). Fragmentation zones detune the zone bed −30 cents and
comb-filter the hum.

---

## 5. VO plan

**Budget:** SFX + light VO, **$500** total line item (master plan §7) — VO scope engineered
accordingly. The parley scenes carry the game, so the dollars go there.

- **3 commissioned heroes** (the negotiation stars — default cast per master plan §14.4: one
  each Security, Research, Behavior): **~40 lines each** — parley barks (greeting, PROBE,
  COUNTER, OFFENDED, WALK, ACCEPT ×3 variants), combat barks, recruit/Den idles.
- **Other 21 agents: 8–12 barks each**, sourced as text + **foley vocalizations** per agent
  "voice-print": a per-agent granular chirp patch (source grain bank + pitch contour + formant
  filter derived from the personality card axes) — Animalese-class expressivity in the
  domain's material signature, infinitely reusable, $0 marginal cost.
- **The muse 6 voice presets**, **synthesis-assisted, human-curated** takes — synthetic
  voice generation curated/edited take-by-take by the owner; **disclosure note:** these
  presets are listed in the Steam AI disclosure (pre-generated tier, "AI-assisted …
  human-curated/edited," master plan §8.4). Presets are selected in the character creator and
  are never live-generated at runtime.
- **Live parley LLM text is text + voice-print chirps only — no live TTS at v1.0** (keeps the
  live-generated disclosure scoped to text, per `09-foundry-spec.md` §9, and keeps us inside
  budget and latency: `02-negotiation-system.md` 2.5 s rule).
- All barks subtitled (§8); bark text for the 21 non-hero agents is written, not recorded —
  chirps carry emotion, text carries words.

---

## 6. Implementation

- **MetaSounds first-class. No middleware license.** **Decision: Wwise loses, MetaSounds
  wins** at this budget and team shape: Wwise costs a license tier at commercial scale,
  a second authoring tool, and an integration surface a solo dev must maintain; MetaSounds is
  in-engine, free, node-graph authorable by the owner (the editor is the owner's lane,
  `11-technical-design.md` §11), Blueprint/C++ parameterizable for every system in §2–§4, and
  ships on the Android tier without porting. Trade-off accepted: weaker profiling/auth
  tooling than Wwise and hand-built state management — mitigated by a small set of reusable
  MetaSound templates (stem mixer, layer machine, voice-print chirp synth) built once in
  Phase 2. Revisit only if a console port materializes.
- **Concurrency rules:** global cap 48 active voices (min-spec 32); per-family caps —
  ability SFX 12 (steal-oldest within family), barks 2 (newest wins; hero VO never stolen by
  chirps), UI 6, ambience 8. Priority order: telegraphs > hero VO > verdict punctuation >
  ability > chirps > UI > ambience.
- **Ducking:** parley opens → music −6 dB, ambience −4 dB (200 ms attack / 800 ms release);
  hero VO ducks chirps −8 dB; boss telegraphs duck everything else −4 dB for their window;
  pause/Command Mode applies a 500 Hz LPF + −3 dB to the world, UI stays full-range (the
  "inside your head" read).
- **Loudness target: −16 LUFS integrated** (game overall, measured over a 30-min reference
  play session), **True Peak ≤ −1 dBTP**; dialogue/bark anchor −23 LUFS momentary. Verified
  per milestone with a loudness-meter capture pass (§7).
- Buses: Master → {Music, SFX (→ Abilities/World/UI), Voice (→ HeroVO/Chirps), Ambience} —
  matching the §8 player sliders exactly. Audio thread budget per
  `11-technical-design.md` §5 (0.5 ms GT flagship / 0.8 ms min-spec).
- **Reusable MetaSound templates (built once, Phase 2, then content-only work):**
  1. `MS_StemMixer` — N-stem crossfader with beat-grid quantize (drives §2.1/§3 music states).
  2. `MS_LayerMachine` — hysteresis-gated layer stack bound to Integrity/tension params.
  3. `MS_ChirpVoice` — the voice-print synth: grain bank + pitch contour + formant filter,
     parameterized from the 5 personality axes (warmth→formant, pride→pitch range,
     patience→grain rate, candor→attack, curiosity→interval spread).
  4. `MS_DomainHit` — material-signature ability hit assembler (transient + body + tail slots).
  5. `MS_ZoneBed` — hum + key + spot-emitter scheduler with DEADLOCK detune/comb hooks (§4.5).
- **Asset count budget (production planning, `14-production-plan.md`):** ≈ 1,400 shipped
  cues — 410 ability/combat (8 domains × kit coverage + 8 bosses), 430 foley/traversal,
  180 UI/network/Observatory, 200 ambience emitters, ~120 hero VO lines, ~230 bark text
  events with chirp renders. All 48 kHz; Vorbis quality 0.7 (music/ambience streamed),
  ADPCM for short SFX; audio pak budget ≤ 900 MB.

### 6.1 The non-game maps

The Observatory, Command Deck, and Avatar & Den maps share the §4.1 UI/data family so the
whole app speaks one language:

- **Neural Observatory:** the galaxy has its own hum (the *real* mind's, slightly brighter
  than the game's); SSE-driven sonification — `job.stage` packets emit soft whoosh-ticks
  panned along their spline, `gate.verdict` pass = the confirm dyad / fail = the error dyad
  pitched down, `route.decision` strums the chosen stratum (per `10-observatory-spec.md` §3.2
  event types). Sonification is rate-limited (≤ 8 events/s audible, overflow coalesces into a
  gentle "activity shimmer") so a busy gateway sounds alive, not alarming.
- **Command Deck:** near-silent professional bed; chat token-stream renders as a faint
  teletype grain (off by default, accessibility-toggleable); approval cards arriving get the
  Compliance bell partial.
- **Avatar & Den:** the coziest mix — zone hum replaced by hearth-room tone; placed Den items
  each register one idle spot emitter (cap 8 audible, nearest-priority).

---

## 7. Mix milestones (tied to master plan §6 phases)

| Phase (master plan) | Audio deliverable |
|---|---|
| 1 — The Spine (wk 4–8) | Temp palette; parley underscore prototype on Disposition; chirp-synth MetaSound v1. "The Moment" video has real parley audio |
| 2 — Vertical Slice (wk 9–16) | Stacks zone bed + combat layer system in; hero #1 VO recorded; domain signatures ×5 agents; first loudness pass |
| 3 — Observatory (wk 17–26) | Observatory soundscape from the UI/data family; route/verdict sonification |
| 4 — Production (wk 17–40) | All zones/agents/gauntlets; finale cue; full VO + chirp coverage; accessibility audio complete |
| 5 — Market engine (wk 30→) | Trailer mix (separate deliverable, trailer budget line); demo build mixed to target |
| 6 — Launch | Final mix pass: −16 LUFS / −1 dBTP verified across a full-campaign capture; min-spec voice-cap QA |

## 8. Audio accessibility

- **Full subtitles**, including barks, chirp-carried lines, and **directional indicators**
  (subtitle edge-arrows for off-screen speakers/telegraphs); size/background-opacity options.
- **Separate volume sliders:** Master / Music / SFX / Voice / Ambience (the §6 bus tree,
  1:1), plus a "Telegraph boost" toggle (+6 dB on boss telegraph family).
- **Mono fold-down** option (single-ear players); verified phase-safe per milestone.
- **Screen-shake-independent audio cues:** every cue that accompanies camera shake or flash
  has a discrete audio identity, so disabling shake/flash (visual accessibility,
  `01-game-design-document.md` options) loses zero information; likewise every
  color-coded combat state (Integrity bands, Disposition direction) has the §3 audible
  counterpart — the game is playable by ear and readable in silence (full subtitle path).
- Settings persist in `USynapseUserSettings` (`11-technical-design.md` §2.1).

---

## 9. Cross-references

- `01-game-design-document.md` — options menus, consent/accessibility UI homes.
- `02-negotiation-system.md` — Disposition meter, verdict enum, 2.5 s latency law.
- `03-combat-gas-design.md` — Integrity meter, pipeline combos, telegraph timing.
- `09-foundry-spec.md` §9 — AI disclosure surface the muse-voice note joins.
- `11-technical-design.md` — audio thread budget, settings persistence, owner-lane mixing.
- Master plan §7 (the $800 + $500 lines), §6 (phase gates), §8.4 (disclosure tiers).
