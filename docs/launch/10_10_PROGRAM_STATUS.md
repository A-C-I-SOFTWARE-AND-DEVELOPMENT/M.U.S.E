# Hermes 10/10 — Program Status (Sprint 0 baseline)

**Date:** 2026-06-05
**Branch:** `claude/bold-hawking-IQ7rn`
**Audited commit:** `adbef49`
**Plan audited against:** the 15-file `hermes_10_10_plan` package (Sprint 0–14).
**Status of this document:** Sprint 0 deliverable — the living program
baseline the plan asks for under
"Create or update `docs/launch/10_10_PROGRAM_STATUS.md`".

> **What this is.** An honest, evidence-backed map of the uploaded
> 15-sprint plan onto the *current* repository. For each sprint it
> records what actually ships (with `path:line` citations), what is
> partial, what is missing, and the single highest-leverage gap. It
> changes **no behavior** — it is a status artifact only.
>
> **What this is not.** A runtime / end-to-end verification. Evidence
> was gathered by static inspection (read + grep) of this branch at
> the commit above. Line numbers are accurate to that commit and will
> drift. Where a claim is qualified, the qualification is stated.

---

## 0. Headline

The 10/10 target is one owned loop:

> Voice/Android cockpit → gateway session → job orchestration →
> worker patch → validation gate → GitHub PR → phone approval.

**The loop is built, but unevenly.** The *production* half —
worker actuators, merge, validation, the GitHub publisher — and the
*Android surface* are deep and well-tested. The *connective tissue and
safety unification* — a single decision verdict, durable per-device
sessions/pairing, push-based approval recovery, per-job telemetry, and
the optional integrations — are where the real gaps live.

A reasonable one-line grade **at the time of the original audit** was
**~60–65%**. Since then (see *§ Update — post-merge audit* just below the
table), 23 PRs landed and an independent re-audit confirmed the decision /
approval / pairing / bridge / cost-consumer spine is wired and verified —
~80%, with the remainder being six well-scoped integration "glue" hops
rather than missing kernels. **As of the capstone update below, all six of
those hops have now landed** (PRs #317–#322): each is tested and strictly
additive, and is *either* wired into a live code path (replay route,
notify-on-decision, decision recording, pairing nav) *or* added as a tested
opt-in seam whose production caller is still pending — specifically the
cost-producer writer (no live caller yet, so real per-job cost still reads
0) and the runtime adapter (nothing injects one by default). Call it
**~85%** — the loop is closed at the *seam* level; what remains is *choosing
to use* the opt-in seams in production flows (notably a live caller +
`JobStore` drain for per-job cost), plus the Sprint-14 unified release gate
and the optional integrations (none of which are missing kernels).

### Score summary

Per-sprint grades are directional, not precise. Read the section, not
the number.

| Sprint | Surface | Grade | One-line status |
|---|---|:--:|---|
| 0 | Baseline & governance | 🟡 5/10 | Policies exist but distributed; no `docs/architecture/`; this doc closes part of it. |
| 1 | Architecture & contracts | 🟡 5/10 | Models live in code, not as named contract docs; fixtures are inline, not JSON. |
| 2 | **Decision engine & owner gates** | 🟢 8/10 | Unified `auto/ask/refuse` `DecisionVerdict` engine shipped **and wired at the publish boundary** (recorded in PR body + status). Hop: adopt it at orchestrator/merge/bridge mutation points too. |
| 3 | Worker actuators (real diffs) | 🟢 8/10 | Execute/handoff modes, worktree isolation, real diffs. Missing fixture repos + some artifacts. |
| 4 | Merge / validation / replay | 🟢 8/10 | Merge + scoring + most gates done; durable event stream + **event-sourced `JobStore.snapshot` rebuild** landed. Hop: invoke it via a route + restart-rebuild. |
| 5 | GitHub PR publisher | 🟢 8.5/10 | Dry-run default, gated live path, allowlist, secret scan, **+ verdict id in the PR body**. |
| 6 | Gateway cockpit API & sessions | 🟢 8/10 | **Per-device pairing (owner-gated, hashed-at-rest) + device tokens accepted in the auth gate.** Hop: Android pairing screen/nav; legacy shared token still plaintext. |
| 7 | Android cockpit | 🟢 9/10 | All surfaces real, secure token storage, state machines, ~123 tests. Pairing client/VM added (nav-wiring pending). |
| 8 | Voice-first duplex | 🟡 6/10 | STT/TTS stack + privacy + barge-in solid; **gateway audio duplex routes incomplete**. |
| 9 | Phone approval push & recovery | 🟡 6.5/10 | **Approval race rules wired** (idempotent/expired/superseded) + local-SSE notification provider + enqueue-on-create. Hops: notify-on-decision (clear pending), optional push provider. |
| 10 | Routing / telemetry / cost | 🟡 7/10 | Budget kernel + **per-job cost consumer wired** (`/status`). Hop: producer glue so cost auto-accumulates from real runs. |
| 11 | Supabase & Vercel | 🔴 1.5/10 | Supabase absent; Vercel is sandbox-exec only (no deploy/preview/logs). |
| 12 | Windows Claude bridge | 🟢 8/10 | **Signed envelope (HMAC+nonce+expiry) wired into the bridge — opt-in, backward-compatible; forged/expired/replayed rejected, nonce persisted.** Hop: threat-model docs + key rotation ops. |
| 13 | Multi-host orchestration | 🟡 6/10 | Lease kernel + durable store + host registry + **observational lease recording in the runner**; `RuntimeAdapter` Protocol + pure reschedule policy added (standalone). Hop: runner→adapter integration + reschedule loop. |
| 14 | Security hardening & release | 🟡 5/10 | Release artifacts distributed; no unified 10/10 gate, smoke script, or `doctor --10-10`. |

Legend: 🟢 mostly done · 🟡 partial · 🔴 missing/weak.

### Update — 2026-06-05 (post-merge audit)

Since the original audit above, **23 PRs landed on `main`** (9 kernels, 4
wirings, 3 features, 4 follow-ups, 3 producers/clients). An independent
re-audit of `main` (read-only, four parallel sweeps) confirms the following
are **wired and verified — no regressions**:

- Unified decision verdict at the publish boundary → `hermes_cli/github_publisher.py` (status + `## Decision` block in the PR body).
- Approval race rules in `gateway/cockpit/handlers.py::approvals_decide` (`resolve_decision`: idempotent / expired / superseded / phrase-gated).
- Per-device pairing — `pair/confirm` is **owner-phrase-gated** (`handlers.py`), tokens **hashed at rest** (`device_pairing.py` + `cockpit_token.py`); device tokens accepted in `auth.authorize_bearer` (fail-closed, revoke-aware).
- Per-job cost **consumer** + budget on `/status` (`orchestrator_api.update_worker` → `accumulate_cost`).
- **Signed bridge envelope** (`bridge_envelope.py` ↔ `remote_bridge.py`): opt-in/backward-compatible, forged/expired/replayed rejected, key never logged or auto-generated, nonce persisted across restart.
- Observational worker-lease recording in `orchestrator_parallel.py` (best-effort; execution unchanged).

**Remaining = six integration "glue" hops** (the kernels exist and are
tested; only the wiring into live paths is left):

1. **Cost producer** — `agent.conversation_loop.build_usage_record`, the `orchestrator_parallel` `usage.json` sidecar, and `iter_worker_usage` have **no non-test callers**; a worker must write the sidecar and a dispatcher must drain `iter_worker_usage → JobStore.update_worker` so per-job cost auto-accumulates (today it stays 0 in real runs).
2. **Replay** — `JobStore.snapshot` (rebuild-from-events) is invoked nowhere live; expose it via a route + a restart-rebuild path (the Sprint 14 "restart mid-job → replay" gate).
3. **Notify-on-decision** *(UX bug)* — `approvals_decide` never clears the pending alert (`PendingApprovalQueue.resolve` / a "decided" notify are uncalled), so a phone shows "approval pending" forever after a grant.
4. **decision_engine breadth** — only the publisher records a verdict; orchestrator dispatch/submit, merge, and remote bridge still use ad-hoc phrase/`approval_policy` checks.
5. **Runtime adapter + scheduler** — `hermes_cli/runtime_adapter.py` + `lease_scheduler.py` have **zero importers**; wire `ParallelRunner` to run workers through a `RuntimeAdapter` + a reschedule loop using `reschedule_plan`.
6. **Android pairing nav** — `DevicePairingClient`/`DevicePairingViewModel` are built and persist correctly, but there's **no `DevicePairingScreen` and no nav route**, so the flow is unreachable.

Optional / unchanged: Supabase (S11) absent; Sprint 14 unified release-gate /
smoke / `doctor --10-10` still distributed; the legacy *shared* cockpit token
remains plaintext-at-rest (per-device tokens are hashed).

### Update — 2026-06-05 (glue-hops complete)

All **six** integration glue-hops listed in the post-merge audit have now
landed on `main` (PRs #317–#322), each strictly additive / opt-in with the
existing default path unchanged. Each is *tested*; four are *wired into a
live path* (hops 2–4, 6) and two are *tested opt-in seams whose production
caller is still pending* (hop 1 cost writer, hop 5 runtime adapter). Where a
hop closes an API/seam but the production-default wiring is deliberately
deferred, the residual follow-up is named on the function and repeated here
— no overclaiming.

1. **Cost producer — done (emit seam).** `orchestrator_parallel.write_usage_sidecar`
   (#322) is the supported, atomic producer counterpart to the existing
   `iter_worker_usage` drain; it no-ops on the `None` an empty turn yields and
   stays free of the agent runtime (takes the already-built
   `build_usage_record` block). *Residual:* no in-repo agent-worker subprocess
   calls it yet, so per-job cost still reads 0 in a real run until a worker
   emits — the live caller and the `ParallelRunner → JobStore` auto-drain
   remain follow-ups (documented on `iter_worker_usage` / `write_usage_sidecar`).
2. **Replay — done (route).** `GET /jobs/{id}/snapshot` (#317) exposes
   `rebuild_snapshot`. *Residual:* `JobStore` is in-memory; restart-rebuild
   persistence is deferred.
3. **Notify-on-decision — done.** `approvals_decide` now calls
   `resolve_and_notify` (#318) so a decided approval clears the phone's pending
   alert instead of showing "pending" forever.
4. **decision_engine breadth — done.** A unified `DecisionVerdict` is now
   recorded at the orchestrator dispatch/merge and remote-bridge mutation
   points, not only the publisher (#320).
5. **Runtime adapter + scheduler — done (opt-in).** `ParallelRunner` can run a
   LOCAL_RUN worker through an injected `RuntimeAdapter` and compute a
   reschedule plan (#321). Placement-bearing workers (cwd / env / worktree)
   stay on the inline path; the reschedule plan *decides, it does not act*;
   adapter cancellation is bounded by `timeout_seconds`. *Residual:* nothing
   injects an adapter by default, and ssh/docker adapters are stubs.
6. **Android pairing nav — done.** `DevicePairingScreen` + a `Screen.Pairing`
   route + a Settings entry make the (already-correct) pairing client/VM
   reachable, with an owner-phrase-gated confirm (#319).

**Net:** the 10/10 loop is closed *at the seam level* — every kernel is now
either wired into a live path (hops 2–4, 6) or available as a tested,
additive opt-in seam (hops 1 and 5), all covered by tests. The remaining
work is no longer "missing kernels" but: (a) opting the opt-in seams into
production use — a live caller + runner→JobStore drain so real per-job cost
stops reading 0 (hop 1), and a default adapter injection (hop 5); (b) replay
persistence behind the snapshot route (hop 2); (c) the Sprint-14 unified
release gate / `doctor --10-10`; and (d) the optional integrations (Supabase
S11). The shared-cockpit-token-at-rest note above is unchanged.

### Critical path to close the loop

In dependency order — each unblocks the next and the Sprint 14 release gate:

1. **Sprint 2 — unify the decision verdict.** Everything downstream
   (publish, merge override, remote dispatch, phone approval) should
   hang off one `auto/ask/refuse` verdict. This is the #1 architectural
   gap; the cockpit cannot render "the verdict" because there isn't one.
2. **Sprint 4 / 6 — event-sourced job state + reconnect.** A durable
   cursor event feed already exists (`event_log.py`); make job snapshots
   reconstructable from events so the Sprint 14 "restart mid-job →
   replay" gate passes deterministically.
3. **Sprint 6 — real device pairing + durable sessions.** Replace the
   single shared cockpit token with per-device pairing, hashed tokens at
   rest, and immediate revocation. Required for a trustworthy phone client.
4. **Sprint 9 — approval push + race rules.** The "phone approval" leg
   of the loop is the least implemented. Add the notification provider
   seam and the decided-once / expired / superseded / idempotent rules.
5. **Then** Sprint 10 telemetry and (only if remote is in launch scope)
   Sprint 12 bridge hardening.

Sprints 7 (Android), 3 (workers), 5 (publisher) are effectively ahead of
the rest and are not on the critical path.

---

## 1. Reconciling with prior audits

This is **not** the repo's first 10/10 assessment. Earlier, *Phase*-numbered
audits cover the same vision and remain valid context:

- `docs/audits/hermes-10-10-gap-report.md` — Phase 00 gap report (2026-05-23), scored the product ~6.5/10.
- `docs/orchestration/final-10-10-readiness-report.md` & `docs/audits/hermes-final-10-10-readiness-report.md` — Phase 24 readiness.
- `docs/audits/hermes-known-limitations.md` — Phase 27 honesty contract.
- `docs/product/hermes-10-10-product-spec.md` — canonical product spec.

The uploaded package re-frames that vision as **Sprints 0–14 with parallel
agent lanes**. The two numbering systems describe the same program; this
document maps the *sprint* structure and supersedes the older gap report
for sprint-plan tracking. Where the older docs and current code disagree,
**current code wins** and is cited below.

---

## 2. Per-sprint findings

### Sprint 0 — Baseline & program governance · 🟡 PARTIAL

- 🔴 `docs/launch/10_10_PROGRAM_STATUS.md` — was absent; **this file** is it.
- 🟡 `docs/launch/PROTECTED_PATHS_10_10.md` — no such file, but a "Global
  protected paths" policy exists at `docs/launch/LAUNCH_BRANCH_MATRIX.md:43`.
- 🔴 `docs/architecture/` directory **does not exist** at all (affects S0 & S1).
- 🟡 Branch-naming / merge-queue policy — distributed across
  `docs/launch/AUTOMATED_MERGE_POLICY.md`, `AUTO_MERGE_RUNBOOK.md`,
  `LAUNCH_BRANCH_MATRIX.md`.
- 🟡 Per-surface current-state docs — partial equivalents exist
  (`docs/api/local-orchestrator-api.md`, `docs/android/hermes-apk-cockpit.md`)
  but not under the plan's exact paths; no `docs/gateway/` dir.

**Gap:** governance is real but scattered and unbranded; no single
architecture map. This doc + a protected-paths file would largely close it.

### Sprint 1 — Canonical architecture & contracts · 🟡 PARTIAL

Strong in **code**, weak in **named contract docs**.

- 🟢 `WorkPacket` — `hermes_cli/jarvis_prime/work_packet.py:86` (full dataclass + validation).
- 🟢 `WorkerArtifacts` — `hermes_cli/workers/base.py:88`.
- 🟢 `DecisionLedger` — `hermes_cli/decision_ledger.py` (the verdict *record*).
- 🟡 `JobEvent` — exists as an event vocabulary + dicts
  (`hermes_cli/orchestrator_events.py`), not one canonical class.
- 🔴 `CockpitSession` — no such class; session state is split across
  `gateway/session.py` and `hermes_cli/job_queue.py`.
- 🔴 Named contract docs (`10_10_system_architecture.md`,
  `cockpit_v1_openapi.md`, `event_stream_contract.md`,
  `work_packet_schema.md`, `decision_verdict_contract.md`,
  `ADR-10-10-product-loop.md`) — absent; `docs/adr/` does not exist.
- 🔴 JSON fixtures under `tests/fixtures/...` — absent; tests use inline
  factories / `conftest.py` instead.

**Gap:** the system is real but under-specified on paper. The biggest
*conceptual* hole is the missing canonical `DecisionVerdict` (see S2).

### Sprint 2 — Unified decision engine & owner gates · 🔴 WEAK (the central gap)

- 🔴 **No single auto/ask/refuse engine.** Decisioning is fragmented across:
  `hermes_cli/approval_policy.py:120` (`Decision` = ALLOW/CONFIRM/DENY),
  `enterprise/policy.py:23` (`Risk` = LOW/MEDIUM/HIGH),
  `enterprise/judge.py:39` (`JudgeVerdict`), and merge-time policy gates in
  `hermes_cli/merge_engine.py`. (The `verdict` symbols in
  `hermes_cli/jarvis_prime/self_audit/` and `tools/skills_guard.py` are a
  *different* domain — self-audit/skill trust — not the action verdict.)
- 🔴 No `DecisionVerdict` / `DecisionInput` models, no `merge_decision_inputs`
  tier-merge (refuse-wins / ask-wins / auto-only-if-all-auto), no reason-code
  enum (`PROTECTED_PATH`, `SECRET_DETECTED`, `LIVE_PUBLISH`, …).
- 🟢 Owner phrase — `hermes_cli/jarvis_prime/owner_auth.py:20`
  (`"Yes, with authorization."`, exact match) + `OWNER_GATED_ACTIONS` set.
- 🟢 Durable approval/audit store — `hermes_cli/approval_policy.py:615`
  (`~/.hermes/approval.log` JSONL) + `enterprise/audit.py:156`
  (per-session JSONL, replay at `:176`).
- 🟡 Decision checks are *not* uniformly wired at every mutation point;
  the publish boundary has no engine call.
- 🟡 Tests cover tiers in pieces (`tests/test_approval_policy.py`,
  `tests/test_jarvis_prime_owner_auth.py`) but no unified-engine test.

**Gap (the program's #1):** there is no one place that returns *the*
verdict. Until S2 lands, the cockpit/phone cannot render a single
rationale, and S5/S9/S12 each re-implement partial gating.

### Sprint 3 — Worker actuators that produce real diffs · 🟢 MOSTLY DONE

- 🟢 `WorkerAdapter` ABC + 5-step contract — `hermes_cli/workers/base.py:134`;
  `WorkerStatus` (`HANDOFF_REQUIRED`/`EXECUTED`/`COMMAND_NOT_FOUND`/`FAILED`) at `:181`.
- 🟢 Execute-vs-proposal per worker via `execute: bool` —
  `aider.py:110`, `claude_code.py:89` (`RUN_MODE_*`), `codex.py`, `goose.py`, `hermes_local.py`.
- 🟢 Worktree isolation, no worker in repo root — `hermes_cli/workers/isolation.py`
  (per-instance branch + worktree at `:224`/`:247`).
- 🟢 Safe degrade when CLI missing → `COMMAND_NOT_FOUND` (`aider.py:147`).
- 🟡 Artifact layout differs from plan: real path is under
  `.hermes-orchestrator/agents/<job>/<worker>/<instance>/`, not
  `~/.hermes/jobs/...`; `prompt.md`/`stdout.log`/`stderr.log`/`state.json`/
  `patch.diff` are written, but `diffstat.json`/`notes.md`/`risk-report.json`
  were not found.
- 🔴 QA fixtures absent: no `tests/fixtures/repos/{python_tiny,…}` and no
  `fake_*_worker.py`.
- 🟡 Allowed/forbidden enforcement is strong at the publish boundary
  (`github_publisher.py:312`) but post-execution per-worker enforcement and a
  centralized command allowlist are thin.

**Gap:** deterministic fixture repos + fake workers, and the missing
artifacts, to make worker output fully testable and decision-ready.

### Sprint 4 — Merge engine, validation gates, replayable jobs · 🟡 PARTIAL

- 🟢 Merge engine — `hermes_cli/merge_engine.py` (winner selection +
  high-risk-no-tests / secrets / score-floor gates at `:121`).
- 🟢 Scoring — `hermes_cli/scoring.py:50` (16 categories).
- 🟢 Validation gates — `hermes_cli/validation.py` (1,831 lines): structure,
  tests (pytest/node/gradle), secrets (staged/unstaged/blocked-paths), plus
  many extra gates (git, ruff, shell syntax, remote tunnel/workers/queue).
- 🟡 **Missing named gates:** unicode/encoding, dependency-lock, Android
  manifest (only APK-binary checks), and a *policy/decision-verdict* gate.
- 🟢 **Durable, replayable event stream** — `gateway/cockpit/event_log.py`
  writes `~/.hermes/cockpit/events.jsonl` and serves cursor reads via
  `read_since_offset()` (`:71`). This is real and survives restart.
- 🟡 Orchestration broker — `hermes_cli/orchestrator_events.py` is an
  *in-memory* pub/sub with bounded per-job replay (`:146`); not durable.
- 🔴 **No event-sourced job rebuild.** Job state is durable as a `job.json`
  snapshot (`hermes_cli/job_controller.py:256`), not reconstructed from the
  event log; no `test_job_replay`.

**Gap:** the event *feed* is replayable; the *job* is not reconstructable
from events. Sprint 14's "restart mid-job → replay" gate needs the latter.

### Sprint 5 — Live GitHub PR publisher behind safe defaults · 🟢 MOSTLY DONE

- 🟢 Dry-run default — `hermes_cli/github_publisher.py:787` (`approve=False`
  → `dry_run=True` at `:842`); live needs `approve=True` + a PAT, and at the
  gateway also owner phrase + loopback (`gateway/cockpit/handlers.py:2019`).
- 🟢 Repo allowlist + writes off by default — `plugins/github_assistant/config.py:42`/`:46`.
- 🟢 Controlled branch prefix `hermes/job-<slug>` — `github_publisher.py:450`;
  no destructive git (`:24`).
- 🟢 Secret scan before publish — `github_publisher.py:806` (patterns at `:354`).
- 🟢 Gateway routes — `…/jobs/{id}/publish` and `…/publish/preview`
  (`gateway/cockpit/handlers.py:1943`/`:1995`).
- 🟡 PR body has the job id but no explicit *validation summary* / *verdict id* block (`:607`).
- 🟡 Idempotency is **per-branch** (409 on existing PR), not a per-job-id ledger.
- 🟡 Tests cover dry-run + secret blocking + approval gating
  (`tests/test_github_publisher.py`, `tests/gateway/test_cockpit_publish.py`);
  missing: allowlist-refusal, idempotency, log-redaction.

**Gap:** wire the (future) S2 verdict id + validation summary into the PR
body, and make idempotency job-id-keyed.

### Sprint 6 — Gateway cockpit API & durable sessions · 🟡 PARTIAL

The cockpit backend lives at `gateway/cockpit/server.py` + `handlers.py`
(not `gateway/platforms/api_server.py` as the plan assumed — a naming drift).

Routes (present unless noted):
- 🟢 `GET /v1/health` (`server.py:48`), `GET /v1/cockpit/diagnostics` (`:51`).
- 🟢 `GET/POST /v1/cockpit/jobs`, `GET …/jobs/{id}` (`:86`/`:87`/`:111`).
- 🟢 `GET /v1/cockpit/approvals`, `POST …/approvals/{id}` decide (`:120`/`:121`).
- 🟢 `GET /v1/cockpit/events` (offset/since cursor) + `…/events/stream` SSE (`:78`/`:169`).
- 🔴 `POST /v1/cockpit/pair/start`, `…/pair/confirm`, `GET /v1/cockpit/session` — **absent.**

Sessions / auth:
- 🔴 **No mobile pairing flow.** Cockpit auth is a single persisted shared
  bearer token (`gateway/cockpit/auth.py:39`); per-device pairing exists only
  for DM/CLI (`gateway/pairing.py`, with short-lived codes + rate-limit +
  lockout — good, but not wired to the mobile cockpit).
- 🔴 Token stored as plaintext compare, not hashed at rest; no immediate revocation.
- 🟢 Reconnect-since-cursor works via the durable event log (see S4).
- 🟢 Loopback binding default; diagnostics redact secrets.
- 🟡 Tests: `tests/gateway/test_cockpit_api.py`, `test_cockpit_events_stream.py`,
  `test_pairing.py` (CLI pairing) — no revocation or mobile-pairing test.

**Gap:** real per-device pairing + hashed/revocable tokens. This is the
phone-trust prerequisite for S9.

### Sprint 7 — Android cockpit product surface · 🟢 DONE (strongest sprint)

All ten surfaces ship as real screens, not stubs:
- Onboarding (`ui/screens/onboarding/OnboardingScreen.kt`), Home
  (`ui/screens/home/JarvisPrimeHomeScreen.kt`), Jobs list
  (`ui/screens/jobs/JobsScreen.kt`), Job detail + ledger timeline
  (`JobDetailScreen.kt`, `ui/screens/ledger/LedgerTimelineScreen.kt`),
  coding/patch surfaces (`ui/screens/coding/*`), approval inbox
  (`approval/ui/screens/ApprovalsScreen.kt`), diagnostics
  (`ui/screens/diagnostics/DiagnosticsScreen.kt`), settings
  (`ui/screens/settings/SettingsScreen.kt`), foreground service
  (`service/HermesService.kt`).
- 🟢 Secure token storage — `data/cockpit/SecureTokenStore.kt`
  (EncryptedSharedPreferences, AES-256, Keystore master key).
- 🟢 State machines — `JobStatus` / `ApprovalStatus` enums incl.
  EXPIRED/EMERGENCY_STOPPED + risk tiers (`data/cockpit/CockpitApi.kt`,
  `approval/model/Models.kt:26`).
- 🟢 Manifest permissions are scoped and intentional (RECORD_AUDIO,
  POST_NOTIFICATIONS, FOREGROUND_SERVICE*, etc. — `AndroidManifest.xml`).
- 🟢 ~123 test files under `app/src/test`.

**Gap:** none structural. It will need the *backend* gaps (S6 pairing, S9
push) to light up end-to-end on a real device.

### Sprint 8 — Voice-first duplex loop · 🟡 PARTIAL

- 🟢 Python voice stack — `tools/voice_mode.py`, `tools/transcription_tools.py`
  (6 STT providers), `tools/tts_tool.py` (9 TTS providers), `hermes_cli/voice.py`.
- 🟢 Android voice — system STT (`AndroidSpeechRecognizerStt.kt`), TTS
  (`AndroidTtsEngine.kt`), barge-in (`VoiceLoop.kt:120`), services + tests.
- 🟢 Privacy — push-to-talk first / no always-on default (`PresenceMode.kt`),
  transcript redaction (`voice_intake.py:redact_transcript`), explicit
  two-step approval ceremony (`VoiceApprovalCoordinator.kt:49`,
  driving-mode veto server-side).
- 🟡 Gateway routes partial: `POST /v1/cockpit/voice/intake` + `…/{id}/decide`
  exist (`server.py:125`/`:126`), but the plan's
  `/voice/transcribe`, `/voice/command`, `/voice/responses/{id}/audio` are
  **absent** — today's flow passes a *transcript string*, not raw-audio
  upload → STT → streamed-TTS-audio back.

**Gap:** the true audio duplex (phone audio in, synthesized audio out over
the gateway) is not wired; the text-transcript path is.

### Sprint 9 — Phone approval push & recovery · 🔴 WEAK (least implemented)

- 🔴 No `NotificationProvider` interface, no subscription backend, no pending-
  approval push queue (searched gateway + plugins).
- 🔴 No FCM and no UnifiedPush. (Upside: nothing forces Google services —
  the SSE/loopback path works without push.)
- 🔴 Approval race rules largely absent: no expiry, no supersession, no
  duplicate-decide idempotency guard in `handlers.py:2537`; owner-phrase
  check is present (`:2547`).
- 🟢 Android has the approval *inbox* UI + repository (S7) — but no push /
  deep-link / offline-reconcile path verified.
- 🔴 No disconnect/expired/duplicate/revoked recovery tests.

**Gap:** the entire push + recovery layer. This is the biggest backend hole
in the actual *loop* and should follow S2/S6.

### Sprint 10 — Skill-aware routing, telemetry, cost control · 🟡 PARTIAL

- 🟢 Deterministic router — `hermes_cli/model_router.py:163` (`RoutingDecision`
  with `selected`, `rejected` + reasons, `explanation`/`rationale`); route fn at `:430`.
- 🟡 Selection is per-*category* (primary + validators + publisher), not a
  minimized per-task fan-out; no `budget` field in the decision output.
- 🟡 Telemetry is per-*call* (`agent/usage_pricing.py`, `agent/account_usage.py`,
  `jarvis_prime/model_scorecard.py:57`) — no per-*job* aggregate.
- 🟡 Budget: a `cost_ceiling` rank is filtered at router input (`:258`) but no
  soft→ask verdict and no hard-stop.
- 🔴 No cockpit telemetry panel (no job cost/elapsed/retry route or UI).
- 🟢 Routing tests (`tests/test_model_router.py`); 🔴 no budget-decision tests.

**Gap:** per-job telemetry aggregation + cockpit panel + soft/hard budget gates.

### Sprint 11 — Supabase & Vercel integrations · 🔴 MOSTLY MISSING

- 🔴 Supabase — **absent**. No `plugins/supabase/`, no memory backend, no
  ledger mirror. (Memory backends exist for byterover/honcho/mem0/supermemory/…
  but not Supabase.) Note: a Supabase **MCP server** is available to this
  session, but that is *not* an in-repo plugin.
- 🟡 Vercel — only a sandbox *execution* adapter (`tools/environments/vercel_sandbox.py`)
  and a `vercel-worker` reference in the router (`model_router.py:137`); no
  deploy/preview/logs/env operations.
- 🔴 No mocked integration tests.

**Gap:** essentially the whole sprint, by design optional. Fine to defer
unless hosted state / deploy previews are launch-scoped.

### Sprint 12 — Secure remote Windows Claude bridge · 🟡 PARTIAL

- 🟢 Bridge code is mature: `hermes_cli/remote_bridge.py` (dispatch / poll /
  collect + append-only audit at `:401`), `hermes_cli/workers/claude_code_windows.py`,
  `hermes_cli/gateway_windows.py`.
- 🟢 Device allowlist (`remote_bridge.py:253`), per-job random `auth_token`,
  secret scrubbing; tests in `tests/test_remote_bridge.py`,
  `tests/test_worker_claude_code_windows.py`.
- 🔴 **No signed-envelope security model.** `JobManifest` (`:324`) lacks
  explicit `signature`, `nonce`, and `expires_at` — the plan's
  non-negotiable. No replay/expiry/workspace-escape tests.
- 🔴 Threat-model docs absent (`windows_bridge_threat_model.md` et al.);
  only the user guide `docs/remote/windows-claude-code-bridge-guide.md` exists.

**Gap:** the bridge *works* but does not yet meet the plan's signed/nonce/
expiry + threat-model bar. Treat as red until that lands.

### Sprint 13 — Multi-host orchestration & scale · 🟡 PARTIAL (lean)

- 🟢 Runtime abstraction — `tools/environments/base.py:288` (`BaseEnvironment`
  ABC) with Local/Docker/SSH/Singularity/Modal/Daytona/VercelSandbox adapters.
- 🟢 `WorkerLease` state machine + durable store landed:
  `hermes_cli/worker_lease.py` (acquire/heartbeat/expire/complete, `can_retry`)
  and `hermes_cli/worker_lease_store.py` (durable JSONL lease store + host
  registry: `register_host`/`hosts`, `for_job`/`active`/`expire_stale`).
- 🟢 Host-execution adapter layer + reschedule policy landed (Sprint 13,
  additive, fully tested):
  - `hermes_cli/runtime_adapter.py` — `@runtime_checkable` `RuntimeAdapter`
    Protocol (`host_id`/`kind`/`prepare`/`run`→`RuntimeResult`/`cleanup`),
    concrete `LocalRuntimeAdapter` (subprocess, streams→files, timeout→124),
    documented `SSHRuntimeAdapter`/`DockerRuntimeAdapter` stubs.
  - `hermes_cli/lease_scheduler.py` — pure `reschedule_plan(now, hosts, leases)`
    that reschedules only EXPIRED + idempotent leases (`can_retry`) to the
    least-loaded registered host; deterministic, clock-injected.
- 🟡 Content-addressed artifacts exist for *evidence* (jarvis_prime), but job
  worker artifacts are not checksummed for cross-host distribution.
- 🟡 Host registry exists in the lease store; multi-host worker status is not
  yet surfaced to the cockpit.
- 🟡 Failure-isolation rules: duplicate-completion-after-expiry reject is
  enforced by the lease kernel; checksum-refuse / host-failure containment
  still absent. Single-host parallel runner is solid
  (`hermes_cli/orchestrator_parallel.py`, tests in `test_parallel_*`).

**Deferred (next step):** wire `RuntimeAdapter`/`lease_scheduler` into the
runner — have `orchestrator_parallel.ParallelRunner` spawn `LOCAL_RUN` workers
through a `RuntimeAdapter` selected per `host_id` from the lease store's host
registry, and act on each `Reschedule` (acquire a fresh lease on the chosen
host, append a ledger entry). The adapters + scheduler are standalone and pure
so this is a runner-side change with no kernel/store edits.

### Sprint 14 — Security hardening & release · 🟡 PARTIAL

- 🟡 Release artifacts exist but are *distributed/unbranded*:
  `docs/launch/LAUNCH_READINESS_CHECKLIST.md`, `LAUNCH_GATE_CHECKLIST.md`,
  `CLAUDE_FINAL_RELEASE_REVIEW.md`, `docs/audits/hermes-release-checklist.md`,
  `docs/orchestration/prompt-to-pr-demo.md`, `docs/voice/voice-first-user-guide.md`.
- 🔴 No unified `10_10_RELEASE_CHECKLIST.md` / `10_10_E2E_RUNBOOK.md` /
  `10_10_SECURITY_REVIEW.md`.
- 🔴 No `scripts/hermes-10-10-smoke.sh`; a `tests/e2e/` dir exists but no
  10/10 smoke; `scripts/hermes-orchestrate.sh` is the closest runner.
- 🔴 `hermes_cli/doctor.py` exists (large) but has **no `--10-10`** readiness flag.

**Gap:** a single launch gate + repeatable smoke + `doctor --10-10` that
exercises the E2E matrix in the plan.

---

## 3. Cross-cutting drift (plan ↔ repo)

Worth fixing in any contract pass so later sprints cite reality:

- **Cockpit API location:** plan says `gateway/platforms/api_server.py`;
  reality is `gateway/cockpit/server.py` + `handlers.py`.
- **Worker artifact path:** plan says `~/.hermes/jobs/<job>/workers/<worker>/`;
  reality is under the repo's `.hermes-orchestrator/` tree.
- **Decision engine module:** plan says `hermes_cli/decision_engine.py` or
  `enterprise/decision.py`; neither exists — logic is fragmented (S2).
- **"DecisionVerdict":** plan treats it as a canonical type; repo has a
  `DecisionLedger` *record* but no verdict *tier* type.
- **Contracts as docs:** plan expects `docs/architecture/`, `docs/adr/`,
  and JSON fixtures; repo keeps contracts in code + inline test factories.

---

## 4. What's genuinely strong today

So the audit reads as honest and not only negative:

- **Android cockpit (S7)** — production-grade, secure storage, real state
  machines, deep test coverage.
- **Worker actuators (S3)** — real isolated-worktree execution with safe
  proposal fallback.
- **Publisher (S5)** — dry-run-default, multiply-gated live path, secret scan.
- **Validation + merge (S4)** — broad gate coverage and deterministic merge.
- **Durable cockpit event feed (S4/S6)** — append-only JSONL with cursor
  replay already powers SSE reconnect.
- **Owner gates + audit (S2)** — the exact-phrase gate and append-only audit
  log are in place; they just need a single verdict to sit behind.

---

## 5. Method & limitations

- Evidence gathered by static inspection (read + grep) across six parallel
  passes covering all 15 sprints, on `claude/bold-hawking-IQ7rn` @ `adbef49`.
- Not a runtime or end-to-end execution test; "present" means the code/route/
  test exists and reads as wired, not that it was run green here.
- Line numbers are accurate to the audited commit and will drift; treat
  `path:line` as a pointer, not a permalink.
- Grades are directional. The per-sprint prose is the source of truth.
