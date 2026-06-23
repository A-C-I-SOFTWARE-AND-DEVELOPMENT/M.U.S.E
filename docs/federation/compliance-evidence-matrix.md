# muse Compliance Evidence Matrix

> Human-readable mirror of
> [`hermes_cli/jarvis_prime/federation/compliance_matrix.py`](../../hermes_cli/jarvis_prime/federation/compliance_matrix.py)
> (`CONTROL_MAPPINGS`). A test asserts every `control_id` below stays in sync
> with the module — the same discipline as the Constitution sync test.

muse supplies the **evidence**, not the certificate: the mappings show
structural alignment, but conformity assessment and certification require an
external auditor (no harmonized EU AI Act standard had been published as of
mid-2026 — see the Volume VI caveats).

Generate a live, content-addressed evidence package at any time:

```bash
python -m hermes_cli.jarvis_prime federation compliance export --framework all --out evidence.json
```

The package embeds the verbatim `verify_chain()` diagnostics, owner/quorum
grant counts, the ledger record-kind histogram, the constitution version, and
the sovereignty index — all computed from the live ledger, then sealed with
`package_sha256` so peers can cross-attest the export itself.

## EU AI Act (high-risk obligations)

| Control | Obligation | muse mechanism | Evidence kinds |
|---|---|---|---|
| **Art9** | Risk management system | Eight verification gates + capability wall (RC0–RC4) + behavioral self-audit | `gate_summary`, `capability_attestation`, `audit_result` |
| **Art11** | Technical documentation (Annex IV) | Constitution + work packets + spec docs as living documentation that exists *before* market placement | `constitution_amendment_decision`, `work_packet` |
| **Art12** | Record-keeping / logging "integrated into the core design" | Hash-chained tamper-evident `GuardrailLedger` with `verify_chain()` — native, not bolted on | `ledger_chain_diagnostics` |
| **Art14** | Human oversight (understand, override, stop) | Owner-approval gate (exact phrase, nonce-bound) + quorum authorization + kill switch + rollback gate | `owner_authorization_grant`, `quorum_grant`, `rollback` |
| **Art15** | Accuracy, robustness, cybersecurity | Executable verifiers (held-out cases) + secret scans + capability attestations | `test_result`, `secret_scan`, `capability_attestation` |

## SOC 2 (common criteria)

| Control | Criterion | muse mechanism | Evidence kinds |
|---|---|---|---|
| **CC4.1** | Monitoring of controls | Constitution self-audit + sovereignty index + ledger kind histogram | `sovereignty_report`, `audit_result` |
| **CC6.1** | Logical access controls | Owner-gated action set + contributor trust ladder (B0–B3) + quorum policies | `owner_authorization_grant`, `contributor_band_change` |
| **CC7.2** | Anomaly detection / immutable audit trail | Append-only hash-chained ledger; `verify_chain()` detects mutation, reorder, truncation — "cannot be changed or deleted, even by super-admins" | `ledger_chain_diagnostics`, `federation_divergence` |
| **CC8.1** | Change management | Amendment engine (non-amendable core) + owner-gated proposals + rollback gate | `constitution_amendment_decision`, `rollback` |

## ISO 27001 (Annex A)

| Control | Control name | muse mechanism | Evidence kinds |
|---|---|---|---|
| **A.5.35** | Independent review of information security | Cross-node attestation + Merkle-anchored leaderboards (trustless third-party verification) | `federation_peer_attestation`, `forge_leaderboard_anchor` |
| **A.8.15** | Logging | `GuardrailLedger`: every gate decision, grant, duel, and amendment is appended | `ledger_chain_diagnostics` |
| **A.8.16** | Monitoring activities | Sovereignty index + divergence detection + intake decisions | `sovereignty_report`, `federation_divergence`, `forge_intake_decision` |
| **A.8.32** | Change management | Amendment engine + owner approval + quorum authorization | `constitution_amendment_decision`, `quorum_grant` |
