# FU-D2: Adopt HERMES_RELEASE_GATE_STRICT in launch-gate CI (Wave D G2)

- **Status:** in-review
- **Risk class:** additive — new standalone CI job; no default code path or
  existing required check changes. Becomes blocking only if/when the operator
  adds it to branch protection.
- **Branch:** `claude/fu-d2-launchgate-strict` · **Base:** `main` @ `e283d39ea`
- **PR:** opens as draft on push (title: "ci: adopt HERMES_RELEASE_GATE_STRICT
  in launch-gate (Wave D G2)")
- **Owner-gate required to merge?** no for the additive job itself (non-required
  check); promoting it into branch protection later IS operator-gated.

## Intent (one paragraph)

WC-2 (merged PR #414) shipped the *capability*: `hermes_cli/release_gate.py`
honors `HERMES_RELEASE_GATE_STRICT=1`, turning tool-absent (ruff/pytest
missing) from a soft WARN into a hard FAIL so a stripped release host can
never report "GREEN SHIP with zero tests executed". Its packet
(`docs/launch/followups/wc-2-release-gate-tooling.md:65-72`) explicitly
deferred the CI adoption. Before this change, **no** workflow ran the release
gate at all (verified: `grep -r 'release.gate' .github/workflows/` → no
matches). This packet adds a `release-gate-strict` job to
`.github/workflows/launch-gate.yml` that runs
`muse doctor --release-gate` with `HERMES_RELEASE_GATE_STRICT=1` on every PR.

## Owned files (the ONLY files this task may write)

- `.github/workflows/launch-gate.yml`
- `docs/launch/followups/fu-d2-launchgate-strict.md` (this snapshot)

## Plan (bounded steps)

1. Read `launch-gate.yml` + `tests.yml`; confirm no workflow runs the gate. [done]
2. Add `release-gate-strict` job mirroring tests.yml's setup exactly:
   checkout @ `de0fac2e…` (v6.0.2), ripgrep, `astral-sh/setup-uv` @
   `d4b2f3b6…` (v5, same SHA as tests.yml) with `enable-cache: true`,
   `uv python install 3.11`, `uv venv` + `uv pip install -e ".[all,dev]"`
   (tests.yml's install form — it does not use `uv sync`). [done]
3. Run step: `source .venv/bin/activate && muse doctor --release-gate` with
   `HERMES_RELEASE_GATE_STRICT: "1"` and blanked API keys. The `muse`
   console script is declared in `pyproject.toml` `[project.scripts]`
   (`muse = "hermes_cli.main:main"`), so the editable install provides it;
   the `python -m hermes_cli.main` fallback was not needed. [done]
4. Aggregate wiring decision: left **standalone, non-required**. The
   `aggregate` job is the single check branch protection requires; giving it
   `needs: release-gate-strict` would instantly hard-block every in-flight
   PR on a brand-new gate. A comment in the workflow's advisory-rollup
   REQUIRED list records this deliberately. [done]

## Validation

- `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/launch-gate.yml'))"` → **YAML OK**
- `python3 scripts/scan_secrets.py --base origin/main` → exit 0 (see PR)
- Local sanity run **without** strict
  (`uv run python -m hermes_cli.main doctor --release-gate`) → exit 0,
  `SAFE TO SHIP ✓`, 24 checks green incl. `ruff lint: ruff check . — clean`,
  with exactly one WARN: `fast test slice: pytest unavailable (no uv/system
  interpreter with pytest) — fast slice not run`. That WARN is the precise
  fail-open scenario WC-2 strict mode converts to a hard FAIL — confirming
  both the motivation for this packet and that the CI job must install
  `.[all,dev]` (which provides ruff + pytest) before invoking the gate.

## Residual / follow-on

- The job is not yet in branch protection's required list nor in the
  aggregate's REQUIRED advisory rollup. After a few green PR cycles the
  operator can promote `Release gate (strict tooling)` to required — that
  promotion is a one-line REQUIRED-array edit plus a branch-protection
  setting, and is operator-/owner-gated.
- The gate's fast pytest slice runs launch-critical tests already covered by
  tests.yml; runtime overlap is accepted for now to keep the gate's verdict
  self-contained on one runner.
