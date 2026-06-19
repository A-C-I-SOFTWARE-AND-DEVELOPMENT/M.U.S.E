# muse — Audit Report (regenerated 2026-06-11)

**Companion to [`REMAINING_WORK_PLAN.md`](REMAINING_WORK_PLAN.md).** The
original drop's audit report never landed in git; this one is regenerated
from the build session that implemented the plan from spec (branch
`claude/remaining-work-plan-18cdzd`). Every claim below was produced by a
command run in that session; verdicts are GO / NO-GO / GO-WITH-CONDITIONS.

Environment: x86_64 Linux container, Python 3.11.15, full axiom deps
installable (z3, blake3, pynacl all present) — so both the proven path
*and* the degraded path were exercised here.

---

## Phase 0 — Foundation. **GO**

**Kernel (z3 present):**
```
$ cd axiom && python -m pytest tests/
66 passed, 1 warning in 3.47s
$ python smoke.py
[1] attested  unit=1b6eb6cab462…  checks=['intent:EARS', 'effects:vocab', 'refs:resolve-or-fail', 'contracts:z3']
[2] run(100C) = 212.0F
[3] forge: champion=v2 (1720), gate-failed=['cheat'] (rating 0)
[4] memory 1 tier=working  R=1.00
[5] ledger: 5 events, chain_valid=True
```

**Degraded mode (z3 import blocked via meta-path hook):**
```
verify ok: True | checks: ('intent:EARS', 'effects:vocab', 'refs:resolve-or-fail', 'contracts:degraded')
warnings: ('z3 unavailable — contracts checked syntactically, not proven',)
run(100C): 212.0
chain_valid: True
```
Malformed contracts still rejected; runtime postconditions still enforced
(`PostconditionViolation` raised on `result > 0` with `result=-1`).

**Bridge:** `status` → `available: true`; record → audit →
`chain_valid: true`; one flipped payload byte →
`chain_valid: false, first_bad_seq: 0`, CLI exit 1;
`muse_AXIOM_GATES=0` → `chain_valid: null`, no file I/O.

**Regression:** `tests/test_jarvis_prime_gates.py tests/test_decision_ledger.py`
→ `73 passed`.

## Phase 1 — Risk-adaptive orchestrator. **GO**

- `create_job` stores `metadata["risk"]` (band/score/profile/strict flag);
  classification chained as `job.classified`.
- Untrusted write-mode job → HIGH; `run_job_gates` on a fully
  self-attested packet → `owner_approval: needs_owner_approval`
  (`HIGH-risk job awaits exact phrase: 'Yes, with authorization.'`).
- LOW job runs exactly `["build", "test"]`; MED is evidence-strict
  (self-attested packet FAILs).
- Tampered chain flips `release_gate` to FAIL:
  `axiom event chain failed verification (first_bad_seq=0)`; inert mode passes.
- `muse_AXIOM_GATES: "0"` exported in `tests.yml`,
  `jarvis-prime-unit.yml`, `orchestration-tests.yml`.
- Proof: `tests/test_job_risk_gating.py` (7 tests) + full suite (below).

## Phase 2 — Flywheel everywhere. **GO**

Record sites: gateway `_handle_message` (`owner.prompt`),
`model_tools.handle_function_call` (`agent.action`, success/failure +
lesson), skill invocation (`skill.used`), `model_router.route`
(`model.routed`). Simulated session digest:
```
"total": 5, "by_kind": {"owner.prompt": 1, "agent.action": 2, "skill.used": 1, "model.routed": 1},
"by_outcome": {"none": 1, "success": 3, "failure": 1}, "pending_improvements": 1
```
Forced failure auto-queued in the same session (exit criterion's test
proxy; the "one normal day of use" reading is owner-side).
`/flywheel [digest|pending]` registered + handled; owner brief gained a
caller-supplied `flywheel_digest` section; `flywheel install-cron`
registers the nightly digest+audit and weekly `.plans/` filing jobs.

## Phase 3 — UE5 live smoke. **GO-WITH-CONDITIONS (owner hardware)**

Buildable parts shipped: `research_fabric/ue5.py` (Remote Control client,
owner-gated spawn, chain events; `ue5_bridge.py` → verbatim shim),
`skills/creative/ue5-render/SKILL.md`, 9 tests (request shapes,
gating — `Popen` unreachable without `muse_UE5_ALLOW_SPAWN=1`, spawn with
grant, shim identity). **UNVERIFIED on this box:** the four live editor
commands and a real offscreen render — no UE5 editor exists in this
container. Queued as `5687fb9f8c1c` (owner-hardware).

## Phase 4 — Surfacing. **GO (two parked items)**

- `GET /v1/cockpit/axiom` — live test: empty home → `chain_valid: null`;
  after events → `true` + tail; tampered byte → `false`;
  `pending_improvements` reflects the queue. Wire contract regenerated
  (113 routes), freeze test green.
- `docs/axiom-integration.md` + README row.
- Rename artifacts: `docs/jarvis-prime-app-launch-readiness-audit.md:117`
  fixed. Residual grep hits: `CLAUDE.md:12` (**parked** — standing order)
  and the plan file's own quotation of the grep pattern (self-referential).
- `sync-aci-to-base44.yml`: the heredoc body escaped the `run:` block
  scalar at column 1 — the YAML did **not** parse (contrary to the drop's
  claim); fixed by indenting to block level, `yaml.safe_load` green.
  Full-mirror semantics documented in the header; a live green run on
  GitHub is owner-side.

## Phase 5 — Hardening ladder. **GO**

- `scripts/self-audit.sh` → **PASS, exit 0**: compileall OK; collect-only
  `29240 tests collected`; tracked YAML/JSON parse sweep OK; secrets grep
  OK (redaction code/fixtures excluded as scanner allowlist). Wired as a
  step in `jarvis-self-audit-live.yml`.
- Triage: repo-wide actionable TODO count is **1** (the plan's "40" did
  not survive into this tree) — queued with the 3 env-dependent failing
  test files, the CLAUDE.md artifact, and the UE5 smoke into
  `improvement_queue.jsonl`; filed to
  `.plans/2026-06-11-flywheel-improvements.md`.
- New test files: `test_axiom_bridge.py` (10), `test_flywheel.py` (9),
  `test_ue5_module.py` (9) — green locally; CI is the PR's gate.

## Full-suite verdict

```
$ muse_AXIOM_GATES=0 python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/e2e
14 failed, 29045 passed, 179 skipped in 0:12:52
```
All 14 failures cluster in 3 files (`tests/gateway/test_google_chat.py`,
`tests/gateway/test_voice_command.py`, `tests/tools/test_ssh_environment.py`)
and reproduce **identically on the pristine base commit `a9a5907`**
(failure-set diff: empty) — pre-existing, environment-dependent, queued
as test-debt. **Zero regressions introduced.**

Focused suites on the final tree: `148 passed` (bridge, flywheel, ue5,
job risk gating, gates, decision ledger, job controller, cockpit panel,
contract freeze). Session chain: `chain_valid: true`.

## Parked items (one-line unblocks)

| Item | Unblock |
|---|---|
| CLAUDE.md:12 rename artifact | Reply `Yes, with authorization.` to touch CLAUDE.md |
| UE5 live smoke + render | Run the 4 CLI commands + `render` on a UE5 machine |
| Android cockpit panel UI | Build/emulator pass consuming `/v1/cockpit/axiom` |
| sync workflow green run | Trigger `workflow_dispatch` on GitHub after merge |
| Merge to main | Owner authorization (draft PR open) |
