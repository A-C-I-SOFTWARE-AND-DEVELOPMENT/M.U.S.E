# g-handlers-extract — extract the autonomy handler group into `handlers_autonomy.py`

**Status:** in-review (OWNER-GATED architectural change — draft PR, do **not** merge
without the owner's exact `Yes, with authorization.`)

**Branch:** `claude/g-handlers-extract`
**Base commit:** `bca93b0a` (`origin/main`)

## Intent

Carve a cohesive, **behaviour-preserving** extraction seam out of the
`gateway/cockpit/handlers.py` import hub (~3.9k lines). This is a
**move-and-re-import refactor only** — zero behaviour change, zero route
changes, zero signature changes. It establishes the pattern for future
handler-group extractions from the hub.

## What moved

The **autonomy handler group** (the FU-12 owner-gate cluster — cohesive and
self-contained) was relocated verbatim from `handlers.py` into a new sibling
module `gateway/cockpit/handlers_autonomy.py`:

| Symbol | Kind | Was (origin/main `handlers.py`) |
|---|---|---|
| `autonomy_get` | handler | lines 2166–2180 |
| `_PRIVILEGED_AUTONOMY_LEVELS` | module helper (frozenset) | lines 2188–2190 |
| `_autonomy_raises_locked` | module helper | lines 2193–2208 |
| `autonomy_set` | handler | lines 2211–2288 |
| `autonomy_decisions` | handler | lines 2291–2303 |

The contiguous source block removed from `handlers.py` was the section header
+ these definitions (origin/main lines **2161–2303**). The five symbols are
**AST-identical** to their originals on `origin/main` (verified) — only
surrounding comments/docstrings differ.

## Re-export proof (the move is invisible to callers)

`handlers.py` re-imports the three public handlers at module scope (a
bottom-of-module import, just before `__all__`):

```python
from .handlers_autonomy import (
    autonomy_decisions,
    autonomy_get,
    autonomy_set,
)
```

so every existing reference keeps resolving **unchanged**:

* `server.py`'s route table (`h.autonomy_get` / `h.autonomy_set` /
  `h.autonomy_decisions`) resolves to the *same function objects* now defined
  in `handlers_autonomy` — verified: `handlers.autonomy_set is
  handlers_autonomy.autonomy_set`, and those objects are present in
  `server._ROUTES`.
* `handlers.__all__` still lists `autonomy_get` / `autonomy_set` /
  `autonomy_decisions`, so the module's public surface is byte-identical from a
  caller's view.

**No routes added / removed / renamed. No handler signature changed.**

## No circular import (either order)

`Request` / `JsonResponse` are defined only in `handlers.py` (their canonical
site) and are **not** re-declared in the new module — it imports them back from
`handlers` so the request/response model stays single-sourced. The two-way
relationship (`handlers` re-exports the handlers; `handlers_autonomy` imports
the types) is made cycle-free by placing each cross-import at the *bottom* of
its module and relying on `from __future__ import annotations` (signatures are
lazy strings, so the handlers can be defined before the types are bound — the
types are only needed at call time). Verified in fresh subprocesses importing
**either** module first; `test_handlers_extract.py` pins this.

## Owned files

- `gateway/cockpit/handlers.py` — removed the autonomy block; added the
  bottom-of-module re-export + explanatory comments.
- `gateway/cockpit/handlers_autonomy.py` — **new**; the moved group.
- `tests/gateway/test_handlers_extract.py` — **new**; seam guards.
- `docs/launch/followups/g-handlers-extract.md` — **new**; this snapshot.

`handlers.py`: 3924 → 3810 lines (141 lines of the moved block removed, 27
lines of comment + re-export added).

## Validation

- `uv run ruff check gateway/cockpit/handlers.py gateway/cockpit/handlers_autonomy.py tests/gateway/test_handlers_extract.py` → **All checks passed!**
- `uv run ty check gateway/cockpit/handlers.py gateway/cockpit/handlers_autonomy.py` → **All checks passed!** (base `handlers.py` also passes → **no new diagnostics**).
- `python -m pytest tests/gateway/ -o addopts="" -q` (full gateway slice;
  proves no behaviour change — the live HTTP autonomy suite
  `test_cockpit_autonomy.py` passes unchanged):
  - First run: **5981 passed, 74 skipped, 2 failed**. The 2 failures were
    `test_cockpit_events_stream.py::test_events_stream_delivers_emitted_event`
    and `::test_events_stream_level_filter` — the live-SSE *timing* integration
    tests, which read a real streaming HTTP connection under short poll
    intervals. **They are unrelated to this change** and were confirmed as
    pre-existing, load/order-dependent flakes:
    - this change touches **no** SSE / `event_log` / `server` code (the diff is
      autonomy-handler relocation only — `grep` over the diff hunks finds zero
      SSE lines);
    - the same two tests pass **10/10** in isolation on this branch;
    - a full gateway-suite run on a clean `origin/main` checkout (base
      `bca93b0a`) came back **5974 passed, 74 skipped, 0 failed** — the flakes
      are non-deterministic across runs, not a regression introduced here.
  - Clean re-run on this branch: **5983 passed, 74 skipped, 0 failed** — the two
    SSE tests passed and the suite is fully green. The +9 vs base is exactly the
    9 new tests in `tests/gateway/test_handlers_extract.py`; no autonomy/extract
    test failed in any run.

## Residual risks

- None functional: the extraction is a verbatim relocation + identity
  re-export; behaviour and the public surface are unchanged.
- The only sensitivity is import topology: a future edit that adds a *third*
  cross-import between `handlers` and `handlers_autonomy`, or moves the
  cross-imports off the bottom of either module, could reintroduce a cycle.
  `test_handlers_extract.py` (subprocess import in both orders) guards against
  that regression.

## Merge gating

**OWNER-GATED — architecturally significant.** Open as a **draft** PR; do not
merge to `main` until the owner replies exactly `Yes, with authorization.`
