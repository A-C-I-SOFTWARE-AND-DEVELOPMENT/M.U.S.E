# Hermes — Private / Local-Only Mode

> **Status:** Product-level requirements for private/local mode.
> Companion to [`muse-10-10-product-spec.md`](muse-10-10-product-spec.md)
> and the existing orchestration-side doc
> [`../orchestration/private-local-mode.md`](../orchestration/private-local-mode.md)
> (which is the implementation guide). This file owns the **product
> contract** — what private mode promises the user, not how the
> stack is wired.

---

## 1. The promise

When Hermes is running in private/local mode, the user gets this
contract:

> **No prompt, no transcript, no code, no log, no diff, and no
> metadata associated with this user's session ever leaves their
> physical control without an explicit, per-event opt-in.**

"Physical control" means: the user's phone, the user's workstation,
the user's home server, or another machine the user owns and has
chosen to trust. It does **not** mean a cloud they pay for unless
they have explicitly opted that cloud in.

This is a product-level promise, not just a config flag. Every
capability listed in
[`muse-10-10-product-spec.md`](muse-10-10-product-spec.md) §4
must either work in private mode or fail loudly with a clear "this
needs network" message when the user tries to use it.

---

## 2. What private mode disables

The implementation guide
([`../orchestration/private-local-mode.md`](../orchestration/private-local-mode.md))
lists the per-component changes. The product-level rules are:

1. **No cloud LLMs.** All inference goes to a local model server
   (llama.cpp, vLLM, Ollama, or a model running on the user's own
   GPU box on the LAN).
2. **No network-touching plugins.** GitHub, MCP servers that resolve
   over HTTPS, public `web_search`, all remote-model providers — all
   off.
3. **No cloud terminal environments.** Modal, Daytona, Vercel
   Sandbox, SSH-to-external — all off. `local`, `docker`,
   `singularity` only.
4. **No internet-bound gateway adapters.** Telegram, Discord, Slack,
   WhatsApp, Signal, Email — all off. The cockpit talks to the
   gateway over loopback or LAN only.
5. **No cloud memory backends.** Honcho Cloud, Mem0 Cloud,
   Supermemory — all off. Local SQLite only.
6. **No telemetry.** No metrics endpoint. Observability is local
   files only.
7. **No cloud STT.** Voice transcription runs on-device. Cloud STT
   opt-in is disabled in private mode.

---

## 3. What private mode keeps

Everything else works the same:

- The orchestrator, the kanban dispatcher, the decision ledger, the
  validation gates, the judge, worker spawning.
- Multi-agent spawning, isolated worktrees, phase gates, persistent
  queue, checkpointing.
- The cockpit, the dashboard, the approval flow, plain-English
  explanations.
- The Windows-bridge worker — provided the workstation is on the
  same LAN (Tailscale / WireGuard / SSH over LAN). Private mode does
  not forbid LAN, it forbids the open internet.

The user does not lose Hermes when they go private. They lose
*specific* capabilities and they are told exactly which ones.

---

## 4. The audit guarantee

Private mode must be **auditable** — the user must be able to prove
the promise holds without inspecting the code.

### 4.1 The audit script

```
muse doctor --private-mode
```

This script:

1. Reads `~/.hermes/config.yaml` and asserts:
   - No remote model provider is configured as active.
   - No cloud memory backend is configured.
   - No cloud terminal environment is in the active environment
     allowlist.
   - All gateway adapters whose `connection_type` is `internet` are
     disabled.
2. Probes the running backend:
   - Lists every plugin loaded and flags any whose `requires_network`
     manifest field is true.
   - Lists every active worker and flags any whose execution
     environment is not in `{local, docker, singularity, lan-ssh}`.
3. Probes the network:
   - Runs a 30 s capture (no payload logged, headers only) and
     reports outbound connections.
   - Flags any connection whose remote address is not loopback or
     RFC1918.
4. Exits 0 if and only if every check is clean. Exits non-zero with
   a per-failure summary otherwise.

### 4.2 The privacy ledger

In private mode, every action that *would* have crossed the network
in normal mode but was blocked produces a privacy-ledger entry under
`~/.hermes/jobs/<id>/privacy-ledger.jsonl`:

```jsonl
{"action":"web_search","blocked_because":"private-mode","ts":"..."}
{"action":"anthropic_api_call","blocked_because":"private-mode","ts":"..."}
```

The user can `grep` this ledger to see what private mode prevented.
Nothing in this ledger contains the *content* that would have been
sent — only the fact that a send was attempted and blocked.

---

## 5. The cockpit in private mode

The cockpit gains a persistent "🔒 Private mode" pill on the top
bar. Tapping the pill opens a screen that shows:

- The mode (private / normal).
- The local model server the backend is using.
- The list of capabilities currently disabled.
- The last 10 entries of the privacy ledger.
- A **"Run audit"** button that triggers `muse doctor
  --private-mode` on the backend and renders the result.

The cockpit refuses to switch modes mid-job. Switching modes is
explicit and produces a ledger entry.

---

## 6. Voice in private mode

Voice capture in private mode:

- Uses on-device STT only. Cloud STT is hard-disabled.
- The transcript never leaves the device until dispatch (and after
  dispatch only travels to the loopback / LAN backend).
- The original audio bytes are deleted after transcription unless
  the user has opted in to keep them locally for debugging.

If the user toggles cloud STT while in private mode, the cockpit
refuses and surfaces *"Cloud STT is disabled in private mode. Turn
off private mode first, or accept the on-device STT engine."*

---

## 7. Driving mode in private mode

Driving mode works in private mode with one constraint: it cannot
use cloud STT. If on-device STT cannot keep up with driving-mode
latency targets, the cockpit warns the user before driving mode is
enabled in private mode. The warning is shown once and remembered.

---

## 8. Capabilities that are gracefully degraded

| Capability | Private-mode behavior |
|---|---|
| GitHub PR creation | Disabled. Hermes still writes the patch and a PR-body markdown locally; the user can push later by exiting private mode or by using a local git remote on the LAN. |
| Supabase / Vercel | Disabled unless the user has a Supabase Local / Vercel-equivalent on the LAN. Plan-only mode is allowed (no apply). |
| Cloud STT | Disabled. |
| Telemetry | Disabled. |
| Profile mining from GitHub | Disabled. Existing local profile files are still consulted. |
| Web search tool | Disabled. The user is told *"web search is off in private mode."* |
| Self-improvement retrospectives | Enabled; they write locally only. |

The product principle is: **anything Hermes can do without a network,
it still does. Anything that needs a network is named and disabled,
not silently degraded.**

---

## 9. Threat model summary

This is a product-level summary. The implementation guide expands
on each.

| Threat | Mitigation |
|---|---|
| A plugin tries to make an outbound HTTP call. | Plugins must declare `requires_network: true` to load in private mode; the loader refuses non-declared plugins; outbound DNS at the OS level is restricted in the recommended deployment. |
| A worker exfiltrates data via DNS / ICMP / a stray socket. | Workers run in `local` / `docker` / `singularity` environments where outbound networking is the user's choice. The recommended container template denies non-loopback by default. |
| The cockpit talks to a malicious backend on the LAN. | Cockpit TLS pinning is enabled by default; private-mode backends advertise a fingerprint the cockpit verifies. |
| The user accidentally switches off private mode. | Mode switch is explicit, two-tap, with a confirmation phrase if driving mode is on. The cockpit pill shows the active mode at all times. |
| Logs leak content to disk that the user did not expect. | Logs in private mode redact prompt bodies and worker output by default; an opt-in toggle keeps full logs locally for debugging. |

The threat model assumes a trusted operator on a trusted device. It
does not promise resistance to a malicious operator or a compromised
device.

---

## 10. The contract, restated

When private mode is on:

- **No prompt** leaves the device or the LAN.
- **No transcript** leaves the device or the LAN.
- **No code** is sent to a cloud LLM.
- **No metadata** is sent to a telemetry endpoint.
- **No PR** is opened on a public GitHub.
- **No deployment** is triggered on a public cloud.
- **No memory** is stored in a cloud backend.

If Hermes ever does any of these in private mode, it is a bug.
Period.

---

## 11. Cross-references

- [`../orchestration/private-local-mode.md`](../orchestration/private-local-mode.md) — implementation guide (model servers, plugin manifests, env vars).
- [`muse-10-10-product-spec.md`](muse-10-10-product-spec.md) — the spec this mode preserves.
- [`muse-definition-of-done.md`](muse-definition-of-done.md) — DoD for private mode.
- [`../mission/best-coding-tool-mission.md`](../mission/best-coding-tool-mission.md) — the rule "keep operator data private."
