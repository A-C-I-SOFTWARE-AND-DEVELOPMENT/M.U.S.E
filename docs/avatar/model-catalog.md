# Pre-wired model catalog

`config/model-catalog.yaml` is the ready-to-go list of OSS models the
agent and the app can select immediately. `hermes_model_catalog.py`
loads + validates it and answers "what's ready right now?".

## What ships ready

- **Cloud OSS hosting:** OpenRouter, NovitaAI, NVIDIA NIM, Ollama Cloud,
  HuggingFace — covering Llama 3.x, Qwen 2.5 (+ Coder), DeepSeek
  R1/V3, Mixtral, Nemotron, Mistral-NeMo.
- **On-device / desktop (no key):** Ollama (`llama3.2`, `qwen2.5`) and
  llama.cpp, via the `custom` provider pointed at the local daemon.
- **Media:** image (`fal` FLUX 2 / `openai` GPT-Image / `xai` Grok) and
  video (`fal` Veo 3 / Kling / Wan, `xai` Grok video).

## Readiness

A model is **READY** when its provider's `requires_env` key is set (the
loader only checks *presence*, never values). Local models need no key —
connectivity to the daemon is checked separately. `defaults` lists a
per-tier preference order; the loader returns the first READY entry, so
you always have a working default regardless of which keys you've added.

```bash
# What's ready with the keys currently in your environment:
python3 hermes_model_catalog.py
```

Set keys in `~/.hermes/.env` (placeholders in `.env.example`, under
"SENTIENT AVATAR"). Adding a model is a YAML edit — no code change.

## In the app

The `/model` picker and the agent router read the catalog. "Make an
image / video" capabilities (`create.image`, `create.video`) and the
photo→avatar conversion (`create.avatar`) route to the media providers
listed under `media:`.

## Validation

`tests/test_model_catalog.py` covers loading, readiness-by-env, default
selection, media readiness, and the loader's guards (duplicate refs,
unknown default refs, missing required fields). Run:

```bash
python3 -m pytest tests/test_model_catalog.py -o addopts=""
```
