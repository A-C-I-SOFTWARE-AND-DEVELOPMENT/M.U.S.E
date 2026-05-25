# JARVIS Prime — Testing Guide

This is the operating manual for the JARVIS Prime test suite. It
explains where tests live, what each one proves, the Termux
import-time discipline, and how to add a new test when you add a new
JARVIS module.

The runtime spec lives in
[`docs/jarvis-prime-operating-system.md`](jarvis-prime-operating-system.md);
this doc covers tests only.

## Where tests live

Flat convention under `tests/`:

```
tests/test_jarvis_prime_<module>.py
```

One test file per runtime module, named after the module it covers
(e.g. `tests/test_jarvis_prime_modes.py` covers
`hermes_cli/jarvis_prime/modes.py`). **No subdirectory.** A new
`tests/jarvis_prime/` folder would split the namespace and break
the discoverability the flat layout buys.

## Coverage map

The 13 mission-critical behaviors and where each is enforced. File
paths are repo-relative.

| # | Behavior | Test file:line |
|---|---|---|
| a | Six modes classify from intent | `tests/test_jarvis_prime_modes.py:27-62` |
| b | Explicit `Mode` override wins over intent | `tests/test_jarvis_prime_modes.py:64-68` |
| c | Builder mode → Claude Code builder route | `tests/test_jarvis_prime_router.py:26-30` |
| d | Review/Critic intent → Codex reviewer route | `tests/test_jarvis_prime_router.py:33-36` |
| e | Mobile voice defers to focused mode | `tests/test_jarvis_prime_router.py:20-23` |
| f | Owner action requires exact authorization phrase | `tests/test_jarvis_prime_owner_auth.py:41-65` |
| g | Verification gate fails when required fields missing | `tests/test_jarvis_prime_gates.py:29-39` |
| h | Verification gate passes with complete packet | `tests/test_jarvis_prime_gates.py:42-52` |
| i | Memory rejects secrets (AWS, GitHub PAT) | `tests/test_jarvis_prime_memory.py:17-25` |
| j | Durable memory rejects low-confidence claims | `tests/test_jarvis_prime_memory.py:38-49` |
| k | Research brief triggers on low confidence | `tests/test_jarvis_prime_research_and_epistemics.py:31-35` |
| l | `Runtime.handle()` returns a structured turn | `tests/test_jarvis_prime_runtime.py:20-27` |
| m | Tick is a no-op when disabled | `tests/test_jarvis_prime_tick.py` (whole disabled-path section) |

Plus two supporting suites:

- `tests/test_jarvis_prime_work_packet.py` — `WorkPacket` dataclass
  contract (required fields, validation findings, severity rules).
- `tests/test_jarvis_prime_termux_imports.py` — import-time
  discipline (see next section).

## Termux import-time discipline

JARVIS Prime runs on Termux, in slim CI images, and in environments
where `pydantic`, `anthropic`, `openai`, `yaml`, the gateway layer,
and Hermes plugins may not be installed. The package promises (in
`hermes_cli/jarvis_prime/__init__.py:18-21`):

> The package is stdlib-only at import time so it loads in Termux
> and slim CI images. Optional plugin backends (memory, gateway,
> github, model router) are imported lazily inside `runtime` and
> `awareness`.

`tests/test_jarvis_prime_termux_imports.py` enforces this. It runs
each JARVIS module's import in a **fresh subprocess** (not the
parent pytest process, which has already imported many of the
forbidden deps via unrelated tests) and asserts that none of the
following appear in `sys.modules` after the import:

- `pydantic`, `requests`, `httpx`, `yaml`
- `anthropic`, `openai`, `supabase`
- `mem0`, `honcho`
- `gateway`, `plugins`, `hermes_cli.kanban`

If you add a new optional-backend dependency, put the `import`
statement **inside the function that needs it**, not at module top.
See `hermes_cli/jarvis_prime/awareness.py:153-179` for the pattern
(`from plugins.memory import sqlite as memory_sqlite` lives inside
`_collect_memory`).

## Hermetic-test rules

`tests/conftest.py` enforces these before every test:

1. **No credential env vars.** Any env var ending in `_API_KEY`,
   `_TOKEN`, `_SECRET`, etc., plus explicit names like
   `GITHUB_TOKEN`, is unset for every test. Local developer keys
   cannot leak into provider-detection assertions.
2. **Isolated `HERMES_HOME`.** A per-test tempdir; tests reading
   `~/.hermes/*` via `get_hermes_home()` see only their own state.
3. **Deterministic runtime.** `TZ=UTC`, `LANG=C.UTF-8`,
   `PYTHONHASHSEED=0`.
4. **Live-system guard.** `os.kill` and `os.killpg` are blocked
   from targeting PIDs outside the test process subtree. Tests that
   need real signal handling must opt in via
   `@pytest.mark.live_system_guard_bypass`.

Test authors should additionally:

- **Never touch `~/.hermes/` directly.** Use `tmp_path` for every
  file path, and pass it as an argument rather than relying on the
  module default. The tick tests in
  `tests/test_jarvis_prime_tick.py` are the reference pattern.
- **Never make a network call.** If a JARVIS module would call out
  (e.g., `awareness.perceive()` shells to `gh`), monkeypatch the
  module-level callable with a stub returning a canned dataclass.
- **Never assert on a specific Python version, Termux version, or
  wall-clock time.** Use `freezegun` only if absolutely necessary
  (the suite currently doesn't).

## Running the tests

The whole JARVIS suite:

```bash
pytest tests/test_jarvis_prime_*.py -q
```

A single file:

```bash
pytest tests/test_jarvis_prime_tick.py -q
```

If your local environment lacks `pytest-xdist` or `pytest-timeout`
(both in the `pyproject.toml` `addopts`), drop the override:

```bash
pytest tests/test_jarvis_prime_*.py -q --override-ini="addopts="
```

CI uses the full `addopts="-n auto --timeout=30"` from `pyproject.toml`.

## Adding a test for a new JARVIS module

1. Create `tests/test_jarvis_prime_<modname>.py`.
2. Mirror the style of `tests/test_jarvis_prime_gates.py` — flat
   functions, `from __future__ import annotations`, fixtures via
   `pytest.fixture`, paths via `tmp_path`.
3. Add `hermes_cli.jarvis_prime.<modname>` to the
   `JARVIS_MODULES` tuple in
   `tests/test_jarvis_prime_termux_imports.py` so the new module
   gets the import-time isolation check automatically.
4. If your module touches one of the 13 mission behaviors, update
   the coverage map above with the new `file:line` citation.
5. Run the whole JARVIS suite (`pytest tests/test_jarvis_prime_*.py
   -q`) before committing. If a Termux-imports test fails, the
   error message will name the leaked dep so you can move that
   import inside a function.

## What this suite does NOT cover

- **Live LLM provider calls.** Provider routing is tested via the
  `Router` decision dataclass, not by hitting the wire.
- **Real gateway delivery.** The `_notify` channel paths other
  than `"none"` are integration territory and live elsewhere.
- **The Android cockpit.** `apps/android/` has its own test
  fixtures.
- **End-to-end slash-command flows.** Those belong in
  `tests/acp/` and `tests/cli/` (and currently aren't all green —
  see the open `tests/agent/lsp/` and `tests/acp/test_server.py`
  flakes that predate the JARVIS work).
