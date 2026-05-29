# Hermes Agent v1.1.0 — Free-First JARVIS Launch

This release makes JARVIS Prime **launchable in one command**, free-first,
with paid APIs strictly opt-in and Claude Code / Codex wired as official
worker lanes.

## Highlights

- **One-click launch.** `bash <(curl … install.sh) --jarvis-launch`
  installs Hermes and brings JARVIS Prime up: free-first model routing,
  local runtime detection, worker-lane detection, safe memory, and a launch
  doctor report. PowerShell parity via `-JarvisLaunch`.
- **`hermes jarvis launch`** — full launch path for existing installs.
- **`hermes models bootstrap --free-first --jarvis`** — a *real* bootstrap
  (detect → plan → write policy → optional pull), not just a recommendation.
- **`hermes doctor --jarvis-launch`** — structured launch-readiness check;
  exits non-zero only on a hard launch blocker.
- Dependency-free equivalents on the stdlib-only path:
  `python -m hermes_cli.jarvis_prime {bootstrap,launch,launch-doctor,stop}`.

## Free-first route order

`${HERMES_HOME}/jarvis_prime/model_policy.json` records:

1. `local_oss` (Ollama / llama.cpp / vLLM / LM Studio)
2. `hosted_free_or_user_configured_oss` (OpenRouter / HF / Nous / … — detected only when a key is already present)
3. `claude_code_worker`
4. `codex_worker`
5. `paid_api_explicit_only` (**disabled** unless `HERMES_JARVIS_ENABLE_PAID=1`)

Model choices come from the OSS model brain catalog (single source of truth).

## Worker lanes (Claude Code & Codex)

- Detection only — via the official CLIs on `PATH`. No credential scraping,
  no API keys, no subscription-boundary bypass.
- Structured lanes: **Claude Code Builder**, **Codex Reviewer**,
  **Codex Bounded Fix Worker**.
- **Single editor per branch** — a file-based, time-boxed branch lease
  (`hermes_cli/jarvis_prime/worker_locks.py`) refuses concurrent editing by
  two tools and self-heals on a crashed (expired) lease. The reviewer lane
  consumes the builder's patch as context rather than editing in parallel.
- Structured handoff packet: mission, repo root, branch, risk class, allowed
  files, forbidden actions, acceptance criteria, verification commands,
  rollback plan, owner-gated actions.

## Safety

- No secrets in git, logs, memory, tests, fixtures, or generated config.
  Bootstrap reads env presence only; key values are never read or written.
- Paid providers are detected for transparency but never auto-enabled.
- Owner-authorization phrase contract preserved; emergency stop preserved
  and now also releases all worker branch leases.
- Termux/Android compatibility preserved — the launch stack is stdlib-only
  at import time.

## New modules

- `hermes_cli/jarvis_prime/model_bootstrap.py`
- `hermes_cli/jarvis_prime/launch.py`
- `hermes_cli/jarvis_prime/launch_doctor.py`
- `hermes_cli/jarvis_prime/worker_registry.py`
- `hermes_cli/jarvis_prime/worker_locks.py`

## New / updated CLI

- `hermes jarvis launch`, `hermes jarvis stop`
- `hermes models bootstrap`
- `hermes doctor --jarvis-launch [--json]`
- `python -m hermes_cli.jarvis_prime {bootstrap,launch,launch-doctor}`

## Installers

- `scripts/install.sh`: `--jarvis-launch` (safe in `curl | bash`; `--no-pull`
  for unattended; fails only if Hermes can't launch; prints recovery commands;
  Termux + root/FHS + hash-verified `uv.lock` paths preserved).
- `scripts/install.ps1`: `-JarvisLaunch` parity.

## Docs

- New: `docs/jarvis-free-first-launch.md`
- Updated: `README.md`, `docs/jarvis-prime-operating-system.md`

## Tests

- `tests/test_jarvis_model_bootstrap.py`
- `tests/test_jarvis_launch_doctor.py`
- `tests/test_jarvis_launch_cli.py`
- `tests/test_subscription_worker_detection.py`
- `tests/test_worker_branch_locking.py`
- `tests/test_installer_jarvis_launch_flag.py`
