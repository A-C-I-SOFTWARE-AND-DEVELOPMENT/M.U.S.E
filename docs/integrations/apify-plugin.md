# Apify plugin — web scraping & automation for M.U.S.E.

The `apify` plugin wires [Apify](https://apify.com) into M.U.S.E. so the
agent can discover, run, and read the output of **Actors** — Apify's
reusable cloud scrapers and automations (e.g. *website-content-crawler*,
*google-maps-scraper*, *instagram-scraper*). It follows the same native
plugin shape as [`github_assistant`](github.md): a folder under `plugins/`,
an `enabled` switch in `~/.hermes/config.yaml`, a Bearer token in
`~/.hermes/.env`, and a thin REST client that never leaks the token.

Unlike the [free public-API plugins](public-apis-plugins.md), Apify needs a
key **and** running an Actor consumes paid compute units — so the run tool
sits behind a second, separate gate.

## Tools

| Tool | Action | Read/run |
|---|---|---|
| `apify_list_actors` | list your Actors, or search the public Apify Store (`search`) | read |
| `apify_get_dataset_items` | fetch items from a dataset id (e.g. a run's `defaultDatasetId`) | read |
| `apify_get_run` | a run's status/metadata (status, timestamps, dataset id, stats) | read |
| `apify_run_actor` | run an Actor, wait for it, and return its dataset items | **run** (billable) |

All four return the uniform `{"success": bool, ...}` envelope, so a flaky
upstream or an HTTP error never breaks the agent's turn loop.

## Two-step opt-in (read) + a third gate (run)

This mirrors `github_assistant`'s `enabled` / `allow_writes` split:

1. **Set the token** in `~/.hermes/.env`:

   ```bash
   # ~/.hermes/.env
   APIFY_TOKEN=apify_api_yourTokenHere   # placeholder; get yours at https://console.apify.com/account/integrations  pragma: allowlist secret
   ```

2. **Enable the plugin** in `~/.hermes/config.yaml`:

   ```yaml
   apify:
     enabled: true
   ```

   Until both are true, every Apify tool is hidden from the model.

3. **Allow runs** — `apify_run_actor` stays hidden *and* refuses to execute
   until you explicitly flip `allow_runs`, because a run spends money:

   ```yaml
   apify:
     enabled: true
     allow_runs: true
     allowed_actors:                       # optional: deny-by-default for runs
       - "apify/website-content-crawler"
   ```

   `allowed_actors` accepts either `username/name` or `username~name` form
   (Apify's REST path uses the tilde; the plugin normalises both). Leave it
   empty to trust the token's own scope; populate it to harden which Actors
   the agent may run.

Then load the plugin like any bundled standalone plugin:

```bash
muse plugins enable apify
# or, inside an interactive session after editing config:
/reload-skills
```

## What the live calls actually do

Honest description of network behaviour, all against `api.apify.com`:

- **apify_list_actors** — `GET /v2/acts` (your Actors) or, with `search`,
  `GET /v2/store` (public Store search). No writes.
- **apify_get_dataset_items** — `GET /v2/datasets/{id}/items?clean=true`.
- **apify_get_run** — `GET /v2/actor-runs/{id}`.
- **apify_run_actor** — `POST /v2/acts/{id}/run-sync-get-dataset-items`
  with your `input` object as the body. This **starts a billable run** and
  blocks until it finishes (run timeout default 60s, max 300s — Apify's
  run-sync ceiling). The Actor's `input` schema is per-Actor; see that
  Actor's README/Input page.

The token is sent as an `Authorization: Bearer …` header (never in a URL or
query string), added to the client's redaction set, and stripped from any
error before it reaches the model or the logs. Result lists are capped
(default 25 items, hard cap 100) and the serialized item payload is trimmed
to a ~200 KB budget so a huge dataset can't blow up the model context.

## Alternative: the Apify MCP server

If you'd rather use Apify's official MCP server, wire it under
`mcp_servers.apify` in `~/.hermes/config.yaml` — the native plugin and the
MCP server coexist cleanly (native tools use bare names like
`apify_run_actor`; MCP tools use dotted names). The native plugin keeps the
token entirely inside the Hermes process and gives you the `allow_runs` /
`allowed_actors` spend gates; pick whichever trust model you prefer.

## Typical flow

1. `apify_list_actors` with `search: "website content"` → find a slug.
2. `apify_run_actor` with `actor_id: "apify/website-content-crawler"` and an
   `input` like `{"startUrls": [{"url": "https://example.com"}]}` → items.
3. For long jobs, instead read results later with `apify_get_run` (to get
   `default_dataset_id`) then `apify_get_dataset_items`.
