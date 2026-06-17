---
description: Show current MUSE architecture-health metrics without rebuilding docs
allowed-tools: Bash, Read
---

Read the existing quality reports without re-running the pipeline:

```bash
cat docs/_generated/health/summary.json 2>/dev/null || echo "No summary yet — run /phase-complete first."
```

Then read the relevant per-tool reports in `docs/_generated/health/` and
summarize: Ruff violation count, ty diagnostics, complexity grades (radon/xenon),
docstring coverage (interrogate), import-contract status, dead code (vulture), and
TODO count. Do not rebuild — if no reports exist, tell the user to run
`/phase-complete` first.
