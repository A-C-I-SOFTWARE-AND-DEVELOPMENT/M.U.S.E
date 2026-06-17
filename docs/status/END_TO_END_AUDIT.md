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
| **Federation** (Vol VI) | ✅ WIRED | CLI `federation`; **cockpit `/v1/cockpit/federation/status`** (public-only); **NEXUS Federation tab**; 9 test files | no autonomous peer loop |
| **Forge** (tournament/championship) | ✅ WIRED | CLI `forge`; **cockpit `/v1/cockpit/forge/leaderboard`**; **NEXUS Championship tab**; 7 test files | no scheduled tournaments |
| **Forge** (NEXUS per-agent knowledge) | ✅ WIRED | NEXUS `/forge`; cockpit `/v1/cockpit/learning` | — |
| **Voice / Avatar** | ✅ WIRED | CLI `/voice`; cockpit `/v1/cockpit/{voice,avatar}/*`; persona/room stores | lockscreen-approval UX; avatar animation engine |
| **Second Brain** | ✅ WIRED (this PR) | CLI `second-brain {status,retrieve,ingest}`; agent `recollect`/`build_context_handoff`; cockpit `/v1/cockpit/second-brain/{status,retrieve}`; NEXUS tab; **in-memory backend** runs with zero infra | durable store needs Postgres (in-memory is process-local); cockpit ingest is CLI-only by design |
| **AOS Enterprise Council** | ✅ WIRED | `hermes_cli/jarvis_prime/aos_council/` registry dispatcher; CLI `council {roster,dispatch}`; cockpit `/v1/cockpit/council/dispatch`; NEXUS Council Dispatch tab; routes the real `operating-registry/registry.json` | per-member LLM execution is opt-in (the dispatcher hands `path` personas to the model layer) |

## What's left (prioritized, honest)

The repo is now activated end-to-end across CLI **and** the gateway/NEXUS. The
items below were closed in this work; only autonomy + a couple of opt-in depth
items remain.

**Done in this activation pass:**
- ✅ **Second Brain runs for real** — zero-infra in-memory backend; CLI + agent
   recollection + cockpit + NEXUS tab. (Durable cross-session storage still uses
   the Postgres backend via `SECOND_BRAIN_BACKEND=postgres`; parity is covered by
   the marked integration test.)
- ✅ **Cockpit + NEXUS surfaces for the CLI-only subsystems** — `forge`
   (Championship) and `federation` (public-only) now have gateway routes + NEXUS tabs.
- ✅ **AOS Council executable runtime** — a registry dispatcher (CLI + cockpit +
   NEXUS) routes a request to the real council; no longer catalog-only.

**Remaining (autonomy + opt-in depth):**
1. **Direct/scheduled triggers** — autoresearch / SIA / forge tournaments run
   on-demand via orchestrator jobs; periodic/continuous scheduling is not wired.
2. **Per-member council execution** — the dispatcher routes + gates members;
   running each engaged member's persona through the model layer is the opt-in
   next layer (the `path` is already surfaced).
3. **Learning loop closure** — the dataset pipeline captures approved traces but
   does not yet invoke downstream SFT/preference training.

**Non-issues (do not "fix"):**
- The 15 `raise NotImplementedError` sites are ABC contracts with concrete
  subclasses — intentional, not gaps.
- Memory backends beyond the holographic default are dormant **by policy**
  (new backends ship as external plugins), not unfinished.

## How this was verified

`grep` of `sub.add_parser(`/`set_defaults(func=` in
`hermes_cli/jarvis_prime/__main__.py` (86 subcommands incl. `federation`, `forge`,
`second-brain`, `council`); the cockpit route table in `gateway/cockpit/server.py`
(120 routes); `hermes_cli/workers/__init__.py` (7 workers); and the per-subsystem test
files under `tests/`. Re-run those greps to refresh this snapshot.
