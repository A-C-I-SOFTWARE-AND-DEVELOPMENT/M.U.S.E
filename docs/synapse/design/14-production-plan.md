# 14 — SYNAPSE Production Plan (Sprints 1–40)

**Project:** SYNAPSE — A M.U.S.E. Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

This document executes master plan §6 (phases & gates), §7 (budget), §10 (P1 parallel lane), and §11 (risk register). It does not re-litigate them. The project clock starts **Monday 2026-06-15 (Week 1)**. Sprints are two weeks, Monday→Friday. Target launch **2027-10-26** (Sprint 36, month 17 — inside the locked 16–20 month window), with contractual slip room to **2028-02-22** absorbed by Sprints 37–40 and the scope ladder in §8 of this doc. A producer handed this document cold should be able to run the project.

---

## 1. Team model

One owner, one AI engineering staff, four contractor slots. Nobody else. Headcount growth is a scope change and goes through change control (§9).

| Seat | Who | Responsibilities | Cannot do |
|---|---|---|---|
| **Director / Producer / Artist-in-training** | Jeremiah Echerd (full-time) | All creative decisions; UE editor work (levels, lighting, Blueprint visual wiring, art curation); playtest direction; all owner-gated approvals; contractor management; marketing voice | Delegate GO/NO-GO authority |
| **Engineering staff** | Claude Code (AI) | All C++ (modules per master plan §5: SynapseCore/Net/Agents/Observatory/FoundryClient/UI); GAS ability implementation; save system; gateway client; CI; test authoring per 15-qa-test-plan.md. **Compile-loop validation is mandatory:** every task ends with pasted UBT build output + runtime log evidence — no output, no done (master plan §13 contract) | Merge to main without owner review; touch the editor; make scope decisions |
| **Contractor slot A — Capsule/key-art illustrator** | TBD, contracted Sprint 13 | Capsule suite + key art per the brief in 16-steam-marketing-launch-plan.md §4 | — |
| **Contractor slot B — Hero creature artist(s)** | TBD, contracted Sprint 3 | 3 commissioned heroes: **EMPATH** (Behavior — starter, needed first), **WARDEN** (Security), **ORACLE** (Research). Model + rig on the shared skeleton + anim set, per 04-roster-24-agents.md specs | Deviate from shared-skeleton rig spec |
| **Contractor slot C — Composer** | TBD, contracted Sprint 17 | Mini-score: main theme, 5 zone beds, parley tension layer, Gauntlet/boss, Council finale | — |
| **Contractor slot D — SFX + light VO** | TBD, contracted Sprint 19 | SFX library pass + negotiation barks (parley scenes carry the game — master plan §7) | — |

### 1.1 Budget — the $10k mapped to slots and sprints (live tracking template)

Lines are master plan §7, verbatim. The owner updates this table **every sprint review**; "Committed" = contract signed, "Spent" = invoice paid. Any line trending >10% over moves money out of Contingency first, then triggers change control.

| Budget line | Allocated | Committed | Spent | Remaining | Owning sprint(s) | Status note |
|---|---|---|---|---|---|---|
| Capsule + key art (pro illustrator) | $1,200 | — | — | $1,200 | S13–S15 (delivery before page-live S15) | |
| 3 hero creature commissions (model+rig+anims) | $3,600 | — | — | $3,600 | S3 contract; EMPATH by S6, WARDEN by S12, ORACLE by S16 | |
| Fab asset packs (env/VFX/UI/anim) | $1,000 | — | — | $1,000 | S1–S20 rolling; ≥$400 held until Phase 4 | |
| Music license / composer mini-score | $800 | — | — | $800 | S17 contract; final masters by S30 | |
| SFX + light VO (negotiation barks) | $500 | — | — | $500 | S19 contract; final by S31 | |
| Tools (Rive, audio, misc subs) | $300 | — | — | $300 | Rolling | |
| Steam Direct fee | $100 | — | — | $100 | S13 (page setup begins) | |
| Hosted brain: 12 mo small GPU/API budget | $1,200 | — | — | $1,200 | S9 onward, $100/mo cap | |
| Trailer edit + festival/marketing | $700 | — | — | $700 | S15 (announce trailer), S33 (launch trailer) | |
| Contingency | $600 | — | — | $600 | Held; first call: §8.5 IP consult (~$300) | |
| **Total** | **$10,000** | | | | | |

**Rules:** no line may borrow from another without a ledger note here; contingency draws are owner-approved in writing; if contingency hits $0 before Sprint 30, invoke the scope ladder (§8) before spending more.

---

## 2. Methodology

### 2.1 Sprint mechanics
- **Two-week sprints**, Monday start. Sprint planning Monday AM (90 min, owner + Claude Code session); sprint review + budget-table update final Friday PM; retro notes (≤10 bullets) appended to the sprint log.
- **One sprint goal sentence** per sprint (the table in §4 is the source). If a task doesn't serve the sentence, it waits.
- Work tracked as a flat checklist per sprint in the SYNAPSE repo (`docs/sprints/S<NN>.md`). No heavyweight tooling.

### 2.2 Phase gates = master plan §6, with evidence exits
Every phase exits through GO/NO-GO with evidence (the house rule). Gates appear as rows in §4. The evidence artifact is named in advance; **no artifact, no exit**. Gate verdicts and artifacts are recorded in `docs/sprints/gates.md`.

| Gate | End of | Evidence exit (verbatim from §6, operationalized) |
|---|---|---|
| **G0 Foundation** | Week 3 (mid-S2) | Empty packaged Win64 build runs; PIE log showing `/health` + `/v1/cockpit/capabilities` over bearer auth; trademark search report filed; GPL re-audit ticket open |
| **G1 The Moment** | S4 | Video: negotiate one wild agent into joining via live local-LLM dialogue, then win one paused-command fight |
| **G2 Vertical Slice (go/no-go, week 16)** | S8 | 20-min Stacks slice; 5 external playtesters; median "would wishlist" ≥ 4/5; 60fps on the Legion (perf capture attached). **NO-GO here = project pivot review, not a slip** |
| **G3 Observatory** | S13 | One real recommendation card from ≥100 replayed tasks, applied via owner phrase, rolled back cleanly — ledger screenshots |
| **GP1 Platform v1.0** | S10 | §10 DoD complete (see §5 lane); claims table all SUPPORTED; installers smoke-tested with output |
| **G4 Content Complete** | S20 | Full campaign playable start→finish by an outsider without dev help (recorded session) |
| **G5 Demo/Fest** | S26 | Demo live; Next Fest entered with ≥2,000 wishlists; median demo session ≥25 min (telemetry) |
| **G6 Launch readiness** | S35 | 17-launch-readiness-checklist.md fully green; owner GO with the exact authorization phrase |

### 2.3 Definition of Done, per discipline

| Discipline | DONE means |
|---|---|
| **C++ / engineering** | Compiles clean via UBT command line, warnings-as-errors for our modules; unit/functional tests added per 15-qa-test-plan.md; runtime evidence pasted; reviewed by owner; merged |
| **GAS ability** | Spec test green (cost, cooldown, tags, expected attribute deltas); fires correctly in the test arena map; VFX/SFX hooks stubbed or final; balance row entered in the tuning sheet |
| **Agent (content)** | All 7 pipeline stages in §6.1 passed, including negotiation test and combat balance pass; personality card reviewed against 04-roster-24-agents.md |
| **Zone (content)** | All 5 pipeline stages in §6.2 passed; perf capture within budget on all three reference rigs; encounter table populated per 05-world-design.md |
| **Level/lighting (owner art)** | Matches the art bible key for the zone; Lumen settings recorded; screenshot pair (target vs. actual) filed |
| **UI screen** | Implements 12-ui-ux-spec.md; gamepad + KBM + UI-scale 80–140% verified; colorblind glyph rule honored |
| **Narrative/dialogue** | In the string table (localization-ready); speaker-labeled subtitles work; reviewed against 06-narrative-campaign.md |
| **Marketing asset** | Approved by owner against 16-steam-marketing-launch-plan.md; filed in the press-kit folder |

---

## 3. Calendar anchors

| Anchor | Date | Sprint |
|---|---|---|
| Week 1 / kickoff | 2026-06-15 | S1 |
| The Moment video (G1) | 2026-08-07 | S4 |
| Vertical-slice go/no-go (G2, week 16) | 2026-10-02 | S8 |
| P1 MUSE Platform v1.0 (GP1, week 20) | 2026-10-30 | S10 |
| Steam page live (week 30 at the latest) | by 2027-01-08 | S15 |
| Content complete (G4, week 40) | 2027-03-19 | S20 |
| Demo live | 2027-04-30 | S23 |
| Steam Next Fest (June 2027 — the last before launch) | 2027-06-14 → 06-21 | S27 |
| Release candidate | 2027-10-01 | S34 |
| **LAUNCH** | **2027-10-26 (Tue), 10:00 PT** | S36 |
| Slip ceiling | 2028-02-22 | beyond S40 — forbidden |

Holiday note: S14 (2026-12-14→12-25) and the S15 opening week run at **half velocity** by plan, not by surprise.

---

## 4. The sprint plan — Sprints 1–40

Goals are sprint-goal sentences; deliverables are the evidence. "Lane P1" items appear in §5. Agent batch and zone cadence detail in §6.3/§6.4.

| # | Dates (2026–27) | Phase | Goal | Key deliverables | Gate |
|---|---|---|---|---|---|
| **S1** | 06-15 → 06-26 | 0 | Stand up the studio | VS2022 + UE 5.6 pinned; SYNAPSE repo + LFS + CI (Win64 Dev build); first-7-days list (§12) done; trademark search + IP consult booked; GPL re-audit ticket; local-LLM Fab plugin streaming a reply in PIE; Prompt 0 run → SynapseCore/SynapseNet scaffolded | |
| **S2** | 06-29 → 07-10 | 0→1 | Prove the wire, start the spine | Gateway client w/ bearer auth + SSE; empty packaged build runs; GAS skeleton (attributes Integrity/Bandwidth, tags); GAS+Lumen course sprint done; Megascans test room lit (becomes The Stacks' first corner) | **G0** (wk 3) |
| **S3** | 07-13 → 07-24 | 1 | One gray-box agent that fights | 1 gray-box agent w/ 4 abilities; RTwP pause loop (Command Mode v0); hero-commission contract signed (slot B); shared-skeleton rig spec frozen | |
| **S4** | 07-27 → 08-07 | 1 | The Moment | Local-LLM parley v0 (free text, closed verdict enum per 02); wheel fallback v0; negotiate → join → paused fight, on video | **G1** |
| **S5** | 08-10 → 08-21 | 2 | Stacks blockout + agents 1–2 | The Stacks blockout (§6.2 stage 1); agents AXIOM + CONTRARIAN through full pipeline (§6.1 proving run); onboarding/Muse-creator v0 | |
| **S6** | 08-24 → 09-04 | 2 | Light the Stacks, land EMPATH | Stacks Megascans dress + lighting key; EMPATH commission delivered + integrated (starter trio complete); network screen v1 (wire/synergy preview) | |
| **S7** | 09-07 → 09-18 | 2 | The Test Gauntlet | Test Gauntlet boss (UE Functional Test per 15-qa §3); agents 4–5; Den v1; encounter fill of slice area; save system v1 (autosave rules per 01 §8) | |
| **S8** | 09-21 → 10-02 | 2 | Slice polish + external eyes | 20-min slice content-locked; 5-tester external playtest per 15-qa §5.1; perf capture 60fps on Legion; fix pass | **G2 go/no-go** |
| **S9** | 10-05 → 10-16 | 3∥4 | Production engine on | Phase 4 kickoff: Foundry zone blockout; agent pipeline re-proof at production cadence (agents 6–7); **Lane O:** `/v1/observatory/*` routes + metrics collector PR (contract regenerated + frozen) | |
| **S10** | 10-19 → 10-30 | 3∥4 | Foundry dress + 2 agents | Foundry zone Megascans dress; agents 8–9; **Lane O:** UE Observatory map v0 (graph LOD clusters render); **Lane P1 closes** | **GP1** |
| **S11** | 11-02 → 11-13 | 3∥4 | Foundry done | Foundry lighting key + encounter fill + polish; Build Gauntlet; agents 10–11; **Lane O:** SSE deltas live (pipeline packets) | |
| **S12** | 11-16 → 11-27 | 3∥4 | Gardens begin; WARDEN lands | Gardens of Memory blockout; WARDEN commission integrated; agents 12–13; Rollback Gauntlet; **Lane O:** recommendation engine v1 (replay harness) | |
| **S13** | 11-30 → 12-11 | 3∥4 | Observatory proof | Gardens dress; agents 14–15; **Lane O gate:** rec card from ≥100 replayed tasks, applied via owner phrase, rolled back — ledger screenshots; capsule illustrator contracted (slot A) + Steam Direct fee paid | **G3** |
| **S14** | 12-14 → 12-25 | 4 | Half-velocity holiday sprint | Gardens lighting key; agents 16–17 *(stretch — may slip to S15 without penalty)*; Review Gauntlet design lock | |
| **S15** | 12-28 → 01-08 | 4∥5 | **Steam page live (week 30)** | Store page live: capsule suite, short+long description, tags, AI disclosure — all final per 16 §4–§6; announce trailer (60–90s) cut from slice+Foundry footage; Discord opens; devlog #1; agents 16–17 if slipped | Page-live |
| **S16** | 01-11 → 01-22 | 4∥5 | Gardens done; ORACLE lands | Gardens encounter fill + polish; Review Gauntlet built; ORACLE integrated; agents 18–19; devlog #2 | |
| **S17** | 01-25 → 02-05 | 4∥5 | The Vault begins | Vault blockout + dress start; agents 20–21; composer contracted (slot C); devlog #3 | |
| **S18** | 02-08 → 02-19 | 4∥5 | Vault rises; roster complete | Vault dress + lighting key; Security Gauntlet; agents 22–23 + **agent 24** (roster 24/24); devlog #4 | |
| **S19** | 02-22 → 03-05 | 4∥5 | Vault done; Foundry service v1 | Vault encounter fill + polish; Owner Approval Gauntlet; foundry server v1 (observe→hypothesize→build→validate→ship per §4.7, hosted-tier caps on); SFX/VO contracted (slot D); devlog #5 | |
| **S20** | 03-08 → 03-19 | 4∥5 | Gate Spire + content complete | Gate Spire (all 5 stages — endgame zone, smaller but denser); Release Gauntlet; Council finale; options/accessibility complete per 01 §9–10; **outsider full-campaign run recorded** | **G4** |
| **S21** | 03-22 → 04-02 | 5 | Full-campaign hardening | Fix pass from outsider run; balance pass across domain ring; 10-tester full-campaign cohort recruited (15-qa §5.2); devlog #6 | |
| **S22** | 04-05 → 04-16 | 5 | Demo build cut | Demo = The Stacks 45-min slice, separate appid/depot, telemetry wired (16 §7); demo QA per 15-qa; devlog #7 | |
| **S23** | 04-19 → 04-30 | 5 | **Demo live** + wishlist checkpoint | Demo published to the page; 10-tester cohort wave 1 running; **week-45 wishlist decision-tree review (16 §12)**; devlog #8 | Demo-live |
| **S24** | 05-03 → 05-14 | 5 | Creature Collector Fest readiness | Fest build + page refresh; clip kit (30-sec parleys) for creators; cohort wave 1 fixes; devlog #9 | |
| **S25** | 05-17 → 05-28 | 5 | Festival #1 window | Creature Collector Fest (or backup per 16 §8 if dates miss); react to demo telemetry; devlog #10 | |
| **S26** | 05-31 → 06-11 | 5 | Next Fest entry gate | Next Fest build locked; **≥2,000 wishlists verified** (target 5,000); press-kit v1; devlog #11 | **G5** |
| **S27** | 06-14 → 06-25 | 5 | **Steam Next Fest (June 2027)** | Fest live ops: daily stream slots, telemetry watch (median session ≥25 min), wishlist surge capture; devlog #12 | |
| **S28** | 06-28 → 07-09 | 5 | Post-fest conversion | Fest retro; demo fixes; cohort wave 2; localization scope locked + strings exported (15-qa §11); devlog #13 | |
| **S29** | 07-12 → 07-23 | 6 | Beta 1 | Full-game beta build; full compatibility matrix pass 1 (15-qa §6); save-torture suite green; music final masters in | |
| **S30** | 07-26 → 08-06 | 6 | Steam Deck + min-spec | Steam Deck verification pass work; GTX 1660 30fps lock; SFX/VO final in; devlog #14 | |
| **S31** | 08-09 → 08-20 | 6 | Beta 2 + safety red-team | Negotiation safety red-team set green (15-qa §9); Foundry verdict-card honesty audit; localization QA pass 1; devlog #15 | |
| **S32** | 08-23 → 09-03 | 6 | Platform compliance | Steam build review submitted; achievements, cloud saves, controller cert; store assets final; age ratings filed; devlog #16 | |
| **S33** | 09-06 → 09-17 | 6 | Launch trailer + press | Launch trailer cut (beats per 16 §5.2); **press/creator kit ships (T-6 weeks: 09-14)**, embargo set; devlog #17 | |
| **S34** | 09-20 → 10-01 | 6 | Release candidate | RC build; RC criteria per 15-qa §12 (zero blocker/critical, ≤5 majors w/ workarounds, crash-free ≥99.5%, all 8 Gauntlet functional tests green, contract-pin green); final playtest cohort on RC | RC |
| **S35** | 10-04 → 10-15 | 6 | Launch readiness | 17-launch-readiness-checklist.md walked top to bottom with evidence; day-0 patch candidate staged; creator embargo previews out; GO/NO-GO ceremony | **G6** |
| **S36** | 10-18 → 10-29 | 6 | **LAUNCH 2027-10-26** | Launch week runbook executed (16 §13); 10% launch discount; review-response protocol on; crash dashboard watch | Launch |
| **S37** | 11-01 → 11-12 | post | Stabilize | Patch 1 (top crashes/majors); review themes triaged; wishlist-to-sale conversion report | |
| **S38** | 11-15 → 11-26 | post | Patch cadence | Patch 2; first free-content beat scoped (16 §14); community event #1 | |
| **S39** | 11-29 → 12-10 | post | First content beat | Free content beat live; Android-tier announce per 16 §14 timing rules | |
| **S40** | 12-13 → 12-24 | post | Close the year | Patch 3; 90-day plan mid-review; Phase 7 (Android tier) production plan drafted as a future `18-android-tier-plan` proposal (post-launch document, intentionally outside this v1.0 package) | |

**Slip mechanics:** if any gate slips, downstream anchors slide sprint-for-sprint, the scope ladder (§8) is consulted at +2 sprints of cumulative slip, and the launch date may move only at gate reviews — never mid-sprint. Absolute ceiling 2028-02-22.

---

## 5. Lane P1 — MUSE Platform v1.0 (parallel, weeks 4–20 = S2–S10)

Runs alongside Phases 1–3 per master plan §10. Budget: ~20% of owner time + dedicated Claude Code sessions; never allowed to block a game gate (if contention, the game gate wins and P1 slips inside its lane). Definition of done = §10.1–10.3, expressed as sprint rows:

| Lane sprint | Dates | P1 goal | Deliverables (evidence) |
|---|---|---|---|
| P1-a (S2) | 06-29 → 07-10 | Resolve the held chain — plan | R00 decision matrix re-confirmed; #131 rebased; merge order locked; owner authorizations scheduled per gate |
| P1-b (S3) | 07-13 → 07-24 | Land the first half | #131, #142 landed (owner-authorized each); CI green after each |
| P1-c (S4) | 07-27 → 08-07 | Land the chain | #143, #147 landed; image-gen provider wired (room editor unblocked — also feeds P3) |
| P1-d (S5) | 08-10 → 08-21 | Close the chain | #149, #150 rebased + landed; voice engine concretes bound |
| P1-e (S6) | 08-24 → 09-04 | Default-on gateway | Live gateway default-on after pairing; full test suite green |
| P1-f (S7) | 09-07 → 09-18 | Everything-functional audit | `aos-audit-validator` run vs README claims table; every UNSUPPORTED/PARTIAL → ticket |
| P1-g (S8) | 09-21 → 10-02 | Burn the audit list | Ticket burn-down ≥80%; `install.ps1` hardened; Linux/WSL/macOS installer + Homebrew working |
| P1-h (S9) | 10-05 → 10-16 | Package everything | Termux path, Docker compose, release-signed APK, Tauri bundle — each with model bootstrap, first-run pairing, and a smoke test that proves the install **with output** |
| P1-i (S10) | 10-19 → 10-30 | **v1.0** | Claims table all SUPPORTED; docs current; v1.0 tagged. **Gate GP1** evidence: audit report + installer smoke logs |

---

## 6. Content pipelines

### 6.1 Agent asset pipeline (per agent, locked stage order)

| Stage | Work | Owner | Est. hours |
|---|---|---|---|
| 1. Base mesh | Curate Fab base / part-bank assembly (commissioned for the 3 heroes) | Owner (art) | 8 |
| 2. Domain overlay | Material/silhouette pass to read as its domain glyph at 10m | Owner (art) | 10 |
| 3. Rig on shared skeleton | Retarget to the shared skeleton; verify anim set | Owner + Claude Code (tooling) | 6 |
| 4. 6–10 GAS abilities | Implement from the vetted component library; spec tests | Claude Code | 14 |
| 5. Personality card | Negotiation profile, banter set, parley openers per 02/04 | Owner (design) | 4 |
| 6. Negotiation test | Golden-prompt run + wheel-parity check (15-qa §4.6) | Claude Code + owner review | 4 |
| 7. Combat balance pass | Tuning-sheet entry; domain-ring matchup sims | Owner + Claude Code | 6 |
| | **Total per agent** | | **~52 h gross; ~30–34 owner-hours** after Claude Code leverage |

**Cadence: 2 agents per sprint** is sustainable only because stages 3–4 and 6 are mostly Claude Code throughput. The S9 re-proof run (agents 6–7) must hit ≤55h each or the cadence is re-planned **before** Phase 4 commits to it.

### 6.2 Zone pipeline (per zone)

| Stage | Work | Duration |
|---|---|---|
| 1. Blockout | Graybox layout, traversal metrics, encounter spaces, vista framing | 1 wk |
| 2. Megascans dress | Fab/Megascans set dress to art-bible key | 2 wk |
| 3. Lighting key | Lumen key light, zone mood per art bible; perf capture checkpoint | 1 wk |
| 4. Encounter fill | Spawn tables, lures, Gauntlet placement, story beats per 05/06 | 1.5 wk |
| 5. Polish | Audio pass, collision/nav audit, perf to budget on all 3 rigs | 0.5 wk |
| | **Total** | **6 wk/zone = 3 sprints**, overlapped (next zone's blockout starts during current zone's encounter fill) |

### 6.3 Zone schedule (Phase 4)

| Zone | Sprints | Notes |
|---|---|---|
| The Stacks | S5–S8 (slice) + S21 polish revisit | Slice zone; expanded to full size in S21 fix pass |
| The Foundry | S9–S11 | Gauntlets: Build, Rollback |
| Gardens of Memory | S12–S14 (+S15 holiday spill) | Gauntlet: Review |
| The Vault | S15–S17 (start) → S19 | Gauntlets: Security, Owner Approval |
| The Gate Spire | S18–S20 | Gauntlet: Release + Council finale; smaller, denser, no spill allowed |

Gauntlet→zone assignment is binding for production scheduling; The Stacks carries Planning + Test.

### 6.4 Agent batch schedule (24 total)

| Batch | Agents | Sprint |
|---|---|---|
| Slice five | AXIOM, CONTRARIAN, EMPATH (starters) + 2 Stacks wilds | S5–S7 |
| Pipeline re-proof | 6–7 | S9 |
| Production batches | 8–9 / 10–11 / 12–13 / 14–15 / 16–17 / 18–19 / 20–21 / 22–23 | S10–S17 (2/sprint; S14 batch may slip to S15) |
| Final + balance | 24 + roster-wide balance pass | S18 |
| Commissioned heroes | EMPATH S6 · WARDEN S12 · ORACLE S16 | contractor deliveries, integrated same sprint |

---

## 7. Dependency map (what blocks what)

```
G0 wire-proof ──► SynapseNet ──► Observatory map (S10) ──► G3
Local-LLM plugin (S1) ──► Parley v0 (S4/G1) ──► all negotiation content; wheel fallback parallel
Shared-skeleton rig spec (S3) ──► ALL agent stage-3 work + hero commissions (blocker if late)
GAS skeleton (S2) ──► gray-box agent (S3) ──► ability component library ──► stage-4 of every agent
Slice (G2) ──► production cadence commit (S9) ──► zone/agent schedule
P1-c image-gen (S4) ──► Den room editor final ──► Den content lock (S20)
P1 v1.0 (S10) ──► BYO-pairing tier certification (15-qa §6) ──► brain-tier matrix in 17
/v1/observatory routes (S9) ──► contract regen+freeze ──► UE Observatory ──► G3 rec card
Foundry server v1 (S19) ──► Foundry validation harness tests (15-qa §10) ──► AI-compliance section of 17
Content complete (G4) ──► demo cut (S22) ──► Next Fest (S27) ──► wishlist curve ──► launch GO
Capsule art (S13–15) ──► page live (S15) ──► the entire wishlist clock
Trademark search (S1) ──► page live naming; GPL re-audit (S1) ──► any commercial distribution
```

**Critical path:** S1 plugin+repo → G1 → G2 → production cadence → G4 → demo → Next Fest → RC → launch. The two most fragile links: shared-skeleton spec (S3) and capsule delivery (S15). Both get weekly status checks from contract signing.

---

## 8. Risk-managed scope ladder (pre-agreed cut order)

Invoked only at gate reviews, in order, one rung at a time. **Never cut, at any rung: the negotiation system (LLM + wheel), the 8 Gauntlets, the 5-zone fiction (zones may merge spatially, not narratively), single-player completeness, or any accessibility commitment in 01 §9.**

| Rung | Cut | Saves | Trigger |
|---|---|---|---|
| 1 | Side content: optional sub-region quests, Den trophy cosmetics, post-game superboss | ~2 sprints | +2 sprints cumulative slip at any gate |
| 2 | Reduce per-zone encounter variety (spawn tables share more agents across zones) | ~1 sprint | +3 sprints |
| 3 | **One zone merges:** Gardens of Memory folds into The Stacks as a major sub-region (its Review Gauntlet and story beats survive intact) | ~3 sprints | +4 sprints, or G4 forecast misses S22 |
| 4 | **Agent count floor 18** (cut 6 non-hero, non-starter agents; domain coverage of all 8 preserved) | ~3 sprints | +6 sprints — last rung before moving launch |
| 5 | Move launch within the window, then toward the 2028-02-22 ceiling | — | Rungs 1–4 exhausted |

---

## 9. Change control & cadence rituals

**Change control:** any change to locked numbers (5 zones / 24 agents / 8 Gauntlets / $24.99 / single-player / dates by more than one sprint) requires a written one-pager, a gate-review slot, and the owner's explicit decision recorded in `docs/sprints/gates.md`. New ideas go to the post-launch list — master plan §11, verbatim.

**Cadence rituals (binding):**

| Ritual | Cadence | From |
|---|---|---|
| CI build (Win64 Dev) | every merge | S1 |
| Nightly cook + smoke (15-qa §3.4) | nightly | S5 |
| **Weekly build** (packaged, archived, playable) | every Friday | S2 |
| **Fortnightly playable** (sprint review = play the build, not slides) | sprint review | S2 |
| **Monthly outsider playtest** (1+ person who has never seen the game) | monthly | S8 (Phase 2 onward) |
| Budget table update (§1.1) | sprint review | S1 |
| Wishlist tracking ritual (16 §12) | weekly, Mondays | S15 |
| Perf capture on 3 reference rigs | per zone-stage-3 + monthly | S6 |
| Backup audit (LFS + saves + project archive offsite) | monthly | S1 |

**Burnout guards (master plan §11):** phase gates are rest gates — the weekend after every gate is mandatory off; the demo at S23 is the planned morale injection; the P1 lane provides task variety through S10. If two consecutive retros flag overload, invoke the scope ladder review early.

---

*This plan executes the master plan; it does not amend it. Where this document and the master plan disagree, the master plan wins and this document gets a versioned errata.*
