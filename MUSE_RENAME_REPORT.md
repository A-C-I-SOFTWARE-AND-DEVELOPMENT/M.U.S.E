# MUSE Rename Report

Hermes → MUSE deep rename with permanent dual-identity compatibility.
One section per phase; every entry records **measured** gate output and the rollback handle (commit sha).
Scope and method: see `MUSE_RENAME_INVENTORY.md` and the approved plan.

## Deviations from the master build prompt (logged once, apply throughout)

1. **Git already exists.** The tree is a git repo on branch `claude/hermes-muse-rename-8n8a6u` (remote exists). No backup copy / `git init` performed; the safety net is one commit per phase + push. Rollback = `git reset --hard <phase sha>`.
2. **`pytest` on PATH is foreign.** `/root/.local/bin/pytest` lacks the project plugins (xdist/timeout). All gates use `python -m pytest`.
3. **Persona lever location.** `hermes_cli/jarvis_prime/persona.py` is *already* unconditionally MUSE. The actual baseline-identity lever is `agent/prompt_builder.py:DEFAULT_AGENT_IDENTITY` + `hermes_cli/default_soul.py:DEFAULT_SOUL_MD` — Phase 5 changes those (spec intent preserved: MUSE default, no flag, abstractions kept).
4. **State-dir migration is rename+symlink, not copy** (atomic, idempotent, no disk doubling; `~/.hermes` keeps resolving via symlink). Breadcrumb `~/.muse/.migrated_from_hermes` written as specified.
5. **Owner decisions taken via Q&A 2026-06-12:** distribution name `hermes-agent` → `muse-agent` in Phase 7; full pytest at every gate.

## Phase 0 — baseline + inventory + triage

- Baseline commit (pre-rename state): `bbc9afc`
- Smoke: `muse --help` → exit 0, M.U.S.E. usage shown.
- compileall (excl. .git/node_modules/website/ui-tui/egg-info/recovered-agent-sources/dotclaude): **exit 0, 0 errors**.
- `python -m pytest --collect-only -q -o addopts="-m 'not integration'"`: **29,310/29,333 collected (23 deselected), exit 0, 37.4s**.
- Full `python -m pytest -q`: **60 failed, 29,040 passed, 214 skipped in 729.72s (12:09)**.
  Pre-existing failures (environment-bound, all unrelated to the rename) — this is the diff base for every later gate:
  - tests/gateway/test_discord_allowed_mentions.py (19), test_discord_clarify_buttons.py (11), test_discord_component_auth.py (9), test_discord_connect.py (3), test_telegram_thread_fallback.py (3), test_send_image_file.py (2)
  - tests/tools/test_ssh_environment.py (7), test_terminal_tool_requirements.py (2), test_local_background_child_hang.py (1), test_path_repair.py (1), test_image_understanding_routing.py (1)
  - tests/hermes_cli/test_web_server.py (1)
- Tooling: libcst 1.8.6 installable via `uv run --no-project --with libcst`; `rename.RenameCommand` present.
- Deliverables: `MUSE_RENAME_INVENTORY.md` (counts, 120 paths, A/B/C triage), allowlist grep snapshot (9,905 lines) at `/tmp/phase0_hermes_cli_allowlist_input.txt`.
- Rollback handle: `6684b68` (`refactor(muse): phase-0 baseline + inventory + triage`).

## Phase 1 — `hermes_cli` → `muse_cli` + permanent meta-path shim

- `git mv hermes_cli muse_cli` (348 file renames). LibCST `rename.RenameCommand` over all 1,112 referencing .py files: **transformed 1,112, failed 0, warnings 0** (~3 min on 4 cores; `.libcst.codemod.yaml` committed with `formatter: ['cat']` — the default `black` formatter was rejected after a first run showed mass reformatting churn; that run was fully reverted).
- Scoped token pass over `tests/` rewrote the ~1,240 string patch/setattr targets; hand-audited production string sites rewritten; **keep-both** legacy tokens restored at: `gateway/status.py` (2 pattern sets), `muse_cli/gateway.py` (process patterns + legacy systemd unit markers), `muse_cli/main.py` (dashboard patterns), `muse_cli/uninstall.py`, `muse_cli/jarvis_prime/sia_self_improve.py`, `muse_cli/user_profile_builder.py` (historical-commit classifiers), `hermes_logging.py` (logger prefixes), `tests/conftest.py` (live-gateway guard).
- Permanent shim `hermes_cli/__init__.py` (meta-path finder; identity alias; runpy `get_code` + mirrored `origin`/`has_location` — the latter found by gate: `python -m hermes_cli.main` initially ran with `__file__=None`). New `tests/test_hermes_cli_shim.py`: **7 passed**.
- pyproject: scripts → `muse_cli.main:main`; `packages.find` gains `"muse_cli", "muse_cli.*"` (fixes latent wheel bug: subpackages were silently dropped) + keeps `"hermes_cli"` for the shim.
- Closing audit: `git grep '\bhermes_cli\b' -- '*.py'` = exactly the keep-both allowlist (8 files); one boundary-missed occurrence (`b"...\x00hermes_cli/main.py..."` in `tests/gateway/test_status.py` — `\b` fails after `\x00`'s `0`) found by the gate and fixed.
- Gates (measured): editable reinstall OK; `import muse_cli` OK; `hermes_cli is muse_cli` identity OK; `python -m hermes_cli.main --version` / `muse --help` / `hermes --help` all exit 0; compileall **0 errors**; collect-only **29,317 green** (baseline + 7 shim tests); full pytest **57 failed / 29,054 passed / 210 skipped in 11:12** — normalized diff vs baseline: 0 new failures (the 1 initial new failure was the fixture above, fixed and re-run green; 4 baseline flakes passed this round).
- Rollback handle: `00ca2da82`.

## Phase 2 — top-level `hermes_*.py` → `muse_*.py` + shim modules

- `git mv` of all six modules (bootstrap, constants, state, logging, model_catalog, time). LibCST `rename.RenameCommand` per module over the ~300 referencing files: **0 failures, 0 warnings**. Scoped token pass rewrote remaining comment/docstring/test-string refs with a `(?!\.db)` guard — `"hermes_state.db"` is a legacy **on-disk filename** in profile copy/exclude lists (`muse_cli/profiles.py`, `muse_cli/profile_distribution.py`) and stays verbatim (Bucket C).
- Six permanent single-file shims left at the old names (`import muse_X as _target; warnings.warn(DeprecationWarning); sys.modules[__name__] = _target`).
- `py-modules` now lists both generations and adds `muse_model_catalog`/`hermes_model_catalog` — the old `hermes_model_catalog` was missing entirely, so wheels never shipped it (latent bug fixed).
- Gates (measured): editable reinstall OK; all six `hermes_X is muse_X` identity checks pass; `from hermes_constants import get_hermes_home` works via shim; compileall **0 errors**; collect-only **29,317 green**; full pytest **59 failed / 29,052 passed / 210 skipped in 10:32** — **0 new failures vs baseline** (normalized diff empty).
- Rollback handle: `50031704a`.

## Phase 3 — `MUSE_HOME` / `MUSE_QUIET` env vars (read-new-then-old)

- `muse_constants`: new `env_first(new, old)` helper; `get_hermes_home()` resolution is now override → `MUSE_HOME` → `HERMES_HOME` (one-shot DeprecationWarning) → `~/.hermes`; `get_default_hermes_root()`/`get_subprocess_home()` use `env_first`; **one-way** import-time mirror `_sync_legacy_env_aliases()` (`MUSE_*` → `HERMES_*` setdefault only) keeps the ~90 scattered direct `HERMES_HOME` readers working for MUSE_HOME-only users without inverting precedence. Canonical aliases added (`get_muse_home`, `display_muse_home`, `get_default_muse_root`, `get_muse_dir`, override fns, `load_muse_dotenv`).
- `MUSE_QUIET` honored at all `HERMES_QUIET` readers; all setters set both names. Subprocess/service spawners now export both vars (cron scheduler, kanban dispatcher, profile relaunch + temp-swap/restore, gateway systemd unit templates, Windows cmd/scheduled-task, codex migration, tools/environments/local). In-process profile overrides set both (MUSE_HOME would otherwise outrank the override). Dockerfile + entrypoint export both.
- Standalone fallback readers (google_chat oauth, google-workspace `_hermes_home.py`, profile-tui, disk-cleanup, achievements dashboard) read `MUSE_HOME` first.
- **Red gate caught a real bug, rolled forward with fix:** first full run failed **841 tests** — conftest pinned `MUSE_HOME` per test, outranking the `HERMES_HOME` that hundreds of tests re-point themselves. Fix: conftest **deletes** `MUSE_HOME` per test (isolation without precedence inversion). Existing `tests/test_hermes_constants.py` / `test_env_loader.py` cases updated to control both vars (new invariant). New `tests/test_muse_env_vars.py` (16 tests: precedence, fallback, empty-counts-as-unset, one-way sync, alias identities, dotenv via MUSE_HOME).
- Gates (measured): compileall clean; targeted env tests 105 passed; full pytest retry **58 failed / 29,068 passed / 210 skipped in 11:13** — **0 new failures vs baseline**.
- Rollback handle: `5d975ac14`.

## Phase 4 — `~/.hermes` → `~/.muse` startup migration (rename + symlink)

- `muse_constants.migrate_legacy_home_once()`: one-shot, idempotent, atomic `os.rename(~/.hermes → ~/.muse)` + `.migrated_from_hermes` breadcrumb + compat symlink at `~/.hermes`. Opts out under: env-configured home (`MUSE_HOME`/`HERMES_HOME`), ContextVar override, managed installs (`*_MANAGED` env or `.managed` marker), existing `~/.muse` (never clobbers), or `~/.hermes` already a symlink. Never copies.
- Read-side `_default_native_home()`: existing `~/.muse` → existing `~/.hermes` → fresh default `~/.muse`; wired into `get_hermes_home()` default branch, `get_default_hermes_root()`, and the profile-fallback warning path. Hooks at `ensure_hermes_home()` (the startup chokepoint) + `muse_cli/main.py:main`, `run_agent.py:main`, `acp_adapter/entry.py:main`, `mcp_serve.py:run_mcp_server`.
- **The migration ran live on this container during the gate** (real `/root/.hermes` → `/root/.muse` with symlink) — incidental end-to-end validation. It also exposed that `_hermes_home_for_target_user()` (sudo service install) only understood the `.hermes` default layout — fixed to handle both, with new tests for the `.muse` layouts.
- New `tests/test_muse_home_migration.py` (12 tests): rename+breadcrumb+symlink, double-run no-clobber with data intact, pre-existing `~/.muse` untouched, env/managed/symlink/nothing no-ops, and default-resolution order. Tests asserting the old fresh-default (`~/.hermes`) rewritten to the new invariant in: test_hermes_home_profile_warning, test_hermes_constants, hermes_cli/test_config, hermes_cli/test_gateway_service (also made hermetic — the container's real post-migration symlink leaked into `Path.resolve()`), tools/test_tirith_security.
- Gates (measured): targeted suites green; compileall clean; collect-only **29,344 green**; full pytest (final) **58 failed / 29,082 passed / 210 skipped in 11:33** — only diff vs baseline was `tests/agent/test_curator.py::test_state_atomic_write_no_tmp_leftovers`, an xdist flake that passes twice in isolation and is unrelated to the rename (no home/env interaction).
- Rollback handle: `e37996119`.

## Phase 5 — MUSE as the default-and-only baseline identity

- `agent/prompt_builder.py:DEFAULT_AGENT_IDENTITY` and `muse_cli/default_soul.py:DEFAULT_SOUL_MD` are now the MUSE identity ("You are MUSE — a local-first AI operating partner… loyal to the user's long-term mission rather than blindly obedient to the moment — challenge weak ideas plainly…"), kept word-for-word identical with a test pinning the equality (no cross-package import — cycle risk).
- **Zero logic changes**: SOUL.md seeding, the stable-slot fallback, codex adapters, and the jarvis_prime Persona (already always-MUSE) pick the constants up. `/personality` overlay mechanics untouched — it is additive, so `none`/other still yields the MUSE baseline; no flag, mode, or command is required (and `load_soul_md()` *seeds* the default SOUL.md on first run, so even an empty home yields MUSE).
- Existing installs: `_ensure_default_soul_md()` upgrades a **never-edited** legacy default SOUL.md (strip-equal to `_LEGACY_DEFAULT_SOUL_MD`) to the MUSE text at startup; an edited SOUL.md is never touched.
- Tests: new `tests/test_muse_identity.py` (9 tests: constant equality, MUSE-not-Hermes, empty-home seeding, `/personality none` → MUSE invariant, legacy upgrade, edited-SOUL-untouched). `tests/cli/test_personality_none.py` kept in full (clear-to-empty overlay semantics preserved). One existing assertion updated (`test_prompt_builder` seeded-soul content). Fixture strings like "You are Hermes." in codex-responses/restore tests left as inert test data (byte-restore invariants).
- Gates (measured): compileall clean; collect-only **29,355 green**; full pytest **58 failed / 29,091 passed / 210 skipped in 11:19** — only diff vs baseline was one telegram-topic xdist flake (passes in isolation and with its file).
- Rollback handle: `6f2c006f1`.

## Phase 6 — user-facing strings (Bucket A)

- Default banner art is now the M.U.S.E. brand: the no-skin fallbacks in `muse_cli/banner.py` switched `HERMES_AGENT_LOGO`/`HERMES_CADUCEUS` → the already-present `MUSE_WORDMARK`/`MUSE_GLYPH` (Hermes art constants retained as skin assets; render smoke-tested).
- Docstrings/usage: `cli.py` ("MUSE — Interactive Terminal Interface" / "MUSE — Interactive AI Assistant"), `muse_cli/__init__.py`, `cli-config.yaml.example` header, the root `hermes` launcher docstring, `muse_cli/doctor.py` SOUL.md template + hint (now MUSE).
- Bucket C untouched: model names (`NousResearch/Hermes-*` LLMs), service unit names, process patterns, env names, banner "Nous Research" credit. `HERMES_AGENT_HELP_GUIDANCE` (skill name + docs URL = external facts) left for the owner-gated list. The openclaw-migration `rebrand_text` (OpenClaw→Hermes) deliberately left: its replacement string is reused for filesystem paths (`~/.openclaw` → `~/.hermes`, which still resolves via the Phase 4 symlink) — rebranding it to MUSE is logged as a follow-up.
- Gates (measured): compileall clean; cli tests 759 passed; full pytest **58 failed / 29,091 passed / 210 skipped in 11:22** — **0 new failures vs baseline**.
- Rollback handle: `0a0d6c1aa`.

## Phase 7 — filenames, packaging, docs, import-linter

**Distribution rename (owner-approved):** pyproject `name = "muse-agent"` + all 21 self-referential extras; `uv lock` regenerated cleanly (282 packages; root renamed); `nix/python.nix` venv key → `muse-agent`; `nix/hermes-agent.nix` → `nix/muse-agent.nix` with `pkgs.muse-agent` canonical and `pkgs.hermes-agent` a permanent overlay alias; Homebrew formula → `packaging/homebrew/muse-agent.rb` (`class MuseAgent`) + `formula_renames.json` mapping `hermes-agent → muse-agent`; `acp_registry/agent.json` pip hint → `muse-agent[acp]` (ACP **id** stays `hermes-agent`, owner-gated); `scripts/release.py` uvx hint; android workflow artifact name; editable install reinstalled as `muse-agent` (old dist uninstalled, console scripts restored).

**Path renames (with reference updates):** `tests/hermes_cli/` → `tests/muse_cli/`, `tests/hermes_state/` → `tests/muse_state/`, `tests/test_hermes_*.py` → `tests/test_muse_*.py` (shim tests keep old-name coverage by design); `setup-hermes.sh` → `setup-muse.sh` and all 7 `scripts/hermes-*` → `scripts/muse-*` — **permanent forwarding stubs left at every old script path**; `.github/actions/hermes-smoke-test` → `muse-smoke-test`; 25 internal docs `docs/**/hermes-*.md` → `muse-*.md` with repo-wide link updates (88 referencing files); root `./muse` launcher twin added beside the kept `./hermes`.

**Import freeze:** `[tool.importlinter]` forbidden contract — production packages (muse_cli, agent, gateway, tools, cron, providers, tui_gateway, acp_adapter) may not import any `hermes_*` legacy name. Measured: **"Legacy hermes_* module names are import-frozen (compat shims only) KEPT — Contracts: 1 kept, 0 broken"** (868 files, 7,042 dependencies). Wired into `.github/workflows/lint.yml` as a blocking job. (grimp can't take single-file modules as roots, so `cli.py`/`run_agent.py` are covered by the grep audit instead — noted in pyproject.)

**Docs:** README gains a "Compatibility with Hermes-era installs" table (all permanent aliases enumerated); CLAUDE.md/AGENTS.md/SETUP.md/CONTRIBUTING.md module paths updated to `muse_cli`/`muse_*`.

**Intentionally KEPT at old names (Bucket C, each with reason):**
- `agent/transports/hermes_tools_mcp_server.py` — `python -m agent.transports.hermes_tools_mcp_server` is the documented launch command in users' `~/.codex/config.toml` (external contract).
- `muse_cli/workers/hermes_local.py` + `docs/orchestration/workers/hermes-local.md` — the worker profile name `hermes-local` persists in user configs and job ledgers.
- `plugins/hermes-achievements/` — plugin folder name is referenced from user `config.yaml` plugin lists.
- systemd `hermes-gateway*` unit names, `_GATEWAY_KIND`, process patterns — live units on user machines.
- `skills/**hermes**`, `dotclaude/**hermes**` — user-invocable skill/command names (data, not code).
- `scripts/install.sh` `$HERMES_HOME/hermes-agent` install dir — script's own in-place-preservation contract.
- `ui-tui/packages/hermes-ink` / `@hermes/ink` npm names — renaming requires rebuilding committed dist bundles (follow-up).
- Android `com.aci.hermes` package / `Hermes*.kt` — application-ID rename is a separate mobile release concern.
- `website/docs/guides/*-hermes*.md` filenames — published URL slugs.
- Historical records: `.reconciliation/`, `docs/audits/hermes-*`, `recovered-agent-sources/`, `hermes-already-has-routines.md`.

**Gate-caught fixes:** 10 new test failures after the renames — ACP-manifest/release tests pinning the old dist name, the termux-all extra test, and termux doc tests reading the now-stubbed script paths — all updated to the new invariant (the ACP **id** assertion still pins `hermes-agent`, correctly).

## Owner-gated proposals — RESOLVED by owner authorization (`Yes, with authorization.`, 2026-06-12)

**Applied under authorization:**
1. **MCP advertised name** → `"muse"` (`mcp_serve.py`), env-overridable via `MUSE_MCP_SERVER_NAME` / legacy `HERMES_MCP_SERVER_NAME` (verified: default `muse`, legacy pinnable to `hermes`). Note: client tool prefixes (`mcp__<name>__*`) come from the *client's own config key*, so existing `mcp__hermes__*` allow-lists keep working unchanged.
2. **MCP tools server** → `"muse-tools"` (env-overridable `MUSE_TOOLS_MCP_SERVER_NAME`/`HERMES_TOOLS_MCP_SERVER_NAME`); module path `agent/transports/hermes_tools_mcp_server.py` kept (external `-m` contract in `~/.codex/config.toml`).
3. **ACP manifest** → `id: "muse-agent"`, `name: "MUSE"`, MUSE description (repo/license/authors unchanged; registry-side coordination still needed when submitting).
4. **PyPI workflow** environment URL → `pypi.org/p/muse-agent` (publish itself still off-machine).
5. **Help guidance + bundled skill**: `skills/autonomous-ai-agents/hermes-agent` → `muse-agent`; `MUSE_AGENT_HELP_GUIDANCE` (legacy constant name kept as alias) now points at the `muse-agent` skill.
6. **openclaw-migration rebrand** → OpenClaw/ClawdBot/MoltBot now rebrand to **MUSE** (lowercase matches become `muse`, so `~/.openclaw` path fragments rewrite to the canonical `~/.muse`); 41 migration tests green.
7. **Website skill-docs generator** brand strings → MUSE (the live site builds from the generator, which still said Hermes).

**Still pending (off-machine or needs coordinated release — cannot be executed from this environment):**
- Homebrew tap publish (formula + `formula_renames.json` are ready in-repo).
- PyPI project creation/redirect for `muse-agent` (local version `+aci.1` can't publish regardless).
- ACP registry submission of the updated manifest.
- Docs domain `hermes-agent.nousresearch.com` (external DNS/site — URLs left intact so links keep working).
- Android `applicationId com.aci.hermes` — store-identity change; needs a mobile release plan (changing it silently orphans existing installs).
- Website guide URL slugs (`*-hermes*.md`) — need `@docusaurus/plugin-client-redirects` first or old URLs 404.
- Per-skill `author: Hermes Agent` frontmatter sweep across hundreds of SKILL.md files (cosmetic; follow-up).

1. **MCP advertised server name `"hermes"`** (`mcp_serve.py`). Client configs (`claude_desktop_config.json`, `.mcp.json`) address tools as `mcp__hermes__*`; renaming breaks every existing allow-list. Proposal: register a second FastMCP entry point advertising `"muse"` (same tools) and document both; never remove `"hermes"`. Verified this session: server still advertises `hermes`.
2. **MCP `"hermes-tools"`** (`agent/transports/hermes_tools_mcp_server.py`) — same pattern: additive `muse-tools` alias server, keep old name + module path (`-m` path is in `~/.codex/config.toml`).
3. **ACP id `"hermes-agent"`** (`acp_registry/agent.json`) + `authors: ["Nous Research"]` + website URL — registry-facing identity. Proposal: coordinate with the ACP registry to add a `muse-agent` entry or alias; until then the id stays.
4. **Homebrew publish** — the renamed formula + `formula_renames.json` are prepared in-repo; pushing to a published tap (and the formula's upstream `url`/`homepage`, which point at NousResearch releases) is an off-machine action.
5. **PyPI project** — `upload_to_pypi.yml` still targets `pypi.org/p/hermes-agent`; the local version (`+aci.1`) can't publish anyway. Proposal: when publishing is desired, create the `muse-agent` PyPI project and keep `hermes-agent` as a redirect/stub release.
6. **`HERMES_AGENT_HELP_GUIDANCE`** (`agent/prompt_builder.py`) — references the `hermes-agent` skill name and `hermes-agent.nousresearch.com` docs URL (external facts).
7. **Website URL slugs** (`website/docs/guides/*-hermes*.md`) and `sync-aci-to-base44.yml` external repo refs.
8. **Android applicationId `com.aci.hermes`** — store-identity change; needs a mobile release plan.
9. **openclaw-migration `rebrand_text`** OpenClaw→Hermes mapping (replacement doubles as a path component) — propose OpenClaw→MUSE with explicit path-mapping table.

## Compat infrastructure now in place (all PERMANENT)

| Layer | Mechanism |
|---|---|
| `import hermes_cli[.x]` | Meta-path finder shim (`hermes_cli/__init__.py`) — identity alias, runpy support, DeprecationWarning |
| `import hermes_{bootstrap,constants,state,logging,model_catalog,time}` | Six single-file `sys.modules` alias shims |
| `hermes` command | Console-script alias → `muse_cli.main:main` |
| `./hermes` launcher | Kept beside new `./muse` |
| `HERMES_HOME`/`HERMES_QUIET` | Read as fallback forever; one-way `MUSE_*`→`HERMES_*` startup mirror for direct readers; spawners export both |
| `~/.hermes` | One-shot atomic rename → `~/.muse` + breadcrumb + compat symlink; never copies/clobbers |
| Legacy function names | `get_hermes_home` etc. kept; `get_muse_home` etc. canonical aliases |
| `setup-hermes.sh`, `scripts/hermes-*` | Permanent exec-forwarding stubs |
| Homebrew | `formula_renames.json` `hermes-agent → muse-agent` |
| Nix | `pkgs.hermes-agent` overlay alias of `pkgs.muse-agent` |
| Process/unit discovery | Keep-both pattern lists (old + new cmdlines, systemd markers) |
| Drift prevention | import-linter forbidden contract, blocking in CI |

## Rollback-handle inventory

| Phase | Commit |
|---|---|
| 0 baseline+inventory | `6684b68` |
| 1 package rename + shim | `d988931cf` (amended) |
| 2 top-level modules | `50031704a` |
| 3 env vars | `5d975ac14` |
| 4 state-dir migration | `e37996119` |
| 5 MUSE identity | `6f2c006f1` |
| 6 display strings | `0a0d6c1aa` |
| 7 packaging/paths/linter | (this commit) |

## Final confirmation

- `muse` launches with the MUSE identity by default — no flag, mode, or command needed (seeded SOUL.md and the hardcoded fallback are both MUSE; `/personality none` still yields MUSE).
- `hermes`, `python -m hermes_cli.main`, `import hermes_cli`, every `HERMES_*` env var, `~/.hermes`, old script paths: all still work, permanently.
- MCP servers still advertise `"hermes"` / `"hermes-tools"` (verified at gate); ACP id unchanged.
- No feature or function removed — rename only (plus two latent packaging bugs fixed: wheel subpackage omission, missing `model_catalog` py-module).
- Final full-suite result (measured): **56 failed / 29,093 passed / 210 skipped in 9:18** — every failure inside the 60-failure pre-existing baseline; **zero new failures**. Final smoke: muse/hermes/`-m hermes_cli.main`/`-m muse_cli.main` all exit 0; shim identity + MUSE identity assertions pass; lint-imports contract KEPT.
