# 09 — The Foundry Specification
### Agents born from your struggle — run honestly

**Project:** SYNAPSE — A muse Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

---

## 1. Purpose & scope

The Foundry is the master plan §4.7 system: the hosted brain observes a consenting player's
*measured* struggle, hypothesizes a tailored helper agent, **validates it in simulation against
that player's actual failures**, and ships it into their world as a discoverable rare — with the
validation receipts printed on the card.

Three laws govern everything below:

1. **Honesty law.** The Foundry never claims a benefit it did not measure. Every player-facing
   number traces to a simulation batch with `n`, baseline, and confidence interval.
2. **Bounded-generation law.** The hosted LLM selects and parameterizes from closed libraries —
   it never emits raw stats, raw abilities, raw art, or free-form mechanics. LLM text NEVER
   mutates stats directly (same rule as `02-negotiation-system.md`).
3. **Optionality law.** The Foundry is opt-in, disclosed, fully skippable, and silently absent
   offline. A tier-1 (local-only) player has a complete game and never sees a nag.

Client module: `SynapseFoundryClient` (see `11-technical-design.md` §2.5). Server: the hosted
brain (master plan P3). Gateway route family `/v1/foundry/*` is **future, additive** work per the
coupling rule — specified here, implemented later via `scripts/generate_cockpit_contract.py` and
frozen by `tests/gateway/test_cockpit_contract_freeze.py`. No gateway code changes this sprint.

---

## 2. Telemetry design

### 2.1 Consent model

- **Opt-in at first run**, default OFF. The consent screen shows the *exact* event list below
  (not a summary), the retention period, and a "what we never collect" panel. Consent UI layout,
  copy, and re-prompt rules are owned by `01-game-design-document.md` (Options → Privacy).
- Consent is revocable at any time from Options. Revocation stops egress immediately
  (client-side gate in `SynapseCore`, see `11-technical-design.md` §2.1) and queues a
  server-side delete request for that player's telemetry.
- Telemetry consent and Foundry enablement are **two separate toggles**. Telemetry-on/Foundry-off
  is a valid state (contributes nothing to the player; data still bounded by this spec).

### 2.2 Exact event list (the complete set — nothing else is sent)

All events share an envelope:

```json
{
  "v": 1,
  "event": "<type>",
  "player_id": "anon-<uuid4>",        // random per-install ID; not Steam ID, not hardware ID
  "session_id": "<uuid4>",
  "ts": "2026-06-10T18:42:11Z",
  "build": "synapse-1.0.3+win64",
  "act": 2
}
```

| # | Event type | Payload fields (all of them) |
|---|---|---|
| T1 | `combat.outcome` | `encounter_id:str`, `result:enum{WIN,LOSS,FLEE}`, `duration_s:int`, `party:[agent_id×3]`, `enemy_set:[agent_id]`, `party_avg_level:int`, `deaths:[agent_id]`, `damage_taken_by_school:{domain:str→float}`, `pipelines_triggered:int`, `pause_count:int`, `player_zone:enum` |
| T2 | `gauntlet.attempt` | `gauntlet:enum{PLANNING,BUILD,REVIEW,TEST,SECURITY,RELEASE,OWNER_APPROVAL,ROLLBACK}`, `result:enum{CLEAR,WIPE,ABANDON}`, `attempt_no:int`, `duration_s:int`, `party:[agent_id×3]`, `wipe_phase:int|null`, `cause_of_wipe:enum{BURST,ATTRITION,MECHANIC_FAIL,TIMEOUT}|null` |
| T3 | `parley.outcome` | `target_agent:agent_id`, `target_domain:enum(8)`, `verdict:enum{ACCEPT,COUNTER,PROBE,OFFENDED,WALK}` (final verdict only, per `02-negotiation-system.md`), `rounds:int`, `wheel_or_freeform:enum{WHEEL,FREEFORM}`, `disposition_final:int(0-100)` |
| T4 | `economy.snapshot` | Emitted at zone transition and every 30 min of play: `cycles:int`, `synapse_thread:int`, `checksum_shards:int`, `roster_size:int`, `network_nodes_wired:int`, `den_items:int` |
| T5 | `foundry.delivery` | `candidate_id:str`, `result:enum{DISCOVERED,RECRUITED,IGNORED_7D,DISMISSED}` (closes the loop for §11 failure analysis) |

### 2.3 What is NEVER collected

- **Free-text parley input.** The player's typed/spoken negotiation lines stay on device,
  always — only the closed verdict enum and round count leave (T3). This is the load-bearing
  privacy promise and is stated verbatim on the consent screen and the Steam AI disclosure.
- No PII: no Steam ID, account name, email, IP retention (the ingest LB strips IPs pre-queue),
  hardware fingerprint, locale beyond build SKU, or any chat/voice content.
- No keystrokes, no screenshots, no save-file contents, no Den layout geometry, no file paths.
- No telemetry of any kind from players who declined consent — there is no "anonymous minimal
  ping" tier. Off is off.

### 2.4 Retention & storage

- **90 days** rolling retention server-side, hard-enforced by a daily purge job; detectors (§3)
  only ever query a ≤90-day window so the purge can never break them.
- Player-initiated delete: honored within 72 h, confirmed by event `foundry.purged` returned to
  the client on next session.
- Storage: append-only event log (JSONL on object storage, partitioned by day) + a per-player
  rolling aggregate row (SQLite/Postgres) used by detectors. No analytics resale, no third-party
  processors beyond the host.

---

## 3. Struggle-pattern detectors

Detectors run server-side as pure functions over the player's ≤90-day window. Each fires at most
one **StruggleTicket** and then enters cooldown. Detectors never fire during act-final story
beats (suppression list shipped in config, owned by `01-game-design-document.md`).

| ID | Detector | Concrete rule | Cooldown after firing |
|---|---|---|---|
| D1 | Gauntlet wall | ≥ **4** `gauntlet.attempt` WIPEs on the **same** gauntlet within a rolling **3 h** of play time (sum of `duration_s`, not wall clock) | 14 days per gauntlet, cleared early on CLEAR |
| D2 | Domain parley futility | `parley.outcome` success rate (ACCEPT / total) **< 25%** vs a single domain over **≥ 8** attempts within 14 days | 14 days per domain, cleared on 2 consecutive ACCEPTs |
| D3 | Economy stall | Two consecutive `economy.snapshot`s ≥ 2 h apart where `cycles` declined AND `roster_size` and `network_nodes_wired` are both unchanged AND ≥ 1 LOSS in window (stuck *and* losing — not idle decoration time) | 7 days |
| D4 | Burst-death signature | Across ≥ 5 `combat.outcome` LOSSes in 7 days, ≥ 60% have `cause_of_wipe=BURST` or a single `damage_taken_by_school` domain ≥ 50% of total | 14 days per domain |

Global limits: at most **1 open StruggleTicket per player**, at most **1 Foundry rare active per
act** (delivery rule, §6), at most **3 Foundry candidates ever built per player per act** even if
earlier ones are dismissed. Tickets carry the raw evidence rows that triggered them — the
verdict card (§5.3) links back to these.

---

## 4. Hypothesis generation (hosted brain, template-constrained)

The hosted LLM receives the StruggleTicket + aggregates and must emit a **CandidateSpec** that
validates against a strict JSON Schema (`foundry/candidate_spec.schema.json`, versioned). Any
schema failure → reject and re-prompt (max 3 attempts) → ticket parked. The LLM chooses *which*
vetted pieces and *which* bounded parameters; it cannot invent pieces.

### 4.1 CandidateSpec (complete shape)

```json
{
  "spec_v": 1,
  "ticket_id": "st-...",
  "archetype": "INTERDICTOR",            // §4.2 closed library of 12
  "level": 23,                            // = player party_avg_level at ticket time
  "stat_budget": { "...": "derived, §4.3 — not LLM-authored" },
  "stat_weights": { "vitality": 0.35, "resilience": 0.30, "throughput": 0.15,
                     "latency": 0.10, "bandwidth": 0.10 },   // must sum to 1.0 ±0.001
  "abilities": ["GA_Interrupt_T2", "GA_DamageShield_T2", "GA_Taunt_T1", "GA_Cleanse_T1"],
  "personality": { "warmth": 0.7, "candor": 0.4, "patience": 0.8, "pride": 0.2,
                    "curiosity": 0.5 },   // §4.5 bounded axes, each ∈ [0,1]
  "name_seed": { "grammar": "G_GUARDIAN", "tokens": ["Bul", "wark", "of-Threads"] },
  "part_recipe": { "skeleton": "SK_Quadruped_M", "parts": ["P_Carapace_03", "P_Visor_01",
                    "P_Tail_Cable_02"], "palette": "PAL_Security_Cool", "fx_accent": "FX_Shield_Hex" },
  "barks": ["string ×8"],                 // filtered, ≤90 chars each — flavor text only
  "target_metric": { "kind": "GAUNTLET_SURVIVAL", "gauntlet": "SECURITY" }
}
```

### 4.2 The 12 helper archetypes (closed library — additions require a design-doc rev)

| Archetype | Role | Counters detector |
|---|---|---|
| INTERDICTOR | Interrupts, burst denial | D1/D4 (BURST) |
| BULWARK | Damage shields, taunt | D4 |
| TRIAGE | Heal-over-time, cleanse | D1 (ATTRITION) |
| OVERCLOCKER | Party haste, cooldown refund | D1 (TIMEOUT) |
| DIPLOMAT | Parley disposition aura, reroll token | D2 |
| LURE | Domain-specific parley opener buffs | D2 |
| PROSPECTOR | Cycles/Shard find bonuses | D3 |
| WEAVER | Synapse Thread generation, wiring discounts | D3 |
| MARKSMAN | Single-target sustained damage | D1 (mechanic DPS checks) |
| SABOTEUR | Enemy debuffs, armor shred | D1/D4 |
| BEACON | Pipeline-combo enabler (mark applicator) | D1 |
| WARDEN | Mechanic telegraphs slowed/highlighted | D1 (MECHANIC_FAIL) |

### 4.3 Stat budget formula (deterministic — computed by the worker, not the LLM)

```
budget_total(level) = BASE(120) + 14 × level
cap_per_stat        = 0.40 × budget_total       // no degenerate single-stat agents
stat_i              = round(stat_weights_i × budget_total), then clamp to cap and
                      redistribute remainder by weight order
power_ceiling       : final simulated DPS+EHP score must be ≤ 1.05 × the median
                      catchable agent of the same level (validated in §5) —
                      Foundry rares are *tailored*, never *overpowered*.
```

### 4.4 Ability set

Drawn ONLY from the **vetted GAS component library** (`SynapseAgents` ability registry, see
`03-combat-gas-design.md`): 4 abilities, each tagged with archetype compatibility; the schema
rejects any ability id not allowlisted for the chosen archetype. No live-authored
GameplayEffects, ever. Tier (T1/T2) gated by level bands (T2 requires level ≥ 18).

### 4.5 Personality, name, art

- **Personality card:** 5 bounded axes (warmth, candor, patience, pride, curiosity) ∈ [0,1],
  consumed by the parley/banter systems exactly like roster agents
  (`02-negotiation-system.md`).
- **Name:** generated from a closed grammar per archetype (`G_GUARDIAN`, `G_TRICKSTER`, …) over
  an allowlisted token bank; collision-checked against the roster and profanity-screened.
- **Art:** a **modular part-bank recipe** — skeleton + allowlisted parts + palette + FX accent,
  all pre-authored, pre-rated assets shipped in the game pak. **NO live-generated raw art or 3D,
  no texture synthesis, no live image-gen.** The recipe assembles at runtime in
  `SynapseFoundryClient` from on-disk parts.
- **Barks:** the only free-ish text; ≤ 90 chars, profanity/illegal-content filtered server-side
  (denylist + classifier), and rendered with the player-facing AI indicator (§9).

---

## 5. Validation harness

### 5.1 Harness

A **deterministic combat-sim service**: the GAS-relevant rules of `03-combat-gas-design.md`
re-expressed as a fixed-timestep headless simulation (authoritative implementation choice:
a headless UE build of `SynapseAgents` run under `UnrealEditor-Cmd` in CI to *generate and pin*
golden traces; the hosted service runs a lightweight deterministic re-implementation validated
against those golden traces each release — drift > 2% on any golden metric blocks deploy).
Seeded RNG; identical inputs → identical outputs.

### 5.2 Procedure

1. Reconstruct the player's **actual failure scenarios** from ticket evidence: encounter set,
   party composition, levels, gear/network state (from T1/T2 payloads).
2. Run **N ≥ 400 simulations** total: ≥ 200 baseline (player party as-was) + ≥ 200 candidate
   (party with the Foundry agent substituted/added per the archetype's slot rule), stratified
   across the player's last ≥ 4 distinct failures, randomized seeds.
3. Compute the ticket's `target_metric` (e.g., gauntlet survival rate, parley-adjacent fights
   excluded for D2 — D2 candidates validate on disposition-delta sims instead).
4. **Promote only if:** improvement **≥ 15 percentage points** AND the **95% CI of the
   difference excludes zero** (two-proportion z-interval; Wilson for small cells). Also enforce
   the §4.3 power ceiling and a regression check (no other tracked metric worsens > 5pp).
5. Failures: re-spec (≤ 2 retries with the verdict fed back) → otherwise park the ticket; the
   player simply never hears about it. **A candidate that didn't validate does not ship.**

### 5.3 Verdict card (player-facing format — real-stat phrasing, exact template)

```
┌──────────────────────────────────────────────────────────┐
│  FORGED FOR YOU                              [AI ✦]      │
│  «Bulwark-of-Threads» — Interdictor                       │
│                                                            │
│  In 400 simulations of your last 6 defeats at the          │
│  Security Gauntlet, your party's survival rose             │
│  31% → 64%  (n=400, 95% CI of gain +26…+40pp).             │
│                                                            │
│  Built from: your 4 wipes (Jun 2–8), burst damage          │
│  pattern.  [View the evidence]                             │
└──────────────────────────────────────────────────────────┘
```

Rules: the numbers ARE the simulation outputs — no rounding flourish beyond integer percent;
"View the evidence" opens the ticket's source events; if a stat wasn't measured it does not
appear. The `[AI ✦]` indicator is mandatory (§9).

---

## 6. Delivery

- The validated agent **spawns as a discoverable rare in that player's world**: a unique shimmer
  encounter placed in the zone of the triggering struggle, marked on no quest log — players find
  it or stumble on a soft rumor bark from a Den visitor.
- Recruitment is the normal parley flow (`02-negotiation-system.md`); the agent's personality
  card makes it *predisposed* but not automatic. Fully optional: ignore it for 7 days → T5
  `IGNORED_7D`, it wanders off (despawns), no penalty, no re-nag.
- **One Foundry rare active per act.** A second validated candidate queues until the active one
  resolves (recruited/dismissed/ignored-out) or the act ends.
- Foundry agents wire into the network like any agent but carry the `Foundry` origin tag —
  visible on the card, excluded from the real-muse skill-unlock bridge (master plan §4.5) at
  v1.0.

---

## 7. Server architecture (hosted brain, P3)

```
ingest (HTTPS, bearer) → IP-strip LB → event queue (Redis stream)
   → aggregator worker  → per-player rolling aggregates (Postgres)
   → detector cron (15-min tick) → StruggleTickets
   → foundry worker pool: LLM spec call → schema validate → sim service (N≥400)
       → verdict store → delivery flag picked up by the game on next session sync
```

- **Queue:** single Redis stream, consumer group per worker type; at-least-once with idempotent
  event ids; backlog alarm at 10 min lag.
- **Budget caps** (master plan §7: $1,200 / 12 months hosted budget — Foundry's slice ≤ $40/mo):
  per-player ≤ 3 LLM spec calls/day and ≤ 2 sim batches/day; global daily token ceiling and sim
  CPU-hour ceiling, enforced by the worker before dequeue; over-cap tickets park until tomorrow.
  Spec calls use the cheap model lane; sims are CPU-only.
- **Abuse limits:** ingest rate ≤ 120 events/min per player (drop+flag beyond), payload schema
  validation at the edge, anonymous-id ban list for synthetic-traffic patterns (impossible event
  cadence, replayed session ids).
- **Kill-switch:** a single server flag `foundry.enabled=false` (operator-only) stops detector
  and worker stages instantly; in-flight verdicts ship, nothing new starts. The game treats
  kill-switch identically to offline (§8). A second flag gates LLM spec generation alone
  (falls back to rule-based archetype selection — D-table column 3 maps detector→archetype
  directly).

---

## 8. Offline behavior

Tier 1 (local GGUF only) and any network-loss state: the Foundry is **silently absent**. No
telemetry buffered for later (consented events are fire-and-forget; offline = not collected), no
locked UI stubs, no "connect to unlock" nags, no dead menu entries. The game is complete without
it, per the standalone-game test (master plan §4.8). If a delivered-but-unfound rare exists when
the player goes offline, it remains in the save (delivery already happened; the agent is local
data from that point).

---

## 9. Steam AI compliance mapping (per master plan §8.4)

| Guardrail (this spec) | Disclosure line it supports |
|---|---|
| Template-constrained CandidateSpec; closed archetype/ability/part libraries (§4) | "…guardrails: template-constrained outputs, allowlisted ability/art components…" |
| No live-gen raw art/3D — part-bank recipes only (§4.5) | "…(no live-gen art assets)…" |
| Server-side profanity/illegal filters on names + barks (§4.5) | "…profanity/illegal-content filters…" |
| `[AI ✦]` indicator on verdict card and Foundry-agent dialogue (§5.3) | "…player-facing AI indicator…" |
| Overlay report path: every Foundry text surface carries a report affordance routed to Steam's in-overlay reporting; reports flag the candidate server-side for human review | "…support for Steam's in-overlay reporting." |
| Free-text parley input never leaves device (§2.3) | The negotiation-dialogue disclosure ("generated at runtime by a bundled local language model") stays truthful: player words are not service inputs |
| Validation receipts on every card (§5.3) | The brand stance: "we wear the label proudly — transparency is the brand" |

---

## 10. Failure modes & rollback

| Failure | Detection | Response |
|---|---|---|
| LLM spec invalid 3× | Schema validator | Park ticket; rule-based fallback archetype if flag set; never ships unvalidated |
| Sim service drift vs golden traces > 2% | Release CI gate | Block deploy; Foundry keeps running prior build |
| Candidate validates but underperforms live (player still wiping with it after 5 attempts) | D1 re-fires with Foundry agent in party | Ticket annotated `FOUNDRY_MISS`; next candidate must beat the *new* baseline including the miss; miss rate > 20% global → auto-disable LLM lane, alert operator |
| Budget cap breach trend | Daily spend report | Caps lower automatically (halve per-player quotas) before the hard ceiling |
| Offensive name/bark escapes filters | Steam overlay report / support | Hotfix: server pushes a rename+bark-swap patch for that candidate id on next sync (recipe re-roll, agent stats untouched); token added to denylist |
| Telemetry consent revoked mid-pipeline | Consent flag check at every stage boundary | Pipeline aborts for that player; purge per §2.4 |
| Full rollback | Operator | Kill-switch (§7) + client config flag; delivered agents remain playable forever (they are local save data and require no service) |

The last row is the design's deepest safety property: **a recruited Foundry agent never depends
on the service again.** Sunset of the hosted brain degrades the Foundry to "no new rares,"
never to "your agent broke."

---

## 11. Cross-references

- `01-game-design-document.md` — consent UI, options, act structure, suppression beats.
- `02-negotiation-system.md` — parley verdict enum, recruitment flow, LLM-never-mutates-stats.
- `03-combat-gas-design.md` — ability registry, attributes, combat rules the sim re-expresses.
- `10-observatory-spec.md` — the same honesty machinery (measured-only claims) applied to muse
- `11-technical-design.md` — `SynapseFoundryClient`, save schema for Foundry rares, consent gate.
- Master plan §4.7, §7 (budget), §8.4 (compliance), §11 (risk register rows 5–6).
