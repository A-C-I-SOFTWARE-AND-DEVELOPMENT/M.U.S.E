# Sprint 5 — Live GitHub PR Publisher Behind Safe Defaults

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Complete the Prompt -> PR leg by making Hermes create real GitHub pull requests from validated patches, while preserving dry-run by default.

## Target architecture

```text
ValidatedPatch
  -> DecisionVerdict(action=github.publish_pr)
  -> if ask: phone approval
  -> GitHub allowlist check
  -> branch creation
  -> commit patch
  -> create PR
  -> record PR URL in job event stream
```

## Files likely touched

- `hermes_cli/github_publisher.py`
- `plugins/github_assistant/client.py`
- `plugins/github_assistant/*`
- `hermes_cli/config.py`
- `gateway/platforms/api_server.py`
- `tests/test_github_publisher*.py`
- `.github/workflows/orchestration-tests.yml`

## Parallel agent lanes

| Lane | Agent | Branch | Mission |
|---|---|---|---|
| A | Publisher Agent | `sprint/5-publisher-core` | Implement default transport for live PRs. |
| B | Security Agent | `sprint/5-publisher-policy` | Repo allowlist, branch prefix, dry-run default, permission checks. |
| C | Gateway Agent | `sprint/5-publisher-events` | Surface publish status/events to cockpit. |
| D | QA Agent | `sprint/5-publisher-tests` | Mock GitHub transport, fixture repo smoke, dry-run tests. |
| E | Docs Agent | `sprint/5-publisher-docs` | Document setup, tokens, allowlists, dry-run/live modes. |
| F | Reviewer Agent | `sprint/5-review` | Review publication safety and rollback behavior. |

## Safety defaults

- `dry_run = true` by default.
- Live publish requires explicit config and environment opt-in.
- Repo must be allowlisted.
- Branch prefix must be controlled, e.g. `hermes/job-<id>`.
- Protected branches are never directly pushed.
- PR body must include validation summary and decision verdict ID.
- Secrets scan must pass before publish.
- Owner approval is required before live publish unless a narrow auto policy is explicitly configured later.

## PR body contract

```markdown
## Hermes Job

- Job: `<job_id>`
- Source session: `<session_id>`
- Decision verdict: `<verdict_id>`
- Validation: pass/fail summary
- Worker selected: `<worker_id>`
- Diffstat: `<files changed>`

## Acceptance criteria

- [ ] ...

## Tests run

```text
...
```

## Rollback

...
```

## Required tests

- dry-run descriptor contains correct branch, title, body, diffstat;
- live transport refuses non-allowlisted repo;
- live transport refuses missing approval;
- branch naming is deterministic;
- PR body redacts secrets;
- transport failure records a recoverable job event;
- duplicate publish is idempotent by job ID.

## Acceptance criteria

- A validated fixture patch can produce a dry-run PR descriptor.
- Mock transport can simulate live PR creation.
- Real transport code is isolated behind allowlist and approval.
- Cockpit sees PR status and URL.
- Re-running publish for the same job does not create duplicate PRs.

## Reviewer prompt

```text
Review GitHub publisher live mode. Verify dry-run remains default, repo allowlist is mandatory, protected branches are never pushed, PR bodies cannot leak secrets, and duplicate publish attempts are idempotent. Confirm every live publish has a DecisionVerdict and audit entry.
```

## Definition of done

Hermes can safely turn a validated patch into a GitHub PR with phone-visible status, while accidental live publishing remains blocked.
