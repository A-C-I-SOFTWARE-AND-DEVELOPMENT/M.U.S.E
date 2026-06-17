# muse-quality — tool reference

Exact commands, thresholds, and install notes for the three-tier pipeline.
Read this only when you need the detail; the SKILL.md body is enough for routine
runs.

## Why not Doxygen for Python

Doxygen's call/caller graphs are reliable for C/C++ but documented as inaccurate
for Python (it invents call edges between methods that have no call relationship,
and it does not display file-dependency graphs for Python at all). It also expects
`@param`-style comments rather than idiomatic docstrings. We therefore use a
Python-native stack and never rely on Doxygen for Python call graphs or PDFs.

## Tier 1 — per edit (`fast_check.sh`, via PostToolUse hook)

- Receives the changed file path; only acts on `*.py`.
- `ruff check "$file"` — report-only (stderr → visible to Claude). Always exits 0.
- `MUSE_QUALITY_AUTOFIX=1` enables `ruff check --fix` (configured rules only).
- Sub-second; never stalls or blocks the agent.

## Tier 2 — checkpoint (`check.sh`, via `/phase-complete` or git pre-push)

| Tool | Role | Blocking? |
|---|---|---|
| `ruff check` (config rules) | lint | **yes** |
| `ty check` | types | no (advisory, like the repo's `lint.yml`) |
| `bandit -r` | security | no |
| `radon cc/mi` | complexity / maintainability | no |
| `xenon --max-absolute B --max-modules A --max-average A` | complexity gate | only if `MUSE_QUALITY_STRICT=1` |
| `interrogate` | docstring coverage | no |
| `lint-imports` | architecture contracts | only if `.importlinter` exists **and** `MUSE_QUALITY_STRICT=1` |
| `vulture --min-confidence 80` | dead code | no |
| `rg "TODO\|FIXME\|BUG\|HACK\|XXX"` | TODO inventory | no |

All reports land in `docs/_generated/health/`; `summarize_health.py` writes
`summary.json`. Missing tools are skipped, not errors.

**Ratchet rule.** Thresholds tighten, never loosen. Never edit `pyproject.toml`,
`.importlinter`, or any threshold to make a gate pass — fix the code.

### Import contracts (`.importlinter`)

The repo ships `.importlinter` with direct-coupling boundary contracts derived
from the actual grimp import graph (not aspirational layers — the four core
packages `agent`/`tools`/`hermes_cli`/`gateway`/`cron` are mutually circular
today, so a strict layered order can't yet be asserted). The contracts that
hold and are enforced:

- `second_brain` is a leaf — imports no other first-party package.
- only `hermes_cli` may directly import `tui_gateway`.
- only `hermes_cli` may directly import `acp_adapter`.
- only `agent` and `hermes_cli` may directly import `providers`.

Boundary contracts use `allow_indirect_imports = True` so they constrain direct
coupling only (indirect chains through `hermes_cli` are expected). Locally
`lint-imports` runs advisory via `check.sh`; in CI the `import-contracts` job in
`muse-quality-pipeline.yml` runs it **blocking**. Tighten over time (e.g. add a
layers contract once the core cycle is broken); never loosen to pass.

## Tier 3 — heavy build (`build_docs.sh`, CI-preferred)

- `pyreverse -o mmd` → Mermaid UML (no Graphviz needed; Termux-safe).
- `pyreverse -o dot`, `pydeps`, `code2flow` → SVG (needs Graphviz `dot`).
- `git-of-theseus-analyze` → ownership/evolution plots.
- `sphinx-build -b html`, then `make latexpdf` (LaTeX) or `-b simplepdf`
  (WeasyPrint, pure-Python fallback) — only if `docs/conf.py` exists.

## Install (WSL2 / Ubuntu)

```bash
sudo apt install -y graphviz default-jre ripgrep
uv tool install ruff ; uv tool install ty            # repo standard
pipx install bandit radon xenon interrogate vulture pydeps pylint code2flow
pipx install import-linter git-of-theseus
uv tool install sphinx ; pip install sphinx-simplepdf  # PDF without LaTeX
```

## Termux (Android) limitations

No Docker (no MegaLinter / Structurizr Lite locally); Graphviz is partially
broken. Restrict to: Ruff, `ty`, ripgrep TODO scans, `pyreverse -o mmd`,
interrogate, radon. Push everything heavy to GitHub Actions
(`.github/workflows/muse-quality-pipeline.yml`).

## Optional context engines (MCP)

- **Repowise** (`pip install repowise`, AGPL-3.0) — C4 views, git-history-aware
  dependency graph, code-health score, 9 MCP tools. Closest single tool to the
  combined vision; pip-installable.
- **Depwire** (`npx depwire-cli`, TypeScript/Node) — tree-sitter cross-reference
  graph, ~13 generated docs, 0–100 health score over MCP. Adopt only if you also
  work in TS/JS; its Python parsing is less mature.

Neither produces print-quality PDFs — that is Sphinx's job.
