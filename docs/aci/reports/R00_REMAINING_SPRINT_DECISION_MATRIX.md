# R00 — Remaining Sprint Decision Matrix (LOCK)

**Companion to:** `R00_CURRENT_LAUNCH_STACK_AUDIT.md`.
**Snapshot:** 2026-05-26, after PR #152 merged.
**Branch:** `aci/r00-launch-stack-audit-lock`.
**Purpose:** Source-of-truth for what the remaining sprint may and
may not do, so subsequent prompts do not duplicate, overlap, fight,
or undo the existing PRs in flight.

---

## A. Headline facts (read first)

1. **PR #152 merged.** Current `main` is `576c334` (which itself
   merged PR #151 atop `69a87b4` = PR #152's merge).
2. **The current launch stack must be refreshed after PR #152.**
   PR #131 and every PR chained off it (#142, #143, #147, #149,
   #150) was authored against the pre-#152 `main` (`bc97e43`) or its
   downstream tip `d0caf92`. None of them have absorbed #152's 68
   files / +24,279 / 13 commits or PR #151's `onboarding.py` +
   `skills_tool.py` fixes.
3. **PR #153 is the independent security follow-up.** It targets
   `main` directly, GitHub already records its base as `576c334`,
   and its 6-file scope (`agent/file_safety.py`, `agent/redact.py`,
   3 new test files, 1 test extension) is **disjoint** from
   anything in the launch chain. It is *not* a launch-stack PR.
4. **There is exactly one Android app.** It lives at
   `apps/android/`. **Do NOT create `mobile/jarvis-prime-android`,
   `apps/jarvis-prime-android`, `mobile/`, or any second Android
   module.** Every Android surface the sprint needs already lives
   (or is staged to live) inside `apps/android/`.

---

## B. PR-by-PR decision matrix

| PR | State | Decision for the remaining sprint | Why |
|---|---|---|---|
| **#131** | open, NOT merged, owner-gated by its own body | **HOLD until owner authorizes + rebase onto `main`.** Do not modify the head branch from any sprint agent. Do not self-merge. | Mass integration of 18 PRs; #123 voice + #127 spine deferred; AUTHORIZATION_PHRASE required. |
| **#142** | open, clean | **HOLD.** Targets #131 head; will rebase after #131 lands. Do not modify. | Wires audit model + SettingsRepository fields so the Android module compiles against #131. |
| **#143** | open, clean | **HOLD.** Already contains #142 cherry-picked; rebases after #131 + #142 land. Do not modify. | Assembles eight launch lanes onto #131 head. |
| **#147** | open, unstable | **HOLD.** Chains off #143; rebase after #143 lands. Do not modify. | Living-avatar + JarvisLive command screen. No new permissions. |
| **#149** | open, unstable | **HOLD.** Chains off #147; rebase after #147 lands. Reconcile with older `launch/jarvis-avatar-picker` per owner decision. Do not modify. | On-device avatar picker (no media permissions). |
| **#150** | open, clean | **HOLD or rebase to `main` per owner.** LaunchGate policy + workflow. Currently rooted on #131 head; can be rebased to land directly on `main`. If un-bundled, treat as Phase A. | Replaces manual `Yes, with authorization.` phrase for repo merges; preserves all runtime owner gates. |
| **#151** | MERGED | **NO ACTION.** Already in `main`. | Pytest unblockers (skill discovery + onboarding email extraction). |
| **#152** | MERGED | **NO ACTION on the PR itself.** Treat as the new baseline. Subsequent sprint PRs branch from current `main`. | Personal → ACI reconciliation; 61 ported files + reconciliation artefacts. |
| **#153** | open, draft | **REVIEW.** Independent security follow-up to #152 (§17 bucket 1). Already targets new `main` (`576c334`). 155 passed, 1 skipped. Owner reviews and un-drafts. | `agent/file_safety` superset + `agent/redact` HTTP access-log redactor + tests. |

---

## C. Sprint-allowed work envelope

Every remaining sprint prompt must:

1. **Branch from current `origin/main`** at the moment of execution
   (re-fetch; do not pin to a stale SHA).
2. **Be docs-only by default** — every R0x prompt in
   `R00_CURRENT_LAUNCH_STACK_AUDIT.md §15` is docs-only.
3. **Restrict ALLOWED FILES** to its own report under
   `docs/aci/reports/` (or its own explicitly-named output paths).
4. **Forbid every path in §D below.**
5. **Open a draft PR only.** No auto-merge. No deploy. No
   credential change. No package publish. No app-store submission.
   No DNS change. No public posting. No money action.
6. **No secrets** in code, logs, docs, tests, screenshots,
   fixtures, or reports.
7. **End every run with the same envelope:** changed files, tests
   run, risks, rollback plan, draft PR summary.

If a needed change is outside the prompt's ALLOWED FILES, **do not
edit it.** Document the need and stop.

If another open branch/PR touches the same allowed files, **stop
and write a collision report** — do not proceed.

---

## D. Do-NOT-touch paths (sprint-wide)

These are off-limits to remaining-sprint agents without explicit
owner direction (full list mirrors `R00_CURRENT_LAUNCH_STACK_AUDIT.md
§13`):

- **`apps/android/**`** — owned by the launch chain. **Do not
  create a duplicate Android module.** The product name is **muse
  Prime**; the canonical app is at `apps/android/`.
- **`apps/android/app/src/main/AndroidManifest.xml`** — locked at
  3 permissions (`POST_NOTIFICATIONS`, `FOREGROUND_SERVICE`,
  `FOREGROUND_SERVICE_DATA_SYNC`). Triple-pinned by launch-chain
  tests. Forbidden: SMS, Call Log, overlay, camera, location,
  media, always-listening, `RECORD_AUDIO` (the last is owner-gated
  via #123). Optional permissions must remain optional; the app
  must still work if denied.
- **`hermes_cli/jarvis_prime/owner_auth.py`** —
  `AUTHORIZATION_PHRASE` and `OWNER_GATED_ACTIONS` are byte-locked.
- **`hermes_cli/jarvis_prime/router.py`** — owned by #150.
- **`.github/workflows/launch-gate.yml`** — owned by #150.
- **`claude/hopeful-bardeen-KBVqi`** (#131 head) and every
  `launch/*` branch — do not push from non-launch-chain agents.
- **`claude/amazing-volta-nXCqM`** (#153 head) — owned by the
  reconciliation follow-up; do not push from R00 / other sprint
  branches.
- **`claude/hermes-aci-reconciliation-84ART`** (#152 head, merged)
  — do not push; PR closed.
- **`agent/redact.py`, `agent/file_safety.py`,
  `tests/agent/test_file_safety*.py`,
  `tests/agent/test_redact.py`** — owned by #153 until it merges
  or closes.
- **`.claude/agents/**`, `recovered-agent-sources/**`,
  `AOS_*.md` (at repo root), `MERGE_STRATEGY.md`, `CLAUDE.md`,
  `SETUP.md`** — ACI canonical sources; do not regress with
  personal versions.
- **Runtime files under `~/.hermes/` and any real secret store**
  — never write into a repo file, fixture, or test. Never embed
  Python runtime inside the APK. Never store gateway-side secrets
  in Android.

---

## E. Global product rules (binding for every sprint prompt)

- **Product-facing name is muse** Hermes can remain only
  for backend/runtime/package compatibility.
- **Android is the muse body/control surface**, not the
  full AI brain. Backend/runtime/gateway/muse remains in
  Hermes/muse backend code.
- **Do not embed Python runtime inside the APK.**
- **Do not store gateway-side secrets in Android.**
- **No SMS, Call Log, overlay, camera, location, media, or
  always-listening behavior.**
- **No automatic notification permission prompt on first launch.**
- **Microphone permission only after user taps voice and only if
  the explicit voice wave authorizes it.** (PR #123 is owner-gated
  for exactly this reason.)
- **Optional permissions must be optional.** App must still work
  if denied.

---

## F. Phase plan (operational rollup)

### Phase A — independent / land-now (no #131 dependency)

| Step | PR | Action | Gate |
|---|---|---|---|
| A1 | #153 | Owner reviews; un-draft; standard owner-gate merge to `main`. | Owner authorization phrase + CI green. |
| A2 (optional) | #150 | Owner approves un-bundling; rebase from `claude/hopeful-bardeen-KBVqi` onto `main`; resolve any conflicts; CI green; merge. | Owner authorization phrase + CI green. |

### Phase B — launch chain (#131-gated)

| Step | PR | Action | Gate |
|---|---|---|---|
| B1 | #131 | Rebase onto `main` (`576c334`); resolve conflicts per §11 of audit; CI green. | Owner authorization phrase. |
| B2 | #131 | Merge to `main`. | Owner authorization phrase + branch-protection reviewer + LaunchGate (if #150 already in place) or current OwnerAuth. |
| B3 | #142 | Rebase onto new `main`; CI green; merge. | Same. |
| B4 | #143 | Rebase onto new `main`; absorb cherry-picked #142; CI green; merge. | Same. |
| B5 | #147 | Rebase onto new `main`; CI green; merge. | Same. |
| B6 | #149 | Rebase onto new `main`; reconcile with older `launch/jarvis-avatar-picker` per owner; CI green; merge. | Same. |

### Phase C — owner-deferred (case-by-case)

| Step | PR | Action | Gate |
|---|---|---|---|
| C1 | #123 | Owner decides on voice / `RECORD_AUDIO`. If approved, mic permission is requested only after user taps voice. | Owner authorization phrase + product-rule compliance. |
| C2 | #127 | Owner decides on gateway event spine. | Owner authorization phrase + architecture review. |

### Phase D — follow-up reconciliation buckets

Once Phase A/B settle, address the remaining buckets from #152 §17
that #153 did not cover:

| Bucket | Notes |
|---|---|
| `tools/file_tools.py` pre-resolve | Un-skips the one #153 test. |
| `.github/workflows/docker-lint.yml`, `skills-index-freshness.yml` | LaunchGate review. |
| `website/` (339 files) | Website-only PR. |
| `docker/` s6 supervision + `Dockerfile` delta | Paired Docker-only PR. |
| Other deferred personal-only buckets | Per #152 coverage matrix. |

---

## G. Quick reference — what NOT to do this sprint

- ❌ Do **not** create `mobile/jarvis-prime-android` or any second
  Android module. The canonical app is `apps/android/`.
- ❌ Do **not** modify `apps/android/**` in a remaining-sprint
  prompt — owned by #131 + chain.
- ❌ Do **not** modify `hermes_cli/jarvis_prime/owner_auth.py`
  constants — byte-locked.
- ❌ Do **not** push to any `claude/*` or `launch/*` branch owned
  by another PR.
- ❌ Do **not** add `RECORD_AUDIO`, `CAMERA`, location, media, SMS,
  Call Log, overlay, or always-listening permissions to the
  Android manifest.
- ❌ Do **not** auto-merge any PR. Drafts only.
- ❌ Do **not** self-authorize the owner-gate ceremony for #131 or
  the final main-merge. Owner gives the literal phrase.
- ❌ Do **not** re-do PR #152 (it is merged) or re-do PR #153 (it
  is in flight). New work goes in new follow-up PRs per #152 §17.
- ❌ Do **not** port stale personal files that regress newer ACI
  architecture (AOS docs, `.claude/agents/`, Android skeleton,
  `MERGE_STRATEGY.md`, `CLAUDE.md`, `SETUP.md`).
- ❌ Do **not** commit secrets, tokens, API keys, credentials,
  private keys, or live env values in any artefact (code, logs,
  docs, tests, fixtures, screenshots, reports).

---

## H. Quick reference — what the sprint MAY do

- ✅ Open small, well-scoped, docs-only draft PRs under
  `docs/aci/reports/R0x_*.md` per the R01–R07 list in
  `R00_CURRENT_LAUNCH_STACK_AUDIT.md §15`.
- ✅ Produce rebase recipes for each stale launch-chain PR (R01,
  R03, R04).
- ✅ Produce owner-facing decision packets for #123 (voice) and
  #127 (spine) (R05).
- ✅ Track the remaining #152 follow-up buckets (R06).
- ✅ Produce the final launch go/no-go packet (R07).
- ✅ Branch from current `main` at execution time, push to the
  prompt's named branch, open a draft PR, end with the standard
  envelope.

---

## I. End-state acceptance criteria for the rest of the sprint

The remaining sprint is complete when:

1. PR #153 is reviewed and either merged or closed with a
   documented reason.
2. PR #150 has either landed (Phase A2) or has a documented
   reason it stays bundled with #131.
3. PR #131 has been rebased onto current `main`, owner-authorized,
   green on CI, and merged.
4. PRs #142, #143, #147, #149 have all been rebased onto post-#131
   `main`, green on CI, and merged in order.
5. Owner has issued explicit decisions on #123 (voice) and #127
   (spine).
6. The launch chain CI is green end-to-end against the new `main`.
7. A final go/no-go packet (R07) has been delivered to the owner
   and the launch-readiness verdict is **GREEN**.
8. No second Android module exists. `apps/android/` remains the
   only Android app.
9. No new permission appears in `AndroidManifest.xml` outside the
   three-permission allowlist (unless the owner approved #123 and
   it shipped exactly as scoped).
10. Every PR opened during the sprint is either merged or closed
    with a written rationale (no stray drafts).

---

_End of R00 sprint decision matrix._

---

## RESOLUTION ADDENDUM — 2026-06-10

> **Append-only.** Nothing above this line has been edited (no-silent-ledger-change
> rule). Every **HOLD** instruction in §B and the Phase B plan in §F are
> **SUPERSEDED BY THIS ADDENDUM** — the original lines stand verbatim as the
> historical record of the 2026-05-26 decision state.

**Authored by:** SYNAPSE P1 lane, ticket **P1-04**
(`docs/synapse/phase0/P1_CLAIMS_AUDIT.md` §3 and §5).

### 1. Outcome

The held chain **#131 → #142 → #143 → #147 → #149 → #150** is **RESOLVED — LANDED
on `main`**, together with the independent security follow-up **#153**. The §I
acceptance criteria covering the chain (items 3, 4) are satisfied; #151/#152
remain MERGED exactly as §A/§B already recorded.

### 2. Evidence constraint — why merge commits are unobservable

Git history on `main` is **truncated to 87 visible commits**; the oldest visible
commit is `ba2c12d` ("Wave B — 10/10 program ledger (#374)"). A grep for
`#131|#142|#143|#147|#149|#150` across all branches returns **zero merge
commits** — the chain predates the visible (squashed/truncated) history. Landing
is therefore proven by **artifacts on `main`** plus the in-repo launch-status
record, not by merge commits. This addendum freezes that artifact→PR map so no
future audit has to re-derive it.

### 3. Artifact → PR evidence map (condensed from P1_CLAIMS_AUDIT.md §3)

| PR | R00 role (§B above) | Status | Artifact evidence on `main` |
|---|---|---|---|
| **#131** | Mass integration trunk of 18 PRs; owner-gated | **LANDED** | Integrated Android module + `hermes_cli/jarvis_prime/` runtime present and iterated on by later visible merges (#404, #415, #423, #434–#444); `docs/launch/LAUNCH_STATUS_CURRENT.md` lists the #131 workstreams (worker engine, orchestrator replay, cockpit↔ledger bridge, Android rebrand, chat screen) as all landed |
| **#142** | Audit model + SettingsRepository fields | **LANDED** | `apps/android/.../ui/screens/audit/AuditViewModel.kt`, `AuditDetailViewModel.kt` (wired in `di/AppContainer.kt:51-52`); extended `SettingsRepository.kt` (:409-441) |
| **#143** | Eight launch lanes assembled onto #131 head | **LANDED** | Lane plan + completion record in `docs/launch/LAUNCH_BRANCH_MATRIX.md:4,21-22`; lane deliverables (chat screen, interactive icon, rebrand) on `main` per `LAUNCH_STATUS_CURRENT.md` |
| **#147** | Living avatar + JarvisLive command screen | **LANDED** | `apps/android/.../ui/screens/live/JarvisLiveScreen.kt`, `JarvisPhotoAvatar.kt`, `JarvisRiveAvatar.kt` + 5 test classes; re-skin merged as visible commit `2d72616` (#415) |
| **#149** | On-device avatar picker | **LANDED** | `apps/android/.../ui/screens/avatar/AvatarPickerScreen.kt`, `AvatarPickerViewModel.kt`, `data/avatar/` (4 test classes); maintained via visible commit `7985f3c` (#404) |
| **#150** | LaunchGate policy + workflow | **LANDED** | `.github/workflows/launch-gate.yml`; `hermes_cli/jarvis_prime/router.py`; hardened by visible commit `4afc2fc` (HERMES_RELEASE_GATE_STRICT, merged via `a26eb80` #435) |
| #151, #152 | Pre-merged baseline (§A.1-2) | MERGED | Per §B above (unchanged) |
| **#153** | Independent security follow-up | **LANDED** | `agent/redact.py`, `agent/file_safety.py`, `tests/agent/test_redact.py`, `tests/agent/test_file_safety*.py` all on `main` |

### 4. Owner decision trail

- **Launch verdict:** `docs/launch/LAUNCH_STATUS_CURRENT.md` (2026-06-01, base
  `084c132`) — **GREEN** on everything runnable in-repo; the prior "RED — 52%"
  verdict declared obsolete; `docs/launch/LAUNCH_BRANCH_MATRIX.md:4` records lane
  execution complete, 211 commits past the `bc97e43` baseline.
- **B6 permission-surface accept (2026-06-01):** the "Sentient muse avatar"
  feature (#170) expanded the Android permission surface beyond §D's
  "locked at 3 permissions" rule. The owner reviewed this (audit §5 B6,
  `LAUNCH_STATUS_CURRENT.md:13-16`) and **ACCEPTED ship-as-is**. §D's manifest
  lock and §E's "no overlay/camera/always-listening" rules are therefore also
  overtaken by that explicit owner decision — recorded here, not edited above.
- **Open follow-ups (recommended, not gating):** runtime consent surface, Play
  data-safety declarations, privacy disclosure — tracked as ticket **P1-05** and
  listed as OPEN owner-decision items in `LAUNCH_STATUS_CURRENT.md`.

### 5. Effect on this matrix

This matrix is **historical** from this line down to readers of the future: do
not execute §B HOLDs, §C's sprint envelope, or §F Phases A/B — they completed.
Current readiness lives in `docs/launch/LAUNCH_STATUS_CURRENT.md`; the claims
audit that produced this addendum lives at
`docs/synapse/phase0/P1_CLAIMS_AUDIT.md`.

_End of resolution addendum (2026-06-10)._
