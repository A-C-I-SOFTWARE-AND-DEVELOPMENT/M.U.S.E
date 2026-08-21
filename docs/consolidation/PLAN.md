# Consolidation plan — tranches T7–T18

Companion to `PORT-LEDGER.md`. The ledger records what *happened*; this file records what
was *decided* up front. Recovered from the design session and committed here because it
previously existed only in a chat transcript — a single lost session would have destroyed it.

Reference commits, branch families, rules and baselines: see `PORT-LEDGER.md`.

## Tranche order and dependencies

```
T6  repair-damaged-deltas  ──┬── blocks T11, T13   (they were written against the damaged files)
T7  branding-seam          ──┴── blocks T8+        (so no tranche re-introduces fork branding)
      T8  moa          T9  fusion       T10 rooms
      T11 orchestration                 T12 jarvis-prime
      T13 cockpit      T14 aos-council  T15 desktop-omni
      T16 nexus        T17 android      T18 misc-features
```

T12, T13 and T15 are **rewrites, not moves** — they were written against internals rather
than seams. Sequenced last deliberately: by the time they are reached, everything
upstreamable is merged and the repo is defensible even if work stops.

## T7 — `port/branding-seam`

Ships the infrastructure later tranches depend on. Must land before T8.

**Skins.** Upstream `hermes_cli/skin_engine.py` already ships 8 built-in skins with a
per-skin `branding:` block and a `get_branding()` seam. **Take upstream's file wholesale;
never the fork's.**

- `caduceus` — **drop entirely.** It is the MUSE serpent glyph; the fork itself removed the
  glyphs in `b5dd64c4de`.
- `singularity` — keep only if the palette stands on its own, re-landed as a **non-default**
  skin renamed (`nebula` / `void`), with `branding: {agent_name: "Hermes Agent"}`.
- Users wanting the MUSE look drop a YAML at `$HERMES_HOME/skins/`. That is what the seam is for.

**Env vars — 90 `MUSE_*` to `HERMES_*`, with a shim, cut at 0.21.**

1. Rename at definition and call sites. Where a rename collides with an existing upstream
   `HERMES_*`, scope it (`HERMES_PRIME_*` for jarvis-prime flags). Compute the collision set:
   `git grep -oh 'HERMES_[A-Z0-9_]*' | sort -u` intersected with the renamed set.
2. One shim, one place: `hermes_cli/env_compat.py`, a complete legacy-to-new table applied once
   at process start (`hermes_cli/main.py`, `gateway/run.py`). If the legacy var is set and the
   new one is not, copy across and emit a one-time deprecation warning.
3. Register all 90 legacy names in upstream's `_DEPRECATED_ENV_VARS` in `doctor.py` — that
   mechanism already exists upstream and is literally built for this.
4. `MUSE_TOOL_BROKER` also has a config-schema path (`security.tool_broker.enabled`); the
   schema entry must move too.
5. **Never regex-rename across the tree.** These names appear in `.md` prose, `.json`
   fixtures and shell heredocs where a blind rewrite breaks the file.
6. Pin `set(shim_table) == set(MUSE_ names in the frozen fork)` as a test fixture. The risk
   being defended against is a partial rename leaving a flag readable under neither name —
   a silent feature-off.

**`pyproject.toml`.** Take upstream's `[project.scripts]` verbatim. No `muse` alias, not even
for compatibility. Version is upstream's 0.20.4. Delete the fork's Vercel comment block.

**Branding gate.** Add `tests/test_no_fork_branding.py`, modeled on the dangling-imports
guard (pure filesystem scan). It matches **fork-specific markers only** — `M.U.S.E`, the
`MUSE_` prefix, the agent-name glyph line, `singularity`, `caduceus`, `jarvis` — with an
allowlist. **Bare case-insensitive `muse` is not a usable signal**: upstream legitimately
contains it in 45 files (Meta's Muse Spark models, where `muse` is a live provider alias; the
Muse EEG headband skill; and substrings like `MEMUSED` / `museum`). See the correction
recorded in `PORT-LEDGER.md`.

**Upstream contribution.** `pr/desktop-branding-seam`: there is no seam for the Electron
app's product name, icon, URL scheme or build config — branding *forces* a core edit today.
A single `apps/desktop/src/branding.ts` exporting
`{productName, appId, protocol, iconPath, aboutText}` fixes that for everyone.

## T8 — `port/moa`

`agent/moa_trace.py`, `hermes_cli/moa_cmd.py`, `hermes_cli/web_moa_api.py`,
`tools/mixture_of_agents_tool.py`. The tool is independently upstreamable
(`pr/tool-mixture-of-agents`); the CLI/web surfaces stay local.
Seam: `register_tool` + `register_cli_command` + a plugin `plugin_api.py` router —
**never** a `web_server.py` edit.

## T9 — `port/fusion`

`agent/fusion_*.py` + `hermes_cli/web_fusion_api.py`. Same seam pattern as T8.

## T10 — `port/rooms`

`hermes_cli/rooms_db.py`, `tui_gateway/methods_rooms.py`, `ui-tui/src/components/roomsPanel.tsx`.
`gateway/cockpit/room_store.py` is a cockpit dependency: **extract the store** to
`hermes_cli/rooms_db.py` and have the cockpit consume it, rather than holding rooms hostage
to T13.

## T11 — `port/orchestration`

`hermes_cli/{workers,swarm,harness,local_models}/`, ~90 loose `hermes_cli/orchestrator_*.py`,
`job_*.py`, `worker_lease*.py`, `decision_ledger.py`, `merge_engine.py`, `scoring.py`, plus
`docs/orchestration/`.

**Restructure on the way in** — 90 loose top-level modules is exactly what made the fork's
merge unresolvable. Move into `hermes_cli/orchestration/` as its own commit so the diff stays
reviewable. Seam: `register_cli_command`. Requires T6 (touches `cli.py` / `main.py`).

## T12 — `port/jarvis-prime` (426 files)

Sub-tranches, in order, because they stack:

1. core runtime (persona, modes, routing, `component_registry`, `context_handoff`)
2. `graphrag/` — unblocks `tools/graph_query_tool.py`, deferred from T2
3. `self_audit/` + constitution
4. `research_fabric/` (64)
5. `federation/`
6. `niches/` (143) — audit hard; likely largely data and largely MUSE-persona-specific

**Naming decision.** "Jarvis" is a Marvel/Disney trademark — a de-branding problem
independent of MUSE. Rename to `hermes_cli/prime/`, slash command `/prime`, keeping
`jarvis_prime` as a deprecated alias for one release. Do the rename as a single dedicated
commit at the head of the tranche with the guard green on both sides.

## T13 — `port/cockpit` (73 files)

Ride `gateway/platform_registry.py` + `ctx.register_platform()` and a plugin
`dashboard/plugin_api.py` router. `MUSE_COCKPIT_*` becomes `HERMES_COCKPIT_*`.
**Do not port the Vercel deployment stack** (`vercel.json`, `build_cockpit_vercel.sh`,
`web/musehq`, repo-root `api/`) — that is the fork's commercial surface, not a capability.
Port the cockpit as a local dashboard only. Requires T6.

## T14 — `port/aos-council` (353 files)

Cheapest big win: skills are `SKILL.md` frontmatter, **no code**. Near-zero risk.
177 of the 261 agent `.md` files live in `agents/hermes/` and are a general library, not
council agents — **de-duplicate against upstream `skills/`**. The 5 files under `registry/`
are the source of truth. Also lands `skills/creative/{game-studio,guide-first}` and
`skills/mlops/local-role-loras`. Strip `MUSE_GAME_ALLOW_SPAWN`, `MUSE_UE5_ALLOW_SPAWN`, etc.

## T15 — `port/desktop-omni` (138 files)

Seam: `apps/desktop/src/plugins/<id>/plugin.tsx`, auto-discovered, importing only
`@hermes/plugin-sdk` + react. Reference: `apps/desktop/src/plugins/hermes-bots/plugin.js`
(10,477 lines, zero core imports) — proof the seam is sufficient at this scale.
**Budget real rewrite time**: the fork's omni was written against `apps/desktop/ui/src/`
directly, not the contrib SDK. This is not a file move.

## T16 — `port/nexus` (175 files)

Separate npm workspace. Add to root `package.json` workspaces; `npm test --workspace apps/nexus`
joins the gate. Check `@vitejs/plugin-react` against upstream's version first — fork commit
`a24d8a63fa` flags dependency alignment as a live issue.

## T17 — `port/android` (458 files)

Self-contained, near-zero Python coupling. Product name, `applicationId`
(`com.muse.*` to `com.hermes.*` — **not reversible for installed users**), icon,
`strings.xml`, `MUSE_DEVICE_TOKEN`, `MUSE_VAPID_PRIVATE_KEY`.

## T18 — `port/misc-features`

`agent/studio` (40), `axiom` (50), `second_brain` (30), `apps/synapse-ue` (92), `web` (266),
work packets, `memory_tree`, `self_improvement`, `enterprise/`, `integrations/`, `templates/`,
`design-system/`. Triage `web/` carefully — it overlaps upstream's `plugins/web`, and
`web/musehq` is commercial surface.

## Gates

**Fast gate — every commit (~10s):**

```
uv run ruff check .
uv run pytest tests/test_no_dangling_imports.py tests/test_no_fork_branding.py -q
```

**Tranche gate — green before the next tranche starts:**

```
uv run ruff check .
uv run ty check                     # no NEW diagnostics vs the 15,382 baseline
uv run pytest tests/test_no_dangling_imports.py tests/smoke tests/characterization -q
uv run pytest <the tranche's surface> -q
uv run python scripts/focused_verification.py
bash scripts/run_tests.sh           # full suite, per-file isolation
npm test --workspace <ui-tui|web|apps/desktop|apps/nexus>   # if a UI workspace was touched
```

**Runtime gate — before T6, T11, T13, T17 and the cutover:**

```
uv run hermes doctor
uv run hermes --version
uv run hermes gateway start && uv run hermes gateway status && uv run hermes gateway stop
uv run hermes serve
```

`hermes doctor` is the best integration canary in this codebase — and it is one of the 13
damaged files. Get it green early.

| Guard | Blocks |
|---|---|
| `test_no_dangling_imports` | **every tranche.** Non-negotiable |
| `smoke/test_registration_smoke.py` | anything registering a provider/tool/plugin |
| `smoke/test_cli_surface_smoke.py`, `test_entrypoint_signatures.py` | anything touching `cli.py` / `main.py` |
| `test_no_fork_branding` | T7 onward |
| `hermes doctor` + gateway start/stop | T6, T11, T13 |
| full `scripts/run_tests.sh` | end of every tranche, no exceptions |

## Standing risks

- **R1 — re-introducing the dangling-symbol class.** The ordering *is* the mitigation: guards
  first, class-D files repaired from the true delta, one seam per tranche, only T6 hand-edits
  core.
- **R5 — fork features depending on damaged files.** Everything in T11/T13 was written against
  the fork's *truncated* `cli.py` / `main.py` / `web_server.py` / `gateway/run.py`. Land T6
  first; grep each ported feature's imports against upstream's actual exports before writing a
  line.
- **R6 — the live install.** `%LOCALAPPDATA%\hermes\hermes-agent` is editable-installed and
  drives 18 Cursor MCP servers. **Never** run `checkout` / `switch` / `rebase` / `pull` /
  `clean` there.
- **R7 — `HERMES_HOME` collision.** All port work runs with
  `HERMES_HOME=C:\Users\Echer\.hermes-port`. Upstream 0.20.4 against a home written by the
  fork's `config.py` (+540 lines of schema) can corrupt `config.yaml`.
- **R8 — upstream drift.** `git merge upstream/main` into `integration` **between** tranches,
  never inside one. Conflicts in more than ~20 files means stop and reassess — that is the
  signal the fork's failure mode is being recreated.
- **R9 — licensing.** No NousResearch PR containing vendored `tools/tokenjuice/rules/` without
  the notice infrastructure in the same PR.

## Cutover (after the tranches)

Build a venv in the combined repo, `pip install -e .`, verify the `hermes` entry point exists,
then rewrite `C:\Users\Echer\.cursor\mcp.json` (57 path references across 18 servers) to the
new venv, with `HERMES_HOME` unchanged. Keep the old `mcp.json`; rollback is one file copy.
`C:\Users\Echer\.cursor\bin\with_hermes_env.py` is referenced by 15 of the 18 servers and must
keep resolving.
