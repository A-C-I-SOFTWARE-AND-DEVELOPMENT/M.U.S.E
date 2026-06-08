# Full-App Build-Out, Validation & End-to-End Smoke — 2026-06-03

**Branch:** `claude/full-app-build-validation-QPDd2` (PR #211)
**Scope (owner-directed):** build out and validate **every** surface of the
app, smoke-test it like a client from beginning to end, drive the open PRs to
done, and verify the surfaces *synergize* (shared memory + shared learning) —
"no degrading, only enhancements."

This is a build/validation pass on an already-mature, CI-green codebase
(~2,077 Python files, ~1,256 test files, plus a React web cockpit and a Kotlin
Android app). "Build out" here means: stand up the real toolchains, prove every
surface compiles/tests/runs end-to-end, finish the in-flight avatar/voice work,
and lock the synergy in with a reproducible test.

## Result summary

| Surface | How validated | Result |
|---|---|---|
| Python core + CLI | `uv pip install -e .[all,dev]`; full `pytest` | **26,800 passed**; entrypoint `hermes --help` OK |
| Cockpit HTTP server | live boot + `urllib` client; `tests/gateway/test_cockpit_*` | health/auth/stream OK; **103 cockpit tests pass** |
| MUSE runtime | streamed turn (perceive→classify→route→gate) | real `thinking→tone→detail→body→done` stream |
| Cross-surface memory | fresh-instance recollect round-trip | **shared brain confirmed** |
| Web cockpit (React/Vite) | `npm ci` + `npm run build` + `eslint` | build green (`web_dist` produced); 5 safe lint fixes |
| Android cockpit (Kotlin) | Android SDK install + `assembleDebug` + unit tests | **APK built (35 MB); 433 unit tests, 0 failures** |
| e2e client journey | new `tests/e2e/test_full_app_smoke.py` | **green locally and in CI** |

## Environment brought up in this container

The container shipped `uv`, `node 22`, `JDK 21`, `docker`, `rustc`. To exercise
**all** functions (not just the curated `[all]` extra) the following were added:

- `uv pip install -e ".[all,dev]"` then `".[messaging,slack,matrix,voice]"` —
  so Discord / Telegram / Slack / Matrix / voice code paths are real, not stubbed.
- System `ripgrep` (present) and `openssh-client` (installed) for the file/SSH tools.
- **Android SDK** — cmdline-tools + `platforms;android-35` + `build-tools;35.0.0`
  + `platform-tools`, licenses accepted (matches AGP 8.7.3 / Gradle 8.11.1 /
  compileSdk 35 / JDK 21). See `scripts/setup-android-sdk.sh`.
- Git **commit signing disabled** in this container (`commit.gpgsign=false`) —
  the sandbox's signing key made fixture commits fail with
  `fatal: failed to write commit object`. Environment-only; no repo change.

## Test triage — every failure root-caused

The first full run reported `92 failed, 12 errors`. **None were code
regressions** (this was unmodified `main`, which is green in CI). They were
container-environment gaps, fixed or classified:

| Bucket | Count | Root cause | Disposition |
|---|---|---|---|
| `test_worktree*`, `test_context_references` | ~34 | git commit-signing fixture failure | **Fixed** (signing off) |
| `test_discord_*`, `test_telegram_*` | ~44 | messaging deps not installed | **Fixed** (installed extras) |
| `test_ssh_environment` | 7 | no ssh client | **Fixed** (installed openssh) |
| `test_gateway_service` (systemd) | 8 | runs as **root** + **no systemd-as-PID-1** | **Environment-only** — see below |

### The 8 systemd tests (deliberately not "fixed")

`generate_systemd_unit(system=True)` refuses to run **as root** (a real safety
guard: "Refusing to install the gateway system service as root"), and
`systemd_restart()` preflight requires **systemd booted as PID 1**. CI runs as
non-root `runner` on a systemd VM, so both pass there. In this rootless,
systemd-less container they cannot pass without weakening the safety code or
masking the tests — neither of which is acceptable under "no degrading." They
are confirmed green in CI; CI remains authoritative for them.

## PR dispositions

- **#182 (deps CVE cleanup)** — **Closed as superseded.** `main` already carries
  every pin it adds (`anthropic==0.87.0`, `starlette==1.0.0` in `pyproject.toml`,
  `tools/lazy_deps.py`, and `uv.lock`); only comment wording differed (hence the
  `dirty` conflict). PyNaCl remains upstream-blocked by `discord.py[voice]==2.7.1`.
- **#210 (alive avatar + stop-go voice)** — **Integrated** into this branch.
  Found feature-complete on its branch (34 files / +2,420 LOC): persistent
  breathing avatar parented in `JarvisShell`, `VoiceLoopService` wired in DI
  (on-device STT/TTS + real agent dispatch behind mic consent), thinking-beat
  pacing, and `ControlViewModel` now reflecting **real** cockpit health/workers.
  Builds clean with the SDK; 433 Android unit tests pass.
- **#211 (this branch)** — consolidation of the validation work + #210.

## Synergy / learning verification ("everything learns from one another")

Confirmed wired and exercised end-to-end, not just importable:

- **One brain, many surfaces:** the cockpit chat responder
  (`gateway/cockpit/agent.py`) drives the **real** `JarvisPrime` runtime —
  perceives, **recollects memory**, classifies mode, routes, surfaces owner
  gates, grounds in the owner profile + project refs
  (`gateway/cockpit/grounding.py`), runs the anti-hallucination epistemic audit,
  and **learns from explicit owner cues** (`_maybe_remember → jp.config.memory`).
- **Shared persistent memory** across surfaces proven by a round-trip: a durable
  fact written by one `JarvisPrime` instance is recollected by a fresh one over
  the same `HERMES_HOME` (codified in `tests/e2e/test_full_app_smoke.py`).
- **Brain-switching** is classification-driven (`_brain_hint`): builder/code →
  coder model, strategy/critic/low-confidence → reasoning model, escalation →
  cloud-first; otherwise free-first local→cloud (`gateway/cockpit/generate.py`).
- **Owner gates respected:** owner-gated actions are surfaced, never executed,
  in the chat path; SIA stays proposal-only.

## Deliverables / enhancements added this pass

- `tests/e2e/test_full_app_smoke.py` — permanent, CI-run client-journey smoke
  (cockpit stream + cross-surface memory). Green locally and in CI.
- 5 safe pre-existing web eslint errors fixed (i18n useless-escape ×4, unused
  prop ×1). Web `eslint` is **not** a CI gate; the build (which **is** gated)
  was already green.
- This report.

## Honest gaps / follow-ups (non-blocking)

- Web `eslint` has ~17 remaining **pre-existing, non-CI-gated** advisory errors
  (mostly React-Compiler "setState in effect" patterns). Not touched — rewriting
  working UI effects with no browser-interaction harness here risks regressions,
  which "no degrading" forbids. Tracked for a dedicated, separately-verified pass.
- The 8 systemd service tests require a systemd, non-root host (CI) to run.
