---
name: vercel-deployment-planner
description: "Plan a Vercel preview or production deployment. Builds the exact `vercel` argv, lists required env var names, and emits rollback + validation notes. Never runs the deploy itself — clears the approval gate so the operator runs the command under their own credentials."
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [integrations, vercel, deployment, planning]
    related_skills:
      - github-publisher
      - supabase-architect
---

# Vercel deployment planner

This skill turns "I want to ship this to Vercel" into a structured
plan the operator can review and execute. The plan includes the exact
`vercel deploy` argv, the env vars the deployment expects (names
only — never values), rollback steps, and validation steps.

## When to use this skill

- The user is about to ship a frontend / serverless project to Vercel.
- The user wants a sanity check before running `vercel --prod`.
- The user wants to document a deployment in the orchestration ledger
  for later auditing.

## When NOT to use this skill

- The user just wants a quick `vercel dev` for local iteration.
- The deployment target isn't Vercel.
- The user is asking about env var *values* — those are out of scope
  for this skill (and for Hermes generally).

## The flow

1. **Confirm the target.** "preview" or "production"? If the user
   isn't explicit, ask. Default to "preview".
2. **Confirm the project link.** `detect()` reports whether
   `.vercel/project.json` exists. If not, the operator needs to run
   `vercel link` interactively first — Hermes never runs it.
3. **List the required env vars.** Names only. If the user names a
   var, also ask which `targets` it applies to
   (development / preview / production). Default is all three.
4. **Build the plan** with
   `hermes_cli.integrations.vercel.plan(project_name=..., target=..., env_vars=[...])`.
5. **Render with `explain(plan)`** and show it to the user.
6. **Wait for approval.**
   - Preview: needs `approve=True`.
   - Production: needs both `approve=True` and
     `approve_production=True`. Confirm the operator understands the
     blast radius.
7. **Call `execute(plan, approve=True, approve_production=...)`** to
   clear the gate.
8. **Do not run `vercel deploy` yourself.** Print
   `plan.deploy_command` and let the operator run it in a shell with
   the Vercel CLI logged in.

## Env-var policy (always echo this to the user)

- Names are public; values are not. Hermes only ever lists names.
- Values are set via `vercel env add` or the dashboard.
- Missing env vars cause runtime failures, not deploy failures —
  verify before approval.
- Preview env vars are production-equivalent for any secret with real
  data access.

## Rollback (always echo this to the user)

- Dashboard → Deployments → previous good deploy → "Promote to
  Production".
- Or: `vercel rollback <deployment-url>`.
- **Never delete a deployment as a rollback** — promotion is
  reversible, deletion is not.

## Validation

- `vercel deploy` prints a URL and exits 0.
- Operator opens the URL and runs the golden-path flow.
- Operator hits `/api/_health` (or equivalent) and confirms 200.
- For production, monitor error rates for the first 10 minutes.

## Things to ask the operator

- **Target environment:** preview vs production. Always confirm.
- **Linked project:** has `vercel link` been run? If not, halt.
- **Env vars:** which ones are required for this build? Are all of
  them present in the Vercel dashboard for the target environment?
- **Recent migrations:** if a Supabase migration just shipped, has it
  been applied remotely? A deploy against a stale schema will boot
  and then fail at first request.

## See also

- [`docs/integrations/vercel.md`](../../docs/integrations/vercel.md)
- [`docs/integrations/integration-policy.md`](../../docs/integrations/integration-policy.md)
- [`hermes_cli/vercel_auth.py`](../../hermes_cli/vercel_auth.py) — the
  device-code login flow Hermes uses for the Vercel CLI itself.
