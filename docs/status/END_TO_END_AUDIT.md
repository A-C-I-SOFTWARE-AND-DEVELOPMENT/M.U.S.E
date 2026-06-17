# MUSE — end-to-end activation audit (what's built, wired, and what's left)

_Snapshot date: 2026-06-17. Verified against `main` by inspecting real entry
points (CLI `add_parser`/`set_defaults`, cockpit routes, tool/worker/plugin
registration) — not from documentation alone. This supplements the
machine-readable [`docs/architecture/muse-component-registry.yaml`](../architecture/muse-component-registry.yaml)._

## Method

A subsystem is **WIRED** only if it has a real runtime entry point:
a `hermes_cli.jarvis_prime` CLI subcommand, a `gateway/cockpit` route, an agent
tool (`toolsets.py`/`tools/`), an orchestration worker
(`hermes_cli/workers/__init__.py`), or a plugin. "Built but not wired" means code
+ tests exist but nothing in the runtime calls it. Counts below are verified:
**86** `jarvis_prime` CLI subcommands, **114** cockpit routes, **7** registered
workers, **1519** test files.

> **Correction vs. the first-pass draft.** An initial automated pass flagged
> `federation` and `forge` as "unwired skeletons with no runtime dispatch." That
> was **wrong**: both have full `jarvis_prime` CLI subcommands delegating to their
> own `main.cli_main`, and 9 and 7 test files respectively. Likewise the 15
> `raise NotImplementedError` sites are abstract-base-class contracts
> (`agent/memory_provider.py`, `tts_provider.py`, `web_search_provider.py`,
> `gateway/platforms/base.py`), not unfinished features. The honest headline is
> that MUSE is **overwhelmingly activated**; the gaps are narrow and specific.

## Status by subsystem

| Subsystem | Status | Entry points (evidence) | What's left |
|---|---|---|---|
| **Orchestration** (Job/Worker/Model/Validation/Ledger) | ✅ WIRED | `/orchestrate`, `/swarm`, `/orchestrator` (`hermes_cli/commands.py`); cockpit `/v1/cockpit/{orchestrate,jobs,ledger}`; 7 workers | distributed swarm; Supabase job persistence (roadmap) |
| **Workers** | ✅ WIRED | `hermes_cli/workers/__init__.py`: aider, autoresearch, claude, codex, goose, local_planner, sia | direct slash triggers (today via orchestrator jobs) |
| **GraphRAG** | ✅ WIRED | CLI `graph`; `graph_query` tool (`toolsets.py`); cockpit `/v1/cockpit/graph/{query,related,build}`; NEXUS panel | optional Neo4j mode is opt-in |
| **Memory Tree + backends** | ✅ WIRED | CLI `memory`/`memtree`/`remember`/`recollect`; `plugins/memory/*` (holographic default); cockpit `/v1/cockpit/memory/*` | cross-provider migration tools |
| **Gateway / cockpit** | ✅ WIRED | 114 routes; loopback + bearer auth; serves NEXUS at `/nexus/` | in-app editors (mostly read-only panels) |
| **NEXUS PWA** | ✅ WIRED / DEPLOYED | `apps/nexus/`; ~33 capabilities; Pages + APK builds | — |
| **NEXUS native APK** | ✅ WIRED | `apps/nexus/android/` (local-gateway autodetect); `nexus-android-latest` release | Play-store signing (debug-signed today) |
| **Autoresearch (Karpathy) + SIA** | ✅ WIRED (owner-gated) | `AutoresearchWorker`/`SiaWorker`; skills `/autoresearch`,`/sia-self-improve`; cost+VRAM gates | continuous/scheduled runs (on-demand today) |
| **Learning dataset** | ✅ WIRED | CLI `learning *`; cockpit `/v1/cockpit/learning/*`; NEXUS Learning Queue | downstream SFT/preference training invocation |
| **Federation** (Vol VI) | ✅ WIRED (CLI) | CLI `federation` → `federation/main.cli_main` (identity/attest/quorum/amend/trust/intake); 9 test files | no cockpit/NEXUS surface; no autonomous peer loop |
| **Forge** (tournament/championship) | ✅ WIRED (CLI) | CLI `forge` → `forge/main.cli_main` (register/duel/tournament/elites/leaderboard); 7 test files | no cockpit/NEXUS surface; no scheduled tournaments |
| **Forge** (NEXUS per-agent knowledge) | ✅ WIRED | NEXUS `/forge`; cockpit `/v1/cockpit/learning` | — |
| **Voice / Avatar** | ✅ WIRED | CLI `/voice`; cockpit `/v1/cockpit/{voice,avatar}/*`; persona/room stores | lockscreen-approval UX; avatar animation engine |
| **Second Brain** | ✅ WIRED (this PR) | CLI `second-brain {status,retrieve,ingest}`; agent `recollect`/`build_context_handoff`; cockpit `/v1/cockpit/second-brain/{status,retrieve}`; NEXUS tab; **in-memory backend** runs with zero infra | durable store needs Postgres (in-memory is process-local); cockpit ingest is CLI-only by design |
| **AOS Enterprise Council** | ⚠ CATALOG / SKILLS | `skills/aos-enterprise-council/` (registries + agent markdown + `verify_registry.py`) | not an executable multi-agent **runtime** — it's a routed catalog loaded as a skill |

## What's left (prioritized, honest)

Most of the repo is already activated. The genuine remaining work is **surfaces,
persistence, and autonomy** — plus one real "build, not activate" item (AOS).

**Activate (flip a switch / add a surface — bounded):**
1. **Second Brain durability** — the in-memory backend (this PR) makes retrieval
   real with zero infra but is process-local. For cross-session use, run the
   Postgres backend (`second_brain/docker-compose.yml`, `SECOND_BRAIN_BACKEND=postgres`).
   Parity is covered by the marked integration test.
2. **Cockpit/NEXUS surfaces for CLI-only subsystems** — `federation` and `forge`
   are fully CLI-wired + tested but have no gateway route or NEXUS tab. Adding
   read surfaces mirrors the Second-Brain/graph route pattern (~2 routes + 1 tab each).
3. **Direct triggers** — expose autoresearch/SIA/forge-tournament as slash commands
   or scheduled jobs (today they run on-demand via orchestrator jobs).

**Build (genuine new implementation):**
4. **AOS Council executable runtime** — today it's a routed catalog of markdown
   agents loaded as a skill. An autonomous multi-agent dispatcher (instance
   factory + state machine over the registry) would be net-new (~large).
5. **Learning loop closure** — the dataset pipeline captures approved traces but
   does not yet invoke downstream SFT/preference training.

**Non-issues (do not "fix"):**
- The 15 `raise NotImplementedError` sites are ABC contracts with concrete
  subclasses — intentional, not gaps.
- Memory backends beyond the holographic default are dormant **by policy**
  (new backends ship as external plugins), not unfinished.

## How this was verified

`grep` of `sub.add_parser(`/`set_defaults(func=` in
`hermes_cli/jarvis_prime/__main__.py` (86 subcommands incl. `federation`, `forge`,
`second-brain`); the cockpit route table in `gateway/cockpit/server.py` (114
routes); `hermes_cli/workers/__init__.py` (7 workers); and the per-subsystem test
files under `tests/`. Re-run those greps to refresh this snapshot.
