# JARVIS Model Router — Scorecards

Status: **shipped**. File: `hermes_cli/jarvis_prime/model_scorecard.py`.
Tests: `tests/test_jarvis_prime_model_scorecard.py`.

Routing should be **evidence-backed, not preference-backed.** This module
records per-job scorecards and aggregates them into per-(model, task, risk)
recommendations.

## Scorecard fields (`ModelScorecard`)
model, provider, task_type, risk_class, tokens_in/out, latency_ms,
cost_usd, tests_passed/failed, reviewer_findings, owner_corrections,
hallucination_corrections, accepted_diff_rate, repeated_error_count,
memory_usefulness, created_at. A bounded `score ∈ [0,1]` rewards pass-rate
and accepted-diff-rate and penalizes reviewer findings, owner corrections,
hallucination corrections, and repeated errors.

## Aggregation
`ScorecardBook.recommend(task_type, risk_class=None)` → `(model,
mean_score, samples)` best first. `render()` prints a leaderboard. Local
JSONL persistence, atomic writes, malformed-line tolerance.

## Catalog lanes
The OSS catalog (`config/model-catalog.yaml`,
`docs/ai-intelligence/oss-model-catalog.yaml`) covers the frontier,
Claude/Anthropic, OpenAI/Codex, Google/Gemini, and local OSS lanes
(Qwen coder, DeepSeek, Kimi, GLM, generic OpenAI-compatible endpoint).
The natural-language coder's `ModelLaneHint` carries a routing hint per
packet.

## Hard rule — local OSS models
OSS/local models are **"wired and ready" only as config / local-endpoint
packets** unless weights/server are actually installed and a smoke request
succeeds. `local_endpoint_packet(model, endpoint, server)` emits an
OpenAI-compatible config with `status="wired_not_confirmed"`, **no sign-in
assumption, and no network call.** Do not claim a local model is running
until a smoke completion returns.

## CLI
```bash
python -m hermes_cli.jarvis_prime model-scorecard add --model claude --provider anthropic --task coding --tests-passed 9 --tests-failed 1 --accepted-diff-rate 0.9 --store PATH
python -m hermes_cli.jarvis_prime model-scorecard list --store PATH
python -m hermes_cli.jarvis_prime model-scorecard recommend --task coding --store PATH
python -m hermes_cli.jarvis_prime model-scorecard local-endpoint --model qwen3-coder --endpoint http://localhost:8000/v1
```

## Owner gates / rollback / risks
- Owner gates: none.
- Rollback: additive module; revert branch.
- Risk: recommendations are only as good as recorded samples; cold-start
  buckets fall back to neutral priors.
