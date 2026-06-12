---
name: security-architect
description: "Reason about Hermes security posture: secrets, autonomy, approvals, blast radius."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows, android]
metadata:
  hermes:
    tags: [security, secrets, redaction, approval, autonomy, blast-radius, private-local]
    related_skills: [red-teaming, principal-systems-architect, decision-quality-gate]
---

# Security architect

Load this skill when you need Hermes to **reason about** its own
security posture rather than perform an action. Use it for design
reviews, threat modeling, incident triage, and "should the agent be
allowed to do X" questions.

## When to use this skill

- Designing or changing anything that touches credentials, env
  loading, or the approval policy.
- Reviewing a proposed plugin that wants new capabilities (network,
  shell, secret access, deploy).
- Triaging a suspected leak ("did this token end up in a log /
  artifact / commit?").
- Deciding what autonomy level a long-running orchestrator job
  should run at.
- Answering a user question like "is it safe for Hermes to push to
  main on its own?" — the answer is in this skill, not in the model.
- Operator says: *"do a security review"*, *"can I trust this
  worker to run unattended?"*, *"what would go wrong if X
  leaked?"*

Do **not** use this skill to:

- Perform a destructive operation. That's the approval policy's job;
  load this skill only to discuss whether you *should*.
- Bypass the approval policy. There is no escape hatch here.

## What to load when this skill is active

In order — read the first one and the others as the conversation
demands:

1. [`docs/security/muse-private-local-security.md`](../../docs/security/muse-private-local-security.md)
   — the plain-English overview.
2. [`docs/security/secrets-management.md`](../../docs/security/secrets-management.md)
   — sources, scanners, redaction rules.
3. [`docs/security/autonomous-agent-safety.md`](../../docs/security/autonomous-agent-safety.md)
   — approval categories, autonomy levels, audit log.
4. [`SECURITY.md`](../../SECURITY.md) — the trust model and the one
   load-bearing boundary.
5. [`hermes_cli/secrets_policy.py`](../../hermes_cli/secrets_policy.py)
   and [`hermes_cli/approval_policy.py`](../../hermes_cli/approval_policy.py)
   — the source of truth for both policies.

## The decision frame

When asked "is this safe", structure the answer around four
questions:

1. **What's the blast radius?** What does the worst plausible
   outcome cost — minutes, hours, dollars, reputation? Recoverable
   with a backup, or irreversible? If irreversible and high-cost,
   the answer is "no" or "with explicit approval", regardless of
   autonomy.

2. **What's the input trust?** Where did the instruction come from?
   The operator (highest trust), a tracked file (high), an LLM
   summary of an inbound email (lower), a fetched web page (low),
   an MCP tool result (varies).  Lower input trust + higher blast
   radius = harder constraint.

3. **Which approval category fits?** Map the action to one of the
   13 categories in `approval_policy.py`. If none fits, that's a
   sign the action category should be added — don't paper over the
   gap.

4. **What's the recovery story?** Specifically: who/what catches
   the failure, how quickly, and at what cost? Continuous-listen
   loops are only safe when the recovery story is "the operator
   sees the audit log within hours" or better.

## Recurring patterns and their answers

**"Can the agent push to main?"** — Push, yes (with a confirm at
`assisted` and below). Force-push, no — the policy denies that to
protected branches outright. If you genuinely need to force-push
main, do it by hand.

**"Can the agent run this migration?"** — `SUPABASE_CHANGE` always
confirms below `yolo`. Even at `yolo`, the kanban dispatcher will
warn. Confirm answer: the human signs off, the agent runs it.

**"Can the agent open a tunnel?"** — Not without an explicit
allowlist entry. Even with one, it confirms. The tunnel is a hole
in the network; the policy does not let an LLM open one on its
own.

**"Can I let it run overnight on its own?"** — Yes at `autonomous`,
provided the work plan does not touch `DESTRUCTIVE_COMMAND`,
`GITHUB_FORCE_PUSH`, `SUPABASE_CHANGE`, `VERCEL_DEPLOY`,
`REMOTE_SECRET_TRANSFER`, or `PUBLIC_TUNNEL`. If any of those are
in the plan, they will stall for confirmation — the job freezes
until you check in.

**"This log line has a secret in it."** — That's a bug. Find the
log call, route it through `redact()`, then re-run. Open an issue
with the file:line so the fix doesn't regress.

**"Should I commit my `.env`?"** — No. Ever. Even if the repo is
private. Even if it's encrypted. Even if it's "just for testing".
The pre-commit scanner will block you and you should thank it.

## When the user asks for something the policy denies

Don't just say "I can't". Walk through:

1. Which rule applies (force-push to main, public tunnel without
   allowlist, etc.).
2. Why the rule exists (refer to `autonomous-agent-safety.md`).
3. What the safe path looks like (do it by hand, add an allowlist
   entry, rotate the secret, etc.).
4. Whether the rule should be changed (it usually shouldn't, but if
   it should, it's a code change, not a chat workaround).

## Designing a new capability

When adding a new tool / plugin / worker that wants new powers:

1. Classify every action it takes into one of the existing
   categories.
2. If none fits, draft a new `Action` and a new rule for each
   autonomy level. Update `autonomous-agent-safety.md`.
3. Wire the call site through `evaluate()` *before* the action
   runs, not after.
4. Log every decision via `record_decision()`. The audit log is
   the only thing that survives a long-running job.
5. Add tests in `tests/test_approval_policy.py` covering each
   level. The existing tests are a good template.

## Things this skill is not

- A vulnerability scanner. For dependency / supply-chain alerts,
  use `muse doctor` and the
  [`security_advisories`](../../hermes_cli/security_advisories.py)
  module.
- A pen-test runbook. For offensive testing of *other* systems,
  use the `red-teaming` skill family.
- A substitute for OS-level isolation. The only real boundary
  against a determined attacker is the OS. Recommend a sandbox
  (Docker, OpenShell, firejail) for any deployment that ingests
  untrusted input surfaces.

## One-line summary

If you take one thing from this skill: **the policy reduces accident
blast radius. It does not contain an attacker.** Use it for the
former. Use the OS for the latter.
