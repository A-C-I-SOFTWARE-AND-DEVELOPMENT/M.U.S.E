# M.U.S.E Workflow Schemas

Standard schemas and playbooks for bounded work in M.U.S.E. Every schema here is
backed by real code so the docs and the runtime agree on field names.

## Work packet

A work packet is the bounded descriptor for a single unit of work. It is
data-only — constructing one performs no IO and executes nothing. Source:
[`hermes_cli/jarvis_prime/work_packet.py`](../../hermes_cli/jarvis_prime/work_packet.py).

Required fields (`REQUIRED_FIELDS`): `mission`, `repo_root`, `branch`,
`risk_class`, `acceptance_criteria`, `rollback_plan`.

```json
{
  "mission": "Add docs/architecture component registry",
  "repo_root": "/home/user/M.U.S.E",
  "branch": "claude/quirky-goodall-9mqubo",
  "risk_class": "RC1",
  "allowed_files": ["docs/architecture/**", "hermes_cli/jarvis_prime/component_registry.py", "tests/hermes_cli/test_component_registry.py"],
  "protected_files": ["hermes_cli/jarvis_prime/owner_auth.py", "hermes_cli/jarvis_prime/gates.py"],
  "non_goals": ["wiring cloud/Web3 infra", "merging to main"],
  "acceptance_criteria": ["registry loads + test passes", "ruff/ty clean", "secret scan clean"],
  "owner_gated_actions": [],
  "owner_authorization_phrase": "Yes, with authorization.",
  "rollback_plan": "revert the single docs commit",
  "confidence": 0.9
}
```

Risk classes (`VALID_RISK_CLASSES`): `RC0`, `RC1`, `RC2`, `RC3`, `RC4`.
`WorkPacket.validate()` returns structured findings instead of raising, so a
caller can show problems to the owner rather than crash. The
`owner_authorization_phrase` always defaults to the canonical
`owner_auth.AUTHORIZATION_PHRASE`.

To turn a plain-English request into a packet without executing anything, use the
`/jarvis-packetize` skill.

## Remote worker manifest + status

The remote worker bridge dispatches a job manifest to a daemon, which runs an
allowlisted command and writes structured artifacts back. Source:
[`hermes_cli/remote_bridge.py`](../../hermes_cli/remote_bridge.py)
(`JobManifest`, `JobState`); transport config template at
[`templates/remote/windows-worker-config.example.yaml`](../../templates/remote/windows-worker-config.example.yaml).

**Inputs (manifest):** the phase prompt (`input.md`), staged attachment files, the
allowlisted command, the target repo root, the device id, and the approval state.

**Outputs (artifacts written back to the shared workspace):**

| Artifact | Contents |
|---|---|
| `output.md` | structured summary block |
| `patch.diff` | the unified diff produced |
| `changed-files.txt` | files touched |
| `validation-output.txt` | command / test output |
| `status.json` | terminal state + metadata |

**Phase state machine:** `todo → ready → in_progress → validating → done`.

**Hardening invariants** (the daemon refuses otherwise): schema-valid manifest,
command on the allowlist, approval present, device id matches, path inside a
configured repo root. Every tool call is appended to `ledger.jsonl` with
`kind=tool_call`. The bridge invents no new approval surface — HIGH-risk events
escalate to the normal surfaces (cockpit Approvals, `/orchestrator status`,
gateway DMs).

## Owner-approval examples

Owner-gated actions never execute on their own. The canonical action set is the
frozenset `OWNER_GATED_ACTIONS` in
[`hermes_cli/jarvis_prime/owner_auth.py`](../../hermes_cli/jarvis_prime/owner_auth.py):
`spend_money`, `post_publicly`, `create_third_party_account`, `oauth_change`,
`credential_change`, `production_deploy`, `dns_change`, `force_push`,
`package_publish`, `app_store_submission`, `delete_recovered_sources`,
`modify_secrets`, `change_default_active_agents`, `registry_mutation`,
`regulated_claim`, `grant_autonomy_charter`.

**Static phrase (RC2-and-below gates).** The owner must reply with the exact
string — approximations do not authorize:

```
Yes, with authorization.
```

**Nonce-bound challenge (strict evidence / RC3+).** The bare phrase is
insufficient; the owner must echo a one-time code so the grant is bound to a
specific action and time, and fails closed on expiry:

```
$ muse guardrails authorize production_deploy --subject "release v2"
required_phrase: Yes, with authorization. Code: 728193

$ muse guardrails authorize-response <challenge-id> "Yes, with authorization. Code: 728193"
authorized: true   # a content-addressed grant artifact is appended to the ledger
```

A successful challenge yields an `OwnerAuthorizationGrant` that emits an evidence
artifact into the decision ledger, satisfying the Owner Approval gate.

## Failure-mode playbooks

| Symptom | Likely cause | First moves |
|---|---|---|
| **Frozen job** — phase stuck in `in_progress` | worker crashed mid-run, or a long allowlisted command | check `~/.hermes/jobs/<job-id>/ledger.jsonl` for the last `tool_call`; inspect `status.json`; re-dispatch the phase (state returns to `ready`); the JobStore rebuilds from the event log on restart |
| **Auth mismatch** — daemon refuses the manifest | device id or repo root mismatch, or missing approval | confirm the device id in the worker config matches the manifest; confirm the path is under a configured repo root; re-issue approval; never widen the allowlist to force it through |
| **Tunnel loss** — bridge can't reach the worker | network/tunnel down (Tailscale/SSH) | `JobState` transitions to `disconnected`; artifacts already written remain valid; reconnect and re-poll; do not re-run a completed phase |
| **Worker crash** — non-zero exit, partial artifacts | tool error or environment drift | read `validation-output.txt`; the phase fails closed (no auto-publish); fix the environment, re-dispatch; the ledger preserves the failed attempt for audit |

## See also

- [MUSE_COMPONENT_REGISTRY.md](MUSE_COMPONENT_REGISTRY.md) — which component owns each schema.
- [MUSE_DATAFLOW.md](MUSE_DATAFLOW.md) — how packets and artifacts move.
- [`../jarvis-verification-gates.md`](../jarvis-verification-gates.md) — the gate contract.
- [`../remote/windows-claude-code-bridge-guide.md`](../remote/windows-claude-code-bridge-guide.md) — the bridge end to end.
