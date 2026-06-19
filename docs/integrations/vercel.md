# Vercel integration

Module: `hermes_cli.integrations.vercel`
Skill:  [`skills/vercel-deployment-planner/SKILL.md`](../../skills/vercel-deployment-planner/SKILL.md)
Policy: [`docs/integrations/integration-policy.md`](./integration-policy.md)

## What it does

Builds a Vercel deployment plan: project name, target environment,
expected env vars, and the exact `vercel` argv that would be invoked.

The adapter is intentionally hands-off about *running* the deploy. It
clears the approval gate and prints the command — the operator runs
`vercel deploy` themselves in a shell that has the correct token.

## What it never does

- Run `vercel deploy` automatically.
- Print, store, or transmit the *value* of any env var. Only names.
- Promote a preview deployment to production without a second explicit
  approval flag (`approve_production=True`).
- Roll back by deleting deployments. Rollback is always via promotion
  of a prior known-good deployment.

## CLI requirements

| Tool     | Required? | Used for                       |
|----------|-----------|--------------------------------|
| `vercel` | yes for execute | deploy + env management   |
| `node`   | yes       | required by the Vercel CLI     |

`detect()` also reports whether `vercel.json` exists at the project
root, and whether `.vercel/project.json` is present (i.e. whether
`vercel link` has been run).

## Building a plan

```python
from hermes_cli.integrations import vercel

p = vercel.plan(
    project_name="hermes-web",
    target="preview",
    env_vars=[
        vercel.EnvVarSpec("NEXT_PUBLIC_API_URL", secret=False),
        vercel.EnvVarSpec("SUPABASE_SERVICE_ROLE_KEY", targets=("production",)),
    ],
)
print(vercel.explain(p))
vercel.execute(p, approve=True)      # gate cleared; operator runs the cmd
```

For production:

```python
p = vercel.plan(project_name="hermes-web", target="production", env_vars=[...])
vercel.execute(p, approve=True, approve_production=True)
```

Without `approve_production=True`, `execute()` refuses to clear the
gate even if `approve=True` is passed.

## Env-var policy

- Env var **names** may be committed (e.g. in `.env.example`); values
  must not.
- Add or rotate secrets via `vercel env add` or the dashboard. muse
  never sends env values to Vercel.
- If an env var is missing for the target environment, the deploy will
  succeed but the app will fail at runtime — confirm presence in the
  dashboard before approving.
- Treat preview env vars as production-equivalent for any secret that
  grants real data access.

## Approval

| Target       | Flags required                                |
|--------------|-----------------------------------------------|
| `preview`    | `approve=True`                                |
| `production` | `approve=True` **and** `approve_production=True` |

The double-approval rule for production exists because preview deploys
are easily reversible (just don't promote them); production deploys
are not.

## Rollback

- Vercel dashboard → Deployments → previous successful deployment →
  *Promote to Production*.
- Or via CLI: `vercel rollback <deployment-url>`.
- **Never delete a deployment as a rollback** — promotion is
  reversible, deletion is not.

## Validation

- `vercel deploy` prints a URL and exits 0.
- Open the preview URL and exercise the golden path.
- Hit `/api/_health` (or equivalent) and confirm 200.
- For production, monitor error rates in the dashboard for the first
  10 minutes before walking away.

## Related

- [`hermes_cli/vercel_auth.py`](../../hermes_cli/vercel_auth.py) —
  the OAuth/device-code login flow muse uses for the Vercel CLI.
