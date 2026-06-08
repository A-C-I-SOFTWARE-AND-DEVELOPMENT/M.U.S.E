# G1b — Complete the `hermes` → `muse` rename cascade

**Grain:** G1b (Swarm Grainler Parallel, MUSE app)
**Branch:** `claude/muse-command-rename-cascade`
**Base commit:** `d0bc7fa38993d82b13f5804796d0a8f4c35afdd8`
(`origin/claude/muse-command-rename` — **contains G1's commit**, cut with
`git checkout -b claude/muse-command-rename-cascade origin/claude/muse-command-rename`)
**Owner decision:** Hard rename — all three console scripts are now
`muse` / `muse-agent` / `muse-acp` (done by G1 in pyproject + installers).
**No PR / no merge** (per grain contract).

## Intent

G1 renamed the console-script **entry points** (`pyproject.toml [project.scripts]`)
and the installer/owned-doc user-facing strings. This grain fixes every **other**
reference that invoked the *old binary names by name* so packaging / Nix / ACP /
tests stay consistent and CI stays green. Scope is the **command/binary name
only** — the PyPI package (`hermes-agent`), the Python package (`hermes_cli`,
module `hermes_bootstrap`), env vars (`HERMES_*`), data dir (`~/.hermes`,
`HERMES_HOME`), Nix file names + derivation `pname` (`hermes-agent`), the
`hermes-acp` **toolset** identifier, the `hermes-setup` ACP auth-method id, and
all "Hermes" / "Hermes Agent" product prose are intentionally **left as-is**.

## Files changed (13 files, +67/-67 — pure in-place renames)

| File | What changed | Kept (intentional) |
|---|---|---|
| `nix/checks.nix` | All produced/checked **binary paths** `${hermes-agent}/bin/hermes`→`/bin/muse`, `/bin/hermes-agent`→`/bin/muse-agent`; `entry-points-sync` loop `for bin in hermes hermes-agent hermes-acp`→`muse muse-agent muse-acp`; `--help` echo labels. (15 binary refs across `package-contents`, `entry-points-sync`, `cli-commands`, `bundled-skills/plugins/tui`, `hermes-node`, `managed-guard`, `extra-python-packages`.) | `${hermes-agent}` package var, `hermes-*` runCommand derivation names, `HERMES_*` env vars, `share/hermes-agent` data dir, `grep -qi "hermes"` on `muse version` output (product name "Hermes Agent" still printed). |
| `nix/hermes-agent.nix` | `makeWrapper` name list `["hermes" "hermes-agent" "hermes-acp"]`→`["muse" "muse-agent" "muse-acp"]` (drives both the `${hermesVenv}/bin/<name>` source + `$out/bin/<name>` output); `meta.mainProgram = "hermes"`→`"muse"` (so `lib.getExe` / `nix run` resolve the real binary). | `pname = "hermes-agent"`, file name, `share/hermes-agent`, `HERMES_*`, homepage URL. |
| `packaging/homebrew/hermes-agent.rb` | Installed-binary test list `%w[hermes hermes-agent hermes-acp]`→`%w[muse muse-agent muse-acp]`; `test do` invocations `#{bin}/hermes version`→`#{bin}/muse version`, `#{bin}/hermes update`→`#{bin}/muse update`. | Formula file name, class `HermesAgent`, `desc`, product assertion "Hermes Agent v#{version}", `brew upgrade hermes-agent` (formula name). |
| `acp_adapter/entry.py` | Docstring usage `hermes acp`/`hermes-acp`→`muse acp`/`muse-acp`; `argparse(prog="hermes-acp")`→`prog="muse-acp"`; setup-shim fallback argv[0] `else "hermes"`→`else "muse"` (test only checks argv[1:]). | Product log "Starting hermes-agent ACP adapter", "Hermes ACP check OK", module `hermes_bootstrap` import. |
| `acp_adapter/session.py` | Docstring WSL launch hint `` `hermes acp` ``→`` `muse acp` ``. | Toolset `["hermes-acp"]` (line 146/599 — NOT a command). |
| `acp_registry/agent.json` | Zed launcher `"args": ["hermes-acp"]`→`["muse-acp"]`. | `id="hermes-agent"`, `name="Hermes Agent"`, `package="hermes-agent[acp]==…"` (registry slug + product + PyPI package; G1 kept the PyPI name; mirrors the unchanged manifest tests). |
| `hermes_bootstrap.py` | Docstring entry-point list ` ``hermes``, ``hermes-agent``, ``hermes-acp`` `→` ``muse``, ``muse-agent``, ``muse-acp`` `. | Module name `hermes_bootstrap`, "Hermes entry point" prose, `python -m gateway.run`/`batch_runner.py`/`cron/scheduler.py` (file/module invocations). |
| `tests/test_hermes_bootstrap.py` | Module docstring command list; `ENTRY_POINTS` inline comments (`# hermes CLI`→`# muse CLI`, etc.); docstring/comment command refs ` ``hermes update`` `→` ``muse update`` `, "leaves hermes recoverable"→"muse", "hermes start"→"muse start". | Module `hermes_bootstrap` (everywhere), `ENTRY_POINTS` file **paths** (`hermes_cli/main.py` etc.), "Hermes entry point"/"hermes-agent repo root" prose. No assertions changed (they test the module name + file paths). |
| `tests/acp/test_entry.py` | Docstring `` `hermes-acp --setup-browser` ``→`` `muse-acp …` ``. | Assertions on product strings "Starting hermes-agent ACP adapter" (L34) and "Hermes ACP check OK" (L42) unchanged — they match the kept product strings in `entry.py`. |
| `tests/acp/test_registry_manifest.py` | `assert uvx["args"] == ["hermes-acp"]`→`["muse-acp"]` (mirrors `agent.json`). | `id=="hermes-agent"`, `name=="Hermes Agent"`, `package==f"hermes-agent[acp]…"` assertions unchanged (kept fields). |
| `tests/scripts/test_release_acp_registry.py` | Fixture `"args": ["hermes-acp"]`→`["muse-acp"]` (L48) and the "args stay untouched" post-bump assertion `== ["hermes-acp"]`→`== ["muse-acp"]` (L71). | Fixture `id`/`name`/`package` `hermes-agent…` (release script only bumps the version pin, not `args` — verified `scripts/release.py` has no `args` rewrite). |
| `website/docs/user-guide/features/acp.md` | Conservative ACP-doc sweep: every user-typed command `hermes acp`/`hermes-acp`/`hermes model`/`hermes doctor`/`hermes status`→`muse …`; JSON editor config `"command": "hermes"`→`"command": "muse"`; the launched console script in `uvx --from 'hermes-agent[acp]==…' hermes-acp`→`muse-acp`. | L22 **toolset** `` `hermes-acp` ``; `hermes-agent[acp]` PyPI pin + `hermes-agent` PyPI prose; `hermes-agent/` registry dir + `/path/to/hermes-agent/acp_registry`; Zed `"hermes-agent"` agent-server key (mirrors registry id); `~/.hermes/*` data dirs. |
| `website/docs/developer-guide/acp-internals.md` | Boot-flow `hermes acp / hermes-acp`→`muse acp / muse-acp`; `uvx … hermes-acp`→`muse-acp`; Related-files `hermes acp` CLI subcommand→`muse acp`, `hermes-acp` script→`muse-acp`. | L119 toolset `enabled_toolsets=["hermes-acp"]`; L182 `hermes-acp` **toolset** definition; L152 `hermes-setup` ACP **auth-method id** (code constant `TERMINAL_SETUP_AUTH_METHOD_ID` in `acp_adapter/auth.py`); `hermes-agent[acp]`/`hermes-agent` PyPI; `~/.hermes`. |

## Validation

- **Assigned pytest suite** (task spec):
  `uv run --extra dev pytest tests/test_hermes_bootstrap.py tests/acp/test_entry.py tests/acp/test_registry_manifest.py tests/scripts/test_release_acp_registry.py -q`
  → **31 passed, 5 skipped** (the 5 skips are Windows-only `hermes_bootstrap`
  tests, correctly skipped on Linux). With `acp` installed, all 10
  `tests/acp/test_entry.py` cases run and pass; `tests/acp/test_registry_manifest.py`
  (incl. `…uses_uvx_distribution…` asserting `args == ["muse-acp"]`) and the
  release-script test pass.
- **Ruff**: `uv run --extra dev ruff check acp_adapter/entry.py acp_adapter/session.py hermes_bootstrap.py tests/test_hermes_bootstrap.py tests/acp/test_entry.py tests/acp/test_registry_manifest.py tests/scripts/test_release_acp_registry.py` → **All checks passed!**
- **agent.json** parses as valid JSON; `args=['muse-acp']`, `id=hermes-agent`,
  `package=hermes-agent[acp]==0.14.1+aci.1`.
- **Nix** evals not run locally (nix unavailable; checks are Linux-CI-only).
  Edits are pure string substitutions inside existing shell-string literals —
  no brace/structure change; diff is balanced (+/- equal, in-place renames).
- **Residual hard-ref grep** (task spec):
  `grep -rnE "\b(hermes|hermes-agent|hermes-acp)\b" nix packaging acp_adapter acp_registry hermes_bootstrap.py tests | grep -v "hermes-agent.nix|hermes-agent.rb|toolset"`
  — in my **owned files**, the only remaining hits are intentional keepers:
  `nix/hermes-agent.nix` `pname = "hermes-agent"`; `tests/test_hermes_bootstrap.py`
  `"hermes_cli/main.py"` (a file path, comment now "muse CLI"). All
  binary-path / `prog=` / `args` / docstring-command refs are now `muse*`.

## Intentional keepers (NOT renamed — by design)

1. **PyPI package** `hermes-agent` / `hermes-agent[acp]` (G1 kept the PyPI name)
   — Homebrew `url`/`brew upgrade hermes-agent`, `acp_registry/agent.json`
   `package`, ACP docs `uvx --from 'hermes-agent[acp]==…'`.
2. **ACP registry identity** `id="hermes-agent"`, `name="Hermes Agent"` — package
   slug + product name; mirrors the unchanged `test_registry_manifest.py`
   assertions and the kept PyPI package.
3. **`hermes-acp` toolset** identifier (`toolsets.py`; `acp_adapter/session.py`
   L146/599, `server.py`; docs `acp.md` L22, `acp-internals.md` L119/182) — a
   tool name, not the command (per G1's explicit note).
4. **`hermes-setup`** ACP terminal-auth-method id (`acp_adapter/auth.py`
   `TERMINAL_SETUP_AUTH_METHOD_ID`; `acp-internals.md` L152) — protocol id, not
   the command.
5. **Nix package/derivation** `pname = "hermes-agent"`, file names, `hermes-*`
   runCommand derivation names, `HERMES_*` env vars, `share/hermes-agent`.
6. **Python module** `hermes_bootstrap` (and `hermes_cli`), data dir `~/.hermes`.
7. **Product prose** "Hermes" / "Hermes Agent" / "hermes-agent ACP adapter" /
   "Hermes ACP check OK" (the `muse version` output still prints "Hermes Agent
   v…", so the Nix `grep -qi "hermes"` version check intentionally stays).

## Residual risks / follow-ups (OUT of this grain's owned scope — flag for orchestrator)

1. **`nix/nixosModules.nix` still invokes the old binary `…/bin/hermes`**
   (L768 `hermes_bin=…/current-package/bin/hermes`, L890 `"${effectivePackage}/bin/hermes"`,
   L977 `…/bin/hermes gateway run --replace`) and L458 description `` `hermes gateway` ``.
   These break a **NixOS service deployment** (container/gateway) post-rename,
   but are NOT realized by plain `nix flake check` evaluation (they live inside
   activation-script string literals / a static description). Out of my assigned
   file list (`checks.nix` + `hermes-agent.nix` only) and a sibling rename grain
   (`claude/g-rename-completion` / `g-rename-prep`) may own the nix module —
   **deferred to avoid file-ownership collision.** Needs a dedicated edit.
2. **`nix/devShell.nix` L26** `echo "Ready. Run 'hermes' to start."` is now a
   stale user-facing run hint (command is `muse`). Out of assigned scope —
   trivial one-line follow-up.
3. **COLLISION with `claude/g-rename-prep` on `packaging/homebrew/hermes-agent.rb`.**
   `docs/launch/followups/g-rename-prep.md` declares that file as owned and plans
   to `git mv` it to `packaging/homebrew/muse.rb` (Homebrew formula-name rename),
   while explicitly **leaving** the `%w[hermes hermes-agent hermes-acp]` binary
   list (it calls that "binary identity … independent of the repo slug"). This
   grain made exactly that binary-list + `test do` edit. The two are
   complementary (slug/formula-name vs. command/binary name) but touch the same
   file → **the orchestrator must reconcile at merge** (apply this grain's
   binary-name edits onto the `muse.rb` rename). Per contract rule 7, the
   later-starting grain rebases; flagged here for the single-writer orchestrator.
4. **Wider docs sweep deferred.** `website/docs/**` + `docs/**` contain 200+ files
   with user-typed `hermes <subcommand>` examples (e.g. `reference/cli-commands.md`
   alone has ~243, `getting-started/quickstart.md` ~46, `nix-setup.md` ~38, all of
   `user-guide/**`). A blanket rewrite is too broad/risky for this CI-focused
   grain and G1 already called for "a broader docs grain." This grain swept only
   the two **ACP** docs (`acp.md`, `acp-internals.md`) that directly mirror the
   `acp_adapter`/`acp_registry` code changed here. **A dedicated docs-sweep grain
   is still needed** for the command-reference + user-guide tree.
5. **`hermes_cli/**` help/status strings unchanged (correct).** G1 did NOT touch
   `hermes_cli/main.py`, so it still emits "hermes gateway", `prog="hermes"`, etc.;
   the paired `tests/hermes_cli/**`, `tests/gateway/**`, `tests/tools/**`
   assertions therefore still pass and are **out of scope** (G1/G2 own
   `hermes_cli/**`). When that surface is renamed, those tests move with it.

## Git

- Base: `origin/claude/muse-command-rename` @ `d0bc7fa3` (G1). Branch
  `claude/muse-command-rename-cascade` contains G1's commit + this one.
- Commit on `claude/muse-command-rename-cascade`; pushed to
  `origin/claude/muse-command-rename-cascade`. **No PR.**
