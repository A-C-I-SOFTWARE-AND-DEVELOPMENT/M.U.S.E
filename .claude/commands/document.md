---
description: Build the heavy MUSE docs — UML/import/call diagrams, ownership, and Sphinx HTML+PDF
allowed-tools: Bash, Read
---

Run the heavy documentation + diagram build for MUSE / hermes-agent:

```bash
bash .claude/skills/muse-quality/scripts/build_docs.sh
```

Then summarize the generated artifacts:

- `docs/_generated/diagrams/*.mmd` (Mermaid UML) and `*.svg` (Graphviz renders)
- `docs/_generated/ownership/` (git-of-theseus plots)
- `docs/_build/html` and `docs/_build/pdf` (Sphinx), when those tools are present

This build is heavy and is normally run in CI
(`.github/workflows/muse-quality-pipeline.yml`). On Termux or minimal installs,
many tools are skipped gracefully — warn the user and confirm before running
locally if the environment looks constrained. Prefer the Mermaid (`-o mmd`)
diagrams, which work without Graphviz.
