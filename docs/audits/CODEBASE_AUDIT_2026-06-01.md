# Hermes Agent — Full Codebase Audit

**Date:** 2026-06-01
**Base commit:** `084c132` (`main` tip at audit time)
**Auditor:** Claude Code (codebase-audit-blockers lane)
**Scope:** entire repository — what is built, what is left, every blocker.

> **Why this audit exists.** The repo's previous launch-status docs
> (`docs/launch/LAUNCH_STATUS.md`, "🔴 RED — 52%") were written on
> 2026-05-26 against PR #131 / base `bc97e43`. `main` is now **211 commits
> past `bc97e43`**, and the integration those docs describe as pending has
> substantially landed. This document re-establishes ground truth against
> the *current* tree. See `docs/launch/LAUNCH_STATUS_CURRENT.md` for the
> live readiness rollup.

---

## 1. Scale

| Metric | Value |
|---|---|
| Python source files | 2,065 |
| Python LOC (approx.) | 952,000 |
| Markdown docs | 1,884 |
| Test files (`tests/`) | ~1,298 |
| Android Kotlin source files | 153 |
| Android Kotlin test files | 61 |
| Package version | `0.14.1+aci.1` |
| Python requirement | `>=3.11` |
| CI workflows | 18 (incl. `launch-gate.yml` aggregator) |
| Open PRs at audit time | 1 (#182 — dependency/CVE cleanup) |

## 2. Verified-green signals (run during this audit)

| Check | Command | Result |
|---|---|---|
| Lint (blocking) | `ruff check .` | ✅ All checks passed |
| Windows footguns | `python scripts/check-windows-footguns.py --all` | ✅ 638 files clean |
| Lockfile | `uv lock --check` | ✅ 218 packages resolved |
| Launch-critical tests | `pytest` (owner_auth, gates, workpacket, jarvis_prime) | ✅ 234 passed |
| Core module syntax | AST parse of `run_agent.py`, `cli.py`, `model_tools.py`, `toolsets.py` | ✅ clean |
| Full Python suite | `pytest -m "not integration"` after `pip install -e ".[all,dev]"` | _recorded in LAUNCH_STATUS_CURRENT.md_ |

## 3. What is built and healthy

### Core agent & tooling
`run_agent.py` (4.1K LOC), `cli.py` (14.7K LOC), `model_tools.py`,
`toolsets.py`, and the `agent/` package form a complete agent loop with tool
orchestration. The 58 `NotImplementedError` occurrences are **legitimate** —
Windows signal-handler guards (`gateway/run.py`, `cron/jobs.py`), abstract
base-class methods (`gateway/platforms/base.py`, `tools/environments/base.py`),
and provider-not-configured guards (`agent/tts_provider.py`,
`agent/web_search_provider.py`). None hide unfinished features.

### Messaging gateway
`gateway/run.py` (18.3K LOC) + `gateway/platforms/` ship real adapters for
Telegram, Discord, Slack, WhatsApp, Signal, Email, Home Assistant, Teams,
Matrix, Mattermost, Feishu, WeCom, DingTalk, Weixin, SMS, BlueBubbles, QQ, and
Yuanbao.

### Worker execution engine (`hermes_cli/workers/`)
A real `WorkerAdapter` ABC drives every worker through the same five-step shape
(`detect → prepare_prompt → run → collect → score`). Two layers, both
first-class:
- **Handoff workers** (Aider, Goose, Codex, Claude Code) — write a worker-tuned
  `prompt.md` and return the invocation; they never spawn the tool or edit the
  repo, so they run **ungated** and are verifiable even without the binary.
- **Live-execute workers** — actually run the tool, correctly gated behind
  `execute=True` / `allow_execute=True` and the runtime owner-gate.

The gating is **deliberate safety**, not a stub hiding incomplete work.

### Orchestration (`hermes_cli/orchestrator*.py` + `gateway/cockpit/`)
Job graph, decision ledger (`decision_ledger.py`, `orchestrator_ledger.py`),
parallel runner (`orchestrator_parallel.py`), events, and replay
(`orchestrator_replay.py`, wired to `/orchestrator replay`) are all present.

### MUSE runtime (`hermes_cli/jarvis_prime/`)
A real Python package: `owner_auth.py`, `gates.py`, `modes.py`, `router.py`,
`work_packet.py`, `memory.py`, `reasoning.py`, `research.py`, `persona.py`, and
more. The owner-gate model (`OWNER_GATED_ACTIONS` frozenset,
`AUTHORIZATION_PHRASE = "Yes, with authorization."`) is enforced literally.
**234 launch-critical tests pass.**

### Android app (`apps/android/`)
153 Kotlin source files + 61 test files. Rebranded to "MUSE"
(`app_name`, splash, themes, colors all migrated). Screens present: splash,
onboarding, home, tasks, **chat** (real `JarvisChatScreen` + ViewModel +
`HttpJarvisChatGateway` + `RoutingJarvisChatGateway` + `MockJarvisChatGateway`),
approvals, memory, audit, capability, control, voice, live, avatar, diagnostics.
Owner-auth, emergency-stop, and redactor surfaces are in place.

### AOS Enterprise Council
`skills/aos-enterprise-council/` plus the root `AOS_*.md` files are **markdown
agent definitions and registries — data by design**, not runtime code. This is
expected and correct.

## 4. What is left (residual gaps — none are silent stubs)

| ID | Gap | Severity | Notes |
|---|---|---|---|
| G1 | Stale launch docs misrepresent readiness | High (clarity) | `LAUNCH_STATUS.md` etc. reference dead PR #131 / `bc97e43` |
| G2 | `PlaceholderScreen.kt` still present | Low | Confirm no live route still binds it |
| G3 | Android test depth below roadmap target | Medium | 61 test files; roadmap wants ViewModel ≥80% + Compose smoke + instrumented E2E + gated emulator CI job |
| G4 | Minor product TODOs | Low | See table below — none launch-blocking |
| G5 | Android W4 voice incomplete by design | Low | Screens exist; `RECORD_AUDIO` intentionally undeclared until voice-enable flow |

### Minor product TODOs (G4)
| File:line | Item |
|---|---|
| `hermes_cli/skills_hub.py:1122` | ClawHub publishing not yet supported |
| `hermes_cli/orchestrator.py:801` | History-mining CLI is a placeholder surface |
| `plugins/platforms/google_chat/adapter.py:3332` | Google Chat Card v2 buttons unsupported |
| `agent/gemini_cloudcode_adapter.py:81` | Gemini multimodal part dropped (logged) |
| `gateway/platforms/feishu.py:712` | Feishu @-mention user_id is a placeholder lookup |
| `hermes_cli/remote_bridge.py:115` | One bridge transport raises `TransportNotImplementedError` |
| `skills/productivity/linear/scripts/linear_api.py:232` | Linear label/assignee name→id lookup omitted (v1) |

## 5. Blockers to verify/close before launch

- **B6 — Expanded permission/privacy posture (owner-accepted risk,
  2026-06-01).** Commit `b8df5c78` ("Sentient MUSE avatar: living body,
  device control, voice, OSS catalog", #170) added four capabilities that the
  app's `docs/jarvis-prime-app-permission-risk-register.md` originally forbade:
  - `JarvisAccessibilityService` / `BIND_ACCESSIBILITY_SERVICE` (device/app
    automation),
  - `JarvisOverlayService` / `SYSTEM_ALERT_WINDOW` (system overlay),
  - `QUERY_ALL_PACKAGES`,
  - always-on `VoiceLoopService` ("MUSE is listening", wake-listener) +
    `RECORD_AUDIO` + `FOREGROUND_SERVICE_MICROPHONE`.

  These back **real shipped features**. They are a Play Store policy minefield
  (accessibility-for-automation, query-all-packages, overlay, always-on mic)
  and a reversal of the originally documented safety model. **The owner reviewed
  this finding on 2026-06-01 and elected to ship as-is, accepting the Play-policy
  and privacy risk** (recommendation against it was logged). The permission
  risk-register has been reconciled to reflect the shipped reality. Action
  still advisable before public store submission (not gating per owner): runtime
  consent for each capability, Play Console accessibility/`QUERY_ALL_PACKAGES`
  declarations, and a privacy-policy disclosure.

- **B1 — Ground truth.** The only authoritative launch status was 211 commits
  stale. → Closed by this audit + `LAUNCH_STATUS_CURRENT.md`.
- **B2 — Full Python suite needs the real install.** From a bare interpreter
  ~592 collection errors appear from missing optional deps (yaml, botocore, mcp,
  tiktoken, ptyprocess, discord/PyNaCl). After `pip install -e ".[all,dev]"`
  they resolve. All 177 `skip`/`xfail` markers are legitimate environment guards
  (Unix-only, optional dep, live-only) — not product gaps.
- **B3 — LSP e2e** (`tests/agent/lsp/test_client_e2e.py`): **RESOLVED — not a
  real failure.** The "6 failing" only occurs under a stray `pytest` whose venv
  lacks `pytest-asyncio` (the marker is then ignored and the coroutines are
  never awaited). Under the project env (`uv run --extra all --extra dev
  pytest`), **all 6 pass in 2.27s**. The test spawns an in-process mock LSP
  server — no `pyright`/`gopls` binary required. `pytest-asyncio==1.3.0` is
  already pinned in the `dev` extra. The historical "baseline failure" label
  was this same interpreter artifact.
- **B4 — Android build** (`assembleDebug` / `testDebugUnitTest` / `lint`):
  unrunnable in this container (no Android SDK). Must be confirmed via
  `android-build.yml` on a fresh CI run; permissions must match the `bc97e43`
  baseline (no new `<uses-permission>`).
- **B5 — `launch-gate.yml` aggregate** must be green and the owner-gate
  audit-hatch (AUTHORIZATION_PHRASE / OwnerAuth present) must stay satisfied
  before any owner-gated merge or deploy.

## 6. Owner-gate posture

The owner-gate mechanism is an **asset, not a blocker**. `OWNER_GATED_ACTIONS`,
`AUTHORIZATION_PHRASE`, `OwnerAuth`, and emergency-stop are preserved verbatim.
Owner-gated steps (merge to `main`, deploy, package publish, app-store
submission, credential change) are performed only on explicit owner
authorization through the existing gate — the gate code itself is not modified.

## 7. Bottom line

The codebase is **substantially built and healthy** — core loop, gateway,
worker engine, orchestration, MUSE runtime, and the Android cockpit are
all real and largely complete. There are **no large unfinished subsystems
masquerading as done**; the residuals are documentation drift (G1, now fixed),
Android test depth (G3), and a short list of minor edge TODOs (G4). The launch
path is dominated by *verification on CI* (B4/B5), not by missing
functionality.
