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

The actual change is applied **out-of-band** via the cockpit owner-approval
path, which is outside the model's control. Env-var **values** and deploy-hook
URLs are never echoed back in a tool response; tokens are scrubbed from any
error text.

## Not yet (follow-ups)

- Out-of-band execution of an approved write (set_env / deploy / cancel) via the
  cockpit owner-approval path.
- Live deploy via the Deployments API (today `vercel_deploy` proposes a Deploy Hook).
- Cockpit preview-URL chips surfaced after a PR job.
