# 03 — Combat Design on the Gameplay Ability System

**Project:** SYNAPSE — A muse Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

Real-time with tactical pause (master plan locked decision #7), party of 3, pure single-player, built entirely on UE 5.6's Gameplay Ability System with GameplayTags as the lingua franca (§5). Pause is the orchestrator fantasy made literal: the Architect stops time and commands the network. Sibling references: per-agent kits in `04-roster-24-agents.md`, encounter/boss placement in `05-world-design.md`, network synergies in `07-progression-neural-network.md`, HUD in `12-ui-ux-spec.md`, module layout in `11-technical-design.md`.

---

## 1. The Attribute Set

All combatants derive from `ASynapseAgentCharacter` carrying a `UAbilitySystemComponent` and `USynapseAttributeSet`. Seven attributes; nothing else touches health or damage math.

| Attribute | Fantasy | Role | Notes |
|---|---|---|---|
| **Integrity** | structural soundness | HP | At 0: player agents enter `State.Crashed` (revivable, 15s field timer or ally Restore ability); enemies despawn |
| **Bandwidth** | processing headroom | stamina / ability resource | Regen 8/s in combat (4/s on bench); abilities cost 15–40 |
| **Latency** | response time | speed — **lower is better** | Action recovery (s) = `1.2 + Latency/50` |
| **Throughput** | raw output | attack power | +1% damage per point (see §8) |
| **Resilience** | fault tolerance | defense | Diminishing-returns mitigation (see §8) |
| **Heat** | overclock pressure | crit rating **and** overload gauge | Crit chance % = `Heat × 0.5`, cap 40%. Separately, a runtime Heat *gauge* (0–100, +6 per ability used, −3/s idle) triggers **Overload** at 100: `State.Overloaded` — damage dealt **and** taken +30% for 8s, then gauge vents to 0 |
| **DomainAffinity** | specialization depth | same-domain amplifier | Abilities whose `Damage.Domain.*` matches the agent's own domain gain `1 + Affinity/200` |

### 1.1 Level curves (1–50, locked)

Growth factor: **`G(L) = 0.94 + 0.06·L + 0.0006·L²`** → G(1)=1.00, G(10)=1.60, G(20)=2.38, G(30)=3.28, G(40)=4.30, G(50)=5.44.

```
Integrity(L)   = round(Base × G(L))
Throughput(L)  = round(Base × G(L))
Resilience(L)  = round(Base × G(L))
Bandwidth(L)   = Base + 2·(L−1)                  (base 100 → 198 at 50)
Latency(L)     = max(40, Base − 0.7·(L−1))       (base 100 → ~66 at 50; lower = faster)
Heat(L)        = Base + 0.6·(L−1)
DomainAffinity(L) = Base + 0.4·(L−1)
```

### 1.2 Archetype base bands (per-agent values in `04-roster-24-agents.md`, drawn from these bands)

| Archetype (roster term) | Integrity | Throughput | Resilience | Latency | Heat | Examples |
|---|---|---|---|---|---|---|
| Vanguard (= "Tank" in `04-roster-24-agents.md`) | 120–140 | 10–12 | 16–20 | 100–110 | 6–10 | WARDEN, FOREMAN, HAZMAT |
| Striker | 85–100 | 15–18 | 8–11 | 80–95 | 12–18 | BREACH, PIPELINE, COMMANDER |
| Support | 90–105 | 9–11 | 12–14 | 90–100 | 8–12 | EMPATH, ARCHIVIST, PATCH |
| Controller | 95–110 | 12–14 | 10–13 | 95–105 | 10–14 | AXIOM, CIPHER, MIRROR |

Hybrid-role agents (e.g. CONTRARIAN, Striker/Controller per the roster table) draw from their **primary** role's band; the secondary role is expressed through the kit, not the statline. Levels come from network Resonance, never per-agent XP — see `07-progression-neural-network.md` §4.

---

## 2. The 8×8 Type Chart

One advantage ring (shared canon): **Architecture → QA/Test → Build/Ops → Compliance → Behavior/Psych → Research → Security → Release → Architecture**, each domain strong (×1.5) against the next, weak (×0.75) against the previous. No immunities, no double-weakness — readability over trivia. Multiplier applies to the **ability's** `Damage.Domain.*` tag vs the **defender's** domain tag.

| atk ▼ / def ► | Arch | QA | Build | Compl | Behav | Rsrch | Sec | Rel |
|---|---|---|---|---|---|---|---|---|
| **Architecture** | 1.0 | **1.5** | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | *0.75* |
| **QA/Test** | *0.75* | 1.0 | **1.5** | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| **Build/Ops** | 1.0 | *0.75* | 1.0 | **1.5** | 1.0 | 1.0 | 1.0 | 1.0 |
| **Compliance** | 1.0 | 1.0 | *0.75* | 1.0 | **1.5** | 1.0 | 1.0 | 1.0 |
| **Behavior** | 1.0 | 1.0 | 1.0 | *0.75* | 1.0 | **1.5** | 1.0 | 1.0 |
| **Research** | 1.0 | 1.0 | 1.0 | 1.0 | *0.75* | 1.0 | **1.5** | 1.0 |
| **Security** | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | *0.75* | 1.0 | **1.5** |
| **Release** | **1.5** | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | *0.75* | 1.0 |

Master-plan fixed edges verified: Security counters Release ✓, QA counters Build ✓, Research counters Security ✓. The chart ships in `DT_DomainChart` and is read by one function (`USynapseCombatStatics::GetDomainMult`) so it can never drift.

---

## 3. Ability Taxonomy

Six ability classes. Every agent ships **6–10 abilities** (exact kits in `04-roster-24-agents.md`) obeying the kit rule: ≥1 Strike, ≥1 pipeline role (Mark or Exploit), ≥1 Shield-or-Field, ≥1 Pipeline-link once promoted.

| Class | Verb | Cost (Bandwidth) | Cooldown | Definition |
|---|---|---|---|---|
| **Strike** | hit | 15–20 | none (recovery-gated) | Direct damage, single target. The bread. |
| **Exploit** | punish | 25–30 | 8–12s | Conditional burst: ×1.5 vs `State.Marked.*`, or vs a state the kit names (Stunned, Overloaded). Consumes the Mark. |
| **Shield** | protect | 20–30 | 10–15s | Absorb shells (`State.Shielded`), cleanses. Absorb = `Caster.Resilience × 6`. The single in-combat revive lives here (PATCH's Duct Tape Doctrine — deliberately unique, `04-roster-24-agents.md`) |
| **Mark** | expose | 15–20 | 6–10s | Applies `State.Marked.<Domain>` (12s) + a minor debuff (−10% Resilience). Opens Pipelines. |
| **Field** | shape | 30–40 | 15–25s | Ground AoE zones, 6–10s duration: damage pulses, slows (`State.Throttled`), Bandwidth drains, ally regen. |
| **Pipeline-link** | combine | 25 | 20s | The Detonate finishers and chain-extenders for §5. Only usable inside an open Pipeline window. |

### 3.1 GameplayTag namespace (locked conventions)

```
Ability.Strike.<Name>            Ability.Mark.<Name>           Ability.Field.<Name>
Ability.Exploit.<Name>           Ability.Shield.<Name>         Ability.Pipeline.<Name>
Damage.Domain.{Architecture,QA,Build,Compliance,Behavior,Research,Security,Release}
State.Marked.<Domain>            State.Shielded   State.Overloaded   State.Crashed
State.Throttled (slow)           State.Segfault (stun)   State.Leak (DoT)   State.Provoked
Combo.Pipeline.{BlueprintAudit,RegressionHammer,ChangeControl,InformedConsent,
                HypothesisEngine,ZeroDayDisclosure,HardGate,PostmortemLoop}
Combo.Window.{Open,Detonate}     Cooldown.Ability.<Name>       Cost.Bandwidth
Gate.Boss.<GauntletName>         Difficulty.{Story,Standard,Architect}
```

Rule: a tag is created in `SynapseGameplayTags.h` (native) or it does not exist. No ad-hoc INI tags after content lock.

### 3.2 Status effects (locked definitions)

| State tag | Effect | Duration | Stacking | Counters |
|---|---|---|---|---|
| `State.Marked.<Domain>` | −10% Resilience; pipeline opener | 12s (18s w/ Peer Review perk) | one Mark per target; newer replaces older | consumed by Exploit; cleansable |
| `State.Throttled` | +40% Latency (slower actions), −30% move speed | 6s | refresh only | cleanse, shield-immune variants |
| `State.Leak` | DoT: 4% of victim's max Integrity per 2s tick | 8s | up to 3 stacks (independent timers) | cleanse |
| `State.Segfault` | hard stun: no actions, no recovery tick | 2–2.5s | non-stackable; 8s same-target immunity after it ends | bosses immune (§7) |
| `State.Shielded` | absorb shell before Integrity | until broken or 12s | one shell per target; strongest wins | shield-break riders (Hard Gate) |
| `State.Overloaded` | +30% damage dealt **and** taken | 8s, then Heat gauge vents to 0 | n/a | self-managed (§1 Heat) |
| `State.Crashed` | downed; untargetable except revive abilities | 15s field timer (player side) | n/a | Duct Tape Doctrine (PATCH — the game's only combat res, `04-roster-24-agents.md`), bench revive, Rollback Clause perk |
| `State.Provoked` | +10% Throughput (parley-broken enemies, `02-negotiation-system.md` §1) | 60s | non-stackable | none — you earned it |

Heat management is a deliberate sub-game: Strikers ride the gauge to ~90 and pause to vent (Command Mode shows the gauge per agent); a Controller's Field can be dropped pre-Overload so the +30% window lands inside a Pipeline detonation. Out of combat, Integrity and Bandwidth restore to full over 6s, Heat gauges vent instantly, Crashed agents stand up at 35% Integrity, and combat cooldowns clear — no camping between packs.

---

## 4. Command Mode (Tactical Pause)

- **Pause is a full stop.** Global time dilation 0; VFX, audio beds, and AI all freeze; the command camera unlocks (orbit + 12m pull-back). No "slow-mo compromise" — the Architect owns time. Toggle: Space / gamepad ⓨ; exits on confirm or re-press.
- **Queue depth: 3 per agent.** Each active agent holds an ordered queue of up to 3 commands (ability+target, move-to, swap, item). Slot 1 is inviolable; slots 2–3 may be re-evaluated by high-Independence agents (§6).
- **Command Point (CP) economy.** Shared pool, max 5, encounter starts at 3, regen **1 CP per 4s of unpaused combat**. Costs: queue an ability **1 CP**; retarget or move-order **0 CP**; swap **2 CP**; cancelling an un-started queued command refunds its CP. Pausing itself is free and unlimited — CP gates *commanding*, not *thinking*.
- **Swaps.** Bench of 3 behind the active 3 (party of 3 is contractual). A swap costs 2 CP and **the incoming agent's turn slice**: it arrives with its action recovery (`1.2 + Latency/50` s) already ticking and an empty queue. Outgoing agent keeps cooldowns running and regens Bandwidth at 50% on the bench. Crashed agents can be swapped out (bench revive over 30s) — the tactical answer to a downed Vanguard.
- Free actions in Command Mode: inspect any unit's attributes/states, preview damage (shows the §8 formula's expected value), read Pipeline windows, use the Rollback checkpoint where unlocked (§7, Rollback Gauntlet).

---

## 5. Pipelines — the Cross-Agent Chain System

The combat showcase (master plan §4.4): **Mark → Exploit → Detonate**.

1. **Mark:** any Mark ability applies `State.Marked.<Domain>` (12s).
2. **Exploit:** an Exploit from the domain **ring-adjacent** to the marker's domain consumes the Mark, deals its ×1.5 bonus, and opens `Combo.Window.Detonate` on the target (4s, flagged in world-space UI).
3. **Detonate:** any third party member's Strike, Field, or Pipeline-link inside the window detonates: that hit gains the **Pipeline multiplier ×1.75** and applies the pipeline's signature rider.

Pipelines are *unlocked by wiring* ring-adjacent agents in the Neural Network (`07-progression-neural-network.md` §3). Eight named launch pipelines, one per domain pairing along the ring:

| # | Pairing (Mark → Exploit) | Pipeline name | Detonation rider |
|---|---|---|---|
| 1 | Architecture → QA | **Blueprint Audit** | Target loses 20% Resilience for 10s |
| 2 | QA → Build | **Regression Hammer** | Detonation repeats at 50% power after 2s |
| 3 | Build → Compliance | **Change Control** | Target `State.Segfault` (stun) 2.5s |
| 4 | Compliance → Behavior | **Informed Consent** | Target deals −20% damage 10s |
| 5 | Behavior → Research | **Hypothesis Engine** | Party gains 1 CP; target revealed (no stealth/cloak 20s) |
| 6 | Research → Security | **Zero-Day Disclosure** | Detonation ignores 50% of mitigation |
| 7 | Security → Release | **Hard Gate** | Target cannot heal or shield 8s |
| 8 | Release → Architecture | **Postmortem Loop** | Party Bandwidth +25 instant; detonator's cooldowns −3s |

A pipeline requires its two named domains present (active party, not bench) and wired adjacent in the network. Chain extension: a Detonate that kills lets the next Mark within 3s start at step 2 ("hot pipeline") — sustained mastery for Architect-difficulty players. Each pipeline has a named GameplayCue (`Cue.Pipeline.<Name>`) and a Niagara signature; landing one is the clip moment.

---

## 6. Semi-Autonomous Ally AI (Personality-Driven)

Between commands, agents fight themselves, driven by the four personality-card axes (0–10, from `04-roster-24-agents.md`). Implementation: utility scorer (`USynapseAgentBrain`, C++; ~150 scored candidates max per decision, decisions on action-recovery expiry only — cheap, single-player).

| Axis | Governs | Concrete effect |
|---|---|---|
| **Aggression** | offense weighting & target choice | Score bonus to damage actions = `Aggression × 4%`; at ≥7 prefers lowest-Integrity target (executes), at ≤3 prefers nearest |
| **Caution** | self-preservation | Self-shield/retreat triggers at Integrity below `15% + Caution × 4%`; at ≥8 will pre-shield before boss telegraphs |
| **Loyalty** | ally protection | Heal/cleanse/guard scored at `Loyalty × 5%` bonus; at ≥8 will body-block a telegraph aimed at a Crashed-adjacent ally |
| **Independence** | obedience to the queue | Slot 1 always executes. If Independence ≥7 and an alternative scores >25% higher, the agent replaces queue slots 2–3 (UI shows a "improvised" flicker); at ≤3 the queue is gospel and the agent idles rather than improvise |

Two locked guarantees: queued slot 1 is **never** overridden, and the AI never spends the party's only combat res (Duct Tape Doctrine) or last cleanse on a >70% Integrity target (hard rule above utility). Banter barks key off axis thresholds and pipeline events (`Cue.Banter.*`), reusing the parley line-bank tech from `02-negotiation-system.md`.

---

## 7. Enemy & Boss Design Rules — the Eight Gauntlet Mandates

Wild/orphaned trash uses the same attribute set with enemy Integrity budgets (§9). Elites add one Mark-able gimmick. **Gauntlet bosses are mechanical sermons: each enforces the verification gate it is named for.** These mandates are binding on encounter design (`05-world-design.md` owns arenas and full boss kits).

| # | Gauntlet (zone) | Boss | Mandate (locked mechanic) |
|---|---|---|---|
| 1 | **Planning** (The Stacks) | SCOPE-CREEP | Boss is invulnerable (`Gate.Boss.Planning`) until the player, in Command Mode, commits a full 3-slot plan for all 3 agents; executing that committed plan uninterrupted breaks the shield for 20s. Mid-fight, "scope tendrils" spawn that re-shield him unless the *committed* plan included an answer. Plan, then execute. |
| 2 | **Test** (The Stacks) | HEISENBUG | Boss is immune until the player **proves the strategy on adds first**: each boss phase spawns 3 "test case" adds that each die only to a specific interaction (e.g. Exploit-on-Marked, Field damage, Shield-block-then-counter). Demonstrating all 3 stamps a "suite green" buff that opens the boss for one burn window. Flaky twist: one test case randomly re-runs. |
| 3 | **Build** (The Foundry) | MONOLITH | Continuous integration: boss reassembles 25% armor every 30s unless a **Pipeline combo** landed in that window. Each landed pipeline locks one armor plate off permanently. No pipelines, no progress — integrate continuously or fight forever. |
| 4 | **Rollback** (The Foundry) | REGRESSION | Teaches checkpointing. A Command-Mode free action, **Checkpoint** (60s cooldown, this fight grants it; kept afterward), banks the party's full state. REGRESSION's "Corruption Cascade" (90s telegraph) is deliberately unsurvivable — the only counter is restoring the banked checkpoint, which also rewinds boss adds. No checkpoint banked = wipe. Save your state before you ship. |
| 5 | **Review** (Gardens of Memory) | THE RUBBER STAMP | Boss copies the player's last 3 used abilities and replays them back amplified; using the same ability twice consecutively is reflected for double. After each copy cycle, a "diff" weak point opens — hitting it with an ability *not yet used this fight* crits automatically. Variety is review rigor. |
| 6 | **Security** (The Vault) | HONEYPOT | Zero-trust fight. Boss is cloaked and untelegraphed unless `State.Marked` (audit before you trust). Least-privilege: a rotating "privilege token" makes only one party agent able to damage the boss at a time (token reassignable in Command Mode, 0 CP); the other two handle intrusion adds. Decoy boss copies punish attacking unmarked targets. |
| 7 | **Owner Approval** (The Vault) | THE SOCKPUPPET | Every 25s the fight pauses itself with an **Authorization Prompt**: the boss requests a capability ("grant me the east turrets") with evidence on screen; the player grants or denies within one Command-Mode decision. Correct denials (forged evidence — readable tells) stagger the boss 6s; wrong grants buff it; correct grants of *legitimate* requests (rare, real) spawn an ally turret. Nothing merges without the owner's eyes. |
| 8 | **Release** (The Gate Spire) | CRUNCHTIME | Go/no-go. Four gate-pylons (Planning/Test/Security/Review mini-checks reprising mandates 1, 2, 5, 6) surround the arena; boss damage only counts during a **green launch window** earned by clearing all four. Attempting to burn the boss with pylons unresolved (shipping with known bugs) triggers Enrage: +50% boss damage until the player backs off. Three windows ends it; the Council finale follows (`05-world-design.md`). |

Boss-design global rules: every unavoidable mechanic has a ≥2s telegraph; every mandate is teachable in Story difficulty via an extra hint banner; bosses are immune to `State.Segfault` but **not** to Marks (pipelines must always work); each boss drops 1 Checksum Shard on first clear (`07-progression-neural-network.md` §6).

---

## 8. Damage Formula (locked) & Worked Examples

```
FinalDamage = AbilityBase × (1 + Throughput/100) × (1 − Mit) × DomainMult
            × AffinityMult × ExploitMult × CritMult × PipelineMult × DiffMult × Variance

Mit          = Resilience_def / (Resilience_def + 120 + 6 × Level_attacker)
DomainMult   = 1.5 / 1.0 / 0.75 from §2 chart
AffinityMult = 1 + DomainAffinity/200   (only when ability domain == agent domain, else 1.0)
ExploitMult  = 1.5 when an Exploit consumes a valid Mark/state, else 1.0
CritMult     = 1.5  (chance = Heat × 0.5%, cap 40%)
PipelineMult = 1.75 on the Detonate hit only, else 1.0
DiffMult     = per §10
Variance     = uniform [0.95, 1.05], drawn from the save's CombatStream RNG
```

**Worked example A — early-game Strike.** AXIOM (Architecture, Controller) L12, Throughput base 14 → `14 × G(12)=1.746` → **24**; Affinity base 12 → 12 + 0.4×11 ≈ **16**. Ability *Load-Bearing Strike* (`Ability.Strike.LoadBearing`, `Damage.Domain.Architecture`, base 90) vs a QA trash unit L11, Resilience base 10 → **17**.
`Mit = 17/(17+120+72) = 0.081`. Damage = 90 × 1.24 × 0.919 × **1.5** (Arch→QA) × 1.08 × 1.0 × 1.0 × 1.0 × var ≈ **166** non-crit (158–174 with variance). Against an Architecture-resisting Release unit instead: ×0.75 → ≈ 83 — the chart visibly matters.

**Worked example B — mid-game Pipeline detonation.** Setup: ORACLE (Research) Marks → CIPHER (Security) Exploits (opens **Zero-Day Disclosure** window) → COMMANDER (Release) cannot detonate into Security... so BREACH detonates. Take the Exploit hit itself: CIPHER L30, Throughput base 16 → `16×3.28` → **52**; Affinity ≈ **25**. *Credential Harvest* (Exploit, base 140, `Damage.Domain.Security`) vs a **Release** elite L30, Resilience base 14 → **46**, target Marked.
`Mit = 46/(46+120+180) = 0.133`. Damage = 140 × 1.52 × 0.867 × **1.5** (Sec→Rel) × 1.125 × **1.5** (Exploit-on-Mark) × 1.5 (crit) ≈ **700**. The follow-up Detonate inside the window adds its own hit at ×1.75 with 50% mitigation ignored (pipeline 6 rider). A full pipeline against an on-ring target deletes ~20% of an elite — exactly the intended reward.

---

## 9. TTK Targets & Enemy Integrity Budgets (locked)

Reference party DPS at level L ≈ `3 agents × avg ability (≈150 × G(L)/G(12)) / 3.0s recovery`. Enemy Integrity is budgeted as a multiple of **average at-level player-agent Integrity** `P(L)`:

| Enemy class | Integrity budget | Pack size | TTK target |
|---|---|---|---|
| Trash | 5 × P(L) per unit | 3–5 | **20–40s per pack** |
| Elite | 18 × P(L) | 1 (+2 trash) | **60–90s** |
| Gauntlet boss | 80 × P(L), split across phases | 1 + mandated adds | **4–7 min** including mandate downtime |

These three rows are the tuning contract; ability base numbers may move, the TTK rows may not. Verification: headless automation (`UnrealEditor-Cmd` test, per master plan §5) runs scripted optimal-play fights per tier and asserts the TTK bands each build.

---

## 10. Difficulty Modes

| Mode | Player dmg | Damage taken | CP regen | Boss mandates |
|---|---|---|---|---|
| **Story** | ×1.25 | ×0.60 | 1 per 3s | Hint banners on; mandate failure forgiveness (1 free retry window per phase) |
| **Standard** | ×1.0 | ×1.0 | 1 per 4s | As specified |
| **Architect** | ×1.0 | ×1.30 | 1 per 5s | Each boss gains one extra mandate wrinkle (authored, in `05-world-design.md`); hot-pipeline chains required for par times |

Applied as a single `GE_Difficulty_<Mode>` infinite GameplayEffect (tag `Difficulty.*`), switchable outside combat at any time, no rewards penalty — completion is completion. **Tactical-Pause-Always** (independent toggle, any difficulty): auto-pauses on encounter start, on any party member <30% Integrity, on Mark expiry ≤2s, and on boss Authorization Prompts. This toggle plus Story mode is the accessibility floor for combat.

---

## 11. GAS Implementation Mapping

| Design construct | GAS / UE construct |
|---|---|
| All seven attributes | `USynapseAttributeSet` (AttributeData + PreAttributeChange clamps; Mit math in `PostGameplayEffectExecute`) |
| Every modifier — damage, buffs, marks, shields, difficulty, Den buffs, network synergies | **GameplayEffects only.** No direct attribute pokes anywhere in code. Damage via a single `UDamageExecCalc` (ExecutionCalculation implementing §8) |
| Base character | `ASynapseAgentCharacter` (player & enemy alike) owning `UAbilitySystemComponent`; player ASCs live on the PlayerState-equivalent persistent `USynapseRosterSubsystem` so bench/swap retains state |
| Abilities | `USynapseGameplayAbility` base (cost = Bandwidth `GE`, cooldown `GE` with `Cooldown.Ability.*` tag, activation-required/blocked tags per §3.1) |
| Marks, states | `GameplayEffect`s granting `State.*` tags; Pipeline windows = short-duration GEs granting `Combo.Window.*` |
| Pipeline detection | `USynapsePipelineSubsystem` listening to ASC gameplay-event delegates (`Event.Mark.Applied`, `Event.Exploit.Consumed`); validates wiring vs the network save, applies window GEs |
| Command queue | `USynapseCommandQueueComponent` per agent; pause via `UGameplayStatics::SetGlobalTimeDilation(0)` + input-context swap (CommonUI) |
| Ally AI | `USynapseAgentBrain` utility scorer (no Behavior Trees for allies; BTs allowed for trash) |
| VFX/SFX/camera shakes | **GameplayCues exclusively**: `Cue.Damage.Domain.*`, `Cue.Pipeline.*`, `Cue.State.*`, `Cue.Banter.*` — Niagara + MetaSounds bound in cue notifies, so combat logic compiles headless with zero content references |
| Type chart, TTK budgets, archetype bands | DataTables: `DT_DomainChart`, `DT_EnemyBudgets`, `DT_ArchetypeBands` |
| Determinism | Named RNG streams (`CombatStream`) in `USynapseSaveSubsystem`; no `FMath::FRand` in combat code |

No replication anywhere: all GEs run `Minimal`-replication-off, single-process — the pure-single-player dividend (locked decision #8) spent on simulation richness, not netcode.
