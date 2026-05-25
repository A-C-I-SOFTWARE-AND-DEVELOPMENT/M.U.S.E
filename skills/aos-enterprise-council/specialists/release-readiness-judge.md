# release-readiness-judge

When to use: Pre-release go/no-go, pilot demo readiness, app store handoff, or production launch checks.

When not to use: Early design planning or unmerged local exploratory work.

Required inputs:
- release scope
- test results
- known issues
- rollback plan
- owner constraints

Required output: Go/no-go report with blockers, mitigations, owner gates, and release checklist.

Verification method: Verify tests, artifacts, rollback path, and owner-only walls are satisfied.

Owner gate: Yes, with authorization.
