# Snapshot — g-navigator-perf

**Intent.** Fix the planner navigator's slow whole-tree walk — the ~306s
"root-at-checkout" cost found by the FU-15 E2E. The navigator's
`RepoIndex.build` walks the repository once with `os.walk`; at a full hermes
checkout it descended into `.claude/worktrees`, which holds full *sibling*
repo checkouts (one per active agent worktree). That subtree alone is six
figures of files, and the walk `stat()`s every file and reads/line-counts
each source/config/doc, so the root build ballooned to minutes.

**Root cause (verified).** `_walk` already pruned an ignore set in place
during `os.walk`, but `DEFAULT_IGNORE_DIRS` did **not** include `.claude`.
The dir-prune logic only dropped `.egg*` and exact name matches, so `.claude`
(and therefore `.claude/worktrees`) was descended. On this machine
`find .claude -type f` = **157,433** files across 22 worktree checkouts.

## Dirs pruned (extends `DEFAULT_IGNORE_DIRS`)

Added the FU-15-required entries that were missing or worth making explicit:

- **`.claude`** — the load-bearing fix; covers `.claude/worktrees` (sibling
  checkouts) and `.claude` scratch. Never index another worktree's tree.
- **`.claude/worktrees`** — explicit nested form (also covered by `.claude`);
  `_walk` now also matches nested `a/b` ignore entries against the path
  relative to the walk root, so callers can target it precisely.
- `.cache`, `.eggs` — small additions alongside the existing
  `.git / node_modules / .venv / venv / __pycache__ / .mypy_cache /
  .ruff_cache / .pytest_cache / dist / build / site-packages / …` set.

No directory that previously contributed *meaningful* index entries is newly
ignored — the pruned dirs are vendored deps, caches, VCS internals, and
duplicate worktree checkouts, none of which were ever useful to index.

## Before / after (measured on the real checkout at `/home/user/hermes-agent`)

| | Files walked | Build time | Ignored paths leaked into index |
|---|---|---|---|
| Before (no `.claude` prune) | **122,836** files traversed by `os.walk` (then stat + line-count each — the FU-15 ~306s) | ~minutes | `.claude/worktrees/**` (duplicate trees) |
| After (this change) | **5,826** genuinely-relevant files | **0.51s** | **0** |

Per-file `os.walk` name iteration alone with the old set is ~0.4s; the FU-15
306s was the *full* `RepoIndex.build` doing `stat()` + line counting over
those 122k files, the bulk being repeated worktree checkouts.

## Changes

- `hermes_cli/jarvis_prime/navigation/repo_index.py`
  - Extend `DEFAULT_IGNORE_DIRS` (adds `.claude`, `.claude/worktrees`,
    `.cache`, `.eggs`).
  - `_walk`: split the ignore set into basenames vs. nested `a/b` forms;
    prune both in place during `os.walk` (the basename path is the hot path;
    nested matching is gated behind a non-empty `nested_ignore`). Widen the
    `ignore` parameter type to `frozenset[str] | set[str]` (clears a
    pre-existing ty diagnostic at the `_walk` call site).
  - `RepoIndex.build`: add an **opt-in** `max_files: int | None = None` cap
    (backstop against pathological trees). Default `None` ⇒ behaviour
    unchanged; only faster because heavy dirs are no longer walked.
- `tests/jarvis_prime/navigation/test_repo_index_perf.py` (new): synthetic
  tmp tree with a fake `node_modules` (200 nested pkgs) and a fake
  `.claude/worktrees` (5 cloned checkouts) plus real source/test/config/doc
  files. Asserts (a) ignored dirs are **never descended** — proven by
  monkeypatching `os.walk` to record visited dirs and asserting none lie in a
  pruned subtree (+ a tight visited-count bound), (b) all real files are still
  indexed with unchanged roles, (c) `max_files` is opt-in, (d) build never
  raises on a missing root.

## Owned files

- `hermes_cli/jarvis_prime/navigation/repo_index.py`
- `tests/jarvis_prime/navigation/test_repo_index_perf.py` (new)
- `docs/launch/followups/g-navigator-perf.md` (this snapshot)

## Branch / base

- Branch: `claude/g-navigator-perf`
- Base commit: `ba2c12df` (origin/main — "Wave B — 10/10 program ledger (#374)")

## Validation

- `uv run ruff check <owned code files>` → **All checks passed!**
- `uv run ty check <owned code files>` → **All checks passed!** (also clears a
  pre-existing `invalid-argument-type` diagnostic at the `_walk` call that was
  present on base `main`; net new diagnostics: **0**).
- `python -m pytest tests/jarvis_prime/navigation/test_repo_index_perf.py -o addopts="" -q`
  → **5 passed**.
- `python -m pytest tests/test_navigation_repo_index.py -o addopts="" -q`
  (pre-existing repo_index suite) → **6 passed** (no regression).

## Constraints honored

- Additive perf only; **public API / return shape unchanged**
  (`build(...)` gains keyword-only `max_files`, default `None`).
- Index semantics preserved: paths still POSIX, relative to root; the same
  real files are indexed (minus heavy ignored dirs that were never meaningful).
- Never-raises preserved (best-effort walk; missing root ⇒ empty index).
- stdlib-only; deterministic, fast, no network.

## Residual risks

- Low. A repo that *intentionally* keeps source under a literal `.claude/`
  directory would no longer index it — but `.claude/` is agent scratch /
  worktrees by convention here, and callers can still override via
  `ignore_dirs` (the parameter only *extends* the default set; it cannot
  un-ignore a default entry). If un-ignoring a default ever becomes needed,
  that is a separate, explicit follow-up.
