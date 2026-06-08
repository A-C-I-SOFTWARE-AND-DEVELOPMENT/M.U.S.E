# Hermes 10/10 — Follow-ups Ledger (audit trail)

**Single-writer.** Per the *Parallel follow-up execution contract* in
[`CLAUDE.md`](../../CLAUDE.md), only the orchestrator session edits this
file. Parallel builder agents write their own snapshot under
[`followups/`](followups/) and never touch this ledger. On resume, read
this file first — it is how state is rebuilt with no context lost.

**Date opened:** 2026-06-05 · **Base:** `main` @ `b32db703` (all six glue-hops merged)

Residual 10/10 follow-ups from [`10_10_PROGRAM_STATUS.md`](10_10_PROGRAM_STATUS.md),
closed in parallel under the contract. Ownership finalized from four read-only
audits → conflict-free partition (no two in-flight tasks shared a writable file).

## Status legend

`planned` → `building` → `in-review` (PR open) → `merged`. Side states:
`blocked` (needs a decision/owner gate), `deferred`.

## Ownership map + outcomes

| Task | Title | Owned files | Risk | Status |
|---|---|---|---|---|
| **FU-1** | Dispatch seam — drain `iter_worker_usage` → `JobStore` (+ adapter passthrough) | `hermes_cli/orchestrator_dispatch.py` + test | additive | **merged → #329** (`c118e200`) |
| **FU-3** | JobStore durability — on-disk event log + restart rebuild | `hermes_cli/job_event_store.py` · `hermes_cli/orchestrator_api.py` · test | **behavior change → owner-gated** | **merged → #330** (`842b0d53`, owner-authorized) |
| **FU-4** | Unified release gate — `doctor --release-gate` | `hermes_cli/release_gate.py` · `hermes_cli/main.py` (doctor block) · test | additive | **merged → #328** (`ca8420ae`) |
| **FU-5** | Supabase status-doc correction (it was already built — 47 tests pass) | `docs/launch/10_10_PROGRAM_STATUS.md` | doc-only | **merged → #327** (`f0592da9`) |

Tracking/governance PR (contract + this ledger): **#326** (merges last).

## Review-driven corrections (orchestrator)

- **FU-1 — default adapter was unsafe.** The first build defaulted a bare shared
  `LocalRuntimeAdapter`; for a multi-worker plan that collides every plain
  worker's `stdout.log`/`stderr.log` in one dir. Corrected to **inline default**
  (per-worker isolation); adapter is caller opt-in. A safe default adapter needs
  a per-worker adapter factory on the runner — **deferred** (old "FU-2").
- **FU-3 — CodeQL path-traversal.** CodeQL flagged caller-supplied `job_id` used
  in the `events.jsonl` path. Fixed by routing `job_id` through the canonical
  `worktrees.sanitize_segment` allow-list (`/` and `..` cannot survive),
  never-raising; added traversal + blank-id regression tests. (`d921a2cb`)

## Honest residuals (not closed by these PRs)

- **Per-job cost still reads 0 live.** FU-1 lands the tested drain seam, but
  there is no live caller of `ParallelRunner` — wiring the server's job
  dispatcher to `run_plan_into_store` is a separate owner decision.
- **Default adapter injection** (old FU-2) deferred — needs a per-worker adapter
  factory on the runner.
- **FU-3 restored-job cost resets to 0** — `JobCost` isn't event-sourced; fine
  for the status/phase/workers/approvals restart gate, a documented follow-up.

## Decision log

- `2026-06-05` — Contract + ledger opened; four read-only audits → disjoint map.
- `2026-06-05` — **Audit A:** no live `ParallelRunner`→`JobStore` caller; cost-drain
  + adapter collapse into one new seam → FU-1.
- `2026-06-05` — **Audit B:** no `job_store.py` (`JobStore` is in `orchestrator_api.py`);
  FU-3 restore-on-boot → owner-gated.
- `2026-06-05` — **Audit C:** unified gate = thin new `release_gate.py` behind
  `doctor --release-gate`; only shared file is `main.py`, edited by no other task → FU-4.
- `2026-06-05` — **Audit D:** Supabase already shipped (47 tests) → FU-5 reduced to a
  doc correction.
- `2026-06-05` — All four built in parallel (worktrees). FU-1 reviewer-corrected;
  FU-3 CodeQL-fixed. **Merged FU-5 (#327), FU-4 (#328), FU-1 (#329)** on green
  (FU-4's only red was the known Android AvatarPicker flake — proven: the
  doc-only sibling PR passed the same Android job at the same time).
- `2026-06-05` — **FU-3 (#330) held for owner authorization** (behavior-changing:
  server boot now restores jobs from disk + writes a new on-disk artifact).
- `2026-06-05` — **FU-3 CodeQL is a verified false-positive.** CodeQL's
  `py/path-injection` flags `job_id` → events-log path, but the code is provably
  safe: `sanitize_segment` reduces `job_id` to a single `[A-Za-z0-9_.-]`
  component (`/` and `..` cannot survive) and `realpath`+`commonpath` re-confirm
  containment. Three canonical mitigations (allow-list, `is_relative_to`,
  `realpath`/`commonpath`) are not recognized by this repo's CodeQL model. The
  readable `jobs/<job_id>/` layout is **kept** (a hash-dir redesign would clear
  the FP but worsen on-disk inspectability — a real cost for a cosmetic gain).
  Resolution deferred to the owner: dismiss the FP in the Security tab
  (recommended) at merge time.
- `2026-06-05` — **Recommendation (factual): land the contract, hold FU-3.**
  #326 (this contract + ledger) merged as the explicit deliverable; FU-3 (#330)
  stays a clean, validated open draft awaiting the owner's exact
  `Yes, with authorization.` + FP dismissal. No behavior change reaches `main`
  without explicit owner consent.
- `2026-06-05` — **Owner authorized (`Yes, with authorization.`) → FU-3 merged
  (#330, `842b0d53`).** Pre-merge, the path-traversal defense was re-verified
  against the actual code: `sanitize_segment` destroys every `/` (→ `-`) so no
  separator survives into a path component, rejects pure-`..`/dot segments
  (`.strip("-.")` → empty → raise), and `realpath`+`commonpath` backstops it —
  two independent barriers. Merge was mechanically clean (`mergeable_state:
  unstable` ⇒ only the non-required CodeQL-FP + Android flake were red; every
  required gate green). **All four follow-ups + the contract are now on `main`.**
  Residual: dismiss the CodeQL FP in the Security tab (cosmetic); the
  restored-job cost-meter reset stays a documented follow-up.

---

# Wave B — 10/10 full-scope program (2026-06-08)

**Single-writer (orchestrator only).** Same contract. Wave A (above) is closed;
Wave B is the owner-commissioned push to a *genuine* 10/10 — "not a demo, a ten
out of ten tool in functionality **and** design."

**Date opened:** 2026-06-08 · **Base:** `main` @ `b74f9889` (PRs #362–#367 merged).

## Locked scope envelope (owner, 4 clarifying answers)

1. **Build:** all three lanes **in parallel** — **A) Depth** (core loop excellent +
   proven E2E: cockpit → orchestrated job → worker patch → validation gate → draft PR
   → owner approval); **B) Breadth** (raise every surface); **C) Safety** (Phase-0/1
   wiring).
2. **Merge:** **pre-authorized on green CI** — additive *and* behavior-changing tasks
   merge on green; report after. (Spend stays a separate gate.)
3. **Spend:** paid APIs **OFF**; pause and quote cost before any paid call ⇒ the
   benchmark must be **free/local**.
4. **Proof bar (every task):** `ruff check .` clean · `ty check` **no new diagnostics
   vs base** · `pytest` green — **plus** a recorded real core-loop **E2E** (depth) and a
   **free/local benchmark scorecard** committed as evidence.

## Status legend

`planned` → `building` → `in-review` (PR open) → `merged`. Side states: `blocked`,
`deferred`. Tests run with **system** `python -m pytest -o addopts="-q"` (the uv venv
lacks pytest/plugins — this is also the root cause of FU-10).

## Ownership map (conflict-free partition — verified disjoint writable files)

| Task | Lane | Title | Owned (writable) files | Risk | Pri | Status |
|---|---|---|---|---|---|---|
| **FU-10-release-gate-venv** | C | `release_gate.py` false-RED → fall back to `sys.executable -m pytest` when uv's venv has no pytest | `hermes_cli/release_gate.py` · `tests/test_release_gate.py` | behavior | **P0** | planned |
| **FU-11-budget-should-stop** | C | Budget guard (`should_stop`) enforced pre-dispatch; default unbounded (no default change) | `hermes_cli/orchestrator_budget.py` (new) · `hermes_cli/orchestrator.py` · `tests/test_orchestrator_budget.py` (new) | behavior (opt-in) | **P0** | planned |
| **FU-12-cockpit-owner-gate** | C | C2+C3 **merged**: wire existing `owner_auth` nonce into `autonomy_set` + gate autonomy-raise | `gateway/cockpit/handlers.py` · `tests/gateway/test_cockpit_autonomy.py` | behavior (new gate) | **P0** | planned |
| **FU-13-allow-external-allowlist** | C | `--allow-external` host/CIDR allowlist; execute-refusal intact | `gateway/cockpit/server.py` · `tests/gateway/test_cockpit_loopback_guard.py` | behavior (net bind) | P1 | planned |
| **FU-14-cockpit-consume-gap** | A | **Client-only** depth cockpit: owner-gated approve/deny, consume `/jobs/stream` SSE, phase rail, model switcher, first-run auto-pair | `gateway/cockpit/static/index.html` · `gateway/cockpit/static/tokens.css` · `tests/gateway/test_cockpit_static_ui.py` | additive | **P0** | planned |
| **FU-15-core-loop-e2e** | A | Record ONE real core-loop E2E over real HTTP (submit→dispatch planner→validate→publish_plan draft-PR→approve) | `tests/e2e/test_core_loop_depth_e2e.py` (new) | additive (test) | **P0** | planned |
| **FU-16-benchmark-scorecard** | A/C | Free/local benchmark **scorecard producer** reusing `model_scorecard`/`benchmark_gate` | `hermes_cli/jarvis_prime/depth_scorecard.py` (new) · `tests/test_depth_scorecard.py` (new) | additive | P1 | planned |
| **FU-17-android-identity** | B | Singularity palette in `JarvisIconColors.kt`+`Theme.kt`; no-gold-at-rest test (**CI-verified only**) | `apps/android/app/src/main/java/com/aci/hermes/ui/jarvis/JarvisIconColors.kt` · `…/ui/theme/Theme.kt` · `…/ui/jarvis/IconColorsTest.kt` (new) | behavior (UI) | P1 | planned |
| **FU-18-aos-honesty-doc** | B | Restate AOS "233 agents" as a routed catalog; reconcile stale status docs | `docs/launch/10_10_PROGRAM_STATUS.md` · stale-status doc(s) | doc-only | P2 | planned |
| **FU-19-gateways-surface** | B | Raise ONE weakest gateway to capability/health parity (exact file declared pre-start) | `gateway/<one_gateway>.py` + its test | additive | P2 | planned |
| **FU-20-voice-graphrag-surface** | B | Raise ONE of voice/GraphRAG backend parity (exact module declared pre-start; not handlers/server/index) | `hermes_cli/jarvis_prime/<module>.py` + test | additive | P2 | planned |
| **FU-21-council-router-proof** | B | Prove AOS routing resolves only registry members (registry read-only) | `tests/test_aos_council_routing.py` (new) | additive (test) | P2 | planned |
| **FU-22-selfplay-theory** | — | Append the deep-research falsifiable hypotheses + free/local experiments | `docs/jarvis_architecture/MUSE_SINGLE_IDENTITY_AND_SELFPLAY.md` | doc-only | P2 | planned |

## Wave plan (disjoint ⇒ truly parallel)

- **Wave 1 (parallel, 8):** FU-10, FU-11, FU-12, FU-13, FU-14, FU-15, FU-16, FU-17.
  Zero shared writable files. (FU-15 exercises FU-11/FU-12 behavior but edits neither.)
- **Wave 2 (after wave-1 cockpit/handler/server merges, 3):** FU-19, FU-20, FU-21 —
  each declares exact files in this ledger before start (contract §3).
- **Wave 3 (last, doc reconciliation):** FU-18 (+ FU-22 doc can land any time).

## Conflict resolution baked in

- **C2 + C3 both edited `autonomy_set`** in `handlers.py` ⇒ collapsed into one writer
  **FU-12** (resolve by merge, not sequencing).
- **Cockpit consume-gap is client-only** — all routes already exist ⇒ FU-14 owns only
  `static/*`, never `handlers.py`/`server.py`; no collision with FU-12/FU-13.
- **`server.py`** sole writer = FU-13; **`handlers.py`** sole writer = FU-12;
  **`orchestrator.py`** sole writer = FU-11 (FU-15 is test-only).

## Load-bearing facts (for resume)

- `hermes_cli/release_gate.py:69-79` — `_pytest_argv()` hard-prefers `uv run`; FU-10
  fallback = `sys.executable -m pytest` when the venv has no pytest.
- `hermes_cli/orchestrator.py` — `dispatch_job` (~367-504) has **no** budget check;
  FU-11 inserts `should_stop` before `adapter.run` (~459).
- `gateway/cockpit/handlers.py` — `autonomy_set` (~2183) ungated; `approvals_decide`
  (~2661) already real-gated.
- `hermes_cli/jarvis_prime/owner_auth.py:146-186` — nonce `create_challenge` /
  `authorize_challenge` already exist; FU-12 *wires* them.
- `gateway/cockpit/server.py` — SSE `/v1/cockpit/jobs/stream`→`_stream_jobs` (180,427)
  and approvals/autonomy routes already registered; `serve()`+`allow_external` (512-541).
- `gateway/cockpit/static/index.html:243` — polls `/v1/cockpit/jobs` via `fetch`; no SSE,
  no approve button / phase rail / model switcher / auto-pair (FU-14 scope).
- `tests/e2e/test_cockpit_jobs_approvals_smoke.py` — the pattern FU-15 extends.

## Decision log

- `2026-06-08` — Owner locked the scope envelope (4 answers: all-parallel · merge
  pre-authorized on green · paid off/ask-per-call · proof = green + E2E + free-local
  benchmark). `/aos-audit` + `/code-review` + `/deep-research` run in parallel as four
  read-only council agents.
- `2026-06-08` — **delivery-scope-controller** returned a verified conflict-free
  12-task / 3-wave partition; the key unlock = cockpit consume-gap is client-only
  (no new routes) ⇒ wave 1 is 8 truly-parallel tasks. Ledger opened (this section).
- `2026-06-08` — **deep-research (general-purpose)** returned five new falsifiable
  hypotheses **H6–H10** (federation-interference theorem; verifier-diversity bound;
  identity-invariance-under-self-play; cross-niche learnability allocation;
  provably-non-relaxing safety gate) + free/local experiments + honesty ledger →
  **FU-22** (append to the theory doc).
- `2026-06-08` — **assurance-risk-director (`/code-review`)** returned a ranked
  defect list (214 relevant tests green under system pytest). See corrections below.

## Review-driven corrections (code-review, 2026-06-08)

These supersede the partition where they conflict. The orchestrator applies them
before cutting branches.

- **FU-11 (budget) re-scoped — do NOT add a new module.** `should_stop` already
  exists (`hermes_cli/budget_policy.py:70`, `evaluate_budget`) and is enforced in
  `orchestrator_parallel.py:1061`. The gap is the **single-job path**:
  `orchestrator.py:367 dispatch_job` never meters cost / consults the policy.
  Worse, `release_readiness_doctor.py:394-408 _check_budget_enforced` greps
  *either* orchestrator file for the token, so it falsely PASSes on the parallel
  match — masking the single-job gap (a *false-certainty* bug). **FU-11 owned files
  →** `hermes_cli/orchestrator.py` · `hermes_cli/release_readiness_doctor.py`
  (tighten the check to require the *enforcing* module to actually meter) ·
  `tests/test_orchestrator_budget.py` (new). Default budget unbounded ⇒ default
  path byte-identical.
- **FU-12 (autonomy gate) sharpened.** `autonomy_set` (`handlers.py:2183`) is the
  lone state-mutating cockpit route with **no** owner phrase (paid-flip :186,
  approvals :2661, pair-confirm :1173, execute :3256 all require it).
  `workspace_path` is caller-supplied ⇒ not a containment boundary. Fix: gate the
  **raise** path (require `AUTHORIZATION_PHRASE`; migrate toward
  `owner_auth.create_challenge` nonce), keep **revoke/lower** ungated; add
  `change_autonomy_level` to `OWNER_GATED_ACTIONS`; add an **env kill-switch** for
  the high-autonomy ceiling (rollback). **The existing
  `tests/gateway/test_cockpit_autonomy.py:83` asserts the bypass as correct** — it
  must be updated (403 without phrase, 200 with) so the fix isn't read as a
  regression. **FU-12 owned files →** `gateway/cockpit/handlers.py` ·
  `hermes_cli/approval_policy.py` · `tests/gateway/test_cockpit_autonomy.py`.
- **FU-10 (release-gate) confirmed**, fix = probe `uv run python -c "import pytest"`
  and fall back to `sys.executable -m pytest`; distinguish *tool-missing* from
  *tests-failed* (same guard for ruff). (Note: reproduces only where uv's venv
  lacks pytest; verify in-container at build.)

## New tasks (from code-review; both disjoint from wave-1 owners)

| Task | Lane | Title | Owned (writable) files | Risk | Pri | Status |
|---|---|---|---|---|---|---|
| **FU-23-candidate-tagging** | C | Machine-tag unverified provider slugs `candidate` (founding "no fake certainty" rule); `_hosted_candidates` sorts verified-first / skips candidates when paid; soften the paid-"floor" docstring to describe double-gating accurately | `docs/ai-intelligence/oss-model-catalog.yaml` · `hermes_cli/oss_model_brain.py` · `hermes_cli/jarvis_prime/task_router.py` · `tests/test_oss_model_brain.py` (or new) | additive | P1 | planned |
| **FU-24-handoff-redaction** | C | Run graph-derived citations/titles + architecture summary through `_redact` in `context_handoff` (today only the request is screened) | `hermes_cli/jarvis_prime/context_handoff.py` · `tests/test_context_handoff.py` | additive | P2 | planned |

Both verified disjoint: no wave-1 task writes `task_router.py`, `oss_model_brain.py`,
the OSS catalog YAML, or `context_handoff.py`. FU-23/FU-24 join **wave 1**.

Also folded in (no new task): FU-13 adds the `_STATIC_TYPES` suffix allowlist;
FU-14 adds percent-encoded path-traversal test cases (`test_cockpit_static_ui.py`).

## Evidence-driven corrections (evidence-architect ground-truth, 2026-06-08)

The evidence agent **ran the commands** (not just read code) and corrected two
priorities — recorded here for honesty (no claiming a bug that isn't real on this
checkout):

- **FU-10 downgraded P0 → P2 (defensive hardening, not a live bug).** On this
  checkout `uv run python -m pytest --version` → **pytest 9.0.3** with xdist /
  timeout / asyncio all importable (declared in `pyproject.toml` `dev` group); the
  release-gate fast slice = **170 passed**. The gate is **GREEN here**. The
  `uv run` preference only false-REDs on a host whose venv is unsynced. So FU-10
  becomes a *robustness* fix (distinguish "pytest missing in chosen env" → WARN
  from "tests failed" → FAIL); it does **not** block GREEN now. Confirmed myself:
  both `uv run` and system pytest report 9.0.3.
- **FU-17 narrowed to ONE file.** `apps/.../ui/theme/Color.kt` is already fully
  Singularity (`JarvisGold = 0xFFFFFFFF` white core, `JarvisCyan = 0xFF7AE0FF`,
  `JarvisViolet = 0xFFB388FF`, `JarvisInkAbyss = 0xFF050507`) and `Theme.kt` reads
  from it correctly — the prior "Theme.kt still gold" was a mis-attribution. The
  real incoherence is **localized to `JarvisIconColors.kt`'s private `JarvisPalette`**
  (`Gold=0xFFFFD700`, `GoldDeep=0xFFB8860B`, `Cyan=0xFF00E5FF`, `Violet=0xFF5865F2`)
  which deliberately decoupled from `Color.kt` and still carries gold-era literals —
  affecting IDLE **and** WAITING_FOR_APPROVAL **and** SERIOUS rings. **FU-17 owned
  files →** `apps/.../ui/jarvis/JarvisIconColors.kt` + new `IconColorsTest.kt`
  ONLY (drop `Theme.kt`). CI-verified only.
- **M4/M5 dropped from my scope.** "Android `LaunchGate`" (M4) matches no Android
  artifact — it's the MUSE owner-gate concept, mis-tagged; nothing to fix. APK
  release signing (M5) is real but **owner-only** (needs the owner's keystore;
  `build.gradle.kts` falls back to debug-signing by design) → stays owner-gated,
  not a builder task.
- **AOS count (FU-18) quantified.** Registry self-describes "233 distinct names /
  248 entries" + "108 sub-agent entries" — a **routed catalog tally**, not 341
  standalone files. Actual `agents/**.md` = 261, but **177 are `agents/hermes/`**
  (the general skill library: `1password.md`, `arxiv.md`, …), ~84 are genuine
  council files. FU-18 reframes the claim precisely and notes `agents/hermes/`.
- **Stale worktrees noted** (`.claude/worktrees/agent-*`, `/tmp/pr362-base`) — left
  from merged PRs; harmless but double grep hits. All edits target the canonical
  tree at repo root.
- **Test reality:** full suite collects **28,886** non-integration tests — per-task
  validation runs the relevant *slice*, not the whole suite (matches both reviewers).

**Revised wave-1 build order (by real severity):** FU-12 (security P0) → FU-11
(budget + doctor honesty, P0) → FU-23 (candidate-tag honesty, P1) → FU-24
(redaction, P2) → FU-13/FU-14/FU-16/FU-17 (additive, parallel) → FU-15 (E2E, after
11/12) → FU-10 (hardening, P2). FU-18/FU-22 docs land any time.

## Wave-1 outcomes — ALL MERGED (2026-06-08)

All six wave-1 tasks built in parallel worktrees (orchestrator did FU-12; builder
agents did FU-11/14/16/17/23), each validated to the proof bar, draft-PR'd, and
**merged to `main`** on green CI under the owner's wave pre-authorization:

| Task | PR | Squash commit | What landed |
|---|---|---|---|
| FU-12 | #368 | `c30200e8` | Cockpit autonomy **escalation owner-gated** (+ `HERMES_COCKPIT_AUTONOMY_LOCKED` kill-switch); 65 tests |
| FU-11 | #373 | `9cb2b107` | Budget `should_stop` enforced on the **single-job path** + readiness-doctor false-PASS fixed; 136 tests |
| FU-23 | #371 | `a16b474f` | Unverified model slugs **machine-tagged `candidate`**, `_hosted_candidates` verified-first; 46 tests |
| FU-16 | #370 | `ad851926` | Free/local deterministic **benchmark scorecard producer** (reuses `research_fabric.benchmarks` + `ModelScorecard`); 25 tests |
| FU-14 | #372 | `9fdda311` | Depth cockpit: **fetch-SSE live jobs, owner-gated approve/deny, phase rail, model switcher, first-run pairing**; 16 tests |
| FU-17 | #369 | `e1ac6eed` | Avatar icon **Singularity palette** (no gold at rest); CI-verified |

**Decisions (honesty):**
- ty `unresolved-import: pytest` on a NEW test file is the universal infra FP
  (warning-only; 5179 pre-existing) → **exempt** from "no new diagnostics"; real
  diagnostics stayed at 0 (FU-23) or only the exempt FP (FU-11/FU-16).
- FU-11 changes single-job runtime behavior only when a budget is configured
  (default path byte-identical); merged under the **wave pre-authorization**.
- FU-14: native `EventSource` can't send the bearer header (server is header-auth
  only), so the shell streams `text/event-stream` via `fetch` — the genuine
  substance of a live subscription. Accepted; tests assert the substance.

**Carried forward (wave-2 / cleanup):**
- **FU-17b** — FU-17 mapped gold→white core, so `WAITING_FOR_APPROVAL` and
  `SERIOUS_ACTION_PENDING` now render identically (white core + white ring). Small
  follow-up: give attention-states distinct on-brand accents (violet ring etc.).
- **FU-13** (`--allow-external` allowlist + `_STATIC_TYPES`), **FU-24** (handoff
  citation/title redaction), **FU-18** (AOS "233" honesty doc), **FU-22** (append
  H6–H10 theory), **FU-10** (release-gate `sys.executable` fallback hardening),
  **FU-15** (recorded core-loop E2E — now unblocked: FU-11/FU-12 are on `main`).

## Wave-2 + keystone outcomes — ALL MERGED (2026-06-08) · PROGRAM COMPLETE

Wave-2 and the keystone/polish tasks built as parallel worktree builders,
validated to the proof bar, and **merged to `main`** on green CI under the wave
pre-authorization:

| Task | PR | Squash commit | What landed |
|---|---|---|---|
| FU-18 | #375 | `c26ba52d` | AOS "233 agents" restated as an honest routed-catalog tally (233 names/248 entries/108 sub-agents; ~84 council files + 177 `agents/hermes/` general skills) |
| FU-10 | #376 | `965ccbe2` | Release gate hardened: probe interpreter for pytest, fall back to `sys.executable`; tool-absent → WARN not false-RED (builder *reproduced* the false-RED) |
| FU-13 | #378 | `ae406e33` | `--allow-external` host/CIDR allowlist (fail-closed non-loopback bind) + `_STATIC_TYPES` suffix allowlist |
| FU-22 | #379 | `4a915d17` | Self-play theory **H6–H10** appended (Parts VI–VIII: federation-interference, verifier-diversity bound, identity invariance, cross-niche allocation, provably-non-relaxing safety gate) + honesty ledger |
| FU-24 | #377 | `3af96285` | Context-handoff redaction extended to graph-derived citations/titles/summary (was request-only) |
| FU-15 | #380 | `1fd94e14` | **Recorded core-loop E2E** over real cockpit HTTP: submit → run (offline planner, `queued→completed`) → owner-gated publish (`github_not_configured`) → owner-gated approve, asserting FU-12 autonomy gate + audit ledger; `1 passed in 1.27s` |
| FU-17b | #381 | `56639c5b` | Distinct on-brand attention states: IDLE cyan → WAITING violet ring → SERIOUS violet core+ring → CRITICAL red (no gold at rest; CVD-robust) |

### Program scorecard — 13 tasks, all merged

- **Wave 1 (6):** FU-11, FU-12, FU-14, FU-16, FU-17, FU-23.
- **Wave 2 + keystone/polish (7):** FU-18, FU-10, FU-13, FU-22, FU-24, FU-15, FU-17b.
- **Proof bar met:** `ruff`/`ty`/`pytest` green (no new *real* diagnostics; pytest-import FP exempt) · free/local benchmark scorecard (FU-16) · **recorded core-loop E2E** (FU-15).
- **Safety net intact + strengthened:** autonomy escalation owner-gated (FU-12) + env kill-switch; budget hard-stop on the single-job path (FU-11); non-loopback bind allowlisted (FU-13); handoff redaction widened (FU-24); no owner gate / paid-opt-in / emergency-stop weakened anywhere.

### Honest residuals (carried, not regressions)

- **CodeQL aggregate flaked red (2s) on FU-24 #377** while every real `Analyze` job passed — non-required; merged correctly. Cosmetic; no code issue.
- **FU-15 run hop uses the offline planner** (repo-mutating execute lanes shell out to paid CLIs + network, not hermetic). A live owner-present execute→real-PR run is the next layer, intentionally out of the no-network test.
- **Planner perf:** rooting the navigator at the full checkout takes ~306s (FU-15 finding) — a real optimization opportunity, out of this program's scope.
- **`IconState.kt` stale "Gold ring" doc comments** (FU-17b residual) — cosmetic, deferred to a doc sweep.
- **Owner-only outward actions remain (by design, never builder-merged):** GitHub repo rename to the MUSE slug; real Android release signing + Play Store permission/disclosure; any paid-API enablement (still OFF / ask-per-call).

### Decision log (close)

- `2026-06-08` — **Program complete.** 13 tasks merged across waves 1–2 + keystone.
  All under the owner's four-answer scope envelope (all-parallel · merge
  pre-authorized on green · paid off/ask-per-call · proof = green + E2E +
  free/local benchmark). Builder≠reviewer honored (orchestrator did FU-12 +
  reviewed/merged all builder PRs); disjoint file ownership held conflict-free
  end-to-end. This tracking PR (#374) merges last.

---

# Swarm — finish-to-10/10 across surfaces (2026-06-08)

**Single-writer (orchestrator).** Grainler parallel swarm continuing the program
to a genuine 10/10 across every surface. Owner directive: **lift the GitHub
repo-rename gate** (rename-prep is now in-scope, staged draft) and **continue all
phases as a grainler parallel swarm**. **All other owner gates stay intact**
(paid/spend, Android release signing, Play Store disclosure, prod deploy) and the
two architectural god-file extractions stay owner-gated.

**Base:** `main` @ `ba2c12df`. Conflict-free 9-grain partition (one read-only
scope pass); every writable file has exactly one owning grain.

## Grain ownership (disjoint; verified conflict-free)

| Grain | Wave | Owned (writable) files | Risk | Gate | Status |
|---|---|---|---|---|---|
| **g-rename-prep** | 1 | `README.md` · `CONTRIBUTING.md` · `.github/**` (templates, dependabot, codeql-config, actions, workflows) · `packaging/homebrew/hermes-agent.rb`→`muse.rb` | outward (slug) | **repo-rename gate LIFTED → stage draft PR, do NOT merge** (merge only at the actual rename, else dead links) | planned |
| **g-fu13-allowhost-cli** | 1 | `hermes_cli/main.py` (cockpit_serve parser + cmd_cockpit) · `tests/hermes_cli/test_cockpit_cli_allowhost.py` (new) | additive | merge-on-green | planned |
| **g-navigator-perf** | 1 | `hermes_cli/jarvis_prime/navigation/repo_index.py` · `tests/jarvis_prime/navigation/test_repo_index_perf.py` (new) | additive (perf) | merge-on-green | planned |
| **g-gateway-parity** | 1 | `gateway/platforms/sms.py` · `tests/gateway/platforms/test_sms_capabilities.py` (new) | additive | merge-on-green | planned |
| **g-graphrag-parity** | 1 | `hermes_cli/jarvis_prime/graphrag/query.py` · `tests/jarvis_prime/graphrag/test_query_parity.py` (new) | additive | merge-on-green | planned |
| **g-aos-router-proof** | 1 | `tests/test_aos_council_routing.py` (new, test-only) | additive | merge-on-green | planned |
| **g-iconstate-docsweep** | 1 | `apps/android/.../ui/jarvis/IconState.kt` (comment-only) | cosmetic | merge-on-green (CI-only) | planned |
| **g-handlers-extract** | 2 | `gateway/cockpit/handlers.py` + `handlers_<group>.py` (new) + test | architectural | **owner-gated**: draft PR + await `Yes, with authorization.` | deferred→wave-2 |
| **g-jpmain-extract** | 2 | `hermes_cli/jarvis_prime/__main__.py` + `cli_<group>.py` (new) + test | architectural | **owner-gated**: draft PR + await authorization | deferred→wave-2 |

## Sequencing & posture

- **Wave-1:** 7 grains, truly parallel (disjoint), each `claude/<grain-id>` from
  `main` in its own worktree. Six merge-on-green; **g-rename-prep stays a staged
  draft** (the only thing the rename gate still governs is the *merge*, gated on
  the actual GitHub rename, which is the owner's one-click — no rename-repo API
  exists in the toolset).
- **Wave-2:** `g-handlers-extract` + `g-jpmain-extract` run parallel **to each
  other** (disjoint import-hub files) but **after** wave-1 merges; both
  owner-gated (architectural) → draft PR + ledger summary + await authorization.
- **Not swarmed (advance-as-far-as-safe, gated step NOT executed):** live
  execute-lane→real-PR E2E (paid+network → harness/skip-mark only), Android real
  signing (owner keystore), Play Store disclosure, paid-API enablement, the
  GitHub rename click itself.
- **Excluded (bounded):** voice arm (chose GraphRAG), extra gateway adapters
  beyond the weakest (`sms`), full god-file rewrites, the 528 substrate
  `hermes-agent` text hits (not outward slug).

## Decision log

- `2026-06-08` — Owner lifted the repo-rename gate + ordered "all phases" as a
  grainler swarm. One read-only scope pass → conflict-free 9-grain / 3-wave
  partition. Wave-1 (7 disjoint grains) fanned out; rename-prep staged-not-merged;
  structural god-file grains held owner-gated for wave-2.
- `2026-06-08` — **SWARM COMPLETE.** Wave-1 merge-on-green grains all merged:
  g-iconstate (#383), g-graphrag (#384), g-fu13 (#385), g-aos-router (#386),
  g-gateway (#387), g-navigator (#388, found+fixed the 306s walk → `.claude/worktrees`
  157k-file descent). Wave-2 structural seams — **owner authorized** (`Yes, with
  authorization.`) and merged: g-jpmain-extract (#390, `99e32216`; `route`→`cli_route.py`,
  byte-identical CLI; review-flagged dead `_cmd_route` alias removed before merge) and
  g-handlers-extract (#391, `70d954d4`; autonomy group→`handlers_autonomy.py`,
  AST-identical, 5983 gateway tests green, re-export keeps `server._ROUTES` intact).
  **8 grains merged.** Remaining: **g-rename-prep (#389) STAGED** — merges only when
  the owner renames the GitHub repo (merging first = dead links); and a **rename-completion**
  sweep (secondary docs + the `brew upgrade` CLI string) to run in lockstep with the
  rename. All non-rename owner gates stayed intact throughout (paid/signing/Play/prod).

