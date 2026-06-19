# Approved Proposal Executor

Status: **shipped**. File: `hermes_cli/jarvis_prime/proposal_executor.py`.
Tests: `tests/test_jarvis_prime_proposal_executor.py`.

Moves `self_update` proposals from approve/reject-only into **safe
execution-plan generation**. It does **not** auto-merge, deploy, or
publish, and makes no GitHub writes.

## Behavior
- Reads an **approved** `Proposal` (`build_execution_plan`). A non-approved
  proposal raises `ProposalNotApproved` (unless `require_approved=False`).
- Packetizes the proposal's diff intent through `natural_language_coder`
  so the plan inherits risk class, owner gates, and validation.
- Produces an `ExecutionPlan`: bounded coding packet, recommended branch
  name, exact test commands (by target area), and a rollback plan.
- High-risk (RC3/RC4) proposals flag `owner_approval_required`.
- `write_artifact(dir)` writes the plan as a JSON artifact (no GitHub).
- `validate_execution_plan(plan)` runs the packet validator.

## Hard rules
- Never merges/deploys/publishes.
- Requires owner approval before any GitHub write; `draft_only=True` by
  default. muse surfaces the plan; the owner decides what executes.

## Owner gates / rollback / risks
- Owner gates: surfaced, never executed.
- Rollback: plan generation is pure; artifacts are local files; revert
  branch.
- Risk: the plan is advisory — a downstream worker still performs the
  bounded edit under the standard builder/reviewer + gate flow.
