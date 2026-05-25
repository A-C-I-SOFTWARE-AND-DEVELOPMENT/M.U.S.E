---
name: supabase-architect
description: "Plan a Supabase schema change as a reviewable migration file. Designs tables, columns, RLS posture, and the local-first apply sequence. Never pushes to a remote project — produces a SQL file the operator commits, reviews, and applies under their own control."
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [integrations, supabase, schema, migrations, planning]
    related_skills:
      - github-publisher
      - vercel-deployment-planner
---

# Supabase architect

This skill helps you turn a schema requirement ("we need a `users`
table with email + created_at") into a versioned migration file under
`supabase/migrations/`. The migration is a normal repo artifact: it
gets PR-reviewed before it lands, and it gets applied by the operator
running the Supabase CLI under their own credentials.

## When to use this skill

- The user describes a data model and needs SQL.
- The user wants to add a column, table, index, or RLS policy.
- The user wants to capture an ad-hoc schema change as a proper
  migration rather than running raw SQL in the dashboard.

## When NOT to use this skill

- The change is a *one-shot* data fix (use the Supabase MCP server's
  `execute_sql` instead, with the user's explicit approval each time).
- The user is asking for a *query*, not a schema change.
- The user wants to mutate production data — that's not a migration,
  that's a maintenance task and needs a different process.

## The flow

1. **Gather the schema intent.** Tables, columns, types, RLS posture
   (enabled by default), foreign keys.
2. **Build the plan** with `hermes_cli.integrations.supabase.plan(...)`.
   This returns a `SupabasePlan` with:
   - the generated SQL,
   - the target file path,
   - the local-first command sequence,
   - the (approval-gated) remote command sequence,
   - rollback notes,
   - validation steps.
3. **Render the plan** with `explain(plan)` and show it to the user.
4. **Wait for explicit approval.** Do not write the file until the
   user says "go" / "approved" / equivalent.
5. **Call `execute(plan, approve=True)`** to write the migration file.
6. **Do not run `supabase db push` yourself.** Print the command from
   `plan.remote_commands` and let the operator run it.

## Defaults

- RLS is enabled on every new table unless the user explicitly opts
  out. A table without RLS is a security incident waiting to happen.
- Primary keys default to `uuid` + `gen_random_uuid()` unless the user
  prefers `bigserial` / `identity`. State the default and confirm.
- `created_at timestamptz not null default now()` and `updated_at`
  columns are suggested but not added without confirmation — they're
  application-policy, not framework-policy.
- Migration filenames use UTC timestamps to match what
  `supabase migration new` does.

## Things to ask the operator

- **Project link:** has `supabase link --project-ref <ref>` been run?
  If not, the remote push step will fail until it is.
- **Local stack:** is `supabase start` running? Required for
  `supabase db reset`.
- **Existing data:** if a column is being added to an existing table,
  what's the backfill plan? Migrations that add `NOT NULL` columns to
  populated tables without a default need a two-step rollout.
- **RLS bypass:** if the user wants RLS disabled, why? Capture the
  answer in the migration's `-- ` header.

## Secrets

- Never embed a JWT secret, service-role key, or DB password in a
  migration file. The adapter doesn't have access to those values
  anyway; if the user pastes one, refuse to include it.
- Seed data containing PII goes in a `.gitignored` seed file, not in
  a migration that ships to the repo.

## Output artifact

After `execute(plan, approve=True)` the migration file appears at:

```
supabase/migrations/YYYYMMDDHHMMSS_<slug>.sql
```

Stage it, commit it, push it through your normal PR flow (the
`github-publisher` skill can help). The Supabase change does not go
live until the operator runs `supabase db push` against the linked
project.

## See also

- [`docs/integrations/supabase.md`](../../docs/integrations/supabase.md)
- [`docs/integrations/integration-policy.md`](../../docs/integrations/integration-policy.md)
