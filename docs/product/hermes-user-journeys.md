# Hermes Core User Journeys

Companion to [`hermes-10-10-product-spec.md`](./hermes-10-10-product-spec.md).

Each journey starts with a single user prompt. Each ends with a reviewable, reversible artifact. Each is exercised through the Android cockpit, the TUI, and the local CLI, and each produces the standard job folder described in the product spec §3.2.

The seven core journeys are:

1. Prompt to PR
2. Prompt to repo audit
3. Prompt to Android APK validation
4. Prompt to local Termux setup
5. Prompt to refactor
6. Prompt to debug
7. Prompt to docs/release

---

## Journey 1 — Prompt to PR

**Trigger prompt (example):** *"Add server-side pagination to /api/orders, default page size 50, keep response shape backward compatible."*

**Hermes flow:**
1. Detect repo: Node + Express + Prisma + Jest. Detect local tools: `claude`, `codex`, `gh`, `pnpm`.
2. Plan: change handler, add pagination params, update Prisma query, update tests, update OpenAPI doc.
3. Route: Claude Code for the handler change (multi-file refactor strength), Codex CLI as a parallel competitor for the test file (sometimes wins on test scaffolding). Decision ledger records both picks.
4. Worktrees: `wt/claude/<job>` and `wt/codex/<job>`.
5. Run: both workers in parallel. Logs streamed to job folder.
6. Collect: diffs, test runs, lint output.
7. Score: rubric weighs passing tests, diff size, backward-compat preservation. Claude wins on the handler, Codex wins on the tests; merge takes the best of each.
8. Validate: full Jest suite + lint + type check. Pass.
9. Publish: draft PR with summary, decision ledger excerpt, scoring table, rollback notes.
10. Cockpit: shows status `published`, one-tap link to the PR, one-tap "request review".

**Success means:** PR exists, CI green, decision ledger and scoring visible, user approved push but did not have to write code.

---

## Journey 2 — Prompt to repo audit

**Trigger prompt (example):** *"Audit this repo for security, dependency, and dead-code issues before the v1 release."*

**Hermes flow:**
1. Detect repo + tools (npm audit, pip-audit, gitleaks, depcheck, knip, etc. — whatever is locally available).
2. Plan: run each available auditor, parse outputs, deduplicate findings, rank by severity and reachability.
3. Route: no worker rewrites code in an audit; workers are used for triage summarization.
4. Run auditors in parallel, capture raw outputs.
5. Score findings (severity × reachability × confidence).
6. Produce `audit-report.md` in the job folder: ranked findings, links to source lines, suggested fixes (without applying them).
7. No publish step by default; audit is read-only. Optionally open a tracking issue per finding.
8. Cockpit: status-first list of findings with severity chips, one-tap "open finding", one-tap "create issue".

**Success means:** no code changed, but the user has an actionable, deduplicated, severity-ranked report — and every finding has a source link and a suggested fix.

---

## Journey 3 — Prompt to Android APK validation

**Trigger prompt (example):** *"Build the Hermes cockpit APK from the current branch and verify it launches, lists jobs, and can open a job detail view."*

**Hermes flow:**
1. Detect Android toolchain (Gradle, Android SDK, emulator availability) and the cockpit project layout.
2. Plan: build APK, install to emulator (or wait for device), run smoke probes (launch, list, navigate), capture screenshots.
3. Route: build is a deterministic CLI task; smoke probes use the `run`/`verify` skills with an Android driver.
4. Run: gradle build → install → drive → screenshot.
5. Collect: APK path, build logs, screenshots, probe pass/fail.
6. Validate: each probe is a discrete pass/fail in `validation/`.
7. Publish (optional): attach APK as a release asset on a draft GitHub release.
8. Cockpit: shows build status, links to screenshots, lets the user download the APK to the same device.

**Success means:** the APK exists, the smoke probes passed (or the failures are named and reproducible), screenshots are attached, the developer can install it from the cockpit.

---

## Journey 4 — Prompt to local Termux setup

**Trigger prompt (example):** *"Set up Hermes on this Termux install so I can run jobs locally with my Anthropic and OpenAI keys."*

**Hermes flow:**
1. Detect Termux environment: pkg list, available Python/Node, storage permissions, existing `~/.hermes/` state.
2. Plan: install missing packages, scaffold `~/.hermes/config.yaml`, prompt the user (via cockpit) for any required API keys without ever writing them to a committed file.
3. Route: this is a scripted setup; no external coding workers are invoked. Hermes does the work directly.
4. Run setup steps with the destructive-command approval policy in effect.
5. Validate: smoke-run a hello-world job end-to-end (plan → trivial worker → score → no publish).
6. Cockpit: shows each setup step with status; failed steps offer one-tap remediation.

**Success means:** the user can issue a real prompt and have it run, on their device, against their keys, without ever pasting a secret into a chat box or a file.

---

## Journey 5 — Prompt to refactor

**Trigger prompt (example):** *"Refactor the auth middleware into a typed module, no behavior change, keep the public API."*

**Hermes flow:**
1. Detect repo + test coverage of the affected paths. If coverage is low, the plan adds characterization tests first.
2. Plan: identify modules in scope, propose new structure, list invariants to preserve.
3. Route: prefer workers strong on multi-file refactors (Claude Code, Aider with whole-file mode). Run two in parallel.
4. Run + collect.
5. Score: weights heavily on "no behavior change" (existing tests still pass) and on diff structure.
6. Merge winner.
7. Validate: full test suite + type check + smoke run.
8. Publish: draft PR labeled `refactor`, decision ledger explains why the chosen worker won.
9. Cockpit: shows before/after structure side by side.

**Success means:** no test regressed, the public API is byte-identical, and the new structure is reviewable as a single coherent diff.

---

## Journey 6 — Prompt to debug

**Trigger prompt (example):** *"Users report intermittent 502s on /api/checkout under load. Find and fix."*

**Hermes flow:**
1. Detect repo + observability (logs path, tracing, load-test tool availability).
2. Plan: reproduce, instrument, isolate, fix, validate.
3. Route: one worker drives reproduction (with the `verify` skill), another drives static analysis of the suspect path. Decision ledger records this split.
4. Run: reproduce locally (or against a recorded trace), instrument, observe, propose fix candidates.
5. Collect: repro steps, traces, candidate diffs.
6. Score: candidates judged on whether they make the repro pass and on minimal blast radius.
7. Merge winner, validate with the repro plus full test suite, plus a load probe if available.
8. Publish: draft PR includes the repro recipe so a reviewer can rerun it.
9. Cockpit: shows the repro as a one-tap "run repro" affordance.

**Success means:** the bug is reproducible before the fix and not reproducible after, with the recipe attached to the PR.

---

## Journey 7 — Prompt to docs/release

**Trigger prompt (example):** *"Cut release v0.15.0: changelog, release notes, version bumps, GitHub release draft."*

**Hermes flow:**
1. Detect repo state: previous release tag, commits since, version files (pyproject, package.json, etc.), changelog format.
2. Plan: group commits by type (feat/fix/chore/docs), draft changelog, draft release notes, bump versions, prep GitHub release.
3. Route: a docs-strong worker for changelog narrative; Hermes itself handles version bumps and tag plumbing.
4. Run + collect.
5. Score: changelog candidates judged on coverage and accuracy against the actual commit set.
6. Merge winner.
7. Validate: version files are internally consistent; changelog references real commits and PRs.
8. Publish: draft GitHub release with notes attached; **no tag pushed** until the user approves from the cockpit.
9. Cockpit: shows the draft release with a one-tap "publish release" once the user has reviewed.

**Success means:** the release exists in draft form, every claim in the notes maps to a real commit, and the user's only remaining action is "publish".

---

## Cross-journey invariants

- **Single prompt is sufficient.** Every journey is reachable from one prompt; multi-step setup is something Hermes does, not something the user does.
- **Branch-per-job.** Every journey that touches code runs in a job-scoped branch and worktree.
- **Decision ledger.** Every journey produces decision entries for at least worker pick, model pick, and (if applicable) merge pick and publish action.
- **One clear next action.** Every blocker surfaces with a single primary action in the cockpit.
- **Reversibility.** Every journey writes a `rollback.md` describing how to undo the run.
