# Sprint 0 — Baseline, Repo Truth, and Program Governance

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Stop expansion, freeze the 10/10 target, and create a delivery operating system so multiple agents can work in parallel without trampling each other.

## Architecture outcome

A living baseline that answers:

- What currently ships?
- Which modules are canonical?
- Which files are protected?
- Which work is allowed during the 10/10 push?
- Which test gates must pass before each merge?
- Which agents own which surfaces?

## Scope

1. Re-run repo inventory against `main`.
2. Confirm the current state of:
   - orchestration workers;
   - gateway API routes;
   - Android cockpit routes and screens;
   - voice primitives;
   - GitHub publisher live/dry-run status;
   - decision/approval policy surfaces;
   - CI and release workflows.
3. Create or update `docs/launch/10_10_PROGRAM_STATUS.md`.
4. Create sprint labels and branch naming convention.
5. Establish a protected-file policy.
6. Define sprint-level acceptance gates.

## Parallel agent lanes

| Lane | Agent | Branch | Mission | Output |
|---|---|---|---|---|
| A | Architecture Agent | `sprint/0-architecture-baseline` | Produce canonical repo truth and module map. | `docs/architecture/current-state-map.md` |
| B | QA Agent | `sprint/0-test-baseline` | Identify reliable test commands and known flakes. | `docs/launch/test-baseline.md` |
| C | Security Agent | `sprint/0-security-baseline` | Identify redactors, owner gates, secrets paths, remote-exec hazards. | `docs/security/10_10_security_baseline.md` |
| D | Android Agent | `sprint/0-android-baseline` | Inventory Android screens, services, API client, storage, permissions. | `docs/android/current-cockpit-state.md` |
| E | Backend Agent | `sprint/0-backend-baseline` | Inventory gateway/orchestrator routes, state stores, job ledgers. | `docs/gateway/current-api-state.md` |
| F | Reviewer Agent | `sprint/0-review` | Review A-E outputs for contradiction. | `docs/launch/sprint_0_review.md` |

## Builder instructions

Each builder must inspect before editing. Do not rely on old docs without checking code. For each module, record:

- file path;
- owner lane;
- public contract;
- current implementation status;
- missing work;
- tests covering it;
- tests missing;
- whether the path is high-risk.

## Protected paths policy

Create `docs/launch/PROTECTED_PATHS_10_10.md` listing paths that need explicit reviewer signoff. Initial candidates:

- security redactors;
- authorization phrase and owner-gated actions;
- Android manifest permissions;
- credential stores;
- gateway auth/pairing;
- GitHub publisher live mode;
- remote bridge configuration;
- installer scripts;
- lockfiles.

## Required commands

Run all that are available in the repo environment:

```bash
uv lock --check
uv run ruff check .
uv run ty check .
uv run pytest -m "not integration" --timeout=30 --timeout-method=signal
```

If full pytest is too expensive, the QA Agent must define a tiered suite:

```bash
uv run pytest tests/test_jarvis_prime_*.py -m "not integration"
uv run pytest tests/test_worker_*.py -m "not integration"
uv run pytest tests/gateway tests/hermes_cli -m "not integration"
```

## Acceptance criteria

- One current-state document exists for each major surface.
- Protected paths are listed.
- Known flaky tests are named with evidence.
- Every sprint file in this package is either accepted or updated against current repo truth.
- A merge queue policy exists.
- No product work starts until this sprint is merged.

## Reviewer prompt

```text
Review Sprint 0 outputs for factual drift, missing protected paths, and false claims. Do not edit implementation code. Produce a contradiction report and a corrected canonical baseline. Flag any sprint in the 10/10 plan that depends on a false assumption.
```

## Definition of done

`main` has a current program baseline and every agent lane knows its branch, scope, tests, and forbidden actions.
