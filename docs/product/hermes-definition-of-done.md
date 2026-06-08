# Hermes — Definition of Done

> **Status:** Per-capability DoD checklists. Companion to
> [`hermes-10-10-product-spec.md`](hermes-10-10-product-spec.md).
> A capability is **done** when every box in its section is ticked
> in a release branch.

The DoD here is stricter than "tests pass." It is the operational
bar: the capability behaves correctly, fails safely, is observable,
is documented, and is explainable in plain English.

Every section ends with **Validation** — how a reviewer can confirm
the section is genuinely done, not "looks done."

---

## How to use this document

- During implementation: copy the relevant section's checklist into
  the PR description, tick boxes as work lands.
- During review: every unticked box is a blocker.
- During release: every section that gates 10/10 (marked
  **10/10-gating** below) must be 100 % green.

The sections track the capabilities listed in
[`hermes-10-10-product-spec.md`](hermes-10-10-product-spec.md) §4.

---

## DoD: cockpit shell (C1) — 10/10-gating

<a id="dod-cockpit-shell"></a>

- [ ] Cold start under 2 s on a 2022-era mid-tier Android phone.
- [ ] App resumes the prior session's last screen on launch (job
      dashboard if a job is in flight; prompt composer otherwise).
- [ ] All screens render at 360 dp width without horizontal scroll.
- [ ] Every primary action is reachable with the right thumb in
      portrait.
- [ ] No required network call blocks the first frame.
- [ ] Crash-free sessions ≥ 99.5 % over a rolling 7-day window in
      pre-release telemetry.
- [ ] Tablet / landscape layout degrades gracefully (no broken
      layout; not required to be optimized).
- [ ] Lock-screen widget renders the next pending approval and
      current job phase.

**Validation:** synthetic startup test in CI; manual one-handed
walkthrough recorded per release; crash-rate dashboard reviewed at
release sign-off.

---

## DoD: voice capture (C2) — 10/10-gating

<a id="dod-voice-capture"></a>

- [ ] Push-to-talk works in every screen that has a mic affordance.
- [ ] Transcript visible within 1 s of release on the default
      on-device engine.
- [ ] Transcript is user-editable before dispatch.
- [ ] STT failure surfaces a "type instead" affordance; never silently
      swaps engines.
- [ ] On-device STT is the default; cloud STT is behind a per-session
      opt-in.
- [ ] Mic-hot indicator is visible (status bar icon + on-screen
      banner) whenever the mic is open.
- [ ] Audio bytes never leave the device unless cloud STT is opted in
      for the current session.

**Validation:** latency budget test with synthetic audio; Espresso
test for the "type instead" fallback; instrumentation asserts the
opt-in flag is set when cloud STT is in use.

---

## DoD: continuous hands-free listening (C3) — 10/10-gating

<a id="dod-hands-free"></a>

- [ ] Off by default.
- [ ] Toggle is in Settings → Voice; not surfaced on any primary
      screen.
- [ ] When on, a persistent foreground notification + on-screen
      banner are visible.
- [ ] Wake-word required before any prompt is captured.
- [ ] Captured utterance is read back; user confirms or cancels by
      voice.
- [ ] Session auto-ends after a user-configurable inactivity timeout
      (default 5 min).
- [ ] No audio is uploaded without an explicit per-prompt
      confirmation tone or banner.
- [ ] Battery-impact is measured and documented (target: < 5 %
      drain over 8 h on a mid-tier device with screen off).

**Validation:** instrumentation reports the foreground service is
running while hands-free is on; integration test verifies wake-word
gating; battery impact tracked per release.

---

## DoD: driving mode (C4) — 10/10-gating

<a id="dod-driving-mode"></a>

- [ ] Manual toggle exists.
- [ ] Auto-trigger via Android Auto handoff or car-Bluetooth
      heuristic, off by default until configured.
- [ ] UI is voice-only: no destructive action is tappable while
      driving mode is on.
- [ ] Approvals require the spoken confirmation phrase, not a tap.
- [ ] Out-of-grammar phrases are rejected with the canned response.
- [ ] Validation reports and gate decisions are read aloud.
- [ ] Visual diffs are never shown on the screen while driving mode
      is on; only audio summaries.
- [ ] Exiting driving mode requires a 3-s safety pause before taps
      are re-enabled.

**Validation:** Espresso test for the restricted surface; voice
grammar unit tests; safety checklist signed-off per release.

---

## DoD: local job controller (C5) — 10/10-gating

<a id="dod-job-controller"></a>

- [ ] Every prompt produces a Job with a deterministic ID.
- [ ] Every Job has a folder under `~/.hermes/jobs/<id>/`.
- [ ] State machine has explicit transitions:
      `captured → researching → planning → awaiting_approval →
      implementing → validating → publishing → done | blocked | failed`.
- [ ] Transitions are atomic (write-then-rename or DB transaction).
- [ ] Each transition writes an entry to `decision-ledger.jsonl`.
- [ ] Killing the backend at any state and restarting it resumes the
      job at the last checkpoint.
- [ ] The cockpit reflects the resumed state within 5 s of restart.

**Validation:** state-machine unit tests; ledger-schema test;
crash-recovery test (`kill -9` in each phase, assert resume).

---

## DoD: phase gates (C9) — 10/10-gating

<a id="dod-phase-gates"></a>

- [ ] No phase begins until the previous phase's artifact passes its
      gate.
- [ ] The approval phase is the only phase that may wait indefinitely
      for a human.
- [ ] All other phases have explicit timeouts and escalations.
- [ ] Gate failures surface in the cockpit within 5 s.
- [ ] Bypassing a gate requires an `override` decision logged to the
      ledger with the operator's identity.
- [ ] Each gate writes a "why this passed / failed" summary in plain
      English to the job folder.

**Validation:** integration test per gate; bypass-requires-explicit-
flag asserted in test; ledger schema test.

---

## DoD: multi-agent spawning and isolation (C7, C8) — 10/10-gating

<a id="dod-isolation"></a>

- [ ] Independent task-graph lanes spawn in parallel.
- [ ] Dependent lanes block until the parent's gate passes.
- [ ] Each lane runs in its own `git worktree` or container.
- [ ] No two workers write the same path at the same time.
- [ ] Worker output paths are under the job folder, never the repo
      root.
- [ ] Worker crashes do not corrupt the job folder.

**Validation:** concurrency stress test (5 lanes, 10 min); worktree
isolation test; conflict-detection test; kill -9 a worker mid-write
and verify the job folder is intact.

---

## DoD: persistent queue and checkpointing (C10, C11) — 10/10-gating

<a id="dod-resilience"></a>

- [ ] All jobs survive a backend restart.
- [ ] Long-running phases checkpoint at least every 60 s of wall
      time.
- [ ] No completed phase is re-run on resume.
- [ ] Mutating operations that already succeeded are not retried.
- [ ] Cockpit reconnection replays missed SSE events from a buffer
      sized for the longer of 5 min or 1 000 events.
- [ ] A pending dispatch in the cockpit's outbox replays on reconnect.
- [ ] Remote-worker outages pause only the affected lane, not the
      whole job.

**Validation:** restart drill in CI (kill -9 every 30 s during a
5-min job); chaos test that drops the cockpit-backend link every
30 s; SSE replay test; mutating-op idempotency test.

---

## DoD: validation loops (C12) — 10/10-gating

<a id="dod-validation-report"></a>

- [ ] Every job declares its validation contract up front in
      `plan.md`.
- [ ] The validation phase runs the contract verbatim.
- [ ] Results are written to `validation-report.md`.
- [ ] The report follows the canonical structure (Promised / Tested /
      Failed / Skipped + bottom line).
- [ ] Reports are readable by a non-engineer (raw tracebacks behind a
      "show details" toggle).
- [ ] The publishing gate refuses to proceed without a passing report.
- [ ] An auto-fix loop re-spawns the worker up to
      `code.auto_lint_max_retries` times before escalating to a
      human.

**Validation:** validation-report lint (no top-level tracebacks);
auto-fix loop tested with a deliberately failing test; publishing
gate refusal asserted in integration test.

---

## DoD: monitoring (C13) — 10/10-gating

<a id="dod-monitoring"></a>

- [ ] Cockpit job cards update within 2 s of a backend state change.
- [ ] `muse orchestrator status <job-id>` matches the cockpit's
      view of the same job.
- [ ] SSE stream is available on `/v1/cockpit/jobs/stream`.
- [ ] Long-poll fallback exists for clients that cannot use SSE.
- [ ] Backend logs include the job ID on every line that touches a
      job.
- [ ] No PII or secrets appear in any log surface.

**Validation:** SSE latency budget enforced; CLI-vs-cockpit diff
test; secret-in-log detector in CI.

---

## DoD: Windows remote bridge (C6) — 10/10-gating

<a id="dod-windows-bridge"></a>

- [ ] Workstation reachable over Tailscale / WireGuard / SSH only —
      no public ingress.
- [ ] Worker registered with Hermes as `windows-claude-code` (or
      similar) with allowlisted paths and commands.
- [ ] stdout/stderr stream back over the same authenticated channel.
- [ ] Commands not on the allowlist are denied; the attempt is
      logged.
- [ ] Workstation does not hold a long-lived secret the backend does
      not own.
- [ ] Workstation outage pauses only the affected lane.
- [ ] On reconnect, the worker resumes from the last checkpoint.

**Validation:** pen-test checklist; allowlist test (denied command
returns a refusal logged to the ledger); outage drill.

---

## DoD: GitHub integration (C16, partial) — 10/10-gating

<a id="dod-github-integration"></a>

- [ ] Read operations (metadata, file contents, PR diffs, comment
      threads) require no extra approval.
- [ ] Every mutating operation (push, comment, PR open / close /
      merge, label) is gated through the approval phase.
- [ ] Every mutating operation is logged to the ledger with the exact
      API call (method, URL, body summary).
- [ ] Default PR creation is **draft**.
- [ ] PR merging is never automatic.
- [ ] Force-pushes require an explicit operator decision.
- [ ] Pre-commit-hook failures do not trigger `--no-verify`.

**Validation:** mutation-gate test; ledger entry test; integration
test against a fixture repo; force-push refusal test.

---

## DoD: Supabase and Vercel integrations (C16, partial) — 10/10-gating

<a id="dod-supabase-vercel"></a>

- [ ] Supabase reads (list_tables, get_logs, get_advisors) are free.
- [ ] Supabase DDL (`apply_migration`, raw DDL via `execute_sql`,
      branch delete, project pause) is gated and logged.
- [ ] Cost-incurring Supabase actions block until `confirm_cost` has
      run.
- [ ] Vercel reads (deployments, build logs) are free.
- [ ] Vercel deploys are gated, with the commit diff vs. last deploy
      surfaced in the plan card.
- [ ] Build failures are summarized in plain English with the failing
      step quoted.

**Validation:** DDL-detection test; cost-confirmation test; deploy
gate test; build-failure summary test.

---

## DoD: routing explanations (C17) — 10/10-gating

<a id="dod-explanations"></a>

- [ ] Every job has a `routing_decision` ledger entry naming the
      worker, the model, and the radar score / budget that won.
- [ ] The cockpit shows a one-paragraph plain-English "why" on each
      job card.
- [ ] Tapping "show details" reveals the structured scoring.
- [ ] If the radar is stale, the explanation says so explicitly.
- [ ] If no `routing_decision` entry exists for a job, the
      explanation says exactly that.

**Validation:** ledger schema test; cockpit-copy lint; stale-radar
fallback test.

---

## DoD: user profile learning (C14) — 10/10-gating

<a id="dod-profile-learning"></a>

- [ ] On first use of a repo, Hermes asks consent before mining the
      user's history.
- [ ] Mined profiles live under `~/.hermes/profiles/<github-user>/`
      as Markdown.
- [ ] Profiles are user-editable; user edits beat re-mined values.
- [ ] Profiles are referenced by routing and code-gen decisions in
      that repo.
- [ ] Profiles can be deleted in one tap from the cockpit.

**Validation:** consent flow asserted before first mine; "edit
beats re-mine" test; deletion test.

---

## DoD: secrets management (C15) — 10/10-gating

<a id="dod-secrets"></a>

- [ ] Backend secrets live in `~/.hermes/.env` and nowhere else.
- [ ] Cockpit secrets live in EncryptedSharedPreferences on the
      device.
- [ ] No secret ever appears in a log surface.
- [ ] Cockpit→backend traffic is TLS or loopback only.
- [ ] TLS pinning enabled on the cockpit by default; opt-out is
      explicit per server.
- [ ] Secrets are scoped per worker; a worker only sees the secrets
      on its allowlist.

**Validation:** secret-in-log detector in CI; allowlist test; TLS
pinning verified on the cockpit.

---

## DoD: plain-English explanations (C17, cross-cutting) — 10/10-gating

<a id="dod-plain-english"></a>

- [ ] Every job card shows a one-paragraph plain-English summary.
- [ ] Every gate decision shows a plain-English "why."
- [ ] Every validation report follows the canonical structure with a
      "bottom line" line a non-engineer can read.
- [ ] No raw JSON / stack-trace / acronym appears in a primary view.
- [ ] A "Why did Hermes do X?" query returns a one-paragraph answer
      grounded in a ledger entry or rule.
- [ ] Flesch-Kincaid grade ≤ 9 on the primary summary copy.

**Validation:** readability score in CI; "no jargon" lint per
screen; "why" query test against a fixture job. See
[`hermes-plain-english-principles.md`](hermes-plain-english-principles.md).

---

## DoD: self-improvement loop (cross-cutting) — 10/10-gating

<a id="dod-self-improvement"></a>

- [ ] Every rejected / reverted / rewritten / grudgingly-accepted
      job produces a retrospective.
- [ ] Each retrospective proposes at least one concrete change.
- [ ] The cockpit surfaces a "Hermes wants to learn this" card with
      the change in plain English.
- [ ] Approved changes commit to config with the retrospective
      filename in the commit message.
- [ ] The same shape of job uses the updated rule on the next run.

**Validation:** retrospective generation test; "no proposed change"
CI warning; cockpit-card Espresso test; before/after routing test on
a fixture.

---

## DoD: private / local-only mode (cross-cutting) — 10/10-gating

<a id="dod-private-local"></a>

See [`hermes-private-local-mode.md`](hermes-private-local-mode.md)
for the full requirements. Summary:

- [ ] Zero outbound DNS / TCP outside loopback or LAN, end-to-end.
- [ ] Cockpit talks to backend over loopback or LAN only.
- [ ] All models run locally.
- [ ] All memory backends are local SQLite.
- [ ] All gateway adapters that need the internet are disabled.
- [ ] Telemetry is off.
- [ ] An audit script (`muse doctor --private-mode`) confirms
      compliance.

**Validation:** network egress test in CI with `iptables` denying
non-loopback; `muse doctor` exit code 0 in the test environment.

---

## DoD: pull-request flow (C16 — shipping) — 10/10-gating

<a id="dod-pr-flow"></a>

- [ ] PRs default to draft.
- [ ] PR title ≤ 70 chars.
- [ ] PR body includes a Summary, a Test Plan, and the job ledger
      link.
- [ ] On opt-in, Hermes watches CI and review comments via the
      PR-activity webhook.
- [ ] CI autofix loop is bounded by `pr.autofix_max_rounds` (default
      3).
- [ ] Hermes never marks a PR ready-for-review without explicit
      operator action.
- [ ] Hermes never merges without explicit operator action.

**Validation:** integration test against a fixture PR; autofix-loop
bound test; "no auto-merge" assertion.

---

## Cross-references

- [`hermes-10-10-product-spec.md`](hermes-10-10-product-spec.md) — the spec these DoDs implement.
- [`hermes-user-journeys.md`](hermes-user-journeys.md) — the journeys these DoDs deliver.
- [`hermes-private-local-mode.md`](hermes-private-local-mode.md) — local-mode requirements expanded.
- [`hermes-plain-english-principles.md`](hermes-plain-english-principles.md) — the principles every readback follows.
- [`../orchestration/release-checklist.md`](../orchestration/release-checklist.md) — the orchestration-specific release gate.
