# FU-D8: CI hygiene — concurrency-cancel, uv caching, Actions-expression-aware secret scan

- **Status:** in-review
- **Risk class:** additive (CI-only; no default runtime code path changes)
- **Branch:** `claude/fu-d8-ci-hygiene` · **Base:** `main` @ `e283d39ea0df678223eb2392f5b94f6b84af1606`
- **PR:** #<set after open> (draft)
- **Owner-gate required to merge?** no — CI hygiene, strictly additive; auto-merge on green CI is acceptable per contract §6

## Intent (one paragraph)

Wave-D grain G8 closes three CI-hygiene gaps. (1) Eight workflows had no
`concurrency` block, so superseded runs on the same PR/branch kept burning
runner minutes — they now cancel in-progress runs, except the two publishing
lanes (`android-release.yml`, `skills-index.yml` whose `deploy-with-index`
job publishes to GitHub Pages) which queue with `cancel-in-progress: false`
so a mid-publish run is never killed. (2) The `astral-sh/setup-uv` steps in
`tests.yml`, `lint.yml`, and `uv-lockfile-check.yml` ran cache-less on every
run — they now use `enable-cache: true` keyed on `uv.lock` (action SHAs
unchanged). `orchestration-tests.yml` was listed in the grain but uses plain
pip, not setup-uv, so no caching change applies there (it already had
concurrency). (3) The durable fix for PR #423's red secret-scan check: the
`env_name` detector flagged workflow lines like
`APPLE_CERTIFICATE_PASSWORD: ${{ secrets.APPLE_CERTIFICATE_PASSWORD }}`,
which are GitHub Actions *expressions* — references to secrets, never
values. `scripts/scan_secrets.py::_scan_line` now suppresses `env_name`
findings whose entire assigned value matches `^\s*\$\{\{[^}]*\}\}\s*$`,
making the per-line `# pragma: allowlist secret` band-aids unnecessary
going forward. Real values on the same names, and expressions embedded in
longer values, still flag.

## Owned files (the ONLY files this task may write)

- `.github/workflows/android-build.yml`
- `.github/workflows/android-release.yml`
- `.github/workflows/contributor-check.yml`
- `.github/workflows/docs-site-checks.yml`
- `.github/workflows/history-check.yml`
- `.github/workflows/muse-desktop.yml`
- `.github/workflows/osv-scanner.yml`
- `.github/workflows/skills-index.yml`
- `.github/workflows/supply-chain-audit.yml`
- `.github/workflows/tests.yml`
- `.github/workflows/lint.yml`
- `.github/workflows/orchestration-tests.yml` (verified: no change needed — pip-based, concurrency already present)
- `.github/workflows/uv-lockfile-check.yml`
- `scripts/scan_secrets.py`
- `tests/test_scan_secrets.py`
- `docs/launch/followups/fu-d8-ci-hygiene.md` (this snapshot)

> NOT owned: `launch-gate.yml` (another grain), `muse-desktop-release.yml`
> (owned by just-merged PR #423). Neither was touched.

## Plan (bounded steps)

1. Verify each of the 8 listed workflows actually lacks `concurrency`; add
   `group: <workflow>-${{ github.ref }}` with `cancel-in-progress: true`
   (CI gates) or `false` (`android-release`, `skills-index` — publish lanes).
2. Verify setup-uv usage; add `enable-cache: true` +
   `cache-dependency-glob: "uv.lock"` where the action is used
   (tests x2 jobs, lint x2 jobs, uv-lockfile-check x1). Keep SHA pins.
3. Read `_scan_line` / the canonical `env_name` detector
   (`hermes_cli/secrets_policy.py::scan_text`); add the
   Actions-expression suppression in `scripts/scan_secrets.py` only
   (policy module untouched). Add `TestActionsExprSuppression` regression
   tests to the existing `tests/test_scan_secrets.py`: the 4 verbatim
   PR #423 false-positive lines (fetched from `refs/pull/423/head`:
   `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` x2,
   `APPLE_CERTIFICATE_PASSWORD: ...`, `APPLE_PASSWORD: ...`) must not
   flag; a real value (`APPLE_CERTIFICATE_PASSWORD: hunter2real`,
   assembled by concatenation) must still flag; expression + extra
   material must still flag.
4. Validate, snapshot, push, draft PR.

## Validation

- YAML parse loop (`yaml.safe_load`) over all 12 edited/verified workflows → all OK
- `uv run ruff check scripts/scan_secrets.py tests/test_scan_secrets.py` → All checks passed!
- `uv run ty check scripts/scan_secrets.py tests/test_scan_secrets.py` → 1 diagnostic
  (pytest unresolved in minimal venv) — byte-identical on base (`git stash` compare): **no new diagnostics**
- `uv run --with pytest python -m pytest tests/test_scan_secrets.py -o addopts="" -q` → **25 passed** (was 13 on base)
- `python3 scripts/scan_secrets.py --tree` advisory sanity:
  before = 383 blocking / 14715 advisory / 214 env_name lines;
  after = **371 blocking / 14715 advisory / 202 env_name** — the 12 removed are all
  verified `NAME: ${{ secrets.X }}` reference lines (workflows + 2 doc snippets in
  `docs/orchestration/faq.md`), diffed before/after
- `python3 scripts/scan_secrets.py --base origin/main` on this branch → `ok … exit=0`

## Residual / follow-on

- The `# pragma: allowlist secret` band-aids in the merged
  `muse-desktop-release.yml` are now redundant but were left in place —
  that file is owned by PR #423's grain, not this one. A later sweep can drop them.
- `orchestration-tests.yml` could migrate from pip to uv for speed; out of
  scope (behavior change to a CI lane, and the grain only asked for caching
  on existing setup-uv steps).
- 371 pre-existing `--tree` blocking findings remain (advisory audit only;
  the CI gate is diff-mode) — unchanged policy, untouched here.
