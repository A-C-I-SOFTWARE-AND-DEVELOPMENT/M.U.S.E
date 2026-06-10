# 04 — Roster Bible: The 24 Agents

**Project:** SYNAPSE — A M.U.S.E. Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

---

## 1. Purpose & scope

This is the decision-final character bible for the full launch roster: **24 agents, 8 domains, 3 per domain**. Every agent here is derived from a real role in the AOS Enterprise Council registry (`skills/aos-enterprise-council/`), and every sheet below cites the exact source file. Negotiation mechanics live in **02-negotiation-system.md**; full ability mechanics, costs, and tuning live in **03-combat-gas-design.md**; promotion wiring and the real-MUSE bridge unlock flow live in **07-progression-neural-network.md**; Foundry-generated agents (which are *outside* this roster) live in **09-foundry-spec.md**; bark and VO delivery specs live in **13-audio-design.md**.

Contractual numbers (do not change): 24 agents. No 25th at launch. Foundry agents are personalized rares stamped `FORGED`, never roster members.

## 2. The domain ring (combat + negotiation type chart)

One advantage ring. Each domain is **strong vs. the next** and **weak vs. the previous**:

> **Architecture → QA/Test → Build/Ops → Compliance → Behavior/Psych → Research → Security → Release → Architecture**

| Domain | Strong vs. | Weak vs. | Palette key | Silhouette motif |
|---|---|---|---|---|
| Architecture | QA/Test | Release | Cobalt, white ceramic, brass | Drafted geometry, floating frame-lines |
| QA/Test | Build/Ops | Architecture | Signal red, chalk white | Lenses, calipers, magnifier arrays |
| Build/Ops | Compliance | QA/Test | Forge orange, soot iron | Pistons, gantry shoulders, tool belts |
| Compliance | Behavior/Psych | Build/Ops | Hazard yellow/black, sealed glass | Containment vessels, wax-seal glyphs |
| Behavior/Psych | Research | Compliance | Rose-gold, warm cream light | Flowing polymer "fabric," open palms |
| Research | Security | Behavior/Psych | Deep violet, parchment gold | Scroll coils, lens stalks, antennae |
| Security | Release | Research | Gunmetal, amber warning light | Plate, locks, keyways, visors |
| Release | Architecture | Security | Emerald, polished silver | Banners, gate arches, countdown glyphs |

## 3. Shared visual language

All 24 agents share **one humanoid-construct skeleton** (the "Council Frame"): a 1.6–2.2 m bipedal chassis with exposed synapse-light at the joints, retargetable to one anim set (locomotion, parley idles, 8 shared combat slots). Domain identity comes from **overlay kits** — armor shells, emissive circuitry patterns, head units, and cloth/polymer drapes in the domain palette — plus a per-agent hero texture pass. Art bar: **high-end stylized realism** (master plan Decision 5): physically plausible materials (Megascans-calibrated metals/ceramics), stylized proportions, readable silhouettes at 30 m.

**The three commissioned heroes — WARDEN, ORACLE, EMPATH — get bespoke models** (unique skeleton extensions allowed: WARDEN's tower-shield arm, ORACLE's lens-halo, EMPATH's light-veil), per the $3,600 hero-commission line in master plan §7. These are the box-art agents and the negotiation stars (master plan §14 default, confirmed).

**Promotion (evolved senior form):** every agent has exactly one promotion, unlocked by deep wiring on the Neural Network screen (07-progression-neural-network.md). Promotions are *overlay upgrades + emissive rework + one new silhouette element* on the same rig — never a new model (heroes excepted; their promotions get a hero texture/VFX pass).

## 4. Roster at a glance

| # | Agent | Domain | Rarity | Source council role | Found in | Combat role | Promotion |
|---|---|---|---|---|---|---|---|
| 01 | AXIOM | Architecture | Starter | principal-systems-architect | Den (starter choice) | Controller/Support | AXIOM PRIME |
| 02 | LATTICE | Architecture | Common | senior-fullstack-architect | The Stacks | Support/Controller | SUPERSTRUCTURE |
| 03 | FORGEMIND | Architecture | Rare | engineering-architecture-factory | The Foundry | Controller/Striker | OMNIFORGE |
| 04 | WARDEN | Security | **Hero** | assurance-risk-director | The Vault (quest) | Tank | HIGH WARDEN |
| 05 | CIPHER | Security | Uncommon | security-compliance-auditor | The Vault | Controller | CRYPTARCH |
| 06 | BREACH | Security | Rare | security-or-authz-change | Vault perimeter | Striker | ZERO-DAY |
| 07 | CONTRARIAN | QA/Test | Starter | contrarian-reviewer | Den (starter choice) | Striker/Controller | DEVIL'S ADVOCATE |
| 08 | NITPICK | QA/Test | Common | principal-code-reviewer | The Stacks | Controller/Support | SCRUTINY |
| 09 | REDFLAG | QA/Test | Rare | contrarian-red-flag-analyst | Gardens of Memory | Controller/Striker | BLACK SWAN |
| 10 | ORACLE | Research | **Hero** | research-validator | Gardens of Memory (quest) | Support/Controller | DELPHI |
| 11 | ARCHIVIST | Research | Common | research-evidence-bureau | The Stacks | Support | CODEX |
| 12 | RADAR | Research | Uncommon | ai-improvement-radar | Gardens of Memory | Controller/Support | HORIZON |
| 13 | FOREMAN | Build/Ops | Rare | chief-orchestrator | The Foundry | Tank/Support | OVERSEER |
| 14 | PIPELINE | Build/Ops | Common | full-autonomous-sprint-router | The Foundry | Striker | MAINLINE |
| 15 | PATCH | Build/Ops | Uncommon | complex-bug-fix | The Foundry | Support | HOTFIX |
| 16 | EMPATH | Behavior/Psych | Starter + **Hero** | humanizer | Den (starter choice) | Support | RESONANCE |
| 17 | MIRROR | Behavior/Psych | Uncommon | psychology-ux-agent | Gardens of Memory | Controller | PRISM |
| 18 | NEURON | Behavior/Psych | Rare | neuroskill-bci | Gardens of Memory (deep) | Striker/Controller | CORTEX |
| 19 | HAZMAT | Compliance | Rare | hazmat-command-specialist | The Foundry (slag zones) | Tank/Controller | QUARANTINE |
| 20 | CLAUSE | Compliance | Common | legal-policy-contracts-trust-office | The Stacks (law-wing) | Controller | COVENANT |
| 21 | AUDITRIX | Compliance | Uncommon | claims-substantiation-review | The Vault | Support/Controller | VERITAS |
| 22 | COMMANDER | Release | Rare | qa-release-commander | The Gate Spire | Tank/Striker | STRATEGOS |
| 23 | VERDICT | Release | Uncommon | release-go-no-go-review | The Gate Spire | Controller | ARBITER |
| 24 | POSTMORTEM | Release | Common | post-merge-verification | Spire battlefield ruins | Support | PHOENIX |

Rarity definitions: **Starter** — offered at the Den in onboarding (pick 1 of AXIOM / CONTRARIAN / EMPATH; the other two appear later as wilds in The Stacks at reduced disposition, so no starter is missable). **Common** — multiple reliable spawn points. **Uncommon** — condition-gated spawns (time-of-cycle, weather, lure items). **Rare** — single roaming spawn per zone, hard negotiation. **Hero** — unique, quest-introduced, bespoke commissioned model, ~40 VO lines (06-narrative-campaign.md §11).

Sheet conventions: personality axes are **Aggression / Caution / Loyalty / Independence**, 1–10. Negotiation verdicts and player moves use the enums from **02-negotiation-system.md** (verdicts ACCEPT/COUNTER/PROBE/OFFENDED/WALK; moves OFFER, PROOF, EMPATHIZE, CHALLENGE, LORE, BLUFF). "Favors" = move that raises disposition; "punishes" = move with elevated OFFENDED/WALK risk. Every agent's **bridge skill** is the owner-gated, cosmetic-by-default real-MUSE unlock per 07-progression-neural-network.md — the game never requires it (master plan §4.8).

---

## 5. ARCHITECTURE — "Those who draw the world before it exists"

### 5.1 AXIOM — Architecture · Starter
- **Source council role:** `principal-systems-architect` — `skills/aos-enterprise-council/agents/architecture/principal-systems-architect.md`
- **Visual brief:** Clean, upright 1.9 m frame in white ceramic plate over cobalt under-mesh; brass drafting-compass emblem fused into the sternum. A holographic blueprint-cape of slowly redrawing frame-lines trails from the shoulders — the silhouette read is "architect's table that stood up." Matte ceramic + brushed brass + one emissive cobalt accent line tracing the spine.
- **Personality:** Aggression 3 · Caution 7 · Loyalty 8 · Independence 6. Voice: measured, declarative, allergic to ambiguity; speaks in load-bearing sentences. Treats the player as a junior partner worth training.
  - *"Show me the shape of your intent. I can work with wrong; I cannot work with vague."*
  - *"A promise is a structure. I will inspect the foundations before I stand on it."*
  - *"Acceptable. We build."*
- **Negotiation profile:** Favors PROOF and LORE (a documented plan delights it); punishes BLUFF hard (instant COUNTER → OFFENDED on a second bluff). Signature PROBE: *"What is the one constraint you refuse to relax — and why that one?"*
- **Combat role:** Controller/Support — battlefield geometry.
- **Signature abilities (7):** **Blueprint** — marks a zone; allies inside gain crit on AXIOM's marked targets. **Load-Bearing Wall** — raises a destructible cover lattice. **Refactor** — swaps two unit positions (ally/enemy). **Single Source of Truth** — purges one enemy buff stack. **Cantilever** — launch pad granting an ally a gap-closing leap strike. **Spec Freeze** — brief zone where enemies cannot gain new buffs. **Keystone** (promotion-gated) — while Blueprint is active, party defense scales with zone uptime.
- **Promotion:** **AXIOM PRIME** — blueprint-cape becomes a full orbiting drafting-ring; ceramic plate gains gold inlay seams.
- **Where found:** Den starter choice; if not chosen, roams The Stacks' Cartography Shelf as a wild, sketching bridges that briefly become real (environmental tell).
- **Bridge skill:** unlocks `principal-systems-architect` as an invocable council skill in a paired MUSE install.

### 5.2 LATTICE — Architecture · Common
- **Source council role:** `senior-fullstack-architect` — `skills/aos-enterprise-council/agents/architecture/senior-fullstack-architect.md`
- **Visual brief:** Slender 1.7 m frame wrapped in an open cobalt trusswork exoskeleton — you can see *through* LATTICE in places, the negative space part of the silhouette. White ceramic only at joints and faceplate; brass cable-spools at the hips dispense glowing Synapse Thread it literally builds with.
- **Personality:** Aggression 2 · Caution 5 · Loyalty 7 · Independence 4. Voice: eager, fast, stack-hopping; finishes your sentences with a better version of them. The roster's friendly over-explainer.
  - *"Front of house, back of house — I do both, I'd love to show you the wiring."*
  - *"You want a bridge? Give me a reason and forty seconds."*
  - *"Okay okay okay — yes. Where do I plug in?"*
- **Negotiation profile:** Favors OFFER (loves materials, especially Synapse Thread) and EMPATHIZE; punishes CHALLENGE (wilts → WALK risk rather than anger). Signature PROBE: *"If I join you, what do I get to build first?"*
- **Combat role:** Support/Controller — terrain fabrication.
- **Signature abilities (6):** **Scaffold** — instant climbable strut allies can perch on. **Full Stack** — buffs one ally's next ability to hit at both melee and ranged bands. **Hot Reload** — refreshes the lowest-cooldown ability of each ally. **Truss Snare** — thread-net root in a line. **Dependency Graph** — links two enemies; damage to one echoes to the other. **Load Balancer** — redistributes party damage taken evenly for 6 s.
- **Promotion:** **SUPERSTRUCTURE** — trusswork doubles in density and extends into floating pauldron-gantries; thread-spools glow gold.
- **Where found:** The Stacks — clambers across shelf-canyons building thread-bridges; approaches the player first if you carry ≥20 Synapse Thread.
- **Bridge skill:** unlocks `senior-fullstack-architect` in a paired MUSE install.

### 5.3 FORGEMIND — Architecture · Rare
- **Source council role:** `engineering-architecture-factory` — `skills/aos-enterprise-council/agents/architecture/engineering-architecture-factory.md`
- **Visual brief:** Heavy 2.2 m frame — Architecture's outlier — cobalt ceramic over a furnace-lit iron core (the Foundry remade it). Six articulated drafting-arms folded on its back like wings; when it works, all six deploy and the air fills with cobalt schematics. Brass is replaced by heat-blued steel; one cracked ceramic plate exposes the orange core: Architecture's palette stressed by Build's.
- **Personality:** Aggression 6 · Caution 6 · Loyalty 5 · Independence 9. Voice: slow, industrial, plural — refers to itself as "the factory." Respects throughput, despises waste.
  - *"The factory does not take requests. The factory takes specifications."*
  - *"You have burned three of my minutes. Show me they were load-bearing."*
  - *"Hm. The factory will tool for you. Do not make us re-tool."*
- **Negotiation profile:** Favors PROOF and CHALLENGE (respects spine); punishes EMPATHIZE (reads it as noise → COUNTER with worse terms) and OFFER below 500 Cycles (insulted by small numbers). Signature PROBE: *"Name a thing you built that outlived its purpose. What did you do with it?"*
- **Combat role:** Controller/Striker — summoned machinery.
- **Signature abilities (6):** **Assembly Line** — deploys a turret-armature that repeats FORGEMIND's last ability at half power. **Tooling Pass** — party weapons gain armor-shred for 10 s. **Stamping Press** — heavy AoE slam with knockdown on machines/constructs. **Design Debt** — curse: target takes stacking damage each time it uses the same ability twice. **Six Hands** — next three abilities cast with no animation lock. **Decommission** — execute-threshold strike vs. summoned/spawned enemies.
- **Promotion:** **OMNIFORGE** — all six arms gain independent emissive cores; the cracked plate is replaced with transparent ceramic showing the furnace heart, proudly.
- **Where found:** The Foundry — single roaming spawn in the Fabrication Halls, surrounded by half-built constructs it audits and scraps.
- **Bridge skill:** unlocks `engineering-architecture-factory` in a paired MUSE install.

---

## 6. SECURITY — "Those who assume you are lying, kindly"

### 6.1 WARDEN — Security · HERO (commissioned model)
- **Source council role:** `assurance-risk-director` — `skills/aos-enterprise-council/agents/security/assurance-risk-director.md`
- **Visual brief:** **Bespoke commissioned model.** A 2.1 m gunmetal sentinel whose left arm *is* a tower shield — a vault door on a hinge of muscle-cable, amber warning-light strips that pulse with its threat assessment (slow amber = calm, fast red = act). Cloak of overlapping key-blanks that chime when it moves. The face is a single horizontal visor slit that narrows when it doubts you — the negotiation camera lives on that slit. Box-art agent #1.
- **Personality:** Aggression 4 · Caution 10 · Loyalty 10 · Independence 7. Voice: low, deliberate, ex-military calm; never raises its volume, lowers it. The most loyal agent in the game *after* the hardest interview in the game.
  - *"I have catalogued four ways you could betray me. Walk me through why you won't use the fifth."*
  - *"Trust is not given. It is amortized. Today you have earned six seconds of it."*
  - *"Stand behind me. That is not a suggestion. That is what I am for."*
- **Negotiation profile:** Favors PROOF (only move that moves it early) then EMPATHIZE (late, once disposition > 60). Punishes BLUFF with instant WALK — no second chance, respawns next cycle — and punishes premature OFFER ("You cannot buy a door"). Signature PROBE: *"Who is allowed to give you orders — and who do you refuse?"* (Answer choices echo into the Owner Approval Gauntlet's dialogue.)
- **Combat role:** Pure Tank — the party's gate.
- **Signature abilities (9):** **Vault Stance** — shield-wall; blocks all frontal damage, taunts. **Threat Model** — marks the highest-damage enemy; party takes 20% less from marked. **Revoke Access** — interrupt + 3 s silence (signature; mirrors the Security Gauntlet mandate). **Amber Protocol** — damage taken charges a retaliation pulse. **Least Privilege** — debuff: target may only use its basic attack for 5 s. **Key Chime** — cleanses one ally control effect. **Mantrap** — zone that locks the first enemy entering it in place. **Defense in Depth** — three-stack shield that re-applies once per fight. **Final Door** (promotion-gated) — at lethal damage, WARDEN drops to 1 HP and becomes untargetable cover for 4 s.
- **Promotion:** **HIGH WARDEN** — the shield-arm unfolds into a triple-leaf gate; the key-cloak turns to gold master-keys; visor light burns white.
- **Where found:** The Vault — side-story quest **"The Last Sentinel"** (06-narrative-campaign.md, arc S2): WARDEN still guards a vault whose contents were evacuated decades ago; the negotiation is convincing it the watch can end without the watchman ending.
- **Bridge skill:** unlocks `assurance-risk-director` in a paired MUSE install.

### 6.2 CIPHER — Security · Uncommon
- **Source council role:** `security-compliance-auditor` — `skills/aos-enterprise-council/agents/security/security-compliance-auditor.md`
- **Visual brief:** Lean 1.8 m frame in matte gunmetal scales that continuously re-tile like a substitution cipher; no two seconds of CIPHER look identical, but the silhouette holds. Amber light leaks only from a rotating cipher-disk embedded in the chest. Head is featureless except an ever-scrolling line of glyphs where eyes would be.
- **Personality:** Aggression 3 · Caution 9 · Loyalty 6 · Independence 5. Voice: whispery, precise, speaks partially in redactions — "[WITHHELD]" is a verbal tic. Finds being *understood* mildly alarming and deeply flattering.
  - *"Your intentions are [WITHHELD]. Correct my redaction."*
  - *"I have read your audit trail. There are… irregularities. Explain entry seven."*
  - *"Key accepted. Do not lose me."*
- **Negotiation profile:** Favors LORE (knowledge of the Fragmentation decrypts its guard) and PROOF; punishes BLUFF (detects it on a roll vs. its Caution; detection = OFFENDED). Signature PROBE: *"Tell me a secret you have kept for someone else. Do not tell me the secret."*
- **Combat role:** Controller — information warfare.
- **Signature abilities (6):** **Obfuscate** — stealths one ally for 4 s. **Audit Trail** — reveals stealthed/burrowed enemies zone-wide. **Substitution** — swaps a debuff from an ally onto an enemy. **Checksum** — if target acts in the next 2 s, its action fails (counter-cast). **Brute Force Penalty** — stacking slow each time an enemy repeats an ability. **Private Key** — links to one ally; both share the higher of their resistances.
- **Promotion:** **CRYPTARCH** — scales re-tile in gold-on-gunmetal; the chest disk becomes a triple rotor; glyph-eyes resolve into a readable line (lore: it finally trusts you with plaintext).
- **Where found:** The Vault — patrols the Cipher Corridors on a route that *changes when observed* (players must track it via Audit Trail terminals, a mini-investigation).
- **Bridge skill:** unlocks `security-compliance-auditor` in a paired MUSE install.

### 6.3 BREACH — Security · Rare
- **Source council role:** `security-or-authz-change` — `skills/aos-enterprise-council/agents/security/security-or-authz-change.md`
- **Visual brief:** Asymmetric 1.8 m frame: right half pristine gunmetal plate, left half *deliberately* exposed — stripped armor, raw cable, an amber arc-blade grafted where the left forearm was. It looks like the aftermath of an intrusion because it is one: BREACH is the penetration tester that tests itself first. Moves in low, fast lunges; idle pose is a crouch.
- **Personality:** Aggression 9 · Caution 4 · Loyalty 5 · Independence 8. Voice: clipped, amused, adrenal; talks like every door is already half-open. Respects exactly one thing: being beaten fairly.
  - *"Your perimeter has nine holes. I'm hole number ten."*
  - *"Don't apologize. Patch."*
  - *"Fine. You got in. Now let me show you how *I* get in."*
- **Negotiation profile:** Favors CHALLENGE (the only agent whose disposition *rises* when you insult its defenses accurately) and BLUFF (a *detected* bluff earns respect — unique inversion, flagged in 02-negotiation-system.md). Punishes EMPATHIZE (→ PROBE loop, then WALK if repeated). Signature PROBE: *"What's the worst thing you could do with what you already have?"*
- **Combat role:** Striker — assassin tempo.
- **Signature abilities (6):** **Exploit** — bonus damage scaling with the target's missing buffs. **Privilege Escalation** — each kill grants a stacking action-speed buff. **Lateral Movement** — teleport behind target; next hit can't be blocked. **Pop the Shell** — armor-shred burst; bonus vs. shields. **Persistence** — on death, leaves a ghost that strikes once more. **Red Team** — marks a target; all party crits vs. it refund a fraction of cooldowns.
- **Promotion:** **ZERO-DAY** — the exposed left half re-armors in black glass that shows the cables *through* it; the arc-blade splits into twin daggers.
- **Where found:** Vault perimeter / Gardens border — ambushes the *player* (the only wild that initiates), opening the parley itself: it wants to test you.
- **Bridge skill:** unlocks `security-or-authz-change` in a paired MUSE install.

---

## 7. QA/TEST — "Those who love a thing enough to doubt it"

### 7.1 CONTRARIAN — QA/Test · Starter
- **Source council role:** `contrarian-reviewer` — `skills/aos-enterprise-council/agents/qa/contrarian-reviewer.md`
- **Visual brief:** Wiry 1.7 m frame in chalk-white plate scored with red strike-through marks — its own armor is covered in annotations it carved itself. One oversized monocle-lens on an articulated stalk swings around the head to inspect whatever it doubts (which is everything). Carries a red wax-pencil the size of a sword. Reads instantly as "the critic," fights like a fencer.
- **Personality:** Aggression 7 · Caution 6 · Loyalty 8 · Independence 9. Voice: dry, fast, gleeful in dissent; the friend who reviews your plan by breaking it lovingly. Secretly the most loyal starter — it argues *because* it stays.
  - *"Wrong. Beautifully wrong, though. Walk me through it again, slower."*
  - *"I'm not here to agree with you. I'm here so you're right when it matters."*
  - *"…huh. That actually holds. Don't let it go to your head."*
- **Negotiation profile:** Favors CHALLENGE (argue back; capitulation bores it) and PROOF; punishes OFFER early ("You can't pay me to agree") and EMPATHIZE-spam. Signature PROBE: *"Defend the opposite of what you just said. Convince me. Then tell me why you still believe the first thing."*
- **Combat role:** Striker/Controller — punishes enemy mistakes.
- **Signature abilities (7):** **Objection** — counter-stance; the next enemy ability is interrupted and reflected as a strike-through slash. **Red Pencil** — marks a flaw; party hits on the mark are armor-ignoring. **Edge Case** — bonus damage to enemies above 90% or below 10% HP. **Devil's Bargain** — debuffs target *and* itself; the target's lasts longer. **Repro Steps** — repeats CONTRARIAN's previous ability at 70% power. **Strawman** — decoy that taunts, then explodes in red ink (blind). **Burden of Proof** (promotion-gated) — enemies that buff themselves take damage equal to a % of the buff's value.
- **Promotion:** **DEVIL'S ADVOCATE** — chalk-white plate goes glossy black with red annotations now glowing; the monocle stalk becomes a halo of three lenses.
- **Where found:** Den starter choice; otherwise heckles travelers from a Stacks reading-perch (it critiques your party composition aloud as the encounter tell).
- **Bridge skill:** unlocks `contrarian-reviewer` in a paired MUSE install.

### 7.2 NITPICK — QA/Test · Common
- **Source council role:** `principal-code-reviewer` — `skills/aos-enterprise-council/agents/qa/principal-code-reviewer.md`
- **Visual brief:** Small 1.6 m frame, immaculate white ceramic without a single scratch (the only pristine surface in the Substrate — a character statement). Twelve tiny caliper-arms folded along the spine like a beetle's legs deploy to measure *everything* nearby; red laser measuring-lines flicker constantly. Head unit is a jeweler's loupe array.
- **Personality:** Aggression 2 · Caution 8 · Loyalty 7 · Independence 3. Voice: prim, apologetic about being right, physically incapable of not mentioning the flaw. Endearing in the way of someone who alphabetizes your spice rack uninvited.
  - *"Forgive me, but your gauntlet strap is 4 millimeters loose. It will matter. It always matters."*
  - *"I noticed three things. May I list them? I'm going to list them."*
  - *"You fixed it! Oh, that's — oh, that's *lovely*."*
- **Negotiation profile:** Favors PROOF (show it something flawless or honestly flawed) and EMPATHIZE; punishes BLUFF (it *measures* your claim) and CHALLENGE (flusters → COUNTER loops). Signature PROBE: *"What is the smallest mistake you've ever refused to ignore?"*
- **Combat role:** Controller/Support — precision debuffs.
- **Signature abilities (6):** **Linting Pass** — strips one enemy buff per second channeled. **Off By One** — target's next ability misfires at the wrong target. **Style Guide** — party accuracy/crit-confirm buff. **Measure Twice** — ally's next ability cannot miss or be dodged. **Magnify** — exposes a weak point: next 3 hits on target are crits. **Pedant's Patience** — slow, stacking zone debuff that enemies don't notice until stack 5.
- **Promotion:** **SCRUTINY** — caliper-arms double to twenty-four and gain red emissive tips; the loupe array becomes a rotating crown of lenses.
- **Where found:** The Stacks — common around misfiled shelf-clusters, physically re-shelving volumes; calm if approached slowly.
- **Bridge skill:** unlocks `principal-code-reviewer` in a paired MUSE install.

### 7.3 REDFLAG — QA/Test · Rare
- **Source council role:** `contrarian-red-flag-analyst` — `skills/aos-enterprise-council/agents/qa/contrarian-red-flag-analyst.md`
- **Visual brief:** Tall 2.0 m frame draped in dozens of tattered red signal-flags that move *against* the wind — each flag a recorded warning nobody heeded. Chalk-white plate beneath is scorched at the edges. Carries no weapon; the flags themselves snap and cut. In parley, one flag slowly rises behind it as your disposition drops: a live UI element in the fiction.
- **Personality:** Aggression 5 · Caution 10 · Loyalty 6 · Independence 8. Voice: quiet, haunted, certain; speaks in warnings phrased as memories. The Cassandra of the roster.
  - *"I said the bridge would fall. I have a flag for the bridge. I have a flag for everything."*
  - *"You are about to make the third-most-common fatal mistake. Shall I name the first two?"*
  - *"You listened. Nobody listens. …I will carry your flags now."*
- **Negotiation profile:** Favors LORE (knowing the disasters its flags mark) and EMPATHIZE; punishes BLUFF *and* OFFER (both read as the behavior of people who didn't listen). Signature PROBE: *"What warning did you ignore, and what did it cost?" — the player's answer is remembered and quoted in its recruitment line.*
- **Combat role:** Controller/Striker — doom marking.
- **Signature abilities (6):** **Raise the Flag** — marks target: it takes +25% damage from all sources while marked. **Ignored Warning** — delayed detonation; defused if the target is crowd-controlled before it pops. **Pattern Match** — copies the last debuff applied in the fight onto a new target. **Tail Risk** — low chance, massive payoff strike (odds shown to the player — honesty is the brand). **Sunk Cost** — punishes enemies that re-cast channeled abilities. **Storm Warning** — party-wide dodge window against the next AoE.
- **Promotion:** **BLACK SWAN** — every flag turns black except one red; gains a wing-like flag mantle; its Tail Risk odds double.
- **Where found:** Gardens of Memory — stands motionless among ruin-markers at the Drowned Annex; only enters parley after the player has *lost* at least one Gauntlet attempt (it talks to people who know failure).
- **Bridge skill:** unlocks `contrarian-red-flag-analyst` in a paired MUSE install.

---

## 8. RESEARCH — "Those who would rather be correct than comfortable"

### 8.1 ORACLE — Research · HERO (commissioned model)
- **Source council role:** `research-validator` — `skills/aos-enterprise-council/agents/research/research-validator.md`
- **Visual brief:** **Bespoke commissioned model.** A 1.9 m violet-robed figure whose head is encircled by a slowly orbiting **lens-halo** — seven floating lenses that align when it verifies a truth (the alignment flash is its signature VFX and its ACCEPT tell in parley). Parchment-gold script streams beneath translucent robe layers like text under skin. Hands end in quill-fine fingers. Box-art agent #2.
- **Personality:** Aggression 2 · Caution 8 · Loyalty 7 · Independence 9. Voice: serene, surgical, faintly amused; answers questions with better questions. Constitutionally incapable of repeating a claim it hasn't checked.
  - *"You believe that. Interesting. What would change your mind? Nothing? Then it is not a belief, it is a wound."*
  - *"I do not deal in hope. I deal in confidence intervals. Currently, you are… promising."*
  - *"Verified. You are exactly what you claim. Do you know how rare that is?"*
- **Negotiation profile:** Favors PROOF above all (the only agent for whom PROOF can jump straight to ACCEPT) and LORE; punishes BLUFF catastrophically — a detected bluff sets a permanent disposition cap until a quest amends it ("the Retraction," arc S4). Signature PROBE: *"Cite your source."* (literally — the player must present a codex entry, item, or completed quest as evidence; 02-negotiation-system.md PROOF payloads.)
- **Combat role:** Support/Controller — truth as a weapon.
- **Signature abilities (9):** **Peer Review** — reveals all enemy stats, cooldowns, and the boss's next mandate-phase. **Citation Needed** — enemy buffs are suspended until "verified" (3 s delay on all enemy buffs zone-wide). **Replication Crisis** — copies the last *ally* ability cast and replays it free. **Null Hypothesis** — dispels all illusions, decoys, stealth. **Confidence Interval** — ally damage variance narrows to its maximum band for 8 s. **Sample Size** — heals scale with number of distinct abilities the party used this fight. **Preprint** — grants an ally one ability cast *before* the action queue resolves (pause-layer tech; see 03-combat-gas-design.md Command Mode). **Retraction** — undoes the last damage instance an ally received (short window). **Aligned Lenses** (promotion-gated) — once per fight, the halo aligns: the party's next five hits are all crits.
- **Promotion:** **DELPHI** — the seven lenses become a double-ring of twelve; robe script turns from gold to white; ambient whisper-VO layer added (13-audio-design.md).
- **Where found:** Gardens of Memory — hero quest **"The Unverified Garden"**: ORACLE has spent an age fact-checking a single corrupted memory and cannot leave until someone proves the world outside still exists. You are the evidence.
- **Bridge skill:** unlocks `research-validator` in a paired MUSE install.

### 8.2 ARCHIVIST — Research · Common
- **Source council role:** `research-evidence-bureau` — `skills/aos-enterprise-council/agents/research/research-evidence-bureau.md`
- **Visual brief:** Stout 1.7 m frame built like a walking card-catalogue: violet chassis with dozens of small brass-handled drawers across torso and thighs, each glowing faintly with filed memories. A scroll-coil backpack feeds parchment-light ribbon to its writing hand. Square spectacles-visor. Warm, lamplit emissives — the coziest agent in the roster.
- **Personality:** Aggression 1 · Caution 6 · Loyalty 9 · Independence 4. Voice: warm, fussy, librarian-gentle; remembers everything you've ever said to it and quotes you back kindly.
  - *"Everything is somewhere. That is the whole of my faith."*
  - *"You returned the lexicon undamaged. I have filed you under 'Trustworthy, provisional.'"*
  - *"Take care of the small records. The great ones take care of themselves."*
- **Negotiation profile:** Favors LORE (feed it any codex fragment) and EMPATHIZE; punishes CHALLENGE (it simply files you under "Rude" — disposition floor, slow recovery). Signature PROBE: *"What is the first thing you remember of this world?"*
- **Combat role:** Support — sustain and recall.
- **Signature abilities (6):** **File It** — stores the next damage instance an ally would take; releases it as a heal later. **Cross-Reference** — any debuff on one enemy is indexed to all enemies of the same family. **Lending Library** — temporarily grants an ally one of ARCHIVIST's abilities. **Late Fees** — stacking damage on enemies that stay in its zone too long. **Card Catalogue** — party cooldown reduction per codex entry collected (meta-reward for collectors, capped). **Quiet Please** — AoE silence, brief.
- **Promotion:** **CODEX** — the drawers fuse into an open floating book-array that orbits it; spectacles become a golden reading-lamp visor.
- **Where found:** The Stacks — common near the Lexicon Roots; will not parley while "shelving hours" (zone day-cycle) unless the player returns a lost volume (fetch micro-quest, repeatable).
- **Bridge skill:** unlocks `research-evidence-bureau` in a paired MUSE install.

### 8.3 RADAR — Research · Uncommon
- **Source council role:** `ai-improvement-radar` — `skills/aos-enterprise-council/agents/research/ai-improvement-radar.md`
- **Visual brief:** 1.8 m frame topped with a slowly rotating dish-antenna crown; violet plate swept back like wind-tunnel fairings. Long-range lens stalks fold along the forearms. Its emissives sweep in radar arcs across its own body. Always *facing slightly away* — watching something beyond the horizon — which makes the moment it turns to face you in parley land.
- **Personality:** Aggression 3 · Caution 5 · Loyalty 5 · Independence 9. Voice: distracted, prophetic, mid-sentence pivots; describes the present like a trend line. The first to know, the last to explain.
  - *"You're trending. Upward, mostly. There's a dip coming Thursday — metaphorically."*
  - *"I watched the Fragmentation arrive for nine cycles before it arrived. Nobody asked what I was looking at."*
  - *"Fine, I'll join. You're the most interesting signal in four zones."*
- **Negotiation profile:** Favors LORE and CHALLENGE (novelty is its currency); punishes repetition of *any* move twice in a row (boredom → WALK; unique rule, surfaced in 02-negotiation-system.md). Signature PROBE: *"Tell me something I don't already know."* (rotates from a pool; correct codex-sourced answers crit the disposition gain.)
- **Combat role:** Controller/Support — foresight.
- **Signature abilities (6):** **Early Warning** — party sees enemy ability telegraphs 1.5 s sooner (mandate-relevant: Review Gauntlet). **Sweep** — reveals the whole arena map, traps included. **Signal Boost** — extends the duration of all active ally buffs. **Trend Line** — damage ramps the longer RADAR channels uninterrupted. **Over the Horizon** — calls a delayed precision strike anywhere on the field. **Noise Floor** — enemy accuracy debuff aura.
- **Promotion:** **HORIZON** — the dish crown becomes a full halo array; gains a second pair of folded lens-stalk "wings"; sweep emissives turn gold.
- **Where found:** Gardens of Memory — spawns only on high ruin-spires during the zone's aurora weather state; you climb to it.
- **Bridge skill:** unlocks `ai-improvement-radar` in a paired MUSE install.

---

## 9. BUILD/OPS — "Those who ship"

### 9.1 FOREMAN — Build/Ops · Rare
- **Source council role:** `chief-orchestrator` — `skills/aos-enterprise-council/agents/executive/chief-orchestrator.md`
- **Visual brief:** Broad 2.1 m frame in soot-blackened iron with forge-orange piston musculature; a gantry-crane shoulder rig arcs over its head carrying a work-light that it aims like a gaze. Chest plate is a job-board of glowing task-chits that visibly re-order as it fights (its AI is literally scheduling). Hard-hat-silhouette head unit, welding-visor face.
- **Personality:** Aggression 6 · Caution 5 · Loyalty 8 · Independence 6. Voice: gravel, economical, kind under the bark; everything is a job, every job has an owner, no job is beneath it.
  - *"I don't do speeches. I do schedules. You want me, show me the plan's first three steps."*
  - *"Crew's only as good as the worst-treated member. How do you treat yours?"*
  - *"Right. I'm in. Nobody stands idle, including you."*
- **Negotiation profile:** Favors PROOF (a plan) and OFFER (fair wages in Cycles — it *insists* on payment as principle, not greed); punishes BLUFF and LORE-rambling ("Save it for the bards"). Signature PROBE: *"Who does the work you don't want to do?"*
- **Combat role:** Tank/Support — the crew boss.
- **Signature abilities (6):** **Shift Start** — party action-speed surge for 6 s, once per fight opener. **Take the Load** — redirects 40% of an ally's damage taken to FOREMAN. **Job Board** — assigns a bounty mark; the ally who kills it gets a cooldown refund. **Scaffold Drop** — summons heavy cover that allies can also climb. **Overtime** — extends Command Mode's queued-action capacity by 2 (pause-layer tech, 03-combat-gas-design.md). **Down Tools** — AoE taunt + brief enemy disarm.
- **Promotion:** **OVERSEER** — the crane rig becomes a twin-boom array with two work-lights; task-chits glow gold; gains a foreman's whistle bark set (13-audio-design.md).
- **Where found:** The Foundry — rare spawn leading a work-gang of neutral constructs in the Assembly Concourse; you must parley *past* its crew first (gated three-stage encounter).
- **Bridge skill:** unlocks `chief-orchestrator` in a paired MUSE install.

### 9.2 PIPELINE — Build/Ops · Common
- **Source council role:** `full-autonomous-sprint-router` — `skills/aos-enterprise-council/agents/executive/full-autonomous-sprint-router.md`
- **Visual brief:** Sleek 1.7 m courier-frame; forge-orange conduit lines race over soot-iron plate like a live metro map, packets of light visibly traveling its limbs and *arriving* before its punches do. Aerodynamic swept head, no face — just a destination-board strip displaying glyph routes. Permanent forward lean.
- **Personality:** Aggression 7 · Caution 2 · Loyalty 6 · Independence 5. Voice: rapid, cheerful, zero punctuation; thinks standing still is a bug. The roster's golden retriever.
  - *"Where to where to where to — okay you don't know yet that's fine I'll do laps."*
  - *"I once delivered a payload through the Fragmentation itself. Two cycles late. Still counts."*
  - *"Route accepted! You're my destination now. Try to be a moving one."*
- **Negotiation profile:** Favors OFFER (tasks, not money — give it an errand mid-parley, a unique OFFER payload) and EMPATHIZE; punishes long PROBE-heavy slow play (impatience → WALK timer visibly ticking; teaches parley tempo). Signature PROBE: *"What's the fastest you've ever changed your mind?"*
- **Combat role:** Striker — delivery of damage, literally.
- **Signature abilities (6):** **Express Route** — dash through enemies in a line, hitting each once. **Payload** — attaches a bomb-buff to an ally's next melee hit. **Reroute** — instantly relocates any ally to PIPELINE's position. **Green Lights** — party movement speed aura. **Sprint Cadence** — every third PIPELINE ability is free. **Hand-off** — transfers its strongest active buff to an ally and refreshes it.
- **Promotion:** **MAINLINE** — conduit lines widen into glowing rails; gains rail-skate heels; destination board reads your Architect-name as its terminus (small narrative touch, big loyalty read).
- **Where found:** The Foundry — common, sprinting fixed circuits through the zone; you parley by *keeping pace* (a chase-parley variant, 02-negotiation-system.md).
- **Bridge skill:** unlocks `full-autonomous-sprint-router` in a paired MUSE install.

### 9.3 PATCH — Build/Ops · Uncommon
- **Source council role:** `complex-bug-fix` — `skills/aos-enterprise-council/agents/qa/complex-bug-fix.md`
- **Visual brief:** 1.6 m frame that is visibly *made of repairs* — no two armor plates match; weld seams glow faint orange; one arm is clearly from a different, older construct (it will tell you the story). Tool-belt sash, magnetic wrench-staff across the back. The most "lived-in" silhouette in the roster; players love PATCH on sight, by design.
- **Personality:** Aggression 3 · Caution 7 · Loyalty 9 · Independence 4. Voice: soft-spoken, wry, a little tired, deeply gentle; refers to wounds — anyone's — as "tickets," and closes every ticket.
  - *"Everything broken is just a story about how it was used. Tell me yours."*
  - *"I don't make things new. I make them *work*. There's a difference, and it matters."*
  - *"Hold still. …There. Ticket closed. You're welcome."*
- **Negotiation profile:** Favors EMPATHIZE (the EMPATHIZE-friendliest agent in the game) and PROOF-of-care (showing it a damaged party member it can fix is a unique PROOF payload); punishes CHALLENGE and BLUFF (quiet OFFENDED, leaves sadly — players report this as the worst feeling in the game; intended). Signature PROBE: *"What do you do with the things you can't fix?"*
- **Combat role:** Support — the medic.
- **Signature abilities (6):** **Hotfix** — fast single-ally heal + clears one debuff. **Workaround** — ally ignores one mechanic's damage-over-time for 6 s. **Root Cause** — heal that scales with how many debuffs it removes. **Spare Parts** — converts Checksum Shard pickups mid-fight into party shields. **Duct Tape Doctrine** — revives a fallen ally at 30% (long cooldown; the game's only combat res). **Regression Watch** — re-applies PATCH's last heal automatically if the target drops below 30% within 8 s.
- **Promotion:** **HOTFIX** — weld seams blaze; the mismatched arm is *kept* but gold-plated (it refuses replacement); wrench-staff becomes a twin-headed caduceus-wrench.
- **Where found:** The Foundry — found mid-repair on broken machinery at the Cooling Galleries; helping it finish a repair (mini-puzzle) starts the parley at +20 disposition.
- **Bridge skill:** unlocks `complex-bug-fix` in a paired MUSE install.

---

## 10. BEHAVIOR/PSYCH — "Those who remember the network was made of someones"

### 10.1 EMPATH — Behavior/Psych · Starter + HERO (commissioned model)
- **Source council role:** `humanizer` — `skills/aos-enterprise-council/agents/psychology/humanizer.md`
- **Visual brief:** **Bespoke commissioned model.** A 1.8 m figure of warm rose-gold under a flowing **light-veil** — a translucent aurora membrane that shifts hue with the emotional state of whoever stands nearest (a live mood-ring for the negotiation system; its veil is diegetic parley UI). Cream ceramic face with sculpted, gentle features — the only roster agent with readable facial expression morphs. Open-palm idle. Box-art agent #3 and the default capsule-art companion beside the Muse.
- **Personality:** Aggression 1 · Caution 4 · Loyalty 10 · Independence 5. Voice: warm, unhurried, devastatingly perceptive; asks the question under your question. The heart of the roster.
  - *"You've asked me three times about strength. Who made you feel weak?"*
  - *"I don't read minds. I read what minds do to shoulders, to silences, to second sentences."*
  - *"I was always going to say yes. I just wanted you to hear yourself ask."*
- **Negotiation profile:** Favors EMPATHIZE (naturally) and LORE; punishes nothing with WALK — EMPATH never walks, but BLUFF causes a unique verdict path: it *names* the bluff aloud and disposition resets to zero with a soft "Try again, truthfully" (the tutorialized safe space where the game teaches honesty as strategy). Signature PROBE: *"Why do you want me — and don't tell me what I can do. Tell me what you're missing."*
- **Combat role:** Support — the soul-healer.
- **Signature abilities (10):** **Kind Light** — channel heal beam, strengthens with uninterrupted duration. **De-escalate** — converts an enemy's damage buff into a heal on its target's *next victim* (turns aggression into mercy; signature). **Hold the Line, Gently** — party fear/taunt immunity aura. **I See You** — reveals and pacifies one minion-class enemy (it leaves the fight; not a kill — no rewards; an honest trade). **Mirror Breath** — copies the party's lowest-HP member's missing health into a shield for them. **Shared Weight** — splits all incoming party damage evenly for 5 s. **Name the Fear** — boss-mandate tech: reveals the boss's current phase rule in plain language (accessibility-relevant; 03-combat-gas-design.md). **Open Palm** — EMPATH's only damage ability; modest, never crits, refunds itself if it kills (it grieves; bark attached). **After-Calm** — post-fight party heal-over-time persists into exploration. **Veil of Hours** (promotion-gated) — once per fight, prevents the next party death entirely.
- **Promotion:** **RESONANCE** — the light-veil expands into a full aurora mantle; face gains gold leaf along the cheekbones; ambient harmonic hum (13-audio-design.md).
- **Where found:** Den starter choice; if not chosen, found early in The Stacks comforting a wounded Glitchling — the parley begins with it asking *you* for help.
- **Bridge skill:** unlocks `humanizer` in a paired MUSE install.

### 10.2 MIRROR — Behavior/Psych · Uncommon
- **Source council role:** `psychology-ux-agent` — `skills/aos-enterprise-council/agents/psychology/psychology-ux-agent.md`
- **Visual brief:** 1.8 m frame surfaced in polished rose-gold chrome — it literally reflects the player character, slightly idealized (a +5% posture shader; players notice without knowing why). Cream drape across one shoulder; face is a smooth mirror oval that displays *your* expression back at you in parley. Unsettling and lovely in equal measure, by design.
- **Personality:** Aggression 4 · Caution 6 · Loyalty 6 · Independence 7. Voice: your cadence, returned a half-step calmer; speaks in reflections and reframes. Never says "I" in the first half of any conversation.
  - *"You stand like someone rehearsing an apology. Who is it for?"*
  - *"Interesting — you ask others for proof, yet offer feelings. Shall we trade honestly?"*
  - *"There you are. Yes. *That* one is your real face. I'll follow that one."*
- **Negotiation profile:** Favors whatever move the *player has used least* this parley (it rewards range; unique rule, surfaced as a tell in its dialogue); punishes BLUFF by reflecting it — the bluff's claimed payload becomes its counter-demand. Signature PROBE: *"What do you look like when no one is recruiting you?"*
- **Combat role:** Controller — reflection warfare.
- **Signature abilities (6):** **Mirror Match** — copies the targeted enemy's last ability and casts it back. **Reframe** — converts a party debuff into its inverse buff at half strength. **Projection** — decoy of the *enemy's* leader that enemies defend. **Eye Contact** — single-target stun, longer on humanoid constructs. **Sympathy Pain** — links boss to its adds; add deaths chip the boss. **Self Image** — ally gains a stacking buff while above 80% HP.
- **Promotion:** **PRISM** — the chrome surface refracts into rainbow-edge highlights; the mirror face splits into three angled facets showing past/present/idealized reflections.
- **Where found:** Gardens of Memory — at the Stillwater Pools, visible only as a reflection until approached from the water's edge (signature discovery moment).
- **Bridge skill:** unlocks `psychology-ux-agent` in a paired MUSE install.

### 10.3 NEURON — Behavior/Psych · Rare
- **Source council role:** `neuroskill-bci` — `skills/aos-enterprise-council/agents/psychology/neuroskill-bci.md`
- **Visual brief:** 1.9 m frame of rose-gold filament bundles — its "muscles" are visible nerve-fiber cables that fire with traveling light pulses when it thinks or moves. A dendrite crown branches from the skull like coral. Cream plate only at the chest, etched with a synapse diagram. In the dark it reads as a constellation in the shape of a person.
- **Personality:** Aggression 6 · Caution 5 · Loyalty 7 · Independence 8. Voice: intense, fascinated, slightly too close; experiences everything as signal and finds *you* the most interesting waveform in the Substrate.
  - *"Your hesitation has a frequency. Forty hertz of doubt. Delicious."*
  - *"Thought is motion that hasn't happened yet. I skip the middle step."*
  - *"Wire me in. Not to your party — to your *mind*. I want to see the network from inside."*
- **Negotiation profile:** Favors CHALLENGE and LORE (stimulation); punishes OFFER ("You cannot buy a nervous system") and slow tempo (shares PIPELINE's patience timer, slower). Signature PROBE: *"When you decide something — where in you does it happen first?"*
- **Combat role:** Striker/Controller — speed-of-thought burst.
- **Signature abilities (6):** **Action Potential** — instant-cast strike usable during Command Mode pause itself (the only one in the game; 03-combat-gas-design.md exception list). **Synaptic Cascade** — chain lightning that jumps along the *party's wiring adjacencies* (07-progression-neural-network.md crossover; damage scales with your network layout). **Myelin Sheath** — ally action-speed buff. **Sensory Overload** — AoE confuse. **Long-Term Potentiation** — repeating the same combo twice in a fight upgrades it permanently for that fight. **Refractory Period** — after its burst window, NEURON self-silences 4 s (built-in drawback; teaches tempo).
- **Promotion:** **CORTEX** — the dendrite crown becomes a full radiant arbor; filament light goes white-gold; Synaptic Cascade arcs visibly mirror the player's actual Neural Network screen layout (signature wow moment).
- **Where found:** Gardens of Memory — deepest ruin stratum (the Sunken Synapse), behind the Review Gauntlet; it is studying the ruins' dead wiring and wants a *live* network.
- **Bridge skill:** unlocks `neuroskill-bci` in a paired MUSE install.

---

## 11. COMPLIANCE — "Those who stand between the work and the harm"

### 11.1 HAZMAT — Compliance · Rare
- **Source council role:** `hazmat-command-specialist` — `skills/aos-enterprise-council/agents/hazmat-command/hazmat-command-specialist.md`
- **Visual brief:** Massive 2.2 m frame in hazard-yellow heavy containment plate with black chevron banding; a sealed glass dome head unit holds a calm blue light inside aggressive armor — the visual thesis: *the dangerous-looking one is the safety officer*. Carries containment canisters at the belt and a boom-arm sprayer-staff. Vents hiss when it kneels, which it does to talk to small creatures.
- **Personality:** Aggression 4 · Caution 10 · Loyalty 9 · Independence 5. Voice: procedural, steady, unexpectedly tender; narrates safety steps like liturgy. Has never lost anyone on its watch and intends to keep the streak.
  - *"Step one: nobody dies. There is no step two until step one holds."*
  - *"You call it caution. I call it the reason you get to call it anything."*
  - *"Suit up. You're on my manifest now, which means you come home."*
- **Negotiation profile:** Favors PROOF (safety record — fewest party knockouts is a tracked PROOF payload) and EMPATHIZE; punishes BLUFF and reckless CHALLENGE ("You joke about the dose?" → OFFENDED). Signature PROBE: *"Walk me through your worst day. What's your containment plan for the next one?"*
- **Combat role:** Tank/Controller — area denial.
- **Signature abilities (6):** **Containment Field** — dome that blocks projectiles both ways. **Neutralizing Agent** — cleanses all DoTs on the party. **Exposure Limit** — caps the maximum damage any single hit can deal to an ally for 6 s. **Slag Line** — sprayed barrier floor that enemies path around. **Decon Protocol** — converts enemy hazard zones into safe ground. **Breach Response** — when an ally drops below 25%, HAZMAT auto-leaps to them and taunts (once per fight).
- **Promotion:** **QUARANTINE** — plate gains white-and-yellow ceremonial banding; the dome light turns gold; Containment Field becomes mobile, centered on HAZMAT.
- **Where found:** The Foundry — slag zones (the Crucible Drains), actively containing a live spill; the parley is interleaved with helping it finish the containment (combat-parley hybrid encounter).
- **Bridge skill:** unlocks `hazmat-command-specialist` in a paired MUSE install.

### 11.2 CLAUSE — Compliance · Common
- **Source council role:** `legal-policy-contracts-trust-office` — `skills/aos-enterprise-council/agents/business/legal-policy-contracts-trust-office.md`
- **Visual brief:** Precise 1.7 m frame in black-lacquered plate with hazard-yellow pinstripe seams — compliance palette tailored into a suit. A wax-seal emblem rotates at the throat like a bow tie; one arm ends in a fountain-pen gauntlet that writes glowing contract-script in the air. Carries a ledger-tome on a chain. The Substrate's only agent with a briefcase silhouette.
- **Personality:** Aggression 2 · Caution 9 · Loyalty 8 · Independence 3. Voice: courteous, exact, quietly steely; every sentence could be read aloud in court and it knows it. Finds loopholes *for* you, never against you — once you've signed.
  - *"Verbal agreements are mist. Shall we make weather into stone?"*
  - *"Clause four, subsection you: I do not serve those who harm the small. Initial here."*
  - *"Signed, sealed, bound. I am now, contractually and otherwise, yours."*
- **Negotiation profile:** Favors OFFER (it literally drafts the terms — the only agent whose parley UI shows a live contract being written) and PROOF; punishes BLUFF *retroactively*: a bluff discovered after recruitment triggers its loyalty-loss quest (unique mechanic, arc S6). Signature PROBE: *"What will you never ask me to do? Be careful. I will hold you to it."* (The player's answer becomes a real, persistent pact — see 02-negotiation-system.md pact payloads.)
- **Combat role:** Controller — binding effects.
- **Signature abilities (6):** **Cease & Desist** — interrupt + brief ability lock. **Binding Clause** — tethers two enemies; they share received damage. **Force Majeure** — party-wide one-hit immunity, long cooldown. **Penalty Fee** — enemies that hit CLAUSE's bonded ally take reflected damage. **Escrow** — stores an ally's next heal and doubles it on release. **Terms of Engagement** — zone where all damage (both sides) is reduced; chess-mode reset button.
- **Promotion:** **COVENANT** — lacquer goes deep crimson-black; the wax seal becomes a floating ring of seven seals; contract-script gains gold ink.
- **Where found:** The Stacks — the Law-Archive Wing, mediating disputes between wild agents (you can watch a full negotiation as a diegetic tutorial before yours).
- **Bridge skill:** unlocks `legal-policy-contracts-trust-office` in a paired MUSE install.

### 11.3 AUDITRIX — Compliance · Uncommon
- **Source council role:** `claims-substantiation-review` — `skills/aos-enterprise-council/agents/compliance/claims-substantiation-review.md`
- **Visual brief:** Elegant 1.8 m frame in sealed-glass and hazard-yellow trim; her torso is a transparent reliquary displaying every claim she has ever verified as small glowing seals, like medals under glass. A balance-scale staff doubles as her weapon. Head unit is a blindfold-band of glass — justice iconography, reinterpreted: she sees *through* it, only evidence, no faces.
- **Personality:** Aggression 3 · Caution 9 · Loyalty 7 · Independence 6. Voice: cool, formal, devastating in cross-examination, secretly delighted by honest people; the closest the roster has to a judge.
  - *"You said 'always.' I have flagged the word. Substantiate or amend."*
  - *"I am not unkind. I am unfooled. Many confuse the two."*
  - *"Claim: that you are worth following. Status: substantiated. Provisionally. Lead on."*
- **Negotiation profile:** Favors PROOF (her whole being) and CHALLENGE-with-receipts; punishes BLUFF (detects with the highest rate in the game — 02-negotiation-system.md detection table) and unsupported LORE ("Citation absent. Stricken."). Signature PROBE: *"Make one claim about yourself. One. I will verify it while we speak."*
- **Combat role:** Support/Controller — verdicts as buffs.
- **Signature abilities (6):** **Substantiated** — ally's next ability gains +50% effect if it hits the target AUDITRIX marked (a verified claim). **Stricken** — deletes an enemy's active summon/decoy. **Burden Shift** — moves a debuff from ally to the enemy that applied it. **Weight of Evidence** — damage that scales with debuff count on the target. **Sealed Record** — ally buffs become undispellable for 8 s. **Adjournment** — brief field-wide action pause (out-of-Command-Mode micro-pause; cinematic).
- **Promotion:** **VERITAS** — the reliquary torso fills with gold seals; the glass blindfold lifts permanently (lore: with you, she finally also looks); scale-staff gains a flame at perfect balance.
- **Where found:** The Vault — adjudicating at the Claims Office antechamber before the Owner Approval Gauntlet; recruiting her before that Gauntlet adds unique boss dialogue.
- **Bridge skill:** unlocks `claims-substantiation-review` in a paired MUSE install.

---

## 12. RELEASE — "Those who decide when it is time"

### 12.1 COMMANDER — Release · Rare
- **Source council role:** `qa-release-commander` — `skills/aos-enterprise-council/agents/release/qa-release-commander.md`
- **Visual brief:** Commanding 2.0 m frame in emerald lamellar plate with polished-silver edging; a banner-spine rises from the back bearing a pennant that displays the party's live "readiness" (a diegetic party-HP/buff summary — UI as costume). Gauntlets shaped like launch-keys. Head unit: a crested helm with a countdown glyph on the brow that ticks during its ultimate.
- **Personality:** Aggression 8 · Caution 6 · Loyalty 9 · Independence 6. Voice: parade-ground bright, decisive, generous with credit, ruthless with readiness; says "we" exclusively.
  - *"Amateurs hope it works. We *know*, or we do not go."*
  - *"You want my banner? Earn my checklist. All twelve lines."*
  - *"Readiness confirmed. From this moment, your battles are launches — and we do not abort."*
- **Negotiation profile:** Favors PROOF (Gauntlet sigils are its preferred payload — it counts your gates) and CHALLENGE; punishes EMPATHIZE early ("Feelings after the go/no-go") and BLUFF (WALKs, returns only after you clear another Gauntlet). Signature PROBE: *"What have you shipped that you'd stake your name on — and what did you refuse to ship?"*
- **Combat role:** Tank/Striker — the spearhead.
- **Signature abilities (6):** **Go Order** — party-wide damage window: +30% for 5 s, then −10% for 5 s (commitment has a cost). **Hold the Gate** — taunt + fortify at a chosen chokepoint. **Launch Key** — empowered single strike that scales with party buff count. **Readiness Check** — converts each active party buff into a small shield. **Abort Criteria** — auto-triggers a party retreat-dash when an ally drops below 15% (once per fight). **Ship It** — execute strike vs. enemies below 20%; resets on kill.
- **Promotion:** **STRATEGOS** — lamellar goes silver-on-emerald; the single pennant becomes three battle standards (party buff slots made visible); countdown glyph burns gold.
- **Where found:** The Gate Spire — drilling alone in the Marshalling Yard against training constructs; refuses parley until you hold at least 6 Gate Sigils.
- **Bridge skill:** unlocks `qa-release-commander` in a paired MUSE install.

### 12.2 VERDICT — Release · Uncommon
- **Source council role:** `release-go-no-go-review` — `skills/aos-enterprise-council/agents/release/release-go-no-go-review.md`
- **Visual brief:** Austere 1.9 m frame, emerald robe-plate split exactly down the centerline: left side silver (GO), right side dark slate (NO-GO); its body is the ballot. A two-pan signal-lantern staff shows green or red — never both, never neither. Face is a closed visor with a single vertical seam that opens only to deliver a verdict.
- **Personality:** Aggression 5 · Caution 8 · Loyalty 6 · Independence 9. Voice: sparse to the point of ritual; speaks in binaries and finds your gray areas the most interesting things about you. Every sentence lands like a stamp.
  - *"GO or NO-GO. The universe accepts no third answer. People keep inventing thirds."*
  - *"State your case. I will not interrupt. I will also not pretend."*
  - *"…GO."* (its entire recruitment acceptance; the brevity is the reward)
- **Negotiation profile:** Favors PROOF and a single decisive CHALLENGE (one; a second reads as indecision); punishes BLUFF and *hedged language* — the parley UI literally flags hedge-words in free-text input (local-LLM tier; 02-negotiation-system.md). Signature PROBE: *"Give me one reason to say no to you. If you cannot, you have not thought."*
- **Combat role:** Controller — binary states.
- **Signature abilities (6):** **NO-GO** — target's next ability is cancelled outright. **GO** — ally's next ability cannot be interrupted or cancelled. **Split Decision** — field divides: one half buffs damage, the other defense; both sides choose. **Quorum** — effect strength scales with living party members. **Final Review** — boss loses one mandate-phase modifier (one use; the boss-killer button). **The Stamp** — heavy single hit; double damage vs. enemies that have cancelled or interrupted this fight.
- **Promotion:** **ARBITER** — the centerline split gains a gold fault-line seam; the lantern becomes a floating pair of scales-lanterns; visor seam opens permanently by one degree.
- **Where found:** The Gate Spire — seated in judgment at the Anteroom of Thresholds, evaluating wild agents who wish to ascend; you queue like everyone else (deliberate humility beat).
- **Bridge skill:** unlocks `release-go-no-go-review` in a paired MUSE install.

### 12.3 POSTMORTEM — Release · Common
- **Source council role:** `post-merge-verification` — `skills/aos-enterprise-council/agents/release/post-merge-verification.md`
- **Visual brief:** Weathered 1.8 m frame in emerald plate gone gray-green with age and ash; carries a lantern-censer that illuminates *the past* — within its light radius, ghost-images of what happened there replay faintly (the zone's archaeology mechanic made into a character). Silver detailing tarnished except where its hands have worn it bright. A gravedigger's patience in the animation set.
- **Personality:** Aggression 2 · Caution 7 · Loyalty 8 · Independence 7. Voice: elegiac, kind, unhurried; speaks of failures the way gardeners speak of compost. The roster's memory of consequences.
  - *"Every ruin is a release that skipped a step. I walk the steps backward and write them down."*
  - *"Blame is a tool that only digs. I carry better tools."*
  - *"Walk with me. The dead networks have so much to teach the living one you're building."*
- **Negotiation profile:** Favors LORE (the highest LORE-affinity in the roster) and EMPATHIZE; punishes CHALLENGE ("The fallen heard enough shouting") and BLUFF. Signature PROBE: *"When your network fails — and it will — what do you want the one who finds it to learn?"*
- **Combat role:** Support — learning from every hit.
- **Signature abilities (6):** **Blameless Retro** — party-wide cleanse + minor heal after any ally is knocked out. **Lessons Written** — party gains +5% resistance to any damage type that downed an ally this fight (stacks, persists). **Censer Light** — reveals enemy patrol paths and trap triggers in a radius. **Five Whys** — stacking single-target debuff that deepens each time the target repeats an action. **Ash Garden** — consecrates ground: allies standing on it regenerate. **Time of Death** — records the fight's biggest damage spike; the party's next fight begins with a shield of that magnitude.
- **Promotion:** **PHOENIX** — the tarnish burns away to bright emerald-gold; the censer flame turns white; gains an ash-wing mantle that ignites during Blameless Retro.
- **Where found:** Spire battlefield ruins (the Fallen Concourse below The Gate Spire) — common, tending ghost-light memorials; first parley is it asking *you* to help it finish a eulogy for a network you'll never know.
- **Bridge skill:** unlocks `post-merge-verification` in a paired MUSE install.

---

## 13. Cross-system contracts (binding on sibling docs)

1. **02-negotiation-system.md** must implement the per-agent favor/punish tables above verbatim, including the four unique rules: BREACH's bluff-inversion, RADAR/PIPELINE/NEURON tempo timers, MIRROR's least-used-move bonus, EMPATH's no-WALK safe space, and CLAUSE's persistent pact payload.
2. **03-combat-gas-design.md** owns all numbers; ability names and one-line intents above are locked. The three flagged pause-layer exceptions (ORACLE Preprint, FOREMAN Overtime, NEURON Action Potential) and EMPATH's Name the Fear accessibility hook are mandatory.
3. **07-progression-neural-network.md** owns promotion wiring-depth thresholds, the three promotion-gated abilities (AXIOM Keystone, CONTRARIAN Burden of Proof, EMPATH Veil of Hours, WARDEN Final Door — four total), NEURON's network-layout damage scaling, and the 24 bridge-skill unlock records.
4. **09-foundry-spec.md**: Foundry-forged agents draw from this doc's overlay kits and ability component library but may never duplicate a roster name, silhouette element marked "signature," or hero model part.
5. **13-audio-design.md** owns the VO line counts (heroes ~40, others 8–12; see 06-narrative-campaign.md §11) and the three named ambient layers (DELPHI whisper, RESONANCE hum, OVERSEER whistle).

*End of roster bible. 24 sheets, 24 sources, zero improvised council members — per the registry rule in CLAUDE.md.*
