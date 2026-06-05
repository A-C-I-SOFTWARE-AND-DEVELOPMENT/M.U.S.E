# Hermes 10/10 — Program Status (repo-truth reconciliation)

> **Status doc owner:** Sprint 0 (Baseline & Program Governance).
> **Created:** 2026-06-05. **Source plan:** `hermes_10_10_plan` (dated 2026-06-04).
> **Purpose:** Freeze the 10/10 target against what the repository *actually*
> ships today, so parallel agents don't rebuild — and conflict with — mature,
> tested, security-critical code.

## TL;DR

The 14-sprint plan was written assuming an early-stage codebase. The real
codebase is mature: **roughly 80% of the plan is already implemented and
tested.** The remaining work is narrower than the plan implies. This program is
therefore reframed as **phased delivery of the genuinely missing/partial pieces,
in dependency order, one PR per phase**, gated by
[`PROTECTED_PATHS_10_10.md`](PROTECTED_PATHS_10_10.md).

The target vertical slice is unchanged:

> Voice/Android cockpit → gateway session → job orchestration → worker patch →
> validation gate → GitHub PR → phone approval.

Almost every box in that chain already exists. The one true structural gap in the
chain is a **single decision verdict** (`auto`/`ask`/`refuse`) — see Sprint 2.

## Legend

- **DONE** — implemented and tested; the plan's sprint assumption is false (do not rebuild).
- **PARTIAL** — substantial implementation exists; a bounded, well-defined slice is missing.
- **OPEN** — genuinely missing; safe to build.

## Reconciled status

| # | Sprint | Status | What exists (file · ~lines) | What's missing |
|--:|---|---|---|---|
| 0 | Baseline & governance | **OPEN** | — | This PR: program status, protected paths, current-state map, test baseline. |
| 1 | Architecture & contracts | **PARTIAL** | `docs/jarvis_architecture/*`, `docs/android/hermes-apk-api-contract.md` (46K) | Canonical 10/10 system map (added here), `docs/adr/`, formal `WorkPacket`/`DecisionVerdict` schema docs. |
| 2 | **Unified decision engine** | **OPEN** | 8 *separate* surfaces (below) — no `DecisionVerdict` type anywhere | One verdict pipeline (`auto`/`ask`/`refuse`) composing the existing surfaces; durable, replayable. |
| 3 | Workers → real diffs | **DONE** | `hermes_cli/workers/` · `worktrees.py` (423) · `workers/isolation.py` (796) | — Workers already run in isolated worktrees and emit real `patch.diff`. |
| 4 | Merge / validation / replay | **DONE** | `merge_engine.py` (735) · `validation.py` (1831) · `orchestrator_ledger.py` (141) · `orchestrator_replay.py` (100) · `scoring.py` (910) | — |
| 5 | GitHub PR publisher | **DONE** | `github_publisher.py` (888): `dry_run: bool = True` default, branch-per-job, secret blocking, idempotent | *Follow-up:* repo allowlist not found inside the publisher — verify/centralize in the PR that revisits Sprint 5. |
| 6 | Cockpit API & sessions | **DONE** | `gateway/cockpit/server.py` (492, 40+ routes) · `auth.py` (109, bearer/HMAC) · `event_log.py` (109, cursor replay) · `pairing.py` (321, rate-limit+lockout) · `session.py` (1404) | — |
| 7 | Android cockpit | **DONE** | `apps/android/` — 76 screens, 4 foreground services, `CockpitApi.kt` (1696), EncryptedSharedPreferences, 123 unit tests | — |
| 8 | Voice duplex | **PARTIAL** | Android voice loop (wake-word/STT/TTS); `/v1/cockpit/voice/intake|decide`; `tools/transcription_tools.py`, `tools/tts_tool.py`, `tools/voice_mode.py` (1018) | **Server audio HTTP routes** (`transcribe`, `command`, `responses/{id}/audio`) wiring existing STT/TTS into the gateway. |
| 9 | Phone approval push & recovery | **PARTIAL** | Approval inbox; Android `WorkWatchService` polling + notifications | **Optional push** (FCM/UnifiedPush) for lock-screen delivery behind a provider interface. |
| 10 | Routing / telemetry / cost | **PARTIAL** | `jarvis_prime/task_router.py`, `jarvis_prime/model_scorecard.py` (`cost_usd`) | **Per-job cost/time aggregation** + **budget gates** (soft⇒ask, hard⇒stop). |
| 11 | Supabase / Vercel | **PARTIAL** | `hermes_cli/integrations/supabase.py` (322), `vercel.py` (272) — local CLI **planners** only | **API integrations** + **Supabase memory provider**; env writes / deploy rollback behind `ask`. |
| 12 | Remote Windows bridge | **PARTIAL** | `hermes_cli/remote_bridge.py` (1226): file-drop transport, per-job token, device + command allowlists, scrubbed audit log; `test_remote_bridge.py` (1028) | **Threat-model docs** + **signed-envelope nonce/expiry/replay** semantics on top of the per-job token. |
| 13 | Multi-host / scale | **PARTIAL** | `tools/environments/` (local/ssh/docker/singularity/modal/daytona/vercel) + branch leasing in `jarvis_prime/worker_registry.py` | Durable `WorkerLease` (heartbeats/expiry/retry), host registry, artifact checksums. |
| 14 | Security hardening & release | **PARTIAL** | Extensive `docs/launch/*`; CI: `tests.yml`, `lint.yml`, `orchestration-tests.yml`, `osv-scanner.yml`, `supply-chain-audit.yml`, `launch-gate.yml`, … | 10/10 **e2e runbook** + `scripts/hermes-10-10-smoke.sh` + `doctor --10-10` + final security review. |

### The 8 separate decision/approval surfaces (Sprint 2 evidence)

No `DecisionVerdict` class exists anywhere in `hermes_cli/` or `enterprise/`.
Approval logic lives in eight independent places:

| File | ~lines | Role today |
|---|--:|---|
| `hermes_cli/approval_policy.py` | 668 | `Action`/`AutonomyLevel`/`Decision` (allow/confirm/deny), `evaluate_action()`. |
| `tools/approval.py` | 1393 | Interactive approval flows / prompts. |
| `tools/tirith_security.py` | 803 | Shell/command risk scanning, secret detection. |
| `tools/slash_confirm.py` | 167 | Slash-command confirmation gate. |
| `hermes_cli/decision_ledger.py` | 750 | Post-hoc decision *audit* (markdown/JSONL), not pre-exec gating. |
| `hermes_cli/orchestrator_ledger.py` | 141 | Per-job JSONL event ledger. |
| `enterprise/judge.py` | 170 | Schema/policy/jury cross-check (validation, not arbitration). |
| `enterprise/policy.py` | 171 | `Risk` classification table. |

Sprint 2 should **compose** these as `DecisionInput` collectors behind one
`merge_decision_inputs() → DecisionVerdict`, not replace them.

## Phased delivery order (post Sprint 0)

Dependency-ordered; each is its own PR with its own design pass and reviewer lane:

1. **Sprint 2** — unified `DecisionVerdict` engine *(foundational; risk-gating depends on it)*.
2. **Sprint 10** — per-job cost telemetry + budget gates *(uses the verdict for ask/refuse on overrun)*.
3. **Sprint 8** — voice audio HTTP routes.
4. **Sprint 11** — Supabase/Vercel API + Supabase memory provider.
5. **Sprint 9** — optional push provider.
6. **Sprint 13** — durable worker leases + host registry + artifact checksums.
7. **Sprint 12** — bridge threat-model + signed-envelope hardening.
8. **Sprint 1/14 close-out** — ADR backfill, e2e runbook + smoke + `doctor --10-10`, final security review.

## Non-negotiables (every phase)

- Preserve dry-run defaults for publish/remote/destructive actions.
- Every externally visible mutation gets a decision verdict + audit entry.
- No cockpit/API surface exposes secrets, raw credentials, raw chain-of-thought, or unredacted logs.
- Do not weaken redactors, owner gates, lockfile checks, validation gates, or test isolation.
- Each phase leaves `main` shippable.

## How this was verified

Three read-only inventory passes over `main` (backend core loop; gateway/voice/
integrations/bridge/CI; Android/tests/docs), plus direct confirmation of every
file path and line count cited above. See
[`current-state-map.md`](../architecture/current-state-map.md) for the as-built
module map and [`10_10_TEST_BASELINE.md`](10_10_TEST_BASELINE.md) for the
reliable command set.
