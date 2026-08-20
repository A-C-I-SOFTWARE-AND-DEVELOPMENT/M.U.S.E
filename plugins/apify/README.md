# apify

Native [Apify](https://apify.com) web-scraping & automation for Hermes
Four REST-backed tools, three independent safety gates, no token leaks.

For setup, the run-gate rationale, and the difference between this plugin
and Apify's MCP server, see
[`docs/integrations/apify-plugin.md`](../../docs/integrations/apify-plugin.md).

## At a glance

```yaml
# ~/.hermes/config.yaml
apify:
  enabled: true
  allow_runs: false                       # apify_run_actor refuses to run
  allowed_actors:
    - "apify/website-content-crawler"     # everything else is denied for runs
```

```bash
# ~/.hermes/.env
APIFY_TOKEN=apify_api_yourTokenHere   # pragma: allowlist secret
```

## Tools

| Tool | Action | Read/run |
|---|---|---|
| `apify_list_actors` | list your Actors, or search the Apify Store | read |
| `apify_get_dataset_items` | items from a dataset id | read |
| `apify_get_run` | one Actor run's status/metadata | read |
| `apify_run_actor` | run an Actor, wait, return its items | **run** (billable) |

`apify_run_actor` starts a **billable Actor run** (consumes Apify compute
units), so it stays hidden from the model and refuses to execute until
`apify.allow_runs` is `true`. An optional `allowed_actors` allowlist
restricts which Actors may be run.
