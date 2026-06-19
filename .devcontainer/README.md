# `.devcontainer/` — M.U.S.E. dev environment (Codespaces / VS Code)

One-click reproducible **development** environment for hermes-agent, on GitHub
Codespaces or any Dev Containers host. It installs the project exactly as CI
does (`uv pip install -e ".[all,dev]"`), adds Node + the GitHub CLI, and
forwards the dashboard port.

```
Code ▸ Codespaces ▸ Create codespace on <branch>
```

Then in the terminal: `muse doctor`, `uv run pytest -q`, `uv run ruff check .`.

## ⚠️ Codespaces is for development, NOT 24/7 hosting

A codespace **auto-suspends after ~30 min idle** (max idle timeout is a couple
of hours, configurable in your GitHub settings) and is billed by core-hour. The
gateway and its in-process cron scheduler — the long-horizon autonomous engine —
**stop the moment the codespace idles out**. So:

| Want | Use |
|---|---|
| Edit MUSE, run tests, open PRs | **this devcontainer / Codespaces** |
| The always-on gateway (24/7, long-horizon) | **a VPS** — [`docs/deploy/vps-deployment-guide.md`](../docs/deploy/vps-deployment-guide.md) + [`scripts/vps-harden-longhorizon.sh`](../scripts/vps-harden-longhorizon.sh) |

If you must keep a codespace running longer: raise the idle timeout in
**GitHub ▸ Settings ▸ Codespaces ▸ Default idle timeout**, keep a terminal
active, and watch your core-hour budget — it is still not a substitute for the
VPS for unattended operation.

## Dev state is isolated

`HERMES_HOME` is set to `.hermes-dev/` in the workspace, so experiments never
touch a real `~/.hermes`. Add API keys for local testing to
`.hermes-dev/.env` (git-ignored). Don't commit secrets.

## Connecting MUSE to GitHub from here

For dev, set a fine-grained PAT as `GITHUB_PERSONAL_ACCESS_TOKEN` in
`.hermes-dev/.env` and enable the `github_assistant` plugin's `github:` block in
`.hermes-dev/config.yaml`. The same wiring on a VPS is what gives you 24/7
GitHub actions — see [`docs/github-integration.md`](../docs/github-integration.md).
