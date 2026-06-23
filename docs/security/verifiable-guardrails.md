# Verifiable Guardrails

muse ships strong guardrail *concepts* — owner gates, verification
gates, memory approval, emergency stop, worker/branch leases, launch-doctor
checks. The **verifiable guardrail subsystem** turns those documented intentions
into evidence-bound, tamper-evident, testable controls: a gate passes only when
backed by a captured artifact, and every guardrail decision is appended to a
hash-chained ledger that detects tampering.

> The whole point: **a gate must not pass because a packet says
> `diff_reviewed=true` or `tests_run=[planned command]`.** It passes only when a
> real artifact — an observed git diff, an executed test run, a clean secret
> scan, a reviewer note, a rollback plan, a challenge-bound owner grant — proves
> it.

Everything here is **stdlib-only**. No new required dependency is introduced.

## The pieces

| Module | Responsibility |
|---|---|
| `hermes_cli/jarvis_prime/guardrail_evidence.py` | Evidence artifacts, evidence bundle, and the hash-chained `GuardrailLedger`. |
| `hermes_cli/jarvis_prime/guardrail_collectors.py` | Collectors that observe reality (git diff, test runs, secret scan, review, rollback). |
| `hermes_cli/jarvis_prime/gates.py` | Strict, evidence-bound gate evaluation (`run_strict_gate_summary`). |
| `hermes_cli/jarvis_prime/owner_auth.py` | Nonce-bound owner challenge/response. |
| `hermes_cli/guardrails_cli.py` | The `muse guardrails` command group (top-level so `--help` never eagerly imports `jarvis_prime`). |
| `hermes_cli/jarvis_prime/launch_doctor.py` | Proves the guardrails are *operational*, not just importable. |

## What is cryptographically verifiable

- **Artifact content addressing.** Every `EvidenceArtifact` carries
  `payload_sha256 = sha256(canonical_json(payload))`. Any change to the payload
  changes the digest; `artifact.verify_payload()` re-checks it.
- **Work-packet identity.** A `CodingWorkPacket.packet_id` is a SHA-256 over the
  packet's stable fields. An evidence bundle is bound to that `packet_id`, so a
  bundle collected for one packet cannot be replayed against another.
- **Tamper-evident decision ledger.** `GuardrailLedger` is append-only JSONL
  where each record stores `previous_record_hash` and
  `record_hash = sha256(canonical_json(record_without_record_hash))`. Any edit,
  reorder, deletion, or truncation breaks the chain. `verify_chain()` reports the
  first break (`broken_at`, `reason`) and **never silently repairs** the ledger.

The baseline integrity guarantee is SHA-256 hash chaining. Ed25519 signing is
used *opportunistically* only if `cryptography` happens to be importable (it
ships transitively via `PyJWT[crypto]`); it is never required.

## What is operationally verifiable

Collectors observe the real world and refuse to fabricate:

- **Git diff** — read-only git plumbing only. Captures branch, HEAD, changed
  files, out-of-scope files (vs the packet's allowed globs), protected files
  touched, working-tree cleanliness, and `git diff --check`. Missing git
  degrades to `git_available=false`, never an exception.
- **Test execution** — runs nothing unless the caller passes `run=True` *and*
  the command passes a strict allowlist (`pytest`, `python -m compileall`,
  `ruff`, `mypy`, `git`, …). Shell metacharacters and commands like `rm`/`curl`
  are refused. A *planned* command is recorded as an explicit non-pass — it can
  never satisfy the test gate.
- **Secret scan** — scans only the supplied/changed files (never your home
  directory), reusing the canonical memory-gate patterns. Findings are stored as
  **redacted snippets only**; a raw secret never reaches an artifact or the
  ledger.
- **Review** — requires non-empty text and an explicit verdict
  (`approve` / `request_changes` / `blocked` / `needs_owner`); RC2+ approvals
  require at least one contrarian/risk note.
- **Rollback** — validates that a plan is operationally plausible (branch +
  changed files, or commit hash + revert instructions). It never executes a
  rollback.

## What is **not** guaranteed

This subsystem is defense-in-depth, not a silver bullet. It is **not** a
replacement for:

- OS-level sandboxing or process isolation;
- hardware-backed keys / a real HSM (the ledger is hash-chained, not
  hardware-signed);
- GitHub branch protection or required-reviews enforcement;
- human review and judgment.

A determined local attacker with write access to `$HERMES_HOME` can delete the
ledger file — but they **cannot** edit history undetected: `verify_chain()` will
report the break. Treat a broken chain as a security event, not a glitch.

## Strict vs legacy packet mode

`run_gate_summary(packet)` keeps its original, packet-level behavior (used by
planning flows and existing tests). Strict, evidence-bound evaluation is opt-in:

```python
from hermes_cli.jarvis_prime.gates import run_strict_gate_summary
summary = run_strict_gate_summary(packet.to_gate_packet(), evidence_bundle)
```

In strict mode a missing bundle is treated as an *empty* bundle, so a
self-attested packet fails by construction. `CodingWorkPacket.to_gate_packet()`
no longer fabricates observed-evidence fields; planned scope/verification are
exposed under explicit `planned_*` keys that strict gates never read as
evidence. Required evidence scales with risk class
(`CodingWorkPacket.to_evidence_requirements()`):

- **RC2+** → `git_diff`, `secret_scan`, `test_result` (or accepted skip),
  `review`, `rollback`.
- **RC3+** → additionally an `owner_authorization_grant`.
- **RC4** → blocked: refusal/review only, no executable plan.

## CLI

```text
muse guardrails status                       # ledger head, chain validity, leases, proposed-memory count
muse guardrails doctor [--json]              # operational proof suite (exit 1 on any failure)
muse guardrails verify-ledger [--json]       # validate the hash chain
muse guardrails collect --packet p.json [--run-tests]
muse guardrails authorize <action> --subject <s>
muse guardrails authorize-response <challenge-id> "Yes, with authorization. Code: NNNNNN"
```

`muse guardrails doctor` proves the guardrails actually work: the ledger
writes and verifies, strict gates reject a self-attested packet then accept real
synthetic evidence, the owner challenge rejects a wrong/bare phrase and accepts
the correct nonce, the secret scanner catches and redacts a synthetic token, and
a *proposed* memory item is held for approval and excluded from live recall.

All commands run with **no network and no credentials**.

## Runtime & launch integration

- `JarvisPrime.gate(packet, evidence_bundle=…)` runs strict gates whenever a
  real bundle is supplied and journals the gate summary to the ledger.
- `JarvisPrime.delegate(...)` includes `packet_id`, `required_evidence`, the
  ledger head hash, and any open owner-challenge ids in the delegation envelope.
- `JarvisPrime.stop(...)` appends a tamper-evident `emergency_stop` record (in
  addition to session memory); a ledger failure surfaces as a `ledger_warning`
  in the result rather than crashing the stop.
- `muse doctor --jarvis-launch` (the launch doctor) gains hard checks:
  `guardrail_ledger_writable`, `guardrail_ledger_verifies`,
  `strict_gate_rejects_self_attestation`, `owner_challenge_nonce_enforced`,
  `secret_scan_operational`, `emergency_stop_journaled`, `packet_id_stable`.

## Ledger location

`$HERMES_HOME/jarvis_prime/guardrail_ledger.jsonl` (default `~/.hermes/...`),
written atomically with best-effort `0600` permissions.
