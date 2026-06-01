# JARVIS Prime / Hermes Runtime — Mass-PR Integration Audit

> **Stale baseline (2026-05-26).** This audit classifies the PR #131 wave
> against `main` at `bc97e43`; `main` has since advanced ~211 commits and most
> of this work has landed. Current launch readiness lives in
> [`docs/launch/LAUNCH_STATUS_CURRENT.md`](docs/launch/LAUNCH_STATUS_CURRENT.md)
> and the full audit in
> [`docs/audits/CODEBASE_AUDIT_2026-06-01.md`](docs/audits/CODEBASE_AUDIT_2026-06-01.md).

**Generated:** 2026-05-26
**Branch:** `claude/hopeful-bardeen-KBVqi`
**Base SHA:** `bc97e43` (`origin/main` at audit time)
**Plan:** see `/root/.claude/plans/mission-you-are-idempotent-bunny.md`
**Scope (owner-confirmed):** all 53 in-scope open PRs (28 JARVIS Prime stack + 25 older Phase orchestration)

> This audit is committed **before** any merge or cherry-pick so the
> classification is reviewable. It is the source of truth for what gets
> integrated, in what order, with what verdict.

## Verdict legend

| Verdict | Meaning |
|---------|---------|
| `MERGE` | Will be merged or cherry-picked into the integration branch |
| `MERGE-FIRST` | Foundation; must land before other PRs in its phase |
| `MERGE-EARLY` | Base structure; must land before feature PRs |
| `MERGE-LAST` | Cleanup; lands after all features integrate |
| `MERGE-SPLIT` | Multiple feature commits split across phases |
| `MERGE-PARTIAL` | Cherry-pick selected files only (overlap resolution) |
| `MERGE-DOCS` | Documentation only, no runtime risk |
| `SUPERSEDED-BY-#NNN` | Functionally replaced by another PR; documented, not merged |
| `REJECT-dupe` | Bot-regenerated duplicate; documented, not merged |
| `DEFER` | Held for owner decision before merging |
| `DEFER-LATER-PASS` | Older Phase orchestration; re-evaluated in Phase 6 of plan |
| `SKIP-OUT-OF-SCOPE` | Not in scope (closed, draft of another lane, etc.) |

## Critical structural finding

**41 of the 53 in-scope branches have no merge-base with current `main`.**
They start with a `chore(<area>): import baseline from main` snapshot
commit that, if applied today, would delete ~93,000 lines including
`.github/workflows/android-build.yml` and `.github/workflows/orchestration-tests.yml`.

**Integration rule:** for orphan branches, cherry-pick **only the feature
commit(s) on top of the baseline-import commit** — never the baseline-import
commit itself. After every orphan cherry-pick, run
`git checkout HEAD~1 -- .github/ .claude/ agents/ recovered-agent-sources/`
to restore anything the cherry-pick wrongly touched outside the feature's
intended path.

## JARVIS Prime stack (28 PRs)

| PR | Title | Base | Verdict | Feature SHA(s) | Notes |
|----|-------|------|---------|----------------|-------|
| #129 | Jarvis Prime home screen as command center | `bc97e43` | `MERGE` | `36fc226` | Wins `HomeScreen.kt` vs #125/#126; aggregates HermesService + repos into JarvisHomeState |
| #128 | Close launch-readiness blockers (docs · backup · tests · CI) | `bc97e43` | `MERGE-LAST` | `516c04d` | Rewrites README, adds `unit-tests` CI job, fixes backup rules, drops stale `hermesGatewayUrl` |
| #127 | Align Android app to JARVIS Prime Gateway Event Spine | ORPHAN | `DEFER` | `e2690a4` | 378-file orphan; overlaps with existing Hermes gateway plugin; owner Q5 |
| #126 | Jarvis Prime mobile command center | ORPHAN | `SUPERSEDED-BY-#125` | — | Foundation contained in #125's full integration |
| #125 | Jarvis Prime full app integration | ORPHAN | `MERGE-PARTIAL` | `fef396b` + `7c22b4e` | Cherry-pick uncontested files only; #129 wins HomeScreen |
| #124 | JARVIS Prime capability UI | ORPHAN | `MERGE` | `ccbad67` | New route in #112's shell |
| #123 | JARVIS Prime voice capture — Phase 1 | `bc97e43` | `DEFER` | (clean-base PR) | Likely adds `RECORD_AUDIO` permission; owner Q4 required |
| #122 | JARVIS Prime memory transparency screen | `bc97e43` | `MERGE` | `637102f` | Clean-base merge |
| #121 | Jarvis Prime cockpit launch-demo polish | ORPHAN | `MERGE` | `7d3a8d9` | Must land AFTER #113 design tokens |
| #120 | Jarvis Prime emergency stop — visible, audited, app-wide | ORPHAN | `MERGE` | `621b07e` | Must land BEFORE #128 README rewrite |
| #119 | Jarvis Prime interactive icon — in-app only | ORPHAN | `MERGE` | `f7782bb` | |
| #118 | JARVIS Prime Audit & Proof History screen | ORPHAN | `MERGE` | TBD (branch tip `12f8b47`) | Resolve feature SHA at execution time |
| #117 | Jarvis Prime chat screen | ORPHAN | `MERGE` | `af1331d` | Verify no conflict with #129 routes |
| #116 | Jarvis Prime task and worker command cards | `bc97e43` | `MERGE` | `d558410` | Clean-base merge |
| #115 | Jarvis Prime control and settings surfaces | `bc97e43` | `MERGE` | `8248cdb` | Clean-base merge |
| #114 | Jarvis Prime Social Intelligence — Memory screen + privacy boundary | ORPHAN | `MERGE` | `4a9a051` | Verify privacy boundary code preserved |
| #113 | Jarvis Prime visual identity + design system | ORPHAN | `MERGE-EARLY` | `8478240` | Foundation; design tokens that downstream PRs reference |
| #112 | Jarvis Prime navigation shell (10 routes + emergency stop) | ORPHAN | `MERGE-EARLY` | `249f7f5` | Lands first; converts 5→10 routes |
| #111 | JARVIS Prime APK launch readiness audit — verdict RED | `bc97e43` | `MERGE-DOCS` | `7919e56` | Reference artefact (1 file) |
| #110 | Deep audit of Android app before Jarvis Prime rebrand | `bc97e43` | `MERGE-DOCS` | `82bf452` | Reference artefact (5 files) |
| #109 | Jarvis Prime onboarding + Python logging redaction | ORPHAN | `MERGE-SPLIT` | `5bf1eb7` (Android), `bbfc6ed` (Python), `d687a8a` (CodeQL fix) | Python redaction is security-critical; lands in Phase 1 |
| #108 | Jarvis Prime Android app product specification | `bc97e43` | `MERGE-DOCS` | `fbbfae4` | Reference artefact (5 files) |
| #107 | Jarvis Prime approval system UI | `bc97e43` | `MERGE` | `b82b6e2` | Clean-base merge |
| #106 | Jarvis Prime notifications command center | ORPHAN | `MERGE` | `abde9b9` | Verify `POST_NOTIFICATIONS` is runtime-requested |
| #105 | Wire CLI proposals + handoff subcommands (Wave 1 CLI lane) | ORPHAN | `MERGE` | `52d5f1b` | 4-file feature delta; Phase 1 |
| #104 | Add WorkPacket schema + canonical repo + wave plan | `bc97e43` | `MERGE-FIRST` | `e3e62ba` | Foundation; purely additive (5 files, +657 lines) |
| #103 | Wave 0 foundation lock — canonical repo, wave plan, WorkPacket | `bc97e43` | `SUPERSEDED-BY-#104` | — | 11 files vs #104's curated 5; #104 is human-authored survivor |

## Wave 0 duplicate cluster (10 PRs, all `REJECT-dupe`, all `SUPERSEDED-BY-#104`)

Bot-regenerated duplicates of #104. Documented for owner reference; cannot
be closed by this integration (safety rule).

| PR | Branch | Verdict |
|----|--------|---------|
| #102 | `claude/jarvis-foundation-lock-FO3ej` | `REJECT-dupe` (`SUPERSEDED-BY-#104`) |
| #101 | `claude/jarvis-foundation-lock-aX4Fs` | `REJECT-dupe` (`SUPERSEDED-BY-#104`) |
| #100 | `claude/jarvis-foundation-lock-zVaul` | `REJECT-dupe` (`SUPERSEDED-BY-#104`) |
| #99  | `claude/jarvis-foundation-lock-cL37G` | `REJECT-dupe` (`SUPERSEDED-BY-#104`) |
| #98  | `claude/jarvis-foundation-lock-g9i9x` | `REJECT-dupe` (`SUPERSEDED-BY-#104`) |
| #97  | `claude/jarvis-foundation-lock-TVECb` | `REJECT-dupe` (`SUPERSEDED-BY-#104`) |
| #96  | `claude/jarvis-foundation-lock-i7Uag` | `REJECT-dupe` (`SUPERSEDED-BY-#104`) |
| #95  | `claude/jarvis-foundation-lock-467r2` | `REJECT-dupe` (`SUPERSEDED-BY-#104`) |
| #94  | `claude/jarvis-foundation-lock-Lrlbn` | `REJECT-dupe` (`SUPERSEDED-BY-#104`; claims "Wave 0 + Wave 1") |
| #93  | `claude/jarvis-foundation-lock-cDOTP` | `REJECT-dupe` (`SUPERSEDED-BY-#104`) |

## Older Phase orchestration PRs (25 PRs, default `DEFER-LATER-PASS`)

All 25 PRs have orphan history vs current `main` (~775-1009 file diffs).
JARVIS Prime runtime v1.0.0 (commit `45a11b0`, 18 modules + 159 tests) and
decision-ledger fix (#92) already landed on main. Most of these older PRs
were authored before those landings and are likely partly or fully
superseded. Default verdict: **`DEFER-LATER-PASS`** — re-evaluated in
Phase 6 (after JARVIS Android stack lands and verifies).

| PR | Title | File-diff vs main | Verdict |
|----|-------|-------------------|---------|
| #84 | Phase 25 CI + test hardening | 812 | `DEFER-LATER-PASS` |
| #82 | Phase 06 — Model/tool registry and routing engine | 814 | `DEFER-LATER-PASS` |
| #72 | AI improvement radar + post-job learning loop (Phase 22) | 809 | `DEFER-LATER-PASS` |
| #70 | Phase 15: validation + monitoring loops | 813 | `DEFER-LATER-PASS` |
| #69 | Phase 12: phase-based job controller | 813 | `DEFER-LATER-PASS` |
| #68 | Structured decision ledger and explainability | 814 | `DEFER-LATER-PASS` (likely superseded by #92) |
| #67 | Phase 09: multi-agent isolated worker spawning | 786 | `DEFER-LATER-PASS` |
| #64 | Phase 16: secrets + approval policy for autonomous agent | 805 | `DEFER-LATER-PASS` (likely overlaps with `owner_auth.py`) |
| #63 | Phase 17: GitHub, Supabase, Vercel adapter layer | 775 | `DEFER-LATER-PASS` |
| #62 | Finish phase 11 worker adapter set | 815 | `DEFER-LATER-PASS` |
| #61 | Phase 21 phone-first backend service runtime | 811 | `DEFER-LATER-PASS` |
| #60 | Phase-gated workflow engine | 807 | `DEFER-LATER-PASS` (likely superseded by `gates.py`) |
| #58 | Phase 07: persistent user profile from GitHub history | 782 | `DEFER-LATER-PASS` |
| #57 | Phase 13: parallel runner with approval gating and resume | 810 | `DEFER-LATER-PASS` |
| #55 | Phase 03: harden orchestrator foundation + full job folder | 819 | `DEFER-LATER-PASS` |
| #54 | Phase 8: integrate orchestration files | 828 | `DEFER-LATER-PASS` |
| #43 | Phase 24: Release hardening + 10/10 final gate | 917 | `DEFER-LATER-PASS` |
| #42 | Phase 21: feature harvest of competing AI agents | 911 | `DEFER-LATER-PASS` (docs only — candidate for early salvage) |
| #41 | Native slash commands for local orchestration | 912 | `DEFER-LATER-PASS` |
| #39 | Port AoS council agents to Hermes-native skills | 900 | `DEFER-LATER-PASS` |
| #38 | Local validation gates (Phase 14) | 908 | `DEFER-LATER-PASS` |
| #36 | Phase 18: APK cockpit spec, API contract, wireframes, Termux bridge | 906 | `DEFER-LATER-PASS` (likely already on main as `CockpitApi.kt` baseline) |
| #32 | Executable runtime for branch/commit/PR plan (github-publisher) | 909 | `DEFER-LATER-PASS` |
| #17 | Phase 7 job controller + worker adapter roadmap | 908 | `DEFER-LATER-PASS` |
| #4 | Android real E2E direct API test, 3-card onboarding | 1009 | `DEFER-LATER-PASS` (predates JARVIS Prime; likely fully superseded) |

## Owner-gated decisions required during integration

These will be surfaced via `AskUserQuestion` when reached. Pre-written
templates are in the plan file under "User-pause points".

| Q# | Trigger | Question |
|----|---------|----------|
| Q1 | Before Phase 0 audit-commit push | Promote/demote any PR before merging begins? |
| Q2 | After #112 nav-shell cherry-pick | Confirm 5→10 route shell migration |
| Q3 | On unexpected `Screen.kt` / `HermesNavGraph.kt` conflict | Resolution ordering |
| Q4 | Before #123 | RECORD_AUDIO permission disposition |
| Q5 | Before #127 | Gateway event spine disposition |
| Q6 | Pre-Phase 5 | HomeScreen overlap resolution (#125 vs #129) |
| Q7 | Pre-Phase 6 | Older Phase PR disposition |
| Q8 | Any non-additive change to owner_auth/gates/emergency-stop | Confirm intent preserved |
| Q9 | Pre-final-PR open | Push and open draft PR? |

## Verification (CI gates required green before final PR)

- `tests.yml` — pytest with `-n auto --timeout=30 --timeout-method=signal`
- `lint.yml` — ruff (PLW1514 blocking) + ty
- `orchestration-tests.yml` — orchestrator-specific pytest
- `android-build.yml` — `./gradlew --no-daemon --stacktrace assembleDebug`
- `unit-tests` — Android unit tests (added by #128)
- `uv-lockfile-check.yml` — `uv lock --check`
- `windows-footguns` — `scripts/check-windows-footguns.py --all`

## Out of scope (will not touch)

- Closing any duplicate or superseded PR (safety rule; recommend in final-PR body)
- Deleting any branch (safety rule)
- Pushing to `main` (safety rule; final action is opening a draft PR)
- Force-pushing over any branch other than `claude/hopeful-bardeen-KBVqi`
- Restricted Android permissions without explicit owner authorization
- Removing any safety gate, owner approval gate, emergency stop logic,
  redaction logic, or permission education copy
- Modifying the canonical `AUTHORIZATION_PHRASE = "Yes, with authorization."`
- Modifying `OWNER_GATED_ACTIONS` frozenset except by additive extension
