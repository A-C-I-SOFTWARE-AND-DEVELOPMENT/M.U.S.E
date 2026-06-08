# Claude Code Windows remote-execution bridge

**Status:** Phase 10 — M.U.S.E. side complete, Windows worker daemon
external. File-drop transport is implemented and tested. HTTP and
WebSocket transports are documented as future work and refused at
dispatch time by the bridge.

> **Verification needed:** the Claude Code CLI flag set referenced
> below (`--print`, headless / non-interactive mode) reflects the
> shape used by the local `claude_code` worker as of 2026-05-23.
> When this doc graduates from Phase 10, re-check the official
> Anthropic Claude Code docs (`https://docs.claude.com/claude-code`)
> and pin the exact flags the Windows daemon should call.

## Why this exists

M.U.S.E. typically runs on Jeremiah's Android phone (in Termux) or on a
small Linux backend. Claude Code, by contrast, runs best on his
Windows desktop where it has fast disk, a real IDE handoff, and an
already-authenticated subscription. The bridge lets M.U.S.E. use that
desktop as a remote worker without ever exposing it to the public
internet.

## Architecture

```text
┌────────────────────────────┐         ┌────────────────────────────┐
│ M.U.S.E. (Android / Linux)   │         │ Windows desktop            │
│                            │         │                            │
│ ┌──────────────────────┐   │  prompt │ ┌──────────────────────┐   │
│ │ orchestrator         │───┼────────►│ │ claude_code_windows  │   │
│ │ + claude_code_windows│   │         │ │ daemon (out of repo) │   │
│ │  worker adapter      │   │         │ │                      │   │
│ └─────────┬────────────┘   │         │ └──────────┬───────────┘   │
│           │ dispatch       │         │            │ runs          │
│           ▼                │         │            ▼               │
│ ┌──────────────────────┐   │ status  │ ┌──────────────────────┐   │
│ │ RemoteBridge         │◄──┼─────────┤ │ official `claude` CLI│   │
│ │ (file_drop transport)│   │         │ │ inside repo / worktree│  │
│ └─────────┬────────────┘   │         │ └──────────┬───────────┘   │
│           │                │         │            │ artifacts     │
│           ▼                │         │            ▼               │
│ shared dir / tunnel ◄──────┼─────────► shared dir / tunnel        │
└────────────────────────────┘         └────────────────────────────┘
```

The shared directory is the only thing both sides must agree on. It
can be served by Tailscale + Syncthing, a Tailscale-routed SMB share,
SSHFS over a Tailscale Funnel, a Cloudflare-tunneled WebDAV mount, or
anything else that surfaces a single path to both processes. See
[secure-tunnel-options.md](secure-tunnel-options.md) for the full
matrix.

## End-to-end flow

1. **Android/Termux M.U.S.E. backend creates a job** — usually via
   `/orchestrate <goal>` or a kanban task being decomposed.
2. **M.U.S.E. selects `claude-code-windows`** — either explicitly via
   the user's profile config or because the orchestrator scored this
   worker highest for the task.
3. **M.U.S.E. writes a worker prompt** — the `claude_code_windows`
   adapter reuses the local Claude Code prompt template and appends a
   Windows-specific epilogue (`Remote worker contract`, status
   protocol, required artifacts).
4. **The remote bridge sends the prompt** — files written into
   `<workspace_root>/jobs/<job_id>/`:
   - `prompt.md` — what to do.
   - `manifest.json` — the contract (command, expected artifacts,
     per-job token, device id, `allow_remote_execute` flag).
   - `status.json` — initial state (`queued` or `awaiting_approval`).
5. **The Windows worker daemon runs the official Claude Code CLI**
   in the configured repo / worktree. The daemon is not part of this
   repo — see [windows-agent-setup.md](windows-agent-setup.md) for the
   reference implementation outline.
6. **The Windows worker writes artifacts**:
   - `output.md` — the model's narrative.
   - `patch.diff` — unified diff of proposed changes (omitted when no
     code changes were proposed).
   - `changed-files.txt` — newline-separated list of touched files.
   - `validation-output.txt` — stdout+stderr from the validation
     command, if one was configured.
   - `status.json` — terminal state, axis scores, `auth_token` echoed
     back, `verdict` (`approve` / `revise` / `block`).
7. **M.U.S.E. collects artifacts** via
   `RemoteBridge.collect_artifacts(job_id, dest_dir)`, which refuses
   to copy until the worker reports `state == "completed"`.
8. **M.U.S.E. scores / merges** — the orchestrator hands the artifacts
   to the council reviewer and ranks them against other workers using
   the same `SCORING_WEIGHTS` as the local Claude Code worker.
9. **No publish without approval** — `github_publisher` (and the
   merge engine in general) require an explicit user OK before
   anything lands on `main` or is pushed to a PR.

## Security model

The bridge is built around three rules:

* **Refuse by default.** Every flag that opens an attack surface
  defaults to "off". A misread config name fails closed, not open.
* **Two-of-two opt-in.** Anything that crosses a trust boundary
  requires both the endpoint config *and* the dispatch caller to opt
  in. This applies to remote execution and to `.env` transfers.
* **Audit everything.** Every dispatch, status read, refusal, cancel,
  and collect lands in an append-only JSONL log with secrets
  scrubbed.

### Authentication

* The transport is authenticated *outside* the bridge — Tailscale's
  WireGuard mesh, SSH key auth, Cloudflare Access, etc. The bridge
  does not implement its own TLS; it trusts the tunnel.
* **No public unauthenticated endpoint is ever opened.** The default
  transport is file-drop over a private mount; HTTP / WebSocket
  remain stubs precisely so we cannot accidentally bind a socket on a
  public interface.
* Each job carries a per-job random token
  (`secrets.token_urlsafe(32)`). Status replies that don't echo the
  token are rejected and the rejection is logged as
  `status_token_mismatch`.
* Each endpoint carries an `allowed_device_ids` set. A status reply
  with a `device_id` outside the allowlist is rejected as
  `status_device_not_allowlisted`.

### Command allowlist

The endpoint's `command_allowlist` is enforced at dispatch time.
v1 defaults to `("claude",)`. Adding entries (`pwsh`, `python`, …)
requires a code review *and* a documented justification — config-only
expansion is intentionally not supported.

### Approval gate

`allow_remote_execute` must be `True` on **both** the endpoint and
the dispatch call before the manifest is marked approved. Otherwise
the job is staged in `awaiting_approval`. Approval happens
out-of-band:

* the user calls `bridge.approve(job_id)` after reading the prompt,
* or hits a confirm button in the cockpit (the Android UI shows the
  staged prompt before unlocking),
* or runs `muse orchestrator approve <job_id>` from the CLI.

### Secret hygiene

* `.env` files are refused unless both
  `endpoint.permit_env_transfer=True` and the caller passes
  `allow_remote_execute=True` and includes them via `env_files=...`.
* The audit log scrubs credential-shaped substrings (`sk-…`,
  `ghp_…`, JWTs, AWS keys, URL-embedded basic-auth, `Authorization:
  Bearer …`) via `remote_bridge.scrub_secrets`.
* Filenames are restricted to `[A-Za-z0-9._-]` and refused if they
  start with `.` or contain path separators, so `../escape.txt`
  cannot be staged.

### Failure recovery

* The bridge holds no long-lived state. Restarting M.U.S.E. mid-job
  rehydrates from the manifest and status files in the shared
  directory.
* If the tunnel drops mid-job, `get_status` returns
  `state=unknown`. Once the tunnel is back, the next call reads the
  current `status.json` — either the worker has finished, is still
  running, or has nothing new to report, all surfaced as fresh
  states.
* `cancel(job_id, reason=…)` writes a `cancel.json` sentinel into the
  workspace; the worker is expected to poll it and abort.

## Remote worker protocol (over-the-wire shapes)

The file-drop transport carries these files:

```text
<workspace_root>/
  jobs/
    <job_id>/
      manifest.json        # M.U.S.E. → worker (immutable after dispatch)
      prompt.md            # M.U.S.E. → worker
      status.json          # both sides write; latest writer wins
      cancel.json          # M.U.S.E. → worker (presence = abort)
      env/<files>          # M.U.S.E. → worker, opt-in only
      output.md            # worker → M.U.S.E.
      patch.diff           # worker → M.U.S.E. (optional)
      changed-files.txt    # worker → M.U.S.E.
      validation-output.txt# worker → M.U.S.E.
```

### Manifest schema (`hermes.remote.job.v1`)

```json
{
  "schema": "hermes.remote.job.v1",
  "job_id": "20260523T120000-1a2b3c4d",
  "endpoint": "jeremiah-windows",
  "command": "claude",
  "prompt_filename": "prompt.md",
  "expected_artifacts": ["output.md", "patch.diff", "changed-files.txt", "validation-output.txt", "status.json"],
  "required_artifacts": ["output.md", "changed-files.txt", "validation-output.txt", "status.json"],
  "auth_token": "<32-byte url-safe random>",
  "device_id": "hermes-android",
  "allow_remote_execute": true,
  "created_at": 1716475200.0,
  "extra": {
    "task_kind": "claude-code-windows",
    "remote_repo_path": "C:\\Users\\jeremiah\\repos\\hermes-agent",
    "validation_command": "pytest tests/test_kanban_swarm.py -q"
  }
}
```

### Status schema (`hermes.remote.status.v1`)

```json
{
  "schema": "hermes.remote.status.v1",
  "job_id": "20260523T120000-1a2b3c4d",
  "state": "completed",
  "detail": "applied 3 files, pytest passed",
  "auth_token": "<must match manifest>",
  "device_id": "jeremiah-windows",
  "last_seen": 1716475300.0,
  "artifacts": {"output.md": "narrative", "patch.diff": "3 files"},
  "verdict": "approve",
  "scores": {
    "architecture_fit": 0.9,
    "risk_control": 0.8,
    "maintainability": 0.7,
    "correctness": 0.85,
    "repo_fit": 0.75
  },
  "validation_exit_code": 0,
  "from": "windows-worker"
}
```

### Cancel schema (`hermes.remote.cancel.v1`)

```json
{
  "schema": "hermes.remote.cancel.v1",
  "job_id": "20260523T120000-1a2b3c4d",
  "reason": "user_requested",
  "issued_at": 1716475250.0,
  "from": "hermes"
}
```

## Adapter API surface (Python)

```python
from hermes_cli.remote_bridge import (
    AuditLog, JobState, RemoteBridge, RemoteEndpoint,
)
from hermes_cli.workers import claude_code_windows as ccw

endpoint = RemoteEndpoint.from_mapping(yaml_config)
bridge = RemoteBridge(endpoint, audit_log=AuditLog("/path/audit.jsonl"))

detection = ccw.detect(bridge)            # is the endpoint reachable?
prepared = ccw.prepare_workspace(task, base_dir)
result = ccw.dispatch(prepared, bridge, allow_remote_execute=True)

# Poll loop (every endpoint.poll_interval_seconds)
while True:
    status = ccw.poll_status(bridge, result.job.job_id)
    if status.state in {JobState.COMPLETED, JobState.FAILED,
                        JobState.CANCELED}:
        break

collected = ccw.collect_artifacts(bridge, result.job.job_id, prepared)
weighted = ccw.score(collected.status["scores"])
```

## Future HTTP / WebSocket protocol (NOT implemented)

When the file-drop protocol is no longer enough — typically because
job throughput exceeds what Syncthing can comfortably handle — a
direct request/response protocol over an authenticated tunnel may be
added. The shape will be:

```text
POST   /jobs                                # body = manifest payload
GET    /jobs/{id}/status
GET    /jobs/{id}/artifacts                 # tarball
POST   /jobs/{id}/cancel
WS     /jobs/{id}/events                    # streaming status updates
```

These endpoints are intentionally NOT implemented in Phase 10 — the
bridge raises `TransportNotImplementedError` if the endpoint config
selects them. Implementing them requires:

1. Mutual TLS via the tunnel's identity layer (Tailscale's
   `tsnet` / SSH cert auth / Cloudflare Access mTLS — not a
   self-signed cert managed by M.U.S.E.).
2. A token-bound device allowlist enforced server-side.
3. The same `command_allowlist`, env-transfer refusal, and audit-log
   guarantees the file-drop transport already enforces.

Until those are designed and reviewed, file-drop is the only
production path.

## Known limitations

* The worker daemon on Windows is out-of-repo. The reference outline
  in [windows-agent-setup.md](windows-agent-setup.md) is informal —
  there is no Hermes-shipped binary for it yet.
* The bridge cannot stream stdout in real time. Status detail and
  `validation-output.txt` are the only feedback channels until the
  WebSocket transport ships.
* Multi-repo dispatch (one job touching repos on two machines) is
  out of scope. Each job targets exactly one endpoint.

## See also

* [secure-tunnel-options.md](secure-tunnel-options.md) — the tunnel
  matrix (Tailscale, WireGuard, SSH reverse tunnel, Cloudflare
  Tunnel, local network, manual handoff fallback).
* [windows-agent-setup.md](windows-agent-setup.md) — how to bring up
  the Windows worker daemon.
* [`templates/remote/windows-worker-config.example.yaml`](../../templates/remote/windows-worker-config.example.yaml)
  — fillable endpoint config.
* [`hermes_cli/remote_bridge.py`](../../hermes_cli/remote_bridge.py)
  — the implementation.
* [`hermes_cli/workers/claude_code_windows.py`](../../hermes_cli/workers/claude_code_windows.py)
  — the adapter.
