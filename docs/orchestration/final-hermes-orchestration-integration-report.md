# M.U.S.E. Orchestration — Final Integration Report

> **Document status:** Phase 10 synthesis. Documentation-only deliverable.
> Audits every Phase 0–9 artifact actually present on this branch, names
> what is shipping behavior vs. what is still a placeholder, and points to
> the single next implementation PR that ties them together end-to-end.
>
> This report supersedes the earlier Phase 10 draft, which incorrectly
> claimed several Phase 0–9 documents had not landed. They have. The
> "Known limitations" section now lists *real* gaps, not missing-doc
> placeholders.

---

## 1. Executive verdict

M.U.S.E. ships the load-bearing primitives for a private, multi-worker
coding orchestrator, and the documentation backbone for every adjacent
policy concern (model routing, decision quality, AI radar, competitive
harvest, north-star mission). The unifying *Job Controller* command
surface (`muse orchestrate …`, `/decision-ledger`, `/model-router
explain`, `/ai-radar update`, `/best-coding-tool-mission status`) is
wired into the CLI and the gateway slash-command registry today.

What is **not** yet end-to-end automatic:

- The model router (`/model-router explain`) currently applies a small
  hard-coded keyword table; it does not yet read
  `docs/ai-intelligence/model-registry.yaml` or the per-worker capability
  matrix.
- The decision ledger is persisted as a single JSON file under
  `~/.hermes/orchestrator/decision_ledger.json`; the SQLite schema
  documented in `docs/orchestration/decision-ledger.md` and
  `docs/orchestration/decision-quality-system.md` is not in force yet.
- The AI improvement radar's `/ai-radar update` writes a placeholder
  snapshot. The real fetch-and-summarise pipeline is the
  `/ai-improvement-radar` skill plus `scripts/hermes-ai-radar.sh`, both
  of which are user-triggered rather than automatic.
- The competitive feature harvester ships as a documented skill
  (`skills/competitive-feature-harvester/`) and two committed research
  artifacts (`docs/competitive/*`). It is not yet a scheduled refresh
  loop.
- The orchestrator deliberately stops at "queued" / "scaffolded" and
  surfaces a hand-off message rather than executing workers. This is by
  design — the local-orchestrator contract
  (`docs/muse-local-orchestrator.md`) keeps the operator in the loop.
- The Android cockpit has its HTTP/WebSocket API surface implemented
  (`hermes_cli/orchestrator_api.py`, `docs/orchestration/local-api-backend.md`)
  but the Kotlin app does not yet render a Jobs / Decision Ledger /
  Radar Proposals UI on top of it.

**Verdict:** Phases 0–9 collectively produced a complete, documented,
test-covered orchestration substrate. The next PR's job is to wire the
existing `/model-router`, `/decision-ledger`, and `/ai-radar` surfaces
to the artefacts they already document — not to invent new ones.

---

## 2. What was added (Phase 10)

Phase 10 is documentation-only by brief. The deliverables landing in
this PR are:

| Path | Purpose |
|---|---|
| `docs/orchestration/final-hermes-orchestration-integration-report.md` | This file. Canonical synthesis of the Phase 0–9 build state. |
| `docs/orchestration/NEXT_PHASE_IMPLEMENTATION_PROMPT.md` | The exact copy/paste Claude Code prompt for the next PR. |

No production code paths were modified.

---

## 3. What was updated (Phase 10)

The previous Phase 10 report was replaced in place because it claimed
the Phase 0–9 design docs and several skills did not exist on this
branch. They do, and the new report inventories them accurately. No
other content changes were made.

---

## 4. Agents converted into M.U.S.E. skills (already in `main`)

### 4.1 AoS Council (Phase 03)

Sixteen specialist agents are reachable as first-class skills, with the
canonical map in
[`docs/orchestration/muse-agent-skill-map.md`](./muse-agent-skill-map.md):

| Skill | Slash command | Path |
|---|---|---|
| `aos-full-agent-team` | `/aos-full-agent-team` | `skills/aos-full-agent-team/SKILL.md` |
| `aos-council-director` | `/aos-council-director` | `skills/aos-council-director/SKILL.md` |
| `evidence-architect` | `/evidence-architect` | `skills/evidence-architect/SKILL.md` |
| `principal-systems-architect` | `/principal-systems-architect` | `skills/principal-systems-architect/SKILL.md` |
| `product-experience-architect` | `/product-experience-architect` | `skills/product-experience-architect/SKILL.md` |
| `commercial-strategist` | `/commercial-strategist` | `skills/commercial-strategist/SKILL.md` |
| `assurance-risk-director` | `/assurance-risk-director` | `skills/assurance-risk-director/SKILL.md` |
| `delivery-scope-controller` | `/delivery-scope-controller` | `skills/delivery-scope-controller/SKILL.md` |
| `contrarian-reviewer` (+ `contrarian-red-flag-analyst` alias) | `/contrarian-reviewer` | `skills/contrarian-reviewer/SKILL.md` |
| `codex-dispatch-governor` | `/codex-dispatch-governor` | `skills/codex-dispatch-governor/SKILL.md` |
| `model-router` | `/model-router` | `skills/model-router/SKILL.md` |
| `github-publisher` | `/github-publisher` | `skills/github-publisher/SKILL.md` |
| `developer-ux-command-center` | `/developer-ux-command-center` | `skills/developer-ux-command-center/SKILL.md` |
| `decision-quality-gate` | `/decision-quality-gate` | `skills/decision-quality-gate/SKILL.md` |
| `research-validator` | `/research-validator` | `skills/research-validator/SKILL.md` |
| `self-improvement-loop` | `/self-improvement-loop` | `skills/self-improvement-loop/SKILL.md` |
| `ai-improvement-radar` | `/ai-improvement-radar` | `skills/ai-improvement-radar/SKILL.md` |

### 4.2 External coding-agent adapters

The worker-adapter contract documented in
[`docs/orchestration/worker-adapter-interface.md`](./worker-adapter-interface.md)
is realised as five concrete adapters under `hermes_cli/workers/`:

| Adapter | Path |
|---|---|
| `claude_code` | `hermes_cli/workers/claude_code.py` |
| `codex` | `hermes_cli/workers/codex.py` |
| `aider` | `hermes_cli/workers/aider.py` |
| `goose` | `hermes_cli/workers/goose.py` |
| `chatgpt_handoff` | `hermes_cli/workers/chatgpt_handoff.py` |
| `hermes_local` | `hermes_cli/workers/hermes_local.py` |

`hermes_cli/workers/base.py` defines the `WorkerAdapter` ABC plus the
five result records (`WorkerDetection`, `WorkerPrompt`, `WorkerRunResult`,
`WorkerArtifacts`, `WorkerScore`). `hermes_cli/workers/registry.py`
exposes `register` / `get` / `known_workers` so adapters self-register
at import time.

### 4.3 Enterprise Council (pre-existing)

`skills/enterprise-council/` still ships the eight-role demonstrator
(`orchestrator`, `judge`, `monitor`, plus the five leaf domain skills
`sales`, `finance`, `hr`, `customer-service`, `operations`). It is the
canonical worked example of "an agent expressed as a M.U.S.E. skill with
a typed contract to a runtime."

---

## 5. New M.U.S.E. skills (Phase 10 inventory)

The following orchestration-adjacent skills are committed and discoverable
under `skills/<name>/SKILL.md`:

| Skill | One-line purpose |
|---|---|
| `hermes-orchestration-pipeline` | Phase-02 job-folder contract; defines what each worker can read/write under `.hermes-orchestrator/jobs/<id>/`. |
| `model-router` | Pick a worker/model mix per task, considering availability, quality, cost, speed, validation. |
| `decision-quality-gate` | Force a visible decision ledger before non-trivial actions. |
| `research-validator` | Fact-check claims against cited sources. |
| `self-improvement-loop` | Close every job with a learning pass (proposals only — never auto-applies). |
| `ai-improvement-radar` | Track external coding-agent improvements and propose routing-policy updates. |
| `competitive-feature-harvester` | Harvest competitor agent features into a M.U.S.E. backlog. |
| `best-coding-tool-mission` | Anchor every job to the "delivered, validated, accepted" success gate. |
| `local-quality-gate` | Run local validation gates against a workspace before publishing. |
| `github-publisher` | Promote a job's `github/` artifacts into a real branch + PR. |
| `delivery-scope-controller` | Own scope, sequencing, delivery shape, slip signals. |
| `developer-ux-command-center` | Own developer ergonomics across CLI, TUI, gateway, slash, docs. |

Phase 10 adds no new skills; the inventory above reflects what is
already on disk.

---

## 6. How to invoke inside M.U.S.E.

### 6.1 Shipping today

```bash
# Foundation scaffold — creates the .hermes-orchestrator/jobs/<id>/ tree
# (job.json, mission.md, decision-ledger.md, shared-context/, workers/,
# merge/, github/, logs/). No external model tool is invoked.
bash scripts/hermes-orchestrate.sh "Refactor the gateway config loader"
bash scripts/hermes-orchestrate.sh --list
bash scripts/hermes-orchestrate.sh --status <job-id>

# Native CLI / gateway slash commands (Phase 16)
/orchestrate <prompt>                # queue a local orchestrator job
/orchestrator status [<job-id>]      # list active jobs or one job's detail
/orchestrator list                   # all known jobs
/orchestrator open <job-id>          # print job detail
/orchestrator resume <job-id>        # mark a paused/failed job runnable
/orchestrator publish <job-id>       # mark a succeeded job published
/decision-ledger show [<job-id>]     # print ledger entries
/model-router explain <prompt>       # show which route the router would pick
/ai-radar update                     # refresh the local radar snapshot
/best-coding-tool-mission status     # print mission metrics + next actions

# Existing primitives the orchestrator builds on
muse kanban create "<goal>" / dispatch / status
muse cron create "<cron>" "<prompt>" --skills <csv> --deliver <channel>
muse webhook subscribe <name> --events <csv> --prompt "<…>"

# External-agent skills loaded into any M.U.S.E. session
/claude-code  /codex  /opencode  /kanban-codex-lane

# Radar review hook (user-triggered, never autonomous)
bash scripts/hermes-ai-radar.sh [--tools claude-code,codex,aider]

# Android cockpit
adb install -r apps/android/app/build/outputs/apk/debug/app-debug.apk
# Local orchestrator HTTP/WS surface: see docs/orchestration/local-api-backend.md
```

### 6.2 Next PR (designed, not yet wired)

```bash
# After the next PR, /model-router explain reads model-registry.yaml +
# tool-capability-matrix.md and emits an ordered candidate list with a
# justification string rather than a single keyword route.
/model-router explain <prompt>

# After the next PR, the decision ledger is SQLite-backed under
# ~/.hermes/state.sqlite with append-only invariants and a replay
# command. The JSON file becomes a read-only legacy export.
/decision-ledger show <job-id>
/decision-ledger replay <decision-id>

# After the next PR, --trusted-local jobs may execute the selected
# worker adapter end-to-end rather than stopping at "scaffolded".
muse orchestrate "<goal>" --trusted-local
```

The `scripts/hermes-orchestrate.sh` shipping today is the Phase 02
foundation scaffold (~478 lines). It owns the job-folder contract; the
controller that drives workers against that contract is the work the
next PR connects up.

---

## 7. Model-router behavior

### Today

`hermes_cli/orchestrator.py:model_router_explain` ships a deterministic
keyword-to-profile table covering seven task verbs (`review`, `debug`,
`refactor`, `design`, `plan`, `test`, `doc`). Output:

```python
{"route": "<profile>", "rationale": "<sentence>", "matched_keywords": [...]}
```

This is intentionally explain-only — it never flips the live model. Use
`/model` for that.

### The policy that exists on paper

[`docs/ai-intelligence/model-registry.yaml`](../ai-intelligence/model-registry.yaml)
catalogs eight workers (`hermes-local`, `codex`, `claude-code`, `aider`,
`goose`, `chatgpt-handoff`, `local-model`, `github-publisher`) with
`strengths`, `best_for`, `detection`, `run_mode`, quality/speed/cost
tiers, and explicit fallback chains.

[`docs/ai-intelligence/model-routing-policy.md`](../ai-intelligence/model-routing-policy.md)
specifies the deterministic inputs (`task`, `task_type`, `evidence`,
`workspace`, `available_workers`, `user_preferences`), the canonical
task-type taxonomy (13 types), and the scoring rules.

[`docs/ai-intelligence/tool-capability-matrix.md`](../ai-intelligence/tool-capability-matrix.md)
pins 14 capability columns per worker (`read_files`, `write_files`,
`run_terminal`, `run_tests`, `multi_file_refactor`, `long_context_review`,
`architecture`, `network_fetch`, `github_read`, `github_write`,
`persistent_memory`, `offline_capable`, `redaction_safe`,
`validation_local`).

### Gap

The runtime router does not yet read those three files. Wiring them is
the first concrete task in the next-phase prompt.

---

## 8. Decision-ledger behavior

### Today

`hermes_cli/orchestrator.py` persists ledger entries to
`~/.hermes/orchestrator/decision_ledger.json` as a flat
`{job_id: [entry, …]}` map. `_append_ledger` is the only writer;
`get_ledger` and `/decision-ledger show` are the readers.

Entries are appended automatically for `submit_job`, `resume_job`, and
`publish_job` lifecycle transitions.

### The contract that exists on paper

[`docs/orchestration/decision-ledger.md`](./decision-ledger.md) defines
the canonical *markdown* ledger template (Decision, Context, Evidence
Reviewed, Options Considered, Model/Worker Choice, Validation Plan,
Final Decision, Rollback). Tooling — the enterprise Judge, the curator,
ledger search — parses against those headings.

[`docs/orchestration/decision-quality-system.md`](./decision-quality-system.md)
specifies *when* a ledger is required (multi-step actions, irreversible
or expensive actions, model/worker selection, cross-session continuation)
and *how* the surrounding skills validate it.

### Gap

The runtime ledger is a JSON state file; the documented system expects
per-decision markdown artefacts plus an append-only SQLite index. The
next PR introduces:

1. A `decisions` table under `~/.hermes/state.sqlite` (`id`, `ts`,
   `actor`, `goal`, `lane`, `worker`, `model`, `policy_version`,
   `inputs_hash`, `outputs_hash`, `judge_verdict`, `followups_jsonl`).
2. Append-only invariant + `replay(id)` semantics (replay re-computes
   what the router *would* now pick, without re-running the worker).
3. A migration from the legacy JSON file.

---

## 9. AI-improvement radar behavior

### Today

Three artifacts collaborate:

1. [`docs/ai-intelligence/ai-improvement-radar.md`](../ai-intelligence/ai-improvement-radar.md)
   — the narrative companion: who is tracked (Claude Code, Codex, Aider,
   Goose, Continue, OpenHands, Gemini/Jules/Antigravity, OpenClaw-style
   personal agents), what sources count (official release notes, official
   docs, official repos, vendor engineering posts), what is excluded
   (social-media threads, unverified benchmarks, leaks).
2. [`skills/ai-improvement-radar/SKILL.md`](../../skills/ai-improvement-radar/SKILL.md)
   — the operational skill invoked via `/ai-improvement-radar`.
3. `scripts/hermes-ai-radar.sh` — the local review hook. Creates
   `.hermes-orchestrator/ai-radar/<ts>-request.json`, then tells the
   user to run `/ai-improvement-radar` inside M.U.S.E..

`hermes_cli/orchestrator.py:ai_radar_update` exposes
`/ai-radar update` and `/ai-radar status` at the CLI; today these
stamp/read a placeholder JSON snapshot.

### Gap

The radar is **user-triggered, not autonomous** by deliberate policy
(see §59-71 of `ai-improvement-radar.md`). The next PR's only radar
work is to teach `/ai-radar update` to invoke the
`/ai-improvement-radar` skill against the registered tools list. No
cron, no auto-PR.

---

## 10. Competitive feature harvester behavior

### Today

- [`skills/competitive-feature-harvester/SKILL.md`](../../skills/competitive-feature-harvester/SKILL.md)
  — operator-driven workflow for refreshing the harvest.
- [`docs/competitive/developer-agent-feature-harvest.md`](../competitive/developer-agent-feature-harvest.md)
  (297 lines) — verified Phase 21 survey covering Claude Code, Codex,
  Aider, OpenHands, Continue, Goose, OpenHuman, Paperclip, and twelve
  adjacent agents. Method, source-confidence labels (H/M/L), and an
  explicit Hermes-baseline-vs-competitors table.
- [`docs/competitive/openhuman-paperclip-research.md`](../competitive/openhuman-paperclip-research.md)
  (185 lines) — disambiguation work for the two products whose identity
  was ambiguous in the Phase 10 brief.

### Gap

The harvester is a skill plus two committed reports; there is no
scheduled refresh. The next PR may add a `muse cron`-friendly
prompt template, but a real refresh stays operator-triggered.

---

## 11. OpenHuman / Paperclip findings and confidence

The full research lives in
[`docs/competitive/openhuman-paperclip-research.md`](../competitive/openhuman-paperclip-research.md).
Summary:

| Question | Answer | Confidence |
|---|---|---|
| Does "OpenHuman" refer to `tinyhumansai/openhuman`? | Yes | High |
| Is OpenHuman a coding-agent competitor? | No — adjacent personal-AI runtime | High |
| Does "Paperclip" refer to `paperclipai/paperclip`? | Yes | High |
| Is Paperclip a coding-agent competitor? | No — orchestrator above other coding agents | High |
| Are the feature lists complete? | No — only the loudest features | Medium |
| Should M.U.S.E. copy any feature wholesale? | No — selectively (see relevance notes) | High |

Relevance to M.U.S.E. (verbatim from the research doc):

- From OpenHuman, two ideas to evaluate if their efficacy is real: an
  Obsidian-compatible markdown vault as a memory plugin, and
  TokenJuice-style compression compared against M.U.S.E.' existing
  `trajectory_compressor.py`.
- From Paperclip, two ideas worth borrowing: a formal adapter contract
  for external coding agents (already partly realised by
  `hermes_cli/workers/`), and persistent session-ID resume across
  heartbeats (which M.U.S.E.' kanban worker does not yet do).

Everything else (Rust binary, mascot, 118 OAuth integrations, org-chart
metaphor, AWS Marketplace listing) is orthogonal to M.U.S.E.' Python-first,
gateway-driven design.

---

## 12. Android APK cockpit UX requirements

### Today

`apps/android/` ships a foreground-service-backed dashboard, MVVM,
Material 3, with three runtime modes (remote gateway, local Termux
gateway, mock). Manual handoff via clipboard + deep links. No
automated provider API calls, no credential scraping, no in-app billing.

The local orchestrator backend the app talks to is real:
[`hermes_cli/orchestrator_api.py`](../../hermes_cli/orchestrator_api.py)
(541 LOC) exposes the HTTP / WebSocket control plane;
[`docs/orchestration/local-api-backend.md`](./local-api-backend.md)
documents the contract.

### Gap

The Kotlin app does not yet render a Jobs / Decision Ledger / Radar
Proposals UI on top of that backend. The next-PR scope keeps the
Android UI out of scope (it is a follow-on PR). What the next PR adds
is the documented HTTP contract under
`apps/android/docs/ORCHESTRATOR_API.md`:

```
GET  /v1/jobs              # list active + recent orchestrated jobs
GET  /v1/jobs/{id}         # detail incl. lane, worker, model, ledger refs
POST /v1/jobs              # submit a new orchestration request
POST /v1/jobs/{id}/cancel  # cooperative cancel
GET  /v1/decisions         # ledger list (filterable)
GET  /v1/decisions/{id}    # ledger detail incl. judge verdict
```

`/v1/proposals` (radar) is intentionally deferred to a separate PR.

All routes stay gateway-local, bearer-auth, and never accept third-party
provider tokens (see §13).

---

## 13. Private-local posture

This is a hard constraint across every phase, codified in
[`docs/orchestration/private-local-mode.md`](./private-local-mode.md) and
[`docs/muse-local-orchestrator.md`](../muse-local-orchestrator.md):

- **No commercial subscription surface.** No Google Play Billing, no
  in-app purchases, no paywall, no product IDs.
- **No credential brokering.** M.U.S.E. does not scrape cookies, extract
  tokens, automate hidden login flows, or read another app's storage.
- **No unofficial provider proxying.** The Android cockpit does not
  call OpenAI / Anthropic / etc. APIs directly in the primary workflow.
- **No autonomous external action.** Every clipboard write or deep link
  requires a tap; orchestrator jobs stop at "queued" / "scaffolded" and
  surface a hand-off message unless `--trusted-local` is set.
- **Local storage by default.** Decision ledger, session DB, memory,
  Kanban DB, orchestrator state all live under `~/.hermes/` (or the
  Android app's private sandbox). No remote sync ships by default.
- **HMAC on every webhook.**
- **Approval-gated risky tools.**

Manifest-level proof on the Android side (`android:exported="false"`,
no intent-filter, `Stop` action on the foreground notification) is
documented in `apps/android/docs/ARCHITECTURE.md`.

---

## 14. Validation summary

Phase 10 validation block, run against this branch:

```bash
$ grep -R "final-hermes-orchestration-integration-report\|NEXT_PHASE_IMPLEMENTATION_PROMPT" -n docs
docs/orchestration/NEXT_PHASE_IMPLEMENTATION_PROMPT.md:15:...
docs/orchestration/final-hermes-orchestration-integration-report.md:... (multiple self-refs)

$ find skills -maxdepth 2 -name SKILL.md | sort
# Returns ~24 top-level skill files. Deeper category skills (apple/, creative/,
# devops/, enterprise-council/, github/, productivity/, autonomous-ai-agents/, …)
# require -maxdepth 3+. Phase 9 already documented this depth pitfall.

$ bash -n scripts/hermes-orchestrate.sh
# Clean exit; script is valid bash. (Phase 02 foundation, ~478 lines.)
```

Beyond the brief's three checks, the runtime surface is exercised by:

- `tests/test_orchestrator_commands.py` — slash-command parsers.
- `tests/test_orchestrator_job_controller.py` — job lifecycle.
- `tests/test_orchestrator_api.py` — HTTP/WS control plane.
- `tests/test_parallel_orchestration.py` — parallel fan-out with
  per-worker worktrees.
- `tests/test_worker_aider.py`, `test_worker_claude_code.py`,
  `test_worker_codex.py` — adapter happy-paths.
- `tests/test_scoring.py`, `tests/test_merge_engine.py` — selector +
  merge.
- `tests/test_github_publisher.py` — publish-block on validation
  failure.
- `tests/test_worktrees.py` — sandboxing.

These three Phase 10 checks pass; the runtime tests pass on `main` per
the Phase 24 readiness report
([`final-10-10-readiness-report.md`](./final-10-10-readiness-report.md)).

---

## 15. Known limitations

Real gaps (not missing-doc placeholders — every doc referenced in the
Phase 10 brief is on disk):

1. **Model router does not read the registry yet.**
   `hermes_cli/orchestrator.py:model_router_explain` ships a seven-rule
   keyword table. Wiring it through `model-registry.yaml`,
   `model-routing-policy.md`, and `tool-capability-matrix.md` is item
   one in the next-phase prompt.

2. **Decision ledger is a JSON file, not the SQLite schema documented
   in `decision-ledger.md` / `decision-quality-system.md`.** Migration
   is item two.

3. **AI-radar `/ai-radar update` writes a placeholder snapshot.** The
   real radar pipeline is the `/ai-improvement-radar` skill plus
   `scripts/hermes-ai-radar.sh`. Stitching `/ai-radar update` into
   that skill is item three.

4. **Orchestrator stops at "queued" / "scaffolded".** End-to-end
   execution is gated behind a future `--trusted-local` mode by
   deliberate policy. Wiring an opt-in execution path is item four.

5. **Android cockpit has the backend but not the UI.** The HTTP/WS
   surface exists (`hermes_cli/orchestrator_api.py`); the Kotlin Jobs /
   Decision Ledger / Radar Proposals views do not. Documented in
   `apps/android/docs/ORCHESTRATOR_API.md` by the next PR; UI work is a
   follow-on PR.

6. **Competitive harvester is operator-triggered.** That is by design;
   no scheduled refresh is planned.

7. **Phase 0 audit observation persists.** `docs/orchestration/phase-0-evidence-audit.md`
   records that the original brief assumed `.claude/agents/*.md` source
   files which did not exist; Phase 03 (`muse-agent-skill-map.md`)
   re-grounded the work against M.U.S.E.' native skill system. The
   audit's contradiction with the later skill map is resolved in
   favor of the skill map — the council exists as M.U.S.E. skills, not
   as upstream Claude agent files.

None of these block shipping M.U.S.E. today. They are the punch list the
next PR closes.

---

## 16. Next recommended implementation PR

**Scope:** make the existing `muse orchestrate` surface honest by
wiring the runtime to the artefacts the docs already specify. Land
just enough behavior change so that `/model-router explain` reads the
real registry, `/decision-ledger show` reads a real SQLite table, and
`/ai-radar update` invokes the real radar skill. Defer end-to-end
worker execution and Android UI to follow-on PRs.

**Concretely (one PR):**

1. `hermes_cli/model_router.py` — pure function
   `route(request: RouteRequest) -> RouteDecision`. Reads
   `docs/ai-intelligence/model-registry.yaml`. Applies
   `docs/ai-intelligence/model-routing-policy.md` rules. Returns an
   ordered candidate list with fallback chain and a justification
   string. Replaces the keyword table in
   `hermes_cli/orchestrator.py:model_router_explain`.

2. `hermes_cli/decision_ledger.py` — SQLite-backed append-only ledger.
   Schema in `docs/orchestration/decision-ledger.md` (§ "Storage").
   Migration from the legacy
   `~/.hermes/orchestrator/decision_ledger.json` (preserve, do not
   delete). New `replay(id)` semantics that re-derive a `RouteDecision`
   from stored inputs without re-running the worker.

3. `hermes_cli/orchestrator.py` — small surgical changes only:
   - `model_router_explain` delegates to `hermes_cli.model_router.route`.
   - Ledger writes go through `hermes_cli.decision_ledger.append`.
   - `ai_radar_update` invokes the `/ai-improvement-radar` skill rather
     than stamping a placeholder JSON.

4. `apps/android/docs/ORCHESTRATOR_API.md` — document (do not
   implement) the HTTP surface listed in §12.

5. Tests under `tests/orchestrator/`:
   - `test_model_router.py` — decision-table tests against the committed
     registry + policy.
   - `test_decision_ledger.py` — append/list/show/replay round-trip;
     append-only invariant; migration of the legacy JSON.
   - `test_orchestrator_router_integration.py` — `/model-router explain`
     returns the new shape; back-compat for the legacy keyword output is
     preserved behind a flag.

**Out of scope** for that next PR (explicitly):

- End-to-end worker execution beyond "queued" / "scaffolded".
- AI-improvement radar implementation beyond invoking the existing
  skill.
- Competitive feature harvester automation.
- Android Jobs / Decision Ledger / Radar Proposals UI (Kotlin side).
- Remote sync of the decision ledger.

The exact copy/paste prompt that implements this scope lives in
[`docs/orchestration/NEXT_PHASE_IMPLEMENTATION_PROMPT.md`](./NEXT_PHASE_IMPLEMENTATION_PROMPT.md).

---

## 17. Exact next Claude Code prompt for the next PR

The full prompt is maintained as its own file so it can be pasted
directly into a fresh Claude Code session without dragging this
report's narrative along:

> [`docs/orchestration/NEXT_PHASE_IMPLEMENTATION_PROMPT.md`](./NEXT_PHASE_IMPLEMENTATION_PROMPT.md)

Open that file, copy the fenced block, and paste it into Claude Code
on a fresh `claude/hermes-router-ledger-radar-wire-<suffix>` branch.

— end of Phase 10 report —
