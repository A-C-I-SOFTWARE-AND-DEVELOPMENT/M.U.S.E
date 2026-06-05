# Hermes 10/10 — End-to-End Runbook

> **Owner:** Sprint 14. **Companion to:**
> [`10_10_RELEASE_CHECKLIST.md`](10_10_RELEASE_CHECKLIST.md) and the runnable
> gate `hermes doctor --10-10`. This runbook walks the
> Voice/Android cockpit → gateway → orchestrator → worker patch → validation →
> decision verdict → GitHub PR → phone approval loop, plus the fast smoke.

## 0. Fast smoke (every change)

```bash
scripts/hermes-10-10-smoke.sh
```

Runs ruff, the 10/10 readiness doctor, and a launch-critical test slice. Exit 0
= safe-to-ship gates green. Use this as the pre-merge gate.

## 1. Prerequisites

- Python ≥ 3.11, `uv` installed; `uv sync` (or the installer in
  [`scripts/install.sh`](../../scripts/install.sh)).
- Secrets live in `~/.hermes/.env` (never in code). The agent never sees raw
  keys; plugins read them.
- For the cockpit/Android leg: a paired device (see §4).

## 2. Readiness doctor

```bash
hermes doctor --10-10            # human-readable
hermes doctor --10-10 --json     # machine-readable (CI / scripts)
```

Hard gates must show ✓; warnings are the documented 10/10 punch list. The doctor
reads the real repo, so it reflects current wiring — not a hard-coded verdict.

## 3. Backend loop (no device required)

This exercises the parts of the loop that run headless.

1. **Start an orchestrated job** (dry-run safe):
   ```bash
   hermes orchestrate "audit the repo and propose a small fix"
   hermes orchestrator status <job-id>
   ```
   Workers run in **isolated git worktrees** and emit real `git diff` artifacts
   (`~/.hermes/jobs/<job-id>/...`). No worker runs in the repo root.
2. **Validation gates** run against the candidate patch (structure, secrets,
   tests, protected paths). A secret in the diff → **refuse**; a failed gate →
   no publish.
3. **Decision verdict at the publish boundary**: `github_publisher` computes a
   `DecisionVerdict`. With `approve=False` (default) it produces a **dry-run PR
   descriptor** — no branch, no push. The verdict id is recorded in the PR body.
4. **Replay**: kill and restart; `JobStore.snapshot(job_id)` rebuilds job state
   from the event log (`hermes_cli/job_replay.py`).

## 4. Cockpit + phone leg

1. **Start the cockpit gateway** (loopback by default):
   ```bash
   scripts/dev/live-cockpit.sh        # or: hermes gateway ...
   ```
   It binds `127.0.0.1`; external binding requires an explicit opt-in and logs a
   warning.
2. **Pair the device**: the Android app performs the pairing handshake
   (`gateway/pairing.py` — rate-limited, lockout, code TTL). The gateway stores a
   **hashed** per-device token; the device keeps the raw token in
   EncryptedSharedPreferences. Revoking a device invalidates its token
   immediately (`device_pairing.verify_device_token`).
3. **Drive a job from the phone**, watch the **live event timeline** (SSE /
   cursor replay), and handle the **approval inbox**. An `ask` verdict enqueues a
   cockpit approval (`gateway/cockpit/notify.py`); a high-risk action requires
   the exact owner phrase `Yes, with authorization.`
4. **Voice (today)**: push-to-talk on the phone does STT locally and posts a
   transcript to `/v1/cockpit/voice/intake`; `/decide` confirms. *Server-side
   audio duplex (audio in / synthesized audio out over the gateway) is a
   documented punch-list item.*

## 5. Remote bridge (optional, opt-in)

Off by default. When enabled, a dispatch is wrapped in a **signed envelope**
(HMAC + single-use nonce + expiry, `bridge_envelope.py`), placed in a durable
queue, and pulled by an allowlisted workstation that runs only allowlisted
commands (default `claude`). Bad signature / expired / replayed nonce →
rejected. Never an arbitrary remote shell.

## 6. E2E matrix

Run the scenarios in
[`10_10_RELEASE_CHECKLIST.md`](10_10_RELEASE_CHECKLIST.md#e2e-test-matrix) on a
real device for a phase sign-off (happy path, missing CLI, validation failure,
secret-in-diff, protected path, phone offline, gateway restart, duplicate
approval, revoked device, bad bridge signature).

## 7. Troubleshooting

- `hermes doctor` (general) and `hermes doctor --jarvis-launch` for environment
  and launch-path issues.
- `hermes doctor --10-10` for release-gate status.
- Per-job state + decision trail: `~/.hermes/jobs/<job-id>/ledger.jsonl`.
- Flaky CI: [`docs/testing/known-flaky-tests.md`](../testing/known-flaky-tests.md).
- Symptom-to-fix table:
  [`docs/troubleshooting/`](../troubleshooting/).
