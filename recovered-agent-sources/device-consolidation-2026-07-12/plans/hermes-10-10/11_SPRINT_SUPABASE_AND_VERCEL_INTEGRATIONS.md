# Sprint 11 — Supabase and Vercel Product Integrations

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Add the hosted-state and deploy-preview integrations needed for a modern personal command center: Supabase for optional cloud-backed state/history, Vercel for deploy previews/logs/env operations.

## Scope boundary

This sprint should not make Hermes dependent on Supabase or Vercel. Both are optional integrations behind config and decision gates.

## Supabase target capabilities

- Auth/session helper tools.
- PostgREST SQL/query wrapper with allowlisted operations.
- Storage upload/download for artifacts if configured.
- Realtime subscription optional.
- Memory backend wrapper conforming to existing memory provider protocol.
- Decision ledger mirror for cockpit history.

## Vercel target capabilities

- Project list/read.
- Deploy current branch or PR artifact.
- Fetch preview URL.
- Tail build/runtime logs.
- Read/write env vars behind approval gate.
- Cancel/rollback deployment behind approval gate.

## Files likely touched

- new `plugins/supabase/`
- new `plugins/memory/supabase/`
- new `plugins/vercel/`
- `hermes_cli/config.py`
- `tools/lazy_deps.py`
- `gateway/platforms/api_server.py`
- Android PR/deploy preview chips
- tests for plugin clients with mocks

## Parallel agent lanes

| Lane | Agent | Branch | Mission |
|---|---|---|---|
| A | Supabase Agent | `sprint/11-supabase-plugin` | Implement Supabase plugin skeleton and safe query/storage tools. |
| B | Memory Agent | `sprint/11-supabase-memory` | Implement optional Supabase memory/ledger mirror. |
| C | Vercel Agent | `sprint/11-vercel-plugin` | Implement deploy/preview/log/env/cancel toolset. |
| D | Security Agent | `sprint/11-integration-policy` | Env var approval, service-role handling, log redaction, allowlists. |
| E | Android Agent | `sprint/11-android-preview-ui` | Show preview URL, deploy/log status chips. |
| F | QA Agent | `sprint/11-tests` | Mock API clients, config tests, redaction tests. |
| G | Reviewer Agent | `sprint/11-review` | Review credential boundaries and destructive operations. |

## Security policy

- Supabase service role key is never sent to Android.
- Vercel token is never sent to Android.
- Env var writes require ask verdict.
- Deployment cancellation/rollback requires ask verdict.
- Logs are redacted before cockpit display.
- Supabase data sync is opt-in and local mode remains fully supported.

## Acceptance criteria

- Supabase plugin can be configured and health-checked without breaking local mode.
- Decision ledger can optionally mirror redacted entries to Supabase.
- Vercel plugin can produce a preview URL in dry-run/mock tests.
- Vercel env writes are gated.
- Android shows preview/deploy status when present.
- Missing credentials degrade with actionable diagnostics.

## Reviewer prompt

```text
Review Supabase/Vercel integrations. Verify no service role or Vercel token can reach Android logs/UI, destructive operations are gated, local/private mode still works, and all external calls are mockable in tests.
```

## Definition of done

Hermes can optionally connect product jobs to hosted state and deploy previews without compromising local-first operation.
