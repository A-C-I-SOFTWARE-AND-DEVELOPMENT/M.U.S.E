# Private / local security guide

This guide is the plain-English answer to: *"How do I keep muse
fully private — nothing leaves my devices?"*

It is also the practical guide to **secrets protection** in normal
mixed use: where API keys live, what the agent can and cannot see,
how approvals stop bad mutations, and how to recover if something
leaks.

> For an air-gapped, no-cloud, llama.cpp-on-loopback configuration
> from a clean install, the canonical recipe is
> [orchestration/private-local-mode.md](../orchestration/private-local-mode.md).
> This page is broader: secrets, approvals, profile data, voice,
> mobile, the bridge — all of it.

---

## What "private / local" means

There are three things people mean. They overlap but aren't the same.

1. **Private cloud.** You're using cloud models, but your prompts
   don't go to anyone but the model provider. Memory, jobs, code
   stay on your machines.
2. **Local-only models.** No cloud model is involved at all. The
   model server runs on the same host as muse on loopback.
3. **Air-gapped.** No outbound network connections of any kind.
   Local model, local everything, kernel-level firewall.

You can run muse in any of the three. Each adds restrictions but
keeps the orchestration shape unchanged.

---

## The threat model, briefly

muse is a multi-tool agent with the ability to:

- Edit files on the host.
- Run shell commands (subject to allowlists).
- Reach external services (GitHub, Vercel, Supabase, gateways).
- Read memory from past sessions.
- Spawn subagents that inherit some of the above.

That means **secrets, code, and external-mutation rights** all flow
through one process. The security architecture rests on three
ideas, in priority order:

1. **The agent never sees API keys.** Keys live in `~/.hermes/.env`
   and are read by plugins inside the process boundary. They are
   not interpolated into prompts, not included in tool arguments,
   not written to the ledger. A plugin uses the key; the agent uses
   the plugin.
2. **Mutations require approvals.** Every external mutation (GitHub
   write, Supabase destructive op, Vercel deploy, gateway DM) goes
   through `enterprise.policy.classify`. HIGH-risk operations always
   escalate to a human surface before executing. No backdoors.
3. **The ledger is tamper-evident.** Every spawn, model call, tool
   call, and mutation lands in `~/.hermes/jobs/<job-id>/ledger.jsonl`.
   It is append-only and the publishing layer refuses to rewrite
   history.

If you want to verify any of this, the policy classifier is in
[`enterprise/policy.py`](../../enterprise/policy.py), the ledger
contract is in [`docs/orchestration/decision-ledger.md`](../orchestration/decision-ledger.md),
and the plugin-token contract is in
[`docs/github-integration.md`](../github-integration.md).

---

## Where secrets live

A short tour of files that hold secrets and what reads them.

### `~/.hermes/.env`

All API keys. Examples:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
SUPABASE_ACCESS_TOKEN=sbp_...
VERCEL_TOKEN=...
TELEGRAM_BOT_TOKEN=...
ELEVENLABS_API_KEY=...
DEEPGRAM_API_KEY=...
```

**Who reads it.** The muse process startup loads it; individual
plugins fetch the variables they need; the underlying model client
gets the model-provider key it needs.

**Who doesn't read it.** The agent's prompt context, the ledger, the
job folder, the memory backend, the cockpit, gateway DM payloads.

`chmod 600 ~/.hermes/.env` is part of the install script. Verify:

```bash
ls -la ~/.hermes/.env
# → -rw------- 1 you you ...
```

### Android Keystore (cockpit)

The bearer token that the cockpit uses to authenticate to the gateway
lives in Android Keystore — hardware-backed where available. The
phone never holds your API keys.

### OS keyring (desktop / Windows)

On Windows, the installer uses Credential Manager for tokens where
applicable. On macOS, the user keychain. On Linux desktops, Secret
Service. muse prefers the keyring over plain files when one is
available.

### SSH keys (Windows Claude Code bridge)

The bridge uses SSH keys you control. muse does not generate or
manage them; it reads from `~/.ssh/` like any other SSH client.

### Memory backend

Memory entries are facts derived from conversation. They should not
contain credentials. The curator has a regex filter for common
credential patterns (PATs, OpenAI keys, SSH keys) and refuses to
store matches; bugs in that filter are security-class issues.

---

## What the agent can see

In a typical run the model receives:

- The user's prompt.
- The system prompt (which describes the agent and its tools).
- Tool definitions (names, descriptions, argument schemas).
- Tool results (output the plugin returned).
- Previous turn context, compressed as needed.
- Loaded skills (Markdown).
- Memory entries the curator surfaces.

**Not** in the model context:

- Raw API keys.
- The contents of `~/.hermes/.env`.
- Tool arguments are scrubbed of credential-pattern values before
  going to the model (the tool *result* may contain redacted forms
  like `ghp_***`).
- Other users' sessions in a multi-tenant install.

You can verify any individual run by reading the ledger:

```bash
jq -r 'select(.kind == "model_call") | .messages_in[].content' \
  ~/.hermes/jobs/<job-id>/ledger.jsonl | less
```

---

## How approvals protect mutations

Three risk tiers, classified by `enterprise.policy`:

| Tier | What gets in here | Default behavior |
|------|------------------|------------------|
| **LOW** | Read-only ops, in-memory work, file reads, model calls without side effects. | Auto-approve, audit-only. |
| **MEDIUM** | File edits inside the job workdir, internal state writes, memory updates. | Auto-approve, audit-only, judge runs. |
| **HIGH** | External mutations: GitHub writes, Vercel deploys, Supabase migrations / destructive ops, gateway DMs, file writes outside the job workdir. | Always escalate to a human approval surface. |

A HIGH-risk phase **cannot** be auto-approved without `--autonomy
yolo` (which is recorded explicitly in the ledger and intended only
for jobs whose worst case you've already inspected).

The full classifier and tier definitions live in
[`enterprise/policy.py`](../../enterprise/policy.py). Tests in
`tests/enterprise/` enforce that HIGH-risk paths always escalate.

---

## How phases work, from a security POV

The kanban substrate enforces several security properties:

- **Workers cannot publish directly.** A research worker that
  decides to open a PR mid-run *cannot*. The publishing phase
  is a separate kanban card; only that card's gate triggers the
  HIGH-risk classifier. This is intentional — see
  [`AGENTS.md` §rules-for-orchestrator-code](../../AGENTS.md#rules-for-orchestrator-code).
- **Schemas are checked before promotion.** A worker that returns
  malformed output gets blocked at the schema gate. It can't smuggle
  in a `created_cards=[T_evil]` reference to a card that doesn't
  exist.
- **The decision ledger is append-only.** A misbehaving worker
  cannot rewrite history. The ledger has rotation and gzip support
  but no in-place edits.
- **Reclaim is auditable.** When a phase is forcibly reclaimed or
  cancelled, the ledger records the reason and the actor.

---

## Private-local quick recipes

Three escalating levels of lockdown.

### Recipe A — Private cloud (default safe)

You use cloud models but want everything else local.

```yaml
# ~/.hermes/config.yaml
plugins:
  github_assistant:
    enabled: true        # if you use it
  web:
    enabled: false       # no web search by default
observability:
  emit_remote: false     # no telemetry
memory:
  backend: sqlite        # local only
voice:
  stt:
    engine: whisper-local
  tts:
    enabled: false
```

Run normally. The only outbound connections are to your configured
model provider and explicit integrations (GitHub, Supabase, Vercel
as you use them).

### Recipe B — Local model

Run a local model server (llama.cpp, vLLM, Ollama) and point muse
at it. Disable cloud providers. Full recipe in
[orchestration/private-local-mode.md](../orchestration/private-local-mode.md).

```yaml
providers:
  anthropic: { enabled: false }
  openai: { enabled: false }
  openrouter: { enabled: false }
profiles:
  default:
    model: local-coder
orchestration:
  routing:
    - when: true
      use: local-coder       # unconditional, no escape
```

Now zero model traffic leaves the host. External integrations
(GitHub etc.) can still be on; if you want them off, disable
those plugins too.

### Recipe C — Air-gapped

Recipe B plus:

```bash
# Linux: drop all outbound except loopback for the muse user
sudo nft add table inet hermes-private
sudo nft add chain inet hermes-private output \
  { type filter hook output priority 0 \; policy drop \; }
sudo nft add rule inet hermes-private output oif lo accept
sudo nft add rule inet hermes-private output meta skuid != $(id -u hermes-user) accept
```

Use a separate user for muse (`hermes-user` above) and run with
`sudo -u hermes-user hermes`. The firewall confines that user's
outbound traffic to loopback only.

For Termux, see the Termux subsection in
[orchestration/private-local-mode.md](../orchestration/private-local-mode.md).

---

## Secrets protection for the bridge

The Windows Claude Code bridge is a special case because it crosses
machines. Important properties:

- **No API keys cross the wire.** The muse backend's keys stay on
  the backend. The Windows Claude Code session uses its own
  credentials configured on the Windows side.
- **Workdir is scoped.** The bridge refuses operations outside the
  configured workdir. Don't leave the workdir as `C:/` (or
  `~/`) — pin it to the project root.
- **SSH key pinning.** Use a dedicated key, lock `known_hosts`
  strictly, disable password auth on the Windows OpenSSH server.

See [remote/windows-claude-code-bridge-guide.md §secrets-across-the-bridge](../remote/windows-claude-code-bridge-guide.md#secrets-across-the-bridge).

---

## Voice privacy

Voice is the surface where audio bytes get involved. The choices:

| Setting | Result |
|---------|--------|
| `voice.stt.engine = whisper-local` | Audio stays on the backend. Default. |
| `voice.stt.engine = deepgram` or `groq` or `openai` | Audio bytes leave the backend to that provider. |
| `voice.retention.raw_audio_minutes = 0` | Raw audio deleted at the moment of transcription. |
| `voice.wake_word.enabled = false` | No always-listening behavior. Default. |
| `voice.tts.enabled = false` | Agent never speaks back. Default. |

For zero audio leaving the host, keep wake-word off, set STT to
`whisper-local`, set audio retention to 0, and rely on hold-to-talk.

The full voice walk-through is
[voice/voice-first-user-guide.md](../voice/voice-first-user-guide.md).

---

## Profile privacy

The user profile (GitHub history, memory) lives under
`~/.hermes/profile/` and `~/.hermes/memory/`. By default it never
leaves the host. If you've configured a cloud memory backend
(Honcho, Mem0, Supermemory) the **derived facts** sync to that
service — not the raw GitHub data.

Wipe with:

```bash
muse profile wipe github
muse memory clear --confirm     # nuclear: wipes all memory
```

See [profile/github-history-profile-guide.md](../profile/github-history-profile-guide.md).

---

## Disconnect / leak recovery

### Suspected key leak

1. **Rotate the key at the provider.** Anthropic console, GitHub
   PAT settings, Vercel tokens, Supabase access tokens — invalidate
   the old token there first.
2. **Update `~/.hermes/.env`** with the new key.
3. **Restart muse** `pkill hermes` and start again.
4. **Audit recent jobs.** `grep -l <last-4-chars-of-old-key>
   ~/.hermes/jobs/*/ledger.jsonl` — the agent should never have
   logged the key; if it did, file a security issue and tar the
   matching job folder for review.

### Suspected unauthorized approval

Someone — or some agent path — approved a HIGH-risk phase you
didn't intend.

1. `jq 'select(.kind == "approval")' ~/.hermes/jobs/<job-id>/ledger.jsonl`
   shows who responded.
2. The ledger field `approval.actor` identifies the source:
   `cli`, `gateway:telegram:<chat-id>`, `cockpit:<device-id>`, etc.
3. Revoke that surface (`muse gateway revoke-token <id>`,
   `muse gateway disable <platform>`).
4. Run `muse orchestrator panic-stop` to halt anything in-flight.

### Lost phone with the cockpit installed

1. From any muse host:
   `muse gateway revoke-token <phone-device-id>`. The cockpit's
   bearer is now invalid.
2. The phone never held API keys; the conversation and job folders
   are on the backend. Wiping the phone removes the cache.

---

## What's in the ledger about secrets

The ledger records that a tool call happened, with arguments. The
publishing layer redacts credential-pattern values **before** writing
them. Patterns:

- `ghp_*`, `ghs_*`, `gho_*`, `ghu_*` (GitHub PATs)
- `sk-ant-*` (Anthropic)
- `sk-*` of length ≥40 (OpenAI-style)
- `sbp_*` (Supabase access tokens)
- Anything matching `[A-Za-z0-9]{40,}` in known credential-named
  fields.

If you find a credential in `ledger.jsonl`, that's a bug — file a
security issue.

---

## Frequently asked

### "Can the agent exfiltrate my keys via a clever prompt?"

The agent never receives the keys in its context. Plugins read keys
inside the process. A prompt that asks *"print my GITHUB_TOKEN"*
gets the agent calling a tool — and the tool refuses or returns
redacted output. The relevant code path is in
[`tools/registry.py`](../../tools/registry.py) and
[`plugins/github_assistant/`](../../plugins/github_assistant/).

### "Does the orchestrator log my source code?"

The ledger records tool calls with arguments. If a tool reads a
file, the ledger may include that file content (depending on the
tool). For sensitive repositories, scope the workdir narrowly and
prefer ephemeral worker environments (`environment: docker`) so
the worker doesn't have host access.

### "What if a model provider stores my prompts?"

That's between you and the provider. The local-model recipe
(Recipe B above) removes the concern entirely.

### "Are gateway DMs encrypted in transit?"

The gateway uses TLS to the messaging platform. The platform's
own encryption (Telegram MTProto, Signal E2E, etc.) is independent.
Use the platforms that match your threat model.

---

## See also

- [orchestration/private-local-mode.md](../orchestration/private-local-mode.md)
  — air-gapped recipe.
- [`../../SECURITY.md`](../../SECURITY.md) — reporting vulnerabilities.
- [`../github-integration.md`](../github-integration.md) — how the
  `github_assistant` plugin keeps PATs out of the agent.
- [voice/voice-first-user-guide.md](../voice/voice-first-user-guide.md)
  — voice privacy controls.
- [profile/github-history-profile-guide.md](../profile/github-history-profile-guide.md)
  — what the profile stores and how to wipe it.
- [troubleshooting/hermes-orchestration-troubleshooting.md](../troubleshooting/hermes-orchestration-troubleshooting.md)
  — symptom-to-fix table.
