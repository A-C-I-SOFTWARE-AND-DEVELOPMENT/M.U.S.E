# Sprint 10 — Skill-Aware Routing, Telemetry, and Cost Control

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Reduce waste and make Hermes observable. Jobs should route to the right workers/skills instead of always paying full fan-out cost, and the cockpit should show time, cost, validation, and quality signals.

## Target architecture

```text
WorkPacket
  -> Skill/Capability Router
  -> Worker selection plan
  -> Budget estimate
  -> Execution
  -> Usage + duration + validation telemetry
  -> Model/worker scorecard update
  -> Cockpit telemetry panel
```

## Files likely touched

- `hermes_cli/orchestrator.py`
- `hermes_cli/kanban_decompose.py`
- `hermes_cli/model_scorecard.py`
- `hermes_cli/scoring.py`
- `agent/account_usage.py`
- `agent/usage_pricing.py`
- `hermes_cli/commands.py`
- `gateway/platforms/api_server.py`
- Android telemetry UI
- tests for routing and budget gates

## Parallel agent lanes

| Lane | Agent | Branch | Mission |
|---|---|---|---|
| A | Routing Agent | `sprint/10-skill-routing` | Implement capability classifier and worker/skill selection. |
| B | Telemetry Agent | `sprint/10-job-telemetry` | Aggregate per-job time, token, cost, worker, validation metrics. |
| C | Budget Agent | `sprint/10-budget-gates` | Add per-job budget policy and ask/refuse decisions when exceeded. |
| D | Android Agent | `sprint/10-android-telemetry` | Add job metrics panel and budget warnings. |
| E | QA Agent | `sprint/10-tests` | Routing fixtures, telemetry aggregation tests, budget decision tests. |
| F | Reviewer Agent | `sprint/10-review` | Review routing correctness and cost guardrails. |

## Routing policy

Start deterministic and explainable. Avoid opaque ML routing first.

Inputs:

- task type;
- repo languages;
- files touched;
- requested outcome;
- risk class;
- previous worker success;
- tool availability;
- estimated cost/time;
- required skills.

Outputs:

```json
{
  "selected_workers": ["claude-code", "codex"],
  "skipped_workers": [{"id": "goose", "reason": "not useful for this task"}],
  "selected_skills": ["repo-audit", "python-tests"],
  "budget": {"max_cost_usd": 1.00, "max_minutes": 20},
  "rationale": "Python code patch with tests; use builder+reviewer lanes."
}
```

## Budget rules

- User can set global and per-job budgets.
- Exceeding hard budget stops execution.
- Exceeding soft budget creates ask verdict.
- Local/free-first routes are preferred when equivalent.
- Paid providers must be visible in telemetry.

## Cockpit telemetry panel

Show:

- elapsed time;
- worker status;
- tests run;
- validation results;
- estimated/actual cost;
- selected worker rationale;
- PR/publish status;
- retry count;
- failure reason.

## Acceptance criteria

- A simple task does not fan out to every worker by default.
- Router decision is logged and visible.
- Per-job cost/time telemetry is recorded.
- Budget overrun triggers decision verdict.
- Cockpit displays useful job metrics.
- Tests cover deterministic routing cases.

## Reviewer prompt

```text
Review routing and telemetry. Ensure routing is deterministic, explainable, and does not hide failed workers. Verify cost telemetry cannot silently omit paid calls and budget gates create decision verdicts.
```

## Definition of done

Hermes runs fewer, better worker lanes by default and shows the user what each job cost in time, money, risk, and validation quality.
