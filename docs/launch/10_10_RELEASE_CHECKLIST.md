# Hermes 10/10 — Release Checklist

> **Owner:** Sprint 14 (Release readiness). **Generated against:** current `main`.
> **Runnable gate:** `hermes doctor --10-10` (and `--json`) +
> `scripts/hermes-10-10-smoke.sh`. This document is the human-readable mirror of
> that gate; the doctor reads the actual repo, so it is the source of truth and
> stays honest as the remaining items land.

## How to run the gate

```bash
scripts/hermes-10-10-smoke.sh          # ruff + doctor + fast test slice
hermes doctor --10-10                  # the release-readiness gates
hermes doctor --10-10 --json | jq .    # machine-readable
```

Exit code is **0 only when every hard safety/correctness gate passes.** The
remaining 10/10 loop-closure items are reported as **warnings** (they do not
block a safe alpha ship, but they are the punch list for a full 10/10).

## Safe-to-ship hard gates — all green ✅

These are verified by `hermes doctor --10-10` and must stay green:

| Gate | Evidence |
|---|---|
| Core package imports (`hermes_cli`, `run_agent`) | doctor: package import |
| Unified `DecisionVerdict` API present | `hermes_cli/decision_engine.py` |
| Owner gate — exact phrase enforced | `hermes_cli/jarvis_prime/owner_auth.py` (`AUTHORIZATION_PHRASE`) |
| Secret redaction wired everywhere | `hermes_cli/secrets_policy.py` `redact`, `gateway/cockpit/redaction.py` |
| GitHub publish is dry-run by default | `hermes_cli/github_publisher.py` (`approve=False`) |
| Remote bridge uses signed envelopes (HMAC + nonce + expiry) | `remote_bridge.py` → `bridge_envelope.py`, durable `SeenNonceStore` |
| Remote bridge command allowlist (no arbitrary shell) | `remote_bridge.py` (`command_allowlist`, default `("claude",)`) |
| Cockpit bearer auth is constant-time | `gateway/cockpit/auth.py` (`hmac.compare_digest`) |
| Cockpit binds loopback by default | `gateway/cockpit/server.py` |
| Dependencies exact-pinned (`==`) + `uv.lock` committed | `pyproject.toml`, `uv.lock` |

Already-wired-and-strong (verified, surfaced as passing punch-list items):
durable **worker leases** (`orchestrator_parallel.py` + `worker_lease_store.py`),
**approval notifications** queue + SSE (`gateway/cockpit/notify.py`),
**per-device pairing** with revocable hashed tokens (`auth.py` → `device_pairing`),
**event-sourced job replay** (`job_replay.py`).

## 10/10 loop-closure punch list — remaining ⚠️

Reported as warnings by the doctor. These do **not** block a safe alpha, but
close the gap to a true 10/10. (The orchestrator/cockpit lane is under active
parallel development — these are tracked, not abandoned.)

| Item | Status | What's left | Where |
|---|---|---|---|
| **Decision verdict at dispatch/merge** | publish-only | Call `merge_decision_inputs` at job dispatch, worker exec, and patch merge — not just the publish boundary. The cockpit can't render *one* verdict for non-publish mutations until this lands. **#1 gap.** | `hermes_cli/orchestrator.py`, `orchestrator_parallel.py` |
| **Per-job budget hard-stop** | computed, not enforced | Act on `budget_decision().should_stop` / `hard_exceeded` before continuing a job (today it is surfaced to the cockpit only). | `hermes_cli/orchestrator*.py`, `job_cost.py` |
| **Server-side voice audio duplex** | transcript-only | Add `/v1/cockpit/voice/transcribe` (audio-in) + a response-audio route; today the phone does STT/TTS and posts a transcript. | `gateway/cockpit/server.py`, `handlers.py` |
| **GitHub repo allowlist** | absent | Add an explicit repo allowlist in the publisher (live publish is currently constrained only by owner-gating the action). | `hermes_cli/github_publisher.py` |

## E2E test matrix (Sprint 14)

Run on a real device + gateway for a full sign-off. Each row is a scenario the
loop must handle:

| Scenario | Expected result |
|---|---|
| Happy path: prompt → validated patch → dry-run PR | PR descriptor (or live PR if opted-in) visible on the cockpit |
| Worker CLI missing | Proposal fallback or a clear, non-crashing failure |
| Validation fails | No publish; failure visible with the gate that failed |
| Secret in diff | `refuse` verdict; no publish |
| Protected-path change | `ask`/`refuse` per policy |
| Phone offline during approval | Pending approval reconciles on reconnect (cursor replay) |
| Gateway restart mid-job | Job state rebuilds from the event log (`job_replay`) |
| Duplicate approval submit | Idempotent (decided-once) |
| Revoked device approval | Refused (token no longer authenticates) |
| Remote bridge: bad signature / expired / replayed nonce | Rejected by `bridge_envelope.verify` |

## Known limitations (ship-honest)

- **CI test job is intermittently flaky under xdist** — see
  `docs/testing/known-flaky-tests.md`. Python flakes are mitigated (real-sleep
  `side_effect`); the **Android ViewModel `resetMain` flake** is a known,
  documented issue (leaked `viewModelScope` coroutine) and is an **Android-only,
  owner-gated follow-up** — it does not gate the Python/backend ship. Re-run the
  single job if it trips; it is not a correctness failure.
- The four punch-list items above are documented, not silently missing.

## Launch phases

- **Alpha (now):** loopback gateway, dry-run publish default, signed bridge
  behind a feature flag, no always-on wake word. All hard gates green.
- **Beta:** decision verdict at dispatch + budget hard-stop wired; live-publish
  repo allowlist; optional push providers.
- **Stable:** voice audio duplex; full E2E matrix green on a real device; the
  Android flake resolved.

## Sign-off

- [ ] `scripts/hermes-10-10-smoke.sh` exits 0
- [ ] `hermes doctor --10-10` shows 0 hard failures
- [ ] Security review (`docs/security/10_10_SECURITY_REVIEW.md`) has no unresolved blocker
- [ ] E2E matrix run on a real device for the targeted phase
- [ ] Release notes list the punch-list items + the Android flake honestly
