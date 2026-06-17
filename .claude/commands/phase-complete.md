---
description: Run the muse-quality checkpoint gate and report failures before a phase ends
allowed-tools: Bash, Read
---

Run the checkpoint quality gate for the MUSE / hermes-agent codebase:

```bash
bash .claude/skills/muse-quality/scripts/check.sh
```

Then read `docs/_generated/health/summary.json` and the per-tool reports in
`docs/_generated/health/`.

Report **failing gates first** (Ruff config-rule violations; xenon complexity and
import-linter contracts when running with `MUSE_QUALITY_STRICT=1`), then advisory
findings (ty diagnostics, Bandit, dead code, docstring coverage, TODO count).

Do **not** loosen any threshold in `pyproject.toml`, `.importlinter`, or elsewhere
to make a gate pass — fix the code instead (the ratchet rule). If the blocking
gate passes, say so and suggest `/document` for the full HTML+PDF/diagram build
(normally done in CI).
