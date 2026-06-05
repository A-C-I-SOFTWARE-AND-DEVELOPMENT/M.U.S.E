# vercel plugin

Native Vercel REST access for Hermes. Seven tools under the `vercel` toolset:

| Tool | Kind | What it does |
|---|---|---|
| `vercel_list_projects` | read | List projects the token can access. |
| `vercel_get_deployment` | read | Status + metadata for one deployment. |
| `vercel_get_preview_url` | read | URL + state of a project's most recent deployment. |
| `vercel_tail_logs` | read | Recent build/runtime log events for a deployment. |
| `vercel_set_env` | write · gated | Set a project environment variable. |
| `vercel_deploy` | write · gated | Trigger a deploy via a project Deploy Hook URL. |
| `vercel_cancel_deployment` | write · gated | Cancel an in-progress deployment. |

## Configuration

`VERCEL_TOKEN` lives in the environment or `~/.hermes/.env`. It is read only
into the `Authorization` header — never logged, never returned to the model,
never sent to the Android cockpit.

Add a `vercel:` block to `~/.hermes/config.yaml`:

```yaml
vercel:
  enabled: true            # master switch (default: false)
  allow_writes: false      # write tools refuse without this (default: false)
  allowed_projects:        # optional; empty = no allowlist enforced
    - "my-app"
```

## Safety model

Writes pass three independent gates:

1. `vercel.enabled` is true **and** `VERCEL_TOKEN` is set.
2. `vercel.allow_writes` is true **and** the project is on the allowlist.
3. The unified **decision engine** returns a verdict (`ask` for these
   owner-gated actions). Write tools are **propose-only**: they return the
   verdict with `executed: false` and never perform the mutation or trust a
   model-supplied phrase — a tool cannot enforce an owner gate on a value the
   model controls (and the owner phrase is a public constant). A `refuse`
   verdict always blocks.

Env-var **values** and deploy-hook URLs are never echoed back in a tool
response; tokens are scrubbed from any error text.

## Execution (out-of-band)

The approved mutation is performed by `plugins/vercel/executor.py`
(`apply_set_env` / `apply_deploy` / `apply_cancel`), registered into the
owner-gated `hermes_cli.action_executors` registry (`vercel.set_env`,
`vercel.deploy`, `vercel.cancel_deployment`). These run **only** off the
out-of-band owner-approval path — the cockpit decide handler (after device auth)
or an owner-run CLI calls
`action_executors.apply_owner_approved(action_type, params, owner_phrase=…)`,
which requires the exact phrase before dispatching. The model never reaches them
(they are not tools). The one remaining hookup is the cockpit decide → dispatch
call, intentionally left in the cockpit lane.

## Not yet (follow-ups)

- Cockpit decide → `apply_owner_approved(...)` hookup (one call; lives in the
  cockpit approval handler).
- Live deploy via the Deployments API (today `vercel_deploy` proposes a Deploy Hook).
- Cockpit preview-URL chips surfaced after a PR job.
