# Private / local-only mode

A M.U.S.E. Orchestration install that:

- never sends data to a cloud provider,
- never opens an outbound connection beyond loopback (optional —
  you can leave LAN access on),
- runs every worker, every model, every gate on the same machine.

This mode is useful for:

- Air-gapped engineering work.
- Personal automations on a laptop that travels.
- Regulated data where "the model provider sees it" is not
  acceptable.
- The Termux-on-phone setup from
  [android-termux-demo.md](android-termux-demo.md).

## What gets disabled

In private/local mode you turn off, in this order of priority:

1. **Cloud LLM providers.** No `anthropic:*`, `openai:*`,
   `openrouter:*`, etc. All model traffic goes to a local server
   (llama.cpp, vLLM, Ollama, Nous Portal running on-prem, etc.).
2. **Network-touching plugins.** `github_assistant`, MCP servers
   that resolve over HTTPS, the public `web_search` tool, anything
   under `plugins/model-providers/<remote>/`.
3. **Cloud terminal environments.** Modal, Daytona, Vercel Sandbox,
   SSH-to-external. Only `local`, `docker`, `singularity` remain.
4. **The messaging gateway adapters.** Telegram, Discord, Slack,
   WhatsApp, Signal, Email all need the outside world. Disable
   them. The Android cockpit can still connect, but only over LAN
   or loopback.
5. **Cloud memory backends.** `honcho` (Honcho Cloud), `mem0`
   (Mem0 Cloud), `supermemory`. Use the local SQLite memory
   backend instead.
6. **Telemetry.** Anything that posts to a metrics endpoint.
   Observability stays local-only.

Everything else — the orchestrator, the kanban dispatcher, the
decision ledger, the validation gates, the judge, the worker
spawning — works unchanged. The orchestration *shape* is
provider-agnostic.

## Step-by-step

### 1. Pick and run a local model server

Any of these works. Pick one.

**llama.cpp server**:

```bash
# build once
git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp && make -j

# serve a model
./build/bin/llama-server -m ./models/qwen2.5-coder-32b-instruct-q4_k_m.gguf \
  --host 127.0.0.1 --port 8081 -c 32768 -t 8
```

**Ollama**:

```bash
ollama serve &
ollama pull qwen2.5-coder:32b
ollama pull llama3.3:70b-instruct
```

**vLLM** (if you have a GPU):

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-32B-Instruct \
  --host 127.0.0.1 --port 8081
```

The orchestrator doesn't care which — they all speak the OpenAI
chat-completions wire format.

### 2. Point M.U.S.E. at the local server

```bash
muse model add local-coder \
  --base-url http://127.0.0.1:8081/v1 \
  --api-key sk-local-no-auth \
  --model-id qwen2.5-coder-32b

muse model set-default local-coder
muse model         # confirm
```

### 3. Lock down providers and plugins

Edit `~/.hermes/config.yaml`:

```yaml
# Disable every cloud provider.
providers:
  anthropic:
    enabled: false
  openai:
    enabled: false
  openrouter:
    enabled: false
  nous:
    enabled: false
  # ...etc for any you have configured

# Disable network plugins.
plugins:
  github_assistant:
    enabled: false
  web:
    enabled: false
  browser:
    enabled: false
  image_gen:
    enabled: false
  video_gen:
    enabled: false

# Local-only memory.
memory:
  backend: sqlite

# No telemetry.
observability:
  emit_remote: false
```

### 4. Constrain every profile to the local model

```yaml
profiles:
  default:
    model: local-coder
    enabled_toolsets: [terminal, file_edit, file_read]
    disabled_toolsets: [web, fetch, browser, github_assistant]
    environment: local

  engineer:
    model: local-coder
    enabled_toolsets: [terminal, file_edit, file_read]
    disabled_toolsets: [web, fetch, browser, github_assistant]
    environment: docker
    environment_config:
      image: python:3.11-slim
      # No --network in environment_config means docker default; for stricter
      # isolation, use a docker network with no egress, or just `--network none`.
      docker_args: ["--network", "none"]

  reviewer:
    model: local-coder
    enabled_toolsets: [file_read]
    environment: local

orchestration:
  routing:
    - when: true
      use: local-coder
```

The unconditional routing rule (`when: true`) guarantees no card
can ever escape to a different model.

### 5. Block the network at the kernel level (optional, paranoid)

If you want a hard kill:

```bash
# Linux: firewall outbound except loopback
sudo nft add table inet hermes-private
sudo nft add chain inet hermes-private output { type filter hook output priority 0 \; policy drop \; }
sudo nft add rule inet hermes-private output oif lo accept
sudo nft add rule inet hermes-private output meta skuid != $(id -u) accept
```

This blocks outbound from the user that runs M.U.S.E., except over
loopback. Adjust for your local model server's port if needed.

On macOS, `pf` is the equivalent; on Termux, see the next section.

### 6. Smoke test

```bash
# 1. The model resolves locally.
muse model       # → local-coder (default)

# 2. A trivial orchestrated job runs without touching the network.
sudo tcpdump -i any -n 'not host 127.0.0.1' &
TCPDUMP_PID=$!
bash scripts/hermes-orchestrate.sh "Write a one-line haiku about local agents." \
  --deliver file
kill $TCPDUMP_PID
# tcpdump should be silent for the duration of the job.
```

If tcpdump captured anything, find which tool / plugin / provider
leaked and disable it. The ledger shows you which tools were
called.

## Local-only on Termux

Same shape, slightly different ingredients:

```bash
# in Termux
pkg install -y python rust git openssl
# install M.U.S.E. (see android-termux-demo.md)

# llama.cpp builds inside Termux:
pkg install -y cmake make clang
git clone https://github.com/ggerganov/llama.cpp ~/llama.cpp
cd ~/llama.cpp && make -j

# Use a smaller model that fits in phone RAM.
./build/bin/llama-server -m ~/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf \
  --host 127.0.0.1 --port 8081 -c 8192 -t 4
```

Then point M.U.S.E. at `http://127.0.0.1:8081/v1` the same way. The
Android cockpit talks to Termux's `muse gateway` over loopback,
which talks to llama.cpp over loopback. Nothing leaves the device.

Battery life is the real limit on Termux. A 7B Q4 model at modest
context can run an orchestrated job in 5–10 minutes. Plug in the
charger.

## Gotchas

- **Skills that web-search by default.** Some skills under
  `skills/research/` and `skills/social-media/` assume network
  access. They won't error in private mode — they'll just produce
  a card that says "I couldn't reach the internet." Disable the
  skills, or scope them out of the orchestrator's preloaded set.
- **MCP servers that resolve hostnames.** Even MCP servers that
  *seem* local sometimes phone home for auth. Audit your
  `mcp_servers:` block before running offline.
- **Anthropic CLI / Claude Code as a worker.** If you have
  workers that shell out to `claude` or other vendor CLIs, those
  CLIs will call out. Replace them with a local-only equivalent
  or strip them from the worker's toolset.
- **Time drift.** Some judges check timestamps. If your offline
  device's clock drifts hard, ledger entries can look inconsistent.
  Sync time before long runs.

## What you don't lose

- Orchestrator decomposition, fan-out, fan-in, dependency engine.
- Decision ledger, validation gates, judge calls (against the
  local model).
- Kanban dispatcher, multiple parallel workers, retries,
  reassignment, reclaim.
- Android cockpit, Termux runtime, slash commands, job folders,
  templates.
- Self-improvement (skill creation, memory curation) — these are
  fully local features and work without any cloud.

The orchestration system was designed so that "private/local" is a
configuration, not a different product.
