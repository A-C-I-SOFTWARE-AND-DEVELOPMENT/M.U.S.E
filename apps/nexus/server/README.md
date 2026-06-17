# NEXUS Unified Provider Gateway

A local, **OpenAI-compatible** proxy that routes one endpoint to many providers'
**official APIs** using **your own API keys** — the supported, ToS-compliant way
to use Claude, GPT, Gemini, OpenRouter, and local OSS models as a single backend.

> This is the legitimate alternative to reverse-proxying the consumer **web**
> apps. It does **not** scrape `chatgpt.com` / `claude.ai` / `gemini.google.com`,
> use extracted session cookies, impersonate the browser, or evade bot
> detection — all of which violate those providers' Terms of Service and
> circumvent their security controls. It calls the documented APIs you're
> licensed to use. For a flat-rate option use **OpenRouter** (one key, many
> models) or a **local** model (free).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| `POST` | `/v1/chat/completions` | OpenAI schema, streaming + non-streaming |
| `GET` | `/v1/models` | model list |
| `GET` | `/health` | which providers have keys |

## Routing (by `model`)

| Model prefix | Provider | Key |
|---|---|---|
| `claude-*` | Anthropic Messages API | `ANTHROPIC_API_KEY` |
| `gpt-*`, `o1*`, `o3*`, `o4*` | OpenAI | `OPENAI_API_KEY` |
| `gemini-*` | Google Gemini (OpenAI-compat endpoint) | `GEMINI_API_KEY` / `GOOGLE_API_KEY` |
| `openrouter/<model>` | OpenRouter | `OPENROUTER_API_KEY` |
| anything else | local OpenAI-compatible server | `LOCAL_BASE_URL` (e.g. Ollama `http://127.0.0.1:11434/v1`) |

## Setup

```bash
cd apps/nexus/server
# Keys: enter them in NEXUS → Settings → Connections & Credentials, click
# "Generate .env", paste into a .env here (or export them), then:
export $(grep -v '^#' .env | xargs)   # or set them however you like
node provider-gateway.mjs             # → http://127.0.0.1:8782/v1
```

No dependencies — Node 18+ (built-in `fetch`/`http`). Override the port with
`GATEWAY_PORT`.

## Use it from NEXUS

Open NEXUS → **Chat** tab → set the gateway URL to `http://127.0.0.1:8782/v1`
and pick a model (`claude-sonnet-4-5`, `gpt-4o`, `gemini-2.0-flash`,
`openrouter/auto`, …). Messages stream back into the chat over a normal API
call — no UI automation, no synthetic keystrokes.

## Use it from anything OpenAI-compatible

```bash
curl http://127.0.0.1:8782/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"claude-sonnet-4-5","messages":[{"role":"user","content":"hi"}]}'
```

Point the OpenAI SDK at `baseURL: "http://127.0.0.1:8782/v1"`.
