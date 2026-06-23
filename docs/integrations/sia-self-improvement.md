# SIA Self-Improvement Integration

How Hermes/muse uses **Hexo Labs' SIA** (Self-Improving AI,
[github.com/hexo-ai/sia](https://github.com/hexo-ai/sia), MIT) to
empirically improve its own skills, agents, and scaffolds — without
ever letting an autonomous loop touch the live runtime.

> **One-line mental model:** SIA iterates autonomously *in a sandbox on
> a copy*; the winner is promoted into the live tree *only* through an
> owner-gated proposal + PR. Autonomy where it's safe, owner control
> where it matters.

## Why

muse already has a self-improvement loop (`docs/orchestration/
self-improvement-loop.md`) and muse already has an owner-gated
proposal path (`hermes_cli/jarvis_prime/self_update.py`). What was
missing is a *closed, benchmark-evaluated* improver. SIA supplies
exactly that: a meta → target → feedback loop that rewrites a target
agent's scaffold across generations. We wrap it so its output feeds the
gates we already trust.

## Architecture

```
/sia-self-improve <target> --task <benchmark>
   │
   ▼  SiaWorker.prepare_prompt → build SIA task dir from objective + baseline
   ▼  SiaWorker.run    → run `sia` INSIDE isolation sandbox (max_gen bounded)
   │                      .hermes-orchestrator/agents/<job>/sia/<instance>/
   ▼  SiaWorker.collect/score → parse runs/run_*/gen_*/ and score best gen
   ▼  benchmark_gate → PASS only if best candidate beats baseline by margin
   │
   ├─ FAIL/SKIP → no proposal (rationale recorded in the outcome)
   └─ PASS      → self_update.Proposal(NEEDS_OWNER_APPROVAL, evidence=…)
                     │
                     ▼ owner: "Yes, with authorization."
                     ▼ proposal_executor → bounded PR (builder + reviewer)
```

### Components

| File | Role |
|---|---|
| `hermes_cli/workers/sia.py` | `SiaWorker(WorkerAdapter)` — runs SIA in a sandbox; `detect/prepare_prompt/run/collect/score`. Registered as worker id `sia`. |
| `hermes_cli/workers/sia_assets.py` | Vendored task-dir format + templates (attribution in `THIRD_PARTY_NOTICES.md`). |
| `hermes_cli/jarvis_prime/benchmark_gate.py` | Score-based promotion gate (`PASS`/`FAIL`/`SKIPPED`), duck-typed like the eight gates in `gates.py`. |
| `hermes_cli/jarvis_prime/sia_self_improve.py` | Glue: worker → gate → owner-gated `Proposal`. Never applies changes. |
| `skills/sia-self-improve/SKILL.md` | The `/sia-self-improve` playbook. |
| Router branch in `hermes_cli/jarvis_prime/router.py` | Builder-mode "self-improve" intent → the skill, owner-gated. |

## Install

SIA is an **external CLI**, treated exactly like `goose` / `codex` /
`aider` / `claude-code`: muse detects `sia` on `PATH` and shells out to
it. It is deliberately **not** a muse dependency — its transitive pins
conflict with muse' locked environment (e.g. the `openhands` extra pins
`openai==2.8` vs muse' `openai==2.24.0`). Install it in its own
environment:

```bash
pipx install 'sia-agent[claude]'          # Claude Agent SDK backend (recommended)
# or, in a dedicated venv:
pip install 'sia-agent[openhands]'        # multi-provider (Gemini/OpenAI/…)
```

Make sure the resulting `sia` is on `PATH`. If SIA is not installed, the
`sia` worker reports unavailable and the skill is a no-op — nothing breaks.

## Configuration

- **Keys:** `claude` backend reuses `ANTHROPIC_API_KEY`; `openhands`
  backend can use `OPENAI_API_KEY` / `GEMINI_API_KEY`. See `.env.example`.
- **`SiaConfig`** (`hermes_cli/workers/sia.py`): `backend`, `max_gen`
  (hard ceiling 10), `meta_model`, `task_model`, `timeout_seconds`.
  For real work, bump `task_model` to a capable model.

## Usage

See `skills/sia-self-improve/SKILL.md` for the runnable example. The key
guarantee: `run_self_improvement(...)` returns a `SiaImprovementOutcome`;
when `improved` is true, `outcome.proposal.status` is
`NEEDS_OWNER_APPROVAL` and **no file in the live tree has been touched.**

## Safety & honesty

- **Sandboxed:** all SIA writes land under `.hermes-orchestrator/` via
  `isolation.prepare_workspace`. The worker never edits the target.
- **Owner-gated promotion:** only `Yes, with authorization.` moves a
  candidate toward a PR, via `proposal_executor` (which never
  merges/publishes on its own).
- **Cost-bounded:** `max_gen` is capped; each generation runs an agent.
- **No fine-tuning claim:** despite some press coverage, SIA's
  open-source loop rewrites *scaffold/code*, not model weights. This
  integration scopes to scaffold rewriting only.

## License

SIA is MIT; muse is MIT. The runnable SIA code is consumed only via
the `sia-agent` dependency. The adapted task-dir format/design is
attributed in `THIRD_PARTY_NOTICES.md`. No SIA source is copied verbatim.

## Related

- `docs/audits/sia-hexo-integration-research-2026-06-02.md` — the
  research + repo-audit report behind this integration.
- `docs/orchestration/self-improvement-loop.md` — the existing loop.
- `docs/jarvis-verification-gates.md` — the gate model.
