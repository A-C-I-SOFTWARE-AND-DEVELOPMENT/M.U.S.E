---
sidebar_position: 9
title: "Run muse Locally with Ollama — Zero API Cost"
description: "Step-by-step guide to running muse entirely on your own machine with Ollama and open-weight models like Qwen3.5, Qwen3-Coder, and gpt-oss, no cloud API keys or paid subscriptions needed"
---

# Run muse Locally with Ollama — Zero API Cost

## The Problem

Cloud LLM APIs charge per token. A heavy coding session can cost $5–20. For personal projects, learning, or privacy-sensitive work, that adds up — and you're sending every conversation to a third party.

## What This Guide Solves

You'll set up muse running entirely on your own hardware, using [Ollama](https://ollama.com) as the model backend. No API keys, no subscriptions, no data leaving your machine. Once configured, muse works exactly like it does with OpenRouter or Anthropic — terminal commands, file editing, web browsing, delegation — but the model runs locally.

By the end, you'll have:

- Ollama serving one or more open-weight models
- muse connected to Ollama as a custom endpoint
- A working local agent that can edit files, run commands, and browse the web
- Optional: a Telegram/Discord bot powered entirely by your own hardware

## What You Need

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **RAM** | 8 GB (for 9B models) | 32+ GB (for 30B models) |
| **Storage** | 6 GB free | 30+ GB (for multiple models) |
| **CPU** | 4 cores | 8+ cores (AMD EPYC, Ryzen, Intel Xeon) |
| **GPU** | Not required | NVIDIA GPU with 8+ GB VRAM speeds things up significantly |

:::tip CPU-only works, but expect slower responses
Ollama runs on CPU-only servers. A 9B model on a modern 8-core CPU gives ~10 tokens/sec. A 30B model on CPU is slower (~2–5 tokens/sec) — each response takes 30–120 seconds, but it works. A GPU dramatically improves this. For CPU-only setups, widen the API timeout via the env var (it's not a `config.yaml` key):

```bash
# ~/.hermes/.env
HERMES_API_TIMEOUT=1800   # 30 minutes — generous for slow local models
```
:::

## Step 1: Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify it's running:

```bash
ollama --version
curl http://localhost:11434/api/tags   # Should return {"models":[]}
```

## Step 2: Pull a Model

Choose based on your hardware. Every model below supports tool calling — pick by role and size:

| Model | Size on Disk | RAM Needed | Tool Calling | Best For |
|-------|-------------|------------|:------------:|----------|
| `qwen3.5:9b` | ~6 GB | 8+ GB | Yes | Fast all-rounder / default daily driver — also does vision |
| `gemma4:12b` | ~8 GB | 12+ GB | Yes | Balanced general + vision (image understanding) |
| `gpt-oss:20b` | ~13 GB | 16+ GB | Yes | Reasoning, planning, and critic work (thinking model) |
| `qwen3-coder:30b` | ~19 GB | 24+ GB | Yes | Coding workhorse — agentic edits and refactors |
| `Qwythos-Mythos` (9B) | ~7 GB | 8+ GB | Yes | Creative / companion + very long context |

:::note Your installed models take priority over these examples
The models above are concrete, currently-available examples. **Your own installed models (run `ollama list`) take priority** — use whatever you have pulled. Browse [Ollama's model library](https://ollama.com/library) for more.
:::

:::warning Tool calling matters
muse is an **agentic** assistant — it edits files, runs commands, and browses the web through tool calls. Models without tool-call support can only chat; they can't take actions. All of the models above support tools, so any of them works for the full muse experience. For coding specifically, `qwen3-coder:30b` is the strongest; for fast daily use, `qwen3.5:9b`.
:::

Pull your chosen model:

```bash
ollama pull qwen3.5:9b
```

:::info Multiple models
You can pull several models and switch between them inside muse with `/model`. Ollama loads the active model into memory on demand and unloads idle ones automatically.
:::

Verify the model works:

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.5:9b",
    "messages": [{"role": "user", "content": "Say hello"}],
    "max_tokens": 50
  }'
```

You should see a JSON response with the model's reply.

## Step 3: Configure muse

Run the muse setup wizard:

```bash
muse setup
```

When prompted for a provider, select **Custom Endpoint** and enter:

- **Base URL:** `http://localhost:11434/v1`
- **API Key:** Leave empty or type `no-key` (Ollama doesn't need one)
- **Model:** `qwen3.5:9b` (or whichever model you pulled)

Alternatively, edit `~/.hermes/config.yaml` directly:

```yaml
model:
  default: "qwen3.5:9b"
  provider: "custom"
  base_url: "http://localhost:11434/v1"
```

## Step 4: Start Using muse

```bash
muse
```

That's it. You're now running a fully local agent. Try it out:

```
You: List all Python files in this directory and count the lines of code in each

You: Read the README.md and summarize what this project does

You: Create a Python script that fetches the weather for Ho Chi Minh City
```

muse will use the terminal tool, file operations, and your local model — no cloud calls.

## Step 5: Pick the Right Model for Your Task

Not every task needs the biggest model. Here's a practical guide:

| Task | Recommended Model | Why |
|------|-------------------|-----|
| File edits, code, refactors, terminal commands | `qwen3-coder:30b` | Coding workhorse — strongest agentic tool use |
| Reasoning, planning, critic | `gpt-oss:20b` | Dedicated thinking model |
| Fast daily Q&A and general use | `qwen3.5:9b` | Quick, capable all-rounder (also handles vision) |
| Image understanding / vision | `gemma4:12b` or `qwen3.5:9b` | Both support vision input |
| Creative / companion, long context | `Qwythos-Mythos` (9B) | Tuned for companion use and very long context |

:::note
Every model above supports tool calls, so all of them work for full agentic work (editing files, running commands, browsing). Match the model to the task — coding to `qwen3-coder:30b`, reasoning to `gpt-oss:20b`, everyday use to `qwen3.5:9b`. Check [Ollama's model library](https://ollama.com/library) for newer models.
:::

Switch models on the fly inside a session:

```
/model qwen3-coder:30b
```

## Step 6: Optimize for Speed

### Increase Ollama's Context Window

By default, Ollama 0.30.11 uses a **4096**-token context (older releases defaulted to 2048). For agentic work (tool calls, long conversations), you need more. The simplest server-wide way is the `OLLAMA_CONTEXT_LENGTH` environment variable on the Ollama server:

```bash
# Applies to every model the server loads
OLLAMA_CONTEXT_LENGTH=16384 ollama serve
```

:::warning Use `OLLAMA_CONTEXT_LENGTH`, not `OLLAMA_NUM_CTX`
The server-side variable is `OLLAMA_CONTEXT_LENGTH`. There is **no** `OLLAMA_NUM_CTX` env var — that name is invalid and silently ignored. (`num_ctx` exists only as a per-request option or a Modelfile `PARAMETER`, not as an environment variable.)
:::

To bake a larger context into a single model instead, use a Modelfile:

```bash
# Create a Modelfile that extends context for one model
cat > /tmp/Modelfile << 'EOF'
FROM qwen3.5:9b
PARAMETER num_ctx 16384
EOF

ollama create qwen3.5-9b-16k -f /tmp/Modelfile
```

Then update your muse config to use `qwen3.5-9b-16k` as the model name.

### Keep the Model Loaded

By default, Ollama unloads models after 5 minutes of inactivity. For a persistent gateway bot, keep it loaded:

```bash
# Set keep-alive to 24 hours
curl http://localhost:11434/api/generate \
  -d '{"model": "qwen3.5:9b", "keep_alive": "24h"}'
```

Or set it globally in Ollama's environment:

```bash
# /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment="OLLAMA_KEEP_ALIVE=30m"
```

### Use GPU Offloading (If Available)

If you have an NVIDIA GPU, Ollama automatically offloads layers to it. Check with:

```bash
ollama ps   # Shows which model is loaded and how many GPU layers
```

For a 30B model on an 8–12 GB GPU, you'll get partial offload (some layers on GPU, the rest on CPU), which still gives a speedup. To control how many layers land on the GPU, use the per-request `num_gpu` option or a Modelfile `PARAMETER num_gpu <n>` — there is no `OLLAMA_NUM_GPU_LAYERS` environment variable.

### 8 GB VRAM / CPU-only Tuning

On a laptop-class GPU (e.g. 8 GB VRAM) or CPU-only, the bottleneck is memory, not raw compute. The 9–12B models (`qwen3.5:9b`, `gemma4:12b`) are the **speed sweet spot** — they fit mostly on an 8 GB GPU. The 20B/30B models (`gpt-oss:20b`, `qwen3-coder:30b`) still run but only partially offload to the GPU, so they're noticeably slower; reach for them when the task quality justifies the wait.

The native context windows these models advertise (256K–1M tokens) are **unreachable at 8 GB** — the KV cache won't fit. Cap context and shrink the KV cache so the model fits. Set these on the Ollama **server** (they take effect when `ollama serve` starts):

```bash
# /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment="OLLAMA_FLASH_ATTENTION=1"      # enable flash attention (lower KV memory)
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"     # quantize the KV cache to 8-bit
Environment="OLLAMA_CONTEXT_LENGTH=16384"   # cap context (see per-size guidance below)
Environment="OLLAMA_NUM_PARALLEL=1"         # one request at a time (don't split VRAM)
Environment="OLLAMA_MAX_LOADED_MODELS=1"    # keep only one model resident
Environment="OLLAMA_KEEP_ALIVE=30m"         # hold the model in memory for 30 minutes
```

After editing the override, reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

Realistic context caps at 8 GB (with `q8_0` KV cache + flash attention):

| Model size | Practical context cap |
|-----------|-----------------------|
| 9–12B | ~16K–24K tokens |
| 20B | ~8K–12K tokens |
| 30B | ~6K–8K tokens |

`OLLAMA_FLASH_ATTENTION=1` plus `OLLAMA_KV_CACHE_TYPE=q8_0` roughly halve KV-cache memory versus the default F16 cache, which is what makes these caps reachable. `OLLAMA_NUM_PARALLEL=1` and `OLLAMA_MAX_LOADED_MODELS=1` keep all of your scarce VRAM dedicated to one model and one request instead of being split. See the [Environment Variables reference](../reference/environment-variables.md#ollama-server-local-serving) for the full list.

## Step 7: Run as a Gateway Bot (Optional)

Once muse works locally in the CLI, you can expose it as a Telegram or Discord bot — still running entirely on your hardware.

### Telegram

1. Create a bot via [@BotFather](https://t.me/BotFather) and get the token
2. Add to your `~/.hermes/config.yaml`:

```yaml
model:
  default: "qwen3.5:9b"
  provider: "custom"
  base_url: "http://localhost:11434/v1"

platforms:
  telegram:
    enabled: true
    token: "YOUR_TELEGRAM_BOT_TOKEN"
```

3. Start the gateway:

```bash
muse gateway
```

Now message your bot on Telegram — it responds using your local model.

### Discord

1. Create a Discord application at [discord.com/developers](https://discord.com/developers/applications)
2. Add to config:

```yaml
platforms:
  discord:
    enabled: true
    token: "YOUR_DISCORD_BOT_TOKEN"
```

3. Start: `muse gateway`

## Step 8: Set Up Fallbacks (Optional)

Local models can struggle with complex tasks. Set up a cloud fallback that only activates when the local model fails:

```yaml
model:
  default: "qwen3.5:9b"
  provider: "custom"
  base_url: "http://localhost:11434/v1"

fallback_providers:
  - provider: openrouter
    model: anthropic/claude-sonnet-4
```

This way, 90% of your usage is free (local), and only the hard tasks hit the paid API.

## Troubleshooting

### "Connection refused" on startup

Ollama isn't running. Start it:

```bash
sudo systemctl start ollama
# or
ollama serve
```

### Slow responses

- **Check model size vs RAM:** If your model needs more RAM than available, it swaps to disk. Use a smaller model or add RAM.
- **Check `ollama ps`:** If no GPU layers are offloaded, responses are CPU-bound. This is normal for CPU-only servers.
- **Reduce context:** Large conversations slow down inference. Use `/compress` regularly, or set a lower compression threshold in config.

### Model doesn't follow tool calls

Very small models sometimes ignore tool-call instructions and produce plain text instead of structured function calls. Solutions:

- **Use a bigger / stronger model** — `qwen3-coder:30b` and `gpt-oss:20b` handle tool calls much better than tiny models; `qwen3.5:9b` is a solid lighter choice.
- **muse has auto-repair** — it detects malformed tool calls and attempts to fix them automatically.
- **Set up a fallback** — if the local model fails 3 times, muse falls back to a cloud provider.

### Context window errors

The default Ollama context (4096 tokens in 0.30.11; 2048 in older releases) is too small for agentic work. See [Step 6](#step-6-optimize-for-speed) to raise it with `OLLAMA_CONTEXT_LENGTH` or a Modelfile.

## Cost Comparison

Here's what running locally saves compared to cloud APIs, based on a typical coding session (~100K tokens input, ~20K tokens output):

| Provider | Cost per Session | Monthly (daily use) |
|----------|-----------------|---------------------|
| Anthropic Claude Sonnet | ~$0.80 | ~$24 |
| OpenRouter (GPT-4o) | ~$0.60 | ~$18 |
| **Ollama (local)** | **$0.00** | **$0.00** |

Your only cost is electricity — roughly $0.01–0.05 per session depending on hardware.

## What Works Well Locally

- **File editing and code generation** — models 9B+ handle this well
- **Terminal commands** — muse wraps the command, runs it, reads output regardless of model
- **Web browsing** — the browser tool does the fetching; the model just interprets results
- **Cron jobs and scheduled tasks** — work identically to cloud setups
- **Multi-platform gateway** — Telegram, Discord, Slack all work with local models

## What's Better with Cloud Models

- **Very complex multi-step reasoning** — 70B+ or cloud models like Claude Opus are noticeably better
- **Long context windows** — cloud models offer 100K–1M tokens; local models are typically 8K–32K
- **Speed on large responses** — cloud inference is faster than CPU-only local for long generations

The sweet spot: use local for everyday tasks, set up a cloud fallback for the hard stuff.