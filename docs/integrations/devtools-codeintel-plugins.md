# Developer + code-intelligence plugins (devtools, codeintel)

Two native muse plugins that give the agent developer-reference lookups and
code-review intelligence over free public APIs. They follow the same pattern as
the [public-API plugins](public-apis-plugins.md) and reuse the shared,
host-pinned, redacting HTTP helper at
[`tools/http_client.py`](../../tools/http_client.py) (which this lane extends
with a `post_json` method for the POST-based query APIs).

## What's added

| Plugin | Tools | Source | Key |
|---|---|---|---|
| `devtools` | `pypi_package`, `npm_package`, `crates_package`, `stackoverflow_search` | PyPI · npm · crates.io · Stack Exchange | **No** |
| `codeintel` | `dependency_audit` | [OSV.dev](https://osv.dev) | **No** |
| `codeintel` | `dependency_info` | [deps.dev](https://deps.dev) | **No** |
| `codeintel` | `run_code` | [Piston](https://github.com/engineer-man/piston) sandbox | **No** (double-gated) |

`dependency_audit` queries OSV.dev for known vulnerabilities affecting a
`package@version` (empty result = no known vulns). `dependency_info` returns
licenses / versions / advisory keys from deps.dev. Both are read-only.

## Enable

Standalone plugins are opt-in. In `~/.hermes/config.yaml`:

```yaml
devtools:
  enabled: true
codeintel:
  enabled: true
  # run_code stays OFF until you explicitly allow third-party code execution:
  allow_code_execution: false
```

Then `muse plugins enable devtools codeintel` (or `/reload-skills` in a
session). No API keys are required for any tool in this lane.

## `run_code` — read this before enabling

`run_code` executes a snippet in the **public Piston sandbox at emkc.org** and
returns stdout/stderr/exit code. It is **double-gated**: its `check_fn` keeps it
hidden from the model unless BOTH `codeintel.enabled` and
`codeintel.allow_code_execution` are `true`. Because the supplied code is sent
to a third-party sandbox:

- **Never pass secrets or proprietary code** to `run_code`.
- Input is capped (50 000 chars) to bound egress.
- There is **no local execution** — muse never runs the code itself.

Leave `allow_code_execution: false` (the default) and the tool simply never
appears.

## What the live calls do

- `pypi_package` → `pypi.org/pypi/{name}/json`; `npm_package` →
  `registry.npmjs.org/{name}`; `crates_package` → `crates.io/api/v1/crates/{name}`.
- `stackoverflow_search` → `api.stackexchange.com/2.3/search/advanced`
  (keyless tier is rate-limited; the response includes `quota_remaining`).
- `dependency_audit` → **POST** `api.osv.dev/v1/query`.
- `dependency_info` → `api.deps.dev/v3/systems/{system}/packages/...`.
- `run_code` → **POST** `emkc.org/api/v2/piston/execute`.

All are best-effort public services; on timeout/error the tools return a
structured `{"success": false, "error": ...}` envelope rather than raising, so a
flaky upstream never breaks the turn loop. Hosts are pinned (the allowlist is
re-checked on every redirect hop) and error messages are secret-redacted.
