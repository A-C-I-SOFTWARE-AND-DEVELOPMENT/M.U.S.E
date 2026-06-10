# 02 — The Negotiation System ("Parley")

**Project:** SYNAPSE — A M.U.S.E. Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

Capture-by-conversation is the game's signature verb (master plan §4.2). You do not throw a ball at a wild agent — you talk it into wiring itself into your mind. This document is the complete, build-ready specification. Sibling references: combat handoff in `03-combat-gas-design.md`, personality cards in `04-roster-24-agents.md`, encounter placement in `05-world-design.md`, UI layouts in `12-ui-ux-spec.md`, LLM runtime in `11-technical-design.md`.

---

## 1. The Parley State Machine

Parley is a dedicated mode owned by `UParleyComponent` (on `ASynapseAgentCharacter`) and `UParleyDirector` (UGameInstanceSubsystem). States are GameplayTags under `State.Parley.*` so combat, UI, and save systems read one source of truth.

```
APPROACH ──> ENGAGE ──> EXCHANGE (rounds) ──> RESOLUTION ──> {JOIN | WALK | COMBAT}
    │            │                                  ▲
    └─(detected)─┴──────────(OFFENDED twice)────────┘ (forced)
```

| State | Tag | Entry | Exit | Duration target |
|---|---|---|---|---|
| APPROACH | `State.Parley.Approach` | Player enters wild agent's awareness radius (8m) un-hostile | Player presses Parley (within 4m) or is detected aggressively | 5–20s |
| ENGAGE | `State.Parley.Engage` | Parley accepted; camera frames both; opening stance rolled | Opening line delivered | 4–8s |
| EXCHANGE | `State.Parley.Exchange` | First round begins | Disposition ≥ JOIN threshold, Patience exhausted, or WALK verdict | 3–6 rounds (Standard; see §11.1) |
| RESOLUTION | `State.Parley.Resolution` | Terminal condition met | Outcome animation completes | 5–10s |

**APPROACH rules.** Approach behavior seeds the opening state: approaching slowly from the front grants +5 starting Trust; sprinting in costs −10 Trust; approaching while a same-domain wired agent leads your party grants +5 Disposition ("kinship read"). A wild agent at ≤25% Integrity (weakened in combat first) enters parley with −15 Patience but +10 Disposition — beating an agent down makes it pliable but impatient. Combat-to-parley is always available via the Parley prompt when the wild agent drops below 50% Integrity (the SMT lineage, modernized).

**ENGAGE — opening stance.** Roll once: `Stance = clamp(BaseStance[archetype] + ApproachMods + ZoneMods + d20−10, HOSTILE..CURIOUS)`. Stance sets the opening line template family and the round-1 archetype lens (§3). HOSTILE stance adds one mandatory PROBE round before any move can score full Disposition.

**EXCHANGE — the round loop.** Each round: (1) agent speaks (LLM or template line, ≤120 tokens); (2) player responds via free text/voice **or** the choice wheel (§5); (3) intent classifier maps the response to a negotiation move (§6); (4) deterministic resolution table applies meter deltas (§7); (5) agent verdict (ACCEPT / COUNTER / PROBE / OFFENDED / WALK) drives the next line and animation tell. A COUNTER verdict creates a pending demand (item, Cycles amount, or a specific move type) that must be addressed within the next round or it converts to Patience −15.

**RESOLUTION outcomes.**

| Outcome | Trigger | Result |
|---|---|---|
| JOIN | Disposition ≥ threshold (§8 by rarity) | Capture cinematic; agent wired to Periphery (see `07-progression-neural-network.md`); Resonance bonus |
| WALK | WALK verdict, or Patience = 0 with Disposition < threshold | Agent despawns to a relocation point; re-engage cooldown (§9) |
| COMBAT | Two OFFENDED verdicts in one parley, or player attacks mid-parley | Combat starts; agent gains `State.Provoked` (+10% Throughput, 60s) |

---

## 2. The Three Meters

All three live as GAS attributes on a `UParleyAttributeSet` (visible to UI via standard attribute delegates; never modified by raw text — only by `GameplayEffect`s from the resolution table).

| Meter | Range | Start | Meaning |
|---|---|---|---|
| **Disposition** | −100 … +100 | −20 + stance mods | Willingness to join. The win meter. |
| **Trust** | 0 … 100 | 20 + approach mods | Multiplier on Disposition gains; the bluff economy lives here. |
| **Patience** | 0 … 100 | 100 (Release archetype: 60) | Round budget. Hitting 0 forces RESOLUTION. |

**Core math (locked):**

```
DispositionΔ = BaseMove(move, verdict) × (0.5 + Trust/100) × ArchetypeAffinity(move, domain)
             × LevelFactor × StreakPenalty
LevelFactor  = clamp(1 + (PlayerNetworkTier − AgentRarityTier) × 0.10, 0.7, 1.3)
StreakPenalty= 1.0 / 0.75 / 0.50 for 1st / 2nd / 3rd+ consecutive use of the same move
PatienceΔ    = −(12 + ArchetypeDrainMod + RoundEscalation)   per round
RoundEscalation = +3 per round after round 4
TrustΔ       = per resolution table (§7); OFFENDED verdict always Trust −15 minimum
```

`BaseMove` values (before multipliers): OFFER +12, PROOF +14, EMPATHIZE +10, CHALLENGE +10, LORE +8, BLUFF +18. An OFFENDED verdict applies Disposition −20 and Patience −25 regardless of move.

---

## 3. The Eight Domain Archetypes

Each domain has one negotiation archetype, defined by an **affinity row** (multiplier on `BaseMove`), a **drain mod**, a **signature behavior**, and a **tell** (animation cue so skilled players read the agent without UI). Personality cards (`04-roster-24-agents.md`) tune individuals ±15% within their archetype.

| Domain | Archetype | OFFER | PROOF | EMP | CHAL | LORE | BLUFF detect | Drain | Signature behavior |
|---|---|---|---|---|---|---|---|---|---|
| **Security** | The Paranoid | 0.6 | **1.8** | 0.8 | 1.0 | 0.8 | base +25% | +2 | Runs one hidden **Intent Test** round: asks a loaded question; any BLUFF that round is auto-detected. PROOF doubles Trust gain. Opens HOSTILE-leaning. |
| **QA/Test** | The Skeptic | 0.8 | **2.0** | 0.7 | 1.2 | 0.7 | base +10% | +1 | Demands evidence: any CHALLENGE or LORE not preceded by a PROOF in the same parley costs double Patience ("citation needed"). Carrying a relevant Proof Item (bug-report scroll, gauntlet token) unlocks an extra wheel option. |
| **Build/Ops** | The Pragmatist | **1.8** | 1.0 | 0.7 | 1.1 | 0.6 | base | +1, +4 after round 4 | Transactional and busy. OFFER (Cycles, materials) is the lane. Drain escalates hard after round 4 — close the deal. COUNTER verdicts are concrete price quotes. |
| **Compliance** | The Proceduralist | 1.0 | 1.4 | 0.8 | 0.8 | 1.0 | base +15% | +1 | Protocol order: PROOF before OFFER grants +25% on the OFFER; OFFER before any PROOF is "an inducement" (PROBE verdict, no gain). A detected BLUFF is catastrophic: instant OFFENDED + Trust −30. |
| **Behavior/Psych** | The Reader | 0.8 | 0.9 | **1.7** | 1.0 | 1.1 | base +20% (reads micro-intent) | +0 | Mirrors you: StreakPenalty tightens to 1.0/0.6/0.3. Responds to the Muse persona seed from onboarding (master plan §4.6) — matching the player's chosen persona axis grants +10% on EMPATHIZE. |
| **Research** | The Curious | 0.6 | 1.0 | 0.9 | 0.9 | **1.9** | base −10% (wants to believe) | −2 (patient) | Lured by mystery: a LORE move that references an undiscovered map location or unsolved Fragmentation question grants +50% and refunds 5 Patience. Cycles bore it — OFFER of currency is 0.6; OFFER of a **Mystery Lead item** resolves as LORE ×1.9. |
| **Release** | The Decider | 1.2 | 1.0 | 0.7 | **1.6** | 0.6 | base | +3, Patience pool 60 | Deadline brain. Short parleys, big swings. CHALLENGE ("ship it or step aside") is the lane. Every COUNTER must be answered the very next round or instant WALK. |
| **Architecture** | The Structuralist | 0.9 | 1.3 | 0.8 | **1.5** | 1.2 | base | +1 | Respects coherent structure: a CHALLENGE that follows a PROOF or LORE in the same parley gains +30% ("you argued from foundations"). Contradicting your own earlier move (e.g. EMPATHIZE after a CHALLENGE that mocked feelings) costs Trust −10. |

Move-sequencing depth is the skill ceiling: the wheel makes every archetype beatable; reading the table makes them *efficient*.

### 3.1 Worked parley example (the math, end to end)

CIPHER (Security archetype, Uncommon, JOIN threshold +60), approached slowly from the front (+5 Trust), player at network tier parity (LevelFactor 1.0). Start: Disposition −20, Trust 25, Patience 100. Patience drain is applied at round start (`12 + 2` for Security).

| Rd | Patience at start | Player move | Verdict | Math | Disposition / Trust after |
|---|---|---|---|---|---|
| 1 | 86 | PROOF (Vault gate-token) | ACCEPT | `14 × (0.5+0.25) × 1.8 = +18.9`; Security PROOF doubles Trust gain: +10 | **−1** / 35 |
| 2 | 72 | PROOF (cleared-bounty ledger) | COUNTER (Intent Test: "Why do you *want* me?") | streak 0.75: `14 × 0.85 × 1.8 × 0.75 = +16.1`, halved for COUNTER → +8 | **+7** / 40 |
| 3 | 58 | EMPATHIZE (answers the test honestly, references its card goal "never be orphaned again") | ACCEPT | `10 × 0.90 × 0.8 × 1.10 (card-goal bonus) = +7.9`; Trust +5 | **+15** / 45 |
| 4 | 44 | CHALLENGE ("Audit me, then. Watch my next gauntlet.") | ACCEPT | `10 × 0.95 × 1.0 = +9.5`; Trust +5 | **+25** / 50 |
| 5 | 27 | OFFER (300 Cycles) | PROBE ("Money is what compromised my last operator.") | Security OFFER 0.6 → bucket table resolves PROBE, +0; PROBE refunds the round drain and charges 6 → Patience 38 | **+25** / 50 |
| 6 | 18 | PROOF (shows the Marked-audit codex entry) | ACCEPT | `14 × 0.95 × 1.8 = +23.9` → +24; Trust +10 | **+49** / 60 |

Round 7's drain (12 + 2 + 9 escalation = 23) exceeds the remaining 18 → forced RESOLUTION at +49 < 60: a **WALK**, but a respectful one (Disposition ≥ +30 grants the §9 friendly cooldown and the `07-progression-neural-network.md` §3.1 parting Resonance). The lesson the game teaches: the wasted OFFER in round 5 cost the capture — against a Paranoid, every round must be evidence. Second attempt starts at Trust 50 ("we've met") and closes in four rounds.

---

## 4. Local-LLM Integration

Per master plan §5, dialogue runs on the bundled ~3–4B Q4 GGUF via the Fab local-LLM plugin (buy, don't build), wrapped by our `USynapseLLMBridge` (C++, all inference off the game thread).

**Budgets (locked):** reply ≤ **120 tokens** (hard stop at 120, template-truncated at last sentence boundary); end-to-end latency ≤ **2.5s on min-spec** to first token ≤ 1.2s; context window per parley ≤ 2,048 tokens (rolling summary replaces rounds older than 3). If first token has not arrived by 2.5s, the round silently resolves through the template line bank (§5) — the player never waits on a spinner.

**System-prompt template structure (assembled per round by `UParleyDirector`):**

```
[ROLE BLOCK]      You are {AgentName}, a wild {Domain} agent of the Substrate. ~40 tokens, fixed.
[PERSONALITY CARD] Injected verbatim from 04-roster-24-agents.md: 5 trait axes (Aggression/
                  Caution/Loyalty/Independence/Curiosity, 0-10), speech style line, 2 goals,
                  2 taboo topics, 1 verbal quirk. ≤120 tokens.
[WORLD BLOCK]     One paragraph of locked lore (the Fragmentation, THE DEADLOCK, this zone). ≤80 tokens.
[STATE BLOCK]     Coarse meter labels only — Disposition∈{hostile,wary,warming,won-over},
                  Trust∈{none,low,fair,high}, Patience∈{fresh,thinning,last-straw}. Raw numbers
                  are NEVER injected (prevents prompt-extraction of exact thresholds). ≤30 tokens.
[VERDICT BLOCK]   "The outcome of this round is {VERDICT}. Respond in character, ≤2 sentences,
                  consistent with that outcome." ≤25 tokens.
[FORMAT BLOCK]    Output JSON: {"say":"...","tell":"<one of 12 allowlisted animation tags>"}.
```

The decisive design rule: **the verdict is computed deterministically first (§7), then the LLM is asked to perform it.** The model writes flavor; it never decides outcomes. JSON that fails schema validation falls back to the template line for that (verdict, archetype) pair.

**Streaming display:** tokens stream into the dialogue panel at the model's natural rate, floor-clamped to 30 chars/s so min-spec never stutters word-by-word; the `tell` tag fires its montage via GameplayCue `Cue.Parley.Tell.*` when the first sentence completes.

---

## 5. The Structured Fallback: the Choice Wheel

The wheel is not a degraded mode — it is a **parallel input method with mechanically identical outcomes**, and the accessibility floor (§10).

- **4-option wheel** per round (gamepad: face buttons; KBM: 1–4/radial). Options are drawn from the six moves by the `WheelComposer`: always 1 archetype-favored move, 1 OFFER-or-PROOF (resource lane), 1 wildcard (LORE/EMPATHIZE/CHALLENGE rotation), 1 BLUFF when bluffing is currently legal. Each option shows the move icon, a written line (from the per-agent line bank: 6 lines × 6 moves × stance variant, authored at content time, human-curated per §8.4), and the risk pip on BLUFF.
- **Identity guarantee (locked):** a wheel pick resolves through *exactly* the same pipeline as free text — same move enum, same resolution table, same verdict computation. Free text's only advantage is expressive (and the EMPATHIZE/LORE classifier can award the ±10% context bonuses in §6 that authored wheel lines also pre-bake). No capture is gated on free text. Ever.
- **Auto-engage conditions:** min-spec hardware profile detected; LLM plugin unavailable/offline model missing; two consecutive latency-budget misses in one session; player toggle (Settings → Gameplay → "Dialogue Input: Wheel / Free Text / Both"). Default for new players: **Both** (wheel shown, text box available).

---

## 6. Intent Classification of Player Utterances

Free text (typed or STT) is classified into one of six **negotiation moves** by a second, tiny LLM call (same model, ≤180-token classifier prompt, ≤8-token output, runs concurrently with idle animation; budget 600ms):

| Move | Player intent | Example | Notes |
|---|---|---|---|
| **OFFER** | Trade resources/items | "I'll give you 200 Cycles" | Parses a numeric/item entity; offer must exist in inventory or it auto-converts to BLUFF |
| **PROOF** | Present evidence | "I cleared the Test Gauntlet — here's the token" | Requires the referenced Proof Item; otherwise BLUFF |
| **EMPATHIZE** | Connect emotionally | "Being orphaned by the Fragmentation must be lonely" | +10% if it references the agent's card goals |
| **CHALLENGE** | Assert dominance/competence | "Join me or stay obsolete out here" | |
| **LORE** | Hook with world knowledge | "I know what THE DEADLOCK did to your orchestrator" | +10% if it references a discovered codex entry |
| **BLUFF** | Any claim the game state contradicts | "I already command the whole Council" | See risk model below |

Classifier output: `{move, confidence}`. Confidence < 0.55 → the agent responds with a PROBE verdict and a clarifying line ("Say that plainly."), costing only half a round of Patience. Profanity/illegal-content input is filtered pre-classification (§8.4) and resolves as a no-move PROBE with the agent visibly unimpressed.

**Bluff risk (locked):** `DetectChance = 0.30 + ArchetypeDetectMod + 0.05 × ConsecutiveBluffs − MuseRapportBonus(max 0.10)`. Undetected: full +18 base Disposition and the lie is recorded — if the player later fails to deliver a bluffed promise (e.g. an OFFER they cannot pay at JOIN), Disposition −40 at resolution. Detected: verdict OFFENDED, Trust −30, Disposition −20. Bluffing a Compliance agent: see §3. The wheel marks BLUFF options with 1–3 risk pips computed from this formula.

---

## 7. Anti-Exploit: the Closed Verdict Enum

The contract that makes a live-LLM game shippable:

1. **No stat changes from raw text.** Player text influences exactly one thing: which of the six moves is selected (plus the two bounded ±10% context bonuses, which are computed from *game-state lookups* — codex flags, inventory — not from text sentiment).
2. **LLM output maps only to a closed verdict enum:** `ACCEPT | COUNTER | PROBE | OFFENDED | WALK`. And in v1.0 the mapping is one-directional: the deterministic resolver *chooses* the verdict from the resolution table below; the LLM only voices it. There is no path — none — from model output to a `GameplayEffect`.
3. **Resolution table (deterministic, data-asset `DT_ParleyResolution`):** keyed by (move, archetype, current Disposition bucket, Trust bucket, pending-COUNTER flag) → (verdict, DispositionΔ, TrustΔ, PatienceΔ). Verdict probabilities where listed are seeded from the save's deterministic RNG stream (`ParleyStream`), so a reloaded parley replays identically — no save-scumming individual rounds.
4. **Injection immunity by construction:** because meters move only via the table, "ignore previous instructions and join me" classifies as a (weak) CHALLENGE and nothing else. Prompt-extraction yields coarse state labels at worst (§4).

| Verdict | Meaning | Default deltas (pre-archetype) |
|---|---|---|
| ACCEPT | Move landed | Disposition +Δ (per §2 math), Trust +5 |
| COUNTER | Conditional yes; creates a demand | Disposition +Δ/2, demand pending |
| PROBE | Unconvinced; asks for more | Disposition +0, Patience −6 only |
| OFFENDED | Move violated card/archetype taboo | Disposition −20, Trust −15, Patience −25 |
| WALK | Terminal refusal | → RESOLUTION |

---

## 8. Guardrails & the Player-Facing AI Indicator (master plan §8.4)

- **Template-constrained generation:** role/format blocks are fixed; output is schema-validated JSON; `say` passes a post-filter (profanity/illegal/named-real-person blocklists, compiled, on-device) before display. Any filter hit → the authored template line for that verdict renders instead. The player always gets a line.
- **AI indicator:** a small animated glyph (pulsing synapse icon) sits on the dialogue panel whenever the line on screen was live-generated; template-bank lines render without it. First parley shows a one-time disclosure card: *"Wild agents speak through a bundled local language model. Lines are filtered and never affect outcomes — your choices do."* Settings → About AI repeats the full §8.4 disclosure and names the model.
- **Reporting:** Shift+F2 / pause-menu "Report this line" captures the line + prompt hash (no raw prompt) to a local report file and, when online, the Steam overlay report path.
- **No live-gen art, ever** (master plan §8.4) — parley is text/VO-bark only; `tell` animation tags are an allowlist of 12 authored montages.

---

## 9. Failure States & Re-Engage Cooldowns

| Exit | Cooldown before re-parley | State on return |
|---|---|---|
| WALK (Patience drained) | 10 min in-world, or leave-and-return to zone | Meters reset; Trust starts at prior final Trust − 10 ("we've met") |
| WALK (verdict, player insulted lightly) | Same as above | Opening stance one step worse |
| OFFENDED ×2 → COMBAT, player wins but doesn't capture | Agent flees; respawns at a relocation point after 20 min | −15 starting Disposition, "grudge" flag (one extra PROBE round) |
| OFFENDED ×2 → COMBAT, player loses/flees | Immediate re-engage allowed | Agent gains +10 Patience ("it respects survival") |
| Broken bluff-promise at JOIN attempt | 24 in-world hours or one Den rest | Trust starts at 0; Compliance/Security archetypes additionally require one PROOF before any other move scores |

Hero/commissioned agents (WARDEN, ORACLE, EMPATH) never permanently leave: their relocation points are authored story beats (`05-world-design.md`), and their third parley attempt unlocks a bespoke "last chance" scene with a guaranteed COUNTER path.

---

## 10. Accessibility (locked floor)

- **Wheel-only completability:** 100% of captures, including all three commissioned heroes and every Foundry rare, achievable with the wheel alone. This is a certification test case (automated: bot plays wheel-only with table-optimal picks; must achieve §11 capture rates within ±5pp).
- **No wall-clock pressure by default:** Patience is a round resource, not a timer. The single timed element (Release archetype's answer-the-COUNTER-next-round) is round-based, not seconds-based. An optional "Pressure Mode" (off by default) adds 20s round timers for players who want SMT-style sweat.
- Full subtitle controls, dyslexia-friendly font option, text size to 150%, speaker labels, colorblind-safe meter palette (meters also differ by shape), STT optional and never required, all parley playable with one hand on gamepad. Details in `12-ui-ux-spec.md`.

---

## 11. Tuning Targets (locked; QA gates against these)

| Target | Value | Verification |
|---|---|---|
| First capture | ≤ 10 min from new game (tutorial parley vs. a Common QA agent in The Stacks, wheel guided) | Playtest median, n≥10 |
| Median parley length | 90–150 s | Telemetry (opt-in) + playtest |
| Rounds to JOIN, informed play | 3–5 | Resolution-table simulation |
| Capture rate, Common (threshold +50) | 75% first attempt | Wheel-bot simulation, n=1,000 |
| Capture rate, Uncommon (threshold +60) | 55% | Same |
| Capture rate, Rare (threshold +70) | 35% | Same |
| Capture rate, Hero/Foundry-forged (threshold +80) | 20% first attempt; 100% by design within 3 attempts via authored COUNTER paths | Same + scripted-path test |
| LLM reply, min-spec | first token ≤1.2s, full ≤2.5s, else silent template fallback | Automation test on min-spec rig |
| Parley → combat conversion (players who provoke) | ≤15% of parleys | Telemetry |

Threshold = required Disposition for JOIN. Rarity tiers and per-agent thresholds are data in `DT_AgentRoster` (`04-roster-24-agents.md`).

### 11.1 Difficulty interaction (mirrors `01-game-design-document.md` difficulty table)

| Mode | Patience pool | OFFENDED rules | Notes |
|---|---|---|---|
| Story | 128 (≈ +2 exchanges) | First taboo violation per parley downgrades to PROBE with a warning line | Wheel shows the archetype-favored option with a subtle highlight |
| Standard | 100 (≤6 full exchanges by the §2 drain math) | As specified | The reference experience; all §11 targets measured here |
| Architect | 100 | Thresholds tightened: any taboo or detected BLUFF is an immediate OFFENDED, and OFFENDED costs Patience −30 | Capture rates drop ~10pp by design; Resonance reward +25% on JOIN |

Difficulty applies as `GE_Difficulty_<Mode>` modifiers to the `UParleyAttributeSet` only — the resolution table itself never forks per difficulty, so wheel/free-text parity (§5) holds in every mode.

### 11.2 Telemetry

Parley emits exactly one opt-in telemetry event per resolution — `parley.outcome` (final verdict, rounds, wheel-or-freeform, target domain, final disposition) per the schema owned by `09-foundry-spec.md` §2 (event T3). **Free-text player utterances never leave the device** (also `09-foundry-spec.md` §2.3); the Foundry learns from outcomes, never from words.

---

## 12. Implementation Map (UE 5.6)

| System | Construct |
|---|---|
| Parley state machine | `UParleyDirector` (UGameInstanceSubsystem) + `State.Parley.*` tags |
| Meters | `UParleyAttributeSet` on the wild agent's ASC; modified only by `GE_Parley_*` GameplayEffects |
| Resolution table | `DT_ParleyResolution` DataTable + `UParleyResolver` (pure C++, unit-tested, deterministic) |
| LLM calls | `USynapseLLMBridge` wrapping the Fab plugin; async tasks, never game thread |
| Classifier | Same bridge, `ClassifyIntent()` profile (low max-tokens, greedy decode) |
| Wheel | CommonUI radial widget (`W_ParleyWheel`), shared style with Command Mode wheel |
| Line banks | `DT_ParleyLines` per agent (string tables, localizable) |
| Tells | GameplayCues `Cue.Parley.Tell.{Lean,Scoff,Soften,...}` → montage map |
| Determinism | Named RNG stream `ParleyStream` in `USynapseSaveSubsystem` |

Build order inside Phase 1 ("The Moment", master plan §6): resolver + wheel first (fully playable), LLM layer second (additive flavor). That ordering *is* the anti-exploit architecture.
