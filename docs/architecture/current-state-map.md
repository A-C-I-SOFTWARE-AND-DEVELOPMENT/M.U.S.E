# Hermes 10/10 — Current-State Architecture Map (as built)

> **Owner:** Sprint 0 (Baseline). **Created:** 2026-06-05.
> **Purpose:** Map each box of the 10/10 target architecture to the **real files**
> that implement it today, so later sprints extend the system instead of
> re-inventing it. Companion to
> [`../launch/10_10_PROGRAM_STATUS.md`](../launch/10_10_PROGRAM_STATUS.md).

This consolidates the Sprint 0 backend / gateway / Android / security baseline
lanes into one as-built map. Line counts are approximate but verified against
`main` on 2026-06-05.

## The vertical slice, annotated with real files

```text
Android Cockpit / Voice Surface
  apps/android/  — 76 Compose screens, 4 foreground services
  data/cockpit/CockpitApi.kt (1696)         ← typed cockpit client
  data/preferences/SecureTokenStore.kt      ← EncryptedSharedPreferences + Keystore
  service/WorkWatchService.kt               ← long-job polling + notifications
  voice/VoiceEngines.kt + service/VoiceLoopService.kt  ← wake-word/STT/TTS loop
        |
        | HTTPS + SSE + bearer token
        v
Gateway API + Pairing + Cockpit Sessions
  gateway/cockpit/server.py (492)           ← 40+ /v1/cockpit/* routes
  gateway/cockpit/auth.py (109)             ← bearer token, hmac.compare_digest
  gateway/pairing.py (321)                  ← rate-limit + lockout + 0600 storage
  gateway/cockpit/event_log.py (109)        ← JSONL event log, cursor replay
  gateway/session.py (1404)                 ← durable conversation sessions
  gateway/platforms/api_server.py (3531)    ← OpenAI-compatible API + Runs/SSE
        |
        | work packet + risk request
        v
Decision / Approval  ⚠️ FRAGMENTED — the one structural gap in the chain
  hermes_cli/approval_policy.py (668)       ← Action / AutonomyLevel / Decision
  tools/approval.py (1393), tools/tirith_security.py (803),
  tools/slash_confirm.py (167)              ← scattered gates
  enterprise/judge.py (170), enterprise/policy.py (171)  ← cross-check + risk table
  hermes_cli/decision_ledger.py (750)       ← post-hoc audit (not pre-exec gating)
  →→ NO unified DecisionVerdict (auto/ask/refuse). Sprint 2 unifies these.
        |
        v
Orchestrator Job Controller
  hermes_cli/orchestrator.py (1579)         ← Job lifecycle, submit/dispatch/approve/publish
  hermes_cli/orchestrator_parallel.py (638) ← thread-pool worker dispatch + cancel
  hermes_cli/job_controller.py (563)        ← filesystem-backed job store
  hermes_cli/orchestrator_ledger.py (141)   ← per-job ledger.jsonl
  hermes_cli/orchestrator_replay.py (100)   ← rebuild job snapshot from events
        |
        | worktree leases + worker prompts
        v
Worker Actuators  (produce REAL git diffs, not prose)
  hermes_cli/workers/base.py                ← WorkerAdapter (detect/prepare/run/collect/score)
  hermes_cli/workers/{claude_code,codex,aider,goose,hermes_local}.py
  hermes_cli/workers/isolation.py (796)     ← per-instance isolated spawn + logs
  hermes_cli/worktrees.py (423)             ← git worktree per job/worker, safety guards
        |
        | git diff + artifacts + logs
        v
Scoring + Merge + Validation
  hermes_cli/scoring.py (910)               ← rank diffs (16 categories)
  hermes_cli/merge_engine.py (735)          ← apply winner / detect conflicts
  hermes_cli/validation.py (1831)           ← gates: git/secrets/language/apk/remote
        |
        | validated patch + (today) approval record
        v
GitHub Publisher
  hermes_cli/github_publisher.py (888)      ← dry_run=True default, branch-per-job,
                                               secret blocking, idempotent
  plugins/github_assistant/*                ← native GitHub access
        |
        | draft/live PR
        v
Phone Approval / Recovery / History
  gateway/cockpit/server.py  /v1/cockpit/approvals[, /{id}]
  apps/android/ …/approval/ui/{screens,components}/*  ← risk-tiered approval cards
  apps/android/ …/approval/state/ApprovalStore.kt     ← persisted inbox
  service/WorkWatchService.kt               ← polling + notification (no FCM/UnifiedPush yet)
```

## Storage layout (as built)

```text
~/.hermes/
  jobs/<job-id>/ledger.jsonl                ← canonical per-job decision trail
  orchestrator/{jobs.json, approvals.json, validation.json, publish_plans.json}
  sessions/                                 ← durable conversation sessions
  cockpit/{token, events.jsonl}             ← bearer token (0600), cursor event log
  remote/audit.log.jsonl                    ← remote-bridge audit (secret-scrubbed)
  scorecards.jsonl                          ← per-task model scorecards (cost_usd, latency)

.hermes-orchestrator/                       ← per-repo (when run inside a repo)
  jobs/<job-id>/{job.json, decision_ledger.md, scorecard.md, workers/<id>/…, github/…}
  worktrees/<job-id>/<worker-id>/           ← isolated git worktrees
```

## Runtime / multi-host substrate

```text
tools/environments/base.py                  ← ExecutionEnvironment ABC
  local.py · ssh.py · docker.py · singularity.py · modal.py · daytona.py · vercel_sandbox.py
hermes_cli/jarvis_prime/worker_registry.py  ← worker lanes + branch leasing (mutex)
hermes_cli/remote_bridge.py (1226)          ← Windows file-drop bridge (allowlisted, tokened)
```

## What is NOT yet in the chain (the real backlog)

1. **Unified `DecisionVerdict`** between the work packet and every mutation
   (job create / worker exec / merge / publish / remote). *Sprint 2.*
2. **Budget gate** between routing and execution; **per-job cost/time telemetry**
   surfaced to the cockpit. *Sprint 10.*
3. **Server-side voice audio routes** (transcribe / command / response audio).
   *Sprint 8.*
4. **Supabase/Vercel API integrations** + Supabase memory provider (today they
   are local CLI planners). *Sprint 11.*
5. **Optional push** (FCM/UnifiedPush) for lock-screen approval delivery.
   *Sprint 9.*
6. **Durable worker leases** (heartbeats/expiry) + host registry + artifact
   checksums. *Sprint 13.*
7. **Bridge threat-model docs + signed-envelope (nonce/expiry/replay)** semantics.
   *Sprint 12.*

Everything else in the diagram above is implemented and tested today.
