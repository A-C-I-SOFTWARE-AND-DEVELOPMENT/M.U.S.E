# Hermes Private Local Posture

Companion to [`muse-10-10-product-spec.md`](./muse-10-10-product-spec.md).

This document defines what "private local" means for Hermes, why it is a deliberate product choice, and which self-protection guardrails remain non-negotiable even in a fully local deployment.

---

## 1. Why private local

Hermes is a private local-first developer command center. It is designed to run on machines the developer already controls — a laptop, a workstation, a Termux session on their own Android device — and to talk to model providers using the developer's own keys.

This posture exists because it reduces the security friction that comes with public-SaaS coding agents:

- **Source code stays local.** The repository is never copied into a vendor's backend in order for Hermes to function.
- **Secrets stay local.** Model keys, GitHub tokens, and any credentials referenced by jobs live in the user's environment, not in a Hermes-operated cloud.
- **Audit stays local.** Every artifact a job produces — prompts, plans, diffs, scores, validation outputs — is on the user's filesystem and inspectable without any Hermes-operated service.
- **No multi-tenant blast radius.** A bug in Hermes cannot leak one user's repo to another user's account because there are no shared tenants.
- **Compliance is the user's, not Hermes's.** Teams that cannot send source to a third-party SaaS for legal, contractual, or policy reasons can still use Hermes.

Reducing public-SaaS friction is the goal. Removing self-protection is **not** the goal. The guardrails below stay in place precisely because local deployment is what makes destructive autonomy possible without a vendor as a safety net.

---

## 2. What "private local" does, and does not, change

### Reduced friction
- No vendor data-processing agreement is required to operate Hermes.
- No vendor outage gates the user's work.
- No vendor telemetry collects prompts, repo contents, diffs, or filenames.
- No mandatory cloud account.
- No source upload to a third-party backend.

### Unchanged self-protection
Even on a fully local install, with the user's own machine, the user's own repo, and the user's own keys, Hermes still enforces the guardrails in §3. Local deployment lowers external trust requirements; it does not lower the bar for destructive-action safety.

---

## 3. Self-protection guardrails (always on)

These guardrails apply to every job, every worker, every workflow, regardless of deployment mode.

### 3.1 No secrets committed
- Hermes scans staged changes for secret-shaped strings (API keys, tokens, private keys, AWS access keys, etc.) before any commit.
- A match blocks the commit and surfaces a clear next action ("remove the literal", "reference via env var", "add to ignore list with justification").
- The scan runs on worker output too — workers cannot bypass it by writing the secret themselves.

### 3.2 No .env edits
- Hermes refuses to write to `.env`, `.env.*`, or any file the project marks as a secret store.
- When a job needs a new env var, Hermes records the requirement in `plan.md` and surfaces it to the user as a one-tap "add this key" prompt in the cockpit, but does not write the value to disk on the user's behalf into a committed location.

### 3.3 Branch-per-job
- Every job that touches code runs on a job-scoped branch in an isolated worktree.
- The user's primary working tree is never mutated by a worker.
- Job branches are named predictably so they are easy to inspect and clean up.

### 3.4 Rollback notes
- Every job writes a `rollback.md` describing exactly how to undo it (revert merge, delete branch, close PR, revert release tag, restore moved files, etc.).
- Rollback steps are concrete shell commands the user can run, not prose.

### 3.5 Destructive command approval
- Any command that deletes, force-overwrites, or rewrites history requires explicit user approval per invocation.
- The approval prompt names the exact command, the affected paths or refs, and the reason Hermes wants to run it.
- A user approving one destructive command does not approve future ones; approval scope never broadens silently.

### 3.6 Push approval
- `git push` requires explicit user approval per push.
- The approval prompt names the remote, the branch, and whether the push is creating, updating, or replacing the remote ref.
- A standing "allow all pushes" mode does not exist by default; if a user opts into one, it is per-repo and clearly indicated in the cockpit.

### 3.7 Force-push block
- `git push --force` and `git push --force-with-lease` are blocked by default.
- Override is per push, requires explicit user action, and is logged as a decision ledger entry.
- Force-push to protected branches (`main`, `master`, release branches per project config) requires a second, distinct confirmation.

### 3.8 Worker sandboxing
- Workers run with the working directory pinned to their assigned worktree.
- Workers do not receive credentials they were not explicitly granted by the routing decision; the decision ledger records which credentials a worker was allowed to see.

### 3.9 Network discipline
- Hermes makes outbound network calls only to (a) configured model providers, (b) configured git remotes, and (c) explicitly enabled tools that the user has activated.
- No "phone home" telemetry endpoint exists in the default build.

### 3.10 Reversible learning
- Updates to routing priors, prompt templates, and worker preferences are stored as plain files.
- A "revert learning to point in time X" command exists and is part of the supported surface.

---

## 4. Threat model

Hermes assumes:

- The user's machine is trusted.
- The user's keys are valid and authorized.
- The user's git remotes are configured by the user.
- The model providers the user configured are entities the user has chosen to trust.

Hermes does **not** assume:

- That every worker output is correct, safe, or non-malicious.
- That every command a worker proposes is one the user wants run.
- That model output is free of secrets, vulnerabilities, or destructive intent.

The guardrails in §3 are the response to that second list.

---

## 5. What this posture excludes

To stay honest about the boundary:

- **Closed-source workers we cannot invoke locally.** If a worker only exists as a vendor-hosted endpoint that requires uploading source, it is not a first-class Hermes worker.
- **Mandatory cloud accounts.** Hermes will not require a Hermes-branded account to operate.
- **Background telemetry.** Hermes will not ship a default-on telemetry pipeline that exfiltrates prompts, diffs, or repo metadata.
- **Cloud-side execution of user code.** Validation runs on the user's machine. Hermes does not silently spin up cloud sandboxes that receive the user's source.

If any future feature would violate these exclusions, it ships disabled by default, behind an explicit, named opt-in, with the cockpit clearly indicating it is active.

---

## 6. Verification

The private local posture is testable. A user can confirm it by:

- Disabling outbound network access except to their configured model providers and git remotes, and observing that Hermes still completes a full job.
- Inspecting the job folder and confirming that every artifact about the run exists on local disk.
- Running a secret-scan probe (a deliberately planted fake key) and confirming Hermes blocks the commit.
- Attempting a `git push --force` through Hermes and confirming it is blocked without an explicit override.
- Attempting a destructive command and confirming the approval prompt names the command and the affected refs/paths.

A release that fails any of these probes does not meet the private local bar.
