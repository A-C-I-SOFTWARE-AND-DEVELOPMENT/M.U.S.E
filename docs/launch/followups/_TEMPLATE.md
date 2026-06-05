# FU-<id>: <title>

- **Status:** planned | building | in-review | merged | blocked | deferred
- **Risk class:** additive | behavior-change (owner-gated) | architecturally-significant (owner-gated)
- **Branch:** `claude/fu-<id>-<slug>` · **Base:** `main` @ `<sha>`
- **PR:** #<n> (draft)
- **Owner-gate required to merge?** yes/no — if yes, awaiting `Yes, with authorization.`

## Intent (one paragraph)

What this closes and why; the live behavior before vs after.

## Owned files (the ONLY files this task may write)

- `path/one.py`
- `tests/path/test_one.py`

> These must be disjoint from every other in-flight task (see the ledger
> ownership map). If a shared file is discovered mid-flight, stop and record
> the collision here.

## Plan (bounded steps)

1. …

## Validation

- `uv run ruff check <files>` →
- `uv run ty check <files>` → (no new diagnostics vs base)
- `uv run --extra all --extra dev pytest <files> -o addopts="" -q` →

## Residual / follow-on

What is intentionally *not* done here, and why.
