# NL-compiler training: dataset validation + Together fine-tuning

`hermes_cli/nlp_training.py` validates training datasets against strict quality
gates and dispatches **owner-gated, cost-guarded** fine-tuning jobs. It is the
outbound counterpart to `hermes_cli/jarvis_prime/nlp_training.py` (which exports
validated NL-compile traces *into* the local learning dataset).

> **Nothing is trained automatically.** A paid job is only ever created when a
> dataset passes every quality gate, `TOGETHER_API_KEY` is present, and you pass
> `--yes-start-paid-training` explicitly. Duplicate jobs for the same
> dataset+model+hyperparams are refused.

## Provider choice

| Provider | Status | Why |
|---|---|---|
| **Together AI** | **default** | Active managed fine-tuning; conversational JSONL; client-side `check_file` validation; LoRA SFT. |
| OpenAI | fallback only | OpenAI has stated its fine-tuning platform is winding down. |
| HF AutoTrain | not selected | No longer maintained. |
| Replicate | later | Training schema is model-version-specific (not a generic first target). |
| Modal | later | Infrastructure, not a managed fine-tune dataset API. |

Default base model: `Qwen/Qwen3-8B` · method: **LoRA SFT** · defaults:
`train_on_inputs="auto"`, `lora=True`, `n_epochs=3`, `n_checkpoints=1`,
`learning_rate=1e-5`, `warmup_ratio=0`, `batch_size="max"`, `weight_decay=0`,
`max_grad_norm=1.0`.

## Dataset quality gates

A dataset is **owner-approved for training only when all gates pass**:

- Valid UTF-8; every non-empty line parses as a JSON object.
- ≥ 10 examples (warn below 50).
- No detectable secrets (OpenAI/Together/Anthropic keys, bearer/OAuth/GitHub
  tokens, AWS/Slack/Google keys, private keys, `.env` credential lines). Only
  the *type* of a detected secret is ever surfaced — never the value.
- Duplicate rate reported (warn above 10%).
- **Conversational/tool-call SFT** rows: `messages` present; first non-system
  message is `user`; valid roles; user/assistant alternation; non-empty content;
  assistant targets exist and are specific (no `TODO`/placeholder); tool-call
  `arguments` are valid JSON with a function name.
- **Prompt-only** rows (`{"prompt": ...}`) are *generation input for
  `batch_runner.py`*, **not** SFT data — never approved directly.
- Reasoning markup in assistant targets is flagged (strip unless the provider
  expects reasoning fine-tuning).
- Diversity: low-diversity datasets (one pattern > 80%) are flagged.

Reports are written under `data/` (gitignored): `training_inventory.json`,
`training_quality_report.json`, `training_selected_dataset.json`,
`training_jobs.json`.

## `.env` setup

API keys live in `~/.hermes/.env` (never in code or `config.yaml`):

```
TOGETHER_API_KEY=...
```

The module loads it with the standard Hermes loader (`load_hermes_dotenv`).

## Commands

```bash
# 1. Discover datasets (incl. gitignored data/ trees)
python -m hermes_cli.nlp_training scan

# 2. Validate / approve
python -m hermes_cli.nlp_training validate data/approved/together_train.jsonl
python -m hermes_cli.nlp_training approve   data/approved/together_train.jsonl --only-if-valid
python -m hermes_cli.nlp_training select

# 3. Convert Hermes/ShareGPT trajectories -> Together conversational JSONL
python -m hermes_cli.nlp_training convert data/<run>/trajectories.jsonl
#   -> data/approved/together_train.jsonl (+ together_valid.jsonl when large enough)

# 4. Together dispatch (paid job needs the explicit flag)
python -m hermes_cli.nlp_training together-upload     data/approved/together_train.jsonl
python -m hermes_cli.nlp_training together-create-job data/approved/together_train.jsonl \
    --base-model Qwen/Qwen3-8B --yes-start-paid-training
python -m hermes_cli.nlp_training together-status   <job_id>
python -m hermes_cli.nlp_training together-events   <job_id>
python -m hermes_cli.nlp_training together-metrics  <job_id>
python -m hermes_cli.nlp_training together-cancel   <job_id>
python -m hermes_cli.nlp_training together-download <job_id> --out data/models
```

`together-create-job` runs local gates → Together `check_file()` → upload
(`purpose="fine-tune", check=True`) → duplicate check (local
`data/training_jobs.json` + remote `fine_tuning.list()`) → create. Without
`--yes-start-paid-training` it refuses before any network call.

## Converting batch-runner output

`batch_runner.py` consumes prompt-only JSONL (`{"prompt": ...}`) and writes
trajectories under `data/<run_name>/trajectories.jsonl`. Those trajectories —
**only if they contain high-quality assistant targets** — are converted to
Together conversational JSONL via `convert` (ShareGPT `from/value` → `role/content`,
`human→user`, `gpt→assistant`; failed/partial trajectories are skipped unless
`--allow-partial`).
