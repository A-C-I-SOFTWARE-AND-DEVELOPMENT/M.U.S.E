# Hermes Agent Setup

This guide is written for a mobile-first builder using Android, Termux, ADB, GitHub, Codex-style tooling, Claude Code, and ChatGPT.

## What this repository currently is

`echerd27-design/hermes-agent` is currently a fork of the Python/CLI-based Hermes Agent project with an added `dotclaude/` global Claude Code operating layer. It is **not currently a native Android app project**: no `app/src/main/AndroidManifest.xml`, Gradle wrapper, or Android module was found during this audit.

That means the safe setup path today is:

1. Run Hermes as a CLI/Python agent on a supported shell environment.
2. Use Termux on Android for mobile operation where practical.
3. Use ADB from another machine or Termux-adjacent workflows only when a real Android app/service exists.
4. Keep Codex/Claude Code authentication separate from Hermes provider API keys.

## Supported setup paths

### Linux, macOS, WSL2, or cloud shell

```bash
git clone https://github.com/echerd27-design/hermes-agent.git
cd hermes-agent
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

### Android / Termux baseline

Install Termux from a trusted source, then:

```bash
pkg update && pkg upgrade
pkg install -y git python ripgrep clang libffi openssl rust
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.profile 2>/dev/null || true

git clone https://github.com/echerd27-design/hermes-agent.git
cd hermes-agent
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[termux]"
hermes doctor
```

Use `[termux]` before `[all]` on Android because some desktop/voice dependencies may not build cleanly under Termux.

## Codex and Claude Code workflow setup

Hermes can help coordinate work, but it does not automatically inherit a ChatGPT, Codex, Claude, or Claude Code subscription as API tokens.

Use the official authentication flow for each tool you install:

```bash
codex --help
claude --help
```

Then bind all tools to the same workspace:

```bash
cd /path/to/hermes-agent
pwd
scripts/hermes-mobile-workspace-init.sh
```

The helper script captures the current working directory, checks for optional CLIs, and prints safe next commands without fabricating unsupported device-auth behavior.

## Provider/API key configuration

Keep provider credentials outside git:

```bash
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export OPENROUTER_API_KEY="..."
```

Do not commit `.env`, tokens, OAuth credentials, API keys, signing keys, or Android keystores.

## Global Claude Code operating layer

PR #1 added `dotclaude/`, which installs a global Claude Code operating layer into `~/.claude/`:

```bash
bash dotclaude/install.sh
```

This is intentionally separate from the Hermes app/CLI runtime. It configures Claude Code behavior on the developer machine; it is not Android application logic.

## Validation after cloning

Run what is available for the current Python repository:

```bash
python --version
uv --version
uv pip install -e ".[dev]"
python -m ruff check .
scripts/run_tests.sh
```

If you are on Termux and `[all,dev]` fails, retry with the narrower Termux extra first:

```bash
uv pip install -e ".[termux]"
hermes doctor
```

## Native Android status

Native Android service/foreground-service work is not implemented in this repository at this time. Before adding `app/src/main/assets/hermes-cli.sh`, `AndroidManifest.xml`, foreground services, or Gradle configuration, create a real Android module and document the execution boundary between:

- Android UI/service code.
- Termux shell execution.
- ADB-triggered commands.
- Hermes Python runtime.
- Codex/Claude Code CLI sessions.

# Architecture

## Current repository shape

This repository is currently a Python/CLI Hermes Agent codebase with an added global Claude Code operating layer under `dotclaude/`.

It is not currently a native Android application project. During the modernization audit, the expected native Android files were not found:

- `app/src/main/AndroidManifest.xml`
- `build.gradle`
- `gradlew`

## Runtime layers

### 1. Hermes Python CLI/runtime

The Python package is configured in `pyproject.toml` and exposes CLI entry points:

- `hermes`
- `hermes-agent`
- `hermes-acp`

This is the real runtime layer for the current repository.

### 2. Termux/mobile shell layer

Android support today should be understood as Termux/mobile-shell support, not native Android foreground-service support.

Termux can run the Python CLI workflow directly when dependencies resolve for Android. Prefer the `[termux]` optional dependency set before trying the full `[all]` set.

### 3. Global Claude Code operating layer

`dotclaude/` installs files into `~/.claude/` for Claude Code. This layer controls developer workflow behavior and multi-agent prompting discipline. It is intentionally separate from the Hermes runtime.

### 4. Codex/Claude Code workspace coordination

`scripts/hermes-mobile-workspace-init.sh` captures the current git workspace and checks for optional CLIs. It does not authenticate tools or provide API tokens.

## Provider/model configuration principle

Model and provider choices must remain configurable. Do not hardcode a single provider/model into orchestration logic unless there is a narrow test fixture reason.

A correct workflow separates:

- Provider credentials.
- Provider/model selection.
- Orchestration logic.
- Validation results.

## Native Android future architecture

If native Android orchestration becomes a product requirement, add it as a real module with explicit boundaries:

- Android Activity/UI.
- Foreground service for long-running visible work if required by Android policy.
- Termux or embedded runtime bridge, if intentionally supported.
- ADB developer hooks.
- Permission model.
- Logging and notification behavior.
- Clear unsupported-background-execution language.

Do not add fake `am startservice` commands unless a real service class and manifest declaration exist.

# Troubleshooting

## `hermes doctor` is not found

The CLI is not installed in the active environment.

```bash
source .venv/bin/activate
uv pip install -e ".[termux]"
hermes doctor
```

On desktop/server environments, use:

```bash
uv pip install -e ".[all,dev]"
```

## Termux dependency installation fails

Use the narrower Termux extra first:

```bash
uv pip install -e ".[termux]"
```

Avoid installing the full `[all]` profile first on Android if voice, desktop, or platform-specific wheels fail to build.

## Codex or Claude commands are missing

`scripts/hermes-mobile-workspace-init.sh` only checks whether optional CLIs exist. Install and authenticate each tool using its official instructions.

Run:

```bash
codex --help
claude --help
```

If either command is missing, install that CLI first. Do not add fake wrapper commands to the repository.

## API key confusion

A ChatGPT, Codex, Claude, or Claude Code subscription is not the same thing as a provider API key available to this Python runtime.

Use supported environment variables or config files for API-backed providers. Never commit the secret value.

## Android service command fails

This repository currently has no native Android service. Commands like:

```bash
adb shell am startservice ...
```

will not work until a real Android app module, manifest, and service class exist.

Use Termux CLI execution for now.

## Tests fail because no virtualenv exists

Create and activate one:

```bash
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[dev]"
scripts/run_tests.sh
```

## Git workspace script fails

`scripts/hermes-mobile-workspace-init.sh` must be run from the root of a cloned git repository:

```bash
cd /path/to/hermes-agent
bash scripts/hermes-mobile-workspace-init.sh
```

# Repository Audit — Hermes Orchestration Readiness

Date: 2026-05-23
Branch: `repo-modernization-hermes-orchestration-readiness`
Repository: `echerd27-design/hermes-agent`

## Executive verdict

Yellow: this repository is credible as a Python/CLI Hermes Agent fork with a useful global Claude Code operating layer, but it is not currently a native Android app. The safe modernization path is to make the Termux/mobile CLI workflow honest, documented, and validated rather than adding fake Android service files.

## Repository mapping performed

Inspected or probed:

- Branches: `main`, `claude/tender-planck-W3MHK`, `repo-modernization-test`, `repo-modernization-hermes-orchestration-readiness`.
- Pull requests: PR #1, `Add Hermes/AOS/Nourish global Claude Code install (dotclaude/)`.
- Root documentation: `README.md`, `SECURITY.md`.
- Build/test configuration: `pyproject.toml`, `.github/workflows/tests.yml`, `scripts/run_tests.sh`.
- Claude operating layer: `dotclaude/` via PR #1 merge contents.
- Android probes: `app/src/main/AndroidManifest.xml`, `build.gradle`, `gradlew` were not found.

## Current architecture observed

- Python package project using `pyproject.toml`.
- CLI entry points: `hermes`, `hermes-agent`, `hermes-acp`.
- Test runner: `scripts/run_tests.sh`.
- CI workflow: `.github/workflows/tests.yml`.
- Termux-specific optional extra exists in `pyproject.toml` as `[termux]`.
- PR #1 already merged `dotclaude/` as a global Claude Code operating layer.

## Important correction

The modernization prompt referenced Android app surfaces such as:

- `AndroidManifest.xml`
- Gradle
- foreground/background Android services
- `app/src/main/assets/hermes-cli.sh`

Those surfaces do not exist in the current repository root. Adding placeholder Android files would create a false signal and would not be production-ready. This pass instead adds mobile/Termux setup docs and a safe workspace initializer script.

## Fixes applied in this pass

- Added mobile-first setup instructions.
- Added `scripts/hermes-mobile-workspace-init.sh` to bind Codex/Claude/Hermes workflows to the same git workspace without fake authentication commands.
- Preserved what was inspected and what was not present.
- Documented PR/branch reconciliation.
- Added an archive policy for stale drafts/plans.

## Security findings

No committed secret values were intentionally added. The new script:

- Uses `set -euo pipefail`.
- Requires execution from a git workspace.
- Does not echo secret values.
- Does not run shell commands from untrusted input.
- Does not fabricate device-code or subscription-token authentication.

## Validation status

Validation was limited by connector access. This audit was performed through GitHub repository tools, not a checked-out execution environment, so local commands were not run here.

Commands for local validation are listed above and in the PR body.

# Pull Request and Branch Audit

## Pull requests inspected

### PR #1 — Add Hermes/AOS/Nourish global Claude Code install (dotclaude/)

Status observed: merged into `main`.

Verdict: useful, already integrated, but must remain clearly separated from runtime application logic.

What it contains:

- `dotclaude/CLAUDE.md`
- `dotclaude/hermes/HERMES_GLOBAL.md`
- global Claude Code agents
- skills
- commands
- rules
- installer script

Reconciliation decision:

- Keep it.
- Treat it as a developer-machine operating layer for Claude Code.
- Do not treat it as Android app code.
- Do not rely on it as proof that Hermes has native Android orchestration services.
- Keep the separation documented in this file.

## Branches inspected

### `main`

Primary source of truth.

### `claude/tender-planck-W3MHK`

Source branch for PR #1. Work already merged. No blind re-merge needed.

### `repo-modernization-hermes-orchestration-readiness`

Current modernization branch created for this pass.

### `repo-modernization-test`

Temporary branch created during tool retry. It was created from a prior merge commit and has no intended changes from this pass. It can be deleted manually after this PR is merged if desired.

# Changelog

## Unreleased

### Added

- Mobile-first setup guide for desktop, cloud shell, and Android/Termux use.
- Architecture notes documenting the current Python/CLI architecture and native Android boundary.
- Troubleshooting guidance for common setup, Termux, CLI, and API-key issues.
- Repository modernization findings.
- PR/branch reconciliation notes.
- `scripts/hermes-mobile-workspace-init.sh` safe workspace binding helper.
- `docs/archive/README.md` archive policy for stale drafts and planning notes.

### Changed

- Clarified that current mobile operation is Termux/CLI-based, not native Android foreground-service execution.
- Clarified that Codex/Claude Code authentication is separate from Hermes provider API keys.

### Security

- Added documentation warning against committing provider keys, OAuth credentials, Android signing keys, and `.env` files.
- Added a helper script that checks optional CLI availability without printing or collecting secrets.
