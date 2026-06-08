# g-fu13-allowhost-cli — expose the cockpit external-host allowlist from the CLI

## Intent

FU-13 follow-on. The cockpit server (`gateway/cockpit/server.py`) already
implements a **fail-closed** host/CIDR allowlist: a *non-loopback* bind requires
the host be named in `serve(allow_external_hosts=[...])` (a host string or CIDR),
*in addition* to `allow_external=True`. The CLI did not expose this — `hermes
cockpit serve` had only `--allow-external`, and `cmd_cockpit` never passed
`allow_external_hosts`, so an operator who wanted a network-reachable cockpit had
no CLI path to satisfy the allowlist (the bind would always fail closed). This
grain closes that gap, additively.

## What changed

Additive CLI only. The server allowlist is **reused, not modified**
(`server.py` untouched).

1. `hermes_cli/main.py` — `cockpit serve` parser: added a repeatable
   `--allow-external-host HOST/CIDR` option (`action="append"`,
   `dest="allow_external_hosts"`, `default=None`, `metavar="HOST/CIDR"`, help
   text noting host-or-CIDR, repeatable, and that it is required in addition to
   `--allow-external` for any non-loopback bind).
2. `hermes_cli/main.py` — `cmd_cockpit` `_serve(...)` call: threaded
   `allow_external_hosts=getattr(args, "allow_external_hosts", None)` through.

### Default-unchanged guarantee

When `--allow-external-host` is absent, the parser default is `None`, and
`_serve(..., allow_external_hosts=None)` is identical to `serve`'s own default
(`allow_external_hosts: Optional[...] = None`). The loopback default bind never
consults the allowlist, so the flag-absent path is byte-identical to pre-grain
behavior. `git diff --stat origin/main -- hermes_cli/main.py` = 12 insertions,
0 deletions.

## Owned (writable) files

- `hermes_cli/main.py` — ONLY the `cockpit serve` argparse parser and the
  `cmd_cockpit` `_serve(...)` call (additive lines only).
- `tests/hermes_cli/test_cockpit_cli_allowhost.py` (new).
- `docs/launch/followups/g-fu13-allowhost-cli.md` (this snapshot, new).

`gateway/cockpit/server.py` was **read only** (allowlist reused, not changed).

## Branch / base

- Branch: `claude/g-fu13-allowhost-cli`
- Base: `origin/main` @ `ba2c12dfd0ff005f8f0a36f5adbaac96edff681d`

## Tests

`tests/hermes_cli/test_cockpit_cli_allowhost.py` (8 tests, hermetic — no real
external socket bind; the real `serve` and the token loader are patched, and the
serve loop is broken via a patched `time.sleep`):

- Parser shape: flag absent → `allow_external_hosts is None`; single host;
  repeatable append preserves order and accepts bare hosts + CIDR.
- Drift guard: a `subprocess` `cockpit serve --help` asserts the **real** CLI
  registers `--allow-external-host` (so the local parser replica can't silently
  diverge from the shipped flag name).
- `cmd_cockpit` threading: parsed list reaches `serve(allow_external_hosts=...)`;
  default (no flag) passes `None` + `allow_external=False` + loopback host.
- Reused server gate still fails closed: a non-loopback host with
  `allow_external=True` but absent from the allowlist (and one outside an
  allowlisted CIDR) still raises `ValueError`.

## Validation

- `uv run ruff check hermes_cli/main.py tests/hermes_cli/test_cockpit_cli_allowhost.py`
  → **All checks passed!**
- `uv run ty check hermes_cli/main.py tests/hermes_cli/test_cockpit_cli_allowhost.py`
  → no new diagnostics. `main.py` has 30 diagnostics on both this branch and
  base `origin/main` (zero introduced); the only test-file diagnostic is the
  exempt `unresolved-import: pytest` false-positive.
- `python -m pytest tests/hermes_cli/test_cockpit_cli_allowhost.py -o addopts="" -q`
  → **8 passed**.
- Regression sweep: `pytest tests/gateway/test_cockpit_loopback_guard.py
  tests/hermes_cli/test_cockpit_cli_allowhost.py` → **27 passed** (the existing
  server allowlist guard tests are unaffected).

## Constraints honored

- Additive CLI only; the existing server allowlist is reused, not touched.
- `server.py` not modified.
- `cmd_cockpit`'s never-raises-surrounding-code posture preserved (the new line
  only adds a kwarg to the existing `_serve(...)` call; no new failure modes).
- stdlib-light (`argparse`, `subprocess`, `unittest.mock`, `pytest` in tests).
- Did **not** edit `docs/launch/10_10_followups_ledger.md`.

## Residual risks

- None to default behavior (flag-absent path byte-identical; verified by
  diffstat + the `test_default_passes_none` test).
- The local parser replica in the test could drift from `main()`; mitigated by
  the real-CLI `--help` subprocess drift guard.
