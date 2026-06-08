# Hermes — Canonical User Journeys

> **Status:** Spec. Companion to
> [`hermes-10-10-product-spec.md`](hermes-10-10-product-spec.md).
> Each journey below is a contract: at the 10/10 bar, these are the
> flows Hermes must support end-to-end without surprises.

Every journey is written from the operator's point of view. Each
journey lists: the trigger, the happy path, the fallback paths, the
artifacts produced, the ledger entries written, and the
"definition-of-done" link in
[`hermes-definition-of-done.md`](hermes-definition-of-done.md).

---

## Index

1. [Voice prompt while driving → safe hands-free job capture](#1-voice-prompt-while-driving)
2. [Prompt → research → plan → approval → implementation](#2-prompt-to-implementation)
3. [Prompt → GitHub repo audit](#3-prompt-to-github-repo-audit)
4. [Prompt → Claude Code on Windows remote execution](#4-prompt-to-claude-code-on-windows)
5. [Prompt → Supabase / Vercel deployment plan](#5-prompt-to-supabase-vercel-deployment-plan)
6. [Prompt → GitHub PR](#6-prompt-to-github-pr)
7. [Prompt → failed network recovery / resume](#7-prompt-to-failed-network-recovery-resume)
8. [Prompt → model / tool selection explanation](#8-prompt-to-model-tool-selection-explanation)
9. [Prompt → validation report](#9-prompt-to-validation-report)
10. [Prompt → learn from mistake and update profile](#10-prompt-to-learn-from-mistake)

---

## 1. Voice prompt while driving

**Trigger.** Jeremiah is driving. His phone is mounted. Driving mode
is on (manual toggle, Android Auto handoff, or Bluetooth heuristic).

**Happy path.**

1. He says *"Hey Hermes."* The cockpit chirps (audio acknowledge).
2. He says *"Audit the Hermes-Agent repo and tell me the top three
   risks."*
3. The transcript is read back: *"You said: audit the Hermes-Agent
   repo and tell me the top three risks. Dispatch?"*
4. He says *"Hermes, dispatch."*
5. The cockpit reads back the job summary: *"Dispatched. This is an
   audit job. I'll send the result when it's ready."*
6. Hermes routes to the **repo audit** worker. No mutation. Validation
   gate runs.
7. When the report is ready, the cockpit speaks: *"Audit complete.
   Top risks: secrets in a checked-in `.env.example`, an unpinned
   `requests` dependency, and a dead workflow file. Want me to read
   the full report?"*
8. He says *"Hermes, status."* → spoken summary.
9. He says *"Hermes, end driving mode."* → 3-s safety pause →
   cockpit returns to tap UI.

**Fallback paths.**

- **STT fails.** Cockpit speaks *"I couldn't hear that. Try again or
  tap the mic when you can."* No prompt is dispatched.
- **Out-of-grammar phrase in driving mode.** Cockpit speaks *"I only
  take a small set of commands while you're driving. Say 'Hermes,
  end driving mode' when you can use the screen."*
- **Backend unreachable.** Cockpit queues the prompt locally,
  speaks *"I can't reach Hermes right now. I'll send this as soon
  as I can."* Replays on reconnect.
- **Job needs approval.** Approval gates are never auto-approved in
  driving mode. The cockpit speaks *"There's an approval waiting.
  I'll hold it until you can review it."* No destructive action is
  taken on a spoken command alone.

**Artifacts.** `~/.hermes/jobs/<id>/voice-capture.wav` (kept locally
only, never uploaded unless cloud STT is opt-in), `transcript.txt`,
`prompt.md`, ledger entries `voice_capture`, `transcript`,
`dispatch`.

**Ledger entries.**

```jsonl
{"phase":"capture","source":"voice","mode":"driving","stt_engine":"on-device-whisper","ts":"..."}
{"phase":"dispatch","worker":"github-repo-audit","gate":"none","ts":"..."}
```

**Definition-of-done link.**
[`hermes-definition-of-done.md#dod-driving-mode`](hermes-definition-of-done.md#dod-driving-mode).

---

## 2. Prompt to implementation

**Trigger.** Any prompt that asks Hermes to change code.

**Happy path.**

1. **Capture.** Voice or text. Hermes creates a Job, ID `J-2026-05-23-001`.
2. **Research phase.**
   - The orchestrator dispatches a research worker.
   - Output: `shared-context/repo-map.md`, `evidence.md`,
     `constraints.md`, `user-preferences.md`.
   - Gate: the research worker's `status.json` is `complete` and
     the judge says the evidence covers every file the plan will
     touch.
3. **Plan phase.**
   - The planner reads the research artifacts and writes
     `plan.md`: scope, files to change, validation contract,
     proposed worker, proposed model, estimated cost/time.
   - Gate: the judge checks the plan against the prompt and the
     user profile (style, tooling, allowlist).
4. **Approval phase.**
   - The cockpit shows the plan as a single card: "Hermes wants to
     do X. Approve?" with **Approve**, **Reject**, **Edit**.
   - The card includes the plain-English "why": worker chosen, model
     chosen, scope summary.
   - The user taps Approve (or speaks the confirmation phrase in
     driving mode).
5. **Implementation phase.**
   - Worker runs in an isolated worktree.
   - Streams progress to the cockpit and the SSE log buffer.
   - Writes `patch.diff`, updated files, and `output.md` summarizing
     what changed.
6. **Validation phase.**
   - Runs the contract: tests, lint, type-check, smoke run, etc.
   - Writes `validation-report.md` in plain English.
   - Gate: the validation contract must pass; failures escalate
     (re-spawn, or surface to user).
7. **Publishing phase.** (See journey #6.)

**Fallback paths.**

- **Research finds the prompt is ambiguous.** Hermes pauses, asks
  one clarifying question in the cockpit, and resumes when answered.
- **Plan exceeds budget / scope.** Plan card surfaces the overage
  with a recommendation: shrink, split, or proceed.
- **Approval declined.** Hermes records the rejection reason, asks
  for a corrective prompt, and discards the worktree.
- **Implementation fails.** Worker writes its failure to `output.md`;
  validation gate is skipped; ledger marks the lane `failed`; cockpit
  surfaces a "Hermes hit a wall" card with the failure summary.
- **Validation fails.** Hermes does **not** publish. It re-spawns the
  worker with the failure context, up to `code.auto_lint_max_retries`
  times. If still failing, the cockpit surfaces a "needs human"
  card with the report.

**Definition-of-done link.**
[`hermes-definition-of-done.md#dod-phase-gates`](hermes-definition-of-done.md#dod-phase-gates).

---

## 3. Prompt to GitHub repo audit

**Trigger.** *"Audit owner/repo for security and code-health issues."*

**Happy path.**

1. Capture; Hermes creates a read-only Job.
2. Research phase loads repo metadata, default branch, recent
   commits, open PRs, dependency manifests, CI workflow files.
3. The audit worker runs a fixed audit playbook (secrets, deps,
   workflow drift, README freshness, license, code health signals).
4. No plan phase; no approval phase (read-only).
5. Validation: the judge re-reads the audit findings against the
   evidence (every finding must reference a file path + line range).
6. Publish: a `audit-report.md` rendered in the cockpit as a single
   scrollable card with one paragraph per finding, ordered by
   severity.

**Fallback paths.**

- **Repo private and the user has not connected GitHub.** Hermes
  shows a "connect GitHub" card; the audit waits in
  `awaiting_secrets` state.
- **API rate-limited.** Hermes backs off, surfaces ETA, resumes.
- **Audit finding is uncertain.** It is filed under "uncertain
  findings" with the uncertainty stated in plain English.

**Definition-of-done link.**
[`hermes-definition-of-done.md#dod-github-integration`](hermes-definition-of-done.md#dod-github-integration).

---

## 4. Prompt to Claude Code on Windows

**Trigger.** *"Use Claude Code on my Windows box to refactor `pkg/foo`."*

**Pre-requisites.**

- Windows workstation reachable over Tailscale, WireGuard, or SSH.
- Claude Code installed on the workstation, registered with Hermes
  as worker `windows-claude-code`.
- The job folder path on Windows is on the allowlist; commands the
  worker may run are on the allowlist.

**Happy path.**

1. Capture; research; plan.
2. Approval card surfaces the worker: *"Send to Windows Claude Code
   on Opus 4.7. Workstation: `home-win-01`. Allowlist: `pkg/foo/**`.
   Approve?"*
3. On approve, Hermes opens an authenticated SSH session, mounts
   the job folder, dispatches the prompt.
4. Worker stdout/stderr stream back over the same channel; the
   cockpit shows live progress.
5. On completion, Hermes pulls back `patch.diff` and validation
   artifacts; the local validation gate runs (not the worker's
   self-report).
6. Publish (or surface failure).

**Fallback paths.**

- **Workstation unreachable.** Hermes pauses the lane, surfaces
  *"`home-win-01` is unreachable — last seen 12 minutes ago"* with
  **Retry**, **Reassign worker**, **Cancel**.
- **Worker exits non-zero.** Hermes captures the exit code, the
  last 200 lines of stderr, and surfaces them in the cockpit.
- **Command outside allowlist.** Worker is denied; ledger records
  the attempt; the cockpit surfaces *"Worker tried to run X — not
  on the allowlist. Want to add it?"*

**Definition-of-done link.**
[`hermes-definition-of-done.md#dod-windows-bridge`](hermes-definition-of-done.md#dod-windows-bridge).

---

## 5. Prompt to Supabase / Vercel deployment plan

**Trigger.** *"Plan a Supabase migration and a Vercel preview deploy
for branch `feat/x`."*

**Happy path.**

1. Capture; research (reads Supabase advisors + current schema +
   Vercel project + last deployment).
2. Plan phase writes a two-part `plan.md`:
   - **Supabase**: every DDL statement, every advisor warning, the
     `confirm_cost` output for any cost-incurring action.
   - **Vercel**: deploy target, env-var diff, build command,
     expected build duration, the commit diff vs. last deploy.
3. Approval card shows the plan in plain English. The user can
   approve **Supabase only**, **Vercel only**, or **both**.
4. On approve: Hermes runs `apply_migration` (Supabase) and/or
   `deploy_to_vercel` and streams logs.
5. Validation: re-reads advisors after migration; re-reads Vercel
   build logs; writes `validation-report.md`.

**Fallback paths.**

- **Supabase advisor flags a `security` issue.** The plan card
  shows the warning prominently and requires an explicit "I have
  read this" tap before approve is enabled.
- **Vercel build fails.** Hermes pulls the build logs, summarizes
  the failure in plain English, suggests next steps.
- **Cost not confirmed.** Approve button is disabled until
  `confirm_cost` has run and the user has seen the price.

**Definition-of-done link.**
[`hermes-definition-of-done.md#dod-supabase-vercel`](hermes-definition-of-done.md#dod-supabase-vercel).

---

## 6. Prompt to GitHub PR

**Trigger.** *"Implement <X> and open a PR."*

**Happy path.**

1. Journey #2 runs end-to-end through validation.
2. Publishing phase opens a draft PR (always draft on first push)
   with a generated title, body, and test plan.
3. The cockpit surfaces the PR URL and the validation report.
4. If the user enables PR-activity subscription (in-app toggle),
   Hermes watches CI and review comments; failing CI triggers an
   autofix loop (bounded by `pr.autofix_max_rounds`).
5. The user marks the PR ready-for-review when they choose; Hermes
   never marks a PR ready or merges without explicit approval.

**Fallback paths.**

- **Pre-commit hook fails.** Hermes does **not** `--no-verify`. It
  surfaces the hook output and either fixes it (if a known
  failure mode) or asks the user.
- **Push rejected by remote.** Hermes inspects (branch protection,
  divergent history, large file). It surfaces the reason and the
  recommended next step. It never force-pushes without explicit
  approval.
- **PR creation fails.** The branch is still pushed; the cockpit
  surfaces *"Branch pushed, PR creation failed: <reason>"* with a
  **Retry PR** action.

**Definition-of-done link.**
[`hermes-definition-of-done.md#dod-pr-flow`](hermes-definition-of-done.md#dod-pr-flow).

---

## 7. Prompt to failed network recovery / resume

**Scenario.** The phone loses signal mid-job, or the backend
restarts, or a remote worker (Windows) loses its tunnel.

**Behaviors per failure mode.**

- **Cockpit loses connection to backend.**
  - Cockpit shows an amber "live updates paused" pill.
  - Reconnects with exponential backoff (2 s → 30 s).
  - On reconnect, replays missed SSE events from the gateway's
    in-memory ring buffer (sized for the longer of "last 5 minutes"
    or "last 1 000 events").
  - Pending dispatches in the cockpit's outbox replay automatically.
- **Backend process is killed mid-phase.**
  - On restart, the job controller scans `~/.hermes/jobs/` for
    incomplete jobs.
  - Each job resumes at its last checkpoint. Phases write their
    checkpoint to the job folder on every state change.
  - The cockpit reflects the resumed state within 5 s of backend
    restart.
- **Remote worker (Windows) loses its tunnel.**
  - Hermes pauses that lane only; other lanes continue.
  - Cockpit shows a "worker unreachable" card on that lane with
    **Retry**, **Reassign** (route to a different worker / model),
    **Cancel**.
  - The lane resumes from its last checkpoint when the tunnel is
    back. Streaming output that was missed during the outage is
    replayed from the worker's local buffer when feasible; if not,
    the worker is re-spawned with a "resume from checkpoint"
    prompt.
- **Cloud LLM 5xx or rate-limit.**
  - The model adapter retries with backoff up to a budget; on
    exhaustion, the routing policy reassigns to the next-best
    model. A ledger entry records the swap.

**Invariants.**

- **No job is silently dropped.** Every failure produces a ledger
  entry and surfaces a card in the cockpit.
- **No work is silently lost.** Every artifact is checkpointed to
  the job folder before any phase transition; resumption never
  re-runs a phase that already completed.
- **No destructive action is retried without consent.** Mutating
  operations that succeeded do not run twice; the ledger records
  the success and the resume skips that step.

**Definition-of-done link.**
[`hermes-definition-of-done.md#dod-resilience`](hermes-definition-of-done.md#dod-resilience).

---

## 8. Prompt to model / tool selection explanation

**Trigger.** The user taps "Why this worker?" on any job card, or
says *"Hermes, status"* and asks *"Why did you pick that?"*.

**Happy path.**

1. The cockpit reads the job's `routing_decision` ledger entry.
2. It renders a one-paragraph plain-English answer:
   > "I sent this to **Windows Claude Code on Opus 4.7** because:
   > it has the best score on Python refactors this week
   > (radar 0.91 vs. next-best 0.83), the workstation is online and
   > under budget, and your profile prefers Opus for Python work in
   > this repo. I'd have picked Codex CLI if Claude Code were busy."
3. Below the paragraph, an "expand" toggle reveals the structured
   data (scores, budget, profile rules) for power users.

**Fallback paths.**

- **No `routing_decision` entry exists.** The cockpit says exactly
  that — *"I don't have a routing record for this job. It may
  pre-date the routing ledger."* — and offers to recompute the
  decision for future jobs.
- **Radar is stale.** The decision falls back to defaults and the
  reason is named explicitly: *"Radar is more than 7 days old so I
  used the default policy."*

**Definition-of-done link.**
[`hermes-definition-of-done.md#dod-explanations`](hermes-definition-of-done.md#dod-explanations).

---

## 9. Prompt to validation report

**Trigger.** Any job that ran a validation contract.

**Happy path.**

1. The validation phase writes `validation-report.md` with this shape:

   ```markdown
   # Validation report — J-2026-05-23-001

   ## What was promised
   - Unit tests in `tests/foo/` pass.
   - `ruff check` is clean.
   - `mypy --strict tests/foo/` is clean.
   - The CLI command `muse foo bar` exits 0 on the sample input.

   ## What was tested
   - Ran `pytest tests/foo/` — 42 passed, 0 failed.
   - Ran `ruff check tests/foo/` — clean.
   - Ran `mypy --strict tests/foo/` — clean.
   - Ran `muse foo bar --input fixtures/sample.json` — exit 0.

   ## What failed
   - (None.)

   ## What was skipped, and why
   - Smoke run against the live API skipped: no network in this run.
     Add `--with-network` to enable.

   ## Bottom line
   Promised contract met. Safe to publish.
   ```
2. The cockpit renders this report as a single scrollable card.
3. A "read aloud" button reads the **bottom line** + the **what
   failed** section out loud (useful in driving mode).

**Fallback paths.**

- **A test was promised but cannot be run** (missing dependency,
  missing fixture): it appears under "skipped" with the reason; the
  publishing gate refuses to proceed unless the operator overrides
  with an explicit logged decision.
- **A validation step times out**: the report names the timeout and
  the bottom line is "publishing blocked — timeout".

**Definition-of-done link.**
[`hermes-definition-of-done.md#dod-validation-report`](hermes-definition-of-done.md#dod-validation-report).

---

## 10. Prompt to learn from mistake

**Trigger.** A job was rejected, reverted, rewritten by hand, or
grudgingly accepted.

**Happy path.**

1. The job's retrospective generator writes
   `memory/longterm-memory/retrospectives/YYYY-MM-DD-<job-id>.md`
   with:
   - What the prompt asked for.
   - What Hermes did.
   - Why the outcome was unsatisfactory (operator's words, captured
     from the rejection comment or voice note).
   - At least one **proposed change**: a routing tweak, a skill
     update, a profile rule, a new validation step, etc.
2. The cockpit surfaces a "Hermes wants to learn this" card with
   the proposed change in plain English. Two taps: **Apply** or
   **Discard**.
3. On Apply: the change is committed to the relevant config (routing
   policy YAML, profile Markdown, skill Markdown) with the
   retrospective filename in the commit message.
4. The next job in the same shape uses the updated rule.

**Fallback paths.**

- **No proposed change can be derived** (e.g. the rejection was
  "wrong day, my bad"): the retrospective is filed without a
  proposed change and a CI warning fires *"retrospective produced
  no proposed change — was the cause too vague?"*
- **Proposed change conflicts with an existing rule.** The cockpit
  card shows both and asks the user which wins; the chosen rule
  carries forward.

**Definition-of-done link.**
[`hermes-definition-of-done.md#dod-self-improvement`](hermes-definition-of-done.md#dod-self-improvement).

---

## Cross-references

- [`hermes-10-10-product-spec.md`](hermes-10-10-product-spec.md) — the spec these journeys exercise.
- [`hermes-definition-of-done.md`](hermes-definition-of-done.md) — DoD checklists per journey.
- [`hermes-mobile-native-vision.md`](hermes-mobile-native-vision.md) — driving-mode and voice details.
- [`hermes-plain-english-principles.md`](hermes-plain-english-principles.md) — the principles every readback follows.
- [`../orchestration/prompt-to-pr-demo.md`](../orchestration/prompt-to-pr-demo.md) — the end-to-end demo this spec generalizes.
- [`../orchestration/self-improvement-loop.md`](../orchestration/self-improvement-loop.md) — the loop journey #10 closes.
