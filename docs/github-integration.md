# GitHub integration for muse

muse can talk to GitHub two ways:

1. **Native plugin** — `github_assistant`, ships in this repo at
   [`plugins/github_assistant/`](../plugins/github_assistant/). Eight
   first-class muse tools, three explicit safety gates, talks straight
   to the GitHub REST API.
2. **MCP server** — point muse at the official
   `@modelcontextprotocol/server-github` via `~/.hermes/config.yaml`.
   Anthropic-maintained, large surface, no plugin code in this repo.

Both can be enabled at the same time and they don't collide: the MCP
tools are prefixed with the server name (`github.*`) and the native
plugin's tools are unprefixed (`github_audit_repo`, etc.). Pick one or
mix them depending on which actions you want exposed.

| Concern | Native plugin | MCP server |
|---|---|---|
| Lives in this repo | ✓ | ✗ (external Node package) |
| Number of actions | 8 (curated) | ~30 (everything `server-github` exposes) |
| Allowlist per repo | ✓ | ✗ (no first-class gate) |
| Block writes by config flag | ✓ | ✗ |
| Token redaction in errors | ✓ (sanitize_error in `client.py`) | partial (mcp_tool.py redacts at boundary) |
| Custom payload slimming | ✓ | ✗ (raw payloads) |
| Dependency footprint | `requests` (already a core dep) | needs `npx` + `mcp` Python package |

Production tip: most operators want **native plugin for writes** (small
attack surface, explicit gates) and **MCP for broad read access** if
they need actions the native plugin doesn't cover yet.

---

## Creating a GitHub token

You want a **fine-grained personal access token**, not a classic one.

1. Visit <https://github.com/settings/personal-access-tokens/new>.
2. **Resource owner**: your user or your org.
3. **Expiration**: 90 days is a reasonable default. Re-issue from this
   same flow when it expires.
4. **Repository access**: pick *Only select repositories* and choose
   the exact repos you want muse to touch. Never grant *All
   repositories* unless you're auditing your full personal account from
   one muse session and you know what you're doing.
5. **Repository permissions** — set only what you need:

   | Permission | Read | Write | Used by |
   |---|---|---|---|
   | Metadata | required | — | every tool |
   | Contents | required | — | `github_get_repo_file` |
   | Issues | required | optional | `github_list_issues`, `github_create_issue`, `github_comment_on_issue_or_pr` |
   | Pull requests | required | optional | `github_list_pull_requests`, `github_get_pull_request`, `github_comment_on_issue_or_pr` |

   Leave everything else *No access*. The principle here is the same
   as for muse' `enterprise.secrets` ACL: the token should only be
   able to do what the agent might legitimately do on your behalf.

6. **Account permissions**: leave at defaults (no access). muse
   doesn't need them.
7. Generate, copy the `github_pat_*` value once, and put it in your
   muse env (next section).

---

## Storing the token

Put the token in `~/.hermes/.env` (gitignored, never committed):

```bash
# ~/.hermes/.env
GITHUB_PERSONAL_ACCESS_TOKEN=github_pat_11ABCDEF...
```

muse loads `.env` before any tool call. Don't paste the token into
`config.yaml` — that file is meant for repo-shareable settings.

The token is read by the plugin's HTTP client at request time and is
never persisted, returned to the model, or written to the audit log.
If you check `~/.hermes/logs/agent.log` after a session you should
not see the token anywhere; the redactor + the plugin's own
sanitizer cover this in depth.

---

## Enabling the native plugin

Add a top-level `github:` block to `~/.hermes/config.yaml`:

```yaml
github:
  enabled: true                  # master switch (default: false)
  allow_writes: false            # blocks create_issue + comment_on_* (default: false)
  allowed_repositories:          # empty = no allowlist; non-empty = deny by default
    - "echerd27-design/hermes-agent"
```

Restart muse (or `/reload` if your CLI supports it). `muse tools
list github` should show all eight `github_*` tools.

Verify a read-only call:

```
>>> github_audit_repo(owner="echerd27-design", name="hermes-agent")
{"success": true, "repo": {...}}
```

Verify writes are gated:

```
>>> github_create_issue(owner="echerd27-design", name="hermes-agent",
                        title="test", body="…")
{"success": false, "error": "writes_disabled", "message": "..."}
```

Flip `allow_writes: true` only when you actively want the agent to be
able to open issues / leave comments on your behalf. That single flag
is the difference between "muse can read GitHub" and "muse can
mutate GitHub" — keep it deliberately tight.

---

## Enabling the MCP server (separate from the native plugin)

Add an `mcp_servers.github` entry to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      # ${VAR} interpolation pulls from your shell env / ~/.hermes/.env
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_PERSONAL_ACCESS_TOKEN}"
    timeout: 60
    connect_timeout: 30
```

The `${GITHUB_PERSONAL_ACCESS_TOKEN}` syntax is expanded by muse' own
config loader (`hermes_cli.config._expand_env_vars`); the literal
string never reaches disk. If the env var isn't set when muse
starts, the interpolation is left as-is and the MCP server will fail
to authenticate — which is the right failure mode (loud, at startup,
not silent at first call).

The MCP server appears under its own `github` toolset prefix:

```
github.list_repositories
github.get_file_contents
…
```

There is no overlap with the native plugin's bare tool names
(`github_audit_repo`, etc.) so both can be enabled simultaneously.

---

## Safe defaults summary

| Setting | Default | What flips it on |
|---|---|---|
| native plugin loaded | yes | bundled — always discovered |
| native plugin tools visible | **no** | `github.enabled: true` + token present |
| writes allowed | **no** | `github.enabled: true` AND `github.allow_writes: true` |
| repo allowlist | **off** | non-empty `github.allowed_repositories` |
| MCP server registered | **no** | adding `mcp_servers.github` block |

If you do nothing, muse does not have GitHub access. If you set the
token only, muse still does not have GitHub access (the master
switch is off). The two-step opt-in is intentional.

---

## Troubleshooting

**`{"success": false, "error": "no_token", ...}`**
The token isn't reaching the plugin. Check `~/.hermes/.env` exists,
has `GITHUB_PERSONAL_ACCESS_TOKEN=...` (no quotes), and that you
restarted muse after editing it.

**`{"success": false, "error": "plugin_disabled", ...}`**
`github.enabled` is not `true`. Set it explicitly — defaulting to
`false` is intentional.

**`{"success": false, "error": "repo_not_allowed", ...}`**
The repo isn't on `github.allowed_repositories`. Either add it or
clear the list to disable the allowlist.

**`{"success": false, "error": "writes_disabled", ...}`**
You called a write tool with `github.allow_writes: false`. Flip it
to `true` if you want this behaviour — don't try to work around it.

**Token leaked into a log file**
File a security report. The plugin's `client.sanitize_error` plus the
global `agent.redact.RedactingFormatter` are both supposed to prevent
this. If you can reproduce it, paste the redacted snippet (you can
verify locally with `grep ghp_ ~/.hermes/logs/`) and we'll harden the
defence.
