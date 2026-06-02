# Research + Audit: Hexo Labs / SIA → Hermes / JARVIS integration

**Date:** 2026-06-02 · **Scope:** evaluate Hexo Labs' "SIA" open-source
AI for reuse in Hermes/JARVIS; audit this repo as the reference baseline;
design and land an owner-gated integration.

---

## 1. What we researched

The request named "Hexo Labs" and "Sia open-source AI." Research resolved
these to **one target plus a name-collision**:

- **Hexo Labs' SIA** — *Self-Improving AI* (a.k.a. "Self-Improving
  Auto-researcher"). Open-source framework that coordinates three agents
  over generations to autonomously improve an agent's scaffold against a
  task. This is the target.
  - Repo: https://github.com/hexo-ai/sia · Org: https://github.com/hexo-ai
    · Company: https://hexolabs.com ("Accelerating Superintelligence").
  - **License: MIT.** PyPI: `sia-agent` (latest `0.2.1`; releases
    `0.1.1`, `0.2.0`, `0.2.1`). Python `>=3.11`. Extras: `claude`,
    `openhands`, `dev`. Released ~2026-05-28 (days old at audit time).
- **`NXture/Sia`** — an unrelated privacy-preserving personal assistant.
  Name collision only; **not** the target.

### 1.1 How SIA works

Three roles, run in generations until `--max_gen`:

1. **Meta-Agent** — reads the task, generates the initial Target Agent.
2. **Target Agent** — attempts the task, records actions/results.
3. **Feedback/Improvement Agent** — reviews the execution log and
   rewrites the Target Agent (`target_agent.py`) for the next generation.

- **CLI:** `sia --task gpqa --max_gen 5 --run_id 1 --backend claude
  --meta_model haiku --task_model <model>`; `--task_dir ./my-task` for
  custom tasks.
- **Backends:** `claude` (Claude Agent SDK, Claude-only) or `openhands`
  (multi-provider).
- **Task format:** `data/public/task.md` (+ data),
  `reference/reference_target_agent.py`,
  `reference/SAMPLE_TASK_DESCRIPTIONS.md`.
- **Artifacts:** `runs/run_{id}/gen_{n}/` → `target_agent.py`,
  `agent_execution.json`, `improvement.md`.
- **Key modules:** `sia/orchestrator.py` (META/FEEDBACK prompts + loop),
  `sia/context_manager.py`, `sia/util.py`, `sia/tasks/`.
- **Built-in tasks:** `gpqa`, `lawbench`, `longcot-chess`,
  `spaceship-titanic`; MLE-Bench bootstrap via Kaggle.

### 1.2 Two caveats that shaped the design

1. **Harness vs weights.** Press coverage said SIA "updates both the
   harness *and the model weights*," but SIA's own `docs/architecture.md`
   describes **scaffold/code rewriting only** — no fine-tuning in the OSS
   code. We scope to scaffold rewriting; the weights claim is treated as
   unverified/marketing until upstream ships a real path.
2. **Maturity.** Days-old repo → expect churn. Mitigation: optional
   dependency, **pinned** exactly (`0.2.1`), minimal vendoring.

---

## 2. Repo audit (the reference baseline)

Hermes already had every primitive SIA needs. The integration is
*additive*, not a refactor.

| Capability | Where | Used by the integration as |
|---|---|---|
| Worker adapter contract | `hermes_cli/workers/base.py` (`WorkerAdapter` ABC; `detect/prepare_prompt/run/collect/score`), `registry.py`, `__init__.py:builtin_worker_classes` | The seam — SIA is a new worker `sia`. |
| Isolated sandbox | `hermes_cli/workers/isolation.py` (`prepare_workspace` → `.hermes-orchestrator/agents/<job>/<worker>/<instance>/`) | Where SIA iterates on a copy. |
| Owner-gated self-update | `hermes_cli/jarvis_prime/self_update.py` (`Proposal`, `ProposalBook`, `NEEDS_OWNER_APPROVAL`), `proposal_executor.py` | Promotion path for a winner. |
| Verification gates | `hermes_cli/jarvis_prime/gates.py` (`Gate`, `GateResult`, `run_gate_summary`) | New benchmark gate is duck-type-compatible. |
| Existing self-improvement loop | `docs/orchestration/self-improvement-loop.md`, `hermes_cli/self_improvement.py`, `agent/curator.py` | SIA is an *engine* that feeds it candidates + scores. |
| Model meta/task split | `hermes_cli/jarvis_prime/model_brain.py` | Mirrors SIA's `--meta_model`/`--task_model`. |
| Skills auto-slash | `agent/skill_commands.py`, `tools/skills_tool.py` | `skills/sia-self-improve/SKILL.md` → `/sia-self-improve`. |

**License compatibility:** Hermes MIT (Copyright Nous Research) + SIA MIT
→ fully compatible. No copyleft. Reuse is lawful with attribution.

---

## 3. What we reused ("what code we could steal")

Owner decision was **Both** (depend + vendor), done lawfully — refined
during implementation when a dependency conflict surfaced:

- **Depend → external CLI.** We initially added optional `pyproject.toml`
  extras, but `uv lock` proved them unsatisfiable: `sia-agent[openhands]`
  pulls `openhands-ai` which pins `openai==2.8`, conflicting with Hermes'
  `openai==2.24.0`. The correct resolution (and the existing pattern for
  goose/codex/aider/claude-code) is to treat SIA as an **external CLI
  detected on `PATH`** and shell out to it — never co-installed into
  Hermes' locked env. So `uv.lock` is untouched and SIA's runnable code is
  consumed from the user's separate `sia-agent` install, unmodified.
- **Vendor (attributed):** SIA's **task-directory format** and three-role
  design → `hermes_cli/workers/sia_assets.py` (template text is
  Hermes-original; layout/design adapted). Attribution in
  `THIRD_PARTY_NOTICES.md`. No SIA source copied verbatim.

The genuinely valuable idea we adopted is **architectural, not a code
copy**: an evaluator-driven loop that rewrites a scaffold and *measures*
each generation — wired so its output is a proposal, not an action.

---

## 4. Autonomy posture (fact-based recommendation, adopted)

**Sandbox-autonomous iteration + owner-gated promotion.** SIA runs its
full loop autonomously, but only inside `isolation.py` on a copy. The
*winner* is surfaced as a `Proposal` (`NEEDS_OWNER_APPROVAL`) and applied
only via the Claude-builder/Codex-reviewer PR flow on the owner's exact
phrase. This is the only posture consistent with
`docs/jarvis-prime-operating-system.md` and the explicit contract in
`self_update.py` ("JARVIS does NOT silently rewrite his own runtime").

---

## 5. What we built

See `docs/integrations/sia-self-improvement.md` for the architecture and
file map. Summary: `hermes_cli/workers/sia.py` (+ `sia_assets.py`),
`hermes_cli/jarvis_prime/benchmark_gate.py`,
`hermes_cli/jarvis_prime/sia_self_improve.py`, a Builder-mode router
branch, the `/sia-self-improve` skill, `.env.example` notes, this report,
and tests (`tests/test_worker_sia.py`,
`tests/test_jarvis_prime_benchmark_gate.py`,
`tests/test_jarvis_prime_sia_self_improve.py`). SIA is invoked as an
external CLI on `PATH`; no Hermes dependency is added (`uv.lock` untouched).

## 6. Risks & mitigations

- **Upstream churn (days-old):** external CLI (not pinned into our lock);
  minimal vendoring of only the task-dir format.
- **Dependency conflict** (`sia-agent[openhands]` → `openai==2.8` vs
  Hermes' `openai==2.24.0`): avoided entirely by shelling out to a
  separately-installed `sia` rather than co-installing it. This drove the
  external-CLI design.
- **Cost/runtime:** `max_gen` capped at 10; each generation runs an
  agent. Keep small.
- **Safety:** sandbox-confined writes; promotion always owner-gated;
  live runtime never auto-modified (test-enforced).

## 7. Sources

- https://github.com/hexo-ai/sia · https://github.com/hexo-ai · https://hexolabs.com
- https://pypi.org/project/sia-agent/
- https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/
- https://sdtimes.com/ai/hexo-labs-releases-sia-an-open-source-self-improving-ai-that-accelerates-superintelligence/
- Name-collision (not the target): https://github.com/NXture/Sia
