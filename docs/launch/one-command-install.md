# One-command install — every platform, plus the first-run flow

This is the canonical "install everything" page. Each one-liner below is
the supported entry point for its platform; the sections after it cover
what each install includes, the first-run flow (models → gateway → pair →
Observatory), and the smoke-test evidence the installer prints.

Repo: `A-C-I-SOFTWARE-AND-DEVELOPMENT/muse`. The CLI command installed
everywhere is `muse`.

---

## The one-liners

### Linux / macOS / WSL

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/main/scripts/install.sh)
```

With options (piped form):

```bash
curl -fsSL https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/main/scripts/install.sh | bash -s -- --skip-setup --bootstrap-models
```

Includes: uv-managed Python 3.11 + venv, the full `[all]` extras set
(hash-verified via `uv.lock` when possible), Node.js 22 + Playwright
Chromium for browser tools (skippable with `--skip-browser`), ripgrep +
ffmpeg (best-effort), config templates under `~/.hermes/`, the `muse`
launcher on PATH, the interactive setup wizard, and optional gateway
service install (systemd) when a messaging token is configured.

### Windows (PowerShell)

```powershell
iex (irm https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/main/scripts/install.ps1)
```

To pass flags, download first:

```powershell
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/main/scripts/install.ps1' -OutFile install.ps1
.\install.ps1 -SkipSetup -BootstrapModels
```

Includes: everything above plus portable Git (PortableGit, no admin
rights), portable Node.js, `HERMES_HOME=%LOCALAPPDATA%\hermes`, and a
stage protocol (`-Manifest` / `-Stage <name>` / `-Json`) that the desktop
GUI's onboarding wizard drives.

### Android / Termux

Same script as Linux — it detects Termux and switches to the tested
pip/venv path (installs the Android build toolchain, prebuilds the psutil
shim, uses the `[termux-all]` profile):

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/main/scripts/install.sh)
```

Browser/WhatsApp tooling is not installed by default on Termux; matrix
e2ee and local faster-whisper extras are excluded (upstream Android
wheel/toolchain blockers).

### Docker

Images are published to GHCR by
[`.github/workflows/docker-publish.yml`](../../.github/workflows/docker-publish.yml)
as `ghcr.io/a-c-i-software-and-development/muse` (per-commit SHA tags;
`:main` tracks the default branch, `:latest` tracks releases — each
guarded by its own promotion job). The supported run path is the repo's
[`docker-compose.yml`](../../docker-compose.yml):

```bash
git clone https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/musegit && cd muse
HERMES_UID=$(id -u) HERMES_GID=$(id -g) docker compose up -d
```

Data lives in `~/.hermes` on the host (mounted at `/opt/data`). The
compose file's security notes apply — the dashboard binds to loopback by
default; do not expose it on LAN without auth.

### Desktop app (Tauri)

Built and published by
[`.github/workflows/muse-desktop-release.yml`](../../.github/workflows/muse-desktop-release.yml):
a rolling **`muse-desktop-latest`** prerelease refreshes on every push to
`main` that touches `apps/desktop/`, and pushing a `muse-desktop-v*` tag
(or running the workflow by hand) cuts a permanent versioned release.
Download the installer for your OS from the repo's
[GitHub Releases](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/releases)
page. The desktop app's onboarding wizard drives `install.ps1`'s stage
protocol under the hood on Windows.

### Android APK (the muse cockpit app)

Built and published by
[`.github/workflows/android-release.yml`](../../.github/workflows/android-release.yml):

- Rolling: the **`android-latest`** prerelease keeps a stable asset name —
  `jarvis-prime-android.apk` — so the download URL never changes:
  `https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/releases/download/android-latest/jarvis-prime-android.apk`
- Versioned: `android-v*` tags (or the one-button workflow dispatch) cut
  permanent releases with `jarvis-prime-<version>.apk`.

> **Owner-gated (signing):** without the `ANDROID_KEYSTORE_*` repository
> secrets the workflow still publishes, but the APK is **debug-signed**
> (clearly marked in the release notes) — installable via sideload, not a
> Play-ready artifact. See
> [`android-release-signing.md`](android-release-signing.md) for the exact
> secret names and the full signing setup.

The app is local-only: it talks to **your own** cockpit gateway (default
`127.0.0.1:8765`) and holds no API keys.

---

## First-run flow

After any install, the path to a working cockpit is four steps. The
installers print these same hints at the end of a run.

### 1. Bootstrap model routing (optional)

```bash
muse models bootstrap --free-first --jarvis --no-pull
```

Local OSS models first; paid providers stay opt-in. `--no-pull` avoids
multi-GB downloads (pull a local model later, e.g.
`ollama pull deepseek-r1:8b`). The installers offer this for you:

| | bash | PowerShell |
|---|---|---|
| Run without prompting | `--bootstrap-models` | `-BootstrapModels` |
| Never run/offer | `--no-bootstrap-models` | `-NoBootstrapModels` |
| Default | prompt when a TTY is available, skip silently when non-interactive | prompt when interactive, skip with `-NonInteractive`/`-Json` |

(`--jarvis-launch` / `-JarvisLaunch` already runs the same bootstrap plus
`muse doctor --jarvis-launch`; the installers won't run it twice.)

### 2. Start the cockpit gateway

```bash
muse cockpit serve
```

This starts the loopback cockpit API on `127.0.0.1:8765` and prints the
pairing token and the browser cockpit URL. `muse cockpit token` reprints
the token (`--rotate` to rotate it). For messaging platforms
(Telegram/Discord/Slack/WhatsApp/...), the full gateway is `muse gateway`
/ `muse gateway install` (systemd service).

### 3. Pair your phone (or browser)

In the muse Android app's pairing screen, enter the base URL
(`http://<host>:8765`) and the token. Under the hood the app calls
`POST /v1/cockpit/pair/start` and `POST /v1/cockpit/pair/confirm`
(both unauthenticated bootstrap endpoints — confirm returns a fresh
per-device token once; see
[`docs/contracts/cockpit-wire-contract.md`](../contracts/cockpit-wire-contract.md)).
The browser cockpit pairs with the same base URL + token.

### 4. Open the cockpit & Observatory

Open `http://127.0.0.1:8765/cockpit/` — the bundled single-page browser
cockpit (it client-side-routes all `/cockpit/...` paths, so deep links
work). The interactive 3D **Neural Observatory** lives at
`http://127.0.0.1:8765/cockpit/observatory.html` (also linked from the
cockpit nav, and embedded by the desktop app's Observatory view and the
Android Observatory screen). It is fed by the bearer-gated
`/v1/observatory/snapshot` / `/v1/observatory/stream` endpoints.

**Observatory is opt-in (default OFF).** Enabling it creates the marker
file `${HERMES_HOME:-~/.hermes}/observatory/.enabled`. What it records,
honestly: per-turn routing decisions and knowledge-graph query
activations, appended to local JSONL files under `~/.hermes/observatory/`
(pruned to the newest 7 days) — nothing leaves your machine. Opt in via
the installer prompt, `--enable-observatory` / `-EnableObservatory`, or
simply `touch ~/.hermes/observatory/.enabled` (set `muse_OBSERVATORY=1`
for env-based enablement). Disable by deleting the marker.

---

## Smoke-test evidence (no-evidence-no-claim)

Both installers ship a smoke test that prints **actual HTTP responses**,
never bare "OK" strings:

```bash
# bash: as part of an install run, or standalone:
bash scripts/install.sh --smoke         # with the install
bash scripts/install.sh --smoke-only    # just the smoke test
```

```powershell
.\install.ps1 -Smoke        # with the install
.\install.ps1 -SmokeOnly    # just the smoke test
```

It also runs automatically at the end of an install when a cockpit API is
already reachable on `127.0.0.1:8765` (override the base URL with
`HERMES_COCKPIT_URL`). It probes:

1. `GET /v1/health` — unauthenticated liveness + version.
2. `GET /v1/cockpit/capabilities` — bearer-gated; uses the token at
   `~/.hermes/cockpit/token` when present.
3. `GET /v1/observatory/snapshot` — bearer-gated; reports a
   disabled/empty view until the Observatory is opted in.

Example output shape (status + first 400 bytes of each real response):

```
→ Smoke test — live responses from http://127.0.0.1:8765 (evidence, not claims):
  GET /v1/health -> HTTP 200
    {"ok": true, "service": "hermes-cockpit", "api_version": ..., "gateway_version": ..., "time": ...}
  GET /v1/cockpit/capabilities -> HTTP 200
    {...}
  GET /v1/observatory/snapshot -> HTTP 200
    {...}
```

When no token exists yet, the bearer-gated probes honestly print their
`HTTP 401` plus the response body, with a pointer to `muse cockpit token`.
When nothing is listening, the smoke test prints exactly how to start it
(`muse cockpit serve`) instead of pretending.

---

## What's owner-gated

- **Android release signing & Play submission** — requires the
  `ANDROID_KEYSTORE_*` repository secrets and a Play Console account; see
  [`android-release-signing.md`](android-release-signing.md).
- **Publishing releases** (desktop tags, `android-v*` tags, PyPI) —
  release cuts follow the owner-gate policy in
  [`CLAUDE.md`](../../CLAUDE.md) (`Yes, with authorization.`).

Everything else on this page is self-serve.
