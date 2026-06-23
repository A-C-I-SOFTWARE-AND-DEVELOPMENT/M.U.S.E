---
title: "MCP catalog & bulk install"
description: "Browse the curated MCP catalog, install one server or all of them, and share credentials across muse and Claude Code."
---

# MCP catalog & bulk install

The **MCP catalog** is a curated set of MCP servers that ship with muse as
ready-to-install manifests under `optional-mcps/`. Instead of hand-writing an
`mcp_servers` block in `~/.hermes/config.yaml`, you pick an entry and muse
writes the config for you — transport, auth, and a safe default tool selection.

> Manifests **never contain secrets.** Each one references credentials by
> environment-variable name (`${VAR}`); the value lives only in
> `~/.hermes/.env`. Presence in `optional-mcps/` = the entry was reviewed and
> merged via PR.

## Commands

| Command | What it does |
|---|---|
| `hermes mcp catalog` | List every catalog entry plus your configured servers + status |
| `hermes mcp install <name>` | Install one entry (prompts for creds, probes tools) |
| `hermes mcp install --all` | Register **every** entry non-interactively (no prompts) |
| `hermes mcp picker` | Interactive selector: install / enable / disable / configure |

### Install one server

```bash
hermes mcp install supabase
```

Prompts for the access token, writes the `mcp_servers.supabase` block, then lets
you pick which of the server's tools to enable.

### Install everything at once

```bash
hermes mcp install --all
```

Registers every catalog entry without prompting. Each server lands in one of
four buckets:

- **Installed** — needs no credentials (or you already set them) → enabled.
- **Needs credentials** — an API-key server whose key isn't in `~/.hermes/.env`
  yet → written but **disabled** (so it doesn't spam connection errors). Add the
  key, then run `hermes mcp install <name>`.
- **Skipped** — needs a git/binary build step. Re-run with `--with-bootstrap`,
  or install it individually.
- **Failed** — something went wrong (shown with the reason); the rest still
  install.

Flags:

- `--enable` — enable API-key servers even before their keys are set.
- `--with-bootstrap` — also clone + build git-installed servers (needs the
  relevant toolchain, e.g. Go).

Start a new muse session afterward to load the newly-enabled tools.

## What ships in the catalog

**Local stdio servers** (`npx` / `uvx` / `pipx` — no clone):
`filesystem`, `git`, `fetch`, `time`, `gcloud`, `gcs`, `firebase`,
`chrome-devtools`, `dart` (Dart & Flutter), `google-analytics`, `supabase`,
`slack`, `notion-local`.

**Hosted remote servers** (HTTP — OAuth or header auth):
`linear`, `notion`, `sentry`, `github`, `figma`, `vercel`, `context7`, `exa`,
`maps-code-assist`, `microsoft-learn`, `cloudflare-docs`.

**Build-from-source servers** (`--with-bootstrap`, needs a toolchain):
`mcp-toolbox-databases` (BigQuery/Cloud SQL/AlloyDB/Spanner/Firestore),
`gke`, `genmedia` (Imagen/Veo), plus `n8n`.

## Credentials

All credentials live in `~/.hermes/.env` (see `.env.example` for the full list
of keys and where to get them). Remote OAuth servers (`notion`, `sentry`,
`github`, `figma`, `vercel`, `linear`) need **no** key — they acquire tokens
through a browser flow on first connect.

## Also available in Claude Code (`.mcp.json`)

The repo ships a project-scoped `.mcp.json` at its root mirroring the same
servers, so Claude Code loads them when you work in this repo. Because
`.mcp.json` is committed to version control, every credential is a `${VAR:-}`
placeholder — there are **no secrets** in the file.

> Claude Code expands `${VAR}` from **its own** process environment, not from
> `~/.hermes/.env`. Export the same keys (or `source ~/.hermes/.env`) before
> launching Claude Code so both surfaces share one credential store.

## Servers that aren't in the catalog

Some MCP servers you may see inside Claude Code (Base44, Era, Gamma, Indeed,
ICD-10, PubMed, Canva, ZipRecruiter, …) are **account-managed connectors** —
there is no local command or public URL to launch them, so they cannot be
packaged as catalog manifests or `.mcp.json` entries. Use them through Claude
Code's connector settings instead.

## Adding a catalog entry

Open a PR adding `optional-mcps/<name>/manifest.yaml` (`manifest_version: 1`).
Model it on an existing entry — `optional-mcps/linear/manifest.yaml` (hosted
OAuth) or `optional-mcps/n8n/manifest.yaml` (stdio + git bootstrap + API key).
See the [MCP config reference](../reference/mcp-config-reference.md) for the
field-by-field schema.
