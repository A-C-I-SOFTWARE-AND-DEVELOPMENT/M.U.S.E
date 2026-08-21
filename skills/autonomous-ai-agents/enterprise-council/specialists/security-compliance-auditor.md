# security-compliance-auditor

When to use: Authz, secrets, regulated data, trust boundaries, network exposure, or compliance claims.

When not to use: Purely cosmetic UI work or local-only refactors without data/access impact.

Required inputs:
- risk class
- changed files
- threat model or data-flow notes
- test evidence

Required output: Security/compliance finding list with severity, mitigations, and go/no-go verdict.

Verification method: Review diffs and run security-relevant tests or static checks where available.

Owner gate: Yes, with authorization.
