# AXIOM Integration — the bridge, the chain, and degraded mode

The AXIOM verification kernel is vendored at [`axiom/`](../axiom/) (its own
package, tests, and pyproject). The Hermes runtime talks to it through one
module: [`hermes_cli/jarvis_prime/axiom_bridge.py`](../hermes_cli/jarvis_prime/axiom_bridge.py).
Nothing else in the runtime imports the kernel directly.

## What the bridge does

| Capability | API | CLI |
|---|---|---|
| Hash-chained event ledger | `get_bridge().record_event(kind, payload)` | — |
| Verify history | `get_bridge().audit()` → `chain_valid: true/false/null` | `python -m hermes_cli.jarvis_prime.axiom_bridge audit` (exit 1 iff invalid) |
| Inspect recent events | `get_bridge().tail(n)` | `… axiom_bridge tail -n 10` |
| Availability / degradation | `get_bridge().status()` | `… axiom_bridge status` |
| Risk classification | `get_bridge().classify_change(...)` → `{risk, score, gates, reasons}` | — |

The chain lives at `$HERMES_HOME/axiom/chain.jsonl` — one JSON record per
line, each carrying `prev` (the previous record's sha256) and `hash`
(sha256 over the canonical record body). `audit()` recomputes every hash
and link; one flipped byte yields `chain_valid: false` with the breaking
`first_bad_seq`. The format is a structural subset of the kernel's own
ledger so events can be mirrored into a full axiom `Ledger` later.

**Who writes to the chain today**

- `jarvis_prime/gates.py` — every `run_gate_summary` records a
  `gate.summary` event, and the **release gates FAIL when the chain fails
  verification** ("ship" means "history verifies").
- `hermes_cli/decision_ledger.py` — every written decision records
  `decision.written`.
- `hermes_cli/job_controller.py` — every created job records
  `job.classified` with its risk band.
- `research_fabric/ue5.py` — `ue5.ping` / `ue5.console` / `ue5.py` /
  `ue5.render` (python payloads are fingerprinted, never stored).

## Risk-adaptive orchestration

Jobs are blast-radius-classified at creation
(`job.metadata["risk"]`); `run_job_gates(job, packet)` then runs **exactly**
the classified profile:

| Band | Gate profile | Evidence |
|---|---|---|
| LOW | build, test | packet-level |
| MED | planning, build, review, test, security, rollback | **strict** (evidence bundle required) |
| HIGH | all eight, including owner_approval | **strict**, and the job itself awaits the exact phrase `Yes, with authorization.` |

Effects and default-behavior changes dominate the score (constants are
kept in parity with `axiom/axiom/orchestrator/gates.py`): a write-mode job
in an untrusted repo is HIGH on its own.

## Environment variables

| Variable | Effect |
|---|---|
| `MUSE_AXIOM_GATES=0` | Bridge inert: no chain reads/writes, `chain_valid: null`, release chain-check skipped. Exported in CI unit-test workflows for hermeticity. |
| `HERMES_HOME` | Relocates the chain (and all runtime state). The bridge singleton re-resolves it on every `get_bridge()`. |
| `MUSE_UE5_ALLOW_SPAWN=1` | Owner gate for `ue5.launch_offscreen_render` — without it the command is built but never spawned. |
| `AXIOM_ALLOW_UNVERIFIED_CONTRACTS=1` | Owner gate for the kernel's **fail-closed** contract policy. Default (unset): when z3 is unavailable a unit that declares contracts is *rejected* (`contracts:unverified`), never attested unproven. Set it only on platforms that genuinely cannot run z3 (e.g. Termux/aarch64) to re-open the degraded attest-with-warning path. |

## Degraded mode (no z3) — fail-closed

`z3-solver` ships no aarch64 wheels, so on Termux the kernel cannot
prove contracts. Because AXIOM never trusts what it cannot verify
(invariant **I2 — verify before attest**), the kernel **fails closed**:

- `axiom.core.contracts.check_contracts` validates every clause against
  the restricted grammar but makes **no SAT/consistency/vacuity claims**;
  the report carries `degraded=True`.
- **By default, a unit that declares contracts is rejected** with
  `contracts:unverified` — an unproven contract earns no attestation.
  A unit with *no* contracts has nothing to prove and still attests
  (labelled `contracts:degraded`).
- The legacy attest-with-warning behaviour is preserved only as an
  explicit, owner-gated opt-in: set
  `AXIOM_ALLOW_UNVERIFIED_CONTRACTS=1`. Then degraded units attest with
  the warning `z3 unavailable — contracts checked syntactically, not
  proven` and the honest `contracts:degraded` label.
- Runtime postcondition enforcement (`eval_concrete`) works fully in
  every mode — a unit that lies at runtime still yields no result, even
  when opted in.
- The bridge chain is stdlib-only and unaffected.

Install the kernel deps with the marker-guarded extra (recommended — it
keeps you on the proven path):

```bash
pip install -e '.[axiom]'   # skips z3 automatically on aarch64
```

## Effect vocabulary

`classify_change(effects=...)` accepts free-form effect strings; the
kernel's canonical vocabulary (see `axiom/axiom/core/effects.py`) uses
dotted names like `fs.write`, `net.fetch`, `process.spawn`. Two or more
effects saturate the effect term — declare what the change *can* touch,
not what it intends.

## Flywheel (companion module)

[`hermes_cli/jarvis_prime/flywheel.py`](../hermes_cli/jarvis_prime/flywheel.py)
is the bridge's working-log sibling: `record(kind, payload, outcome,
lesson)` appends to `$HERMES_HOME/flywheel/events.jsonl`, failures
auto-queue into `improvement_queue.jsonl`, and `digest()` / `pending()`
(`python -m hermes_cli.jarvis_prime.flywheel digest|pending`) surface
them. No hash chain — promote durable facts to the bridge.
