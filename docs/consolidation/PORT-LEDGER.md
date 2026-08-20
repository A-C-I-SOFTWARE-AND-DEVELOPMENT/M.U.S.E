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
| T1 | `pr/model-providers` | **done** | 5 generic providers. See below |
| T2 | `pr/tools-generic` | **done** | Generic tools, security + grading layers. See below |
| T3 | `port/tokenjuice` | **done** | Compaction library + notice infrastructure. See below |
| T4 | `pr/plugins-batch-{a,b,c}` | **done** | 18 plugins landed, 6 deferred. See below |
| T5 | `pr/fix-*` | **done** | 4 of 5 landed; 1 rejected as dead code. See below |
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
| `scripts/run_tests.sh` | **40 failing test files**, exit 1 | 3,177 files, per-file isolation. Set recorded in `BASELINE-full-suite.md` |

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

## T1 — model providers (done)

`pr/model-providers` @ `bff2764a77`, cut from `upstream/main`, merged to `integration` as
`6232e06390`.

Ported: `plugins/model-providers/{cerebras,groq,mistral,perplexity,together}/`. Zero
branding, zero fork coupling — each imports only `providers.register_provider` and
`providers.base.ProviderProfile`. **No API drift**: every field these profiles pass is
accepted by upstream's current `ProviderProfile`, which has since gained further optional
fields. The plan's flagged risk (that they might reference the fork's
`hermes_model_catalog.py`) does not exist.

Added `tests/providers/test_bundled_openai_compatible_profiles.py` — a profile that fails
to register raises nothing at import time, it just stops resolving. Includes a
registry-wide alias-collision check, since two providers claiming one alias is decided by
registration order and the loser vanishes silently.

Not ported: `needle` — fork-specific, goes with the model-switch seam work.

| Gate | Baseline | After T1 |
|---|---|---|
| dangling imports | 1 passed | 1 passed |
| smoke | 1451 passed / 310 skipped | 1451 passed / 309 skipped |
| `ruff check .` | clean | clean |
| `tests/providers` | 66 passed | 84 passed |
| providers registered | 41 | 46 |

## T2 — generic tools, security, grading (done)

`pr/tools-generic` @ `7a3d6d84f5`, merged to `integration` as `b39360b042`.

Ported: `tools/http_client.py`, `tools/skill_cache.py`, `tools/skill_search_tool.py`,
`tools/security/`, `tools/grading/`. Every dependency already existed here.

Deferred, because their imports do not resolve yet:

| File | Blocked on |
|---|---|
| `tools/graph_query_tool.py` | `hermes_cli.jarvis_prime.graphrag` → the prime tranche |
| `tools/mixture_of_agents_tool.py` | `agent.auxiliary_client`; belongs with the MOA surfaces |
| `tools/lmstudio_tools.py` | three symbols in `hermes_cli/models.py` → the models tranche |
| `tools/security/tests/test_pickle_site_adoption.py` | `research_fabric/autoresearch/vendor/prepare.py` |

### The guard earned its place on day one

`tools/lmstudio_tools.py` passed an import-level scan — `hermes_cli.models` *does* exist
upstream — and then failed the dangling-import guard at merge:

```
tools/lmstudio_tools.py:63  hermes_cli.models.download_lmstudio_model
tools/lmstudio_tools.py:79  hermes_cli.models.lmstudio_download_status
tools/lmstudio_tools.py:92  hermes_cli.models.unload_lmstudio_model
```

All three are fork additions to a class-D file. **Module presence is not symbol presence**
— precisely the gap that produced the original 67 dangling symbols. Caught at merge time
instead of at a user's terminal. The merge was reset and the file deferred.

### The suppression baseline was regenerated, not inherited

The fork's `secret_scan_suppressions.json` had 625 entries, **201 (32%) naming files absent
from this tree**. Its own `test_hand_triaged_paths_still_exist` would have failed on it.
Rebuilt via the documented `python -m tools.security.build_suppressions`: **496
suppressions over 9,845 files**. Three hardcoded `HAND` entries were pruned and commented
in place for restoration by the tranche that lands each file.

**Seven locations are left in the triage queue deliberately** — `cli.py:12106`,
`hermes_cli/cli_agent_setup_mixin.py:113`, `hermes_cli/model_switch.py:{2014,2020,2022}`,
`hermes_cli/prompt_size.py:74`, `hermes_cli/runtime_provider.py:1369`. All are
pre-existing code here, not ported material, and the tool is explicit that a heuristic hit
is a triage aid and never a finding. Suppressing them unread would defeat the purpose.

De-branded: `MUSE_PICKLE_PINS_STRICT`/`_FILE` → `HERMES_PICKLE_PINS_*`,
`.muse-pickle-pins.json` → `.hermes-pickle-pins.json`, `muse-pin` → `hermes-pin`. No
deprecation shim needed — these names never shipped here.

Resolved the T0 deferral: `tests/characterization/test_output_normalization.py` now runs
(128 passed, 2 skipped) because `tools.grading` is present.

| Gate | Baseline | After T2 |
|---|---|---|
| dangling imports | 1 passed | 1 passed |
| smoke | 1451 / 310 skipped | 1463 / 309 skipped |
| tranche surfaces | — | 314 passed, 2 skipped |
| `ruff check .` | clean | clean |

## T3 — TokenJuice (done)

`port/tokenjuice` @ `115e19e1f2`, merged to `integration` as `ccbeb022b3`.

107 files, **zero first-party imports** — a self-contained library that compacts tool
output before it enters the model context.

**The licensing infrastructure landed in the same commit**, which is the whole reason this
was its own tranche. This repo had no `THIRD_PARTY_NOTICES.md`; it does now, and it is
where any future vendored material gets recorded. The 96 rule JSONs are vendored verbatim
from the MIT-licensed `vincentkoc/tokenjuice` set, full license text reproduced,
attribution preserved in `rules/NOTICE.md`. The Python reducer is a clean-room
reimplementation from the public spec — no source from any TokenJuice port, including
GPL-licensed ports, is copied.

Ported 3 of 4 test files (32 passed). `test_tokenjuice_tool_loop` deferred: it imports
`agent.tool_executor`, and wiring compaction into the tool loop is a core edit that
belongs in its own change.

The scanner found 4 new locations — tokenjuice's own credential-redaction patterns in
`scrub.py` and its tests — and classified all four as `redaction_code`. Suppressions
regenerated: **500 over 9,982 files**. TokenJuice adds **no** unsuppressed findings; the 7
in the triage queue are unchanged.

| Gate | Baseline | After T3 |
|---|---|---|
| dangling imports | 1 passed | 1 passed |
| smoke | 1451 / 310 skipped | 1473 / 309 skipped |
| `ruff check .` | clean | clean |

## T4 — plugins (done)

Three stacked branches merged to `integration` (`6c8fa41fd7`, `72dee18cef`, `8e0bd18372`).

| Batch | Landed |
|---|---|
| A — pure/offline | `timeutil`, `webutils`, `codeintel`, `devtools`, `knowledge`, `learning`, `recipe`, `cooking` (73 tests) |
| B — keyed services | `apify`, `finance`, `github_assistant`, `image_search`, `news`, `places`, `sports`, `weather` (136 tests) |
| C — provider kinds | `memory/supabase`, `image_gen/gemini` (+19 tests) |

**Deferred, with cause:**

| Deferred | Why |
|---|---|
| `recommend` | A catalog of the fork's own product surfaces (cockpit, Android, GraphRAG, Termux). Shipping it hands the agent a tool that recommends features the user does not have |
| `supabase`, `vercel` | Import `hermes_cli.action_executors` and `hermes_cli.decision_engine` — the orchestration tranche |
| `asset3d_gen/{meshy,hunyuan3d}` | Need `agent.asset3d_gen_provider` **and** a `register_asset3d_gen_provider` seam on `PluginContext` — a core extension, not a plugin |
| `memory/holographic` | See below |

### "Applies cleanly" is not "is correct" — the holographic case

The triage classified `plugins/memory/holographic/*.py` as `PORT-AS-IS`, and
`git apply --3way` confirmed it applied cleanly. Landing it anyway produced **28 new
failures, 14 of them in this repo's own holographic tests** (`test_holographic_auto_extract`,
`test_holographic_store`, `test_holographic_shutdown_closes_db`).

The fork's holographic work assumes sibling modules that moved on **both** sides since the
fork point, so a textually clean patch lands semantically incompatible code. It also needed
two fork-only additions (`embeddings.py`, `consolidation.py`) that were not in the modified-
file set at all.

Backed out entirely. Holographic needs its own tranche reconciling the whole subsystem.
**The `PORT-AS-IS` class means git can merge the text, not that the result works** — treat
it as a cost estimate, never as a verdict.

### Pre-flight lesson: two AST node types, not one

A first pre-flight pass checked only `from X import Y` (`ast.ImportFrom`) and pronounced
batch A clear. Seven of eight plugins then failed to import because they use plain
`import tools.http_client` — an `ast.Import` node. Batch A became a **stacked** PR on the
tools branch rather than an independent one. Check both node types, or the pre-flight gives
false confidence.

### Guard hardening

`KNOWN_OPTIONAL` in the dangling-import guard is now **empty**. Both inherited entries
(`plugins.memory.sqlite`, `plugins.github_assistant.api`) named modules that do not exist
here and that nothing imports — they allowlisted nothing while reading as though they
covered something. Guard re-run with the stricter list: still green.

### Correcting outbound identity

`image_search`, `places` and `sports` sent an HTTP **User-Agent** naming the fork's
repository. OpenStreetMap Nominatim's usage policy requires a User-Agent identifying the
application; sending a stale third-party URL misattributes the traffic and points operators
at a repo that cannot answer for it. All three now identify this project.

| Gate | Baseline | After T4 |
|---|---|---|
| dangling imports | 1 passed | 1 passed |
| smoke | 1451 / 310 skipped | 1473 / 325 skipped |
| `ruff check .` | clean | clean |

## T5 — individual fixes (done)

Four branches merged (`2b79f561f5`, `9adf511c64`, `bfb114f95b`, `28329e7a29`). Each was cut
from `upstream/main` and verified against the control worktree.

| Fix | Outcome |
|---|---|
| `plugins/platforms/sms/adapter.py` | Landed — **trimmed**. Only the TYPE_CHECKING fix; dropped a `capabilities()`/`_platform_id()` describe surface that no platform adapter implements and nothing calls, in either tree |
| `hermes_cli/mcp_catalog.py` | Landed. Non-interactive install that skips entries whose credentials are absent. 7 tests. CLI-dispatcher tests deferred — they assert routing that differs here |
| `plugins/model-providers/custom/__init__.py` | Landed. Not "multi-provider keys" as planned but an Ollama `/v1` diagnostic: the shim accepts `options.num_ctx` then ignores it, so a user's context window silently stays at 4096 |
| `hermes_cli/models.py` | Landed — **split**. LM Studio helpers kept; Ollama Cloud retirement filter dropped (below) |
| `agent/conversation_loop.py` | **Rejected.** See below |
| `tools/lmstudio_tools.py` | **Restored** — the T2 deferral closing, verified not assumed |

### Rejected: the "Codex entity stickiness" fix is dead code

The plan called this the highest-value upstream contribution (+203 lines). It is not
reachable. `_maybe_route_openai_entity` is called **only from tests**, in *both* trees —
`grep` across the entire fork finds no production call site. `build_usage_record`, bundled
into the same delta, is consumed only by `hermes_cli/orchestrator_parallel.py`, which
belongs to the orchestration tranche.

Porting it would have added 203 lines of unreachable code. It needs a production call site
before it means anything; that the fork never wired it either is worth knowing.

### Split: a hardcoded retirement list had gone stale

`hermes_cli/models.py` bundled LM Studio helpers with an Ollama Cloud retirement filter.
The filter marks **`glm-5` retired while this repo still serves it**, so landing it broke
two passing tests (`TestOllamaCloudMergedDiscovery::test_merges_live_and_models_dev` and
`::test_falls_back_to_models_dev_without_api_key`).

Applied by AST extraction of the wanted functions rather than patch surgery, since the
isolated hunk's line context assumed the earlier hunks. Result: 30 ollama tests pass,
matching pristine upstream exactly.

A hardcoded retirement list is a snapshot that decays. If wanted later, read the live
catalog.

### Working note: clean `__pycache__` after switching branches

`__pycache__/` is gitignored, so `git checkout` removes a directory's tracked files but
leaves the cache behind — and `tests/providers/test_plugin_discovery.py` iterates
directories on disk, so it then reports `cerebras missing __init__.py`. That looks exactly
like a regression and is not one. Clear caches before trusting a disk-iterating test after
a branch switch.

| Gate | Baseline | After T5 |
|---|---|---|
| dangling imports | 1 passed | 1 passed |
| smoke | 1451 / 310 skipped | 1474 / 325 skipped |
| `ruff check .` | clean | clean |

## ⚠ Correction: the de-branding gate cannot grep for "muse"

The plan's Stage 4 acceptance gate was *"`git grep -ni 'muse'` returns zero."* That is
**impossible to satisfy and harmful to attempt.** Upstream itself contains "muse" in **45
files**, none of it fork branding:

| Upstream use | Where |
|---|---|
| **Meta AI's Muse Spark model family** — `muse-spark-1.2`, and `muse` is a live provider **alias** | `plugins/model-providers/meta-ai/`, `agent/models_dev.py`, `hermes_cli/models.py`, `hermes_cli/model_data_policy_guard.py`, `tests/agent/test_auxiliary_client.py` |
| **Muse EEG headband** | `optional-skills/health/neuroskill-bci/` |
| **Substring false positives** | `MEMUSED` (vendored `native/fts5_cjk/vendor/sqlite3.h`), `isSystemUser` (nix), `SpectrumUser`, `FromUserName`, `randomuser`, `museum` |

A blanket `muse` → `hermes` rewrite would rename Meta's models, break the `meta-ai`
provider and its aliases, corrupt a vendored C header, and turn "museum" into "hermeseum".

**The branding gate must instead match fork-specific markers** — `M.U.S.E`, the `MUSE_`
env prefix, `◉ muse`, the `singularity`/`caduceus` skins, `jarvis` — with an explicit
allowlist for the upstream uses above. Bare case-insensitive `muse` is not a usable signal
in this repo.

## Upstream defect found: Windows tests write into the repo root

The full-suite baseline left 14 artifacts in the repo root: `$tmp`, a `%SystemDrive%/`
directory tree containing copied Windows cache files, and 12 files whose names are entire
mangled Windows paths (`C:UsersEcherAppDataLocalTemppytest-of-unknown...`). Tests are
expanding path variables literally and writing relative to the CWD instead of a temp dir.
Cleaned with `git clean`; worth an upstream issue.

## Deliberate drops

Not ported. Preserved in the fork archive if ever needed.

| Dropped | Why |
|---|---|
| `vercel.json`, `vercel_app.py`, root `api/`, `web/musehq`, `deploy/`, `docker-compose.hosted.yml` | The fork's commercial deployment/business wiring, not an agent capability |
| fork-root `hermes_model_catalog.py` | Superseded by upstream's `hermes_cli/model_catalog.py` seam |
| Fork CI/hygiene churn | Upstream has its own conventions. Exception: `.importlinter` ships as `pr/import-linter` |
| 87 MB `checkpoints/needle2.pkl` | Binary; lives in the filesystem archive, not git |

## Per-file triage (done)

`scripts/consolidation/triage_shared_files.py` → `docs/consolidation/triage.csv`.
Run once; do not re-derive by hand.

**699 shared files the fork modified:**

| Class | Count | Meaning |
|---|---|---|
| `PORT-AS-IS` | **650** | The fork's delta applies cleanly onto upstream today |
| `BRANDING` | **28** | Every touched line is a pure rename. Discard |
| `D` | **13** | Damage. Port the true fork delta, never the fork's file |
| `BINARY-ASSET` | **8** | Logos/banners/favicons. Decided by eye, never merged |

The `D` set reproduces the independently-derived damage list **exactly** — same 13 files,
same line counts. Two independent methods agreeing is the reason to trust it.

### "Applies cleanly" is not "should port"

Of the 650 `PORT-AS-IS` files, **285 still mention fork branding** in their diff and need a
keep/discard decision; **364 are brand-free** and safe to port mechanically. The
`carries_brand` column records this per file. The branded ones cluster in `website/` (179),
`web/` (19), `agent/` (17), `hermes_cli/` (16).

### Three classifier bugs found and fixed

Recorded because each produced confident, wrong output that would have mis-sized the port:

1. **Text-mode diff capture corrupted every patch.** Capturing `git diff` with
   `encoding="utf-8", errors="replace"` silently rewrote bytes; the resulting patch no
   longer matched its own blobs, so `git apply --3way` reported conflicts that did not
   exist. Measured on one 5,776-byte diff: 12 bytes lost, clean apply turned into failure.
   **The first run reported 657 files needing hand-porting. The true number is 0** — every
   one of those was this bug. Diffs are now handled as bytes end to end.
2. **Binary assets masqueraded as hand-port work.** `git apply` cannot 3-way a PNG, so 8
   logos and favicons classified as `PORT-DELTA`. They are now `BINARY-ASSET`.
3. **A branding rename read as merge damage.** `\bmuse\b` cannot match inside
   `test_muse_launcher_x` — `_` is a word character, so there is no boundary before `m`.
   One renamed test function therefore looked like a vanished symbol. Symbol comparison now
   uses boundary-free normalization, which is what brought `D` from 14 to the correct 13.
