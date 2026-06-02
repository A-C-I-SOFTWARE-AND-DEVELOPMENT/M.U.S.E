---
name: sia-self-improve
description: "Run Hexo Labs' SIA self-improving agent in an isolation sandbox to produce a benchmark-beating candidate for a target skill/agent/scaffold, then surface the winner as an owner-gated JARVIS proposal. SIA iterates autonomously on a COPY; promotion into the live runtime always requires owner authorization."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [self-improvement, sia, hexo-labs, benchmark, owner-gated, builder]
    related_skills: [self-improvement-loop, best-coding-tool-mission]
    owner_gated: true
---

# SIA Self-Improvement (owner-gated)

> SIA (https://github.com/hexo-ai/sia, MIT) is a self-improving agent
> that rewrites its own scaffold across generations. Hermes runs that
> loop **inside a sandbox** and treats the output as a *proposal*, not
> an applied change. **JARVIS never silently rewrites his own runtime.**

Load this skill when the owner asks Hermes/JARVIS to "improve yourself",
"get better at <task>", "self-improve a skill/agent", or to "use SIA".

## What it does

1. **Sandbox.** Builds a SIA task directory from the objective + the
   current (baseline) contents of the target and runs the `sia` CLI
   inside `.hermes-orchestrator/agents/<job>/sia/<instance>/`. SIA
   iterates over generations autonomously — but only on a copy.
2. **Score.** Parses each generation's result and scores the best one.
3. **Gate.** The benchmark gate compares the best candidate to the
   baseline. Promotable only if it *beats* baseline by the margin.
4. **Propose (owner-gated).** A promotable candidate becomes a
   `Proposal` with status `NEEDS_OWNER_APPROVAL`. Nothing is applied.
5. **Promote.** On the owner's exact phrase `Yes, with authorization.`,
   the proposal goes through the standard PR flow (Claude builder +
   Codex reviewer). A non-improving candidate yields no proposal.

## Inputs

- **objective** — what "better" means (be concrete and measurable).
- **target_path** — the skill/agent/module to improve (its current
  contents become the baseline).
- **task** — a benchmark name/description used to score generations.
- Optional: **baseline_score**, **min_margin**, **max_gen**, **backend**
  (`claude` | `openhands`), **task_model**.

## Runtime

Use `hermes_cli.jarvis_prime.sia_self_improve.run_self_improvement`:

```python
from hermes_cli.jarvis_prime.self_update import ProposalBook
from hermes_cli.jarvis_prime.sia_self_improve import SiaJob, run_self_improvement
from hermes_cli.workers.sia import SiaWorker, SiaConfig

book = ProposalBook()
worker = SiaWorker(repo_root=".", config=SiaConfig(max_gen=3, backend="claude"))
outcome = run_self_improvement(
    SiaJob(objective="...", target_path="skills/foo/SKILL.md", task="foo-bench"),
    book=book, baseline_score=0.0, min_margin=0.02, worker=worker,
)
print(outcome.gate.outcome, "improved" if outcome.improved else "no change")
if outcome.proposal:               # status == NEEDS_OWNER_APPROVAL
    print(book.render_for_owner())  # owner reviews; nothing applied yet
```

## Guardrails

- **Install required:** SIA is an external CLI (like goose/codex). Install
  it in its own env — `pipx install 'sia-agent[claude]'` — and put `sia` on
  `PATH`. If SIA is absent, the run reports unavailable and does nothing.
- **Cost:** each generation runs an agent. Keep `max_gen` small (≤3 to
  start; hard ceiling 10). Bounded by the worker.
- **No live edits:** this skill never writes the target. The only path
  to a live change is the owner-approved PR flow.
- **Honesty:** SIA's open-source loop rewrites *scaffold/code*, not
  model weights. Don't claim fine-tuning.

## Verification gate reminder

Promotion is an owner-gated action. Surface the proposal, render it for
the owner, and wait for `Yes, with authorization.` before any PR.
