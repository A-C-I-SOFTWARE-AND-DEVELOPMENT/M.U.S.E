# R00 — Current MUSE Launch-Stack Audit (LOCK)

**Snapshot taken:** 2026-05-26 (after PR #152 merged to `main`).
**Audit branch:** `aci/r00-launch-stack-audit-lock`.
**Audit scope:** docs only. No source changes. No merges. No deploys.
**Mission:** Lock the current launch-stack state so the remaining
sprint does not duplicate, overlap, or fight existing PRs.

---

## 1. Current `main` SHA

| Ref | SHA | Note |
|---|---|---|
| `origin/main` (now) | `576c334` | Merge of PR #151 (skill discovery + onboarding email fixes). |
| `main` one commit ago | `69a87b4` | Merge of **PR #152** (personal → ACI reconciliation, 68 files, +24,279). |
| `main` two commits ago | `bc94cff` | Pre-#152 baseline. |
| `main` long-stale | `bc97e43` | The base PR #131 (and the entire downstream launch chain) is still branched from. |

> **The new `main` has moved 2 PRs (#152, #151) ahead of the launch
> chain's base.** Anything that targets `claude/hopeful-bardeen-KBVqi`
> (PR #131 head) or anything chained off it is now stale relative to
> `main`.

---

## 2. PRs that target `main`

| PR | Title | State | Base | Head | Notes |
|---|---|---|---|---|---|
| **#131** | MUSE + Hermes runtime — 53-PR mass integration | open, NOT merged | `main` (`bc97e43`) | `claude/hopeful-bardeen-KBVqi` (`d0caf92`) | Body explicitly says **owner-gated** — treat as owner-gate even though GitHub `draft=false`. |
| **#150** | LaunchGate automated merge policy | open | `claude/hopeful-bardeen-KBVqi` (NOT `main` directly — sibling of #143, still routes through #131 to reach main) | `launch/launch-gate-auto-merge` (`ba439da`) | Sibling of the candidate chain; rides #131. |
| **#152** | Reconcile echerd27 personal enhancements into ACI Hermes | **MERGED** 2026-05-26 23:08:05Z by `echerd27-design` | `main` | `claude/hermes-aci-reconciliation-84ART` | Landed as commit `69a87b4`. 68 files, +24,279/−2. |
| **#153** | Reconcile follow-up: agent/file_safety + agent/redact hunk ports | open, draft | `main` (`576c334` — picked up the new tip automatically) | `claude/amazing-volta-nXCqM` (`72573f5`) | Independent security follow-up to #152; does NOT depend on the launch chain. |

---

## 3. PRs that target PR #131's branch (`claude/hopeful-bardeen-KBVqi`)

| PR | Title | State | Head |
|---|---|---|---|
| **#142** | fix(android-base): wire missing audit model for PR #131 | open, `mergeable_state=clean` | `launch/base-compile-repair` (`846934a`) |
| **#143** | chore(launch): assemble MUSE launch candidate | open, `mergeable_state=clean` | `launch/jarvis-prime-auto-merge-candidate` (`5a9005d`) — already contains #142 cherry-picked |
| **#150** | LaunchGate automated merge policy | open, `mergeable_state=clean` | `launch/launch-gate-auto-merge` (`ba439da`) — sibling of #143 |

---

## 4. PRs that target PR #143's branch (`launch/jarvis-prime-auto-merge-candidate`)

| PR | Title | State | Head |
|---|---|---|---|
| **#147** | feat(android): living MUSE avatar + live command screen | open, `mergeable_state=unstable` | `launch/jarvis-living-avatar` (`ead15cb`) |

---

## 5. PRs that target PR #147's branch (`launch/jarvis-living-avatar`)

| PR | Title | State | Head |
|---|---|---|---|
| **#149** | on-device avatar picker on the launch candidate | open, `mergeable_state=unstable` | `launch/jarvis-avatar-picker-on-candidate` (`c7a1522`) |

---

## 6. PRs already merged (relevant to this audit)

| PR | Title | Merge commit |
|---|---|---|
| **#151** | fix(tests): unblock skill discovery + onboarding email extraction | `576c334` (current `main` tip) |
| **#152** | Reconcile echerd27 personal enhancements into ACI Hermes | `69a87b4` |

PRs #142, #143, #147, #149, #150 — **all still open, none merged.**

---

## 7. PRs stale because PR #152 changed `main`

**All five launch-chain PRs are now stale relative to `main`.** They
were authored against `bc97e43` (or its downstream tip `d0caf92`),
which is 2 PRs behind the current tip `576c334`.

| PR | Base SHA at PR time | Current `main` SHA | Stale? | Reason |
|---|---|---|---|---|
| #131 | `bc97e43` | `576c334` | **YES — 2 PRs behind** | Has not seen the 68 files / +24,279 / 13 commits #152 landed; has not seen #151's `hermes_cli/jarvis_prime/onboarding.py` + `tools/skills_tool.py` fixes. |
| #142 | branches off `claude/hopeful-bardeen-KBVqi` (= #131 head) | — | **YES — via #131** | Inherits the staleness. |
| #143 | branches off `claude/hopeful-bardeen-KBVqi` | — | **YES — via #131** | Inherits the staleness. |
| #147 | branches off `launch/jarvis-prime-auto-merge-candidate` (= #143 head) | — | **YES — via #143 → #131** | |
| #149 | branches off `launch/jarvis-living-avatar` (= #147 head) | — | **YES — via #147 → #143 → #131** | |
| #150 | branches off `claude/hopeful-bardeen-KBVqi` | — | **YES — via #131** | |

> **Current launch stack MUST be refreshed after PR #152.** Re-base
> PR #131 onto current `main` (`576c334`) first; then every
> downstream branch rebases onto the new #131 tip in order:
> #142 → #143 → #147 → #149, and (sibling) #150 → #131.

PR #153 is **not** in this stale group — it targets `main` directly
and GitHub already records its base as `576c334`. It is an
independent security follow-up to #152, not a launch-chain PR.

---

## 8. PRs safe to merge independently

| PR | Why safe | Caveat |
|---|---|---|
| **#153** | Targets `main` directly. Independent of #131 / launch chain. Scope is `agent/file_safety.py`, `agent/redact.py`, plus three new test files (M-set: 2; A-set: 3). 155 passed, 1 skipped in local validation. Pure-additive. | Still draft; owner reviews before un-drafting. Carries the standard owner-gate convention for repo merge to `main`. |
| **#150** | Touches only `.github/`, `docs/`, and `hermes_cli/jarvis_prime/{owner_auth,router}.py` (router-side wiring + comments). No Android, no runtime gate weakening, no permission change. | **Still bases on `claude/hopeful-bardeen-KBVqi`** — must be rebased to `main` to land independently of #131. After rebase, it is genuinely independent and safe. |

Nothing else in the chain is independently merge-safe — every other
launch PR carries Android changes that depend on #131 landing first
(or on each other in order).

---

## 9. PRs that must be rebased / refreshed before merge

All six launch-stack PRs (#131, #142, #143, #147, #149, #150) need
explicit refresh action before merging. Recommended sequencing:

1. **Rebase #131** onto current `main` (`576c334`). This is the
   single hardest rebase in the stack (164 files, +25,541/−558,
   31 commits) and now overlaps with PR #152's 68 files. Expect
   conflicts in any file touched by both #131 and #152.
2. Once #131 is rebased and green, rebase **#142** onto new #131
   head.
3. Rebase **#143** onto new #142 tip (#143 already contains #142
   cherry-picked, so the merge should absorb cleanly).
4. Rebase **#147** onto new #143 tip.
5. Rebase **#149** onto new #147 tip.
6. **#150** rebases independently onto new #131 tip (or directly to
   `main` if owner accepts the unbundling — see §8).

---

## 10. PRs that must NOT be merged directly to `main`

| PR | Why not |
|---|---|
| #131 | **Owner-gated.** PR body requires the literal authorization phrase `Yes, with authorization.` from `hermes_cli/jarvis_prime/owner_auth.py:AUTHORIZATION_PHRASE`. Also defers #123 (voice / RECORD_AUDIO) and #127 (gateway event spine) to owner decision. Treat as owner-gated regardless of GitHub `draft=false`. |
| #142 | Base is `claude/hopeful-bardeen-KBVqi`, not `main`. Author explicitly says: *"Do not merge this PR into `main`."* |
| #143 | Base is `claude/hopeful-bardeen-KBVqi`. Author explicitly says: *"Do not merge this PR into `main`."* |
| #147 | Chained off #143; depends on #142 → #143 landing first. |
| #149 | Chained off #147; depends on #147 → #143 → #142 landing first. |
| #150 | Currently bases on `claude/hopeful-bardeen-KBVqi`; needs rebase before it can target `main`. Touches the LaunchGate workflow (`.github/workflows/launch-gate.yml`) and `OwnerAuth` — review under standard repo-merge gate. |

---

## 11. Files identified as conflict hot spots

The launch chain (#131 + chain) and PR #152 (now in `main`) touch
overlapping surfaces. Expect rebase conflicts in:

- `apps/android/**` (entire tree) — #131 reshapes the Android module
  on a base that pre-dates several #152 unrelated additions and any
  intermediate Android CI changes. Hottest sub-paths:
  - `apps/android/app/src/main/java/com/aci/hermes/data/preferences/SettingsRepository.kt` — #142 expands.
  - `apps/android/app/src/main/java/com/aci/hermes/data/model/audit/**` — #142 introduces; #143 deduplicates.
  - `apps/android/app/src/main/AndroidManifest.xml` — pinned by three different launch-chain permission tests (must not regress).
  - `apps/android/gradle/libs.versions.toml`, `apps/android/app/build.gradle.kts` — #142 restores `kotlinx-coroutines-test`.
  - `apps/android/app/src/main/res/values/strings.xml` — #142 adds 35+ strings, #143 reconciles further.
- `hermes_cli/jarvis_prime/owner_auth.py` — #150 modifies, #131 ships its frozenset. Any rebase must preserve `AUTHORIZATION_PHRASE` and `OWNER_GATED_ACTIONS` byte-for-byte.
- `hermes_cli/jarvis_prime/router.py` — #150 modifies; #131 may have touched.
- `hermes_cli/` generally — PR #152 added 11 new modules here (`secrets_cli`, `mcp_catalog`, `portal_cli`, etc.). If #131 also has work here, conflicts likely.
- `agent/` — PR #152 introduced `agent/secret_sources/bitwarden.py`, `agent/credential_persistence.py`, `agent/tts_provider.py`, etc. #131 should not touch these (it's an Android integration), but verify.
- `tools/` — PR #152 added `tools/threat_patterns.py`, `tools/computer_use/vision_routing.py`, etc. Verify no #131 overlap.
- `hermes_constants.py` — PR #152 added two additive helpers (`get_optional_mcps_dir`, `secure_parent_dir`). Any #131-side change here will conflict.
- `optional-skills/`, `optional-mcps/`, `skills/` — PR #152 added several. Conflicts likely if #131 touched these dirs.
- **PR #153 hot spots** are disjoint: `agent/file_safety.py`, `agent/redact.py`, `tests/agent/test_file_safety*.py`, `tests/agent/test_redact.py`. The launch chain should not touch these — verify on rebase.

---

## 12. Recommended merge order

Phase A — **independent / safe to land now**:

1. **PR #153** — review and un-draft, then standard owner-gate
   merge to `main`. Confined to `agent/file_safety` + `agent/redact`
   hunk ports + tests. 155 passed, 1 skipped locally.
2. (Optional) **PR #150 rebased to `main`** — if owner accepts
   un-bundling LaunchGate from the launch chain. Adds the
   `LaunchGate aggregate` workflow and policy docs.

Phase B — **launch chain (owner-gated)**:

3. Owner authorizes **PR #131** merge with the literal phrase.
4. Rebase **#131** onto current `main` (`576c334`). Resolve any
   conflicts surfaced by §11. Re-run full CI.
5. Merge **#131** into `main` after owner phrase + green CI +
   reviewer approval.
6. Rebase **#142** onto new `main`; merge.
7. Rebase **#143** onto new `main`; merge (cherry-picked-#142 will
   absorb cleanly if #142 already landed).
8. Rebase **#147** onto new `main`; merge.
9. Rebase **#149** onto new `main`; merge.

Phase C — **owner-deferred** (see §14):

10. Decision on **#123** (voice / RECORD_AUDIO) per global rule
    that microphone permission is only requested after the user
    taps voice.
11. Decision on **#127** (gateway event spine) — 378-file orphan;
    architecture review.

Do not advance Phase B without explicit owner authorization for
#131. Do not advance Phase C without explicit owner direction on
each deferred item.

---

## 13. Do-NOT-touch paths

These paths are governed by other PRs / launch-stack agreements and
must not be modified by remaining-sprint work without explicit owner
direction:

- `apps/android/**` — owned by the launch chain (#131 → #149 + #142,
  #143, #147). **Do not create `mobile/jarvis-prime-android`** —
  there is one canonical Android app at `apps/android/`. Do not
  create a duplicate Android module under any name.
- `apps/android/app/src/main/AndroidManifest.xml` — locked by three
  independent permission tests (lane 3, lane 5, lane 8). No new
  permission additions. The allowed set is exactly:
  - `android.permission.POST_NOTIFICATIONS`
  - `android.permission.FOREGROUND_SERVICE`
  - `android.permission.FOREGROUND_SERVICE_DATA_SYNC`
  Forbidden: `READ_MEDIA_*`, `READ_EXTERNAL_STORAGE`,
  `WRITE_EXTERNAL_STORAGE`, `MANAGE_EXTERNAL_STORAGE`,
  `RECORD_AUDIO`, `SYSTEM_ALERT_WINDOW`, `CAMERA`,
  `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`,
  SMS/Call-log/Always-listening of any kind.
- `hermes_cli/jarvis_prime/owner_auth.py` — `AUTHORIZATION_PHRASE`
  and `OWNER_GATED_ACTIONS` are byte-locked. Only #150 (LaunchGate
  policy) may add comments to this file; the constants themselves
  are immutable here.
- `hermes_cli/jarvis_prime/router.py` — modified by #150; do not
  touch in parallel work without rebase coordination.
- `.github/workflows/launch-gate.yml` — owned by #150; do not
  duplicate.
- `claude/hopeful-bardeen-KBVqi` (PR #131 head) and every
  `launch/*` branch — do not push to these from non-launch-chain
  agents.
- `claude/hermes-aci-reconciliation-84ART` (PR #152 head, already
  merged) — do not push; PR is closed.
- `claude/amazing-volta-nXCqM` (PR #153 head) — owned by the
  reconciliation follow-up agent; do not push from R00 or other
  remaining-sprint branches.
- `agent/redact.py`, `agent/file_safety.py`,
  `tests/agent/test_file_safety*.py`,
  `tests/agent/test_redact.py` — owned by PR #153 until that PR
  merges or closes. Other sprint PRs should not touch these.
- `recovered-agent-sources/**`, `.claude/agents/**`,
  `AOS_*.md` at the repo root, `MERGE_STRATEGY.md`, `CLAUDE.md`,
  `SETUP.md` — ACI canonical sources; do not regress with personal
  versions.
- `~/.hermes/**` runtime files (`.env`, `auth.json`,
  `mcp-tokens/`, etc.) — never write into a repo file or test
  fixture; never commit secrets or live env values; redaction rules
  in `agent/redact.py` are guardrails, not licenses.

---

## 14. Owner-gated decisions

Pending owner direction before they can be actioned:

1. **Repository merge ceremony for PR #131.** The merge of #131 to
   `main` requires the literal authorization phrase `Yes, with
   authorization.` per `hermes_cli/jarvis_prime/owner_auth.py:AUTHORIZATION_PHRASE`.
   Per CLAUDE.md, this is an owner-gated action (main-branch
   merge). No agent can self-authorize this merge.
2. **Voice capture / `RECORD_AUDIO`.** Per global product rules,
   microphone permission is only requested after the user taps
   voice and only if the explicit voice wave authorizes it. PR
   **#123** likely adds `RECORD_AUDIO` — deferred to owner in
   PR #131's body. Owner must authorize before any voice surface
   ships.
3. **Gateway event spine.** PR **#127** is a 378-file orphan; #131
   defers it to owner architecture review. Owner must direct
   whether to revive on the launch stack or close.
4. **Final main merge.** After Phase A (#153, optionally #150) and
   Phase B (the launch chain), the rollup to `main` is the
   final owner-gated act. Branch protection + LaunchGate (#150)
   handle the repo-side checks, but the owner authorization phrase
   still gates the act per current `OwnerAuth` semantics until
   #150 lands and branch protection requires `LaunchGate
   aggregate`.
5. **Reconciliation between `launch/jarvis-avatar-picker` (older,
   pre-candidate, on `bc97e43`) and `launch/jarvis-avatar-picker-on-candidate`
   (PR #149, candidate-integrated).** Either pick one or merge
   their intent. Owner call per #149's body.

---

## 15. Remaining prompts to run (the rest of the sprint)

Suggested per-sprint prompts, all docs-only on isolated branches,
all draft-PR only, all forbidden from touching the do-not-touch
paths in §13:

- **R01 — `aci/r01-pr131-rebase-plan`** — produce the exact rebase
  recipe for PR #131 onto current `main` (`576c334`). Inputs: file
  conflict list from §11, #131's 164-file diff, #152's 68-file
  diff. Output: per-file resolution intent; no source edits.
- **R02 — `aci/r02-pr152-postmerge-audit`** — confirm #152 landed
  cleanly: smoke-test imports of the 11 new `hermes_cli/` modules,
  run the ported tests against current `main`, check that nothing
  on `main` regressed since `69a87b4`.
- **R03 — `aci/r03-pr150-independent-rebase`** — produce the rebase
  recipe and risk note for un-bundling PR #150 from #131 and
  targeting `main` directly. Decision is owner-gated.
- **R04 — `aci/r04-android-launch-chain-flatten`** — produce the
  exact order to land #142 → #143 → #147 → #149 once #131 lands,
  including per-PR rebase recipes and the CI gates that must be
  green at each step.
- **R05 — `aci/r05-pr131-voice-and-spine-decisions`** — assemble
  the owner-facing decision packets for #123 (voice / RECORD_AUDIO)
  and #127 (gateway event spine). No code.
- **R06 — `aci/r06-pr153-followup-tracker`** — list every #152 §17
  follow-up bucket not yet covered by #153 (e.g. `tools/file_tools.py`
  pre-resolve, docker-lint.yml, skills-index-freshness.yml, website
  reconciliation, docker s6) and stage them as separate small PRs.
- **R07 — `aci/r07-final-launch-go-no-go`** — once all upstream
  PRs are green and rebased, produce the owner-facing go/no-go
  packet with the LaunchGate checklist results, secret-scan
  results, permission audit, owner-gate audit, and a one-page
  summary.

Each sprint prompt should:
- branch from current `origin/main` at execution time,
- restrict allowed files to its own report under `docs/aci/reports/`,
- forbid every path in §13,
- open a draft PR only,
- end with the same envelope this report uses (changed files,
  tests, risks, rollback, PR summary).

---

## 16. Final launch-readiness score: **YELLOW**

| Dimension | Status | Reason |
|---|---|---|
| Reconciliation (PR #152) | ✅ GREEN | Merged 2026-05-26 23:08:05Z. |
| Security follow-up (PR #153) | 🟡 YELLOW | Draft, validated locally (155 passed, 1 skipped). Needs owner review. |
| LaunchGate policy (PR #150) | 🟡 YELLOW | Open. Currently chained to #131 base; can be rebased to `main` to land independently. |
| Launch chain rebase (#131 + #142/#143/#147/#149) | 🟠 YELLOW-leaning-RED | **All five PRs are stale relative to `main` after #152.** Each needs an explicit rebase before merge. PR #131 is the single hardest rebase and is also the owner-gate bottleneck. |
| Owner-gated decisions | 🟡 YELLOW | Four open: #131 merge phrase, #123 voice, #127 spine, final-main-merge ceremony. None are auto-resolvable. |
| Android manifest permissions | ✅ GREEN | Locked at the 3-permission allowlist by three independent permission tests in the launch chain; no proposed PR violates the allowlist. |
| Duplicate Android module risk | ✅ GREEN | None proposed. **DO NOT create `mobile/jarvis-prime-android` or any second Android module.** The canonical app is `apps/android/`. |

Overall verdict: **YELLOW** — not RED because the merged work is
clean, PR #153 is well-scoped, and the launch chain is structurally
sound; not GREEN because the entire launch chain still needs a
rebase pass and an owner-gate ceremony before any Android work can
land on `main`.

> Re-rate to GREEN only after Phase A + Phase B of §12 are complete,
> the rebased launch chain is green on CI, and the owner has issued
> all four §14 authorizations.
