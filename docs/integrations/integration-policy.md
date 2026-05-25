# Integration policy

This document defines the rules every integration adapter under
`hermes_cli/integrations/` must follow. The goal is one consistent
safety posture across GitHub, Supabase, Vercel, and any future
service.

## 1. Plan first, execute only on approval

Every adapter exposes a four-call shape:

| Call          | Side effects                                              |
|---------------|-----------------------------------------------------------|
| `detect()`    | None. Probes the local environment for CLI presence.      |
| `plan(...)`   | None. Returns a dataclass describing the proposed action. |
| `explain(p)`  | None. Renders the plan in plain English for a human.      |
| `execute(p)`  | Only with `approve=True`. Some adapters require a second  |
|               | `approve_production=True` flag for prod-class actions.    |

The default invocation is *always* a dry-run. If the operator does not
pass `approve=True`, no branch is pushed, no migration is written, no
deploy is queued.

## 2. Detect CLI availability before suggesting commands

`detect()` returns a `Detection` dataclass with `cli_present: bool` and
operator-readable `notes`. The agent must surface those notes when the
CLI is missing instead of building a command the operator can't run.

## 3. Build commands as argv lists, never as shell strings

Plans expose `*_command: list[str]` so the operator (or test harness)
can `subprocess.run(cmd)` directly without quoting concerns. Rendering
to a string is only ever done in `explain()` for human display.

## 4. Block secret-shaped content at the boundary

* **GitHub**: filename + content scan via `github_publisher.scan_for_secrets`
  before any file is staged.
* **Supabase**: migrations are reviewed for embedded credentials at
  PR-review time; seed data with PII goes in a `.gitignored` seed file,
  not in the migration.
* **Vercel**: env var *values* never leave the operator's machine.
  Adapters only ever list env var *names*.

## 5. Emit a rollback note alongside every plan

Every plan dataclass carries a `rollback_notes: list[str]` field. The
note must describe the reversal action in concrete commands — not just
"revert if needed". For irreversible actions (destroyed data, deleted
deployments), the note must say so explicitly.

## 6. Emit a validation plan

`validation_steps: list[str]` describes what the operator can run or
inspect to confirm the action succeeded. CI passing is necessary but
not sufficient — the validation plan should also cover behavioural
checks (open the URL, hit the health endpoint, inspect RLS).

## 7. Never automate the "ship it" moment

* **GitHub**: PRs are always opened as drafts. Adapter never merges.
* **Supabase**: adapter writes the migration file; it never runs
  `supabase db push` against a remote project.
* **Vercel**: adapter prints the `vercel deploy` argv; the operator
  runs the deploy themselves. Production targets require a separate
  `approve_production=True` flag.

## 8. No network calls in `detect()` or `plan()`

These functions must be safe to call inside tests and inside
permission-restricted environments. Anything that needs a network goes
inside `execute()` and is gated by `approve=True`.

## 9. Secrets never appear in adapter state

* Adapter dataclasses never store API keys, OAuth tokens, or
  passwords. If an adapter needs a credential, it reads it from the
  ambient environment at `execute()` time and forgets it immediately.
* Plans, ledger entries, and PR bodies emitted by the adapter must not
  echo secret values back. The adapter's own logging must redact.

## 10. Failure mode: fail closed, never fail open

If the adapter cannot verify a precondition (CLI missing, repo not
linked, project name invalid), it raises and refuses to proceed.
There is no "best effort" execute path that silently degrades into a
half-done state.

---

## Adapter checklist

Use this when adding a new integration:

- [ ] Implements `detect()`, `plan()`, `explain()`, `execute()`.
- [ ] `detect()` makes no network call.
- [ ] `plan()` returns a frozen dataclass carrying `approval_required`,
      `dry_run`, `rollback_notes`, and `validation_steps`.
- [ ] `execute()` refuses to run unless `approve=True`.
- [ ] Any "production" or otherwise-irreversible action requires a
      second approval flag.
- [ ] Commands are built as `list[str]` argv, not shell strings.
- [ ] Secret-shaped content is rejected at the boundary.
- [ ] A doc page lives at `docs/integrations/<service>.md`.
- [ ] A skill lives at `skills/<service>-*/SKILL.md` describing the
      human-in-the-loop flow.
- [ ] Tests at `tests/test_integration_<service>.py` cover the
      detect/plan/explain/execute contract.
