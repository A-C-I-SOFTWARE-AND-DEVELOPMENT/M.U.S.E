# ACI muse — Setup Guide

> **Repo:** `A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E`
> **Owner:** ACI Software & Development
>   ( **A**ccountability · **C**ommunication · **I**nformation · Software & Development )
> **Upstream:** Hermes Agent by [Nous Research](https://nousresearch.com)
> (MIT-licensed — upstream attribution is preserved everywhere it was authored)

This guide is the **fastest honest path** to a working ACI muse
development environment. It covers the two runtimes that ship in this
repo and how they relate.

For deep-dive material:

- General product / feature docs → [`README.md`](README.md)
- Codebase orientation for AI assistants → [`AGENTS.md`](AGENTS.md) and
  [`CLAUDE.md`](CLAUDE.md)
- Android companion app → [`apps/android/README.md`](apps/android/README.md)
- Termux runtime → [`docs/termux/`](docs/termux/)
- Orchestration system → [`docs/orchestration/README.md`](docs/orchestration/README.md)

---

## 1. What's actually in this repo

ACI muse is **two runtimes plus a bridge**:

| # | Runtime | Status today | Where it lives |
|---|---|---|---|
| 1 | Python CLI + gateway (the main agent) | Stable, shipped | repo root, `agent/`, `gateway/`, `hermes_cli/`, `cli.py`, `run_agent.py` |
| 2 | Native Android companion (Kotlin + Compose) | **Alpha** — debug APK builds in CI, foreground service runs | [`apps/android/`](apps/android/) |
| 3 | Termux / ADB bridge between #1 and #2 | Manual scripts; no auto-pairing yet | [`scripts/hermes-termux-doctor.sh`](scripts/hermes-termux-doctor.sh), [`scripts/hermes-termux-service.sh`](scripts/hermes-termux-service.sh), [`scripts/hermes-mobile-workspace-init.sh`](scripts/hermes-mobile-workspace-init.sh) |

The Android app is a **thin native client**, not a CPython-in-APK
embedding. The intended on-device topology is:

```
Android app  ──(localhost HTTP)──►  muse gateway (running under Termux)  ──►  LLM provider
```

…with the gateway also reachable from a server / VPS if you don't want
to host it on the phone.

---

## 2. Desktop / cloud setup (Python CLI)

Tested on Linux, macOS, WSL2. For Windows-native and the universal install
one-liner, see [`README.md`](README.md#quick-install).

### 2a. Manual checkout (recommended for contributors)

```bash
git clone https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E
cd M.U.S.E

# uv handles Python version + venv creation in one step.
# If you don't have uv: curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv .venv --python 3.11
source .venv/bin/activate

# Dev install (lint, tests, debugger).
uv pip install -e ".[dev]"
```

### 2b. Sanity checks

```bash
ruff check .                  # lint — should be clean on main
scripts/run_tests.sh          # full test suite (hermetic env, 4 workers)
muse doctor                 # runtime / config / provider diagnostic
```

If `muse doctor` complains about a missing provider key, see
§5 — keys live in `~/.hermes/.env`, never in the repo.

### 2c. First conversation

```bash
muse                          # interactive CLI
muse model                  # pick a model (OpenRouter / NovitaAI / NIM / local / …)
muse setup                  # full setup wizard
```

---

## 3. Termux setup (phone / on-device)

Termux is the supported on-phone shell. The Android companion app
(§4) does **not** replace it — they cooperate.

### 3a. Termux packages

In a fresh Termux session:

```bash
pkg update
pkg install git python uv rust clang make pkg-config openssl libffi
termux-setup-storage          # one-time: grants ~/storage symlink
```

`rust` + `clang` + `openssl` + `libffi` are needed because several of
muse's transitive deps build from source on Android.

### 3b. Clone and install with the Termux extra

```bash
git clone https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E
cd M.U.S.E

uv venv .venv --python 3.11
source .venv/bin/activate

# IMPORTANT: use the [termux] extra, not [all]. The .[all] extra pulls
# voice deps (faster-whisper, sounddevice, numpy) that don't build on
# Termux. The [termux] extra carries only what works on-device.
uv pip install -e ".[termux]"
```

### 3c. Verify the runtime

```bash
bash scripts/hermes-termux-doctor.sh                # read-only environment scan
bash scripts/hermes-mobile-workspace-init.sh        # workspace + tooling probe
muse doctor
```

### 3d. Run as a background service (optional)

Termux has no systemd. `scripts/hermes-termux-service.sh` is a small
supervisor that uses a PID file, a wake lock, and `nohup`. Read the
script's header for environment variables — and never put secrets in
them.

```bash
bash scripts/hermes-termux-service.sh start
bash scripts/hermes-termux-service.sh status
bash scripts/hermes-termux-service.sh stop
```

For auto-start on device boot, install Termux:Boot and follow
[`docs/termux/hermes-termux-boot.md`](docs/termux/hermes-termux-boot.md).

---

## 4. Native Android companion app

The Android module lives under [`apps/android/`](apps/android/) and is
already wired up — it is **not** a placeholder.

### 4a. What's actually built

- `applicationId = "com.aci.hermes"`, namespace `com.aci.hermes`
- `minSdk = 26`, `targetSdk = 35`, `compileSdk = 35`
- Kotlin 2.1 + Jetpack Compose (Material 3)
- `HermesService` — local-only foreground service with a persistent
  notification, notification channel `hermes_orchestrator`, foreground
  service type `dataSync`
- `POST_NOTIFICATIONS`, `FOREGROUND_SERVICE`, and
  `FOREGROUND_SERVICE_DATA_SYNC` permissions declared
- Debug build APK assembled by CI on every PR touching `apps/android/`
  (see [`.github/workflows/android-build.yml`](.github/workflows/android-build.yml))

### 4b. Building locally

Prereqs: JDK 17, Android SDK with platform `android-35` and build-tools
`35.0.0`. (Android Studio installs these for you.)

```bash
cd apps/android
./gradlew assembleDebug
# APK lands at apps/android/app/build/outputs/apk/debug/app-debug.apk

adb install -r app/build/outputs/apk/debug/app-debug.apk
```

### 4c. Service intent contract

`HermesService` is `exported=false`, so ADB invocations need the debug
build's component name. The supported namespaced extras
(`hermes_workspace`, `hermes_mode`, `hermes_agent`, `hermes_debug`) are
currently **observational only** — they are logged to `logcat` for
wiring verification. See
[`apps/android/README.md`](apps/android/README.md#service-intent-contract)
for the full table and example commands.

### 4d. What is NOT done yet

- No embedded CPython — Android sandboxes can't ship a full POSIX
  toolchain. Use Termux for an on-phone gateway.
- No production release signing config (debug builds only by default).
- `usesCleartextTraffic="true"` for local-network testing — must be
  gated before a Play Store release.
- Push-from-gateway, skill picker UI, voice input: tracked in
  [`apps/android/README.md`](apps/android/README.md#whats-not-wired-up-yet).

---

## 5. Authentication and secrets

**Hard rules.** Read these before configuring anything.

1. All provider API keys (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`,
   `ANTHROPIC_API_KEY`, `NOVITA_API_KEY`, …) live in `~/.hermes/.env`
   on the host that runs the agent. They are loaded by the plugin
   layer; the agent core never sees raw key strings.
2. **Never commit a key.** `.gitignore` already covers `.env` and
   `~/.hermes/`, but `git status` before every push regardless.
3. **A ChatGPT subscription is not an OpenAI API key.** A Claude.ai
   subscription is not an Anthropic API key. The browser products and
   the API platforms have separate billing. If you need API access,
   create an API key on the provider's developer console.
4. **Codex CLI and Claude Code CLI authenticate independently** of
   anything in this repo. Run their own `login` / `auth` flows once;
   `scripts/hermes-mobile-workspace-init.sh` will not (and should not)
   try to do that for you.
5. `[`SECURITY.md`](SECURITY.md)` covers vulnerability reporting and
   the supply-chain hardening (exact-pinned deps, OSV scanner, etc.).

`.env.example` lists every variable muse recognizes, all commented
out. Copy it to `~/.hermes/.env` and uncomment what you need.

---

## 6. Day-to-day commands

Inside the interactive CLI or any gateway DM:

| Command | What it does |
|---|---|
| `/orchestrate <goal>` | Start an orchestrated job |
| `/orchestrator status` | List active jobs |
| `/orchestrator status <job-id>` | One job's task graph |
| `/reload-skills` | Re-scan skill files after editing |
| `/profiles` | List configured worker profiles |
| `/<skill-name>` | Load any skill into the session |
| `/new` or `/reset` | Start a fresh conversation |
| `/model [provider:model]` | Switch model mid-conversation |

Shell:

```bash
muse                         # interactive CLI
muse gateway               # start the messaging gateway
muse tools                 # configure enabled tools
muse config set            # set a single config value
muse doctor                # diagnose install / config
muse update                # update muse
```

---

## 7. ACI ownership context

This repository is owned and operated by **ACI Software & Development**.
muse is being adapted into ACI's orchestration foundation — the same
codebase will eventually carry:

- The ACI Agent Suite (structured agents with role + duty + validation).
- The ACI AOS Layer (intake → plan → delegate → execute → review).
- The ACI Supervisory Unit layer.
- The ACI Audit + Validation layer.
- The ACI Memory + Skills layer.
- The ACI Orchestration Bridge (Codex, Claude Code, Termux, GitHub,
  MCP).

See [`ACI_BASE44_IMPORT_HANDOFF.md`](docs/audits/ACI_BASE44_IMPORT_HANDOFF.md) for
the canonical scope description Base44 was given.

Upstream Nous Research authorship and the MIT license are preserved
intact — see [`LICENSE`](LICENSE) and the headers / docs that name
the original authors.

---

## 8. When something breaks

In order:

1. `muse doctor` — environment + config sanity check.
2. [`docs/orchestration/troubleshooting.md`](docs/orchestration/troubleshooting.md)
   — orchestration-specific failures.
3. `~/.hermes/jobs/<job-id>/ledger.jsonl` — orchestrator decision log
   for a single job.
4. `~/.hermes/logs/` — agent / gateway / Termux logs (depending on
   what's running).
5. GitHub issue with `muse doctor` output and a tar of the job
   folder attached (scrub anything that looks like a secret first).

For native Android issues, also attach:

- `adb logcat -s HermesService` (the service's own log tag).
- The Gradle output of the failing `./gradlew` invocation.
- Output of `bash scripts/hermes-mobile-workspace-init.sh --json`.

Welcome aboard.
