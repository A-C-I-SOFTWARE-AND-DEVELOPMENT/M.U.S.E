# G1 — Hard-rename the `hermes` command to `muse`

**Grain:** G1 (Swarm Grainler Parallel, MUSE app)
**Branch:** `claude/muse-command-rename`
**Base commit:** `9fa25b19e22d3f4c2d55aefb5773ab079424626b` (`git rev-parse origin/main`)
**Owner decision:** Hard rename, **no `hermes` alias**.

## Intent

Rename the user-facing CLI **command** from `hermes` to `muse` across the
console-script entry points and every installer / user-facing doc that tells the
user what to type. This renames the **command only** — the data directory
(`~/.hermes`, `$HERMES_HOME`, `%LOCALAPPDATA%\hermes`), the repo/install dir
(`hermes-agent`, `/usr/local/lib/hermes-agent`), the Python package
(`hermes_cli`, `hermes-agent` on PyPI), env vars (`HERMES_HOME`,
`HERMES_GIT_BASH_PATH`), and internal helper-script filenames
(`scripts/hermes-*.sh`) are intentionally **left as-is**.

## Files changed (all within owned paths)

| File | What changed |
|---|---|
| `pyproject.toml` | `[project.scripts]`: `hermes`/`hermes-agent`/`hermes-acp` → `muse`/`muse-agent`/`muse-acp` (same targets). Also 3 code comments referencing `hermes tools`/`hermes dashboard` → `muse …`. |
| `scripts/install.sh` | Shim creation now writes `$command_link_dir/muse` (Termux `$PREFIX/bin/muse`, Linux `~/.local/bin/muse`, root FHS `/usr/local/bin/muse`). `HERMES_BIN`/`which`/`command -v`/`venv/bin/…` lookups point at `muse` (pip now generates `muse`). All user-facing log messages + `--help` text + completion banner + JARVIS-launch hints say `muse`. Internal var names (`HERMES_BIN`, `HERMES_CMD`, `resolve_hermes_cmd`) kept. `$HERMES_HOME`/`~/.hermes`/`hermes-agent` dirs kept. |
| `scripts/install.ps1` | pip auto-generates `muse.exe` (entry handled by pyproject). `Resolve-HermesCmd`, gateway autostart, JARVIS-launch use `muse.exe` / `Get-Command muse`. Every user-facing string + completion command list + comments referencing the command say `muse`. `$HermesHome`/`HERMES_HOME`/`%LOCALAPPDATA%\hermes`/`hermes-agent` kept. |
| `website/docs/getting-started/installation.md` | Install one-liner unchanged (URL). All `hermes <subcommand>` usage examples → `muse`; install-layout table `hermes` binary column + `/usr/local/bin/hermes` + `~/.local/bin/hermes` symlink → `muse`; troubleshooting rows; Windows feature-parity list; auto-detection paragraph. Repo source bootstrap file `~/.hermes/hermes-agent/hermes` kept (see residual risks). |
| `website/docs/getting-started/termux.md` | `ln -sf "$PWD/venv/bin/muse" "$PREFIX/bin/muse"`; all usage examples (`muse version`, `muse doctor`, `muse model`, `muse setup`, `muse`); installer-summary bullet; troubleshooting headings. Clone dir / `~/.hermes` / `.[termux]` kept. |
| `docs/remote/windows-claude-code-bridge-guide.md` | All `hermes <subcommand>` invocations in code blocks + the troubleshooting table → `muse`. Install URL, `~/.hermes`, and `scripts/hermes-orchestrate.sh` helper filename kept. |
| `README.md` | All `hermes <subcommand>` examples → `muse` (quickstart, getting-started block, JARVIS launch, CLI-vs-messaging table, OpenClaw migration, Termux gateway, `model` switch line, "interactive `muse` CLI" prose). `setup-hermes.sh` line: `~/.local/bin/hermes` symlink → `~/.local/bin/muse`. Repo source `./hermes` bootstrap file kept. Doc URLs / repo-dir / `agents/hermes/` / `/hermes-orchestration-pipeline` slash command kept. |
| `docs/launch/muse-app/g1-command-rename.md` | This snapshot. |

## Out-of-owned-path references to `hermes-agent` / `hermes-acp` BY NAME (for the orchestrator)

These invoke the renamed console scripts (`hermes-agent`, `hermes-acp`) or the
`hermes` command by name and live **outside** G1's owned paths. They were **not**
touched by G1 and need a follow-up grain (or owner decision) to stay consistent
with the hard rename:

- **`packaging/homebrew/hermes-agent.rb` L29** — `%w[hermes hermes-agent hermes-acp].each do |exe|` (Homebrew formula asserts all three console scripts exist). NOTE: `docs/launch/followups/g-rename-prep.md` already anticipates a renamed `packaging/homebrew/muse.rb`.
- **`nix/hermes-agent.nix` L165** — lists `"hermes-acp"` (Nix package wrapper).
- **`nix/checks.nix` L83** — `for bin in hermes hermes-agent hermes-acp; do` (Nix smoke test asserts the three binaries are on PATH).
- **`acp_registry/agent.json` L13** — `"args": ["hermes-acp"]` (Zed ACP registry launcher; also `website/docs/.../acp.md` + `developer-guide/acp-internals.md` reference `uvx --from 'hermes-agent[acp]==<version>' hermes-acp`).
- **`acp_adapter/entry.py` L13, L113** — docstring + `argparse` `prog="hermes-acp"` (the ACP CLI's own self-reported program name).
- **`hermes_bootstrap.py` L17** — docstring listing entry points (`hermes`, `hermes-agent`, `hermes-acp`).
- **Tests** that assert the console-script set / `prog` name will fail against the renamed scripts, e.g. `tests/test_hermes_bootstrap.py`, `tests/acp/test_entry.py`, `tests/acp/test_registry_manifest.py`, `tests/scripts/test_release_acp_registry.py`. These are out of G1 scope but **will break CI** once the rename lands — sequence a test-update grain.
- Website docs under `website/docs/**` (not in G1's owned set) contain many `hermes <subcommand>` examples + `hermes-acp` references (e.g. `reference/cli-commands.md`, `user-guide/**`, `getting-started/nix-setup.md`). A broader docs grain should sweep these.

NOTE (not a rename target): `toolsets.py` defines a **toolset** literally named
`"hermes-acp"` (and `acp_adapter/*` default to it). That is a toolset
identifier, **not** the console command, and must **not** be renamed as part of
the command rename.

## Validation

- `python3 -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('pyproject OK')"` → **OK** (re-run after comment edits → still OK).
- `[project.scripts]` now = `{'muse': 'hermes_cli.main:main', 'muse-agent': 'run_agent:main', 'muse-acp': 'acp_adapter.entry:main'}`; `grep -nE '^(hermes|hermes-agent|hermes-acp)\s*=' pyproject.toml` → **none**.
- `bash -n scripts/install.sh` → **syntax OK**.
- `shellcheck` → **not installed in this environment** (could not run; `bash -n` is the available syntax gate).
- Guard grep across all 7 owned files for `hermes <subcommand>` (chat/setup/gateway/config/model/tools/doctor/update/whatsapp/claw/kanban/plugin/profile/models/version/jarvis/dashboard/--) → **No matches**.
- Guard grep for `bin/hermes` / `hermes.exe` command-binary paths → **none**.
- Remaining bare `` `hermes` `` tokens are intentional keepers: a systemd
  service-account **username** example, and the repo source **bootstrap file**
  reference (`~/.hermes/hermes-agent/hermes`).
- Diff stat: 7 files, 170 insertions / 170 deletions (in-place renames, no
  structural changes). Default runtime behavior is byte-for-byte unchanged
  except for the deliberate command-name change.

## Residual risks

1. **The console command changes for everyone.** This is a behavior change
   (the binary users invoke is now `muse`, not `hermes`). Existing installs that
   created a `hermes` shim/symlink keep the stale name until they re-run the
   installer; the installer no longer writes `hermes`. Owner accepted the hard
   rename with no alias.
2. **Cross-file consistency / CI breakage.** Homebrew, Nix, the ACP registry,
   `acp_adapter/entry.py`'s `prog`, `hermes_bootstrap.py`'s docstring, and the
   bootstrap/ACP tests still reference `hermes` / `hermes-agent` / `hermes-acp`
   and are outside G1's owned paths. Until those land, `brew test`, the Nix
   smoke check, and several pytest assertions will fail. See the out-of-path
   list above — sequence follow-up grains.
3. **Repo source bootstrap file `hermes`.** The repo ships a root-level `hermes`
   bootstrap script (and `./hermes`, `setup-hermes.sh`) used for from-source dev
   runs. G1 did **not** rename that source file (out of owned paths). Docs that
   point at it (`~/.hermes/hermes-agent/hermes`, `./hermes`) intentionally still
   say `hermes`. If the owner wants the source file renamed to `muse` too,
   that's a separate grain touching the repo root + `setup-hermes.sh`.
4. **Docs outside owned set still say `hermes`.** The four owned docs are
   consistent, but the wider `website/docs/**` tree and other `docs/**` guides
   still show `hermes <subcommand>`. A docs-wide sweep grain is needed for full
   consistency.

## Git

- `git fetch origin main` (origin/main advanced `d4c66c09 → 9fa25b19` during the run).
- Branch `claude/muse-command-rename` cut from `origin/main` (`9fa25b19`).
- Commit pushed to `origin/claude/muse-command-rename`. **No PR** (per grain contract).
