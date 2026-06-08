# MUSE Verification Gates

This document defines review gates for MUSE operating-layer work. It is documentation only and does not change runtime behavior.

## Gate Philosophy

MUSE should move quickly without becoming reckless. Each gate exists to keep local-first work scoped, reviewable, and reversible.

A gate can pass, fail, or require owner approval. When a gate is skipped, the handoff must state why and name the remaining risk.

## Planning Gate

Purpose: confirm the mission is clear before execution.

Minimum checks:

- repo, branch, and working tree state are known;
- goal is specific;
- allowed files and disallowed files are listed;
- non-goals are explicit;
- acceptance criteria are defined;
- owner gates are identified.

Fail this gate when the request is too broad, emotionally satisfying but strategically weak, or missing critical context.

## Build Gate

Purpose: ensure implementation stays inside scope.

Minimum checks:

- builder packet exists;
- allowed files are respected;
- protected files are not edited without approval;
- runtime code is not touched in docs-only stages;
- Claude Code and Codex are not editing the same branch simultaneously;
- no secrets are added.

## Review Gate

Purpose: catch weak logic, regression risk, and scope creep.

Minimum checks:

- diff is reviewable;
- findings are severity-ranked;
- blocking issues are separated from improvements;
- contrarian review identifies the strongest objection;
- review output cites files, lines, commands, or concrete reasoning.

## Test Gate

Purpose: verify behavior locally when tools are available.

Minimum checks:

- requested verification commands are run;
- targeted tests or scripts pass;
- `git diff --check` passes for edited files;
- skipped tests are explained;
- unverified risk is named.

## Security Gate

Purpose: prevent credential, privacy, supply-chain, and unsafe action mistakes.

Minimum checks:

- no secrets are committed;
- `.env` and credential files are not edited unless explicitly approved;
- dependency changes are reviewed separately;
- network calls are not added to local-only scripts;
- public posting, publishing, deployment, and spending require owner approval.

## Release Gate

Purpose: ensure the work is ready for PR or release handoff.

Minimum checks:

- changed files are listed;
- commits are scoped;
- verification results are summarized;
- non-goals are stated;
- remaining risks are stated;
- rollback plan exists;
- PR body is ready when requested.

## Owner Approval Gate

Purpose: preserve Jeremiah's control over high-impact decisions.

Owner approval is required for:

- merges;
- force-pushes;
- deploys;
- publishing;
- deleting recovered sources;
- modifying secrets;
- changing default always-active agents;
- broad AOS registry mutation;
- spending money or changing external services.

If owner approval is missing, stop before the action and present the risk and recommended next step.

## Rollback Gate

Purpose: make changes reversible.

Minimum checks:

- rollback path is stated;
- commit hash or file list is available;
- risky runtime changes have a revert or feature-flag strategy;
- docs-only changes can be reverted cleanly;
- follow-up owner review is identified when rollback is uncertain.

## Gate Summary Template

```text
GATE SUMMARY
Planning gate:
Build gate:
Review gate:
Test gate:
Security gate:
Release gate:
Owner approval gate:
Rollback gate:
Result:
Remaining risk:
```

## Evidence-bound (strict) gates

The gates above are also implemented in code
(`hermes_cli/jarvis_prime/gates.py`). By default they run in **legacy mode**:
they read fields from a work packet, which is fine for *planning* but is
self-attestable — a packet that simply asserts `diff_reviewed=true` and
`tests_run=[…]` would otherwise pass.

**Strict evidence mode** closes that gap. In strict mode the six observation
gates (build, review, test, security, release, rollback, owner approval) ignore
self-attested packet fields entirely and pass **only** when the matching
captured artifact is present in a
[`GuardrailEvidenceBundle`](security/verifiable-guardrails.md):

| Gate | Required evidence |
|---|---|
| Build | `git_diff` artifact; observed changed files in scope, no protected files |
| Review | `review` artifact with an explicit non-blocking verdict |
| Test | an executed `test_result` that passed (planned commands never count) |
| Security | `secret_scan` artifact over the changed files, clean |
| Release | release fields **plus** a real `git_diff` + `rollback` artifact |
| Rollback | `rollback` artifact judged operationally plausible |
| Owner approval | a challenge-bound `owner_authorization_grant` artifact |

The evidence bundle is bound to the packet's `packet_id`, so a bundle collected
for one packet cannot be replayed against another. Strict mode is enabled on the
runtime and doctor paths:

```python
from hermes_cli.jarvis_prime.gates import run_strict_gate_summary
summary = run_strict_gate_summary(packet.to_gate_packet(), evidence_bundle)
```

The legacy signature (`run_gate_summary(packet)`) is unchanged for backward
compatibility. See
[`docs/security/verifiable-guardrails.md`](security/verifiable-guardrails.md)
for the evidence model, the tamper-evident ledger, and the
`hermes guardrails` CLI.

## Challenge-bound owner authorization

The static phrase `Yes, with authorization.` remains, but a replayed phrase
carries no binding to *which* action was approved. Strict owner approval
therefore requires a **nonce-bound challenge**:

```text
$ hermes guardrails authorize production_deploy --subject "release v2"
required_phrase: Yes, with authorization. Code: 728193

$ hermes guardrails authorize-response <challenge-id> "Yes, with authorization. Code: 728193"
authorized: true   # a grant artifact is appended to the ledger
```

A successful response mints an `owner_authorization_grant` evidence artifact;
the bare phrase alone never satisfies a strict owner gate.
