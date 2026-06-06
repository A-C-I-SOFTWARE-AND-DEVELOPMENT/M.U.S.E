---
name: research-fabric
description: >-
  Bounded-autonomous, verifier-gated self-improvement. Use when the task is to
  run or inspect the research fabric — propose/verify/ratchet a self-improvement,
  grant or check an autonomy charter, run self-play or the evolutionary loop,
  grade a benchmark suite, or read fabric status. Software-first; autonomy is
  charter-gated and "never worsens itself".
---

# Research Fabric

The research fabric is JARVIS's safe self-improvement engine. Its one rule:
**self-improvement tracks the quality of the verifier** — a change is only ever
accepted when an *executable* verifier (tests, op-count, a repo's real test
command) proves it is both correct and strictly better, and auto-apply happens
only inside an owner-signed, revocable charter with automatic rollback.

Full architecture: `docs/jarvis-prime/research-fabric.md`. Constitution clauses
**C33** (bounded-autonomy exception) and **C34** (inviolable verifier wall).

## When to use

- "self-improve X", "evolve a faster/cheaper implementation", "grade this on the
  benchmark", "grant/revoke the autonomy charter", "is autonomy on?", "show the
  fabric status / champion / archive".

## The guarantees (never bypass these)

1. **Correctness is a hard gate** — verified by execution, never by a model's
   say-so. A model's output is always a *candidate*.
2. **Strict ratchet** — meet/beat the champion on every required domain, clear
   the 0.80 floor, beat composite by margin, win the ≥0.55 evaluator gate, pass
   a held-out set, never regress on safety. (`validators.evaluate_ratchet`.)
3. **Hard wall (C34)** — runtime, gates, owner-auth, model registry, routing,
   the verifier/monitor/ledger harness, and the Constitution can NEVER auto-apply.
4. **Charter-gated auto-apply** — only inside an active charter; otherwise an
   owner-gated proposal. Canary re-check auto-rolls-back any regression.
5. **Fail-closed domains** — a domain with no executable verifier is never
   autonomy-eligible (supervised + owner-gated only).

## Commands

```bash
# Inspect
research-fabric status            # ledger/champion/charter/archive at a glance
research-fabric report            # full report + chain integrity
research-fabric domains list      # registered domains + autonomy eligibility
research-fabric champion show
research-fabric archive members | sample-parent

# Improve (verifier-gated; --model wires any OpenAI-compatible endpoint)
research-fabric improve --domain algorithms [--model M --base-url URL]
research-fabric improve --domain swe_local
research-fabric selfplay run | evolve

# Benchmark wall
research-fabric benchmarks run --suite suite.jsonl --gate

# Validate / dry-run a candidate
research-fabric validate --scores '{...}' --holdout '{...}' --eval-win-rate 0.6
research-fabric run --candidate-json cand.json   # dry-run unless --execute

# Autonomy (owner-gated; nonce-bound)
research-fabric charter challenge --allowed-kinds skill_update --risk-ceiling RC2
research-fabric charter grant --challenge-id <id> --phrase "Yes, with authorization. Code: <nonce>"
research-fabric charter status | revoke --charter-id <id>
```

## Owner gates

Granting a charter and any live `--execute` are owner-gated. Auto-apply turns on
ONLY after the owner mints a charter with the exact nonce-bound phrase. Outside an
active charter, **C28** governs: every self-change is an owner-decided proposal.

## Pitfalls

- Trusting a model's output without the executable verifier. Fix: always grade.
- Using a held-out benchmark as a training signal. Fix: train-on-A / gate-on-B.
- Expecting autonomy without a charter. Fix: it falls back to a proposal — by design.
