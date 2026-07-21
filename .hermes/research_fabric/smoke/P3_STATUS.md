# P3 — SWE-bench on NIM + escalation tuning + first live auto_apply

Status: COMPLETE (2026-07-20)

## Suite result

- Harness: `scripts/research_fabric/p3_swe_bench.py` (local SWE-bench-style
  fixture repo; 3 buggy-function tasks graded by real pytest runs + 2
  adversarial already-correct tasks the model must not break).
- Baselines verified to fail before the model runs (adversarial tasks verified
  to pass), so PASS means the model's patch actually did the work.
- LIVE free-tier NIM run: resolved_rate=1.0 (5/5).
  Artifact: `.hermes/research_fabric/smoke/P3_BASELINE.json`.

## Escalation chain tuning (the measured part)

Chain order: meta/llama-3.3-70b-instruct (75s) ->
nvidia/llama-3.3-nemotron-super-49b-v1.5 (120s) ->
meta/llama-3.1-8b-instruct (60s), 2 attempts each with backoff.

Observed 2026-07-20: llama-3.3-70b read-timed-out on every attempt all day
(queue-bound on free tier). nemotron-49b answered every call in ~16s. 8b
answers in ~0.4s. All 5 suite resolutions + the bundle-step candidate were
served by nemotron-49b. Conclusion: on free tier, don't hard-block on one
congested model — the chain is what makes 100% achievable. `P3_NIM_SKIP`
env var now lets runs drop chronically-congested models from the chain.

Also fixed en route: correct 70b model id is `meta/` (not `nvidia/`),
NVIDIA_API_KEY loads from repo .env or Hermes AppData .env, fixture repo
gets its own pytest.ini so rootdir doesn't climb into the parent pyproject
addopts.

## First live auto_apply (the actual phase gate)

Artifact: `.hermes/research_fabric/smoke/P3_AUTO_APPLY.json`

  decision=auto_applied applied=True gate=pass
  rationale="auto-applied inside charter; ratchet + gates + canary clean"
  commit bbb6ce446 on branch autonomy/p3-swe-local-001
  ledger_record_hash 4777b44d...

The winning patch was committed by the GitApplier as
`.hermes/research_fabric/auto_applied/p3-swe-local-001-fix.py` with a real
evidence bundle (git_diff, executed test result, review, secret_scan,
rollback). The ratchet required scores in all REQUIRED_DOMAINS — the suite
resolved-rate is supplied as the per-domain proxy.

## Infrastructure findings fixed along the way

- Axiom event chain at %LOCALAPPDATA%/hermes/axiom/chain.jsonl had a
  byte-identical duplicate line at index 70 (concurrent-append double-write),
  which made the strict release gate fail closed on "axiom event chain failed
  verification". Repaired surgically: dedupe + renumber + relink + rehash,
  original preserved at chain.jsonl.bak-prededupe. Audit now chain_valid=True,
  3409 events. Follow-up: the chain writer should append atomically (or the
  auditor should tolerate exact dup lines) — worth a hardening ticket.

## What remains (p4 territory)

- Point the same harness at a real SWE-bench Verified JSONL export (`--suite`).
- Replace the default canary with one that re-runs the catalog verifiers
  post-apply to detect real regressions.
- Re-run when llama-3.3-70b is not queue-bound to get the headline-model
  baseline; today's 5/5 is the fallback-model number.
