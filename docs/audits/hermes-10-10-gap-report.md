# Hermes Agent — 10/10 Product Gap Report (Phase 00)

**Date:** 2026-05-23
**Branch:** `claude/hermes-repo-audit-TZ26F`
**Pairs with:** `docs/audits/hermes-full-repo-audit.md`,
`docs/audits/hermes-file-inventory.md`

This document grades the current Hermes repo against the **10/10
product vision**:

> Hermes is a **mobile-native, voice-first, autonomous AI agent
> orchestrator** for Jeremiah. It runs as a local/private developer
> command center, coordinates multiple coding agents, executes or
> hands off work to Claude Code on a Windows workstation through a
> secure remote execution bridge, integrates GitHub / Supabase /
> Vercel and related tools, validates every decision, preserves
> state across disconnects, and surfaces everything through an
> Android/Flutter cockpit.

For every dimension the report lists: what's present, what's
missing, the implementation risk, and where the work goes.

---

## Score summary

| Dimension | Today | Notes |
|---|---|---|
| Core agent runtime | **10/10** | `run_agent.py` + `agent/` is production-grade. |
| Provider coverage | **10/10** | 22+ providers, direct + plugin paths, fallback wiring. |
| Tool surface (built-in) | **10/10** | 95 tools, registry-discovered, lazy-installed. |
| Skill system | **10/10** | 200 SKILL.md, slash invocation, hub, provenance, autocomplete. |
| Messaging gateway | **10/10** | 22+ platforms, unified slash registry, session continuity. |
| TUI / dashboard | **9/10** | Ink TUI + browser dashboard via PTY. No "ops cockpit" panel for orchestrated jobs. |
| Orchestration substrate | **10/10** | Phase 24 declared 10/10. Foundation is right. |
| **Worker actuators (mutate code)** | **3/10** | Proposals only; no patches; documented limitation. |
| **Voice-first cockpit UX** | **3/10** | Primitives exist; not the default surface; no duplex Android voice loop. |
| **Mobile cockpit (Android)** | **4/10** | Skeleton + screens exist; cockpit API not all live; no push, no full auth flow. |
| **Remote Windows Claude Code bridge** | **2/10** | Handoff worker exists; no secure remote-execution agent. |
| **Live GitHub publisher** | **5/10** | Dry-run is real; live transport is a caller seam. |
| **Supabase integration** | **0/10** | No plugin, no tool, no memory backend. |
| **Vercel integration** | **3/10** | Sandbox env + ai-gateway only; no deploy/preview/logs. |
| **Decision-quality unification** | **6/10** | Tirith + approval + policy + judge exist but not fused into one verdict. |
| **State across disconnects** | **6/10** | SQLite + jobs.json exist; no durable replayable cockpit session. |
| **Skill-aware routing** | **2/10** | Every job pays 6× fan-out; no skill pre-route. |
| **Cost/time telemetry** | **3/10** | Per-call usage tracked; no per-job aggregate, no cockpit chart. |
| **Multi-host orchestration** | **2/10** | Threadpool-only; spec'd in `next-roadmap.md` §2. |
| **Validation gates (count)** | **6/10** | 5 of 8 spec'd gates implemented. |

**Weighted product score:** ~6.5 / 10. The substrate is at 10/10; the
**productized end-to-end loop for Jeremiah** is at ~5–6/10.

---

## Gap 01 — Voice-first cockpit UX

**Today.**
`tools/voice_mode.py` (1,018 LOC) runs a push-to-talk / silence-
detect loop. `tools/transcription_tools.py` (936 LOC) wraps
faster-whisper + cloud STT backends. `tools/tts_tool.py` (2,289
LOC) wraps edge-tts (default), ElevenLabs, OpenAI, MiniMax, NeuTTS.
`hermes_cli/voice.py` (846 LOC) exposes a process-wide voice API
the TUI gateway can call. The `/voice` slash command toggles modes.

**Missing for 10/10.**

1. **Voice is the default surface on Android**, not a CLI toggle.
   The cockpit needs a push-to-talk mic in every screen.
2. **Duplex voice over the gateway** — record on phone, stream to
   gateway STT, agent reasons, TTS streams back to phone as the
   tokens arrive. Today STT/TTS run on the same host as the agent.
3. **On-device STT/TTS** for low-latency + offline. Whisper.cpp
   via NNAPI for STT; on-device TTS for the common phrases.
4. **Wake word ("Hermes")** — opt-in; explicit privacy posture.
5. **Voice approval flow** — "approve dangerous command Y/N"
   should accept a spoken yes/no with verification.

**Risk.** Medium. The Python primitives exist; the cockpit and
Termux gateway need wiring. Privacy posture for always-on
microphone needs care.

**Where work goes.**
- `apps/android/app/.../ui/screens/orchestrator/` — add voice
  composer.
- New `apps/android/app/.../voice/` package for STT/TTS bridges
  (Android NNAPI Whisper, on-device TTS, fallback to gateway).
- `gateway/platforms/api_server.py` — duplex audio routes.
- `tools/voice_mode.py` — extract a non-CLI duplex variant.
- `docs/android/` — voice UX spec.

---

## Gap 02 — Production cockpit wiring (Android ↔ gateway)

**Today.**
The Android cockpit (`apps/android/`, Kotlin + Compose) has
screens for `splash`, `settings`, `orchestrator` + detail,
`diagnostics`. The `CockpitApi.kt` HTTP client is in place.
`docs/android/hermes-apk-api-contract.md` specifies every route
(jobs, approvals, sessions, push, SSE). Only `/v1/health` is
live in `gateway/platforms/api_server.py`.

**Missing for 10/10.**

1. **Live routes**: `/v1/chat`, `/v1/jobs`, `/v1/jobs/{id}`,
   `/v1/approvals`, `/v1/sessions`, `/v1/notifications/subscribe`
   per the contract.
2. **SSE / WebSocket** for live job tails and chat streaming.
3. **Push notifications** — FCM or a self-hosted equivalent
   (Unified Push) so the user gets approval requests on the
   lock screen.
4. **Pairing / device-trust flow** — currently spec'd in
   `gateway/pairing.py` but no Android-side onboarding.
5. **Auth** — bearer token in `EncryptedSharedPreferences` works
   today; lacks rotation + revocation.
6. **Foreground service for in-flight jobs** — `HermesService.kt`
   is a shell; needs to keep the SSE channel alive across screen-off.

**Risk.** Low–medium. The contract is spec'd; the implementation
is mechanical.

**Where work goes.**
- `gateway/platforms/api_server.py`
- `gateway/run.py` (route registration)
- `apps/android/app/.../service/HermesService.kt`
- `apps/android/app/.../data/cockpit/CockpitApi.kt`
- New `apps/android/app/.../data/push/` package.

---

## Gap 03 — Secure remote Windows Claude Code bridge

**Today.**
`hermes_cli/workers/claude_code.py` is a **handoff** worker: it
writes a prompt + status file into a workspace dir and waits for
the user to run `claude` against it. There is **no remote
execution path**.

**Missing for 10/10.**

1. **Bridge agent** on the Windows workstation (PowerShell or
   small Rust/Go service installed via `winget`/MSI). Runs as a
   user-mode service; reads from a signed-command queue.
2. **Reverse tunnel** — WireGuard, Tailscale, or Cloudflare
   Tunnel — so the phone-side cockpit can reach the workstation
   without exposing it to the internet.
3. **Command queue** — append-only signed-message queue. Phone
   pushes "run Claude Code with prompt X in workspace Y";
   bridge runs `claude` non-interactively; result is uploaded
   back as a worktree patch + status JSON.
4. **Per-workspace allowlist** — bridge refuses workspaces
   outside an explicit list.
5. **Hardware-key approval** (optional) — high-risk commands
   require a touch on a YubiKey at the workstation.
6. **Bridge crash-safe** — bridge restarts cleanly; queue is
   durable; idempotent retries.

**Risk.** **High.** This is the single highest-risk item in the
build because:
- A poorly-scoped bridge becomes a remote-code-execution loophole.
- Command-injection containment is hard.
- The cockpit must NOT be the place where Windows secrets live.

**Threat-model first.** Don't write a line of bridge code until
the threat model is approved.

**Where work goes.**
- New `bridge/windows/` directory (Rust or Go preferred for a
  small static binary).
- `hermes_cli/workers/claude_code.py` — add a `remote_bridge`
  execution mode behind `allow_execute=True` + bridge URL config.
- `docs/orchestration/workers/claude-code-worker.md` — bridge
  section.
- `enterprise/policy.py` — `tier: remote_windows_claude` risk
  policy.

---

## Gap 04 — Worker actuators (proposal → patch)

**Today.**
Workers return Markdown proposals. The merge engine, gates, and
publisher are built to handle real proposals (per Phase-24
readiness report), but no worker actually mutates files.
Limitation §1–2 in `docs/orchestration/known-limitations.md`.

**Missing for 10/10.**

1. Each worker's `_execute` shells out to its real tool
   (Codex CLI, `claude` CLI, Aider, Goose) inside the
   worktree.
2. The worktree contains a real `git diff` after execution.
3. Merge engine operates on diffs (3-way merge if multiple
   workers' diffs touch the same file).
4. Conflict policy is deterministic.

**Risk.** Medium. Each worker is one file change; the open
question is patch-conflict semantics when six diffs disagree.

**Where work goes.**
- `hermes_cli/workers/{claude_code,codex,aider,goose,hermes_local}.py`
- `hermes_cli/merge_engine.py`
- `tests/test_worker_*.py`

---

## Gap 05 — Live GitHub publisher transport

**Today.**
`hermes_cli/github_publisher.py` emits a `PublishDescriptor`
(PR or issue). Live mode requires a caller-supplied transport
which the default build does NOT ship. `plugins/github_assistant/`
is a working REST client with allowlist + write-block.

**Missing for 10/10.**

1. Ship a transport that uses `plugins/github_assistant/client.py`
   (REST) or the GitHub MCP server when available.
2. Default remains dry-run. `HERMES_PUBLISH_LIVE=1` plus a
   per-repo allowlist enables live posting.
3. Smoke test against a fixture repo in CI.

**Risk.** Low. The wiring is small; the policy decision (which
repos can be published to) is the load-bearing part.

**Where work goes.**
- `hermes_cli/github_publisher.py` (`_default_transport`)
- `plugins/github_assistant/client.py` (already does most of it)
- `.github/workflows/orchestration-tests.yml` (smoke against fixture)

---

## Gap 06 — Decision-quality policy unification

**Today.** Four overlapping decision surfaces:

- `tools/tirith_security.py` — content-level shell command guard.
- `tools/approval.py` + `tools/slash_confirm.py` — TTY approval gate.
- `enterprise/policy.py` + `enterprise/judge.py` — enterprise policy.
- Orchestration gates in `hermes_cli/validation.py` —
  `structure`, `size`, `secrets`, `unicode`, `policy`.

Each fires independently; the cockpit can't render "the verdict"
because there's no single verdict.

**Missing for 10/10.**

1. A single risk-tiered **DecisionVerdict** type
   (`tier ∈ {auto, ask, refuse}`, `rationale`, `inputs[]`).
2. One engine that calls each guard and merges the result.
3. Cockpit renders the verdict + rationale; can override (with
   audit ledger entry).
4. `/decision-ledger show <id>` returns the verdict per mutation.

**Risk.** Low–medium. Mostly a refactor + new module.

**Where work goes.**
- New `enterprise/decision.py` or `hermes_cli/decision_engine.py`
  to host the unified verdict.
- `tools/tirith_security.py`, `tools/approval.py`,
  `enterprise/policy.py`, `enterprise/judge.py` — adapt to
  return `DecisionInput`.
- `hermes_cli/orchestrator.py` — call the engine at the publish
  boundary.
- `apps/android/.../ui/screens/orchestrator/` — verdict pane.

---

## Gap 07 — Supabase integration

**Today.** Zero. The only `supabase` matches in the repo are
example strings inside a creative skill.

**Missing for 10/10.**

1. `plugins/supabase/`:
   - `auth` tools (sign-in/sign-up/magic-link)
   - `db` tool (SQL via PostgREST or supabase-py)
   - `storage` tool
   - `edge-functions` trigger
   - `realtime` subscription (optional)
2. **Memory backend** wrapper at `plugins/memory/supabase/` that
   speaks the existing memory-provider protocol (mirror of
   `plugins/memory/honcho/`).
3. **Decision-ledger sink** — write `~/.hermes/orchestrator/
   decision_ledger.json` entries to Supabase as well, so the
   cockpit can query history without the phone reaching the
   laptop.

**Risk.** Low. supabase-py is mature.

**Where work goes.**
- `plugins/supabase/` (new)
- `plugins/memory/supabase/` (new)
- `hermes_cli/config.py` — add `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
  `SUPABASE_SERVICE_ROLE_KEY` to `OPTIONAL_ENV_VARS`.

---

## Gap 08 — Vercel integration (beyond sandbox + gateway)

**Today.**
`tools/environments/vercel_sandbox.py` is a terminal-environment
backend. `plugins/model-providers/ai-gateway/` uses Vercel AI
Gateway as a model provider. `hermes_cli/vercel_auth.py` reports
auth status. No native deploy/preview/logs.

**Missing for 10/10.**

1. `plugins/vercel/`:
   - `deploy` tool (project + deployment)
   - `preview_url` tool (after a PR is opened)
   - `logs_tail` tool (runtime + build logs)
   - `env` tool (read/write project env vars)
   - `cancel_deployment` tool
2. Cockpit shows the preview URL inline after a PR job.
3. Optional: `vercel rollback` tool for safe revert.

**Risk.** Low. Vercel REST API is well-documented; the `vercel`
PyPI extra is already in `pyproject.toml`.

**Where work goes.**
- `plugins/vercel/` (new)
- `hermes_cli/config.py` — `VERCEL_TOKEN` already known.
- `apps/android/.../ui/screens/orchestrator/TaskDetailScreen.kt`
  — preview-URL chip.

---

## Gap 09 — State across disconnects

**Today.**
`hermes_state.py` (SQLite + FTS5) stores sessions.
`~/.hermes/jobs/<id>/` keeps per-job state + decision ledger.
Resume works (`/resume`, `/sessions`). But the **cockpit-side
identity** is not durable: a phone reboot loses in-flight chat
context unless the same gateway session is rejoined.

**Missing for 10/10.**

1. **CockpitSession** — a long-lived identity stored on the
   phone (UUID + last-known cursor + last-seen event id).
2. **Replay-on-reconnect** — when the cockpit reconnects,
   gateway replays missed SSE events from the cursor.
3. **Crash-safe job tail** — job tail file is append-only;
   resume reads from the cursor offset.
4. **Approval inbox** — pending approvals survive cockpit
   restart and pop up on the next launch.

**Risk.** Low–medium. Requires a small event-id scheme + a
durable cursor store.

**Where work goes.**
- `gateway/session.py` — add `event_id` per published event.
- `gateway/platforms/api_server.py` — `/v1/events?since=<id>`.
- `apps/android/.../data/cockpit/CockpitApi.kt` — cursor handling.
- `apps/android/.../data/cockpit/CockpitSession.kt` (new).

---

## Gap 10 — Skill-aware routing

**Today.** Every `/orchestrate` job fans out to all six workers.
The pre-route step in `docs/orchestration/next-roadmap.md` §10
is not implemented.

**Missing for 10/10.**

1. Pre-orchestration step inspects the task prompt against the
   skills index (`scripts/build_skills_index.py` output).
2. Tasks that match a single skill route to a constrained
   subset of workers.
3. Routing decision recorded under `task.metadata.routing`.

**Risk.** Low.

**Where work goes.**
- `hermes_cli/orchestrator.py` — `_select_workers(task)` helper.
- `skills/index-cache/` (already exists) — extend with a
  worker-affinity field.

---

## Gap 11 — Cost + time telemetry

**Today.** Per-API-call usage is tracked in `agent/account_usage.py`
+ `agent/usage_pricing.py`. No per-job aggregate, no cockpit
chart, no Prometheus textfile output.

**Missing for 10/10.**

1. Per-worker `cost_estimate_cents` + `elapsed_seconds` +
   `tokens_used` (zero for local).
2. Per-job aggregate at `.hermes/runs/run-<id>.json`.
3. Prometheus textfile when `HERMES_TELEMETRY_DIR` is set.
4. Cockpit "last 30 days" chart.

**Risk.** Low.

**Where work goes.**
- `hermes_cli/workers/base.py` — `report_costs()` hook.
- `hermes_cli/orchestrator.py` — aggregate + persist.
- New `hermes_cli/telemetry.py`.
- `web/src/pages/AnalyticsPage.tsx` — chart.
- `apps/android/.../ui/screens/orchestrator/` — chart.

---

## Gap 12 — Multi-host orchestration

**Today.** In-process `ThreadPoolExecutor`. Multi-host is item
§2 in `docs/orchestration/next-roadmap.md`.

**Missing for 10/10.**

1. Queue-based dispatcher (Redis or SQLite wrapper).
2. Worktrees on a shared filesystem or rsync'd over SSH.
3. Worker auth (each host has its own token).

**Risk.** High. Coordination + partial-failure semantics get
hairy. **Defer until single-host actuators are rock-solid
(Gap 04).**

**Where work goes.**
- New `hermes_cli/dispatcher/` package.
- Refactor `hermes_cli/orchestrator.py` to depend on dispatcher
  rather than `ThreadPoolExecutor` directly.

---

## Gap 13 — Replay + re-arbitration

**Today.** No `hermes-orchestrate replay`.

**Missing for 10/10.**

1. `muse orchestrate replay <job-id>` loads
   `.hermes/runs/run-<id>.json`, re-runs the arbiter + merge
   engine, writes a fresh artefact, and diffs against original.
2. Deterministic when weights unchanged.

**Risk.** Low.

**Where work goes.**
- `hermes_cli/orchestrator.py` — new subcommand.
- `tests/test_orchestrator_replay.py` (new).

---

## Gap 14 — More validation gates

**Today.** Five gates (`structure`, `size`, `secrets`, `unicode`,
`policy`).

**Missing for 10/10.** Three more per `next-roadmap.md` §8:
- `tests` gate: re-runs `pytest -q` inside merged worktree.
- `style` gate: runs `ruff check` if present.
- `policy.skill` gate: rejects skill changes without a SKILL.md
  `version` bump.

**Risk.** Low.

**Where work goes.**
- `hermes_cli/validation.py` (or `hermes_cli/orchestrator.py`
  depending on where the substrate's `GATES` table lives).
- `tests/test_validation_gates.py` — add pass + fail per gate.

---

## Gap 15 — Mobile wake-word / hotkey

**Today.** None.

**Missing for 10/10.**

1. Opt-in on-device wake-word ("Hermes") via Porcupine,
   Vosk, or Whisper-tiny.
2. Quick-tile (Android) for one-tap mic.
3. Wear-OS companion (stretch).

**Risk.** Low–medium. Privacy posture and battery testing matter.

**Where work goes.**
- `apps/android/.../voice/WakeWord.kt` (new).
- `apps/android/app/src/main/AndroidManifest.xml` — Quick Settings tile.

---

## Risk map (sorted by build risk × blast radius)

| Gap | Risk | Blast radius | Order |
|---|---|---|---|
| 03 Remote Windows Claude Code bridge | **High** | RCE potential on workstation | Phase 04 (after 01–03 land) |
| 12 Multi-host orchestration | High | Partial-failure corruption | Defer to Phase 12 |
| 04 Worker actuators | Medium | Patch conflicts | Phase 03 |
| 01 Voice-first cockpit UX | Medium | Always-on mic privacy | Phase 01 |
| 02 Cockpit API wiring | Low–medium | Cockpit dead until live | Phase 02 |
| 06 Decision-quality unification | Low–medium | Approval semantics drift | Phase 06 |
| 09 State across disconnects | Low–medium | Lost approvals | Phase 10 |
| 11 Cost telemetry | Low | None | Phase 09 |
| 05 Live GitHub publisher | Low | Accidental PR (gated) | Phase 05 |
| 07 Supabase plugin | Low | None | Phase 07 |
| 08 Vercel native | Low | None | Phase 08 |
| 10 Skill-aware routing | Low | None | Phase 09 |
| 13 Replay | Low | None | Phase 10 |
| 14 More gates | Low | None | Phase 11 |
| 15 Wake-word | Low–medium | Always-on mic privacy | Phase 13 |

---

## Strategic build order (with exit criteria)

Mirrors the recommendation in
`docs/audits/hermes-full-repo-audit.md`. Each phase touches at
most one of the five orchestration primitives (Job / Worker /
Model routing / Validation gate / Decision ledger), per the
"don't invent a sixth primitive" rule in `AGENTS.md`.

### Phase 01 — Voice-first cockpit (push-to-talk)
- Wire `/v1/chat` SSE on the gateway.
- On-device push-to-talk STT (Whisper.cpp via NNAPI; fallback
  to gateway STT).
- TTS playback in cockpit.
- **Exit:** spoken question → spoken answer end-to-end on a
  real Android device against a real gateway.

### Phase 02 — Cockpit API surface
- Implement spec'd Phase-18 routes (`/v1/jobs*`, `/v1/approvals`,
  `/v1/sessions`, `/v1/notifications/subscribe`).
- SSE for live job tails.
- Foreground service keeps SSE alive.
- **Exit:** cockpit can start `/orchestrate`, watch live tail,
  approve a gate, see the published artefact.

### Phase 03 — Worker actuators (Claude Code first)
- `claude_code` worker mutates its worktree, emits a real diff.
- Merge engine consumes diffs.
- **Exit:** a `/orchestrate` run produces a real diff inside
  `.hermes/worktrees/claude-<task>` and merge engine outputs
  a real combined patch.

### Phase 04 — Remote Windows Claude Code bridge
- Threat model signed off first.
- Bridge agent on Windows (Rust or Go; user-mode service).
- Reverse tunnel via Tailscale or Cloudflare Tunnel.
- Signed command queue; per-workspace allowlist.
- **Exit:** cockpit triggers a `claude_code` job whose
  execution actually runs on the Windows workstation; the
  resulting diff round-trips back; the bridge refuses any
  workspace not in its allowlist.

### Phase 05 — Live GitHub publisher transport
- Wire `plugins/github_assistant/client.py` as the default
  transport.
- Per-repo allowlist.
- Smoke against fixture repo in CI.
- **Exit:** with `HERMES_PUBLISH_LIVE=1` and a token in
  `HERMES_GITHUB_TOKEN`, a successful run creates a draft PR.

### Phase 06 — Decision-quality policy unification
- Single `DecisionVerdict` engine fusing tirith + approval +
  policy + judge.
- Cockpit verdict pane.
- **Exit:** every mutation has one verdict; cockpit renders +
  can override; override is logged.

### Phase 07 — Supabase plugin
- `plugins/supabase/` tools + memory backend.
- Decision-ledger sink option.
- **Exit:** a job's decision ledger can be queried in Supabase
  from the cockpit without reaching the laptop.

### Phase 08 — Vercel native integration
- `plugins/vercel/` deploy/preview/logs/env.
- Cockpit shows preview URL after PR job.
- **Exit:** PR job → preview URL chip in cockpit; tap → opens.

### Phase 09 — Skill-aware routing + cost telemetry
- Pre-route based on skills index match.
- Per-job cost aggregate persisted to `.hermes/runs/`.
- **Exit:** a clearly-routable task does not pay 6× fan-out;
  cockpit shows last-30-days cost.

### Phase 10 — State preservation + replay
- Cockpit-side durable identity + cursor.
- `hermes-orchestrate replay <job-id>`.
- **Exit:** killing the cockpit mid-run and reopening shows
  uninterrupted state; replay is deterministic for unchanged
  weights.

### Phase 11 — More validation gates
- `tests` (pytest), `style` (ruff), `policy.skill` (SKILL.md
  version bump).
- **Exit:** 8 gates total; each has pass + fail test;
  `scripts/hermes-orchestrate.sh` exit code reflects them.

### Phase 12 — Multi-host orchestration
- Replace in-process executor with dispatcher.
- **Exit:** workers fan out across ≥ 2 hosts; the six
  proposals are still collected before scoring.

### Phase 13 — Wake-word + ambient voice mode (opt-in)
- On-device wake word.
- Quick-tile.
- **Exit:** phone wakes on word with explicit privacy posture;
  default off.

---

## Anti-goals (don't do these)

- **Don't rewrite the agent loop.** `run_agent.py` and the
  conversation loop are correct; every gap is a *surface*
  problem (cockpit, bridge, plugin), not a *brain* problem.
- **Don't fork the kanban substrate.** The kanban DB is dense
  and load-bearing for orchestration.
- **Don't re-implement the primary chat experience in React.**
  AGENTS.md is explicit — the chat surface is the embedded
  TUI via PTY. The cockpit is a control surface, not a chat
  surface.
- **Don't add a sixth orchestration primitive.** Job / Worker /
  Model routing / Validation gate / Decision ledger is enough.
- **Don't bypass the lazy-deps policy.** Provider-specific deps
  belong in `tools/lazy_deps.py`, not base `dependencies`.
- **Don't introduce ranged dependency pins** without a written
  exception (Shai-Hulud policy in `pyproject.toml`).
- **Don't write the Windows bridge before the threat model is
  signed off.**
- **Don't expose `HERMES_PUBLISH_LIVE=1` by default.**

---

## Acceptance for "10/10 product reached"

The product is at 10/10 the day **all** of the following are
true:

1. Jeremiah can stand at his kitchen counter, hold up his
   phone, say *"Hermes, audit the hermes-agent repo and open a
   draft PR"*, and watch the live job tail on the cockpit. The
   PR opens. The preview URL appears as a chip. He taps it.
2. A spoken "approve" gates the publish step.
3. A `claude_code` worker job dispatches to his Windows
   workstation through the bridge, produces a real diff, and
   the cockpit shows the diff before merge.
4. The decision-ledger surfaces one verdict per mutation with
   rationale.
5. Closing the cockpit and reopening it five minutes later
   resumes the job tail from the exact cursor.
6. No third-party cloud sees a request the user didn't approve
   (per `private-local-mode.md`).
7. The CI matrix (tests + lint + orchestration-tests +
   supply-chain + android-build) is green.
8. `pytest` and `scripts/hermes-orchestrate.sh` exit cleanly on
   a fresh Termux install.

Until every one of those is true, this gap report is the
backlog.
