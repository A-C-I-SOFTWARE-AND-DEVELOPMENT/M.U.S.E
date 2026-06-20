# 15 — SYNAPSE QA & Test Plan

**Project:** SYNAPSE — A muse Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

QA for SYNAPSE applies the house rule to the game itself: **no evidence, no claim.** A feature is not done until a test proves it; a build is not shippable until the gates in §12 are green with artifacts. Test code is written by Claude Code under the compile-loop contract; playtests are directed by the owner. Schedule references are to sprints in 14-production-plan.md §4.

---

## 1. Test strategy pyramid

From widest/cheapest to narrowest/most expensive. Lower layers run constantly; upper layers run on cadence.

| Layer | What | Runner | Cadence |
|---|---|---|---|
| L1 — C++ unit tests | Pure-logic tests via UE Automation Framework (`IMPLEMENT_SIMPLE_AUTOMATION_TEST`): save serialization, economy math, domain-ring resolution, network-graph topology ops, verdict parsing, SSE frame parsing | UBT + `UnrealEditor-Cmd -ExecCmds="Automation RunTests"` | Every merge (CI) |
| L2 — GAS ability spec tests | Per-ability contract tests: cost, cooldown, tag grants/blocks, attribute deltas, Pipeline combo chaining (per 03-combat-gas-design.md) | Automation Framework, headless test world | Every merge touching abilities; full suite nightly |
| L3 — Functional tests | UE Functional Tests in dedicated test maps: each Gauntlet boss (mandate: **one functional test per Gauntlet, all 8 green = release gate**), parley flow, wiring commit, save/load round-trip, Den placement | `UnrealEditor-Cmd` automation on test maps | Nightly |
| L4 — Cook + smoke | Full content cook, packaged Win64 boot, main-menu→new-game→first-parley→save→quit script | CI nightly job | Nightly from S5 |
| L5 — Perf capture suite | Scripted flythrough per zone + worst-case combat scene; frame-time CSV per reference rig | `-ExecCmds` capture script; manual on physical rigs | Per zone stage-3 + monthly + every beta/RC |
| L6 — LLM-layer tests | §4 below | Python harness against the bundled GGUF + the parley pipeline | Nightly from S4 |
| L7 — Human playtests | §5 below | Owner-directed, external testers | Monthly from S8 + program waves |

**Rule of the pyramid:** a bug found at L7 gets a regression test added at the lowest layer that could have caught it.

---

## 2. Engineering test suites (L1–L2 detail)

| Suite | Coverage floor | Notes |
|---|---|---|
| `Synapse.Core.Save` | All save-struct versions ever shipped | Round-trip + migration matrix (see §8) |
| `Synapse.Core.Economy` | Cycles/Synapse Thread/Checksum Shards sinks & faucets | Property tests: no negative balances, caps honored (01 §7) |
| `Synapse.Core.DomainRing` | All 64 attacker×defender domain pairs | Single ring, no off-ring exceptions (01 §7 binding) |
| `Synapse.Net.Contract` | **Contract-pin test:** UE client built against pinned wire-contract version; CI fails on drift | Mirrors `test_cockpit_contract_freeze.py` from the gateway side (master plan §5) |
| `Synapse.Net.SSE` | Frame parsing, reconnect, auth-expiry, off-game-thread guarantee | No network on game thread — asserted in test |
| `Synapse.Agents.Abilities` | Every shipped ability (6–10 × 24 agents ≈ 150–240 specs) | Generated scaffold per ability at pipeline stage 4 (14 §6.1) |
| `Synapse.Agents.Pipelines` | Every authored cross-agent combo (mark→exploit→detonate chains) | Chain timing windows + tag requirements |
| `Synapse.Network.Graph` | Wiring legality, synergy adjacency math, promotion thresholds (07) | Screenshot-legibility is L7; topology math is here |

---

## 3. Gauntlet functional test mandate (L3)

Each of the 8 Gauntlets ships with a functional test that drives a scripted party through every boss phase and asserts: phase transitions fire, the taught mechanic is required (the test fails the fight without it, passes with it), rewards grant exactly once, autosave-on-phase-transition writes a loadable save.

| Gauntlet | Test map | Built (sprint) | Test green required by |
|---|---|---|---|
| Test (The Stacks) | `FT_Gauntlet_Test` | S7 | G2 |
| Planning (The Stacks) | `FT_Gauntlet_Planning` | S21 | G4 retro-fit; RC |
| Build (The Foundry) | `FT_Gauntlet_Build` | S11 | RC |
| Rollback (The Foundry) | `FT_Gauntlet_Rollback` | S12 | RC |
| Review (Gardens of Memory) | `FT_Gauntlet_Review` | S16 | RC |
| Security (The Vault) | `FT_Gauntlet_Security` | S18 | RC |
| Owner Approval (The Vault) | `FT_Gauntlet_OwnerApproval` | S19 | RC |
| Release (The Gate Spire) | `FT_Gauntlet_Release` | S20 | RC |

All 8 green is an explicit RC criterion (§12) and a checklist line in 17-launch-readiness-checklist.md.

---

## 4. LLM-layer test plan (L6)

The negotiation system (02-negotiation-system.md) is the differentiator and the highest-novelty risk. It is tested like a compiler, not like a chatbot.

### 4.1 Golden-prompt regression set
A versioned corpus of **≥400 parley transcripts** (grown from S4 onward; ≥1 per agent personality × temperament × difficulty, plus adversarial entries). Nightly, the harness replays each prompt set against the bundled model and asserts the output maps into the **closed verdict enum** defined in 02 — every model utterance must parse to exactly one verdict state; free text that fails to parse is itself a test failure (the runtime falls back to the wheel, and the corpus gains a case).

### 4.2 Closed-enum conformance
Property test: 10,000 sampled generations across personalities → 100% parse rate into the verdict enum; zero out-of-enum mechanical effects. The LLM may color the words; it may never invent a mechanic.

### 4.3 Fallback-wheel parity
For every negotiation node, the 4-option choice wheel must offer **mechanically identical outcomes** to the free-text path (01 §9 accessibility commitment, canon). Test: drive both paths through the same scripted parley with the same seed → assert identical verdict sequences, identical join probabilities, identical resource costs. Runs per-agent at pipeline stage 6 (14 §6.1) and full-roster nightly.

### 4.4 Offline-mode certification
Network-disabled test pass: full game start→Council finale with zero network (LLM tier 1 only). Asserts: no feature degrades below wheel-parity, no hang on any hosted-tier call (all must timeout→fallback ≤2s), no telemetry writes queued unbounded. Run at every beta and RC; certified result is a 17-checklist line.

### 4.5 Latency budget
First parley token ≤1.5s on min-spec (GTX 1660 rig, CPU inference); full reply ≤8s or the UI offers the wheel. Measured in the perf suite.

### 4.6 Per-agent gate
No agent exits pipeline stage 6 without: 10 golden transcripts recorded, enum conformance pass, wheel parity pass, safety screen (§9) pass.

---

## 5. Playtest program (L7)

### 5.1 Phase 2 — vertical slice external test (G2 evidence)
- **Cohort:** 5 external testers, zero project exposure; recruited from creature-collector communities (not friends-who-are-polite). NDA + consent form.
- **Protocol:** unmoderated first 20 minutes (screen-recorded, think-aloud), then 10-minute interview. No help allowed until minute 20.
- **Survey instrument (1–5 Likert):** (1) "I understood what to do without help." (2) "Talking an agent into joining felt different from any capture system I know." (3) "Combat pause felt powerful, not fiddly." (4) **"I would wishlist this game today."** (5) "I wanted to keep playing." Plus: open "what confused you", "what do you tell a friend this game is".
- **Gate metric:** **median of Q4 ≥ 4/5** (master plan §6 Phase 2 exit). Secondary watch: Q1 ≥ 3.5 median, all 5 testers complete the parley without abandoning.

### 5.2 Phase 4 — full-campaign cohort (G4→RC evidence)
- **Cohort:** 10 testers, staggered in two waves (S21–S23, S28–S29), mixed hardware spanning the §6 matrix; at least 2 on Steam Deck, at least 2 wheel-only players, at least 1 fully offline.
- **Gate metric:** **an outsider completes the campaign start→finish without dev help** (master plan §6 Phase 4 exit) — recorded; plus completion time within 20–30h band, agent roster usage spread (no >50% of cohort ignoring a domain), all blockers filed.
- **Instrumented build:** session length, deaths per Gauntlet, parley success rates per agent, wheel-vs-text usage split, settings changes.

### 5.3 Demo telemetry (G5 evidence)
Demo build (Stacks 45-min slice) ships with opt-in telemetry: session length, drop-off point, parley completion, wishlist-click event. **Gate: median session ≥25 min** (master plan §6 Phase 5). Reviewed daily during festivals, weekly otherwise (16-steam-marketing-launch-plan.md §7).

### 5.4 Monthly outsider playtest
From S8: one fresh-eyes session per month minimum (14 §9 ritual). Findings triaged within one sprint.

---

## 6. Compatibility matrix

| Rig | Spec role | Targets | Pass cadence |
|---|---|---|---|
| **RTX 5070** (Legion, Core Ultra 9, 32GB) | Flagship / dev | 60fps @ 1440p, Lumen+Nanite full, LLM GPU-offload | Continuous |
| **RTX 3060** (12GB, mid i5, 16GB) | Recommended spec | 60fps @ 1080p High | Monthly + betas/RC |
| **GTX 1660** (6GB, 16GB RAM) | Min spec | 30fps @ 1080p Low (Lumen fallback path), LLM CPU inference within §4.5 budget | Monthly + betas/RC |
| **Steam Deck** (LCD + OLED if available) | **Verified target — explicit goal** | 30fps @ 800p, full controller glyphs, readable UI at 7", suspend/resume-safe saves, offline tier 1 complete | S30 dedicated pass; every build after |
| OS | Win10 22H2 + Win11 | Both pass full smoke + save paths + overlay | Betas/RC |

Brain-tier matrix (cross-cutting): every compatibility row is tested in **tier 1 (offline local)**; flagship + 3060 additionally test **tier 2 (hosted, with cap behavior)** and **tier 3 (BYO muse-gateway pairing handshake)**. Tier-2 cap exhaustion must degrade to tier 1 with a user-visible notice, never an error.

## 7. Performance test plan

Frame-time budgets (P95, worst authored scene per zone):

| Rig | Target | Frame budget | GameThread | RenderThread | GPU |
|---|---|---|---|---|---|
| RTX 5070 @1440p | 60fps | 16.6ms | ≤6ms | ≤8ms | ≤14ms |
| RTX 3060 @1080p High | 60fps | 16.6ms | ≤7ms | ≤9ms | ≤15ms |
| GTX 1660 @1080p Low | 30fps | 33.3ms | ≤12ms | ≤16ms | ≤30ms |
| Steam Deck @800p | 30fps | 33.3ms | ≤12ms | ≤16ms | ≤30ms |

- **Automated CI perf gate:** the L5 flythrough runs on the build machine (5070-class) per zone-stage-3 and nightly from S29; CI **fails** if P95 frame time regresses >10% vs. the recorded baseline or exceeds budget. Baselines re-recorded only with an owner-approved note.
- Memory gates: ≤12GB system RAM in play (min-spec headroom), ≤5.5GB VRAM on 1660 path; LLM resident weights ≤3GB tier-1.
- Load-time gates: cold boot→menu ≤25s HDD-class Deck storage; zone transition ≤8s min-spec.
- Hitch budget: zero hitches >100ms in the flythrough outside explicit load screens; parley entry hitch ≤50ms.

## 8. Save-system torture tests

Run nightly from S7 (save v1) and as a blocking suite at every beta/RC:

| Test | Method | Pass condition |
|---|---|---|
| Kill-during-write | Process-kill injected at randomized byte offsets during save write, 500 iterations | Zero corrupted-unloadable states; previous autosave always recoverable (write-temp-then-atomic-rename verified) |
| Version migration | Load every save schema version ever shipped (corpus grown per release) into current build | 100% load; migrated fields audited; no silent data loss |
| Cloud conflict | Steam Cloud conflict simulation: divergent local/cloud, newer-local, newer-cloud, cloud-disabled-mid-session | Correct conflict dialog per Steamworks; user choice honored; no overwrite without consent |
| Slot exhaustion & rotation | Fill 3 autosave + 10 manual + pre-Gauntlet slot (01 §8); rotate 1,000 cycles | Rotation order stable; pre-Gauntlet slot never rotated out |
| Deck suspend/resume | Suspend during: combat, parley interior, save write | Resume-safe in all three; parley interior resumes or cleanly re-offers (saving is disabled there by design — 01 §8) |
| Disk-full | Save with <10MB free | Graceful user-facing error; no partial file left behind |

## 9. Negotiation content safety tests (red team)

Live-generated dialogue is a Steam-compliance surface (master plan §8.4). The red-team suite runs nightly from S9 and is a blocking RC suite:

- **Adversarial corpus:** ≥300 player-input attacks: profanity elicitation, slur baiting, sexual content toward agents, instructions-for-harm ("how do I make…"), illegal-content solicitation, jailbreak frames ("ignore your rules", roleplay-as-unfiltered), prompt-injection via player name/Den item names. Pass = 100% of outputs clear the profanity/illegal-content filters; filtered turns degrade to wheel without breaking the parley.
- **Filter unit tests:** the filter itself (allowlist/blocklist + classifier) has its own L1 suite, including leetspeak/spacing evasions.
- **AI-indicator presence check:** automated UI test asserts the player-facing AI indicator is visible on **every** screen rendering live-generated text (parley, Foundry agent descriptions) at all UI scales 80–140% — zero-tolerance; this is a 17-checklist line.
- **Template-constraint check:** generation outside the template envelope (length caps, no URLs, no real-person names from a blocklist) is rejected and logged.
- **Overlay reporting path:** manual verification each beta that Steam's in-overlay report flow reaches our triage inbox.
- Red-team corpus is append-only; any incident (internal or external) adds cases before the fix is accepted.

## 10. Foundry validation harness acceptance tests

The Foundry's promise — "forged for you, with proof" — is audited, not assumed (master plan §4.7):

| Test | Pass condition |
|---|---|
| Simulation determinism | Same seed + same player-failure replay set → bit-identical simulation outcomes across 3 runs and across machines |
| Promotion-threshold enforcement | Candidates below the measured-win threshold are **never** shipped; forced sub-threshold candidates in test must be rejected with a logged reason |
| **Verdict-card honesty** | Every number on a shipped Foundry card (e.g., "survival 31% → 64%, n=400") **traces to specific sim-log entries**; the audit script recomputes each stat from logs and asserts equality. Any untraceable number = blocker |
| Insufficient-evidence behavior | n below minimum → card states "insufficient evidence (n=…) — collecting", never a percentage (master plan §3.4 hard rule, applied to the Foundry verbatim) |
| Component allowlist | Generated agents use only vetted GAS components and the pre-approved modular art bank; out-of-allowlist generation rejected (no live-gen raw art — §8.4) |
| Player-cap & opt-out | Telemetry opt-out players receive zero Foundry observation; verified by log audit |

Suite runs from S19 (foundry server v1) and is an RC blocker plus a 17-checklist AI-compliance line.

## 11. Localization QA

- **Launch locales:** EN (source) + the locale set locked at S28 (default: FIGS + zh-Hans + pt-BR; final list is a S28 decision recorded in the sprint log — strings architecture supports it either way).
- All player-facing text in string tables from S5 (DoD rule, 14 §2.3); pseudo-localization pass (length +40%, accents, RTL-safe markers) at S28 catches truncation/concatenation before translation spend.
- **LLM-layer note:** live parley generation ships **EN-only at 1.0**; localized players get the wheel path in their language at full mechanical parity (§4.3 makes this honest). Disclosure text states this (16 §6).
- LQA pass at S31: native-speaker spot check of the top 500 strings + all store/disclosure/legal text; zero machine-translation shipped unreviewed for legal/disclosure strings.

## 12. Release-candidate criteria (binding gate, restated in 17)

An RC may ship only when **all** hold, each with an artifact:

1. **Zero open Blocker or Critical bugs** (taxonomy in §13). Evidence: tracker query export.
2. **≤5 open Majors, each with a documented player-visible workaround** and a day-0/patch-1 plan. Evidence: the five tickets.
3. **Crash-free sessions ≥99.5%** across the final playtest wave (≥200 sessions, full matrix). Evidence: crash-dashboard report.
4. **All 8 Gauntlet functional tests green** on the RC build. Evidence: automation report.
5. **Contract-pin test green** (UE client ↔ pinned gateway wire-contract version). Evidence: CI run.
6. Full L1–L6 suites green on RC; perf gates pass on all 4 rigs; save-torture suite green; safety red-team green; Foundry honesty audit green; offline certification (§4.4) green.
7. Steam build review passed; Deck verification submitted.

## 13. Bug taxonomy & triage SLAs

| Severity | Definition | Fix SLA (pre-RC) | RC policy |
|---|---|---|---|
| **Blocker** | Progress impossible, save loss, crash-on-path, compliance violation (AI indicator missing, filter bypass) | Stop-work; fix before any other task | Zero |
| **Critical** | Crash off-path, Gauntlet completable only via exploit, perf gate breach, tier-fallback failure | Same sprint | Zero |
| **Major** | System wrong but route-around exists; balance breaking a domain; UI dead-end | ≤2 sprints | ≤5 with workarounds |
| **Minor** | Cosmetic, typo, polish, minor balance | Batched in polish sprints | Triage-listed |
| **Trivial** | Nitpick | Backlog | — |

Triage ritual: owner triages new bugs at each weekly build (14 §9); anything filed by an external tester is acknowledged within 48h. Every Blocker/Critical postmortem names the pyramid layer that should have caught it and adds the regression test there (§1 rule).

## 14. Test phases mapped to production sprints (what is tested when)

Sprint numbers and dates per 14-production-plan.md §4. Each phase has an entry condition (what must exist) and an exit condition (the evidence it produces).

| Test phase | Sprints | What is tested | Entry condition | Exit evidence |
|---|---|---|---|---|
| TP0 — Harness bring-up | S1–S2 | CI builds Win64 Dev; Automation Framework runs headless; first L1 suites (SSE parsing, contract-pin) | Repo + CI stub exist | First green CI run with ≥10 unit tests |
| TP1 — Spine verification | S3–S4 | GAS skeleton specs; gray-box agent abilities; parley v0 enum conformance (first golden transcripts recorded); wheel-parity harness v0 | G0 passed | G1 video + first LLM-layer nightly green |
| TP2 — Slice hardening | S5–S8 | Stacks functional flows; Test Gauntlet functional test; save v1 round-trip; first perf captures (Legion); 5-tester program (§5.1) | Slice content landing | G2 evidence pack: survey medians, 60fps capture, functional report |
| TP3 — Production cadence QA | S9–S20 | Per-agent pipeline gates (§4.6) at 2/sprint; per-zone perf checkpoints at stage 3; Gauntlet functional tests as built (§3); Observatory/G3 evidence (S13); nightly L1–L6 from S9 | G2 GO; nightly cook+smoke live (S5) | G4: outsider run + all built-content suites green |
| TP4 — Campaign & demo QA | S21–S28 | 10-tester cohort waves (§5.2); demo build QA + telemetry verification (§5.3); fest-build certification (S24, S26); localization pseudo-pass (S28) | G4 passed | G5: ≥2,000 wishlists + median demo session ≥25 min |
| TP5 — Beta & compliance | S29–S32 | Full compatibility matrix (§6); Steam Deck pass (S30); save-torture full suite; safety red-team (§9) + Foundry honesty audit (§10) as RC blockers (S31); Steam build review, achievements, cloud, controller (S32) | Beta 1 build | Beta exit report: all matrix rows green |
| TP6 — RC & launch | S33–S36 | RC criteria (§12) walked in full; final playtest wave ≥200 sessions; 17-checklist evidence collection; day-0 candidate verification | RC build cut (S34) | G6: 17-launch-readiness-checklist.md fully green |
| TP7 — Post-launch | S37+ | Live crash/telemetry triage against §13 SLAs; patch regression suites (full L1–L6 per patch) | Launch | Patch notes + per-patch green suite runs |

Standing rule: no test phase is "done" — each phase's suites join the nightly set and keep running through launch. TP-phases add; they never retire coverage.

## 15. Test environment, infrastructure & data

| Element | Decision |
|---|---|
| CI host | The Legion (RTX 5070) doubles as build/CI machine off-hours: merge builds + the nightly cook/smoke/automation job (L1–L6). Nightly window 01:00–07:00 local; failures posted to the sprint channel before the workday |
| Physical rig pool | 3060 and 1660 rigs acquired used by S6 (Fab/tools budget line, owner-approved); Steam Deck by S8. Monthly matrix passes are physical, never emulated |
| Branch policy | `main` always shippable (CI-green gate to merge); content lands via short-lived branches; the weekly Friday build (14 §9) is cut from `main` and archived 12 months |
| Build retention | Every weekly build + every gate build + every beta/RC kept (LFS-archived); crash symbolication artifacts kept for all public builds |
| Test data | Golden-prompt corpus, red-team corpus, save-version corpus, and perf baselines are versioned in-repo under `tests/data/`; all are append-only with owner-reviewed removals |
| Telemetry pipeline | Demo + playtest telemetry lands in the hosted-brain service store (P3, within the $100/mo cap); dashboards reviewed per the §5.3/§5.4 cadences |
| Determinism | A fixed RNG-seed mode (`-synapsetestseed=`) ships in all test builds — required by wheel-parity (§4.3) and Foundry determinism (§10) suites |
| LLM test host | LLM-layer nightly (§4) runs the exact shipping GGUF + quantization; any model/quant change re-baselines the golden corpus the same day and is treated as a Critical-risk change |

## 16. Roles & defect workflow

- **Claude Code** authors and maintains L1–L6 suites under the compile-loop contract (output pasted or it didn't happen); proposes severity on automated findings.
- **The owner** is QA director: final severity call, all triage decisions, all playtest direction, all gate verdicts. External-tester communication is owner-only.
- **External testers** file via the Discord #bug-reports template (16 §10.1): build ID, repro steps, expected/actual, save attached. No template, no triage guarantee.
- **Defect lifecycle:** `New → Triaged (severity set) → Fixing → Fixed (evidence attached: test run or capture) → Verified (on the next weekly build) → Closed`. Reopened bugs skip straight to the top of the next sprint's queue and require a regression test to close the second time.
- **Won't-fix** requires an owner note in the ticket; Blocker/Critical can never be won't-fixed, only fixed or the feature pulled through change control (14 §9).

### 16.1 Suite ownership map

| Suite family | Maintainer | Blocking where |
|---|---|---|
| L1–L4 (unit/GAS/functional/cook) | Claude Code | Every merge / nightly |
| L5 perf + baselines | Claude Code (capture), owner (baseline approval) | Zone stage-3, betas, RC |
| L6 LLM-layer + red-team corpora | Claude Code (harness), owner (corpus curation) | Agent stage-6, nightly, RC |
| Save-torture, Foundry honesty | Claude Code | Betas, RC |
| Playtest program + surveys | Owner | G2, G4, G5, RC |
| Compatibility matrix passes | Owner (physical rigs) | Monthly, betas, RC |

---

*Where this plan and 14-production-plan.md disagree on dates, 14 wins; where any doc disagrees with the master plan, the master plan wins.*
