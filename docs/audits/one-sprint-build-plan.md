# One-Sprint Build Plan + Follow-up Tickets

## Built this sprint (deep + tested)

1. `tools/tokenjuice/` — clean-room TokenJuice reducer (MIT rules), pass-through
   safe + fail-open + credential scrub + raw log + config.
2. Integration into `agent/tool_executor.py` (concurrent + sequential), before
   `maybe_persist_tool_result`, behind `tool_output.compaction.enabled`.
3. Config in `cli-config.yaml` / `hermes_cli/config.py`; `[tokenjuice]` metrics.
4. `hermes_cli/background_learner/` — now **ENABLED by default** in `DEFAULT_CONFIG`
   (`enabled=True`, `idle_only=True`, `max_jobs_per_cycle=50`); self-learning
   queue runs real handlers in idle time. (Originally shipped as an allowlisted
   dry-run scaffold; promoted to default-on by commit `a7f5296fd`.)
5. Tests under `tests/` for all of the above; audit docs under `docs/audits/`.
6. `THIRD_PARTY_NOTICES.md` attribution; `.gitignore` raw-log path.

> **Note:** a model registry/router scaffold was planned, but the audit found
> Hermes **already has** a mature `hermes_cli/model_registry.py` +
> `hermes_cli/model_router.py`. The scaffold collided with it and was removed;
> model-routing work is reframed as the eval-gating extension ROUTE-2 below.

## Sprint 2 — deferred items now BUILT (extend-don't-duplicate)

All six follow-ups were subsequently implemented as extensions of existing
systems (verified no parallel architectures):

- **TJ-1 Multimodal compaction** — DONE. `tools/tokenjuice/compact_multimodal_text`
  + `agent/tool_executor.py::_tokenjuice_compact` now compacts only `type=="text"`
  parts, preserving image blocks.
- **ROUTE-2 Eval-gated routing** — DONE. `WorkerEntry.eval_passed/eval_results` +
  opt-in `RouterContext.require_eval_for` in the existing `model_router.py`.
- **EVAL-1 Eval harness** — DONE. `hermes_cli/evals/` deterministic suite feeding
  ROUTE-2; delegates heavy runs to `mini_swe_runner` via an optional runner.
- **LEARN-1 Background-learner live jobs** — ENABLED BY DEFAULT. `hermes_cli/background_learner/
  runner.py` real handlers; code/skill jobs emit owner-gated `ProposalBook`
  proposals; `JobQueue` gained an `executor` hook + `drain()`. Commit `a7f5296fd`
  promoted this to a default-on capability in `DEFAULT_CONFIG`
  (`enabled=True`, `idle_only=True`, `max_jobs_per_cycle=50`) — no longer just a
  scaffold; new installations get self-learning out of the box.
- **MEM-1 Layered memory** — DONE. `agent/memory_layers/` (raw event log +
  provenance + selective retrieval filter + curator bridge to `ProposalBook`
  `MEMORY_PROMOTION`); untrusted content never auto-promotes.
- **INT-1 Integration registry** — DONE. `hermes_cli/integrations/registry.py`
  capability + approval governance for email/SMS/calendar (sends owner-gated, no
  new outbound credential path); complements the existing github/supabase/vercel
  adapters without touching them.

Docs: `docs/self-improvement/policy.md`, `docs/self-improvement/eval-gates.md`.

## Remaining follow-up tickets (interfaces + acceptance criteria, no code)

- **TJ-1 Multimodal-summary compaction** — compact only the text-summary part of
  multimodal tool results, preserving image blocks. Accept: image parts
  untouched; text summary compacted; vision-model path unaffected.
- **MEM-1 Layered memory** — raw event log (append-only, provenance, trust,
  permissions) → bounded working memory → semantic (hybrid keyword+vector,
  rerank, confidence) → knowledge tree (Obsidian-compatible) → episodic session
  search → curator (propose/merge/stale/reject-untrusted). Accept: retrieval is
  selective + auditable; no full-memory prompt dump.
- **ROUTE-2 Eval-gated routing (extend existing)** — add `eval_passed`/
  `eval_results` to `WorkerEntry` and an opt-in `require_eval_for` gate in
  `hermes_cli/model_router.py` so un-evaluated workers can't become the default
  for gated task categories. Extends the existing registry/router — does not
  replace it.
- **EVAL-1 Eval harness** — per-task benchmarks (coding, tool-call correctness,
  retrieval, summarization, hallucination, security, latency/cost, compaction
  quality); gate routing (ROUTE-2) + self-update.
- **LEARN-1 Live background jobs** — implement allowed kinds with real (still
  approval-gated for high-risk) effects; idle scheduler, rate limits, resource
  budgets, audit log, cancellation/backoff.
- **SELF-1 Self-update workflow** — proposal → branch+patch → tests → evals →
  security review → human approval. Docs: `docs/self-improvement/policy.md`,
  `eval-gates.md`.
- **INT-1 Integration registry** — MCP/adapter-based email/SMS/calendar/contacts
  with explicit approval gates; no hard-coded one-offs; scalable registry.
- **REG-1 Registry updater** — scheduled check of curated sources for new
  open-weight models; flags missing/updated; never auto-downloads.

## Exact commands to run next (verification)

```bash
# from repo root
python -m pytest tests/test_tokenjuice_reduce.py tests/test_tokenjuice_integration.py \
  tests/test_tokenjuice_scrub.py tests/test_model_registry.py \
  tests/test_background_learner.py -q
python -m pytest tests/ -q -k "tool_executor or tool_result or budget"
ruff check tools/tokenjuice hermes_cli/model_registry hermes_cli/background_learner
```
