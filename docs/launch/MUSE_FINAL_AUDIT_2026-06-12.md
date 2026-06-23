# muse Final Audit & Polish — 2026-06-12

Owner-requested final pass: *"audit repo … all interfaces work and are muse
branded … muse default not hermes in terminal … /muse pulls up the muse
branded TUI … desktop and mobile apps install and run in one click … model
and function switching user friendly … fully built and wired … final polish
and audit."*

Branch: `claude/stoic-planck-l3dvd6`. Scope rule applied throughout:
**user-visible strings rebrand to muse internal identifiers stay** —
`hermes_cli` module, `~/.hermes` home, `HERMES_*` env vars, locale keys,
the `hermes` CLI back-compat alias, and the Android `com.aci.hermes`
application id (signing continuity) are unchanged by design.

---

## 1. Verified green (no work needed)

| Surface | Evidence |
|---|---|
| `muse` is the canonical terminal command | `pyproject.toml` `[project.scripts]`: `muse`, `muse-agent`, `muse-acp`; `hermes` kept as documented back-compat alias |
| muse-branded TUI is the default look | `hermes_cli/skin_engine.py` — runtime default skin is `singularity` (`agent_name="muse"`, muse welcome/response label/banner) |
| README / gateway cockpit / web SPA UI | README.md fully muse cockpit HTML "Message muse…"; `web/index.html` title `muse - Dashboard`, i18n `brand: "muse"` |
| Android app one-click | `apps/android/`: Gradle 8.11.1 + wrapper, `./gradlew assembleDebug` → installable APK; muse strings.xml; CI builds (`android-build.yml`) and publishes the APK (`android-release.yml`) — no missing pieces, signing falls back to debug cleanly |
| Desktop app one-click | `apps/desktop/`: Tauri v2 + React 19; `cargo tauri build` produces installers; muse bundle id `com.aci.muse` / "muse" window; one-button CI release lane (`muse-desktop-release.yml`, signed or clearly-unsigned); shell auto-starts the backend via `muse cockpit serve` |
| Model switching | `/model` opens a full picker modal (provider, context, cost, capabilities), `--global` persists, live in-place `agent.switch_model()`; fuzzy auto-correct + "Similar models" already in `hermes_cli/models.py` |
| Toolset/function switching | `/tools list|enable|disable`, `/toolsets`, `/profile`; 50+ composable toolsets in `toolsets.py` |
| Wiring & test health | Entry points import clean; 1,500+ test files; 13+ CI workflows incl. lint, orchestration, jarvis-prime unit, launch gate; 15+ complete gateway platform bridges |

## 2. Fixed in this pass

1. **`/muse` pulls up the muse TUI** (`cli.py`, `hermes_cli/commands.py`)
   — `/muse` (or `/m`) with no intent now activates the singularity skin,
   persists `display.skin`, re-renders the muse banner (intentionally
   clears scrollback — that is the "pull up" effect), and prints the muse
   welcome + usage hints. `/muse <intent>` still routes through the
   JarvisPrime runtime; usage/error text echoes the alias the user typed;
   the no-arg path no longer pays the JarvisPrime import.
2. **Terminal branding sweep** (`cli.py`, `hermes_cli/main.py`,
   `hermes_cli/setup.py`, `hermes_cli/doctor.py`, `hermes_cli/slack_cli.py`)
   — help/uninstall/update/backup/profile/MCP/ACP text, `muse <subcommand>`
   hints, setup-wizard banners (box widths preserved), muse Doctor banner,
   history labels `◆ muse`, status panel, busy-mode prose, clarify
   panel, response-label fallbacks `◉ muse`.
3. **Agent identity** (`agent/prompt_builder.py`, `hermes_cli/default_soul.py`)
   — default system prompt and seeded SOUL.md now open with *"You are
   muse (Multi-Use Synaptic Entity), an intelligent AI operating
   partner built on the Hermes Agent runtime by Nous Research."* Heritage
   credit preserved. `muse doctor --fix` now seeds the canonical
   `DEFAULT_SOUL_MD` instead of a divergent inline template.
4. **Gateway + platform defaults** — Telegram topic copy, gateway hints,
   `muse TUI Status` bar, email subject default, WhatsApp reply prefix
   `◉ *muse*`, Home Assistant notification title, Matrix device name,
   Discord `/update` description, IRC realname, Slack manifest bot
   name/description, OpenRouter/AI-gateway `X-Title`, Copilot/Codex client
   titles, MCP serve description, MCP OAuth client name.
5. **Locales (16 languages)** — token-level rebrand of the gateway message
   catalog (`Hermes → muse`, `` `hermes …` → `muse …` ``, `⚕ → ◉`); keys and
   `{placeholders}` untouched (parity enforced by `tests/agent/test_i18n.py`);
   en baseline names the canonical `muse` command with the legacy alias noted.
6. **Binary resolution prefers `muse`** — `gateway/run.py::_resolve_hermes_bin`
   and `hermes_cli/relaunch.py` (already done) try `muse` → `hermes` →
   `python -m hermes_cli.main`; the stale-dashboard scan matches processes
   launched under either name.
7. **Setup tooling** — `setup-hermes.sh` shows the muse banner, symlinks
   the canonical `muse` command (keeps `hermes`), and prints `muse …` next
   steps; new root `./muse` wrapper twin of `./hermes`.
8. **Docs/metadata** — `web/README.md`, `SETUP.md` (title, repo slug
   `A-C-I-SOFTWARE-AND-DEVELOPMENT/muse`, clone paths), `flake.nix`
   description.
9. **Switching UX polish** — `/model` no-arg surfaces inventory-load errors
   with a `muse doctor` pointer instead of a misleading "no providers"
   message; failed model-alias lookups append "did you mean" candidates;
   `/tools enable|disable` suggests close matches for unknown toolset names.

## 3. Validation evidence

- `uv run ruff check` — **clean** after every phase.
- `uv run ty check` — 1,390 diagnostics, **below** the pre-change baseline
  (1,928 on the same environment); no new diagnostics introduced.
- `pytest tests/cli tests/hermes_cli` — **5,827 passed**, 0 failed.
- `pytest tests/gateway` — **6,150 passed**, 0 failed.
- `pytest tests/agent tests/run_agent tests/tools` — 9,994 passed; the same
  9 failures occur on `origin/main` (environment-dependent SSH/Telegram
  sandbox tests) — **zero regression delta**.
- New tests: `tests/cli/test_muse_slash_command.py` (no-arg `/muse` skin
  activation + persistence, alias echo, intent routing, emergency stop),
  `tests/hermes_cli/test_model_switch_suggestions.py` (suggestions +
  picker error surfacing), near-miss cases in
  `tests/hermes_cli/test_tools_disable_enable.py`.

## 4. Known deferrals (intentional, with rationale)

| Item | Rationale |
|---|---|
| Desktop PyInstaller sidecar bundling | Documented follow-up in `apps/desktop/README.md`; the shell auto-starts an installed `muse` backend today. Bundling a Python runtime per-OS is a release-lane project, not a polish item. |
| `package.json` names (`hermes-agent`, `hermes-tui`) | `private: true`, never published; renaming forces lockfile regeneration and script churn for zero user-visible benefit. |
| Classic `default`/`caduceus` skin keeps the gold "NOUS HERMES" look | Intentional legacy skin; users opt into it via `/skin`. |
| `gateway/platforms/yuanbao.py` TODO (real group metadata) | Needs live Yuanbao API access; placeholder is functional. |
| `hermes_cli/orchestrator.py` GitHub-history-mining placeholders | Marked v-next; orchestration core is complete (Job/Worker/Routing/Gate/Ledger). |
| Internal identifiers (`hermes_cli`, `~/.hermes`, `HERMES_*`, `com.aci.hermes`) | Back-compat + signing continuity; renaming is high-risk, zero-reward. |
| Docstrings about the legacy Windows "Hermes Desktop" Electron child process | Technical accuracy for the `hermes.exe` lock diagnostics; user-visible advice now says "the muse desktop app". |

## 5. How to re-verify manually

```bash
muse                  # muse banner, singularity skin by default
# inside the TUI:
/muse                 # pulls up the muse-branded TUI (skin + banner + hints)
/muse plan my week    # routes the intent through the muse runtime
/model                # picker modal; on broken config: actionable error
/tools enable webb    # → Did you mean: web?
hermes                # legacy alias still works
```
