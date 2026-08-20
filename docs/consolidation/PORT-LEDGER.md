# Consolidation port ledger

Single source of truth for the consolidation of a downstream fork into this repo.
**Single writer.** Read this first on resume — it is how a new session rebuilds state.

## What this is

This repo started from pristine upstream `NousResearch/hermes-agent` at `2d92793045`
(v0.20.4, 2026-08-20). A long-lived downstream fork is being ported *into* it, de-branded,
capability by capability. Generic improvements are shaped as PRs back to upstream.

The fork is frozen and archived; it is a read-only source. It is never merged wholesale.

## Why the port runs this direction

The fork suffered a merge (`d938501dd3`, 2026-08-10) with 756 conflicts resolved in ten
minutes, inconsistently in both directions. **13 files lost ~794 upstream symbols**; three
of them were left as the pre-merge fork blob with the upstream file discarded entirely.
The result was 67 dangling symbols, 13 crashing on import, and the gateway in a restart
loop.

Starting from upstream and porting in means that damage is never inherited.

## Rules

1. **Guards before material.** `tests/test_no_dangling_imports.py` must be green on every
   commit. It is the guard for the exact failure class above.
2. **Seams over core edits.** Upstream policy: *"a plugin that needs to edit core files is
   a design smell."* Only the `port/repair-damaged-deltas` tranche may hand-edit core.
3. **De-brand on the way in**, never "port then rename."
4. **`pr/*` branches cut from `upstream/main`.** If a `pr/*` branch needs anything from
   `integration`, it is misclassified and not upstreamable.
5. **Never port a file the bad merge truncated.** For those, the port source is
   `git diff e2fd462ebe bb78a5bf1c -- <path>` — the *true* fork delta — applied onto
   upstream's current file. Never `git checkout <fork-tip> -- <path>`.
6. **Upstream merges happen between tranches, never inside one.** If such a merge conflicts
   in more than ~20 files, stop and reassess.

## Reference commits

| Commit | Meaning |
|---|---|
| `2d92793045` | Upstream `main` at consolidation start (v0.20.4, 2026-08-20) |
| `e2fd462ebe` | True fork point (2026-05-19) |
| `bb78a5bf1c` | Pre-merge fork tip — **correct source for the true fork delta** |
| `d938501dd3` | The damaging merge (2026-08-10) |
| `a98aee47ce` | Upstream v0.20.0; merge parent #2 |
| `d797a925d3` | Fork tip |
| `8552232a8f` | Fork freeze commit (adds 107 previously-uncommitted files) |

Reference worktrees: `C:\Users\Echer\refs\{muse-tip,muse-premerge,forkpoint,base-v0200}`.
Fork archives: `C:\Users\Echer\Archive\M.U.S.E.git` (fetch source, remote `muse-archive`)
and `C:\Users\Echer\Archive\M.U.S.E-frozen-2026-08-20` (byte-exact, includes gitignored
material and an 87 MB checkpoint deliberately kept out of git).

## Branches

| Branch | Role |
|---|---|
| `main` | Tracks `upstream/main`. Only ever fast-forwarded |
| `integration` | The combined product. Merges `pr/*` and `port/*` |
| `pr/<topic>` | Cut from `upstream/main`. Generic, de-branded, one PR each |
| `port/<topic>` | Cut from `integration`. Fork-specific capability |

## Tranche status

| # | Branch | Status | Notes |
|---|---|---|---|
| T0 | (on `integration`) | **done** | Guard tests. See below |
| T1 | `pr/model-providers` | planned | 5 generic providers + auth env aliases |
| T2 | `pr/tools-generic` | planned | Generic tools; also unblocks `test_output_normalization` |
| T3 | `port/tokenjuice` | planned | Licensing-gated; needs `THIRD_PARTY_NOTICES.md` first |
| T4 | `pr/plugins-batch-{a,b,c}` | planned | ~20 general plugins + provider kinds |
| T5 | `pr/fix-*` | planned | Individual upstream bug-fix PRs |
| T6 | `port/repair-damaged-deltas` | planned | The 13 damaged files. **Only core-edit tranche** |
| T7 | `port/branding-seam` | planned | Must land before T8+ |
| T8–T18 | see plan | planned | Feature tranches |

## T0 — guard tests (done)

Landed on `integration`, de-branded:

| File | Source | State |
|---|---|---|
| `tests/test_no_dangling_imports.py` | fork | **green on pristine upstream** (1 passed, 20s) |
| `tests/smoke/` (9 files) | fork | **green** — 1451 passed, 310 skipped, 45s |
| `scripts/focused_verification.py` | fork | ported as a **scaffold** — see below |

Landed as `c8988af683`, directly on upstream `2d92793045`.

## Baselines on pristine upstream (2026-08-20)

**Every gate compares to these, never to zero.** Upstream is not clean by absolute
measures; the question is only whether *we* made it worse.

| Measure | Baseline | Notes |
|---|---|---|
| `tests/test_no_dangling_imports.py` | 1 passed | The critical gate. Green from the start |
| `tests/smoke/` | 1451 passed, 310 skipped, 0 failed | Skips are missing optional deps, by design |
| `ruff check` (T0 files) | clean | |
| `ty check` | **15,382 diagnostics**, exit 101 | Upstream is not type-clean. Gate = no *new* diagnostics |
| `scripts/run_tests.sh` | _running_ | 3,177 test files, per-file subprocess isolation |

Environment for all port work: `HERMES_HOME=C:\Users\Echer\.hermes-port` (risk R7 — never
let a run touch the production home at `C:\Users\Echer\AppData\Local\hermes`).
Repo venv: `uv sync --extra dev` (pytest 9.1.1, Python 3.11.15).

### Discovery-floor recalibration

`MIN_DISCOVERED` in `tests/smoke/_discovery.py` was calibrated to the fork's module counts
and had to be retuned to upstream's:

| Package | Fork count | Upstream count | Old floor | New floor |
|---|---|---|---|---|
| `hermes_cli` | 619 | 287 | 400 (**failed**) | 200 |
| `gateway` | 120 | 91 | 90 (margin of **1**) | 63 |
| `agent` | 254 | 196 | 180 | 137 |
| `tools` | 162 | 148 | 110 | 103 |

These floors **rise** as tranches land modules. Raise them deliberately; never lower one to
make a red run green.

### Deviations from the plan, and why

Three items the plan assigned to T0 could not land as written. Each was caught by checking
against pristine upstream before copying:

1. **`scripts/focused_verification.py` — `FOCUSED_SET` emptied.** All 11 gated subsystem
   paths are absent from pristine upstream (they arrive in T11/T12). Porting as-is would
   make the gate red from birth, which trains people to ignore it. The mechanism is ported
   with an empty set and an explicit contract: **every tranche that lands an
   architecture-carrying subsystem must append its row in the same commit.**

2. **`tests/characterization/test_output_normalization.py` — deferred to T2.** It imports
   `tools.grading` (fork-only, lands in T2) and references `results.jsonl` and
   `benchmarks/gaia_runner.py`, neither of which exists upstream. It cannot run at T0.

3. **`tests/characterization/test_seams_documented.py` — deferred indefinitely.** It reads
   an external plan file at `../muse-dsh/docs/SEAM_EXTRACTION_PLAN.md` via a
   `MUSE_SEAM_EXTRACTION_PLAN` env var. It guards a fork-specific seam-extraction effort
   that has no meaning in this repo. Revisit only if that effort is revived here.

### Guard allowlist note

`KNOWN_OPTIONAL` in the dangling-import guard names `plugins.memory.sqlite` and
`plugins.github_assistant.api`. Both are absent from pristine upstream, so both entries are
inert today. `github_assistant` arrives in T4 — re-verify the entry is still justified then.

## Deliberate drops

Not ported. Preserved in the fork archive if ever needed.

| Dropped | Why |
|---|---|
| `vercel.json`, `vercel_app.py`, root `api/`, `web/musehq`, `deploy/`, `docker-compose.hosted.yml` | The fork's commercial deployment/business wiring, not an agent capability |
| fork-root `hermes_model_catalog.py` | Superseded by upstream's `hermes_cli/model_catalog.py` seam |
| Fork CI/hygiene churn | Upstream has its own conventions. Exception: `.importlinter` ships as `pr/import-linter` |
| 87 MB `checkpoints/needle2.pkl` | Binary; lives in the filesystem archive, not git |

## Per-file triage

Populated by the Stage 2 classifier (`path, class, gone_syms, lines_*, applies_3way,
tranche`). Classes: `D` (damage — port the true fork delta onto upstream),
`BRANDING` (discard), `PORT-AS-IS`, `PORT-DELTA`.

_Not yet run._
