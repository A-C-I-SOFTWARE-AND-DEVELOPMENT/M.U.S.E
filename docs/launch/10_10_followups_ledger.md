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
  artifact — it's the muse owner-gate concept, mis-tagged; nothing to fix. APK
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
- **Owner-only outward actions remain (by design, never builder-merged):** GitHub repo rename to the muse slug; real Android release signing + Play Store permission/disclosure; any paid-API enablement (still OFF / ask-per-call).

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
| **g-rename-prep** | 1 | `README.md` · `CONTRIBUTING.md` · `.github/**` (templates, dependabot, codeql-config, actions, workflows) · `packaging/homebrew/hermes-agent.rb`→`muserb` | outward (slug) | **repo-rename gate LIFTED → stage draft PR, do NOT merge** (merge only at the actual rename, else dead links) | planned |
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

## Repo rename — COMPLETE (2026-06-08)

Owner lifted the repo-rename gate and renamed the GitHub repo
`hermes-agent` → **`A-C-I-SOFTWARE-AND-DEVELOPMENT/muse`** (Settings → Rename).
The slug came back as **`muse`** (dots/caps), not the lowercase `muse` the
staged patch assumed — caught before merge (merging the `muse` patch would have
created dead links, since GitHub redirects only the *old* name `hermes-agent`,
not `muse`). Owner chose to keep `muse`; the patch was reworked accordingly.

- **#389** (`64bead62`) — reworked to the real slug + reduced to a **minimal-safe**
  set: this repo's user-facing GitHub URLs (`README`, `CONTRIBUTING`, issue/PR
  templates) → `A-C-I-SOFTWARE-AND-DEVELOPMENT/muse`. The `github.repository ==`
  **publish/deploy guards**, Docker/PyPI/Cachix registry names, and the homebrew
  formula were **reverted to status quo** (dormant on this repo; registry renames
  are owner-coordinated; changing them risked dead refs or activating publishing).
- **#392** (`d975651c`) — completion sweep: the **install one-liners**
  (`scripts/install.{sh,ps1}` raw URLs, `docs/jarvis-prime-operating-system.md`,
  `docs/jarvis-free-first-launch.md`) and `CANONICAL_REPO.md` → `…/muse`.
  These use `raw.githubusercontent.com`, which (unlike github.com) does **not**
  reliably follow the rename redirect — so they were the must-fix.

**Left intentionally:** ~1000 `hermes-agent` refs in historical/audit/launch docs
(period-accurate records; GitHub's redirect covers their github.com URLs); the
local install-dir `~/.hermes/hermes-agent` and `hermes_cli`/`hermes_agent`
identifiers (substrate — renaming breaks existing installs).
**Owner-coordinated remaining (separate platforms):** Docker Hub / PyPI / Cachix /
homebrew namespace renames (+ the `brew upgrade` CLI string) — do at publish time.

**Honest correction (doc-only, no code impact):** #389's `-s ours` merge — run
against a momentarily-stale local `origin/main` during the rework — inadvertently
reverted #382's *swarm-ledger section* from this file. Verified **all 8 swarm
grains' code is intact** on `main` (`handlers_autonomy.py`, `cli_route.py`, the
sms `capabilities()`, the new tests, 9 snapshots — all present); only this audit
doc's section was affected, and it is **restored** in this commit.

---

# Wave C — Comprehensive AOS audit closeout (2026-06-08)

**Date opened:** 2026-06-08 · **Base:** `main` @ `860a88b8e` (post-Wave-B,
post-swarm, post-#411 docs sweep).

A comprehensive `/aos-audit` ran six council members in parallel against the
post-Wave-B state and surfaced four bounded packets. Owner authorized via
`Yes, with authorization.` on the same day. Wave C lands as a **single
branch / single PR** on `claude/vigilant-knuth-519h3u` (the session's
designated branch — the cross-task parallel-worktree pattern of Wave B does
not apply here because the branch is fixed by the session contract).

## Audit findings → packet map

| Finding | Source agent | Packet |
|---|---|---|
| `muse` first-run gate ignores `model_policy.json` — README's headless instruction is a dead end | product-experience-architect, evidence-architect | **WC-1** |
| `_parser.py:90 prog="hermes"` + 4 more happy-path "hermes" leaks (deferred from g1b cascade) | contrarian-reviewer, evidence-architect | **WC-1** (collapsed) |
| Release gate fails OPEN when both interpreters lack pytest/ruff (`release_gate.py:222-272`) — highest single risk | assurance-risk-director | **WC-2** |
| No test in the repo calls a real model — "proof bar" is partially synthetic + offline E2E not even gated by CI unit job | contrarian-reviewer, evidence-architect | **WC-3** |
| FU-18 "233 → routed catalog" honesty did not propagate to 4 `AOS_*.md` surfaces | evidence-architect | **WC-4** |
| `handlers.py` is a 3,810-line god-module with 17 imported subsystems; three hand-mirrored web clients (cockpit static / desktop Tauri / Android) | principal-systems-architect | **out-of-scope — EPIC-COCKPIT-SEAM, owner-decision-gated** |

## Ownership map + outcomes

| Task | Title | Owned files | Risk | Status |
|---|---|---|---|---|
| **WC-1** | First-run gate reads `model_policy.json` + detection-aware non-interactive guidance + happy-path "hermes"→"muse" sweep (collapsed single writer) | `hermes_cli/main.py` · `hermes_cli/setup.py` · `hermes_cli/_parser.py` · `tests/hermes_cli/test_api_key_providers.py` · `tests/hermes_cli/test_setup_noninteractive.py` | **behavior change → owner-gated** | **merged → #414** (`4e84b28b1`) |
| **WC-2** | Release gate hard `tooling_present` precondition (`HERMES_RELEASE_GATE_STRICT=1` opt-in; FU-10 default preserved) | `hermes_cli/release_gate.py` · `tests/test_release_gate.py` | **behavior change → owner-gated** | **merged → #414** (`4e84b28b1`) |
| **WC-3** | `tests/e2e/test_core_loop_live_smoke.py` (`@pytest.mark.live`, `--run-live`/`HERMES_E2E_LIVE=1` opt-in) + conftest hook + CI annotation | `tests/e2e/test_core_loop_live_smoke.py` (new) · `tests/conftest.py` · `.github/workflows/tests.yml` | additive (test) | **merged → #414** (`4e84b28b1`) |
| **WC-4** | Propagate FU-18 "routed catalog" qualifier to 4 stale `AOS_*.md` surfaces | `AOS_AGENT_REGISTRY_COMPLETE.md` · `docs/aos-recovery/AOS_AGENT_RECOVERY_REPORT.md` · `docs/aos-recovery/AOS_AGENT_REGISTRY_COMPLETE.md` · `docs/aos-recovery/AOS_INSTALLATION_REPORT.md` | doc-only (RC0) | **merged → #414** (`4e84b28b1`) |

Per-task snapshots: `docs/launch/followups/wc-1-firstrun-rebrand.md`,
`wc-2-release-gate-tooling.md`, `wc-3-live-smoke.md`,
`wc-4-honesty-233-docs.md`.

## Decision log

- `2026-06-08` — `/aos-audit` (comprehensive) dispatched six council members
  in parallel: `evidence-architect`, `principal-systems-architect`,
  `product-experience-architect`, `assurance-risk-director`,
  `contrarian-reviewer`, `delivery-scope-controller`. All read-only; tree
  unchanged before/after.
- `2026-06-08` — `delivery-scope-controller` returned a 4-task partition with
  one explicit **collapse**: WC-1 and WC-2 of the original proposal both
  wanted `hermes_cli/main.py` line 1394 (the same string for the gate
  message AND the rebrand). Single writer is mandatory by the parallel
  contract §7 → collapsed into WC-1. Final partition is 4 tasks, disjoint
  on writable files.
- `2026-06-08` — Owner authorized: `Yes, with authorization.` (covers WC-1
  + WC-2 behavior-change merges + WC-3 CI lane edit; WC-4 auto-merges as
  RC0).
- `2026-06-08` — Three `/deep-research` agents dispatched in parallel as a
  read-only council seat: (a) cold-start UX for autonomous agent CLIs
  (Aider's ordered-env-var scan + OpenRouter OAuth fallback is the
  strongest pattern; informs WC-1 design); (b) free/local LLM stack
  mid-2026 (GLM-4.5 / Qwen3 32B / vLLM is the recommended stack; BFCL v3
  multi-turn / τ²-bench / SWE-bench Pro are the real benchmarks; informs
  the post-WC-3 depth program); (c) god-module decomposition (Pattern 2+1
  hybrid — per-domain `_ROUTES` siblings + central registry; 5-phase
  strangler; informs the out-of-scope EPIC-COCKPIT-SEAM). Synthesis lands
  in the PR description; full reports archived in the chat transcript.
- `2026-06-08` — All four packets built on `claude/vigilant-knuth-519h3u`,
  validated locally (`ruff check` clean; `ty check` no new diagnostics on
  edited lines; focused pytest selection 218 passed, 1 skipped — the
  WC-3 live smoke is correctly skipped by default). Single draft PR opens
  on push.
- `2026-06-08` — **Wave C closed.** PR #414 merged to `main`
  (`4e84b28b1`). Status rows above refreshed to `merged` during the
  Wave-D ledger reconciliation (2026-06-10); the rows had been left at
  `building → in-review` after the merge — ledger-only staleness, no
  code drift.

# Wave D — 10/10 readiness fix sweep (2026-06-10)

**Trigger:** owner directive — "do a 10/10 readiness audit … extensive
audit and fix sweep in grainler parallel … fix all PRs/drafts, organize
and optimize entire repo/files … extensive ui/ux polish upgrading to
apple quality keeping my brand and colors."

**Owner authorizations on file (2026-06-10, via in-session decision
prompts):** (1) fix **and merge** all open PRs; (2) UI/UX polish across
**all surfaces equally** (Android / web cockpit / TUI / desktop);
(3) EPIC-COCKPIT-SEAM **Phase 0 only** (wire-contract freeze, additive).
`design-system/tokens.json` is **frozen** this wave — every UI grain
consumes tokens, none edits them.

## Wave-0 closeout actions (orchestrator, sequential — done first)

| Action | Outcome |
|---|---|
| Merge #432 (small-fixes G6, additive tier, 30/30 green) | **merged** (`08e42502`) |
| Un-draft + merge #433 ("Hey muse" wake word, green, owner-authorized) | **merged** (`e283d39e`) |
| Fix #423 red check (secret-scan: 4 `env_name` FPs on `${{ secrets.* }}` *references* in `muse-desktop-release.yml`) | pragma-allowlisted on the PR branch (`ebfdba215`); local scan exits 0; merge on green CI; durable scanner fix = grain G8 |
| #408 (CodeQL advanced setup) | **closed: blocked-on-owner-settings** — repo runs CodeQL Default Setup, which rejects SARIF from advanced workflows; the failing matrix is unfixable from a PR. Owner options recorded on the PR: add Kotlin to Default Setup languages (recommended, one click) or disable Default Setup and revive #408. |
| Ledger reconciliation | Wave C rows → `merged`; navigator-perf residual **closed** by #388 (306 s → 0.51 s, see `followups/g-navigator-perf.md`); `gateway/platforms/yuanbao.py:4678` TODO T06 **deferred** (needs live Yuanbao credentials — untestable free/local); EPIC P1–P5 remain owner-gated |

**New finding (Wave-0):** GitHub reports 4 Dependabot alerts on `main`
(1 critical, 3 moderate) — triage added to this wave as grain **G9**.

## Wave-1 grain table (parallel; disjoint owned files; one branch +
worktree per grain, cut from post-Wave-0 `main`)

| Grain | Branch | Owned files (summary — full set in snapshot) | Risk tier | Status |
|---|---|---|---|---|
| **G1 root-tidy** | `claude/fu-d1-root-tidy` | 13 `RELEASE_v*.md` → `docs/releases/`; 9 root `AOS_*.md` consolidated into `docs/aos-recovery/`; one-off reports → `docs/audits/`; inbound-link rewrites (`CLAUDE.md`, `AGENTS.md`, `SETUP.md`, …) | doc-only → auto-merge | **merged** — PR #438 (`f0e413241`) |
| **G2 launchgate-strict** | `claude/fu-d2-launchgate-strict` | `.github/workflows/launch-gate.yml` only | additive CI job → auto-merge | **merged** — PR #435 (`a26eb80a3`) |
| **G3 cockpit-contract-p0** | `claude/fu-d3-cockpit-contract-p0` | `scripts/generate_cockpit_contract.py` · `docs/contracts/cockpit-wire-contract.{json,md}` · `tests/gateway/test_cockpit_contract_freeze.py` (all new) | additive → auto-merge | **merged** — PR #436 (`30df5952b`) |
| **G4 android-polish** | `claude/fu-d4-android-polish` | `HermesNavGraph.kt` · `JarvisShell.kt` · `Theme.kt` · `Type.kt` · `EmptyState.kt` · `DesignSystemGallery.kt` | UI behavior change → pre-authorized | **merged** — PR #437 (`165811996`) |
| **G5 web-polish** | `claude/fu-d5-web-polish` | `web/src/themes/presets.ts` · `web/src/index.css` · `web/src/components/EmptyStateCard.tsx` (new) · bare-empty-state pages · `hermes_cli/web_server.py` + theme-list test | default-theme change → pre-authorized | **merged** — PR #439 (`07fe20269`) |
| **G6 tui-polish** | `claude/fu-d6-tui-polish` | `ui-tui/src/theme.ts` · `ui-tui/src/components/{helpHint,branding,thinking}.tsx` | UI (light theme) change → pre-authorized | **merged** — PR #440 (`451f5612c`) |
| **G7 desktop-polish** | `claude/fu-d7-desktop-polish` | `apps/desktop/src-tauri/{src/lib.rs,Cargo.toml,Cargo.lock,capabilities/default.json}` · `apps/desktop/ui/src/{App.tsx,styles/app.css}` — **not** `tauri.conf.json` (#423's) | shell behavior change → pre-authorized | **building** — relaunched post-#423; first run lost to session suspension; +glib triage from G9 |
| **G8 ci-hygiene** | `claude/fu-d8-ci-hygiene` | 13 workflow files (not `launch-gate.yml`) · `scripts/scan_secrets.py` · its test | infra change → pre-authorized | **merged** — PR #441 (`57701fe8a`) |
| **G9 dependabot-triage** | `claude/fu-d9-dependabot` | TBD by triage (lockfile/dependency bumps only) | security fix → pre-authorized | **merged** — PR #442 (`bb19e9c45`); glib alert deferred → G7 |

## Wave-1 closeout (orchestrator, 2026-06-10)

| Event | Record |
|---|---|
| Merge path | #423 → `7ba9f7bd` (orchestrator); #438 G1 → `f0e413241`, #435 G2 → `a26eb80a3` (orchestrator, on green CI); #436 G3, #437 G4, #439 G5, #440 G6, #441 G8, #442 G9 and ledger PR #434 merged directly by the owner (~04:30Z) |
| G2 secret-scan fix | strict-gate job's blanked API-key env lines (`launch-gate.yml:190-192`) flagged as `env_name` FPs; orchestrator pushed pragma allowlist (`7d831153`) — empty strings cannot be values. G8's durable fix covers `${{ … }}` references; empty-value suppression not included (pragmas remain correct) |
| Contract §7 collision (G1 × G8 on `scripts/scan_secrets.py` + test) | resolved by sequencing: G1 merged first (decode robustness, `errors="replace"`); G8's `_scan_line` change touched a different region and merged cleanly after |
| Pre-existing corruption repaired | truncated UTF-8 em-dash in `docs/aos-recovery/AOS_FULL_SOURCE_INVENTORY.md` (the byte pair that crashed the scanner in G1's diff) repaired to a full `—`; file now decodes clean |
| Housekeeping note | `claude/fu-d8-ci-hygiene` was re-pushed by the orchestrator after the owner's merge auto-deleted it (race during the merge train); the stray branch is inert — PR #441 is merged; owner may delete it |
| Operator-gated follow-on (G2) | after a few green cycles, promote the "Release gate (strict tooling)" job into branch protection / the launch-gate REQUIRED rollup |
| Dependabot | 4 alerts → 1 remaining (glib `GHSA-wrw7-89jp-8q8g`, moderate, alert #49) — bump attempt assigned to G7 |

**Deferred (recorded, no grain):** yuanbao T06 live chat-info fetch;
EPIC-COCKPIT-SEAM P1–P5; #408 advanced CodeQL (owner settings);
registry/namespace renames (Docker Hub / PyPI / Cachix — publish-time,
owner-coordinated).

## Out-of-scope (tracked separately)

**EPIC-COCKPIT-SEAM** — owner-decision-gated. Multi-week. Phase
breakdown:

- P0 — Freeze the cockpit wire contract as an OpenAPI snapshot + Syrupy
  golden fixtures + `oasdiff` CI gate (no behavior change).
- P1 — Introduce `gateway/cockpit/handlers/__init__.py` re-export shim
  plus `ROUTE_GROUPS = [LEGACY_ROUTES]`, no handler moves yet (the
  registry seam pattern, validated by FastAPI / Netflix Dispatch /
  Django's historical `core/management` split).
- P2–P4 — Extract domain siblings one PR per domain, lowest-coupling
  first (`health`+`pairing` → `runtime`+`models`+`capabilities` →
  `memory`+`evidence`+`audit`+`ledger` → `jobs`+`orchestrate`).
  Preserves first-match `_ROUTES` order byte-for-byte (the cockpit's
  regex dispatch table requires it).
- P5 — Unify the TypeScript client across cockpit-static and desktop
  Tauri; regenerate from the (unchanged) OpenAPI spec; verify zero diff.

Awaits owner go/no-go before any branch is cut.

---

# Wave E — finish all remaining follow-ups (2026-06-13)

**Trigger:** owner directive (`/goal`) — "finish all remaining follow ups."
**Single-writer (orchestrator).** Base: `main` @ `851930f2d` (post-#454
autoresearch, post-#455 muse final audit). Session branch
`claude/stoic-planck-l3dvd6` (single-branch pattern, as Wave C).

## Remaining-items inventory (ground-truthed against code/PRs/branches)

| Item | Disposition |
|---|---|
| **G7 desktop-polish** (Wave D, was `building`) | **merged → #456** (`93f0bd891`, full board green). Built+validated on `claude/fu-d7-desktop-polish-r2` but its PR was never opened (session suspension; the snapshot's "#438" was a stale placeholder). Cherry-picked onto current main with keep-both resolution against the brain sidecar that landed in the same files; Cargo.lock re-resolved (+347 lines, glib unchanged 0.18.5); fully re-validated. Both Codex review P2s fixed pre-merge: webview clipboard grant **removed** (copy happens Rust-side) and Copy Gateway URL copies the UI-selected base via the validated `gateway_url_hint_set` app command (label de-URL'd so it can't go stale). Snapshot: `followups/fu-d7-desktop-polish.md`. |
| **Post-#454 main breakage** (found this wave) | **fixed — merged in #456:** (a) the blocking *Windows footguns* gate failed on every PR — autoresearch `engine.py` bare `os.killpg`/`SIGKILL` now platform-gated; `vendor/` dirs excluded from the scanner (byte-pinned files can carry neither fixes nor suppressions); (b) *vendor-integrity test red on main* — GitHub autofix commits on #454 had edited `vendor/prepare.py` + `vendor/train.py`; restored byte-identical to the import (`64ad937e4`); the two CodeQL alerts those autofixes closed re-open on vendor files → **owner: dismiss them in the Security tab** (vendor policy: adaptations live in sibling modules); (c) `test_dataset_candidate_offer_is_soft_fail` red on main — missing call-site guard in `autoresearch_improve.py` added. 45 autoresearch tests green. |
| **glib GHSA-wrw7-89jp-8q8g (alert #49)** | **blocked upstream (re-affirmed at rebase):** `glib ^0.18` ← `gtk v0.18.2` ← `tauri v2.11.2`; gtk3-rs is maintenance-only. Auto-closes when Tauri drops `gtk ^0.18`; re-check on each Tauri upgrade. |
| **FU-3 residual — restored-job cost resets to 0** | **in-review → draft PR #459 (owner-gated).** Cost is now event-sourced (`cost.accumulated`); restart-replay rebuilds the meter; pre-event logs restore with the old zero meter. Behavior change (new event kind on the stream + restore now carries cost) ⇒ merge awaits the owner's exact `Yes, with authorization.` |
| **FU-2 (old) — per-worker default adapter factory** | **in-review → draft PR #459** (same PR; strictly additive — `adapter_factory` on the runner + `per_worker_local_adapter` canonical factory; default path byte-for-byte). |
| **FU-1 residual — wire the live server dispatcher to `run_plan_into_store`** | **owner-decision-gated** (unchanged; no live caller by design until the owner wires it). |
| **yuanbao T06** | blocked: needs live Yuanbao credentials — untestable free/local. |
| **EPIC-COCKPIT-SEAM P1–P5** | owner go/no-go gate (P0 contract freeze merged #436). |
| **#408 advanced CodeQL** | blocked on owner repo settings (CodeQL Default Setup). |
| **Registry/namespace renames** (Docker Hub / PyPI / Cachix / homebrew) | owner-coordinated, publish-time. |
| **G2 follow-on — promote "Release gate (strict tooling)" to required** | owner GitHub-settings click (several green cycles have elapsed since Wave D). |
| **PR #453 — deep Hermes→muse rename (owner's PR)** | **closed — stale/superseded-for-now** (owner delegated the disposition: "whichever action completes the task"). The 1,505-file diff was `dirty` vs main; the user-visible rebrand is on main via #455 and the audit records internal identifiers as intentionally kept, so closing leaves the audited, accepted state. The branch + `muse_RENAME_REPORT.md`/`muse_RENAME_INVENTORY.md` are preserved as the blueprint; redo = re-run the codemod phases fresh against then-current main as an owner-gated program (full rationale on the PR). |
| Audit deferrals (desktop sidecar bundling, `package.json` names, classic skin, orchestrator v-next placeholders) | intentionally deferred with rationale — `docs/launch/muse_FINAL_AUDIT_2026-06-12.md` §4; unchanged. |

## Decision log

- `2026-06-13` — Goal received; ledger read first (contract §1). Inventory
  ground-truthed: G7 identified as the only unfinished *built* grain; landed
  as PR #456 after rebase + re-validation. While #456 was in CI, its blocking
  *Windows footguns* failure exposed the post-#454 main breakage (gate +
  vendor pin + soft-fail test) — repaired in the same PR so the blocking gate
  works again for every PR.
- `2026-06-13` — **FU-2 + FU-3 built** (one commit, sequential PR on the same
  session branch after #456): per-worker ``adapter_factory`` on the runner +
  ``per_worker_local_adapter`` canonical factory (FU-2, additive); cost
  event-sourcing via ``cost.accumulated`` so restart-replay rebuilds the cost
  meter (FU-3, behavior change on emit + restore paths). Validation: 170
  runner/replay/dispatch tests + 82 API + 65 e2e/contract green; ruff clean;
  ty unchanged vs base (35). The FU-3 behavior change makes the PR
  **owner-gated** per contract §6 — draft opens after #456 merges; merge
  awaits the owner's exact `Yes, with authorization.`
- `2026-06-13` — **#456 merged** (`93f0bd891`) on a fully clean board (every
  check green, including the repaired footgun gate and the full web test
  job). Codex review's two P2 findings fixed pre-merge (webview clipboard
  grant removed; Copy Gateway URL copies the UI-selected base). **FU-2 +
  FU-3 opened as owner-gated draft PR #459** — Wave E's last buildable item;
  everything else remaining is blocked-on-owner/external by design (see
  inventory above). Wave E build phase complete.
- `2026-06-13` — **#453 closed** (owner-delegated disposition; rationale +
  redo blueprint on the PR; branch preserved). **Final audit on `main`
  @ `93f0bd891`:** footgun scan clean (898 files); vendor-integrity, bridge
  soft-fail, autoresearch engine, `/muse`, and restart-replay suites all
  green in a fresh worktree. Open-PR census: #459 (this wave's owner-gated
  draft — awaiting `Yes, with authorization.`) and #458 (another session's
  in-flight Vol-VI draft, opened mid-wave — not a ledger follow-up, not
  touched). **Wave E closed.** Owner action items: authorize/decline #459;
  dismiss the two vendor-file CodeQL alerts; optional settings clicks
  (#408 CodeQL language, strict-gate required promotion).

## Wave F — "perfect MUSE" residual sweep (2026-06-13)

Owner asked to finish every genuinely-unfinished feature ("leave no drafts").
A two-deep audit (Explore + Plan subagents, re-verified against HEAD) confirmed
the system was already ~86% with the loop closed at the seam level; several
prior "gaps" were already shipped (voice audio duplex, Android pairing nav,
FU-2/FU-3 #459, signed bridge envelope) and were **not** reopened. Five real
residuals remained, built on `claude/perfect-muse-mmfke2`:

| Lane | Item | Owned files | Risk | Status |
|---|---|---|---|---|
| **F-A** | Real SSH + Docker runtime adapters (were `NotImplementedError` stubs) — stdlib `subprocess`, no new deps | `hermes_cli/runtime_adapter.py` · `tests/test_runtime_adapter{,_ssh,_docker}.py` | additive | **built — auto-merge on green** |
| **F-B** | Yuanbao `get_chat_info` enriched from the existing live group-info API, with creds-absent fallback (closes `TODO T06`) | `gateway/platforms/yuanbao.py` · `tests/test_yuanbao_chat_info.py` | additive | **built — auto-merge** |
| **F-C** | Linear `--label`/`--assignee` name→id resolution (closes `TODO`); added missing update-issue flags | `skills/productivity/linear/scripts/linear_api.py` · `tests/skills/test_linear_skill.py` | additive | **built — auto-merge** |
| **F-D** | Decision verdict recorded at the out-of-band owner-approved mutation seam (recorded-not-gating) | `hermes_cli/action_executors.py` · `tests/test_action_executors.py` | additive | **built — auto-merge** |
| **F-E** | Live caller for the per-job cost seam — `POST /jobs/{id}/dispatch` drains worker usage into `JobCost` (real cost stops reading 0) | `hermes_cli/orchestrator_api.py` · `tests/test_orchestrator_dispatch_route.py` | **behavior change → owner-gated** | **built — default-off (`HERMES_ORCHESTRATOR_DISPATCH`), draft PR, awaits `Yes, with authorization.`** |

- `2026-06-13` — All five lanes built + validated: `uv run --extra dev ruff
  check .` clean, `ty check` clean on every touched module (no new
  diagnostics), and the full touched-suite selection green (166 tests) plus
  yuanbao regression (126). **F-E is behavior-changing and owner-gated**: the
  dispatch route is registered but 403s unless `HERMES_ORCHESTRATOR_DISPATCH=1`,
  so booting the API is byte-identical by default. F-A…F-D are strictly
  additive (eligible to merge on green); **F-E merges only after the owner's
  exact `Yes, with authorization.`**
- `2026-06-13` — **Wave F merged → #464** (squash `c1286f4`, owner-authorized
  `Yes, with authorization.` + admin-merge over two pre-existing reds). The
  `test_startup_plugin_gating` red was **already fixed on `main` by #463**
  (`2d3a37c` registered the real top-level `sync` subcommand in
  `_BUILTIN_SUBCOMMANDS`); #464 only saw it because it branched before #463
  merged. Verified on current `main`: all 37 gating tests pass. No follow-up
  needed for that item.
- `2026-06-13` — **CodeQL `#408` follow-up (separate PR, branch
  `claude/codeql-advanced-setup`).** Root cause: the committed advanced config
  `.github/codeql/codeql-config.yml` (vendor `paths-ignore` + clear-text-logging
  query-filter) is ignored because the repo runs CodeQL *default setup* with no
  advanced workflow — hence the 2s "CodeQL" failure + two un-suppressed vendor
  alerts. Added a **dormant** advanced workflow `.github/workflows/codeql.yml`
  (jobs gated on `vars.CODEQL_ADVANCED == 'true'` → skipped/neutral until
  activated, so it adds no red check) plus
  `docs/security/codeql-advanced-setup.md`. **Owner finish (two clicks):**
  Settings → Code security → switch CodeQL Default→Advanced, then set repo
  variable `CODEQL_ADVANCED=true`. That applies the config (clears the 2s
  failure + vendor alerts). Owner-gated by nature (repo Security settings);
  opened as a draft PR.

