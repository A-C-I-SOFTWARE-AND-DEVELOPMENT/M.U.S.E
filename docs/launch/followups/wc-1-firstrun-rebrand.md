# WC-1: First-run gate + happy-path rebrand (collapsed single writer)

- **Status:** building → in-review (PR opens on push)
- **Risk class:** behavior-change (owner-gated) — the gate now returns True
  on a bootstrap-written `model_policy.json` with a locally-executable route
- **Branch:** `claude/vigilant-knuth-519h3u` · **Base:** `main` @ `860a88b8e`
- **PR:** TBD (draft on push)
- **Owner-gate required to merge?** **yes** — owner authorized via
  `Yes, with authorization.` on 2026-06-08 (the comprehensive `/aos-audit`
  closeout thread).

## Intent (one paragraph)

Close the live "muse not working" symptom. Before WC-1, a user who followed
the README's headless instruction (`muse models bootstrap`) was told
"success" but then hit the identical first-run gate exit-1 on the next
`muse` invocation — `model_bootstrap.py:491-494` wrote
`~/.hermes/jarvis_prime/model_policy.json` while
`hermes_cli/main.py:287-398:_has_any_provider_configured()` never read it.
The documented escape hatch was a dead end. WC-1 closes the
bootstrap-writes-X / gate-reads-Y disconnect: the gate now reads the
policy file and returns True when any locally-executable enabled route is
viable (claude / codex worker with the binary on PATH, or a local OSS
runtime, or a hosted-free provider). It *also* sweeps the highest-leverage
happy-path "hermes" brand leaks the rebrand-cascade deliberately deferred
(`g1b-rename-cascade.md:117-118`): `_parser.py:90 prog="hermes"` so every
`--help` and usage error prints `usage: hermes`; the gate banner; the
post-install banner; the doctor remediation; the non-interactive setup
guidance.

Collapsed in WC-1 (single writer) because the gate fix and the brand
sweep edit *the same line* at `main.py:1394` and *the same function* at
`setup.py:177-192` — sequencing them would force the second to rebase
onto an inherent conflict.

## Owned files (the ONLY files this task may write)

- `hermes_cli/main.py` — gate (`_has_any_provider_configured`) +
  user-visible banner / docstring / doctor / `_require_tty` strings.
- `hermes_cli/setup.py` — `print_noninteractive_setup_guidance`
  (detection-aware) + rebrand strings.
- `hermes_cli/_parser.py` — `prog="muse"`, description, `_EPILOGUE`.
- `tests/hermes_cli/test_api_key_providers.py` — new
  `TestProviderGateReadsBootstrapPolicy` (8 cases).
- `tests/hermes_cli/test_setup_noninteractive.py` — assertion updates
  (`hermes config set` → `muse config set`).

## Plan (bounded steps)

1. **Gate**: add a `model_policy.json` reader to `_has_any_provider_configured`
   (after the existing Claude Code creds branch). Honor four enabled-route
   shapes: `claude_code_worker`, `codex_worker` (binary on PATH);
   `local_oss` (`runtimes` non-empty); `hosted_free_or_user_configured_oss`
   (`providers` non-empty). Read via `get_hermes_home()` so the existing
   test patch chain (`config.get_hermes_home`) keeps the new branch
   hermetic. Drop the redundant in-function `import json` from the Nous
   Portal branch (it was shadowing the module-level import and creating
   `UnboundLocalError`s when my code referenced `json` before that branch
   ran). [done]
2. **Non-interactive guidance**: detect `shutil.which("claude")` or
   `shutil.which("codex")`. If present, recommend
   `muse models bootstrap --jarvis --no-pull` as the cheapest one-line fix
   (it pairs with step 1's gate read). Always emit the `muse config set ...`
   env-var fallback. [done]
3. **Happy-path rebrand**: `prog="hermes"` → `prog="muse"`, description,
   `_EPILOGUE`, gate banner, post-install banner, doctor message,
   `_require_tty` error. Intentional out-of-scope (substrate, NOT happy
   path): module docstring at `main.py:1-44`, `tests/conftest.py:1`,
   `pyproject.toml:6 name`, `~/.hermes/` home dir, `HERMES_*` env vars,
   class names. [done]
4. **Tests**: 8-case `TestProviderGateReadsBootstrapPolicy` mirroring the
   `_isolate` pattern from `test_claude_code_creds_ignored_on_fresh_install`.
   Update two existing setup tests whose assertions hard-coded
   `"hermes config set model.provider custom"`. [done]

## Validation

- `uv run ruff check hermes_cli/main.py hermes_cli/setup.py hermes_cli/_parser.py tests/hermes_cli/test_api_key_providers.py tests/hermes_cli/test_setup_noninteractive.py` → **all checks passed**
- `uv run ty check` on edited files → **zero new diagnostics on the
  edited lines** (40 pre-existing diagnostics in `main.py:1-48` etc.
  remain — they are intentionally out of scope per the partition).
- `uv run python -m pytest tests/hermes_cli/test_api_key_providers.py::TestProviderGateReadsBootstrapPolicy tests/hermes_cli/test_setup_noninteractive.py -q` →
  **all passed** (8 new + 1 updated, plus full file regression-green).

## Residual / follow-on

- Per the deep-research finding, the strongest cold-start pattern is
  Aider's ordered-env-var scan + OpenRouter OAuth fallback to a *free
  tier* (proven by `aider/onboarding.py`'s ANTHROPIC → DEEPSEEK → OPENAI
  → GEMINI → OPENROUTER chain). WC-1 closes the bootstrap loop; a future
  task can extend the gate to *probe* common credentials and trigger a
  free-tier OAuth fallback. Tracked as a successor packet, not folded in.
- Module docstring `main.py:1-44` still teaches `hermes <cmd>`. It is
  reached by `--help` *epilogue* (handled here via `_parser._EPILOGUE`)
  but the docstring itself is reached only by `pydoc`/IDE hover, so it
  is lower-leverage. Left for a follow-on doc-sweep packet.
- The `HERMES_HOME` env var stays. Renaming it would break every existing
  install at once (state.db / sessions / SOUL.md all live under
  `~/.hermes/`). A future migration packet is the right place for that.
