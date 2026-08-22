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
| T6 | `port/repair-damaged-deltas` | **done** | The 13 damaged files. **Only core-edit tranche**. See below |
| T7 | `port/branding-seam` | **done** | Branding gate live and green. See below |
| T8a | `port/moatool` | **done** | MoA fan-out tool, rebased onto upstream's MoA |
| T10 | `port/rooms` | in progress | Unblocked by T-SEAM |
| T12a | `port/prime` | in progress | prime navigation + graphrag as a plugin |
| T14a | `port/skills` | **done** | Enterprise council skills, 354 files to 78 |
| T-SEAM | `port/seam` | **done** | Extension points. Unblocks T10 and future panels |
| T9/T11/T13/T15–T18 | see below | scoped | Measured against upstream; most dropped. See below |

## T6 — repair damaged deltas (done)

The only tranche permitted to hand-edit core. All 13 class-D files resolved.

**Method.** Each file's port source is the true fork delta
(`git diff e2fd462ebe bb78a5bf1c -- <path>`), applied onto upstream's current file —
never the fork's post-merge blob. Every candidate was analysed once, then reviewed a
second time by a pass whose only instruction was to **refute** it.

**43 claims raised, 24 survived, 19 killed.** The refutation stage is the reason to
trust the result; a sample of what it caught:

| Killed | Why |
|---|---|
| `config.py` "stop echoing credential characters" | Not a leak. The line keeps `U+{ord(ch):04X}`, which uniquely determines the character it claimed to redact |
| `doctor.py` connectivity/OAuth-fallback row | Breaks a currently-passing test (`test_run_doctor_ignores_invalid_direct_keys_when_oauth_fallback_is_healthy`) |
| `doctor.py` punch-list narrowing | Regresses under `provider=auto` and `provider=moa`, the most common config values |
| `setup.py` `setup_orchestrator_trio()` | References a module that does not exist here yet. Deferred to T11, where it arrives with its feature |
| `web_server.py` `POST /api/env/test` | Dead on arrival — no call site, and the proposed code was not the fork's |
| 4 of 8 proposed `cli.py` ty suppressions | ty does not flag those lines; landing them is a net lint **regression** (`unused-ignore-comment`) |
| `gateway.py` `gateway.auto_start` | Depends on unported material. Deferred |

### What landed

| File | True delta | Outcome |
|---|---|---|
| `hermes_cli/banner.py` | 65/31 | **Discarded** — 100% branding (the ASCII wordmark) |
| `hermes_cli/slack_cli.py` | 9/9 | **Discarded** — pure rename |
| `hermes_cli/auth.py` | 37/37 | 3 provider env aliases (`ZHIPU_API_KEY`, `MOONSHOT_API_KEY`, `NIM_API_KEY`/`NVIDIA_NIM_API_KEY`). The delta's two "restored" functions already existed upstream |
| `hermes_cli/uninstall.py` | 16/16 | 8 `ty: ignore` on `winreg` call sites (absent off-Windows) |
| `cli.py` | 466/178 | `/model` surfaces inventory-load failures instead of masking them; `TypeError` on unhashable `min_coding_score`; 22 implicit-Optional params; `value: any` → `Any`; 4 ty suppressions |
| `hermes_cli/doctor.py` | 316/63 | Azure Foundry probe no longer passes `url=None` to `httpx.get`; Azure authenticates with `api-key` not Bearer; Kimi row honours `KIMI_CODING_API_KEY`/`MOONSHOT_API_KEY`; `--fix` seeds `DEFAULT_SOUL_MD` instead of a fourth divergent template |
| `hermes_cli/gateway.py` | 324/41 | Windows arm restored to the "Start it now?" recovery dispatch; `hermes gateway ensure`; one load-bearing ty suppression for `ctypes.windll` |
| `hermes_cli/web_server.py` | 143/13 | Swagger UI moved to `/api-explorer` |
| `hermes_cli/config.py` | 540/84 | Inline `open()`/`os.fdopen()` encoding kwargs; `redact_key()` accepts `Optional[str]` |
| `hermes_cli/main.py` | 1585/338 | 8 argparse ty suppressions |
| `hermes_cli/setup.py` | 92/45 | Headless guidance names `ANTHROPIC_API_KEY`; 2 implicit-Optional |
| `hermes_cli/commands.py` | 100/15 | Gate narrowing before `.split()`; widened tuple annotations |
| `gateway/run.py` | 486/133 | `_gateway_runner_ref` annotation corrected; implicit-Optional on `session_key` (×3) and `TurnRunner.progress_callback` |

### The Swagger/SPA collision, recorded because it is easy to re-introduce

FastAPI registers its docs route inside `FastAPI.__init__` → `setup()`, long before
`mount_spa()` installs the SPA catch-all. It therefore wins the match-order race and
served Swagger UI on every hard load, refresh, or deep link of `/docs` — shadowing the
SPA's own Documentation page. Fixed with `docs_url="/api-explorer"`. The fork's
`redoc_url=None` was **not** ported: nothing collides at `/redoc`.

### Deviation from strict fork-delta-only, taken deliberately

One of the three `session_key` implicit-Optional fixes lands on `_run_agent_inner`, an
**upstream-only** function created after the fork point that carries the identical
defect. Annotation-only, no runtime effect. Recorded here rather than silently included.

### Gate results

Every measure compared against pristine upstream, never against zero.

| Measure | Result |
|---|---|
| `ruff check .` | clean |
| dangling-imports guard + `tests/smoke/` | 1475 passed, 325 skipped, **0 failed** |
| doctor/config/setup/commands/gateway/web_server test files | 26 failed, 812 passed, 24 skipped — a **byte-identical failure set** to pristine upstream |
| gateway files + dangling guard, after `gateway ensure` landed | 22 failed — **identical** to the control's gateway subset |
| `ty` | `main.py` 50 → 18, `doctor.py` 7 → 1, no `unused-ignore` at any new site |
| Runtime | `hermes --version` ok; `hermes doctor` runs end to end; `hermes gateway ensure` present in `gateway --help` |

The 26 pre-existing failures are Linux `systemd`/`launchd`/XDG-runtime paths and Windows
symlink-permission tests that cannot pass on this host. They fail identically on pristine
upstream, which is the only thing that matters.

## T7 — branding seam (done)

### The plan's marker list was wrong, and it would have produced an unusable gate

`PLAN.md` proposed gating on `M.U.S.E`, `MUSE_`, `singularity`, `caduceus` and `jarvis`.
Three of those mean something else entirely in this repo:

| Marker | Plan assumed | What it actually is here | Hits |
|---|---|---|---|
| `singularity` | a fork skin | the **Singularity/Apptainer container runtime**, an upstream terminal backend beside docker/modal/ssh/daytona | 181 |
| `caduceus` | "the MUSE serpent glyph" | `HERMES_CADUCEUS` — upstream's **own** ASCII art. The caduceus is Hermes's staff | 10 |
| `jarvis` | the fork's `jarvis_prime` | openWakeWord's built-in `hey_jarvis` wake word, a cron incident note, a desktop test fixture | 34 |
| `M.U.S.E` | fork branding | fork branding — the only one that was right | 2 |

This is the same class of error already recorded for bare `muse`. **Judge what the string
means, never the substring.** The skins question resolved itself: the fork's `singularity`
skin was never ported here, and `caduceus` is upstream's own.

### The guard

`tests/test_no_fork_branding.py` — 15 markers over git-tracked file **content and paths**,
~2.9 s across 10,099 files.

**Scanning paths is not incidental.** A ported `hermes_cli/jarvis_prime/` package whose file
contents are perfectly clean is invisible to a content-only scan — and T12 is 426 such files.
Same for `contributors/emails/<address>`, where the identity is the filename and there is
nothing to grep.

42 upstream-legitimate strings and 9 upstream-legitimate paths are pinned as **executable
negative controls**. If a future widening starts eating `muse-spark`, the Singularity backend
or `HERMES_CADUCEUS`, the guard fails loudly rather than teaching people to ignore it.

**Documented residual gaps** — recorded so nobody "fixes" them into false positives: bare
title-case `Muse` (35 legitimate lines) and bare lowercase `muse` (~110) cannot be gated. A
context-negated attempt produced 73 false positives across 19 files. `HERMES_MUSE_MODE` also
escapes, since `` cannot hold after `_`. Those spellings still need human review.

### The 32 leaks it found

| Marker | Sites | Notes |
|---|---|---|
| `echerd27-design` | 7 (from T4) | The fork owner's GitHub org. The worst is `plugins/github_assistant/tools.py:150` — a **tool-schema `description`**, so it shipped into the model's tool context at runtime and would be echoed back as the suggested repo owner. Now `NousResearch` |
| `M.U.S.E` | 2 (from T2) | Fork product name in `tools/security/` docstrings |
| `Work Packet §…` | 23 | Citations to a fork-private planning document that does not exist in this repo — dangling for any reader |

Two could not be fixed as isolated lines:

- `tools/grading/README.md` **transcribes the literal banner** emitted by
  `tools/grading/validator.py:337`. Changed together, so the documented sample output stays
  truthful.
- `tools/security/secret_scan_suppressions.json` is **generated**. De-branded the constant in
  `secret_scan.py` and re-ran `python -m tools.security.build_suppressions` rather than
  hand-editing. Verified afterwards that all 500 entries are byte-identical modulo the
  re-stamped `added_at`.

### `hermes_cli/env_compat.py` — landed early, deliberately

The legacy `MUSE_*` → `HERMES_*` shim, with an **empty table by design**: no ported material
carries a legacy name yet.

It landed now rather than at T11 for a structural reason. The shim must run at process start,
and installing a process-start hook is a **core edit** — and T6 was the last tranche permitted
to make one. Wiring it now cost two lines each in `hermes_cli/main.py` and `gateway/run.py`;
wiring it at T11 would have required breaking the seams-over-core-edits rule. Recorded here as
a deliberate exception rather than smuggled in.

`tests/hermes_cli/test_env_compat.py` pins that both hooks stay in place — without them the
shim is dead code and every legacy variable silently stops working, which is exactly the
failure the shim exists to prevent.

**Contract for T8–T18:** every tranche that ports material carrying a `MUSE_*` name adds its
rows to `LEGACY_ENV_ALIASES` *in the same commit* as the rename, and registers the legacy name
in `_DEPRECATED_ENV_VARS` in `doctor.py`. Never regex-rename across the tree.

### Gate results

| Measure | Result |
|---|---|
| `ruff check .` | clean |
| `tests/smoke/` + both guards | 1531 passed, 326 skipped, **0 failed** |
| branding guard alone | 54 passed — every negative control green, zero false positives |
| `env_compat` + guards | 68 passed |
| github_assistant + security + grading + characterization | 290 passed, 2 skipped |
| Runtime | `hermes --version` ok |

From here the **fast gate gains `tests/test_no_fork_branding.py`**, so no later tranche can
re-introduce fork branding silently.

## T8-T18 — measured, and mostly not what the plan said (scoping done)

Every remaining tranche was scoped against what upstream **actually ships**, because the
plan's estimates had already been materially wrong three times. They were wrong at least
five more times. The measurements below supersede `PLAN.md` wherever the two disagree.

### Two systemic traps that invalidate directory-level planning

**1. The CRLF trap.** The fork checkout is CRLF, upstream is LF, so a raw `diff` reports
every file as 100% changed and inflates volume roughly **60x**. `web/` reads as 159 files /
105,822 lines; normalized it is **37 files / 1,656 lines**.

> **Rule:** never size a delta from a raw diff against `refs/muse-tip`. Normalize first:
> `diff -u <(tr -d '\r' < A) <(tr -d '\r' < B)`.
>
> Every T0-T7 estimate taken from a raw diff should be treated as suspect.

**2. Upstream is AHEAD of the fork in places, so a "port" is a revert.** Confirmed for
`agent/moa_loop.py`, `agent/moa_trace.py`, `kanban_db.py`, `kanban.py` and `web/`.

### Already upstream — do not port these, porting them DELETES shipped fixes

| File | Status |
|---|---|
| `hermes_cli/moa_cmd.py`, `hermes_cli/moa_config.py` | **byte-identical** to upstream |
| `hermes_cli/kanban_swarm.py` | **byte-identical** to upstream |
| `agent/moa_trace.py` | upstream is ahead: it has `slot_metrics(acct, label, output=)`; the fork does not |
| `agent/moa_loop.py` | upstream is ahead by 183 lines: the `cache_ttl` threading that fixes the advisor prompt-cache 1h→5m regression (**#84733**), plus `_last_reference_metrics` on both MoAClient layers |

Copying the fork's `moa_loop.py` or `moa_trace.py` over upstream's would delete a shipped
bug fix and the observability hooks. Upstream also ships a far deeper MoA subsystem than the
plan assumed — `provider=moa` is a first-class provider wired into `cli.py`, `gateway/run.py`
(6 sites), `run_agent.py`, `conversation_loop.py`, `auxiliary_client.py` and `acp_adapter/`.

### The seam gap — the one genuine design problem left, and it needs a decision

The plan asserts a plugin router seam: *"a plugin `plugin_api.py` router — never a
`web_server.py` edit."* **It does not exist.** All 14 `include_router` calls are hand-written
lines in `hermes_cli/web_server.py`; `web_routers/` is a code-organization split with no
discovery mechanism. The only auto-mounting path, `_mount_plugin_api_routes()`, hard-codes
`prefix=f"/api/plugins/{name}"` — so it is available but it **moves the URLs**.

The same gap exists for the TUI: upstream has **no** extension point for gateway method
families or TUI overlays. `sessions`, `skillsHub`, `pluginsHub` and `petPicker` are each
hand-edited entries in the same hardcoded tuples.

This blocks T10 (Rooms) and both web APIs. Since T6 closed core edits, the honest options are
a sanctioned **T-SEAM** tranche that builds the extension points properly, or 19 quiet core
edits. **This needs a decision from someone with authority; it is not a detail to absorb.**

### Corrections to specific claims in the plan

| Plan said | Measured reality |
|---|---|
| `gateway/cockpit/room_store.py` is a rooms dependency to extract | It is **AI room-decor assets**, unrelated to `rooms_db` — the fork's own docstring says so |
| `ctx.register_platform()` is the cockpit's HTTP seam | It registers a chat `BasePlatformAdapter`, **not an HTTP surface** |
| T11 is "most likely to touch `cli.py`/`main.py`" | T11 is the **best-served** tranche: upstream ships an injectable `dispatch_once(spawn_fn=)` at `kanban_db.py:9811` and four live kanban worker-lifecycle hooks |
| T17's Android id is `com.muse.*` | It is **`com.aci.hermes`**. A rename keyed on "muse" would have reported success while shipping 2,286 references to the fork owner's org |
| T16 `apps/nexus` is a 175-file tranche | **Byte-subsumed by T15**: 57 identical, 34 older, 0 unique. Scoping both would put two copies of the same SPA in the tree |

### Branding gate hardened (T-LEDGER)

Three markers were missing and are now added:

- **fork owner identity** — widened from the `echerd27` handle to the surname stem, which also
  catches the owner's **legal name**. That name is baked into a system prompt in the fork
  (`jarvis_prime/system_contract.py`) and was matched by nothing. A private individual's real
  name reaching an upstream PR is worse than shipping late.
- **`com.aci` / `A-C-I-SOFTWARE`** — the fork's Android package and signing identity, 2,286
  references, previously matched by nothing on any list.
- Four new negative controls (`lecher`, `pacific`, `veracity`, bare `ACI_`) so the widened
  markers are proven not to over-fire.

Also fixed: `tests/hermes_cli/test_env_compat.py` was allowlisted. **T7 merged with a latent
guard failure** — the guard scans git-*tracked* files, and it was validated before the new
T7 files were tracked, so its own shim test went unscanned. Validate the guard *after*
`git add`, not before.

### The governing rule for everything that remains

> **Nothing lands without a live caller in this repo, in the same commit.**

The recurring danger is not effort, it is dead-on-arrival code. The fusion leaves,
`fusion_router`, `agent/studio`, `axiom`, `second_brain`, the orphaned web pages and the
entire Android app all share the property that their consumers live in tranches that are
dropped or unscoped. This is the `conversation_loop.py` trap from T5, repeated at scale.

### Additional deliberate drops

Beyond those already recorded. Each was measured, not assumed.

| Dropped | Why |
|---|---|
| **T13 cockpit, in full** (27 py / 15,117 lines + 46 static, plus `deploy/cockpit-https/`, `docs/android/`, 53 test files) | Product surface (a PWA), double-blocked on `jarvis_prime` and on the router seam that does not exist |
| **T16 `apps/nexus`, in full** | Byte-subsumed by T15. Salvage at most the vite config |
| **T17 `apps/android`** (458 files, 59k lines) | Well-engineered, but a thin client for two unported server bodies; its own KDoc cites `jarvis_prime/research_vault.py`. Ported as scoped it compiles, installs, and reaches nothing |
| `hermes_cli/orchestrator_*.py` (9), `job_*.py` (5), `worker_lease*.py` + `lease_scheduler.py` | A **second, weaker scheduler** duplicating upstream `kanban_db`'s claim/heartbeat/release_stale |
| `hermes_cli/{release_gate,release_readiness_doctor,sync_releases}.py` | Release-engineering product surface; `sync_releases` dispatches the fork's own GitHub Actions |
| `hermes_cli/web_moa_api.py`, `web_fusion_api.py` (490 lines) | No legal seam, and their only consumers are dashboard product surface |
| `jarvis_prime/federation/` (11 files) and `forge/` minus `glicko2.py` | Every docstring cites a fork-private volume; a constitution amendment engine and sovereignty index |
| `jarvis_prime` persona layer (~1,800 lines) | **Hardcodes a named private individual** as the agent's operating partner |
| `jarvis_prime/niches/specs/` (137 YAML) | Machine-generated 20-line templates encoding the fork's consumer verticals |
| 233 AOS recovery stubs + `registry/ docs/ migration/ archive/` | 87% name skills this repo already ships; 79 point at the already-dropped `recovered-agent-sources/` |
| `skills/mlops/local-role-loras` | Windows-only; hardcodes the operator's private `localhost:8888` and machine paths |
| `enterprise/` (13), `axiom/` (50), `second_brain/` (30), `templates/` (8), `design-system/` (8) | Zero non-test callers in this repo — the `conversation_loop.py` trap verbatim |
| `apps/synapse-ue` (92) | The fork's own README stages it for migration to a private standalone repo; UE 5.6 C++ |
| The fork's `web/` wholesale | A **regression**: 15 files exist only upstream and upstream's `plugins/registry.ts` is a strict superset |

### Licensing risk carried forward

`jarvis_prime/research_fabric/` ships **two vendored third-party trees**
(`autoresearch/vendor/`, `llm_jepa/vendor/`, each with its own `VENDOR.md` and
`checksums.json`), already carved out of the fork's own lint and packaging config. They are
not the fork's to relicense. Same class as the `tools/tokenjuice/rules/` notice requirement
(R9) — no upstream PR may carry them without the notice infrastructure.

### Remaining work, sized honestly

The plan describes 2,000+ files. After measurement the genuinely deliverable capability is
**roughly 200 files / 25,000-30,000 lines**, and the tractable orders are **8-12 weeks** of
focused work. Everything else is already upstream, dead in the fork, product surface, or
blocked on a seam that does not exist.

| Order | Tranche | Effort | What lands |
|---|---|---|---|
| 1 | **T-LEDGER** | done | These corrections + the hardened gate |
| 2 | T9a fusion leaves | 1-2 d | 1,528 lines pure-stdlib + 784 lines of tests. **Only with a live caller** |
| 3 | T18a web UX subset | 2-3 d | Backend-free components riding APIs upstream already serves |
| 4 | T8a `mixture_of_agents_tool` | ~2 wk rebased | Model-invocable fan-out tool. **Rebase onto upstream MoA**; as-is it is OpenRouter-hardwired with 4 hardcoded slugs |
| 5 | T14a AOS skills | 3-4 d | ~89 authored files of 354. **Three quarters of the work is deletion** |
| 6 | T12a prime navigation + graphrag | 1.5-2 wk | ~26 files / 4,900 lines — the two genuinely excellent nuggets in a 66k-line package |
| 7 | T11a orchestration | 3-4 wk | 55 files / 15,544 lines on three verified seams |
| 8 | **T-SEAM** | 1 wk | TUI/router extension points. **Decision required before any code** |
| 9 | T10 rooms | 1 wk | Gated on order 8. A redesign, not a copy |
| 10 | T12b prime NL→IR | 1 wk | Optional; regenerate a generic spec set, not the fork's 137 |
| 11 | T12c self-audit / research_fabric | — | **Defer, do not schedule.** Needs a written diff against upstream's counterparts first, plus the vendoring decision |

## T-SEAM — extension points for method families and TUI overlays (done)

The scoping pass found upstream has **no** extension point for gateway RPC method families
or TUI overlays, and that this blocked T10 and any future panel. T6 closed core edits, so the
choice was ~19 quiet hand-edits or building the mechanism. **Decision: build it.**

| Before | After |
|---|---|
| `tui_gateway/server.py` named every handler family **twice** — an import tuple and a registration tuple, both inside a 19K-line file. A typo in either silently dropped a whole family of RPC methods | `tui_gateway/method_modules.py` walks `methods_*.py` with `pkgutil`. Adding `methods_rooms.py` with a `register(server)` is the entire change |
| Adding an overlay meant **six** hand-edits that had to agree: an `OverlayState` field, a `buildOverlayState()` key, the name in **both** halves of `$isBlocked`, a name in `hasFloatingPanel()`, a name in `resetFlowOverlays()`'s preserve list, and a `widgets.push()` block | `ui-tui/src/app/overlayRegistry.ts` derives all six from one entry, and the **type system requires** the renderer, so it cannot be forgotten |

Two properties the walk guarantees deliberately: **deterministic order** (sorted, never
filesystem order — order that depends on luck is a bug waiting to be written), and **one
broken family cannot take the gateway down** (import/register failures are logged and
skipped; the old tuple had no containment).

### Behaviour preservation was the whole risk, so it was measured

| Check | Result |
|---|---|
| Gateway RPC method names, enumerated before and after | **167 both sides, identical sets** |
| Python: dangling + branding guards, `tests/tui_gateway`, `tests/gateway` | 81 failed / 6451 passed vs **81 failed / 6437 passed** on pristine — identical failure sets, +14 passing |
| `npm test --workspace ui-tui` | 10 failed / 1703 passed vs **10 failed / 1689 passed** on pristine — identical failure sets, +14 passing |

> **Trap:** the TS control is meaningless until you run
> `npm run build --workspace ui-tui/packages/hermes-ink`. Without `dist/entry-exports.js`,
> **63 test files fail to load** and you will compare 95 passing files against 155.

### Known limitation, recorded rather than hidden

`ui-tui/src/app/slash/registry.ts` still hardcodes its eight command-group imports. Not
converted deliberately: it is one flat list whose failure mode is **loud** (the command is
simply absent), unlike the six interlocking overlay edits whose failure mode was silent. The
bundled-TS equivalent is `import.meta.glob`, whose bundle-time resolution semantics are a
real risk for no proportionate gain. T10 adds one line there.

## T14a — enterprise council skills (done)

354 source files reduced to **78**. Three quarters of this tranche was deletion.

Dropped: 233 recovery stubs + 17 README indexes of them (87% named skills this repo already
ships; 79 pointed at the already-dropped `recovered-agent-sources/`), 146KB of
recovery-process documentation, and `operating-registry/registry.json` (runtime config for an
unported dispatcher).

**Also dropped — five files whose identity is one of the fork owner's private commercial
products**: the "Nourish" nutrition specialist and the "HazMat Command" specialist (in both
`agents/` and `specialists/`) plus the hazmat compliance rule. The consolidation had already
dropped the fork's `niches/specs/` for exactly this reason. All 27 downstream references were
**repaired, not blanket-deleted**: pointers generalized, product framing neutralized, and the
regulatory-citation examples **kept** but made product-neutral — "cite the primary text" is a
genuinely generic discipline worth keeping.

### Two corrections to the plan, both measured

1. **Depth.** All 199 upstream skills sit at `skills/<category>/<skill>/SKILL.md`. The fork
   put this at depth 3, where `prompt_builder` derives the category as the `"general"`
   fallback. Landed at `skills/autonomous-ai-agents/enterprise-council/`; derived category
   verified as `autonomous-ai-agents`.
2. **`description:` is an always-on tax.** It is injected into every turn's system prompt.
   The fork's was **654 chars**. The repo's own enforced hardline is 60
   (`tests/skills/test_authoring_standards.py`); measured p50 across 199 skills is 55.
   Rewritten to **57**.

## T8a — the MoA fan-out tool (done)

The only portable file from T8, and it is a **rebase, not a port**. `moa_cmd.py` /
`moa_config.py` were byte-identical already; `moa_trace.py` and `moa_loop.py` are files where
**upstream is ahead**, so copying the fork's versions would have deleted a shipped
prompt-cache fix. None were touched.

Ported as-is the tool was hardwired to OpenRouter with four hardcoded slugs — a strict
capability subset unable to reach a local or Anthropic model. Roughly half the fork's file
was OpenRouter plumbing that upstream already does better, and was deleted rather than
ported. The tool now resolves its panel through `moa_config.resolve_moa_preset` and fans out
via `moa_loop._run_references_parallel`.

**Four bugs found by adversarial review and fixed before landing:**

| Bug | Why it mattered |
|---|---|
| Multi-round wipeout | `if not answers: return _fail(...)` fired on round 2+ as well, discarding round 1's **already-billed** fusion |
| Silent override loss | The caller's `reference_models` was gated on `isinstance(list, tuple)`, so a bare string or dict silently ran the preset's panel instead — and models routinely emit a scalar where a schema asks for an array |
| `MAX_REFERENCE_MODELS` vetoed the user's own config | The cap ran after the preset branch, so a 9-slot preset made the tool **permanently unusable** |
| Dead surface | A documented `max_tokens` knob the schema never exposed |

Default-off (`moa` is not in `_HERMES_CORE_TOOLS`) — deliberate, since one call bills every
model on the panel, and adding it to the default set would be a core edit.

## ⚠ Gate findings — two of our own gates were weaker than assumed

**1. `ruff check` is VACUOUS for plugin code.** `pyproject.toml` sets `select = ["PLW1514"]`
as the *only* enabled rule, and `[tool.ruff.lint.per-file-ignores]` then sets
`"plugins/**" = ["PLW1514"]`. A green `ruff check .` therefore proves **nothing** about
anything under `plugins/` — which includes all 18 plugins landed in T4 and the T12a plugin.
Coverage there comes from the dangling-imports guard and registration smoke, not ruff. Do not
cite ruff as evidence for a plugin tranche.

**2. The branding guard only scans git-*tracked* files** (`git ls-files`). Validating it
before `git add` scans none of the new files. This has now shipped **twice**: once in T7 (its
own shim test went unscanned) and once in T14a's first pass (all 83 new files unscanned).
Always `git add -A --intent-to-add` first.

## ⚠ Working-tree discipline

Two separate agent runs wrote into the **main** repo while working, despite being scoped to
their own worktrees — once copying whole fork directories (`hermes_cli/jarvis_prime/`,
`axiom/`, `enterprise/`, `foundry/`, `second_brain/`, `agent/fusion_*`) and once an unrelated
bot-roster feature. Both were untracked or reverted before any commit, and nothing polluted
history — but the first **invalidated a 27-minute control run**, because those untracked fork
modules made `test_no_dangling_imports` fail in the control.

> **Check `git status --short` in the main repo is empty before trusting any control run.**

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
