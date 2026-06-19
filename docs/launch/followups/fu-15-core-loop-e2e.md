# FU-15 — Recorded core-loop E2E (submit → run → validate → owner-gated publish/approve)

**Status:** in-review
**Risk class:** additive (a new test only; zero runtime/default-path changes)
**Branch:** `claude/fu-15-core-loop-e2e` (cut from `main` @ `e1ac6eed`)
**Owner of this snapshot:** the FU-15 builder agent (sole writer)
**Owner-gate required to merge?** no — strictly additive test; may auto-merge on green CI.

## Intent

This is the proof-bar centerpiece for "a proven tool, not a demo." It is one
**recorded, end-to-end** test that boots the *real* cockpit HTTP server
(`gateway.cockpit.server.serve` on a loopback ephemeral port, tmp `HERMES_HOME`,
known bearer token) and drives the muse core loop over the wire with `urllib`,
asserting the **owner gates** and the **decision/audit ledger** at every hop.
It exercises the genuine handlers, the genuine owner-phrase gate, the genuine
orchestrator worker, and the genuine audit trail — it does **not** mock the
system under test. The only things stubbed are the *external world*: the GitHub
PAT is made absent (so publish lands on the honest `github_not_configured`
path) and nothing touches the network (the dispatched worker is offline by
construction). Before this, the cockpit jobs/approvals/autonomy surfaces were
each covered in isolation; nothing proved the **whole loop** end to end across
all the gates in a single run.

## The loop the test proves (hop by hop, all over real HTTP)

0. **Liveness + auth wall.** `GET /v1/health` (unauthenticated) is `200 ok`;
   every other cockpit route refuses a missing bearer token (`401`).
1. **Submit.** `POST /v1/cockpit/orchestrate` records a real orchestrator job
   (status `queued`); `POST /v1/cockpit/jobs` enqueues a real JobQueue entry.
   Both appear in the aggregated `GET /v1/cockpit/jobs`.
2. **Run / validate (real worker, real status progression).**
   `POST /v1/cockpit/jobs/{id}/run` dispatches the orchestrator job to the
   built-in **offline, non-destructive** `hermes-local-planner` lane
   (deterministic repo navigation — no edits, no shell, no network;
   `requires_approval = False`). The job advances `queued → completed` through
   *real* statuses (asserted on both the run response and a follow-up job GET),
   and the run returns the *real* five-step worker ledger trail (`worker_dispatch`
   + `worker_result` present). On the same job, an **execute** lane
   (`codex-execute`) WITHOUT the phrase is refused over the wire (`403`, hint
   carries the exact owner phrase) — the gate that protects irreversible /
   agentic actions.
3. **Owner gate on autonomy (FU-12).** Raising autonomy to a privileged level
   (`owner_high_autonomy_coding`) WITHOUT the phrase → `403`
   `{authorization_required: true}` **and the floor stays `assisted`** (the
   escalation did not take effect); WITH `"Yes, with authorization."` → `200`.
   De-escalation (`read_only`) needs no phrase → `200`.
4. **Publish gate.** `POST /v1/cockpit/jobs/{id}/publish` against a JobQueue job
   carrying a git workspace: WITHOUT the phrase → `200`
   `{status: "approval_required", authorization_required: true}` (no GitHub
   call); WITH the phrase → the owner gate **passes** and, with no PAT in the
   hermetic env, hits the honest `403 github_not_configured` path. The gate
   passed; no real PR is opened — that is the proven, correct behavior. The test
   does **not** require a real GitHub PR.
5. **Approvals (FU-14 path).** A seeded pending proposal surfaces as an
   `ApprovalCard` (`PENDING`); `POST /v1/cockpit/approvals/{id}` is refused
   (`403`) without the exact phrase and **decided** (`200`, `status: "approve"`)
   with it.
6. **Audit / decision ledger.** `GET /v1/cockpit/autonomy/decisions` reflects
   the `autonomy_change` event, and the decided proposal is no longer `PENDING`
   in the approvals list — the audit trail records the loop.

## What is covered vs. what needs a live worker (stated honestly)

- **Covered hermetically (this E2E):** the full submit → run → validate →
  owner-gated publish → owner-gated approve loop, every owner gate (autonomy
  escalation, execute lane, publish, proposal approval), the real status
  progression of a job driven by a real worker, and the audit/decision ledger
  reflecting the loop — all over the real cockpit HTTP server.
- **The "run" hop uses the offline planner deliberately.** The repo-mutating /
  external execute lanes (`codex-execute`, `claude-execute`, Aider, etc.) shell
  out to paid CLIs and the network, so running one is **not** hermetic. The E2E
  therefore drives the run hop with `hermes-local-planner` (genuine deterministic
  navigation that reaches `completed` with real localized artifacts) and proves
  the execute-lane **gate** (`403` without the phrase) rather than executing a
  paid lane. Driving a real execute lane to a merged PR is what a **live,
  owner-present** run would add on top of this; it is intentionally out of scope
  for the hermetic test.
- **Publish stops at the gate by design.** With no PAT, the with-phrase publish
  proves the gate passed and then honestly reports `github_not_configured`
  instead of opening a PR. Opening a real PR requires a live PAT and is not part
  of the hermetic proof.

## Owned (writable) files

- `tests/e2e/test_core_loop_depth_e2e.py` — the recorded core-loop E2E (new).
- `docs/launch/followups/fu-15-core-loop-e2e.md` — this snapshot (new).

> Both files are new and disjoint from every other in-flight task — no shared
> writable file, no collision.

## Constraints honored

- **Hermetic:** loopback-only server, tmp `HERMES_HOME` + isolated orchestrator
  home, no network, no paid API, no real GitHub (PAT env deleted), no shell-out
  to external coding tools (the offline planner is used).
- **No hangs:** the server is shut down in fixture teardown; every HTTP call is
  bounded by a `timeout`. The dispatched planner is rooted at a tiny scratch git
  repo (the test makes it the process cwd), so the navigation completes in
  sub-second time — well within the HTTP timeout. (Rooting at the full hermes
  checkout took ~5 minutes and would exceed the timeout; the tiny-repo cwd keeps
  the worker genuine and fast.)
- **Asserts real behavior, not mocks of the SUT:** only the external world is
  stubbed (PAT absent, network unreachable via the offline worker). Every gate,
  status, and ledger assertion runs against the live handlers.
- **Additive:** no runtime code touched; default code paths byte-for-byte
  unchanged.

## Validation (recorded)

- `uv run ruff check tests/e2e/test_core_loop_depth_e2e.py` → **All checks passed!**
- `uv run ty check tests/e2e/test_core_loop_depth_e2e.py` → **1 diagnostic**, the
  exempt `unresolved-import: pytest` false-positive (identical to the baseline on
  `tests/e2e/test_cockpit_jobs_approvals_smoke.py`; `pytest` is provided by
  `uv run --with pytest` at run time). No new diagnostics vs base.
- `python -m pytest tests/e2e/test_core_loop_depth_e2e.py -o addopts="" -q`
  (under `uv run --with pytest`, pytest 9.0.3) → **recorded passing run:**

```
.                                                                        [100%]
1 passed in 1.27s
```

  Verbose form (for the record):

```
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/user/hermes-agent
configfile: pyproject.toml
plugins: anyio-4.12.1
collected 1 item

tests/e2e/test_core_loop_depth_e2e.py::test_core_loop_submit_run_validate_owner_gated_publish_and_approve PASSED [100%]

============================== 1 passed in 1.30s ===============================
```

- Cross-interference check: run alongside the reference suites
  (`tests/e2e/test_cockpit_jobs_approvals_smoke.py`,
  `tests/gateway/test_cockpit_autonomy.py`) → **14 passed** (no shared-state
  interference; the new test is fully isolated via tmp `HERMES_HOME` + cwd).

## Residual / follow-on

- A **live** end-to-end (real execute lane → real PR) is the natural next layer
  on top of this hermetic proof; it requires an owner-present run with a real
  PAT and paid CLI and is deliberately not part of the no-network test.
- The run hop asserts the worker trail contains `worker_dispatch` +
  `worker_result`; it does not assert specific localized file names (those depend
  on the navigator's ranking and would make the test a brittle change-detector).
