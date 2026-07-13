# Vendored: LLM-JEPA fine-tune harness (clean-room)

| | |
|---|---|
| Upstream reference | <https://github.com/rbalestr-lab/llm-jepa> |
| Paper | "LLM-JEPA: Large Language Models Meet Joint Embedding Predictive Architectures" — Huang, LeCun & Balestriero, arXiv 2509.14252 (Sept 2025) |
| Upstream license | MIT |
| Nature | **Clean-room implementation of the published objective**, not a byte copy |
| Integrity | `checksums.json` (sha256 per file; CI-enforced) |

## Why clean-room (not a byte-identical snapshot)

Unlike the autoresearch engine — which vendors Karpathy's repo byte-for-byte
from a pinned zip — the files under `vendor/` here are a **clean-room** MUSE
implementation of the LLM-JEPA *objective* described in arXiv 2509.14252, in the
same spirit as the tokenjuice clean-room port (see `tools/tokenjuice/` and
`THIRD_PARTY_NOTICES.md`). LLM-JEPA is a small, well-specified loss
modification, so MUSE ships an auditable reimplementation rather than importing
an external training repo wholesale. The upstream repo above is the reference
for the objective and the credit; this code is original to MUSE and MIT-licensed
alongside it.

## Do-not-edit rule

Everything under `vendor/` is treated as **inert data**: it is never imported by
muse code or tests, never linted / type-checked (ruff- and ty-excluded), and
never mutated in-repo. The engine's fine-tune loop mutates only *copies* inside
disposable workspaces under `$HERMES_HOME/llm_jepa/workspaces/<tag>/`. All muse
adaptations (planning, gating, promotion, the two-view builder) live in the
sibling modules (`engine.py`, `views.py`) and in
`hermes_cli/workers/llm_jepa.py`.

The `checksums.json` manifest pins the reviewed snapshot of these files; the
integrity test (`tests/jarvis_prime/test_llm_jepa_vendor_integrity.py`) fails if
any of them is edited in-repo, so changes go through review + a manifest bump.

## What's vendored

`train.py` (the harness — the loop's only mutable surface, mutated only in
workspaces), `program.md` (loop instructions), `README.md`, `pyproject.toml`
(carries the `pytorch-cu128` index `uv run` needs inside workspaces),
`.python-version`.
