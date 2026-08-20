# PROVIDER POLICY

## Discovery, not hard-coding (§14)

Teachers are discovered from `config/model-catalog.yaml` by `foundry/teacher.py`.
40 catalog models; 14 currently env-available on this machine. The plan fills from the local lane
first (privacy + zero marginal cost): measured plan 2026-08-12 —
primary `ollama-local/qwen3-coder-30b`, secondary `ollama-local/gpt-oss-20b`,
local `ollama-local/gemma4-12b`, adversarial `ollama-local/qwen3_5-9b`.

## Teacher ≠ truth (§94)

Every teacher output is candidate data. It must pass `foundry/dataset.py` validation
(schema conformance, dedupe, quarantine) before it can enter a training set. Teacher identity
(provider/model IDs only — never credentials) is recorded per example (§16).

## Upstream's teacher default

`needle generate-data` targets OpenRouter (`deepseek/deepseek-v4-flash`) and requires
`OPENROUTER_API_KEY`. The Foundry wraps this: use `foundry/teacher.py` to select, then either
(a) drive OpenRouter via M.U.S.E.'s existing credential pool, or (b) synthesize with the local
lane and validate deterministically. No training example is accepted without schema validation.

## Privacy

Provider prompts may contain project context. The teacher interface must scrub secrets and
respect the privacy classification before any external call (§56). Local lane is the default for
anything containing unreleased project data.

## Drift (§59/§60)

- Needle upstream drifted under us once already (weights/ → checkpoints/ rename, 2026-08-12).
  Always pin revisions; re-verify hashes before any run (`docs/foundry/NEEDLE_HASHES.json`).
- Provider models change silently; record model IDs in provenance and re-run EVAL_RUNTIME_SHADOW
  when a provider version rolls.
