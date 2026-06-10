# 17 — SYNAPSE Launch Readiness Checklist

**Project:** SYNAPSE — A M.U.S.E. Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

This is the **single launch gate document** — Gate G6 in 14-production-plan.md, walked end-to-end in Sprint 35 (2027-10-04 → 10-15) ahead of launch on **2027-10-26**. House rule, applied without exception: **no evidence, no claim.** Every item is a checkbox plus an `evidence:` line naming the artifact that proves it. An unchecked box with no artifact is a NO-GO for its section; section NO-GOs roll up to the ceremony in §13. Artifacts are filed under `docs/launch/evidence/` in the SYNAPSE repo, named as cited here.

Sources of each gate: 15-qa-test-plan.md (quality), 16-steam-marketing-launch-plan.md (marketing), master plan §6/§8/§10 (everything else). This document restates; it does not invent.

---

## 1. Product completeness

- [ ] **All 24 agents content-complete** — every agent passed all 7 pipeline stages (14 §6.1), including negotiation test and combat balance pass.
  evidence: `roster-completion-matrix.md` — 24 rows × 7 stages, each cell linking its artifact (spec-test run, golden transcripts, tuning-sheet row)
- [ ] **All 5 zones content-complete** — Stacks, Foundry, Gardens of Memory, Vault, Gate Spire each passed all 5 zone-pipeline stages (14 §6.2).
  evidence: `zone-completion-matrix.md` + per-zone perf captures (§2)
- [ ] **All 8 Gauntlets shipped** — Planning, Build, Review, Test, Security, Release, Owner Approval, Rollback bosses complete with phase scripts, rewards, autosave behavior.
  evidence: the 8 functional-test reports in §2 (the test *is* the completeness proof)
- [ ] **Council finale complete** including THE DEADLOCK confrontation per 06-narrative-campaign.md.
  evidence: recorded finale playthrough `finale-run.mp4`
- [ ] **Campaign outsider-completable** — an external player finished start→Council finale on the RC build without dev help.
  evidence: `outsider-rc-run.mp4` + tester attestation note
- [ ] **20h+ length verified** — RC cohort completion times fall in the 20–30h contract band.
  evidence: `cohort-completion-times.csv` (10-tester instrumented data, 15-qa §5.2)
- [ ] **Starter trio + commissioned heroes final** — AXIOM/CONTRARIAN/EMPATH starters; WARDEN/ORACLE/EMPATH commissioned assets integrated at final quality.
  evidence: contractor final-delivery sign-offs + in-game capture reel
- [ ] **Accessibility commitments shipped** — all six items of 01-game-design-document.md §9 (wheel-only completion, full remap, subtitles/UI scale, colorblind glyphs, photosensitivity pass, no permadeath/save rules).
  evidence: `accessibility-verification.md` — item-by-item test notes incl. a full wheel-only campaign run log

## 2. Quality bars (RC criteria from 15-qa §12, restated as gates)

- [ ] **Zero open Blocker/Critical bugs.** evidence: tracker query export `rc-bug-snapshot.csv`, dated RC day
- [ ] **≤5 open Majors, each with documented player-visible workaround + patch plan.** evidence: the ≤5 tickets, linked
- [ ] **Crash-free sessions ≥99.5%** over the final playtest wave (≥200 sessions, full matrix). evidence: crash-dashboard report `rc-crash-report.pdf`
- [ ] **All 8 Gauntlet functional tests green on the RC build.** evidence: automation report `rc-functional-tests.log`
- [ ] **Contract-pin test green** — UE client ↔ pinned cockpit wire-contract version. evidence: CI run link `rc-contract-pin.log`
- [ ] **Full L1–L6 suites green on RC** (unit, GAS specs, functional, cook+smoke, perf, LLM-layer). evidence: nightly suite report for RC build
- [ ] **Perf gates pass on all 4 rigs** — 5070 60fps@1440p, 3060 60fps@1080p, 1660 30fps@1080p, Deck 30fps@800p, P95 within 15-qa §7 budgets; zero >100ms hitches in flythroughs. evidence: `rc-perf-captures/` frame-time CSVs per rig
- [ ] **Steam Deck verified pass achieved** (controller glyphs, readability, suspend/resume, offline). evidence: Valve Deck-verification result + our `deck-pass-notes.md`
- [ ] **Save-torture suite green** (kill-during-write ×500, migration matrix, cloud conflict, slot rotation, Deck suspend, disk-full — 15-qa §8). evidence: `rc-save-torture.log`
- [ ] **Offline-mode certification** — full campaign on tier 1 with network disabled; all hosted calls timeout→fallback ≤2s. evidence: `offline-cert-run.md` (15-qa §4.4)
- [ ] **Localization QA closed** — pseudo-loc pass + LQA spot-check done; zero unreviewed machine translation in legal/disclosure strings. evidence: LQA report S31

## 3. AI compliance

- [ ] **Steam AI disclosure live on the store page**, matching 16 §6 verbatim, with the frozen shipping model name/version inserted. evidence: store-page screenshot + Steamworks submission record
- [ ] **Player-facing AI indicator present in the shipping build** on every surface rendering live-generated text, at all UI scales. evidence: automated indicator-presence test report (15-qa §9) + screenshot set
- [ ] **Guardrail red-team pass green** — ≥300-case adversarial corpus, 100% filtered; filter unit tests green incl. evasion cases. evidence: `rc-redteam.log`
- [ ] **Steam in-overlay report path honored** — a test report filed via the overlay reached the triage inbox. evidence: end-to-end test note with timestamps
- [ ] **Foundry verdict-card honesty audit green** — every shipped card number recomputed from sim logs and matched; promotion thresholds enforced; insufficient-evidence behavior verified; component allowlist enforced; opt-out players receive zero observation. evidence: `foundry-honesty-audit.md` (15-qa §10 suite output)
- [ ] **No live-generated art assets ship** — generation limited to allowlisted components per master plan §8.4. evidence: allowlist-enforcement test log + content audit note
- [ ] **Live-generation kill toggle works** — player can disable all runtime generation; wheel path verified at parity. evidence: toggle test note + parity suite run (15-qa §4.3)

## 4. Legal

- [ ] **Trademark/name search closed** — "SYNAPSE" cleared in games (USPTO + Steam), or a locked backup adopted (master plan Task 0.4, owner decision §14.1). evidence: search report + owner decision record
- [ ] **GPL/license re-audit of shipping deps closed** (master plan §8.5) — SYNAPSE links nothing GPL (verified); local-LLM plugin and bundled model licenses permit commercial redistribution; model license card included; gateway distribution posture for P1 verified. evidence: `license-audit-final.md` with dependency-by-dependency disposition
- [ ] **IP consult done** (~$300, contingency line). evidence: consult summary memo
- [ ] **Privacy policy final** — covers demo + 1.0 telemetry, Foundry observation, hosted tier, crash reporting. evidence: published policy URL + version hash
- [ ] **Telemetry consent final** — opt-in at first run with the full observation list shown (owner decision §14.5 resolved). evidence: first-run consent screenshot + the consent copy in the string table
- [ ] **Contractor IP assignments on file** for all four slots (capsule, heroes, music, SFX/VO). evidence: signed agreements index
- [ ] **Third-party attribution/licenses screen complete** (Fab/Megascans terms, model license, font licenses). evidence: credits-screen capture + license manifest

## 5. Platform (Steam)

- [ ] **Steam build review passed**; release build on the default branch (hidden) with correct depots (game + demo separation intact). evidence: Steamworks review status + build IDs
- [ ] **Achievements final** — full list implemented, tested, icons uploaded; no achievement gated on difficulty (01 §8). evidence: achievement test checklist
- [ ] **Cloud saves enabled and conflict-tested.** evidence: cloud-conflict suite run (15-qa §8)
- [ ] **Controller certification** — full pad support, glyphs correct per device, Steam Input config published. evidence: controller test matrix
- [ ] **Store assets final** — capsule suite all sizes, 6+ screenshots, trailers encoded and live, tags per 16 §3. evidence: store-page final review screenshot set
- [ ] **Age ratings filed** — IARC questionnaire completed (and regional certs where required); rating consistent with 01 §11 content contract; AI-generated-content questions answered consistently with §3. evidence: rating certificates
- [ ] **Pricing matrix set** — $24.99 base, regional matrix accepted, 10%/14-day launch discount scheduled. evidence: Steamworks pricing screenshot
- [ ] **Soundtrack DLC + Art PDF live and linked.** evidence: DLC page links

## 6. Brain-tier matrix

- [ ] **Tier 1 (bundled local) certified complete** — the full game, offline, on min-spec CPU inference within latency budget (first token ≤1.5s, reply ≤8s or wheel offered). evidence: offline cert (§2) + latency capture on the 1660 rig
- [ ] **Tier 2 (hosted) caps tested** — free-tier caps enforce; cap exhaustion degrades to tier 1 with user-visible notice, never an error; queue limits hold under synthetic load. evidence: cap/load test report
- [ ] **Tier 3 (BYO MUSE-gateway) pairing handshake tested** — pairing, bearer auth, SSE stream, unpair, and auth-expiry recovery against MUSE Platform v1.0. evidence: pairing test log against the GP1-tagged release
- [ ] **Kill-switches verified** — per-tier disable toggles (player-side) and the hosted-service kill-switch (operator-side) each tested live; game remains fully playable on tier 1 in every kill state. evidence: kill-switch test matrix
- [ ] **Hosted-brain cost guard armed** — monthly spend cap + alerting on the $100/mo budget line. evidence: billing-alert configuration screenshot

## 7. P1 — MUSE Platform v1.0 lane (master plan §10 DoD)

*(Gated at GP1, Sprint 10 — re-verified here because tier 3 and the post-game MUSE bridge depend on it.)*

- [ ] **Held PR chain resolved per R00** — #131 → #142 → #143 → #147 → #149 → #150 rebased and landed, owner-authorized at each gate. evidence: merge commits + per-gate authorization records
- [ ] **Image-gen provider wired** (room editor unblocked; feeds P3). evidence: room-editor generation demo capture
- [ ] **Voice engine concretes bound.** evidence: voice round-trip demo log
- [ ] **Live gateway default-on after pairing.** evidence: fresh-install pairing log
- [ ] **Test suite green; docs current.** evidence: CI run on the v1.0 tag + docs review note
- [ ] **Everything-functional audit closed** — `aos-audit-validator` run; README claims table all SUPPORTED. evidence: final audit report
- [ ] **Installable packages proven** — install.ps1, Linux/WSL/macOS + Homebrew, Termux, Docker compose, release-signed APK, Tauri bundle — each with model bootstrap, first-run pairing, and a smoke test **with output**. evidence: smoke-test output per installer, archived

## 8. Marketing readiness

- [ ] **Wishlist threshold check** — ≥7,000 wishlists (Popular Upcoming threshold). If below: the §13 ceremony weighs the 16 §12 decision tree outcome on record — launching below threshold is an explicit owner decision, not a drift. evidence: Steamworks wishlist report, launch-week dated
- [ ] **Press/creator kit shipped T-6 weeks (by 2027-09-14)** — kit contents per 16 §9: fact sheet, key art + capsule crops, 6 screenshots, parley GIFs, both trailers, demo/preview build keys, AI-transparency one-pager, embargo terms. evidence: distribution list + send receipts
- [ ] **Launch trailer live** at embargo lift. evidence: trailer URL + analytics snapshot
- [ ] **Creator embargo lifts scheduled** — previews T-3 days (2027-10-23). evidence: embargo calendar + confirmations from committed channels
- [ ] **Launch-week creator wave 2 keys staged** (top-25 converting channels). evidence: key batch + assignment list
- [ ] **Demo still live and current** — demo build matches launch messaging; telemetry on. evidence: demo build ID check
- [ ] **Discord ready** — launch-day channel plan, rules, FAQ, pinned known-issues template. evidence: server audit note

## 9. Ops day-0

- [ ] **Crash dashboard live** — symbolicated crash reporting from the RC build flowing; alert thresholds set (spike >0.5% sessions). evidence: dashboard URL + a test-crash round trip
- [ ] **Hotfix pipeline rehearsed** — a real hotfix built, pushed to a beta branch, and promoted in <4 hours, end-to-end, in S35. evidence: rehearsal timeline log with build IDs
- [ ] **Day-0 patch staged** (Blocker/Critical fixes only, per 16 §13 policy) — or an explicit "no day-0 patch" decision recorded. evidence: staged build ID or decision note
- [ ] **Support inbox live** — support@ address routed, response templates ready, refund-question macro consistent with Steam policy. evidence: test ticket round trip
- [ ] **Community mods briefed** — at least 2 moderators with the launch runbook, known-issues list, and escalation path. evidence: briefing note + mod acknowledgments
- [ ] **Rollback artifacts staged** — previous-known-good build retained on a branch; store-page rollback copy drafted; §14 protocol printed. evidence: branch/build IDs
- [ ] **On-call calendar** — owner coverage hours for T-0→T+7 written down, including sleep (a runbook that requires a 24/7 solo human is a defect). evidence: the calendar

**Day-0 alert thresholds (armed before T-0; each alert names its action, not just its number):**

| Metric | Threshold | Automatic action |
|---|---|---|
| Crash rate | >0.5% of sessions (1h window) | Page the owner; open hotfix decision per the rehearsed pipeline |
| Tier-1 LLM init failure | >2% of fresh installs | Page the owner; known-issues post within 1h (wheel path keeps players unblocked) |
| Save-failure reports | Any ≥3 matching reports | Treat as Blocker; rollback consideration per §14 |
| Refund rate | >8% day-1 | Read every refund reason; same-day diagnosis post |
| Review score | <70% positive at 50 reviews | Theme triage; pinned commitments post per 16 §13 protocol |
| Hosted-tier spend | >2× daily budget | Hosted-tier soft cap engages automatically (degrades to tier 1 — §6 verified) |

## 10. Observatory & game↔MUSE bridge (ship-config sanity)

- [ ] **Neural Observatory mode stable** — G3 evidence still reproducible on RC (snapshot, stream, one rec card honest-by-construction). evidence: G3 artifacts re-run on RC
- [ ] **Real-MUSE unlock bridge** is owner-gated, cosmetic-by-default, opt-in, and fully absent from the offline path (standalone-game test, master plan §4.8). evidence: config audit + offline-cert cross-check
- [ ] **Post-game MUSE reveal** does not gate any campaign content. evidence: outsider run (§1) reached credits with zero MUSE pairing

## 11. T-minus countdown (the order this checklist gets walked)

The checklist is not walked in one sitting. Items mature on this schedule; S35 is verification, not discovery.

| T-minus | Date | What must already be true | Checklist sections maturing |
|---|---|---|---|
| T-26w | 2027-04-30 | Demo live; telemetry flowing | §8 (demo line), §6 tier checks begin |
| T-19w | 2027-06-14 | Next Fest entered ≥2,000 wishlists | §8 wishlist trajectory on record |
| T-13w | 2027-07-23 | Beta 1; compatibility pass 1; save-torture green | §2 first full walk (red items get sprints, not hope) |
| T-9w | 2027-08-20 | Red-team + Foundry honesty audits green; model frozen | §3 complete except store-page items |
| T-6w | 2027-09-14 | Press kit shipped; Steam build review submitted; ratings filed | §5, §8 majority green; §4 closed (legal items may not be open inside T-6w) |
| T-4w | 2027-10-01 | RC cut; RC criteria walk begins | §1, §2 final walk on RC |
| T-3w | 2027-10-08 | Hotfix rehearsal done; dashboards live; mods briefed | §9 complete |
| T-11d | 2027-10-15 | **GO/NO-GO ceremony (§13)** | All sections verdict-ready |
| T-3d | 2027-10-23 | Embargo lifts; day-0 decision final | §8 final lines |
| T-0 | 2027-10-26 | Run of show (§15) | — |

Any section still red at its maturity date is escalated at that week's sprint review — not discovered at the ceremony. The ceremony confirms; it must never surprise.

## 12. Evidence standard & section verdict roll-up

**Filing standard (applies to every `evidence:` line above):**
1. Artifacts live in `docs/launch/evidence/` under the exact filename cited; screenshots carry visible timestamps; logs are raw, untrimmed output (the compile-loop rule extended to launch).
2. Every artifact names its build ID. Evidence from a non-RC build satisfies nothing in §1–§3, §5, §6.
3. Derived numbers (crash-free %, session medians, completion times) must be recomputable from an attached raw export — the Foundry honesty rule applied to ourselves.
4. An artifact may satisfy multiple boxes; a box may never be satisfied by narrative alone.

**Verdict roll-up (filled during the ceremony, lives in `go-no-go-record.md`):**

| § | Section | Boxes | Green | Red | Waived | Verdict |
|---|---|---|---|---|---|---|
| 1 | Product completeness | 8 | | | — | |
| 2 | Quality bars | 11 | | | — | |
| 3 | AI compliance | 7 | | | — | |
| 4 | Legal | 7 | | | — | |
| 5 | Platform | 8 | | | — | |
| 6 | Brain-tier matrix | 5 | | | — | |
| 7 | P1 platform v1.0 | 7 | | | — | |
| 8 | Marketing | 7 | | | (wishlist only) | |
| 9 | Ops day-0 | 7 | | | — | |
| 10 | Observatory & bridge | 3 | | | — | |

**Waivable register (pre-declared, closed):** exactly one item in this document is waivable — the §8 wishlist threshold, and only with the 16 §12 decision-tree outcome attached. Quality (§2), AI compliance (§3), legal (§4), and ops (§9) items are never waivable; if that ever feels constraining, the answer is §14, not a waiver.

**Artifact index template (`docs/launch/evidence/INDEX.md`, maintained from T-13w):**

| Artifact | Satisfies | Build ID | Date | Filed by | Raw data attached? |
|---|---|---|---|---|---|
| `rc-crash-report.pdf` | §2 crash-free | | | | Y/N |
| `rc-functional-tests.log` | §1 Gauntlets, §2 functional | | | | Y/N |
| *(one row per artifact cited in §1–§10)* | | | | | |

## 13. The GO/NO-GO ceremony

**When:** Friday **2027-10-15** (end of S35), 10:00 local. **Who:** the owner (sole launch authority), with the Claude Code engineering summary and this document, fully walked, on the table.

**Agenda (90 minutes, timeboxed):**

| Min | Item |
|---|---|
| 0–10 | Claude Code engineering summary: RC build ID, suite results, open Majors with workarounds |
| 10–50 | Section-by-section verdict walk (§12 roll-up filled live, artifact spot-checks) |
| 50–65 | Red items: fix / waive (register only) / NO-GO decisions |
| 65–75 | Risk read-back: the owner restates, aloud, what is being shipped with which known issues |
| 75–90 | Decision + recording; if GO, T-3d embargo and day-0 decisions confirmed on the spot |

**Procedure:**
1. Read every section verdict aloud: each of §1–§10 is GREEN (all boxes checked with evidence) or RED (any box open).
2. Any RED section → the section owner-action list is read; the owner chooses **(a) fix-and-re-walk** within the S35 window, **(b) waive** — allowed only for items explicitly marked waivable in writing with a dated remediation plan (wishlist threshold is the only pre-declared waivable item; quality, AI-compliance, and legal items are never waivable), or **(c) NO-GO**.
3. GO requires the owner's exact authorization phrase, in writing, in the gate record:
   > **`Yes, with authorization.`**
   No paraphrase counts. The phrase, the date, the build ID, and the section verdicts are recorded in `docs/launch/evidence/go-no-go-record.md`. This mirrors the house owner-gate rule: launch is a deploy.
4. NO-GO → §14.

## 14. NO-GO / rollback & delay protocol

- **Delay decision:** pick the next viable Tuesday ≥2 weeks out that clears the fix list; never slip by less than 2 weeks (thrash) or past the **2028-02-22 ceiling** without a full master-plan review. Wishlist momentum is preserved with an honest delay post (the transparency brand applies to bad news first).
- **Announce within 24h** of NO-GO: store page post + Discord + press-list email with the new date and the one-sentence true reason.
- **Re-walk rule:** a delayed launch re-walks §2 (quality), §3 (AI compliance), and §9 (ops) in full; other sections re-verify only changed items.
- **Post-launch rollback (if a catastrophic defect ships):** Steam build rollback to the staged known-good build (§9) — execute first, explain second; pinned known-issues post within 1 hour; hotfix per rehearsed pipeline; postmortem within 72h naming the checklist line that should have caught it, and amending this document.

**Delay announcement template (FINAL — fill brackets, change nothing else):**

> SYNAPSE is moving to **[new date]**. The reason is simple: **[the one true sentence — e.g., "our release candidate didn't hit our crash-free bar, and we won't ship below it"]**. Every gate this game ships through is public in our launch checklist, and this one stayed red. The demo stays up, the date is firm, and we'll show you the fix the same way we show everything else — with the receipts. — Jeremiah

**Rollback announcement template (FINAL):**

> We've rolled SYNAPSE back to build **[ID]** while we fix **[issue]**. If it affected your save: **[status + instructions]**. Fix ETA: **[honest window]**. Postmortem to follow within 72 hours. — Jeremiah

---

## 15. Launch Day Run of Show — Tuesday 2027-10-26 (all times Pacific)

| Time | Action | Owner | Evidence captured |
|---|---|---|---|
| 07:00 | Wake, coffee. Final checklist glance; confirm crash dashboard + support inbox green overnight | Owner | dashboard screenshot |
| 07:30 | Verify default-branch build ID = GO-record build ID; verify discount scheduled; verify trailer set as page lead | Owner | Steamworks screenshots |
| 08:00 | Creator wave-2 keys sent; "launching today" post to Discord + socials | Owner | send receipts |
| 09:00 | Final smoke: fresh install from Steam (beta-visible), boot→new game→first parley→save | Owner | smoke log |
| 09:45 | Stop touching things. Release-button checklist open. Breathe | Owner | — |
| **10:00** | **PRESS RELEASE. Game live, 10% discount live** | Owner | store page screenshot, timestamped |
| 10:05 | Launch announcement everywhere simultaneously (Steam News, Discord @everyone, socials, press-list email); pin Discord launch thread | Owner | post links |
| 10:30 | First buyer telemetry check: install success, crash rate, tier-1 LLM init success rate | Owner | dashboard snapshot |
| 12:00 | **Hotfix decision point #1** — crash spike >0.5% or any Blocker report → rehearsed pipeline; else log "no action" | Owner | decision note |
| 13:00 | First reviews read; respond per protocol (facts and bugs only — 16 §13); known-issues post updated | Owner | response log |
| 15:00 | Tag-rank check #1 (Creature Collector tag, New & Trending); archive screenshots the moment placements appear | Owner | rank screenshots |
| 17:00 | **Hotfix decision point #2**; community Q&A hour in Discord (scheduled, announced in the morning post) | Owner | decision note |
| 19:00 | Day-1 numbers snapshot: units, wishlist conversion %, refund rate, review score, crash-free % | Owner | `day1-report.md` |
| 20:00 | Day-1 thank-you post with one real number in it (proof-over-promise, to the end); set T+1 priorities | Owner | post link |
| 21:00 | Handoff to overnight alerting (§9 thresholds page the owner only for Blocker-class spikes). **Stop. Sleep.** | Owner | on-call config |
| T+1 09:00 | Day-2 standup with Claude Code: triage queue, patch-1 scope opens, runbook continues per 16 §13 | Owner | triage notes |

**Run-of-show ground rules:** nothing ships on launch day that wasn't staged before launch day; every decision point produces a written note even when the decision is "no action" (the ledger habit); and if any §9 threshold trips, the threshold's pre-written action executes — launch day is for following the plan, not improvising one.

**Document history:** v1.0 (2026-06-10) — initial DESIGN LOCKED issue. Amendments only by versioned errata recorded here; the GO/NO-GO record (§13) cites the exact version walked.

---

*This checklist restates gates defined in 14/15/16 and the master plan. If a gate here ever conflicts with its source, the source wins and this file gets a versioned errata. The launch is GO only on the recorded phrase — `Yes, with authorization.` — and on nothing else.*
