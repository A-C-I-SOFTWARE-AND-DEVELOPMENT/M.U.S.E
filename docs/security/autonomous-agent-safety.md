# Autonomous agent safety

M.U.S.E. can run at varying degrees of autonomy. The approval policy
([`hermes_cli/approval_policy.py`](../../hermes_cli/approval_policy.py))
decides, for each proposed action, whether the agent may proceed on
its own, must pause for a confirmation prompt, or must refuse
outright.

This doc explains the model, the autonomy levels, and the rules that
hold regardless of how much rope you've given the agent.

## The mental model

Every proposed action has a category. There are 13 of them:

| Category                    | What it is                                                        |
|-----------------------------|-------------------------------------------------------------------|
| `SAFE_READ`                 | Reading tracked files, listing directories.                       |
| `SAFE_LOCAL_WRITE`          | Writing inside the worktree.                                      |
| `LOCAL_COMMAND`             | Running tests, type-checkers, formatters.                         |
| `DESTRUCTIVE_COMMAND`       | `rm -rf`, `git reset --hard`, drop-table, kill-process.           |
| `REMOTE_COMMAND`            | Anything that runs off-host (SSH, modal, daytona).                |
| `SECRET_ACCESS`             | Reading a credential by name.                                     |
| `REMOTE_SECRET_TRANSFER`    | Sending a credential to a worker outside this host.               |
| `GITHUB_PUSH`               | `git push` to any remote.                                         |
| `GITHUB_FORCE_PUSH`         | `git push --force` / `--force-with-lease`.                        |
| `SUPABASE_CHANGE`           | `apply_migration`, `execute_sql` with DDL.                        |
| `VERCEL_DEPLOY`             | `deploy_to_vercel`, `promote`.                                    |
| `PUBLIC_TUNNEL`             | cloudflared, ngrok, tailscale-funnel.                             |
| `CONTINUOUS_LISTEN`         | Subscribe-and-react loops (PR webhooks, cron jobs).               |

Every action ends up with a `Decision`:

- **`ALLOW`** — the agent proceeds unattended.
- **`CONFIRM`** — the gateway surfaces a prompt; agent waits.
- **`DENY`** — the agent does not proceed; no prompt either.

## The autonomy levels

Set with `HERMES_AUTONOMY=...` or via `/autonomy <level>` at the CLI.

| Level         | Behavior                                                                      |
|---------------|-------------------------------------------------------------------------------|
| `read_only`   | Only `SAFE_READ` runs. Everything else denied.                                |
| `assisted`    | Default. Safe reads run; everything else confirms.                            |
| `autonomous`  | Safe + local-command + safe writes + secret-access + listen run unattended.   |
| `yolo`        | Almost everything runs. Hard-limit set still applies.                         |

## The hard-limit set

Even at `yolo`, these never run unattended — they always either
prompt or deny:

1. **`GITHUB_FORCE_PUSH` to a protected branch.** `main`, `master`,
   `release`, `production`, `prod` (and any custom set you've
   configured). **Always denied.** No prompt.
2. **`REMOTE_SECRET_TRANSFER` without an explicit target.** Always
   denied. With a named target, still always confirmed.
3. **`PUBLIC_TUNNEL` without an allowlist entry.** Always denied.
   With an allowlist entry, still always confirmed.

You can't turn these off with an env var. The point of a policy is
to be a policy.

## What "always confirms" means in practice

For: `DESTRUCTIVE_COMMAND`, `GITHUB_PUSH`, `GITHUB_FORCE_PUSH`
(non-protected), `SUPABASE_CHANGE`, `VERCEL_DEPLOY`,
`REMOTE_SECRET_TRANSFER` (with target), `PUBLIC_TUNNEL` (with
allowlist):

- At `read_only` / `assisted` / `autonomous`: prompts every time.
- At `yolo`: prompts every time *except* the always-confirm
  categories not in the hard-limit set — those get auto-approved.

## Why each rule is there

- **Destructive-command always confirms.** Recovery from a wrong
  `rm -rf` is hours of work at best, "restore from backup" at worst.
  One confirm prompt is cheap.
- **Force-push to main always denies.** Lost commits on `main` are a
  team-wide outage. No agent should ever make that call without a
  human being in the loop. If you really need it, do it by hand.
- **Remote secret transfer requires a target.** "Send the
  `SUPABASE_SERVICE_ROLE_KEY` to the worker pool" is the kind of
  sentence that needs an explicit destination. The policy refuses
  to let "to the worker pool" mean "to whoever is listening".
- **Public tunnel requires an allowlist.** Punching a hole in your
  network so an LLM-driven worker can reach back through it is
  exactly the kind of decision that shouldn't be made by the
  worker.
- **Continuous-listen is allowed in `autonomous`.** PR-watch and
  cron loops *are* the autonomous use case. They're allowed
  unattended at `autonomous`, but they don't escalate their own
  privileges — the actions *inside* a loop iteration still go
  through the policy.

## Every decision is logged

`record_decision()` appends a redacted JSON line to
`~/.hermes/approval.log`:

```json
{
  "ts": 1716501234.123,
  "actor": "agent",
  "action": "github_push",
  "summary": "push feature branch",
  "target": "origin/feature/x",
  "branch": "feature/x",
  "remote_branch": "feature/x",
  "details": {},
  "decision": "confirm",
  "reason": "github_push requires operator confirmation",
  "needs_prompt": true
}
```

The summary, target, and details are all run through `redact()`
before write. If you ever see a raw secret in the audit log, that's
a bug — file an issue.

## Working with the policy from the inside

If you're a plugin author or a worker, you should never bypass the
policy. The API is:

```python
from hermes_cli.approval_policy import (
    Action,
    ApprovalRequest,
    evaluate,
    record_decision,
)

req = ApprovalRequest(
    action=Action.DESTRUCTIVE_COMMAND,
    summary="rm -rf the build cache",
    target=".cache/",
)
result = evaluate(req)
record_decision(req, result)

if result.decision is not result.decision.ALLOW:
    # Either surface the prompt (CONFIRM) or refuse (DENY).
    ...
```

The orchestrator's worker adapters (`docs/orchestration/worker-adapter-interface.md`)
already route every shell call through `evaluate()`. New adapters
should do the same; if you find yourself wanting to skip it, that's
a sign the action belongs in a new `Action` category.

## A note on "yolo"

`yolo` exists for narrow, recoverable tasks:

- Mass test-suite triage where you'd hit `y` to every prompt anyway.
- Bulk-rename or codemod runs on a throwaway branch.
- Building a one-off scratch project.

It is **not** the right setting for long-running orchestrator jobs
that touch production. The kanban dispatcher will warn you if a job
that touches `Action.VERCEL_DEPLOY` is launched at `yolo` — the warn
is non-blocking, but read it.

## Related

- [`secrets-management.md`](secrets-management.md) — the redaction
  side of the policy.
- [`hermes-private-local-security.md`](hermes-private-local-security.md)
  — the high-level "why".
- [`SECURITY.md`](../../SECURITY.md) — the trust model and reporting
  policy.
- [`docs/orchestration/worker-adapter-interface.md`](../orchestration/worker-adapter-interface.md)
  — where the policy plugs into the orchestrator.
