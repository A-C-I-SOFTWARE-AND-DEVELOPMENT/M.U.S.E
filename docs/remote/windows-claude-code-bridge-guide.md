# Windows Claude Code bridge guide

This guide is for running M.U.S.E. against a **Windows** host that
runs Claude Code (or a Claude Code session running on Windows that
you want to drive from a M.U.S.E. backend elsewhere).

> **Heads-up:** Native Windows M.U.S.E. is **early beta**. WSL2 is the
> battle-tested Windows path. If you're starting from scratch and
> can use WSL2, do that — the rest of this doc still applies and is
> simpler. The native-Windows path below works for users who
> deliberately want to avoid WSL2.

---

## What the bridge is

The Claude Code Windows bridge is a small adapter that lets a M.U.S.E.
worker drive a **Claude Code** session running on Windows as if it
were a M.U.S.E. worker environment. It exists because:

- Some users have Claude Code subscriptions and want to point M.U.S.E.
  at *that* runtime rather than calling a model API directly.
- Some users have Windows-only toolchains (Visual Studio, MSBuild,
  Unreal, custom hardware drivers) where the Windows file system is
  the only place the work can actually happen.
- Some shops keep Windows for compliance reasons and want M.U.S.E.
  orchestration on top.

The bridge maps a `claude-code-windows` worker environment to:

- a long-lived Claude Code session on a Windows box, addressable
  over an SSH-ish wire protocol,
- with **M.U.S.E.' validation gates, ledger, and approvals** in front
  of it.

You get the best of both: Claude Code's tooling on the Windows host
**plus** the orchestrator's decomposition, audit, and approvals
around it.

---

## Two deployment shapes

The bridge supports two shapes depending on where the M.U.S.E. backend
lives.

### Shape A: M.U.S.E. backend on Linux, Claude Code on Windows

```
[ Your phone / laptop / CLI ]
            │
            ▼
  [ M.U.S.E. backend (Linux) ]
    ── ledger ── gates ── kanban ──
            │
            ▼  (ssh / claude-code-bridge)
  [ Claude Code on Windows host ]
            │
            ▼
       [ Windows file system, tools, builds ]
```

This is the recommended shape. M.U.S.E.' backend runs where it's
happiest (Linux), and only the worker environment lives on Windows.

### Shape B: M.U.S.E. backend on Windows native

```
[ Your phone / laptop / CLI ]
            │
            ▼
  [ M.U.S.E. backend (Windows native) ]
    ── ledger ── gates ── kanban ──
            │
            ▼  (in-process)
  [ Claude Code (Windows) ]
```

Works, but pulls M.U.S.E.' own runtime onto Windows. Use this only if
you have a reason to avoid Linux entirely on this machine.

---

## Windows setup (from scratch)

### 1. Install M.U.S.E. on Windows

```powershell
iex (irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1)
```

The installer pulls a portable MinGit (~45 MB) into
`%LOCALAPPDATA%\hermes\git` if you don't already have Git, so your
system Git stays untouched.

Verify:

```powershell
muse doctor
muse --version
```

If `muse doctor` flags anything, fix it before continuing. The
common Windows issues are PATH ordering (Git Bash vs MinGit), the
PSReadLine version on PowerShell 5.1, and antivirus quarantining
`node_modules`.

### 2. Install Claude Code on Windows

Follow the Claude Code installation docs for your platform. Make
sure you can `claude` from a fresh PowerShell.

### 3. Install the bridge adapter

```powershell
muse plugin enable claude-code-bridge
muse config set claude_code_bridge.transport ssh
muse config set claude_code_bridge.host 127.0.0.1
muse config set claude_code_bridge.port 22
muse config set claude_code_bridge.user $env:USERNAME
```

For Shape A (backend on Linux), the Linux backend talks to your
Windows host over SSH. Make sure OpenSSH server is running on
Windows:

```powershell
Get-Service sshd
# If not running:
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'
```

Test from the Linux side:

```bash
ssh you@windows-host claude --version
```

If that prints a Claude Code version, the wire is up.

### 4. Configure a M.U.S.E. profile that uses the bridge

In `~/.hermes/config.yaml` (on whichever host runs the M.U.S.E.
backend):

```yaml
profiles:
  windows-engineer:
    environment: claude-code-windows
    environment_config:
      host: windows-host.local       # or 127.0.0.1 for native
      user: you
      workdir: C:/work/my-project
      claude_args:
        - --dangerously-skip-permissions   # only for trusted, sandboxed work
    enabled_toolsets: [terminal, file_edit, file_read, github_assistant]
    # The "model" field is ignored — Claude Code uses its own model
    # selection. M.U.S.E. routes the *phase* here; Claude Code handles
    # generation.
```

Confirm:

```bash
muse profile list   # → windows-engineer should appear
```

### 5. Smoke test

```bash
bash scripts/hermes-orchestrate.sh "On the Windows host, run `npm run build` and report any warnings." \
  --assign-to windows-engineer
```

M.U.S.E.:

1. Decomposes the goal.
2. Routes the build phase to `windows-engineer`.
3. Bridges into the Claude Code session on Windows.
4. Claude Code runs the build inside the Windows workdir.
5. Output streams back to the M.U.S.E. ledger and the user surface.
6. Gates run against the output.
7. Final summary lands in the job folder.

---

## What runs where

| Step | Runs on | Why |
|------|---------|-----|
| Orchestrator skill (decomposes the goal) | M.U.S.E. backend | The orchestrator profile lives in M.U.S.E.. |
| Kanban dispatcher | M.U.S.E. backend | Source of truth for phase state. |
| Validation gates (schema, policy, judge) | M.U.S.E. backend | Gates aren't optional — they apply to bridge workers too. |
| Decision ledger | M.U.S.E. backend | Every bridge invocation logs `kind=spawn`, `kind=tool_call`, etc. |
| The actual Claude Code work | Windows host | Claude Code's editor, build tools, file ops. |
| Approvals (HIGH-risk) | Whichever surface you respond on | The bridge cannot bypass `enterprise.policy`. |

The bridge does **not** let Claude Code call publishing tools
directly. A bridge-worker that wants to open a PR returns its diff;
the orchestrator's separate publishing phase calls
`github_assistant` (and that phase, like any HIGH-risk phase, asks
you first). This is intentional: it means a misbehaving bridge worker
cannot ship anything without you approving.

---

## How phases work over the bridge

Each phase that lands on the Windows bridge is mapped to a single
Claude Code session **task** with a structured input/output contract:

- **Input.** The M.U.S.E. phase's `input.md` is fed in as the prompt.
  Any attached files are staged in a workdir Claude Code can see.
- **Output.** Claude Code writes back to the workdir; the bridge
  collects the diff, the stdout, and a structured summary block.
- **Validation.** The M.U.S.E. side runs the schema gate (did Claude
  Code produce the requested output shape?), the policy gate
  (sandbox checks), and the optional judge gate.
- **Ledger.** Every bridge tool call ends up in `ledger.jsonl` with
  `kind=tool_call`, `tool=claude_code.<verb>`, and arguments.

The phase still cycles through the same kanban states
(`todo → ready → in_progress → validating → done`). The only
difference is that `in_progress` means *"Claude Code is working on
Windows."*

---

## How approvals look across the bridge

The bridge does **not** invent a new approval surface. HIGH-risk
events from the Windows side still escalate to your normal surfaces:

- The cockpit's **Approvals** screen.
- A `/orchestrator status` row with state `escalated`.
- Your gateway DM (Telegram, Discord, Slack, …) if configured.

What classifies as HIGH-risk over the bridge:

- The same external mutations as elsewhere (`github_assistant`
  writes, Vercel deploys, Supabase destructive ops, outbound DMs).
- **Anything the policy marks `claude_code.runs_arbitrary_command`
  inside an unsandboxed workdir.** If `--dangerously-skip-permissions`
  is on, the policy is the only thing between you and unintended
  Windows changes — be careful.

If you want stricter control, run Claude Code in a sandbox on the
Windows side (a separate user account, a containerized workdir) and
leave `--dangerously-skip-permissions` off.

---

## Driving the bridge from a phone

Once the bridge is configured and a profile exists, the phone path
is identical to any other orchestrator run:

1. Open the cockpit, type or speak a prompt.
2. Use `--assign-to windows-engineer` in the prompt or rely on
   routing rules to pick the bridge profile.
3. The job runs on the backend; the Windows phase runs on Claude
   Code; the cockpit shows progress like any other job.

There is no separate "Windows app" — the orchestrator does the
work and the phone is just a window into it.

---

## Disconnect recovery

The bridge is designed to survive both ends going up and down.

- **Backend restart.** On restart, the kanban dispatcher re-reads
  the ledger, finds `in_progress` phases on the bridge, and reclaims
  them. If the Claude Code session on the other end is still alive,
  the bridge reattaches; if it isn't, the phase is reset to `ready`
  and re-dispatched.
- **Windows host restart.** The Claude Code session is gone. The
  bridge marks all `in_progress` Windows phases as `failed` with a
  `host_unreachable` reason; the orchestrator retries them on the
  next dispatcher tick.
- **Network blip.** Up to `claude_code_bridge.reconnect_grace_seconds`
  (default 30s), the bridge waits without marking failure. After
  that, behave as host-unreachable.

You can force a manual reclaim:

```bash
muse kanban reclaim <task-id>
```

---

## Secrets across the bridge

The bridge is a **mutual-trust** boundary:

- The M.U.S.E. backend trusts the Windows host enough to ship prompts,
  diffs, and (sometimes) source code to it.
- The Windows host trusts the M.U.S.E. backend enough to take its
  instructions.

That means:

- **SSH key pinning.** Use a dedicated SSH key, not your personal
  one. Configure `~/.ssh/known_hosts` strictly. Disable password
  auth in Windows OpenSSH.
- **No API keys cross the bridge.** M.U.S.E. does **not** send your
  Anthropic / OpenAI / GitHub keys to the Windows host. The Windows
  Claude Code session uses its own credentials, configured on the
  Windows side. The bridge is data-only.
- **Workdir scoping.** Pin `environment_config.workdir` to a
  specific Windows path; don't let it default to user-home. The
  bridge refuses requests that try to walk above the configured
  workdir.

If you want to disable the bridge in a hurry:

```bash
muse plugin disable claude-code-bridge
```

Any `in_progress` Windows phase rolls back on the next dispatcher
tick.

---

## Windows quick start (one screen)

```powershell
# On Windows
iex (irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1)
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
# (install Claude Code separately, confirm `claude --version` works)

# On the host running the M.U.S.E. backend
muse plugin enable claude-code-bridge
muse config set claude_code_bridge.host windows-host.local
muse config set claude_code_bridge.user $YOUR_WINDOWS_USER

# Configure a profile, then:
ssh $YOUR_WINDOWS_USER@windows-host.local claude --version   # smoke test
bash scripts/hermes-orchestrate.sh "Confirm the Windows bridge works: print Node version." \
  --assign-to windows-engineer
```

If the smoke job completes, you're done.

---

## Prompt examples for the bridge

Bridge prompts work best when they make the Windows scope explicit.

| Prompt | What runs where |
|--------|------------------|
| *"On Windows, run a release build of the Unreal project and report any warnings."* | Orchestrator decomposes; build phase runs on Windows via Claude Code; report phase aggregates on the backend. |
| *"Profile the .NET service in C:/work/api for startup time and propose three improvements."* | Profile + analyze on Windows; the proposal phase runs on the backend so it can hit the LLM with full repo context. |
| *"Update the Visual Studio solution to MSBuild 17, run all unit tests, and post the diff."* | Update + test on Windows; diff returns to backend; PR-open phase escalates for approval as usual. |
| *"Reproduce the issue from PR #142 on Windows and capture a minidump."* | All on the Windows side; minidump attaches to the job folder; you review on whichever surface. |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `bridge: host_unreachable` | OpenSSH server stopped, or firewall blocking | `Get-Service sshd`; allow port 22; retry. |
| `bridge: claude_not_found` | Claude Code not on PATH for the SSH user | Reinstall Claude Code with system-wide PATH, or hardcode `environment_config.claude_bin`. |
| Phase stuck `in_progress` for hours | Claude Code is silent on the Windows side (likely a UAC / interactive prompt blocking) | `muse kanban reclaim <task-id>`; on Windows, run the same command in an interactive shell to surface the prompt. |
| Phase finishes but output is empty | Workdir scope mismatch — Claude Code wrote outside the configured workdir | Set `environment_config.workdir` explicitly; rerun. |
| `policy: HIGH-risk refused (sandbox=off)` | Policy rejects because workdir is wide-open | Narrow the workdir, or wrap Claude Code in a constrained user account. |
| Repeated judge fails on a bridge phase | Claude Code's output shape doesn't match the orchestrator's acceptance criteria | Sharpen the orchestrator skill's acceptance criteria, or downgrade the judge to peer-level. |

Anything else: see
[../troubleshooting/hermes-orchestration-troubleshooting.md](../troubleshooting/hermes-orchestration-troubleshooting.md).

---

## See also

- [mobile/mobile-app-guide.md](../mobile/mobile-app-guide.md) — the
  cockpit you'll likely use to drive the bridge.
- [security/private-local-security-guide.md](../security/private-local-security-guide.md)
  — keeping bridge traffic private to your LAN.
- [orchestration/worker-adapters.md](../orchestration/worker-adapters.md)
  — how worker adapters work in general.
- [integrations/github-supabase-vercel-guide.md](../integrations/github-supabase-vercel-guide.md)
  — the publishing-side integrations a bridge phase typically feeds.
