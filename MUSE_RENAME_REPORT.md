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
- Rollback handle: this phase's commit (see git log: `refactor(muse): phase-0 baseline + inventory`).
