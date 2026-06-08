# GitHub, Supabase, and Vercel integrations guide

This page is the plain-English guide to wiring M.U.S.E. to the three
integrations most teams reach for first: **GitHub** (for code, PRs,
issues), **Supabase** (for database, auth, storage), and **Vercel**
(for deploys and runtime logs).

Each is configured independently. You can use one, two, or all
three. The orchestration shape — decompose, dispatch, validate,
publish — is the same for every integration; only the publishing
verbs change.

---

## How integrations plug in

M.U.S.E. has two integration shapes:

1. **Native plugins** under `plugins/`. The canonical example is
   `github_assistant` — a first-party plugin written in Python that
   exposes typed tools (`github_create_pull_request`,
   `github_search_code`, etc.). Tokens live in `~/.hermes/.env`;
   the agent never sees them.
2. **MCP servers** the gateway forwards tool calls to. Used for
   Supabase and Vercel by default — both publish official MCP
   servers, and M.U.S.E. can connect to any MCP server you list under
   `mcp_servers` in `~/.hermes/config.yaml`.

Either way, the agent calls tools, the plugin / MCP server calls the
API, and HIGH-risk mutations go through the policy gate before they
execute.

---

## GitHub setup

The canonical reference is
[`../github-integration.md`](../github-integration.md). The
shortest path:

### 1. Make a fine-grained PAT

GitHub → **Settings → Developer settings → Personal access tokens →
Fine-grained tokens → Generate new token**.

- **Repository access:** select only the repos you want M.U.S.E. to
  touch.
- **Permissions:**
  - *Contents:* Read (Read & Write if you want PRs).
  - *Pull requests:* Read & Write.
  - *Issues:* Read & Write.
  - *Metadata:* Read (auto).
  - Leave everything else off.

Copy the token (`github_pat_...` or `ghp_...`).

### 2. Add it to M.U.S.E.

```bash
echo "GITHUB_PERSONAL_ACCESS_TOKEN=ghp_..." >> ~/.hermes/.env
chmod 600 ~/.hermes/.env
```

### 3. Enable the plugin

```bash
muse plugin enable github_assistant
muse config set github.enabled true
muse config set github.allow_writes true
muse config set github.allowed_repositories "echerd27-design/hermes-agent,owner2/repo2"
```

`allowed_repositories` is a defense-in-depth list. Even if a worker
asks to write to `someone-else/repo`, the plugin refuses unless that
repo is in the list. The token's GitHub-side scope is the first
fence; this list is the second.

### 4. Confirm

```bash
muse config get github.enabled         # true
muse config get github.allow_writes    # true
muse config get github.allowed_repositories
```

Then in `muse`:

```
/github status
```

You should see your username + the writable-repo list.

### 5. Smoke test

```bash
bash scripts/hermes-orchestrate.sh \
  "Open a draft issue on echerd27-design/hermes-agent titled 'M.U.S.E. integration smoke test' with body 'ignore me'." \
  --deliver gateway
```

You'll get a HIGH-risk approval request. Approve. The issue opens.
Close it manually after — that's the test.

### GitHub MCP server as an alternative

If you'd rather use the GitHub MCP server (more verbs, slower
auth), wire it up under `mcp_servers:` in `~/.hermes/config.yaml`.
The trade-offs are in
[`../github-integration.md`](../github-integration.md). For most
users the native `github_assistant` plugin is the right default.

---

## Supabase setup

Supabase ships an official MCP server you point M.U.S.E. at.

### 1. Get a Supabase access token

Supabase Studio → **Account → Access Tokens → Generate new
token**. Scope it to the projects you want M.U.S.E. to manage.

### 2. Add the token

```bash
echo "SUPABASE_ACCESS_TOKEN=sbp_..." >> ~/.hermes/.env
```

### 3. Wire up the MCP server

In `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  supabase:
    command: npx
    args:
      - -y
      - "@supabase/mcp-server-supabase@latest"
      - --access-token
      - ${SUPABASE_ACCESS_TOKEN}
    enabled: true
    # Restrict to specific projects / orgs as defense-in-depth:
    allowed_projects:
      - hermes-prod
      - hermes-staging
```

### 4. Confirm

```bash
muse mcp status
```

You should see `supabase: connected` and a count of tools the
server exposed (typically ~30: list_projects, execute_sql,
apply_migration, get_logs, etc.).

In an interactive session:

```
/supabase list_projects
```

…lists the projects your token can reach.

### 5. Policy for Supabase

The policy gate classifies Supabase tool calls:

- `list_*`, `get_*`, `search_*` → LOW (auto-approve).
- `execute_sql` with read-only SELECT → LOW.
- `execute_sql` with mutation, `apply_migration`,
  `deploy_edge_function`, `create_branch` → HIGH (always escalate).
- `delete_*`, `reset_branch`, `pause_project` → HIGH and additionally
  refused outright unless `supabase.allow_destructive: true` is set.

You can tighten further with explicit allowlists in
`~/.hermes/config.yaml`:

```yaml
supabase:
  allow_destructive: false      # default
  allow_writes_in_projects:
    - hermes-staging            # mutations allowed only here
```

### 6. Smoke test

```bash
bash scripts/hermes-orchestrate.sh \
  "Tell me how many rows are in the users table of the hermes-staging Supabase project."
```

Read-only, runs without approval.

---

## Vercel setup

Vercel publishes an MCP server too. Same shape.

### 1. Get a Vercel token

Vercel dashboard → **Settings → Tokens → Create**. Scope to the
team / project you want M.U.S.E. to manage.

### 2. Add the token

```bash
echo "VERCEL_TOKEN=..." >> ~/.hermes/.env
```

### 3. Wire up the MCP server

```yaml
mcp_servers:
  vercel:
    command: npx
    args:
      - -y
      - "@vercel/mcp-adapter@latest"
    env:
      VERCEL_TOKEN: ${VERCEL_TOKEN}
    enabled: true
    allowed_projects:
      - hermes-web
      - hermes-marketing
```

### 4. Confirm

```bash
muse mcp status
```

`vercel: connected` and the tool list (list_projects,
list_deployments, get_deployment_build_logs, get_runtime_logs,
deploy_to_vercel, etc.).

```
/vercel list_projects
```

### 5. Policy for Vercel

- `list_*`, `get_*`, `search_*` → LOW.
- `get_deployment_build_logs`, `get_runtime_logs` → LOW.
- `deploy_to_vercel` → HIGH (always escalate).
- `web_fetch_vercel_url` against a preview → MEDIUM.
- Anything that affects production environment variables → HIGH and
  refused unless `vercel.allow_production_env_writes: true`.

### 6. Smoke test

```bash
bash scripts/hermes-orchestrate.sh \
  "Show me the build logs for the most recent deployment of the hermes-web project."
```

Read-only, runs without approval. The orchestrator pulls the latest
deployment ID, fetches logs, summarizes.

---

## How the three integrations work together

A typical end-to-end *"ship this feature"* job uses all three:

```
T1 (researcher)    — read the spec from a Notion doc / GitHub issue.
T2 (engineer)      — write the code change.
T3 (engineer)      — supabase apply_migration in hermes-staging.   [HIGH]
T4 (reviewer)      — diff sanity-check.
T5 (engineer)      — github_create_pull_request (draft).            [HIGH]
T6 (engineer)      — vercel deploy_to_vercel (preview, --target=preview). [HIGH]
T7 (reviewer)      — fetch the preview URL, smoke-test, report.
```

T3, T5, T6 each escalate; you approve each one separately or use a
`--deliver pr,supabase,vercel` configuration that defers them all
until you've reviewed the diff.

The orchestrator skill knows the typical shape and proposes it. You
adjust before approving.

---

## Quick start, all three

```bash
# Tokens
echo "GITHUB_PERSONAL_ACCESS_TOKEN=ghp_..." >> ~/.hermes/.env
echo "SUPABASE_ACCESS_TOKEN=sbp_..."        >> ~/.hermes/.env
echo "VERCEL_TOKEN=..."                     >> ~/.hermes/.env
chmod 600 ~/.hermes/.env

# Plugins / MCP
muse plugin enable github_assistant
muse config set github.enabled true
muse config set github.allow_writes true
muse config set github.allowed_repositories "owner/repo"

# Edit ~/.hermes/config.yaml to add the supabase + vercel mcp_servers blocks above.

# Confirm
muse config get github.allowed_repositories
muse mcp status

# Smoke test
bash scripts/hermes-orchestrate.sh \
  "List my GitHub repos, my Supabase projects, and my Vercel projects."
```

You should get three short lists back, with no approvals (all
read-only).

---

## How secrets are protected across the three

Same model as everywhere in M.U.S.E.:

- Tokens live in `~/.hermes/.env` (`chmod 600`).
- Plugins / MCP servers read them at startup; the agent itself never
  receives them.
- The ledger redacts credential-pattern values before writing.
- HIGH-risk mutations always escalate to a human surface.
- `allowed_repositories` / `allowed_projects` lists provide a second
  fence so a confused agent can't write to the wrong place even with
  a valid token.

The full security model is
[security/private-local-security-guide.md](../security/private-local-security-guide.md).

---

## Prompt examples

| You say | What runs |
|---------|-----------|
| *"Open a draft PR titled `chore(deps): bump axios` against `owner/repo`."* | github_assistant phase, HIGH-risk → approval. |
| *"Show me the last 24h of runtime logs for my `web` Vercel project."* | Vercel MCP, LOW. |
| *"Run `SELECT count(*) FROM users` against my staging Supabase project."* | Supabase `execute_sql` (read-only), LOW. |
| *"Migrate this schema on staging, smoke-test the API, then open a draft PR with the migration."* | Multi-phase: Supabase HIGH, then Vercel preview HIGH, then GitHub HIGH. Three separate approvals. |
| *"What changed in production between the last two Vercel deploys?"* | Vercel + GitHub combined, all read-only. |
| *"Add a new edge function `webhook-receiver` to my Supabase project."* | Supabase `deploy_edge_function`, HIGH-risk → approval. |
| *"Which of my open PRs have failing CI?"* | github_assistant search, LOW. |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `github: not configured` | Plugin not enabled or token missing | `muse plugin enable github_assistant`; check `~/.hermes/.env`. |
| `github: write blocked: repo not in allowed_repositories` | Second-fence list doesn't cover the target | Add the repo to `github.allowed_repositories`; `/reload-skills`. |
| `mcp: supabase failed to start` | `npx` not on PATH, or token invalid | `which npx`; rotate the Supabase token; restart M.U.S.E.. |
| `supabase: allow_destructive=false` refuses delete | Defense-in-depth refusal | Set `supabase.allow_destructive: true` *only if you mean it*. |
| `vercel: production env write refused` | Same as above for Vercel | Set `vercel.allow_production_env_writes: true` if you mean it. |
| Approval notification not arriving | Gateway down or device unsubscribed | See [mobile/mobile-app-guide.md §disconnect-recovery](../mobile/mobile-app-guide.md#disconnect-recovery). |
| MCP server connects but no tools appear | Server started but the `tools/list` call failed; check `~/.hermes/logs/agent.log` | Update the MCP server package; restart M.U.S.E.. |
| Tools available but every call fails 401 | Token expired or scoped wrong | Rotate at the provider, update `~/.hermes/.env`, restart. |

Anything else: see
[../troubleshooting/hermes-orchestration-troubleshooting.md](../troubleshooting/hermes-orchestration-troubleshooting.md).

---

## See also

- [`../github-integration.md`](../github-integration.md) — the
  native `github_assistant` plugin in depth.
- [security/private-local-security-guide.md](../security/private-local-security-guide.md)
  — secrets and the approval model.
- [profile/github-history-profile-guide.md](../profile/github-history-profile-guide.md)
  — what M.U.S.E. learns from your GitHub history.
- [orchestration/prompt-to-pr-demo.md](../orchestration/prompt-to-pr-demo.md)
  — the canonical multi-phase GitHub example.
- [orchestration/worker-adapters.md](../orchestration/worker-adapters.md)
  — adding more worker environments around these integrations.
