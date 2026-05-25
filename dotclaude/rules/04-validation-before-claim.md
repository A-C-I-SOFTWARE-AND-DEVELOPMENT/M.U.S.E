# Rule: Validation Before Claim

No claim of "ready", "done", "shipped", or "production-ready" is valid
without the matching evidence:

| Claim | Required evidence |
| --- | --- |
| "Compiles" | typecheck command + exit code |
| "Lints clean" | lint command + exit code |
| "Tests pass" | test command + exit code + count |
| "Builds" | production build command + exit code |
| "Deploys" | preview / staging URL serving 200s on smoke routes |
| "Secure" | `security-privacy-risk-officer` report with no open CRITICAL/HIGH |
| "Launch-ready" | `qa-launch-validator` gate report all GREEN or justified N-A |
| "Store-ready" | `mobile-release-engineer` checklist all PASS or justified N-A |

If the evidence is missing, the correct phrasing is **"implemented but
not validated"**, with a list of the validations that were skipped and why.
