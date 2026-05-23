# Hermes 10/10 Product Spec

Status: canonical (Phase 01)
Audience: Hermes maintainers, contributors, and integration partners
Companion docs:
- [`hermes-user-journeys.md`](./hermes-user-journeys.md)
- [`hermes-definition-of-done.md`](./hermes-definition-of-done.md)
- [`hermes-private-local-posture.md`](./hermes-private-local-posture.md)

---

## 1. Product thesis

**Hermes is the command center.** It is the single surface a developer talks to. One prompt is enough to start work; everything that follows — analysis, planning, routing, execution, scoring, merging, validation, publishing, and learning — happens behind that prompt without the user needing to drive a second tool.

The shape of the system is intentional:

- **Hermes is the command center.** It owns intent, decisions, artifacts, scoring, and audit.
- **The Android APK is the cockpit.** It is the primary visibility and approval surface — status-first, phone-friendly, designed for one-thumb operation while away from the desk.
- **Termux (and any local shell) is the engine.** It hosts the orchestrator, worktrees, model calls, and worker processes. Hermes assumes local-first execution and treats the cloud as optional.
- **External coding tools are workers.** Claude Code, Codex CLI, Cursor CLI, Aider, OpenHands, Continue, MiniSWE, custom scripts — these are interchangeable workers Hermes routes to. None of them is the product; Hermes is.

This is what we mean by **private local**: the developer's repo, secrets, model keys, and worker processes stay on machines the developer controls. Hermes reduces the public-SaaS security friction that comes from sending source and credentials to a vendor backend, while keeping the self-protection guardrails (no secret commits, branch-per-job, destructive command approval, force-push block) that make autonomous execution safe.

The 10/10 bar means: a developer types one prompt on their phone, walks away, and comes back to a reviewable PR, a decision ledger explaining every nontrivial choice, scored worker outputs, validation results, and a learning update — all inspectable, all reversible.

---

## 2. Core capabilities

Hermes is a 10/10 product when it can, end to end, from a single prompt:

1. **Understand the repo.** Detect language, framework, package manager, test runner, lint/format tools, CI shape, and prior Hermes job history.
2. **Detect local tools.** Enumerate which CLIs are installed (claude, codex, cursor-agent, aider, gh, git, node, python, uv, pnpm, docker, etc.) and which model providers have keys configured.
3. **Plan.** Produce a structured plan: goal, subgoals, candidate workers, candidate models, expected artifacts, validation strategy, rollback plan.
4. **Route.** Choose the best worker/model mix for the job, with the choice and the alternatives recorded in a decision ledger.
5. **Generate worker prompts.** Emit a worker-specific prompt for each chosen worker — a Claude Code prompt, a Codex prompt, an Aider prompt — that is copyable so a human can run it manually too.
6. **Run.** Spawn workers in isolated git worktrees (branch-per-job), in parallel when useful, with logs captured to the job folder.
7. **Collect.** Gather each worker's diff, test output, lint output, runtime logs, and worker-reported notes into durable artifacts.
8. **Score.** Apply a rubric (correctness signals, validation passing, diff size, risk surface, prior-success priors) and produce per-worker scores with rationale.
9. **Merge.** Pick the winning result, apply it to the job branch, and record why competing results were rejected.
10. **Validate.** Run tests, linters, type checks, and any project-defined validation hook. If validation fails, attempt bounded self-repair before surfacing a blocker.
11. **Publish.** Open or update a GitHub PR (as draft by default), attach the decision ledger and validation summary, request review when ready.
12. **Learn.** Update routing priors, prompt templates, and worker preferences based on what scored well and what shipped.
13. **Be visible.** Show all of the above — status, logs, diffs, validation, GitHub actions — in the Android cockpit, with the same data accessible in the TUI/web UI.

If any one of these is missing, Hermes is below 10/10.

---

## 3. System shape

### 3.1 Roles
- **User.** Issues prompts, approves destructive or publish actions, reviews PRs.
- **Cockpit (Android APK).** Surfaces job state, prompts for approvals, exposes copyable worker prompts.
- **Command center (Hermes core).** Owns the job lifecycle: plan, route, score, merge, validate, publish, learn.
- **Engine (Termux/local backend).** Hosts the orchestrator process, worktrees, and worker subprocesses.
- **Workers.** External coding tools (Claude Code, Codex CLI, Aider, OpenHands, MiniSWE, custom). Hermes calls them; they do not call Hermes.

### 3.2 Artifacts
Every job produces a durable folder under the Hermes state directory:

```
jobs/<job-id>/
  prompt.md              # original user prompt + parsed intent
  plan.md                # structured plan
  decisions/             # decision ledger entries (one file per decision)
  workers/<worker>/      # per-worker prompt, logs, diff, score, notes
  scoring.md             # comparison table and rationale
  merge.md               # what was merged, what was rejected
  validation/            # test/lint/type-check outputs
  publish.md             # GitHub PR link, review state, CI status
  learning.md            # updated priors / template diffs
  rollback.md            # how to revert this job
  events.jsonl           # append-only event log for the UI
```

These files are the source of truth. Every UI view is a projection of this folder. A developer can `cd` into the job folder and reconstruct the entire run without Hermes running.

### 3.3 Decision ledger
A decision ledger entry is a short markdown file with:
- **Decision:** what was chosen
- **Alternatives:** what was considered
- **Why:** the reasoning, including any rubric scores or detected-tool inputs
- **Reversibility:** how to undo this choice
- **Confidence:** low / medium / high

Decisions that always get a ledger entry: worker selection, model selection, plan-vs-execute split, merge choice, validation-failure response (retry vs surface), publish target (draft vs ready, base branch), destructive command approval.

---

## 4. 10/10 acceptance criteria

These are the literal pass/fail checks that define the 10/10 bar. The [Definition of Done](./hermes-definition-of-done.md) restates them as a checklist.

1. **One prompt creates a job.** A single user prompt is sufficient to instantiate a job folder, a plan, and a worktree. No second step required to "start" it.
2. **Every job has durable folder artifacts.** The structure in §3.2 exists for every job, even failed or abandoned ones.
3. **Every major decision has a decision ledger entry.** Worker pick, model pick, merge pick, publish action — all logged.
4. **Hermes detects local tools.** A tool-detection pass runs at job start; results are an input to routing and are recorded in the plan.
5. **Hermes chooses the best worker/model mix.** Routing is rubric-based and explainable, not hardcoded.
6. **Hermes can generate worker-specific prompts.** Each chosen worker gets a prompt tailored to its CLI conventions, and that prompt is copyable from the UI.
7. **Hermes can run official local CLIs when available.** When `claude`, `codex`, `aider`, etc. are installed, Hermes invokes them directly rather than reimplementing them.
8. **Hermes can create isolated worktrees.** Branch-per-job. Workers never operate on the user's checked-out working tree.
9. **Hermes can collect outputs.** Diff, logs, test results, worker self-notes — all written to the job folder.
10. **Hermes can score outputs.** A scoring pass produces a comparable score per worker output with rationale.
11. **Hermes can merge the best result.** The winning diff is applied to the job branch; losers are preserved as artifacts.
12. **Hermes can validate.** Tests, lint, type checks, and any project-defined validation hook run on the merged result.
13. **Hermes can publish to GitHub.** Draft PR by default, decision ledger and validation summary attached, review requested when ready.
14. **Hermes can learn from job results.** Routing priors, prompt templates, and worker preferences update based on outcomes.
15. **UI shows status, logs, diffs, validation, GitHub actions.** Every artifact is inspectable from the cockpit; nothing about agent state is hidden.

---

## 5. Worker model

Workers are first-class but interchangeable. Hermes treats every worker as a black box defined by:

- **Invocation contract.** How to start it (CLI args, env vars, stdin, working directory).
- **Prompt contract.** What format of prompt it expects.
- **Output contract.** How its diff, logs, and self-notes are captured.
- **Capabilities.** What it can do well (refactor, debug, docs, multi-file edits, long-context, browser-driven, etc.).
- **Cost.** Token cost, wall-clock cost, blast radius.
- **Priors.** Historical success rate for this repo, language, and task type.

Routing combines capabilities, cost, and priors with the current detected-tools snapshot to pick one or more workers. When parallel execution is useful (high uncertainty, conflicting priors, contested task type), Hermes runs multiple workers in separate worktrees and scores the results.

---

## 6. Validation model

Validation has three layers:

1. **Static.** Lint, format, type check.
2. **Dynamic.** Unit tests, integration tests, project-defined validation hooks.
3. **Behavioral.** For UI or runtime-visible changes, Hermes runs the app and observes (per the `verify` and `run` skills) before declaring success.

Validation failure is not silent. It triggers a bounded self-repair loop (default: up to N attempts, configurable per project). If repair fails, the job surfaces a blocker with one clear next action — never a wall of red.

---

## 7. Publish model

Publishing is deliberate:

- Default state: **draft PR**.
- PR body includes: prompt, plan summary, decision ledger excerpts, scoring table, validation summary, rollback notes, link to the local job folder path on the user's machine.
- Force-push is **blocked** by default on shared branches; the user must explicitly override.
- Push and PR-creation always require the user-configured approval policy to permit them (see [private local posture](./hermes-private-local-posture.md)).

---

## 8. Learning model

After every job, Hermes updates:

- **Routing priors.** Per (language × task type × worker × model) success rate.
- **Prompt templates.** When a worker prompt led to a winning score, the template's weight goes up; when it lost, down.
- **Validation strategy.** Which checks were the most predictive of merge success.
- **Cost model.** Wall-clock and token cost per worker for this repo.

All learning state is local, inspectable, and reversible. A `learning.md` per job records what changed.

---

## 9. UI/UX principles

These are non-negotiable surface rules. They apply to the Android cockpit, the TUI, and any web UI.

1. **No hidden agent state.** If the orchestrator knows it, the UI can show it.
2. **All artifacts inspectable.** Every file in the job folder is reachable from the UI; the UI is a projection, never a translation that drops information.
3. **Every blocker has one clear next action.** If Hermes is stuck, the cockpit shows exactly one primary button: "Approve push", "Retry with Codex", "Open diff", "Resolve secret reference". Never an undifferentiated wall of errors.
4. **Phone-friendly, status-first.** The default cockpit view is a vertical list of jobs, each with status, current step, and the one-tap next action. Detail views are reachable but not in the way.
5. **Copyable worker prompts.** Every generated worker prompt is one tap away from the clipboard, so a developer can run it manually in any worker CLI if they want.
6. **Visible quality scores.** Scores are shown as numbers with their rationale visible, not as opaque badges.

---

## 10. Out of scope (for this phase)

- Replacing any specific worker tool. Hermes orchestrates them; it does not compete with them.
- Hosting a Hermes-branded model service. Hermes uses whichever providers the user has keys for.
- Multi-tenant SaaS. The private local posture is the product.
- Closed-source workers we cannot invoke from a local CLI.

---

## 11. Glossary

- **Job.** One end-to-end run kicked off by a prompt.
- **Worker.** An external coding tool Hermes invokes.
- **Worktree.** A git worktree used to isolate a worker's edits.
- **Decision ledger.** The set of decision records for a job.
- **Cockpit.** The Android APK UI.
- **Engine.** The Termux / local backend that runs the orchestrator.
- **Command center.** Hermes core: the orchestration brain.
- **Private local.** The deployment posture: code, keys, workers stay on user-controlled machines.
- **10/10.** The acceptance bar in §4.
