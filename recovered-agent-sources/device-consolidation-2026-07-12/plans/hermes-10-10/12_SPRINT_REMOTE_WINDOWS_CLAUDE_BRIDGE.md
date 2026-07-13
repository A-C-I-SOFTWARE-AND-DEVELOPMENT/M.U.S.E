# Sprint 12 — Secure Remote Windows Claude Code Bridge

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Build a threat-modeled remote bridge so Hermes can ask a Windows workstation to run Claude Code in an allowlisted workspace and return a patch. This is the highest-risk sprint and must be gated by design review.

## Non-negotiable warning

Do not implement arbitrary remote shell. The bridge exists to run a narrow set of signed job envelopes against allowlisted workspaces. Anything broader becomes a remote-code-execution backdoor.

## Phase 1: threat model before code

Produce:

- `docs/security/windows_bridge_threat_model.md`
- `docs/security/windows_bridge_protocol.md`
- `docs/security/windows_bridge_allowlist_policy.md`
- `docs/security/windows_bridge_recovery_and_revocation.md`

Threats to cover:

- stolen phone token;
- compromised gateway;
- malicious repo prompt injection;
- command injection through work packet;
- workspace escape;
- secret exfiltration;
- replayed signed command;
- bridge downgrade;
- tunnel exposure;
- log leakage;
- privilege escalation;
- service persistence abuse.

## Target architecture

```text
Hermes Gateway
  -> creates BridgeCommand envelope
  -> decision engine returns ask/refuse
  -> owner approves
  -> command is signed
  -> command is placed in durable queue
  -> Windows Bridge pulls command over reverse tunnel
  -> bridge validates signature, nonce, expiry, workspace allowlist
  -> bridge runs claude in constrained workspace
  -> bridge captures patch/logs
  -> bridge redacts and uploads WorkerArtifact
```

## Bridge command envelope

```json
{
  "command_id": "bcmd_...",
  "job_id": "job_...",
  "workspace_id": "repo_alias",
  "workspace_path_hash": "...",
  "worker": "claude-code",
  "prompt_artifact_url": "...",
  "allowed_files": [],
  "forbidden_files": [],
  "timeout_seconds": 1800,
  "created_at": "...",
  "expires_at": "...",
  "nonce": "...",
  "signature": "..."
}
```

## Files likely touched

- new `bridge/windows/` directory;
- `hermes_cli/workers/claude_code.py` remote mode;
- `hermes_cli/config.py` bridge config;
- `enterprise/policy.py` or decision engine bridge policy;
- `gateway/platforms/api_server.py` bridge queue endpoints;
- tests for signed envelopes and allowlists;
- installer docs, not automatic install first.

## Parallel agent lanes

| Lane | Agent | Branch | Mission |
|---|---|---|---|
| A | Security Agent | `sprint/12-threat-model` | Complete threat model and protocol. No code. |
| B | Protocol Agent | `sprint/12-envelope-protocol` | Implement signed envelope library and tests. |
| C | Bridge Agent | `sprint/12-windows-bridge` | Implement minimal Windows user-mode bridge after threat model approval. |
| D | Worker Agent | `sprint/12-claude-remote-worker` | Add `remote_bridge` mode to Claude worker. |
| E | Gateway Agent | `sprint/12-bridge-queue` | Implement queue/poll/upload routes with auth. |
| F | QA Agent | `sprint/12-bridge-tests` | Replay, expiry, bad signature, workspace escape tests. |
| G | Reviewer Agent | `sprint/12-red-team` | Red-team bridge before merge. |

## Implementation constraints

- User-mode service only.
- No admin requirement in first release.
- Workspace allowlist required.
- No raw command string execution from phone.
- Signed command envelopes with nonce and expiry required.
- Bridge pulls commands; gateway does not need inbound access to workstation.
- Bridge never stores gateway secrets in repo workspaces.
- Logs redacted before upload.
- Hardware-key approval optional future enhancement.

## Acceptance criteria

- Threat model approved before implementation merge.
- Bad signature is rejected.
- Expired command is rejected.
- Replayed nonce is rejected.
- Non-allowlisted workspace is rejected.
- Forbidden file modification is detected.
- Bridge returns patch artifact, not uncontrolled shell output.
- Remote bridge actions require owner approval.

## Reviewer prompt

```text
Red-team the Windows bridge. Try to turn it into arbitrary remote shell, workspace escape, secret exfiltration, replay attack, or stale approval execution. Block merge if any command path bypasses signed envelopes, workspace allowlists, expiry, or decision verdicts.
```

## Definition of done

Hermes has a minimal, threat-modeled, owner-gated bridge path that can run Claude Code remotely and return a patch without becoming a general remote shell.
