# Hermes — Ten-out-of-Ten Product Specification

> **Status:** Canonical product spec. When this disagrees with any other
> document in `docs/product/`, this file wins.
>
> **Companion docs:**
> - [`muse-mobile-native-vision.md`](muse-mobile-native-vision.md)
> - [`muse-user-journeys.md`](muse-user-journeys.md)
> - [`muse-definition-of-done.md`](muse-definition-of-done.md)
> - [`muse-private-local-mode.md`](muse-private-local-mode.md)
> - [`muse-plain-english-principles.md`](muse-plain-english-principles.md)

---

## 1. Product thesis

Hermes is a **mobile-native, voice-first, autonomous coding command
center**. One person should be able to ship production-grade software
from a phone — while driving, walking, cooking, parenting, sleeping —
by issuing a prompt and trusting Hermes to research, plan, get
approval, implement, validate, and publish without further hand-holding.

The product is built on four immovable beliefs:

1. **The phone is the cockpit, not the cabin.** The Android app is
   where intent is captured, decisions are approved, and progress is
   monitored. It is voice-first, glanceable, and safe to use one-handed.
   It is not where compilation happens.
2. **The backend is the engine.** A Hermes backend — running on a
   VPS, home server, workstation, or Termux on the phone itself —
   owns execution, state, workers, validation, memory, and publishing.
   The phone never holds the source of truth.
3. **External AI tools are workers, not authorities.** Windows
   Claude Code, Codex, Aider, Goose, ChatGPT, Cursor, Copilot —
   all are interchangeable workers behind the same orchestration
   contract. None of them dictate Hermes's behavior; Hermes routes
   each job to whichever worker the routing policy and the
   `ai-improvement-radar` say is best for that job.
4. **Every prompt is a managed job with explicit phases.** Research,
   plan, approval, implementation, validation, and publishing are
   distinct phases with explicit artifacts, gates, and audit entries.
   No phase is silently merged into another. No artifact is published
   without passing the gate before it.

### The user we are building for

Jeremiah ships code from his phone, often while away from a desk and
sometimes while driving. He owns multiple repos, several
Supabase/Vercel projects, a Windows workstation he can reach
remotely, and a fleet of AI tools whose interfaces all differ. He
wants:

- One place to start any job, by voice, from his phone.
- Confidence that the job will not silently lose state if the network
  flaps, the phone sleeps, or the worker crashes.
- Plain-English explanations of every decision — *why* this worker,
  *why* this model, *why* this branch, *why* this gate failed.
- The ability to say "approve" or "reject" with one tap, at the
  right moments, and never to be ambushed by a destructive action
  he did not authorize.
- All of this to work offline-safe (private/local mode) when the
  data is sensitive or the network is gone.

### What this spec is not

- Not a roadmap. Roadmaps live under `docs/plans/` and
  `docs/orchestration/next-roadmap.md`.
- Not an implementation plan for a specific phase. Phase plans live
  under `docs/orchestration/PHASES.md` and per-phase prompts.
- Not a UI design doc. Screen-level UX lives under `docs/android/`.

This spec defines the **bar** every Hermes release is measured
against. If a capability listed here is not 10/10, Hermes is not
done.

---

## 2. Architectural shape

```
+---------------------------------------------------------+
|  Cockpit (Android / Flutter app)                        |
|    voice capture · job dashboard · approval gates       |
|    plain-English explanations · driving mode            |
+---------------------------------------------------------+
                          | TLS / loopback
                          v
+---------------------------------------------------------+
|  Hermes backend (CLI + gateway + orchestrator)          |
|    job controller · phase gates · decision ledger       |
|    validation · memory · routing · publishing           |
+---------------------------------------------------------+
        |               |              |              |
        v               v              v              v
+-------------+ +-------------+ +-----------+ +-----------+
| Windows     | | Cloud LLMs  | | Local     | | External  |
| Claude Code | | (Anthropic, | | models    | | services  |
| Codex CLI   | |  OpenAI,    | | (llama.cpp| | (GitHub,  |
| Aider,Goose | |  OpenRouter)| |  vLLM,    | |  Supabase,|
| over SSH /  | |             | |  Ollama)  | |  Vercel)  |
| WireGuard   | |             | |           | |           |
+-------------+ +-------------+ +-----------+ +-----------+
```

Three rules:

1. **Cockpit never executes jobs.** It only captures intent, shows
   state, and arms switches.
2. **Backend never trusts a worker's self-report.** Every claimed
   success is re-validated by the gate the job promised.
3. **Workers are stateless from Hermes's point of view.** State
   lives in the job folder (`~/.hermes/jobs/<job-id>/`) and the
   decision ledger. Any worker can crash and be re-spawned without
   data loss.

---

## 3. Core user journeys (summary)

The full narrative of each journey — voice transcript, screens,
backend state transitions, ledger entries, fallback paths — lives
in [`muse-user-journeys.md`](muse-user-journeys.md). The ten
journeys this spec commits to:

1. **Voice prompt while driving** → safe hands-free job capture.
2. **Prompt → research → plan → approval → implementation** — the
   five-phase canonical flow.
3. **Prompt → GitHub repo audit** — read-only diagnostic job.
4. **Prompt → Claude Code on Windows remote execution** — worker
   on a separate machine, results streamed back.
5. **Prompt → Supabase / Vercel deployment plan** — integration
   workers produce a plan, never deploy without approval.
6. **Prompt → GitHub PR** — the canonical "ship it" flow.
7. **Prompt → failed network recovery / resume** — job survives
   network drops, phone sleep, backend restart.
8. **Prompt → model / tool selection explanation** — *why this
   worker, why this model*, in plain English.
9. **Prompt → validation report** — what was tested, what passed,
   what failed, what was skipped and why.
10. **Prompt → learn from mistake and update profile** — the
    self-improvement loop closes on every job.

---

## 4. Required product capabilities

| # | Capability | Owner module(s) | Notes |
|---|---|---|---|
| C1  | Mobile-native app shell (Android-native today; Flutter is the **future-state** target) | `apps/android/` | See [`muse-mobile-native-vision.md`](muse-mobile-native-vision.md) for the decision rationale. |
| C2  | Voice-to-text pipeline | cockpit + gateway STT adapter | On-device first; cloud STT only with explicit opt-in. |
| C3  | Optional continuous hands-free listening mode | cockpit | Off by default. Opt-in per session, with visible "listening" indicator. |
| C4  | Driving-mode restrictions and safety boundaries | cockpit | No destructive taps; voice-only confirmation; large-target UI. |
| C5  | Local job controller | `agent/` + orchestrator | Owns phase state machine; survives crashes via checkpoint. |
| C6  | Secure remote Windows execution bridge | new `workers/windows-claude-code/` | SSH + WireGuard / Tailscale; explicit allowlist of paths and commands. |
| C7  | Multi-agent spawning | orchestrator + kanban worker plugin | Independent lanes run in parallel; dependent lanes wait. |
| C8  | Isolated workers | `tools/environments/` (docker, ssh, modal, singularity, local-worktree) | One worker per worktree; no shared state outside the job folder. |
| C9  | Phase gates | orchestrator + judge | Research → Plan → Approval → Implementation → Validation → Publish, each gated. |
| C10 | Persistent queue | SQLite kanban board + `~/.hermes/jobs/` | Resumes after reboot. |
| C11 | Checkpointing | job folder + decision ledger | Any phase can resume from its last good checkpoint. |
| C12 | Validation loops | local validation gates, judge, auto-lint/auto-test | Every promise is verified; nothing self-attests. |
| C13 | Monitoring | cockpit dashboard + gateway SSE + `muse orchestrator status` | Live state per job. |
| C14 | User profile learning from GitHub history | `plugins/github_assistant/` + memory | Extracts style, naming, review tone, preferred libraries. |
| C15 | Secrets management | `~/.hermes/.env` + EncryptedSharedPreferences on device | No secret ever crosses the cockpit→backend boundary in cleartext over an untrusted network. |
| C16 | GitHub / Supabase / Vercel integrations | first-party plugins | Read-only by default; mutating actions gated. |
| C17 | Plain-English explanations | `plain-english-principles` skill + judge output | Every decision is explainable in one paragraph a non-engineer can read. |

A capability is **only** complete when it satisfies the matching row
in §5 below and the corresponding entry in
[`muse-definition-of-done.md`](muse-definition-of-done.md).

---

## 5. 10/10 acceptance criteria

The bar. Each row defines what 10/10 looks like and how it is verified.

### 5.1 Cockpit and capture

| Capability | 10/10 Behavior | Validation |
|---|---|---|
| Mobile-native app shell | App cold-starts in < 2 s on a mid-tier Android phone; resumes prior session state from cache; never blocks the UI on a network call; layout works one-handed in portrait at 360 dp width. | Synthetic startup test in CI; manual one-handed walkthrough recorded per release; Lighthouse-style budget enforced. |
| Voice-to-text pipeline | "Long-press mic → speak → release" produces a transcript visible within 1 s of release; user can edit before dispatch; cloud STT only used when user has opted in; STT failures degrade to "type instead", never silently drop the prompt. | Latency budget tested with synthetic audio clips; opt-in flag asserted in instrumentation; fallback path covered by an Espresso test. |
| Continuous hands-free listening | Off by default. When enabled, a persistent foreground notification + on-screen banner + LED-style mic icon indicate the mic is hot. Wake-word required before any prompt is captured. Session auto-ends after a user-configurable timeout. Recording is never transmitted off-device without an explicit per-prompt confirmation tone or visual cue. | Mic state surfaced via instrumentation; integration test verifies wake-word gating; privacy doc lists every byte that leaves the device. |
| Driving-mode restrictions | When driving mode is on (manual toggle or Android Auto / car-Bluetooth detection), the UI shows only voice controls + a large "End" button; no destructive action is reachable; approvals require spoken confirmation phrase, not a tap; visual diffs are summarized aloud, never shown as code on the screen. | Espresso test for the restricted surface; CarPlay/Auto-style heuristics covered by unit tests; safety checklist signed-off per release. |
| Plain-English explanations on every screen | Every job card, every gate decision, every model choice carries a one-paragraph plain-English "why" the user can tap to expand. No raw JSON, no opaque model names, no acronyms without expansion. | Screenshot diff per screen vs. a "no jargon" lint; reviewer signs off per release; see [`muse-plain-english-principles.md`](muse-plain-english-principles.md). |

### 5.2 Job lifecycle and orchestration

| Capability | 10/10 Behavior | Validation |
|---|---|---|
| Local job controller | Every prompt becomes a `Job` with a deterministic ID, a folder under `~/.hermes/jobs/<id>/`, a status state machine (`captured → researching → planning → awaiting_approval → implementing → validating → publishing → done | blocked | failed`), and an append-only `decision-ledger.jsonl`. State transitions are atomic. | State machine unit tests; ledger schema test; crash-recovery test (kill -9 in each phase, verify resume). |
| Phase gates (Research → Plan → Approval → Implementation → Validation → Publish) | No phase begins until the previous phase's artifact passes its gate. The Approval gate is the **only** phase that may pause indefinitely waiting for the user; all others have explicit timeouts and escalations. | Integration test per gate; "gate skipped" failure path tested; ledger entry per transition. |
| Multi-agent spawning + isolated workers | Independent lanes in the task graph spawn in parallel, each in its own worktree (`git worktree add`) or container; lanes that depend on a parent block until the parent's gate passes; no two workers ever write to the same path at the same time. | Concurrency stress test (5 lanes, 10 minutes); worktree isolation test; conflict detection test. |
| Persistent queue + checkpointing | If the backend is killed at any point, restarting it picks every in-flight job up at the last checkpoint with no human action. The cockpit reflects the restart within 5 s. Long jobs (≥ 1 h) checkpoint at least every 60 s of wall time. | Restart drill in CI (kill -9 every 30 s during a 5-min job); checkpoint cadence asserted from ledger timestamps. |
| Network recovery / resume | If the cockpit loses connection mid-stream, it reconnects with exponential backoff and replays missed events from the gateway's SSE buffer. If the backend loses connection to a remote worker, it pauses the worker's lane (not the whole job) and surfaces a "worker unreachable" card with **Retry** and **Reassign** actions. | Chaos test that drops the link every 30 s; SSE replay test; "worker unreachable" surfaced in cockpit within 10 s. |
| Validation loops | Every job declares its validation contract up front (tests, lint, type-check, smoke-run, manual review). The validation phase runs that contract verbatim; results are written to `validation-report.md`; the gate cannot be bypassed without an explicit "override" decision logged to the ledger with the operator's identity. | Validation contract schema test; bypass requires explicit flag asserted in integration test; report shape asserted against a fixture. |
| Monitoring | The cockpit dashboard updates each job card in < 2 s of a backend state change; `muse orchestrator status <job-id>` matches the cockpit byte-for-byte; the gateway emits SSE events that any other client can subscribe to without polling. | SSE latency budget enforced; CLI-vs-cockpit diff test; long-poll fallback test for clients without SSE. |

### 5.3 Workers, models, and integrations

| Capability | 10/10 Behavior | Validation |
|---|---|---|
| Secure remote Windows execution bridge | Hermes can dispatch a job to Windows Claude Code on a workstation reachable over Tailscale / WireGuard / SSH; the worker runs only commands in the job's allowlist; stdout/stderr stream back over an authenticated channel; the workstation never holds long-lived secrets that the backend does not own. | Pen-test checklist; allowlist enforced by tests; "command not on allowlist" returns a refusal logged to the ledger. |
| GitHub integration (`github_assistant`) | Read operations (repo metadata, file contents, PR diffs, comment threads) require no extra approval. Mutating operations (push, comment, PR create/merge, label) are gated through the approval phase and logged to the ledger with the exact API call. | Mutation gate test; ledger entry test; read-only happy path covered by integration test against a fixture. |
| Supabase integration | Read operations (list_tables, get_logs, get_advisors) are free. Schema changes (`apply_migration`, `execute_sql` with DDL, branch delete, project pause) are gated and logged. Cost-incurring actions require `confirm_cost` to have run first. | DDL detection test; cost gate test; advisor-before-change suggestion test. |
| Vercel integration | Read operations (list deployments, get build logs) are free. Deploy operations are gated and the gate's plan output includes the diff between the deployed and to-be-deployed commits. | Diff test; deploy gate test. |
| Model / tool selection explanation | Every job's `decision-ledger.jsonl` carries a `routing_decision` entry naming the worker, the model, and the *radar score* and *cost / latency budget* that won. The cockpit surfaces this as plain English: *"Sent to Windows Claude Code on Opus 4.7 because it has the best score on Python refactors this week and the job is under your latency budget."* | Ledger schema test; cockpit copy lint; radar score availability test (falls back to defaults with a "fallback" reason if radar is stale). |
| User profile learning from GitHub history | On first use of a repo, Hermes mines the user's prior commits / PRs / reviews and writes `~/.hermes/profiles/<github-user>/style.md`, `preferences.md`, `review-tone.md`. The profile is referenced by every routing and code-generation decision in that repo and re-mined periodically. The user can read, edit, or delete the profile at any time. | Profile schema test; "user edited profile is respected over re-mining" test; consent flow asserted before the first mine. |
| Secrets management | Secrets live in `~/.hermes/.env` on the backend and in EncryptedSharedPreferences on the cockpit. No secret is logged. No secret is sent to a worker that is not on the secret's allowlist. Cockpit→backend traffic is TLS or loopback only. | Secret-in-log detector in CI; allowlist enforced by tests; TLS pinning verified on the cockpit. |

### 5.4 Self-improvement and learning

| Capability | 10/10 Behavior | Validation |
|---|---|---|
| Learn from mistakes and update profile | Every failed or grudgingly-accepted job triggers a retrospective under `memory/longterm-memory/retrospectives/`. The retrospective produces at least one proposed change to the routing policy, a skill, or the user profile. Proposed changes are surfaced in the cockpit as a "Hermes wants to learn this" card; the user approves or rejects with one tap. | Retrospective generation test; "no proposed change" treated as a CI warning; cockpit card asserted by Espresso test. |
| Validation report quality | The validation report is a Markdown document a non-engineer can read. It lists what was promised, what was tested, what passed, what failed, what was skipped, and *why*. No raw stack traces unless explicitly requested. | Validation-report lint (no raw tracebacks at top level); user-readability check per release. |
| Plain-English explanations end-to-end | Any user can ask the cockpit "Why did Hermes do X?" and receive a one-paragraph answer grounded in a ledger entry, a profile rule, or a radar score. No dead-ends ("I don't know"); if the source is missing, the answer says exactly what is missing and what to do. | "Why" query test against a fixture job; missing-source path tested; readability score (Flesch-Kincaid grade ≤ 9). |

---

## 6. Non-functional bar

| Property | 10/10 target |
|---|---|
| Cockpit cold start | < 2 s on a 2022-era mid-tier Android phone |
| Voice-to-prompt latency | < 1 s after release (on-device STT); ≤ 3 s round-trip with cloud STT |
| Backend RSS at idle | < 250 MB per Hermes process |
| Crash-free sessions | ≥ 99.5 % over a rolling 7-day window |
| Cockpit→backend connection drops | recoverable in ≤ 10 s with no user action |
| Time from prompt to first ledger entry | ≤ 2 s |
| Time from approval tap to worker spawn | ≤ 5 s |
| Local-only mode | Zero outbound DNS / TCP outside loopback or LAN, end-to-end |
| Offline capability | Cockpit can read cached job state and draft new prompts with no network; dispatch is queued until reconnect |

---

## 7. Out of scope (for the 10/10 bar)

These are real product needs but they do **not** gate the 10/10
designation:

- A web cockpit (the Android app is primary; web is a follow-on).
- An iOS cockpit (planned for the post-10/10 phase).
- A managed cloud Hermes service (Hermes ships as software the user
  runs; managed hosting is a separate product).
- Image / vision input to the prompt builder (text + voice only at 10/10).
- Multi-user / team mode (single-operator at 10/10).

When the 10/10 bar is met across §5, the door opens for these
additions, not before.

---

## 8. Open questions tracked elsewhere

These items are decisions we have **not** yet made and they live in
the documents below — this spec does not pre-empt them.

- **Android-native vs. Flutter shell** — see
  [`muse-mobile-native-vision.md`](muse-mobile-native-vision.md).
- **Which on-device STT engine** — see the same vision doc.
- **Driving-mode legal disclosures** — see
  [`muse-user-journeys.md`](muse-user-journeys.md), journey #1.
- **Private/local mode threat model details** — see
  [`muse-private-local-mode.md`](muse-private-local-mode.md).

---

## 9. Source-of-truth pointers

| Topic | Document |
|---|---|
| Mobile-native vision and Android/Flutter decision | [`muse-mobile-native-vision.md`](muse-mobile-native-vision.md) |
| Ten canonical user journeys with full narratives | [`muse-user-journeys.md`](muse-user-journeys.md) |
| Definition-of-done checklists per capability | [`muse-definition-of-done.md`](muse-definition-of-done.md) |
| Private / local mode requirements | [`muse-private-local-mode.md`](muse-private-local-mode.md) |
| Plain-English communication principles | [`muse-plain-english-principles.md`](muse-plain-english-principles.md) |
| Orchestration primitives (Job, Worker, Routing, Gate, Ledger) | [`../orchestration/README.md`](../orchestration/README.md) |
| The success metric (delivered / validated / accepted) | [`../mission/best-coding-tool-mission.md`](../mission/best-coding-tool-mission.md) |
| Current Android cockpit API contract | [`../android/muse-apk-api-contract.md`](../android/muse-apk-api-contract.md) |
| Existing Android cockpit screen spec | [`../android/muse-apk-cockpit.md`](../android/muse-apk-cockpit.md) |
