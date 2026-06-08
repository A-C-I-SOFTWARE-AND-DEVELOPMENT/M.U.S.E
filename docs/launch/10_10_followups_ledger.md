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

