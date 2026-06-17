---
name: muse-quality
description: >-
  Documentation, quality-gate, diagram, and architecture-health pipeline for the
  MUSE / hermes-agent Python codebase. Use when the user asks to lint, document,
  generate diagrams or call/import graphs, check architecture health, run quality
  gates, inventory TODOs, or when finishing a phase / preparing to push. Tiered:
  fast per-file checks (auto, via hook) vs a checkpoint gate vs a heavy full build
  that belongs in CI.
allowed-tools: Bash, Read, Grep, Glob
---

# MUSE Quality & Documentation Pipeline

MUSE / hermes-agent is a large (~2,500+ file) stdlib-heavy Python agent system.
First-party Python lives in top-level packages — there is **no `src/`** layout.
Doxygen is **not** used for Python call graphs here (its Python call/caller graphs
are documented as unreliable). Use the Python-native stack below.

## Source paths

Scripts target the first-party packages via the `QUALITY_PATHS` env var. The
default is the core set:

```
agent tools hermes_cli gateway tui_gateway cron acp_adapter providers second_brain
```

Override per-invocation, e.g. `QUALITY_PATHS="agent hermes_cli" bash scripts/check.sh`.
`plugins/` and `optional-skills/` are partly user-authored and are excluded from
the default heavy passes (matching `pyproject.toml` per-file-ignores).

## Tooling alignment with the repo

- **Lint:** `ruff check` runs against the repo's configured rule set
  (`pyproject.toml [tool.ruff.lint]`, currently `PLW1514`). Do **not** widen the
  rule set or run `ruff format` to make a gate pass — see the ratchet rule.
- **Types:** `ty check` (Astral's checker, the repo standard) — **not** mypy.
  Run advisory, like the repo's own `lint.yml`; it is not a hard gate because the
  existing tree carries diagnostics.
- **Heavy tools** (sphinx, pyreverse, pydeps, code2flow, git-of-theseus, …) are
  not installed locally by default. Every script guards each tool with
  `command -v` and skips it gracefully. The full build belongs in CI.

## When to run which tier

- **Fast (per edit):** handled automatically by the `PostToolUse` hook
  (`scripts/fast_check.sh` — Ruff on the changed file, report-only). Do not
  re-run it manually.
- **Checkpoint (this skill, default):** run `bash scripts/check.sh`. Runs Ruff
  (blocking, config rules), `ty` (advisory), and — when installed — Bandit,
  radon/xenon, interrogate, import-linter, vulture, plus a TODO inventory. Writes
  JSON to `docs/_generated/health/` and a `summary.json` you can parse.
- **Heavy full build:** run `bash scripts/build_docs.sh` ONLY when explicitly
  asked (`/document` or `/phase-complete`) or defer to CI. Generates UML/import/
  call diagrams (Mermaid + SVG), ownership plots, and Sphinx HTML+PDF when those
  tools are present.

## Procedure

1. Run `bash scripts/check.sh`. Read `docs/_generated/health/summary.json`.
2. If the blocking gate fails (Ruff config rules, or a configured strict gate),
   report the specific files and STOP — do not proceed to docs.
3. **Ratchet rule** ("Intelligence proposes; the verifier disposes"): thresholds
   may tighten, never loosen. Never edit `pyproject.toml`, `.importlinter`, or any
   threshold to make a gate pass. Fix the code instead.
4. For diagrams, prefer `pyreverse -o mmd` (Mermaid) so output embeds in Markdown
   and works without Graphviz (important on Termux).
5. Summarize results to the user with the failing gates first.

See `references/tools.md` for exact commands, thresholds, and install notes.
