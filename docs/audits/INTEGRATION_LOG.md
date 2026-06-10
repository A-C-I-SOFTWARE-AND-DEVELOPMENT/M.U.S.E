# MUSE Integration Log

> **Stale baseline (2026-05-26).** This log records the PR #131 integration
> from base `bc97e43`; `main` has since advanced ~211 commits. Current launch
> readiness lives in
> [`docs/launch/LAUNCH_STATUS_CURRENT.md`](docs/launch/LAUNCH_STATUS_CURRENT.md)
> and the full audit in
> [`docs/audits/CODEBASE_AUDIT_2026-06-01.md`](docs/audits/CODEBASE_AUDIT_2026-06-01.md).

**Branch:** `claude/hopeful-bardeen-KBVqi`
**Started:** 2026-05-26
**Plan:** `/root/.claude/plans/mission-you-are-idempotent-bunny.md`
**Audit:** `INTEGRATION_AUDIT.md`
**Base SHA:** `bc97e43` (origin/main at start)

Each phase records its starting SHA, the SHA after each op, and the SHA at
phase end (the checkpoint). Rollback uses the checkpoint of the
last-known-good phase.

## Phase 0 — Setup and audit (no code changes)

**Start SHA:** `bc97e43`

| Step | Status | SHA | Notes |
|------|--------|-----|-------|
| Create `INTEGRATION_AUDIT.md` | DONE | — | Full classification of 53 PRs |
| Create `INTEGRATION_LOG.md` | DONE | — | This file |
| Commit audit-only | PENDING | — | Single commit, no code |
| Push to origin | PENDING | — | `git push -u origin claude/hopeful-bardeen-KBVqi` |
| **Q1: Owner review of audit** | PENDING | — | Promote/demote any PR? |

**Phase 0 checkpoint SHA:** TBD

---

## Phase 1 — Python foundation — DONE

**Plan:** WorkPacket schema (#104), Python log redactions (#109 part), CLI proposals (#105).
**Start SHA:** `3fce42f`

| Step | PR | Method | Target SHA | Status | Result SHA | Notes |
|------|----|----|-----|--------|-----|-------|
| 1.1 | #104 | `merge --no-ff` | `e3e62ba` | DONE | `87c353a` | clean merge; +5 files / +657 lines (additive) |
| 1.2 | #109 part | `cherry-pick -x` | `bbfc6ed` | DONE | `28b2cf1` | 10 files; auto-merge in `gateway/run.py`, `tools/skills_tool.py` |
| 1.3 | #109 part | `cherry-pick -x` | `d687a8a` | DONE | `8e3dcb9` | 1 file; CodeQL taint-break |
| 1.4 | #105 | `merge --no-ff` | branch tip `52d5f1b` (3 commits) | DONE | `d8fd69d` | 4 files / +761 lines; brings 9ac789e (feat) + 31424cb (15 tests) + 52d5f1b (docs) |

**Phase 1 gate result:**
- `ruff check hermes_cli/jarvis_prime/ tests/test_jarvis_prime_*.py` → **All checks passed**
- `python3 scripts/check-windows-footguns.py --all` → **No Windows footguns (556 files)**
- `python3 -m pytest tests/test_jarvis_prime_*.py tests/test_orchestrator_*.py -q` → **398 passed, 1 skipped in 9.95s**

**Phase 1 checkpoint SHA:** `d8fd69d`

**Reclassification note:** #109 confirmed orphan (no merge-base, 39 commits ahead from fork history). #105 reclassified from ORPHAN → clean-base; the audit was wrong (shallow fetch). #105 merge-base = `bc97e43`, 3 feature commits on top.

---

## Phase 2 — Documentation — DONE

**Start SHA:** `d8fd69d`

| Step | PR | Method | Target SHA | Status | Result SHA | Notes |
|------|----|----|-----|--------|-----|-------|
| 2.1 | #108 | merge --no-ff | `fbbfae4` | DONE | (merge) | 5 docs added; product spec, screen map, user flows, onboarding spec, launch standard |
| 2.2 | #110 | merge --no-ff | `82bf452` | DONE | (merge) | 5 docs added; deep audit, final gap map, finish roadmap, permission risk register, research translation map |
| 2.3 | #111 | merge --no-ff | `7919e56` | DONE | `0801d3c` | 1 doc added; launch readiness audit (verdict RED, 87/280) |

**Phase 2 gate result:** Docs render; 11 new `docs/jarvis-prime-app-*.md` files; no `apps/android/` or `hermes_cli/` touched.

**Phase 2 checkpoint SHA:** `0801d3c`

---

## Phase 3 — Android base (theme + navigation) — DONE

**Start SHA:** `0801d3c`

| Step | PR | Method | Target SHA | Status | Result SHA | Notes |
|------|----|----|-----|--------|-----|-------|
| 3.1 | #112 | `cherry-pick -x` | `249f7f5` | DONE | `e3e3870` | Clean cherry-pick; 13 files, no protected paths touched; 5→10 route shell |
| 3.2 | #113 | `cherry-pick -x` | `8478240` | DONE | `699515a` | 2 conflicts resolved (SplashScreen.kt — dropped redundant ☤; strings.xml — took #113 polish + preserved #112 nav/onboarding additions); 35 files total |
| 3.3 | guard | `git diff --name-only` | — | DONE | — | All changes confined to `apps/android/` + `docs/jarvis-prime-app-*.md`; no protected paths touched |

**Phase 3 gate result (local pre-CI check):**
- XML well-formed (195 string entries)
- AndroidManifest permissions = baseline (3 unchanged: POST_NOTIFICATIONS, FOREGROUND_SERVICE, FOREGROUND_SERVICE_DATA_SYNC)
- HomeScreen.kt imports resolve (orchestrator package preserved for ViewModel)
- ScreenTest.kt validates required routes catalog
- **Note: cannot run `./gradlew` locally (no Android SDK); CI workflow `android-build.yml` will validate APK build on push**

**Phase 3 checkpoint SHA:** `699515a`

## Phase 4 — Android feature screens — DONE (via selective cherry-pick strategy)

After Phase 4.2 abort, owner approved selective cherry-pick strategy: extract
NEW FILES only from each remaining PR, skip centralized-config edits, do one
wiring commit at the end.

| Step | PR | Method | Result SHA | Notes |
|------|----|--------|------------|-------|
| 4.bundle | #115, #122, #124, #120, #121, #114, #118, #129, #128(tests) | `git checkout <sha> -- <new files>` | `8769342` | 57 files / +8831 lines; all new packages, no conflicts |
| 4.audit | #118 (re-pull after deeper fetch) | `git checkout 56c1e07 -- audit/*` | `2194771` | 8 audit production files + AuditFormattingTest |
| 4.wiring | (integration) | `Edit AppContainer/Screen/NavGraph/strings.xml` | `fa74a70` | Adds repos + 6 new VM factories; new Capability route; replaces Memory/Audit placeholders with real screens; new AuditDetail full-screen push |
| 4.fix | #128 (non-test parts) | `git checkout 516c04d -- README + gradle + workflow + backup` | `2276e04` | README rewrite, backup_rules.xml tightened, unit-tests CI job added, stale gateway-URL comment dropped |

**DEMOTED (incompatible / orphan re-baseline):**
- #109a Android onboarding — different package (`com.jeremiahecherd.jarvisprime`)
- #106 notifications — separate gradle module
- #117 chat — orphan re-baseline pattern
- #119 interactive icon — orphan re-baseline pattern

**DEFERRED:**
- #123 voice (RECORD_AUDIO) — owner Q4
- #127 gateway event spine — owner Q5

**Phase 4 final checkpoint SHA:** `2276e04`

**Phase 4 verification:**
- Local pytest: 398 passed, 1 skipped
- ruff: clean
- windows-footguns: clean (556 files)
- AndroidManifest permissions: IDENTICAL to baseline
- strings.xml: well-formed (198 entries)
- No protected paths touched (`.github/workflows/*` only ADDS `unit-tests` job)

## Phase 7 — Demo trace — DONE

Wrote `docs/jarvis-prime-integration-demo-trace.md` (`f43fdc8`):
- 8 sections matching the plan's structure
- Per-PR provenance table
- Safety inventory with literal authorization phrase + owner-gated actions
- Open items including the CodeQL 12-thread context and pre-existing LSP failures

## Phase 8 — Final PR composition

PR #131 (DRAFT) is the deliverable. Body updated with:
- Audit table link, log link, demo trace link
- Provenance summary
- Open items + owner-gated decisions pending
- Owner authorization request: `Yes, with authorization.`

**Final SHA (will be updated as PR receives reviewer feedback):** `f43fdc8`

**Owner action required for any merge:** the literal phrase
`Yes, with authorization.` per `hermes_cli/jarvis_prime/owner_auth.py`.

**Start SHA:** `699515a`

| Step | PR | Method | Target SHA | Status | Result SHA | Notes |
|------|----|----|-----|--------|-----|-------|
| 4.1 | #107 | merge --no-ff | `b82b6e2` | DONE | `632fca0` | 5 conflicts resolved: AppContainer.kt (kept both orchestratorServiceController + new approval store/sink), Screen.kt (dropped #107's duplicate route declarations — already in #112), HermesNavGraph.kt (unified imports + dropped #107's onboarding callback additions + replaced Approvals placeholder with real ApprovalsScreen wrapped by ShellHost), HomeScreen.kt (kept HEAD's shell-aware signature, dropped #107's Scaffold/TopAppBar pattern), strings.xml (preserved both sets, added 2 new approvals_empty_* keys from #107) |
| 4.2 | #115 | merge --no-ff (ATTEMPTED) | `8248cdb` | ABORTED | — | 5 conflicts surfaced; #115 uses different route strings (`jarvis_control`, `jarvis_audit`, `jarvis_memory`) that collide with #112's `control`, `audit`, `memory`; also adds Memory/Audit screens that are duplicates of what #122 and #118 will land. Marking BLOCKED-conflict-too-deep pending escalation. |
| 4.3-4.12 | #116, #122, #123, #109 part, #117, #118, #119, #120, #124, #106, #114 | — | — | PAUSED | — | Pending owner decision on conflict-resolution strategy after Phase 4.2 escalation |

**Phase 4 checkpoint SHA:** `632fca0` (Phase 4 paused after step 4.1)

### Phase 4 escalation note

The file-by-file conflict policy is working but per-PR cost is high. #107 required 5 conflict resolutions in centralized files (Screen.kt, HermesNavGraph.kt, AppContainer.kt, HomeScreen.kt, strings.xml). #115 surfaced 5 more conflicts — and inspection showed #115 was authored against a different baseline (different route strings, different Memory/Audit implementations than #122/#118 will land later).

Projecting forward: 11 more screen PRs × ~5 conflicts each = ~55 more manual conflict resolutions, each requiring careful inspection of which side to prefer. Some PRs (#115's Memory/Audit, #126 entirely, possibly #114) are functionally superseded by other PRs in the same wave and contribute net negative value.

**Pausing for owner decision** at Q2-bis: how to proceed given the actual scaling cost.

---

## Phase 4 — Android feature screens

Order: clean-base merges first, then orphan cherry-picks.

| Step | PR | Method | Target SHA | Status | Result SHA | Notes |
|------|----|----|-----|--------|-----|-------|
| 4.1 | #107 | merge --no-ff | `b82b6e2` | PENDING | — | approval UI |
| 4.2 | #115 | merge --no-ff | `8248cdb` | PENDING | — | control + settings |
| 4.3 | #116 | merge --no-ff | `d558410` | PENDING | — | task/worker cards |
| 4.4 | #122 | merge --no-ff | `637102f` | PENDING | — | memory transparency |
| 4.5 | #109 part | cherry-pick -x | `5bf1eb7` | PENDING | — | Android onboarding |
| 4.6 | #106 | cherry-pick -x | `abde9b9` | PENDING | — | notifications |
| 4.7 | #114 | cherry-pick -x | `4a9a051` | PENDING | — | social intelligence |
| 4.8 | #117 | cherry-pick -x | `af1331d` | PENDING | — | chat screen |
| 4.9 | #118 | cherry-pick -x | TBD | PENDING | — | audit/proof; resolve SHA at execution |
| 4.10 | #119 | cherry-pick -x | `f7782bb` | PENDING | — | interactive icon |
| 4.11 | #120 | cherry-pick -x | `621b07e` | PENDING | — | emergency stop; preserve owner-audit log |
| 4.12 | #124 | cherry-pick -x | `ccbad67` | PENDING | — | capability UI |
| (skip) | #123 | DEFER | — | DEFER | — | **Q4 pre-merge:** RECORD_AUDIO disposition |

After each: run guard `git checkout HEAD~1 -- .github/ .claude/ agents/ recovered-agent-sources/`. Verify AndroidManifest.xml permissions = baseline + any explicitly authorized.

**Phase 4 gate:** APK builds, lint, unit tests, no new restricted permissions.

**Phase 4 checkpoint SHA:** TBD

---

## Phase 5 — Android integration glue (overlap resolution)

**Q6 BEFORE Phase 5 begins.** Default plan: option A (cherry-pick #129, then #125 selective files only, drop #126).

| Step | PR | Method | Target SHA | Status | Result SHA | Notes |
|------|----|----|-----|--------|-----|-------|
| (skip) | #127 | DEFER | — | DEFER | — | **Q5 pre-merge:** gateway disposition |
| 5.1 | #129 | merge --no-ff | `36fc226` | PENDING | — | HomeScreen wins |
| 5.2 | #125 | cherry-pick -x (selective) | `fef396b` + `7c22b4e` | PENDING | — | Uncontested files only; revert overlapping files |
| (skip) | #126 | SUPERSEDED-BY-#125 | — | DROP | — | Documented |

**Phase 5 gate:** Full APK build + manual code-walk of HomeScreen composition.

**Phase 5 checkpoint SHA:** TBD

---

## Phase 6 — Cleanup + older Phase PRs re-eval

**Q7 at start of Phase 6.**

| Step | PR | Method | Target SHA | Status | Result SHA |
|------|----|----|-----|--------|-----|
| 6.1 | #121 | cherry-pick -x | `7d3a8d9` | PENDING | — |
| 6.2 | #128 | merge --no-ff | `516c04d` | PENDING | — |
| 6.3 | Older Phase PRs | per-PR re-audit | — | PENDING | — |

**Phase 6 checkpoint SHA:** TBD

---

## Phase 7 — Verification + demo trace

| Step | Status | Notes |
|------|--------|-------|
| `ruff check .` | PENDING | — |
| `python scripts/check-windows-footguns.py --all` | PENDING | — |
| `pytest tests/ -q --ignore=tests/integration --ignore=tests/e2e -n auto --timeout=30 --timeout-method=signal` | PENDING | — |
| `cd apps/android && ./gradlew --no-daemon --stacktrace lint testDebugUnitTest assembleDebug` | PENDING | — |
| APK metadata captured | PENDING | `aapt dump badging` |
| `docs/jarvis-prime-integration-demo-trace.md` written | PENDING | 6 sections |
| Permissions diff against baseline | PENDING | grep `<uses-permission` |
| Safety inventory | PENDING | redaction sites, OWNER_GATED_ACTIONS, AUTHORIZATION_PHRASE preserved |

---

## Phase 8 — Final PR (DRAFT)

**Q9 before opening PR.**

- [ ] Title set
- [ ] Body skeleton populated with audit + log + demo-trace links
- [ ] Provenance table with all SHAs
- [ ] Owner-gate request: explicit `Yes, with authorization.` ask
- [ ] DRAFT status
- [ ] PR URL recorded here: TBD

---

## Rollback log (records of any phase reset)

(none yet)
