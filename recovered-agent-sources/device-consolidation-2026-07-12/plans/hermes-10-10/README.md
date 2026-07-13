# Hermes 10/10 Full-Scope Implementation Package

This package turns the current Hermes foundation into a productized personal AI operating layer.

The plan is intentionally broad. It assumes Hermes already has substantial substrate: agent runtime, provider routing, tool registry, skill system, messaging gateway, orchestration, Android cockpit, TUI/dashboard, voice primitives, CI, security controls, and learning infrastructure. The remaining work is not another foundation rewrite; it is end-to-end product convergence around one owned loop:

> Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.

## File map

| File | Sprint | Purpose |
|---|---:|---|
| `00_SPRINT_BASELINE_AND_PROGRAM_GOVERNANCE.md` | 0 | Freeze scope, create delivery lanes, confirm current repo truth, define branch/merge policy. |
| `01_SPRINT_SYSTEM_ARCHITECTURE_AND_CONTRACTS.md` | 1 | Canonical architecture, API contracts, event model, state model, and module boundaries. |
| `02_SPRINT_DECISION_ENGINE_AND_OWNER_GATES.md` | 2 | One risk verdict system for auto/ask/refuse, audit ledger, owner approvals. |
| `03_SPRINT_WORKER_ACTUATORS_REAL_DIFFS.md` | 3 | Convert orchestration workers from Markdown proposals to real patches. |
| `04_SPRINT_MERGE_VALIDATION_AND_REPLAYABLE_JOBS.md` | 4 | Deterministic diff merge, validation gates, job ledger, resumable execution. |
| `05_SPRINT_GITHUB_PR_PUBLISHER.md` | 5 | Live GitHub PR creation behind allowlists and dry-run defaults. |
| `06_SPRINT_GATEWAY_COCKPIT_API_AND_SESSIONS.md` | 6 | Durable cockpit API, SSE/WebSocket, session replay, approval inbox backend. |
| `07_SPRINT_ANDROID_COCKPIT_PRODUCT_SURFACE.md` | 7 | Android job console, chat, approvals, pairing, diagnostics, foreground service. |
| `08_SPRINT_VOICE_FIRST_DUPLEX_LOOP.md` | 8 | Phone-recorded audio -> gateway STT -> agent -> streaming TTS back to phone. |
| `09_SPRINT_PHONE_APPROVAL_PUSH_AND_RECOVERY.md` | 9 | Push/UnifiedPush approval flow, lock-screen decisions, reconnect/replay behavior. |
| `10_SPRINT_ROUTING_TELEMETRY_AND_COST_CONTROL.md` | 10 | Skill-aware routing, per-job cost/time telemetry, dashboards, budget gates. |
| `11_SPRINT_SUPABASE_AND_VERCEL_INTEGRATIONS.md` | 11 | Product integrations needed for hosted state, deploy previews, logs, and cockpit history. |
| `12_SPRINT_REMOTE_WINDOWS_CLAUDE_BRIDGE.md` | 12 | Threat-modeled remote bridge for Claude Code on Windows. |
| `13_SPRINT_MULTI_HOST_ORCHESTRATION_AND_SCALE.md` | 13 | Multi-host worker execution, lease management, artifact sync, failure isolation. |
| `14_SPRINT_SECURITY_HARDENING_AND_RELEASE.md` | 14 | Security review, red-team pass, release checklist, docs, install/upgrade path. |

## How to run the plan with parallel agents

For each sprint:

1. Create a parent integration branch: `sprint/N-short-name`.
2. Assign each builder lane to a separate branch: `sprint/N-lane-name`.
3. Require every builder to output:
   - patch summary;
   - changed files;
   - tests run;
   - risks introduced;
   - rollback plan;
   - open questions.
4. Run reviewer lanes after builder patches exist.
5. Merge into the sprint branch only after acceptance criteria pass.
6. Merge sprint branch to `main` only after a final integration gate.

## Default agent roles

- **Architecture Agent:** owns contracts, module boundaries, ADRs, and backward compatibility.
- **Backend Builder Agent:** implements Python gateway/orchestrator/service code.
- **Android Builder Agent:** implements Kotlin/Compose UI, services, storage, and networking.
- **Worker Builder Agent:** implements Claude/Codex/Aider/Goose/Hermes-local workers and worktree mutation.
- **Security Agent:** owns threat model, secret redaction, authorization, allowlists, and abuse-case review.
- **QA Agent:** writes and runs tests; owns fixtures and regression strategy.
- **Docs Agent:** updates user docs, operator docs, API docs, and launch runbooks.
- **Reviewer Agent:** reviews diffs, comments, and produces bounded fix packets; it does not rewrite the builder branch directly.

## Global non-negotiables

- Preserve dry-run defaults for publishing, remote execution, and destructive actions.
- Every externally visible mutation must have a decision verdict and audit entry.
- No remote bridge may execute arbitrary shell text without signed command envelopes, workspace allowlists, and owner gates.
- No cockpit API may expose secrets, raw credentials, raw chain-of-thought, or unredacted logs.
- Do not weaken redactors, owner gates, lockfile checks, validation gates, or test isolation.
- Each sprint must leave `main` shippable.
