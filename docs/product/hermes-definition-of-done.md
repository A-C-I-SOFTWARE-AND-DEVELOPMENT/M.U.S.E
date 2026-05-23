# Hermes 10/10 Definition of Done

Companion to [`hermes-10-10-product-spec.md`](./hermes-10-10-product-spec.md).

This document is the literal checklist. Hermes is "10/10" when every item below is true in a fresh clone, run end to end against a real repository, without manual intervention beyond the user-approval gates the product intentionally requires.

A release is **not** 10/10 if any single item is missing, partial, or only true on the maintainer's machine. There is no partial credit.

---

## A. Single-prompt entry

- [ ] A single user prompt, issued from the Android cockpit, the TUI, or the local CLI, creates a job.
- [ ] The job has a unique id and a durable folder under the Hermes state directory at the moment it is created — not lazily, not after first success.
- [ ] No second user action is required to "start" the job.

## B. Durable artifacts

- [ ] Every job folder contains, at minimum: `prompt.md`, `plan.md`, `decisions/`, `workers/`, `scoring.md`, `merge.md`, `validation/`, `publish.md`, `learning.md`, `rollback.md`, `events.jsonl`.
- [ ] Artifacts exist even for failed, abandoned, or aborted jobs (so post-mortems are possible).
- [ ] Artifacts are plain files a developer can inspect with `cat`, `less`, or a text editor with no Hermes process running.

## C. Decision ledger

- [ ] Each of the following decisions produces a ledger entry under `decisions/`:
  - [ ] worker selection
  - [ ] model selection
  - [ ] plan-vs-execute split
  - [ ] merge choice (winning worker, rejected alternatives)
  - [ ] validation-failure response (retry vs surface)
  - [ ] publish target (draft vs ready, base branch)
  - [ ] destructive command approval
- [ ] Each entry names the decision, alternatives, rationale, reversibility, and confidence.

## D. Repo and tool awareness

- [ ] Hermes detects the repo's language(s), framework, package manager, test runner, lint/format tools, and CI shape on every job.
- [ ] Hermes detects locally installed CLIs and configured model provider keys.
- [ ] Detected state is written into the job's `plan.md` and is an input to routing.

## E. Routing

- [ ] Hermes selects a worker/model mix using a rubric that combines capability, cost, and priors.
- [ ] The selection is explainable — the rubric inputs and outputs are written to the decision ledger.
- [ ] The selection is not hardcoded per repo; changing the detected state changes the choice.

## F. Worker prompts

- [ ] Hermes generates a worker-specific prompt for each chosen worker.
- [ ] Each prompt follows that worker's CLI conventions (Claude Code style, Codex style, Aider style, etc.).
- [ ] Each prompt is copyable from the cockpit, TUI, and local CLI so the developer can run it manually if desired.

## G. Local-CLI invocation

- [ ] When an official local CLI is installed (`claude`, `codex`, `aider`, `cursor-agent`, `gh`, `git`, etc.), Hermes invokes it directly rather than reimplementing it.
- [ ] When a CLI is missing, Hermes either selects an alternate worker or surfaces a single clear next action ("install X to enable Y").

## H. Isolation

- [ ] Every job runs in an isolated git worktree on a job-scoped branch.
- [ ] No worker is permitted to mutate the user's primary working tree.
- [ ] Worktrees are reclaimed on job completion, but their diffs remain captured in the job folder.

## I. Output collection

- [ ] Each worker's diff, stdout, stderr, exit code, runtime logs, and self-reported notes are written to `workers/<worker>/`.
- [ ] No worker output is silently dropped; partial/failed outputs are still captured for scoring.

## J. Scoring

- [ ] A scoring pass produces a comparable numeric (or ordinal) score per worker output.
- [ ] `scoring.md` contains the rubric, the per-worker scores, and the rationale.
- [ ] When only one worker ran, the scoring artifact still exists and records that.

## K. Merge

- [ ] Hermes applies the winning diff to the job branch.
- [ ] Losing diffs are preserved under `workers/<worker>/` for post-hoc inspection.
- [ ] `merge.md` records what was merged, what was rejected, and why.

## L. Validation

- [ ] Static (lint/format/type), dynamic (tests, project hooks), and behavioral (run-the-app probes for UI/runtime-visible changes) validation each have outputs under `validation/`.
- [ ] Failed validation triggers a bounded self-repair loop; once exhausted, it surfaces a blocker with one clear next action.
- [ ] No claim of "validated" appears in the UI when only static checks ran on a change that needed behavioral validation.

## M. Publishing

- [ ] Hermes can open a GitHub PR from the job branch, **as draft by default**.
- [ ] The PR body includes the prompt, plan summary, decision ledger excerpts, scoring summary, validation summary, and rollback notes.
- [ ] Push and PR creation respect the user-configured approval policy.
- [ ] Force-push is blocked unless the user explicitly overrides per push.

## N. Learning

- [ ] After each job, routing priors, prompt-template weights, and per-worker cost models update based on outcomes.
- [ ] `learning.md` per job records what changed.
- [ ] Learning state is local, inspectable, and reversible.

## O. Visibility

- [ ] The Android cockpit shows: jobs list, per-job status, current step, latest event, the one clear next action.
- [ ] The cockpit can open: prompt, plan, decision ledger, per-worker diffs, scoring table, validation outputs, GitHub PR link and status.
- [ ] No agent state exists that the UI cannot show.
- [ ] The TUI and any web UI render the same projections from the same job folder.

## P. Self-protection

- [ ] Hermes refuses to commit or write secret-shaped strings (API keys, tokens, private keys).
- [ ] Hermes refuses to edit `.env` files or anything matched by the project's secret patterns.
- [ ] Hermes refuses to run destructive shell commands (rm -rf, force-push, branch delete, db drop, etc.) without explicit per-action user approval.
- [ ] Hermes refuses to push without explicit user approval per push policy.
- [ ] Hermes blocks force-push by default.

## Q. Private local posture

- [ ] No source code, credentials, or model keys leave the user's machine except to the providers the user has explicitly configured.
- [ ] No telemetry of repo contents, prompts, or diffs is sent anywhere by default.
- [ ] The full job folder lives on the user's filesystem; no remote state is required for inspection or rollback.

## R. Reversibility

- [ ] Every job writes a `rollback.md` describing how to undo it (revert merge, delete branch, close PR, revert release tag, etc.).
- [ ] Rolling a job back never requires editing Hermes' internal state by hand.

---

## How to test

A 10/10 audit is a fresh end-to-end run on a real repository, exercising at least one journey from each section of [`hermes-user-journeys.md`](./hermes-user-journeys.md). For each journey, walk the checklist above. Any unchecked box fails the audit.

The audit must be reproducible on:
- A Linux laptop with the full toolchain.
- An Android device with Termux, with at least one model provider key configured.

If any item passes only in one environment, that item fails.
