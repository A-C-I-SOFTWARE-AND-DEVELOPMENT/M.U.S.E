# Snapshot — g-jpmain-extract

**Grain:** `g-jpmain-extract` — carve a cohesive, behavior-preserving
extraction seam out of `hermes_cli/jarvis_prime/__main__.py` (~3365 lines of
CLI dispatch). Move-and-re-import only — **zero behavior change**, `--help`
unchanged.

**Status:** in-review (OWNER-GATED architectural — do **not** merge without the
owner's exact `Yes, with authorization.`)

**Branch:** `claude/g-jpmain-extract`
**Base commit:** `bca93b0a` (`origin/main` — "g-navigator-perf: prune heavy
dirs in the repo navigator walk (#388)")

## Intent

Extract one cohesive, self-contained subcommand group out of the monolithic
`__main__.py` into a sibling module, exposing a small wiring API, with the
subcommand registered and dispatched **exactly as before**. Physical
relocation + re-wire only: no new/removed/renamed subcommand, no flag change,
no output change, no exit-code change.

## Which subcommand moved

**`route`** — "Explain the evidence-backed model route for a task class".

It was chosen as the most cohesive, lowest-coupling candidate among the
suggested options (`context`, `avatar`, `route`):

- Handler `_cmd_route` (was `__main__.py:1810-1835`) depends only on:
  - `hermes_cli.jarvis_prime.task_router` (imported lazily *inside* the
    handler — moves with it, no new top-level import),
  - `sys` (stdlib),
  - `_print_json` (a 1-line `json.dumps` helper — duplicated verbatim into the
    new module to avoid a circular import).
- Parser setup (was `__main__.py:3128-3141`) used only argparse: two flags
  (`--task`, `--json`), one epilog, `set_defaults(func=...)`.
- No other code in the repo references `_cmd_route` or the `route` parser
  object; no existing test drives the `route` subcommand via the CLI, so the
  relocation is invisible to the rest of the tree.

`context` was rejected (larger handler, more flags, GraphRAG/context-handoff
coupling); `avatar` was rejected (already has a dedicated test and more
embodiment surface area). `route` is the tightest seam.

## New module: `hermes_cli/jarvis_prime/cli_route.py`

Wiring API:

- `add_route_parser(subparsers) -> ArgumentParser` — registers the `route`
  subparser (help text, epilog, `--task`, `--json`, `set_defaults(func=...)`)
  byte-for-byte as the inline block did.
- `cmd_route(args) -> int` — the handler, moved verbatim (same lazy
  `task_router` import, same stderr error path returning exit 2, same JSON /
  text branches, same exit 0).
- `_print_json(obj)` — local copy of the `__main__` helper (identical body:
  `print(json.dumps(obj, indent=2, default=str))`).

No circular import: `cli_route` imports only stdlib at module load and
`task_router` lazily inside the handler; `__main__` imports `cli_route`.

## Re-wire proof (in `__main__.py`)

1. New import: `from hermes_cli.jarvis_prime.cli_route import add_route_parser, cmd_route`.
2. The 26-line `_cmd_route` body was replaced by `_cmd_route = cmd_route`
   (the historical name is re-exported so any in-repo reference keeps
   resolving — and the new test pins `__main__._cmd_route is cli_route.cmd_route`).
3. The 14-line inline `p_route = sub.add_parser("route", ...)` block was
   replaced by `add_route_parser(sub)`.

**Behavior-preserving, `--help` unchanged** — verified by byte-diff against a
baseline captured before any edit:

| Check | Baseline | After | Diff |
|---|---|---|---|
| `--help` | exit 0, 78 lines | exit 0 | **identical** |
| `route --help` | exit 0 | exit 0 | **identical** |
| `route --task coding_build --json` | exit 0 | exit 0 | **identical** |
| `route --json` (all routes) | exit 0, JSON list of 10 | exit 0 | **identical** |
| `route --task bogus_class` | exit 2, stderr error | exit 2 | **identical** |

The top-level subcommand list in `--help` is unchanged (still
`{...,model-scorecard,route,context,owner-brief,...}`).

## Test: `tests/jarvis_prime/test_main_extract.py`

Drives the public `main([...])` entry (real `__main__` → `cli_route` wiring):

- `route --task coding_build --json` parses + dispatches, exit 0, payload has
  `task_class == "coding_build"` and routing fields.
- `route --json` (no task) emits a JSON list of routes, exit 0.
- `route --task <unknown>` → exit 2 with `error:` + `Known task classes:` on
  stderr (names a real class).
- `--help` still lists `route` and its help string (argparse `SystemExit`
  code 0).
- `route --help` parses, exits 0, mentions `--task` / `--json`.
- Wiring guard: `__main__._cmd_route is cli_route.cmd_route`.

## Validation

- `uv run ruff check hermes_cli/jarvis_prime/__main__.py hermes_cli/jarvis_prime/cli_route.py tests/jarvis_prime/test_main_extract.py` → **All checks passed!**
- `uv run ty check` on those files → only **the exempt pytest unresolved-import
  false-positive** plus **1 pre-existing `not-iterable` diagnostic** in
  `__main__.py` (present identically on base in-tree: base = 1 diagnostic,
  branch `__main__.py`+`cli_route.py` = same 1 diagnostic). **No new
  diagnostics vs base.** `cli_route.py` adds zero diagnostics.
- `python -m pytest tests/jarvis_prime/ -o addopts="" -q` → **19 passed**.
- `python -m hermes_cli.jarvis_prime --help` → unchanged subcommand list
  (byte-identical to baseline).
- Existing CLI / `task_router` tests
  (`tests/test_oss_model_brain.py`, `tests/test_jarvis_prime_phase2_cli.py`,
  `tests/test_jarvis_prime_avatar.py`, `tests/test_context_handoff.py`,
  `tests/test_aos_council_routing.py`) → **63 passed**.

## Owned files (writable by this grain only)

- `hermes_cli/jarvis_prime/__main__.py` (re-wire: import, `_cmd_route` alias,
  `add_route_parser(sub)` call)
- `hermes_cli/jarvis_prime/cli_route.py` (NEW)
- `tests/jarvis_prime/test_main_extract.py` (NEW)
- `docs/launch/followups/g-jpmain-extract.md` (NEW — this snapshot)

## Residual risks

- Low. Pure physical relocation + re-wire; default behavior is byte-for-byte
  unchanged across every probed surface. The only structural delta is one
  extra import and a small wiring indirection.
- `_print_json` is now duplicated (one line) in `cli_route.py` to avoid a
  circular import. Acceptable and intentional; a future consolidation could
  move shared CLI helpers into a `cli_common` module, but that is out of scope
  for this behavior-preserving grain.

## Gate

Architecturally significant (touches the CLI dispatch structure) →
**OWNER-GATED**. Draft PR opened; do **not** merge to `main` without the
owner's exact `Yes, with authorization.`
