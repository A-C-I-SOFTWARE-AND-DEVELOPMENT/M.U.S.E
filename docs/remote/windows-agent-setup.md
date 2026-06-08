# Windows worker daemon setup

This document describes the **Windows side** of the Claude Code
bridge — the worker daemon that polls the shared workspace, runs the
official `claude` CLI on M.U.S.E.' behalf, and writes artifacts back.

> **Status:** the daemon is not shipped in this repo yet. The file
> below is the spec the daemon must satisfy. A reference Python
> implementation is sketched in §Reference daemon.

> **Verification needed:** the `claude --print` flag pattern was
> taken from `hermes_cli/workers/claude_code.py`. Cross-check with
> the upstream Claude Code release notes before pinning a specific
> flag combination — Anthropic ships flag changes frequently.

## Prerequisites

* Windows 10 / 11 (or Windows Server 2022+). The daemon does not
  depend on anything WSL-specific.
* The official Claude Code CLI installed and authenticated to
  Jeremiah's subscription. Confirm with `claude --version`.
* Python 3.11+ on the Windows side, used by the reference daemon.
  (Any language is fine — the contract is the on-disk schema, not a
  particular SDK.)
* A configured secure tunnel — see
  [secure-tunnel-options.md](secure-tunnel-options.md). The daemon
  needs read+write access to one local directory; that directory
  must be the shared one.
* `git` on `PATH`. The daemon shells out to `git diff` to populate
  `patch.diff` and `changed-files.txt`.

## High-level lifecycle

```
        ┌────────────────────────────────────────────┐
        │ poll <workspace_root>/jobs/ every 1–5s     │
        └──────────────────────┬─────────────────────┘
                               │
                               ▼
         For each <job_id>/manifest.json not yet started:
         1. Validate schema, command, auth_token presence.
         2. Refuse if allow_remote_execute == false.
         3. Refuse if command not in local allowlist.
         4. Refuse if device_id (M.U.S.E. side) is not approved.
         5. Switch into manifest.extra.remote_repo_path.
         6. Write status.json {state: "running"}.
         7. Run:  claude --print prompt.md  (or equivalent)
         8. Capture stdout/stderr → output.md.
         9. `git diff` → patch.diff;  `git diff --name-only` → changed-files.txt
        10. If manifest.extra.validation_command:
             a. Run it; capture combined output → validation-output.txt.
             b. Record exit code in status.json.validation_exit_code.
        11. Write final status.json with state, verdict, scores,
            auth_token echoed verbatim.
        12. Move on to next job. Never delete files M.U.S.E. wrote.
```

## Filesystem contract

The daemon owns these files inside `<workspace_root>/jobs/<job_id>/`:

| File                     | Direction | Required? | Notes |
|--------------------------|-----------|-----------|-------|
| `manifest.json`          | M.U.S.E. → worker | yes | Read-only on the worker side. Do not modify. |
| `prompt.md`              | M.U.S.E. → worker | yes | The text to drive `claude` with. |
| `cancel.json`            | M.U.S.E. → worker | optional | If it appears mid-run, abort and set `state: canceled`. |
| `status.json`            | both sides | yes | Worker overwrites with the latest state at least every `manifest.created_at + N`. |
| `output.md`              | worker → M.U.S.E. | yes | Narrative summary; usually `claude`'s stdout. |
| `patch.diff`             | worker → M.U.S.E. | when code changes proposed | Unified diff of the working tree. Omit when nothing changed. |
| `changed-files.txt`      | worker → M.U.S.E. | yes | `git diff --name-only`. Empty file is OK. |
| `validation-output.txt`  | worker → M.U.S.E. | yes | Tests / build output. Empty when no validation command was supplied. |

Anything outside this list (caches, scratch state) belongs **outside**
the shared directory so it does not get synced to M.U.S.E..

## Auth model the daemon must enforce

The daemon is the second line of defence behind the bridge:

1. **Manifest schema check.** Refuse jobs whose `schema` is not
   `hermes.remote.job.v1`.
2. **Command allowlist.** Maintain a hard-coded allowlist on the
   Windows side. Refuse manifests whose `command` is not in it.
   v1 allowlist: `{"claude"}`.
3. **`allow_remote_execute` gate.** If the field is `false`, do not
   execute — write `status.json` with `state: awaiting_approval` and
   move on. M.U.S.E. may rewrite the manifest later with the field
   flipped to `true` (the bridge's `approve()` method does exactly
   that).
4. **`auth_token` echo.** Every status the worker writes must include
   the `auth_token` from the manifest verbatim. Without it the
   bridge rejects the reply as a forgery.
5. **Device ID self-identification.** Every status the worker writes
   must carry `device_id` so the bridge can match it against
   `allowed_device_ids`.
6. **Never read outside the workspace.** The only files the daemon
   needs are the manifest, the prompt, and (if approved) the `env/`
   subdirectory. Refuse instructions that ask for arbitrary files
   off the host.

## Secret hygiene

* The daemon should run as a dedicated Windows user, not Jeremiah's
  personal account. Use a service account whose home directory is on
  a separate volume from any developer credential store.
* The shared directory should be ACL'd so only that service account
  and Jeremiah can read it. Other users on the Windows machine — and
  Cloudflare Tunnel's `cloudflared` service if you use one — should
  not have access.
* The daemon must not log the full prompt or full output to Windows
  Event Viewer; it can log job ids and state transitions.
* If a job's `manifest.extra` contains a `validation_command`, treat
  it as untrusted input. Restrict it to a hard-coded allowlist
  (`pytest`, `npm test`, `cargo test`, …) or reject the manifest.
  **Never `cmd /c <validation_command>` without sanitisation.**

## Configuration

The daemon is configured by a small YAML file. The reference fields:

```yaml
shared_workspace: C:\Users\jeremiah-bridge\HermesShared
device_id: jeremiah-windows
poll_interval_seconds: 3
command_allowlist:
  - claude
validation_command_allowlist:
  - pytest
  - npm test
  - npm run test
  - cargo test
  - python -m pytest
repo_roots:
  hermes-agent: C:\Users\jeremiah\repos\hermes-agent
  hermes-android: C:\Users\jeremiah\repos\hermes-android
```

The `repo_roots` map is the only safe way to interpret
`manifest.extra.remote_repo_path` — accept the value only if it
matches a configured root (exact string equality, no realpath
hopping).

## Reference daemon (Python)

The daemon is short enough to fit on one page. It is NOT shipped in
this repo on purpose (the M.U.S.E. process and the Windows daemon
should be deployed independently), but this is the shape it needs:

```python
# windows_worker_daemon.py — reference outline, not shipped.
import json, time, subprocess, secrets
from pathlib import Path

CONFIG = yaml.safe_load(Path("worker.yaml").read_text())
SHARED = Path(CONFIG["shared_workspace"])
ALLOW  = set(CONFIG["command_allowlist"])
VALIDATION_ALLOW = set(CONFIG["validation_command_allowlist"])
REPOS  = {k: Path(v) for k, v in CONFIG["repo_roots"].items()}

def process(job_dir: Path) -> None:
    manifest = json.loads((job_dir / "manifest.json").read_text())
    if manifest.get("schema") != "hermes.remote.job.v1":
        return _refuse(job_dir, manifest, "schema mismatch")
    if manifest["command"] not in ALLOW:
        return _refuse(job_dir, manifest, "command not allowlisted")
    if not manifest.get("allow_remote_execute"):
        return _write_status(job_dir, manifest, "awaiting_approval",
                             "waiting for M.U.S.E. approval")

    repo = manifest["extra"].get("remote_repo_path")
    repo_root = next((p for p in REPOS.values() if str(p) == repo), None)
    if repo_root is None:
        return _refuse(job_dir, manifest, f"unknown repo: {repo!r}")

    _write_status(job_dir, manifest, "running", "claude running")
    prompt = job_dir / manifest["prompt_filename"]
    proc = subprocess.run(
        [manifest["command"], "--print", str(prompt)],
        cwd=repo_root, capture_output=True, text=True, timeout=1800,
    )
    (job_dir / "output.md").write_text(proc.stdout + proc.stderr)

    diff = subprocess.run(["git", "diff", "--no-color"], cwd=repo_root,
                          capture_output=True, text=True)
    (job_dir / "patch.diff").write_text(diff.stdout)
    names = subprocess.run(["git", "diff", "--name-only"], cwd=repo_root,
                           capture_output=True, text=True)
    (job_dir / "changed-files.txt").write_text(names.stdout)

    val_cmd = manifest["extra"].get("validation_command")
    val_exit = None
    if val_cmd in VALIDATION_ALLOW:   # exact match — no shell parsing
        v = subprocess.run(val_cmd.split(), cwd=repo_root,
                           capture_output=True, text=True)
        (job_dir / "validation-output.txt").write_text(v.stdout + v.stderr)
        val_exit = v.returncode
    else:
        (job_dir / "validation-output.txt").write_text("")

    _write_status(job_dir, manifest,
                  "completed" if proc.returncode == 0 else "failed",
                  f"exit {proc.returncode}", validation_exit_code=val_exit)

def _write_status(job_dir, manifest, state, detail, **extra):
    payload = {
        "schema": "hermes.remote.status.v1",
        "job_id": manifest["job_id"],
        "state": state,
        "detail": detail,
        "auth_token": manifest["auth_token"],
        "device_id": CONFIG["device_id"],
        "last_seen": time.time(),
        "from": "windows-worker",
        **extra,
    }
    (job_dir / "status.json").write_text(json.dumps(payload, indent=2))

def _refuse(job_dir, manifest, reason):
    _write_status(job_dir, manifest, "failed", f"refused: {reason}")

def main_loop():
    seen = set()
    while True:
        jobs = sorted((SHARED / "jobs").glob("*/manifest.json"))
        for m in jobs:
            if m.parent in seen: continue
            try: process(m.parent)
            except Exception as exc:
                _refuse(m.parent, json.loads(m.read_text()), str(exc))
            seen.add(m.parent)
        time.sleep(CONFIG.get("poll_interval_seconds", 3))

if __name__ == "__main__":
    main_loop()
```

This sketch is for illustration. A production daemon should also:

* run as a Windows Service (e.g. via `nssm` or a `pythonservice.exe`
  wrapper) so it survives reboots,
* persist the `seen` set across restarts,
* check for `cancel.json` between every long subprocess call,
* prune completed jobs older than N days,
* expose Windows-side health to M.U.S.E. (e.g. by writing a heartbeat
  file at `<workspace_root>/worker-heartbeat.json`).

## Verifying the setup

1. On the M.U.S.E. side, write a tiny test job:
   ```python
   from hermes_cli import remote_bridge as rb
   from hermes_cli.workers import claude_code_windows as ccw

   endpoint = rb.RemoteEndpoint.from_mapping({
       "name": "jeremiah-windows",
       "workspace_root": "/mnt/syncthing/hermes-remote",
       "device_id": "hermes-laptop",
       "allowed_device_ids": ["jeremiah-windows"],
       "allow_remote_execute": True,
   })
   bridge = rb.RemoteBridge(endpoint)
   prepared = ccw.prepare_workspace(
       ccw.RemoteWorkerTask(
           mission="Sanity check: say hello and write output.md.",
           remote_repo_path=r"C:\Users\jeremiah\repos\hermes-agent",
       ),
       base_dir=Path("/tmp/hermes-staging"),
   )
   ccw.dispatch(prepared, bridge, allow_remote_execute=True)
   ```
2. Watch the Windows side write `status.json: running` within
   a poll interval.
3. Watch it transition to `state: completed` and confirm
   `output.md` shows up on the M.U.S.E. side.
4. Inspect the audit log at `~/.hermes/remote/audit.log.jsonl` —
   you should see `dispatch` and `collect` events with no secret
   substrings.

## Failure modes & recovery

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `state: awaiting_approval` indefinitely | Endpoint config has `allow_remote_execute: false`, or the daemon's manifest read finds `allow_remote_execute: false`. | Call `bridge.approve(job_id)` from M.U.S.E. — the bridge rewrites the manifest with the flag flipped. |
| `state: unknown` with detail `auth_token mismatch` | The daemon is writing the wrong token, or two daemons are racing on the same workspace. | Restart the daemon; ensure exactly one daemon polls the workspace. |
| Status frozen at `running` for hours | Daemon crashed mid-run; status file never updated. | Side-channel kill the `claude` process on Windows; write a manual `state: failed` to release the workspace. |
| Tunnel dropped, M.U.S.E. can't see status | Expected — the bridge surfaces `state: unknown` until the tunnel is back. | No action needed unless the tunnel stays down longer than
  `endpoint.status_timeout_seconds`. |

## Hardening checklist

Before letting this run unsupervised:

- [ ] Daemon runs as a non-admin Windows service account.
- [ ] Shared folder ACL'd to that account + Jeremiah only.
- [ ] `command_allowlist` and `validation_command_allowlist`
      reviewed and minimal.
- [ ] `repo_roots` is an exhaustive list — no wildcards.
- [ ] Tunnel auth is on, with a documented rotation cadence.
- [ ] Audit log on the M.U.S.E. side ships to a long-term sink
      (e.g. weekly `git commit` to a private repo, or a SIEM).
- [ ] `cancel.json` propagation tested at least once.
- [ ] `.env` transfer disabled (`permit_env_transfer: false` unless
      a specific job documented a reason).
