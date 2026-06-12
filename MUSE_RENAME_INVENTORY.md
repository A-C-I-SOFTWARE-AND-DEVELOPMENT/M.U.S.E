# MUSE Rename Inventory (Phase 0)

Measured on baseline commit `bbc9afc` (branch `claude/hermes-muse-rename-8n8a6u`), 2026-06-12.

## Headline counts

| Metric | Value |
|---|---|
| Files containing `hermes` (any case) | 3,672 |
| Total `hermes` string hits | 46,378 |
| `.py` files containing `\bhermes_cli\b` | 1,426 (9,905 grep lines incl. non-py) |
| Static `import`/`from hermes_cli` lines | ~4,856 |
| `hermes_cli` self-imports inside the package (absolute) | ~1,273 |
| Test string patch targets `mock.patch("hermes_cli…")` | ~925 (117 files) |
| Test `monkeypatch.setattr("hermes_cli…")` string targets | ~315 |
| Test string targets for top-level `hermes_*` modules | ~84 |
| Static imports of the six top-level `hermes_*` modules | ~466 |
| Distinct `HERMES_*` env var names | ~344 |
| hermes-named paths (files + dirs, excl. `.git`/egg-info/pycache) | 120 |
| `hermes_cli` submodules | 349 `.py` files |

## Hits by file type (files / hits)

py 1,773/26,752 · md 1,204/14,121 · kt 401/2,645 · ts 86/418 · yaml 62/313 · tsx 44/99 · sh 23/573 · json 22/119 · nix 12/272 · xml 9/30 · css 5/317 · js 4/308 · ps1 1/136 · toml 1/34 · rb 1/9 · service 1/6 — remainder negligible.

## Bucket triage

### Bucket B — internal symbols/imports (CST-rename in lockstep)
- The `hermes_cli` package (349 modules) and every import site (~1,426 .py files).
- Top-level modules: `hermes_bootstrap.py`, `hermes_constants.py`, `hermes_state.py`, `hermes_logging.py`, `hermes_model_catalog.py`, `hermes_time.py` (~466 import lines).
- Test patch/setattr **string** targets (~1,324) — CST-invisible; rewritten by scoped token-unique text pass over `tests/`.
- Audited production string sites that build module paths (`-m hermes_cli…` argv, doctor probes, logger-prefix map, `scripts/release.py` version path) — hand-curated list in the plan.

### Bucket C — load-bearing external/protocol strings (PRESERVE or alias; never naive-rename)
| String | Where | Treatment |
|---|---|---|
| MCP server name `"hermes"` | `mcp_serve.py:458` (FastMCP) | PRESERVE — rename advertised name is owner-gated |
| MCP server name `"hermes-tools"` | `agent/transports/hermes_tools_mcp_server.py` | PRESERVE — owner-gated |
| ACP id `"hermes-agent"` | `acp_registry/agent.json` | PRESERVE — owner-gated |
| `HERMES_HOME`, `HERMES_QUIET` | repo-wide | Keep working forever; `MUSE_*` read first (Phase 3) |
| Other ~340 `HERMES_*` env vars (`HERMES_KANBAN_*`, `HERMES_UID/GID`, `HERMES_MANAGED`, `HERMES_WEB_DIST`, …) | scripts, Docker, plugins, workflows | PRESERVE verbatim (out of scope; `_env2` helper is the future pattern) |
| `~/.hermes` state dir | ~510 .py files via `get_hermes_home()` | Migrate via rename+symlink (Phase 4); old path keeps resolving |
| `hermes` console script | `pyproject.toml [project.scripts]` | Keep forever as alias (already present) |
| Distribution name `hermes-agent` | pyproject, Homebrew, Nix, install scripts, npm | Renamed to `muse-agent` in Phase 7 (owner-approved); Homebrew `formula_renames.json` maps old→new |
| Process-match patterns containing `hermes_cli` | `gateway/status.py`, `muse_cli/gateway.py`, `main.py`, `tests/conftest.py` | Extend to match BOTH tokens (a new `muse gateway stop` must find a pre-rename process) |
| Legacy-install detection `'hermes_cli' in content` | `uninstall.py:111` | Keep old token, add new |
| Docker image | `.github/workflows/docker-publish.yml` | Already `muse` — no change |
| Historical records | `.reconciliation/*`, `docs/audits/*`, changelog-like docs | Leave verbatim (historical) — allowlisted |

### Bucket A — cosmetic/user-facing (text-replace freely, Phase 6/7)
Display strings (banner, help/usage text, log/print messages), docstrings, Markdown prose, website docs, READMEs — everything not in B or C above.

## The 120 hermes-named paths (Phase 7 `git mv` targets unless noted)

Python (renamed in Phases 1–2): `hermes_cli/` (Phase 1), `hermes_bootstrap.py`, `hermes_constants.py`, `hermes_logging.py`, `hermes_model_catalog.py`, `hermes_state.py`, `hermes_time.py` (Phase 2; permanent shims left at old names).

Kept at old name permanently (compat): `./hermes` launcher (gets a `./muse` twin).

Left as-is (historical/external/recovered): `recovered-agent-sources/from-hermes-agent/**`, `docs/audits/hermes-*.md` (audit history), `docs/hermes-kanban-v1-spec.pdf` (binary spec), `skills/aos-enterprise-council/agents/hermes/` (catalog content), `website/static/img/hermes-agent-banner.png` (asset, re-pointed if rebranded later), Android `com.aci.hermes` Java package + `Hermes*.kt` classes (application ID / package rename is a separate mobile release concern — surfaced in report, not this pass).

Phase 7 rename targets (with reference updates): `.github/actions/hermes-smoke-test`, `agent/transports/hermes_tools_mcp_server.py` (file only; advertised name preserved), docs/{android,mobile,orchestration,product,security,termux,troubleshooting}/hermes-*.md, `docs/hermes-local-orchestrator.md`, dotclaude hermes-* agents/commands/skills, `hermes_cli/workers/hermes_local.py` → `muse_cli/workers/`, `nix/hermes-agent.nix`, `packaging/homebrew/hermes-agent.rb` (+ rename map), `plugins/hermes-achievements`, `plugins/kanban/systemd/hermes-kanban-dispatcher.service`, `scripts/hermes-*.sh`, `scripts/hermes-gateway`, `setup-hermes.sh`, skills `hermes-*` dirs, `optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py`, `skills/productivity/google-workspace/scripts/_hermes_home.py`, tests `test_hermes_*.py` / `tests/hermes_cli/` / `tests/hermes_state/`, `ui-tui/packages/hermes-ink` + `hermes-ink.d.ts`, website hermes guides, `hermes-already-has-routines.md`.

## Gate baselines (Phase 0, measured)

- `python -m compileall -q -j 0 -x '(\.git|node_modules|\.venv|website/|ui-tui|.*egg-info|recovered-agent-sources|dotclaude)' .` → **exit 0, zero errors**.
- `python -m pytest --collect-only -q -o addopts="-m 'not integration'"` → **29,310/29,333 collected (23 deselected), exit 0, 37s**.
- Full `python -m pytest -q` → recorded in `MUSE_RENAME_REPORT.md` (Phase 0 row) once the baseline run completes.
- NOTE: `pytest` on PATH (`/root/.local/bin/pytest`) lacks the project plugins — all gates use `python -m pytest`.

Closing-audit input: full `git grep -n '\bhermes_cli\b'` snapshot (9,905 lines, 1,426 files) captured at `/tmp/phase0_hermes_cli_allowlist_input.txt` (not committed; counts above are the durable record).
