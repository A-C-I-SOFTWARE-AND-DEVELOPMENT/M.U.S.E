# Vendored: Karpathy autoresearch

| | |
|---|---|
| Upstream | <https://github.com/karpathy/autoresearch> |
| Snapshot | `autoresearch-master.zip` (March 2026), vendored 2026-06-12 |
| License | MIT — Copyright (c) Andrej Karpathy |
| Integrity | `../checksums.json` (sha256 per file; CI-enforced) |

## Do-not-edit rule

Everything under `vendor/` is **byte-identical upstream payload, committed as
data**. It is never imported by muse code or tests, never linted/type-checked
(ruff-excluded), and never edited in-repo — the autoresearch experiment loop
mutates only *copies* inside disposable workspaces under
`$HERMES_HOME/autoresearch/workspaces/<tag>/`. All muse adaptations (device
shim, governance, cost ceilings) live in the sibling modules
(`platform.py`, `engine.py`, `swarm.py`) and in
`hermes_cli/workers/autoresearch.py` / `hermes_cli/jarvis_prime/autoresearch_improve.py`.

## What's vendored / excluded

Vendored: `prepare.py` (read-only harness), `train.py` (the loop's only
mutable surface — mutated only in workspaces), `program.md` (agent loop
instructions), `README.md`, `pyproject.toml` (carries the `pytorch-cu128`
index `uv run` needs inside workspaces), `.python-version`.

Excluded: `uv.lock` (re-resolved on owner hardware), `analysis.ipynb`,
`progress.png`, `.gitignore` (workspace hygiene is the driver's job).
