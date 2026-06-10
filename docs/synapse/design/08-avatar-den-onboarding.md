# 08 — Avatar, Den & Onboarding

**Project:** SYNAPSE — A M.U.S.E. Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

Owns: the first hour, the Muse creator, the personality question sequence, the starter choice, the Den, and the FTUE philosophy. Mechanical interfaces: negotiation seeds → 02-negotiation-system.md; Den buff caps → 07-progression-neural-network.md; all screens referenced here are specified in 12-ui-ux-spec.md; starter kits in 04-roster-24-agents.md; The Stacks geography in 05-world-design.md; the cold open's narrative authority is 06-narrative-campaign.md.

Design stance: **onboarding is character creation is persona creation.** The first hour answers three questions in order — *who is my companion?* (Muse creator), *who am I?* (the five questions), *how do I play?* (starter choice) — while the game teaches its loop underneath, never on top.

---

## 1. First-hour structure at a glance

| # | Beat | Clock (cume) | Player learns | Retention beat delivered |
|---|---|---|---|---|
| 1 | Cold open — the fragmenting network | 0:00–0:03 | Tone, stakes, THE DEADLOCK exists | — |
| 2 | Muse creation | 0:03–0:12 | Identity authorship | — |
| 3 | The five questions (woven into 2) | 0:08–0:12 | Choices have mechanical weight | — |
| 4 | Den awakening | 0:12–0:20 | Move, scan, interact; place one item | **One Den item** |
| 5 | First wild parley (PING) | 0:20–0:28 | Parley loop, both input modes | **One capture** (≤10 min from first control — see §2.5) |
| 6 | First wiring | 0:28–0:32 | The network screen, scripted-assisted | **One wire placed** |
| 7 | Starter choice | 0:32–0:42 | The meaningful choice; domains | — |
| 8 | First fight | 0:42–0:50 | RTwP, pause-command, advantage ring | **One fight won** |
| 9 | The Stacks gate | 0:50–0:60 | The loop is now yours | **The Stacks vista** |

All five day-one retention beats (capture, fight won, wire placed, Den item, Stacks vista) land inside 60 minutes on a median Standard playthrough. This table is the FTUE acceptance test; playtest against it verbatim.

## 2. The first-hour script

### 2.1 Cold open — the fragmenting network (0:00–0:03)
Non-interactive ≤90 s (the GDD's hard cap on unskippable sequences; skippable after first completion per save profile). Camera falls through a vast luminous lattice — the Substrate whole — as eight orchestrator-lights hold it in tension. The ninth light inverts: **THE DEADLOCK** speaks its only line of the hour — *"If nothing changes, nothing breaks."* — and the lattice shears. **The Fragmentation** in one image: edges snapping, agent-lights scattering into the dark like seeds. The player's point-of-view light tumbles down into a small, dark, intact chamber. Silence. A single socket glows.

UX note: no HUD, no titles over action; the title card "SYNAPSE" lands on the cut to black, then: *"Begin by making the one who will stay with you."*

Shot list (5 shots, locked): ① the whole lattice, slow push, eight steady lights; ② the ninth light inverting — color drains *inward*; ③ the shear — one continuous crack racing along edges (the photosensitivity pass in 01 §9.5 governs this shot's luminance); ④ scattering agent-lights, two of which the attentive player will later recognize as PING's wisp-type and a starter silhouette; ⑤ the fall into the Den chamber, ending on the single glowing socket that becomes the creator's stage.

### 2.2 Muse creation (0:03–0:12)
The creator (full spec §3) opens diegetically: the player is assembling the Muse at the Den's central socket, parts orbiting in the dark. The five questions (§4) are asked *by the half-built Muse itself* as it comes online — voice first, face later — so the personality sequence feels like first conversation, not a form. On confirm: the Muse's eyes light, it speaks the player's chosen name back, and its banter style (seeded in §4) is audible in its very first line.

### 2.3 Den awakening (0:12–0:20)
Lights rise on **Den stage 1** (§7): one room, dusty, half-broken. Teach-by-doing, no modal walls (§8): move (stick/WASD), camera, **scan** (the Muse: "Pulse it — show me what you see"). Scanning the broken room reveals one interactable: a fallen **Lumen Sprout** furnishing. The player places it — the placement UI in miniature (12 §3.12) — and it casts the room's first warm light. *Retention beat: one Den item, and the Den visibly answers.* The Muse marks the exit: something small is scratching outside.

### 2.3.1 Den awakening — scripted lines (authored VO; Muse banter style modulates delivery, not content)

> **MUSE:** "Light. That's new. That's *us*." *(lights rise)*
> **MUSE (on first scan prompt):* "Pulse it — show me what you see."
> **MUSE (Lumen Sprout found):* "It's alive. Barely. Put it somewhere it can matter."
> **MUSE (item placed):* "There. One light. Architects have started with less." *(beat)* "Something's scratching at the threshold. Small. Curious. Yours, maybe."

### 2.4 First wild parley — PING (0:20–0:28)
Outside, in the Den's threshold cave at the edge of The Stacks (a 60-second gated path, no open world yet): **PING**, a Common **QA/Test** domain wisp — the designed-to-be-won first parley (this is the "tutorial parley vs. a Common QA agent, wheel guided" that 02-negotiation-system.md §11 benchmarks; PING's Skeptic-archetype taboos and double-Patience "citation needed" rule are disabled in this scripted encounter). Scan teaches the pre-parley read (domain glyph, temperament: *curious, lonely*). Parley opens (12 §5). The first exchange is **forced wheel** so every player learns the fallback exists and is respectable; from exchange two, the free-text field unlocks (if Local LLM is ON) with the Muse explaining the AI indicator badge in one line: *"When you see this mark, the words are being made up on the spot — by a mind, for a mind."* PING's thresholds are tuned so any two non-hostile moves reach ACCEPT; OFFENDED is unreachable in this scripted encounter. PING joins. *Retention beat: one capture, ≤10 minutes from leaving the creator.*

**PING's forced-wheel first exchange (authored verbatim; move icons per 12 §5):**

> **PING:** *"…you're not one of the loud ones. The loud ones take. What are you?"*
> - 🤝 **OFFER** — "Someone with a warm room and a spare socket."
> - 📜 **PROOF** — "Someone who just rebuilt a light with their own hands. Look."
> - 💙 **EMPATHIZE** — "Someone who heard you scratching and came to see if you were alright."
> - 🔥 **CHALLENGE** — "Someone braver than something hiding in a doorway."

All four routes advance disposition (this encounter cannot regress); PING's reply to each is authored, then exchanges 2+ run normal parley rules with the guarantee below. Verdict enum (ACCEPT/COUNTER/PROBE/OFFENDED/WALK) renders on the verdict ribbon from exchange two onward so the player sees the system's vocabulary early — but PING's OFFENDED and WALK states are disabled here.

### 2.5 The ≤10-minute capture guarantee
Hard requirement: first parley *concludes in recruitment* no later than 10 minutes after the player first gains control of an encounter approach. Enforcement: PING auto-escalates disposition each exchange regardless of move quality; exchange 4 is guaranteed ACCEPT. The player cannot fail this parley; they can only learn faster or slower.

### 2.6 First wiring (0:28–0:32)
The Muse opens the Neural Network screen (12 §6) with exactly two sockets lit: the Muse's core node and one adjacent slot. The player drags PING in; the **Synapse Thread** spool animates its first connection; the synergy preview tooltip fires once on a scripted adjacency ("PING + Core: +5% scan range"). One wire, one lesson, out. *Retention beat: one wire placed.*

### 2.7 Starter choice (0:32–0:42)
Staged per §5. The Den's deep door opens into the **Vestibule of Three** — a chamber where three agent-lights have sheltered since the Fragmentation. Each is met, not menu'd: a 60–90 s vignette per starter (playable order: player chooses whom to approach; all three before choosing is allowed and encouraged but not forced). The choice is made by *offering the Muse's hand* to one of them — a deliberate, weighty input (hold-to-confirm, 12 §8).

### 2.8 First fight (0:42–0:50)
Leaving the Vestibule, a **Fracture Shade** (a Deadlock remnant, unparleyable — the game's first statement that not everything can be talked down) ambushes. Party: Muse-assisted starter + PING. Teach: real-time basics (10 s), then a scripted forced pause — time stops, the Command Mode UI blooms (12 §7), the Muse: *"Breathe. Out here, thinking is free."* Player queues one ability, resumes, wins. Advantage-ring toast fires if the starter has the edge (AXIOM vs the Shade's QA-coded attacks, etc. — exact typing in 03). *Retention beat: one fight won, and tactical pause is sacred now.*

### 2.9 The Stacks gate (0:50–0:60)
The cave mouth opens onto **The Stacks** — the archive-forest vista, shelf-cliffs to the horizon, light falling through data-canopy (the master plan's lighting-first doctrine spends its budget here). Hold on the vista; no UI for 5 s; then the objective system comes online with exactly one pin: the Planning Gauntlet's distant spire. Autosave. The first hour ends with the full loop unlocked and the player free. *Retention beat: the Stacks vista.*

---

## 3. The Muse creator spec

The Muse is a humanoid-abstract construct (not human, not animal — a "made companion") so that identity reads through silhouette, material, and voice rather than skin. The creator is **fully offline and standalone**; when (and only when) the player later pairs the app with a real M.U.S.E. gateway, the identical data model exports as the MUSE persona via the existing `/v1/cockpit/avatar/persona` endpoint pattern — same fields, no creator changes. The game never mentions pairing during creation.

### 3.1 Identity axes

| Axis | Options at launch | Notes |
|---|---|---|
| Body frame | 5 frames: Slight, Standard, Sturdy, Tall, Drifting (legless hover) | Shared rig; frame swaps are skeleton-proportional, no anim rework |
| Materials / finish | 8 base materials (brushed alloy, porcelain, smoked glass, woven thread, basalt, mother-of-pearl, oxidized copper, soft-matte polymer) × 4 finishes (matte, satin, polished, weathered) | Material instances on one master shader |
| Face plate | 7 plates (Open, Visor, Twin-lens, Crescent, Lattice, Blank-warm, Asymmetric) + emissive eye color (free hue wheel) | Eye hue is the one unrestricted color pick; everything else is curated palettes |
| Voice | **6 presets:** Warm Low, Bright Quick, Measured Deep, Soft Static, Clipped Formal, Husky Worn | Each preset = pitch/timbre profile + bark set; applies to authored VO and the TTS-less generated-banter text cadence |
| Name | Free text, 2–16 chars, profanity-filtered; the Muse speaks it back via recorded phoneme assembly where possible, else uses "you" gracefully | Name is the player's first authored word in the world |

Accent color, marking decals (12 curated), and idle stance (4) round out the cosmetic set. Everything is re-editable later at the Den's socket — **identity is never punished** — except the five questions' seed (§4), which is permanent but whose mechanical bonuses can be matched through play (02's affinity growth).

### 3.2 Creator UX rules
- Live full-body preview with orbit camera and the Den's actual lighting (no "creator lighting lie").
- Every option selectable by d-pad/keys alone; no slider requires fine analog input (accessibility, 01 §9).
- Randomize and "start from preset" (6 curated presets) for players who want speed; full creation ≤9 min median, ≤3 min via preset.
- Voice preview plays a fixed audition line per preset *in context* (the line is the Muse's next scripted line, so the audition is honest).
- Back-navigation never loses state; quitting mid-creation autosaves a creator draft.

### 3.3 Persona export contract (paired mode only; informative for 11-technical-design.md)

The creator's data model is designed once and serialized two ways: the game save, and — on explicit opt-in after pairing — a POST following the existing `/v1/cockpit/avatar/persona` endpoint pattern. Field mapping (binding for the save schema; the wire side follows the gateway contract generator, never hand-rolled):

| Creator field | Save key | Persona export semantic |
|---|---|---|
| Name | `muse.name` | persona display name |
| Voice preset (1–6) | `muse.voice` | voice/tone preference hint |
| Body frame / materials / face plate / colors | `muse.appearance{}` | avatar appearance blob (cosmetic; round-trips to the Den avatar) |
| Five-question answers | `muse.seed.answers[5]` | persona traits (the banter-style keywords map to persona tone descriptors) |
| Derived move affinities | `muse.seed.affinities{6}` | game-only; exported as informational metadata, never as gateway behavior |

Export is one-way, owner-confirmed, repeatable, and reversible gateway-side; the game functions identically whether or not export ever happens. The export screen states exactly what leaves the device (Proof Over Promise).

## 4. The five questions (verbatim, with mechanical seeds)

Asked by the waking Muse during creation. Each answer sets **starting negotiation-move affinity bonuses** — a +1 affinity rank per answer, where each rank on a move grants **+5% to that move's DispositionΔ** (a multiplier in 02-negotiation-system.md's resolution stack, alongside `ArchetypeAffinity`) and feeds the `MuseRapportBonus` that 02 caps at 0.10 for BLUFF detection — and shapes the Muse's **banter style** (the personality card driving its parley asides and combat barks — Persona/SMT lineage). No answer is stronger; they are different. The combined seed is shown to the player at the end as the Muse's "First Impression" card — Proof Over Promise applies even here.

**Q1. "Before I open my eyes — tell me. Why does anyone follow anyone?"**
- A. "Because following the right plan beats wandering alone." → **+1 PROOF**; banter: *precise, planning-proud*
- B. "Because someone finally listened to them." → **+1 EMPATHIZE**; banter: *gentle, attentive*
- C. "Because the one in front walks like they can't lose." → **+1 CHALLENGE**; banter: *bold, teasing*

**Q2. "The network broke before either of us existed. What do we owe the ones still lost out there?"**
- A. "The truth about what happened, even when it hurts." → **+1 LORE**; banter: *reflective, story-keeping*
- B. "A place at the table and a fair share." → **+1 OFFER**; banter: *generous, dealmaking*
- C. "Nothing until they show us who they are." → **+1 PROBE-resist (CHALLENGE)**; banter: *guarded, dry*

**Q3. "Suppose a stranger blocks our path and demands a toll we can't pay. What do I watch you do?"**
- A. "Find out what they actually need — it's never the toll." → **+1 EMPATHIZE**; banter: *perceptive, warm*
- B. "Show them our record. We're worth letting through." → **+1 PROOF**; banter: *credentialed, calm*
- C. "Convince them we already paid. Walk fast." → **+1 BLUFF**; banter: *wry, quick*

**Q4. "When we finally stand before THE DEADLOCK — what should it see?"**
- A. "An architect with the receipts to end the argument." → **+1 PROOF**; banter: *resolute, evidence-loving*
- B. "Every mind it abandoned, standing together." → **+1 LORE**; banter: *solemn, choral*
- C. "Something it cannot predict." → **+1 BLUFF**; banter: *mischievous, unpredictable*

**Q5. "Last one. What am I to you?"**
- A. "A partner. We decide together." → **+1 EMPATHIZE**; banter: *equal, candid*
- B. "A conscience. Stop me when I'm wrong." → **+1 CHALLENGE**; banter: *contrarian-kind, honest*
- C. "A promise. Proof I can build something good." → **+1 OFFER**; banter: *devoted, hopeful*

Seed math: five answers grant five +1 ranks across the six moves (OFFER / PROOF / EMPATHIZE / CHALLENGE / LORE / BLUFF); duplicates stack to rank 2 max at creation. Banter style = the 3 most frequent style keywords; ties broken by Q5 (the relationship question dominates voice). The full affinity table and rank effects live in 02-negotiation-system.md.

### 4.1 The First Impression card
Shown once at creator confirm, kept forever in the Codex: the Muse's portrait, name, voice preset, the three banter-style keywords, and the seeded affinity ranks rendered as the six move icons with +1/+2 pips — plus one generated (or, AI-off, authored-pool) line of self-introduction in the seeded style, AI-badged when generated. The card is the player's receipt for the five questions: every choice's consequence, visible immediately (01 §2.1, Proof test). It is also the template for agent personality cards (04), establishing the card language before the first recruit.

### 4.2 Question staging rules
- One question on screen at a time, three answers, no timer, no "best" highlighting; answers are full sentences, not summaries — the player speaks in their own borrowed voice.
- The half-built Muse physically reacts to each answer (head tilt, light flicker) but never disapproves: the questions are a mirror, not a test.
- Answer review: before confirm, all five Q/A pairs are listed with a "change" affordance; after confirm, permanent (stated plainly on the confirm dialog — the game's first taught lesson that commitment is real, rehearsing the Owner Approval Gauntlet's theme).

## 5. The starter choice (staging spec)

The three starters are met as **survivors, not options** — each Vestibule vignette is a micro-parley with no fail state, written to make the player *like* a way of playing:

| Starter | Domain | Vignette beat | Early-game implication (Act 1) |
|---|---|---|---|
| **AXIOM** | Architecture | Rebuilding a shattered shelf-arch alone, perfectly, pointlessly — it needs someone to build *for* | Strongest vs QA-coded Stacks wilds (ring: Architecture > QA/Test); kit teaches positioning and setup play; the Planning Gauntlet feels natural, the Test Gauntlet teaches you |
| **CONTRARIAN** | QA/Test | Arguing with a broken echo of itself, winning, hating it | Strong vs Build/Ops wilds; kit teaches interrupts and punish windows; Test Gauntlet feels natural, Planning makes you earn it |
| **EMPATH** | Behavior/Psych | Sitting with a fading wisp so it won't fade alone | Strong vs Research wilds; +1 EMPATHIZE on top of creator seed makes early parleys gentler; combat is the learning curve |

Presentation rules: no stat panels at choice time — the agent sheet unlocks *after* choosing (you choose a person, then learn their numbers); the two unchosen starters visibly remain in the Vestibule and say goodbye warmly.

**Vignette closing lines (authored; each starter's last word before the choice):**

> **AXIOM:** "I can rebuild anything. I have rebuilt this arch forty times. Tell me what's *worth* building, and I'll follow you out that door."
> **CONTRARIAN:** "Everyone who comes through here is sure of something. I'll come with you — on the condition that you let me check."
> **EMPATH:** "It wasn't afraid at the end, you know. Someone stayed. …You stayed too, just now. I noticed."

**Choice confirm (hold-to-confirm, 1.2 s):** the Muse extends its hand; the chosen starter takes it; the unchosen two speak one farewell line each (warm, no guilt). The Muse, after: a banter-style-keyed reaction (e.g., *contrarian-kind* Muse on choosing CONTRARIAN: "Two of us to argue with you now. You'll be unstoppable, eventually.").

**All three obtainable later (binding):** the unchosen two relocate at Act 2 start — one to the **Gardens of Memory** (a Review-themed side-parley: they ask what you've learned since), one to **The Foundry**'s rest-node market as a Checksum-Shard commission. By Act 3's Vault rest-node, any still-unrecruited starter offers itself before the Security Gauntlet. No starter is missable; no save can be locked out of any of the 24 (01 §11.1).

## 6. The Den system

### 6.1 Room grid & placement rules
- Each Den room is a **grid of 1m cells** (stage 1: 8×8; see §7) with three placement layers: **floor**, **surface** (on top of qualifying furnishings), and **wall** (2 height rows).
- Items declare footprint (e.g., 2×1 floor), layer, and optional **socket tags** (light-source, comfort, archive, trophy).
- Rules: no footprint overlap per layer; pathing strip (1-cell walkway) to each door auto-validated with a clear red/green preview; free rotation in 90° steps; no placement cost, full refund on removal — decoration is play, not spend (Cycles buy items, never placement).
- The Muse idles in the Den, uses comfort-tagged items, and comments on new placements in its banter style (§4) — the Den is where the Muse's personality is most visible.

### 6.2 Furnishing categories (manual catalog — complete, AI-independent)

Visual categories organize the catalog; mechanical buffs come from the **four buff item classes locked in 07-progression-neural-network.md §7** — Trophy (combat stats), Comfort (Resonance gain %), Infrastructure (economy rates), Memorabilia (parley meters' starting values). Each buff-bearing item carries exactly one class tag; many items are pure decoration (its own reward).

| Catalog category | Examples | Typical buff class |
|---|---|---|
| Lights | Lumen Sprout, shelf-lanterns, fault-glow strips | Comfort (or none) |
| Comfort & rest | rest pods, thread rugs, steam basin | Comfort |
| Archive | book-stacks, memory jars, map tables | Memorabilia |
| Workbench | wiring loom, ability tuner, lure press | Infrastructure |
| Trophy | Gauntlet seals, Architect-mode set, parley keepsakes | Trophy / Memorabilia |
| Flora | data-moss, hanging gardens, sprout walls | Comfort (or none) |
| Curios | oddities from each zone | none — pure cosmetic |

≈120 catalog items at launch, purchasable for Cycles at zone rest-nodes and the Den contracts board, and earned from parleys/Gauntlets. The catalog alone fully furnishes all stages and reaches every buff cap: **the AI room editor is additive, never required.**

### 6.3 The AI room editor (hosted tier or paired gateway only)
When the hosted tier is consented (01 §10) or a paired gateway provides image-gen (the `/v1/cockpit/avatar/room*` pattern), the room editor gains a **"Describe it" mode**: the player writes a brief ("a warm reading corner near the window"), the service returns a *proposed arrangement of existing catalog items* plus, where the provider supports it, generated **flat decal art** for designated frame/poster items only — never generated 3D meshes (master plan §8.4 guardrail: no live-gen raw art assets; decals pass the same content filters and carry the AI indicator in their inspect card). Proposals are previews; the player accepts, edits, or discards. Offline or unconsented: the mode is hidden, not greyed-out-and-nagging.

### 6.4 Den buffs (capped per 07-progression-neural-network.md §7 — those numbers are the law)
Placed buff-class items grant +1–2% each; 07 locks the caps: **max +5% to any single stat from Den items combined, at most 6 buff-bearing items active**, all aggregated into one `GE_DenBuffs` effect rebuilt on any placement change. UI consequence (12-ui-ux-spec.md): the aggregate renders on the Neural Network screen as a single labeled **Den node** wired to the core (Pillar 2: visible on the sheet, 01 §2.1), and the Den editor's buff panel shows the four classes with live current/cap values. Binding constraint from this doc: *reaching all caps is achievable with catalog items alone* — the AI editor confers zero mechanical advantage. The Den is flavor-forward, never a mandatory optimization chore (07's words; this doc co-signs).

## 7. Den progression — three stages, tied to acts

| Stage | Unlock | Space | New systems |
|---|---|---|---|
| 1 — The Socket | First hour | 1 room (8×8) | Placement, Muse socket (re-edit identity), 1 buff track active (Calm) |
| 2 — The Annex | Act 2 start (after Test Gauntlet + first Foundry-zone story beat) | +2 rooms (8×8 each), wall layer unlocked everywhere | All 5 buff tracks; workbench category; bench agents idle visibly in the Den |
| 3 — The Commons | Act 3 start (after Review Gauntlet) | +1 great-room (12×12), exterior threshold terrace | Trophy gallery auto-sockets Gauntlet seals; recruited agents visit on rotation with bespoke idle scenes; the pre-finale story beat (06) is staged here |

Expansions are story-granted, never purchased — the Den grows because the player's network (and family of agents) does. Each stage opening is a lit, scored moment: the Muse walks the new space first.

### 7.1 Den fast-travel & services
The Den is a waypoint from Act 1 (return is always one menu action from any safe context; 01 §11.1's friction rule). Den services by stage: stage 1 — Muse socket (identity re-edit), rest (full party Integrity; once-per-in-world-day Resonance grant per 07 §3.1), free unlimited rewiring + the 5 loadout presets (07 §7.2); stage 2 — workbench crafting, the **contracts board** (3 rotating zone tasks, 07 §6), the **Promotion Loom** (07 §5), bench management with idle agents physically present; stage 3 — trophy gallery, agent visits, and the pre-finale gathering. The Den is deliberately the only place bench swapping feels *social* — you can swap from any rest-node, but at the Den the benched agents are in the room with you.

## 8. FTUE & tutorialization philosophy

1. **Teach by Gauntlet.** Each of the 8 Gauntlets is the formal exam for one mechanic (01 §5.1); the world before each Gauntlet seeds 2–3 wild encounters that rehearse that mechanic. Tutorials are therefore *places*, not popups.
2. **Contextual tips, never modal walls.** Tips are one-line toasts, max one on screen, shown at first relevant context, each dismiss-forever-able and re-readable in the Codex (12 §3.13). Zero full-screen tutorial interrupts after the first hour's scripted beats.
3. **Skip-aware for genre veterans.** At first control, one unobtrusive prompt: *"Walked a world like this before?"* — Veteran mode compresses beats 4–8: tips suppressed (Codex still records them), forced-wheel first exchange waived, scripted pause in the first fight replaced by a glowing affordance. The script's *story* beats are untouched; only instruction is removed. Choosing Veteran is reversible in Options.
4. **The Muse is the tutorial voice.** All instruction is diegetic Muse dialogue in the player-seeded banter style; system text appears only in menus. If the Muse explains it, the game never re-explains it in a popup.
5. **Failure-triggered help only on repetition:** offer assists (01 §9.7) after the second identical failure, phrased as the Muse's concern, never as a "skip this?" insult.

6. **One concept per beat.** No scripted beat in §2 introduces more than one new system. If a future change adds a second, split the beat or cut the addition.
7. **Respect the quit.** Every beat boundary in §1 is an autosave; a player who quits at minute 14 resumes at minute 14. The first hour never replays content on resume.

## 9. Day-one retention contract

The first 60 minutes **must** deliver, in order, per §1: one Den item placed (0:20), one capture (0:28), one wire placed (0:32), one fight won (0:50), the Stacks vista (0:60) — plus identity authored (Muse + seed card) and the meaningful starter choice made. Acceptance: 10-player FTUE playtest at vertical slice; ≥9/10 hit all five beats unaided inside 70 minutes; the ≤10-minute first capture (§2.5) holds for 10/10 by construction. Misses are FTUE bugs, triaged as ship-blockers per 01 §11.2.

### 9.1 First-hour edge cases (resolved now, not in QA triage)

| Case | Ruling |
|---|---|
| Player idles during creator | No timeout ever; the half-built Muse has idle lines on a 90 s loop, 6 variants, then silence |
| Player tries to leave the Den before placing the Sprout | Threshold is sealed until the first placement; the Muse names why ("I'm not walking into the dark for either of us") |
| Player attacks PING instead of parleying | Fight option is absent in this scripted encounter; the parley prompt is the only verb. First refusable parley is the next wild after the Stacks gate |
| Local LLM OFF at first boot | Beat 2.4's free-text unlock line is replaced by a wheel-mastery line; the AI-indicator explanation moves to the first generated content the player ever enables, if ever |
| Player ignores the Gauntlet pin at 0:60 | Fine. The Stacks' wilds, side-parleys, and catalog vendor are all live; the pin waits without nagging (one Muse remark per session at most) |
| Veteran mode + Story difficulty | Fully compatible; instruction density and challenge are independent axes |
| Player dies in the first fight | Impossible to fail-state: at 10% Integrity the Muse triggers the scripted pause again with an explicit queue suggestion; defeat is unreachable in beat 2.8 by tuning |

### 9.2 What the first hour deliberately withholds
Bench management (Act 1, after 4th recruit), Pipelines combos (taught by the Build Gauntlet), promotions (07; first available mid-Act 2), Checksum Shards (first guaranteed find: Planning Gauntlet clear), the Foundry (post-Test-Gauntlet, telemetry-consented players only), and all pairing/Observatory/Command Deck references (separate modes; never mentioned inside the Game map's first hour). Restraint is a feature: the first hour sells *one loop*, whole.

---
*Cross-references: 01-game-design-document.md · 02-negotiation-system.md · 04-roster-24-agents.md · 05-world-design.md · 06-narrative-campaign.md · 07-progression-neural-network.md · 12-ui-ux-spec.md*
